"""
DeepSeek Code Patrol — noćni autonomni code reviewer.
Skenira sve naše Django appove, traži stvarne probleme,
zapisuje kao ImprovementSuggestion → Trojstvo evaluira.

Pokretanje:
  manage.py deepseek_patrol            # sve appove
  manage.py deepseek_patrol --app pos  # samo jedan app
  manage.py deepseek_patrol --dry-run  # bez pisanja u bazu
  manage.py deepseek_patrol --force    # čak i ako je danas već pokrenuto

Troškovi: ~83 appova × ~2000 tok = ~166K tok/noć ≈ $0.02
"""

import logging
import textwrap
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger("deepseek_patrol")

SKIP_LABELS = {
    "admin",
    "auth",
    "contenttypes",
    "sessions",
    "messages",
    "staticfiles",
    "humanize",
    "rosetta",
    "modeltranslation",
    "rest_framework",
    "drf_spectacular",
    "import_export",
    "django_celery_beat",
    "django_celery_results",
    "channels",
    "daphne",
    "silk",
    "authtoken",
}

TARGET_FILES = [
    "models.py",
    "views.py",
    "views_arhiva.py",
    "views_scan.py",
    "tasks.py",
    "serializers.py",
    "forms.py",
    "admin.py",
]

MAX_LINES_PER_FILE = 400
VALID_CATEGORIES = {"bug", "security", "performance", "code_quality", "workflow", "ux", "other"}

PRIORITY_APPS = [
    "pos",
    "documents",
    "companies",
    "accounts",
    "core",
    "fiscal",
    "fiskalizacija",
    "finance",
    "invoicing",
    "partners",
]

SYSTEM_COMPANY_ID = "52e2e048-fd94-401e-8259-fd0cb245f24c"

_SYSTEM_PROMPT = (
    "Ti si senior Django/Python code reviewer. "
    "Trazis KONKRETNE, STVARNE probleme u kodu — ne apstraktne savjete. "
    "Svaki nalaz mora imati specificnu lokaciju u kodu. "
    "Ako nema problema, vracas prazan JSON niz []. "
    "Odgovaras ISKLJUCIVO validnim JSON-om bez ikakve dodatne prose."
)


class Command(BaseCommand):
    help = "DeepSeek Code Patrol — autonomni nocni code review"

    def add_arguments(self, parser):
        parser.add_argument("--app", type=str, help="Skeniraj samo ovaj app")
        parser.add_argument("--dry-run", action="store_true", help="Ispisi nalaze bez pisanja u bazu")
        parser.add_argument("--max-apps", type=int, default=83)
        parser.add_argument(
            "--min-priority", type=int, default=3, help="Max prioritetni broj (1=kriticno, 3=srednje, 5=sve)"
        )
        parser.add_argument("--force", action="store_true", help="Pokreni cak i ako je danas vec pokrenuto")

    def handle(self, *args, **options):
        from core.deepseek_client import deepseek_direct

        dry_run = options["dry_run"]
        target_app = options.get("app")
        max_apps = options["max_apps"]
        min_priority = options["min_priority"]
        force = options["force"]

        self.stdout.write(self.style.SUCCESS("DeepSeek Code Patrol — START" + (" [DRY RUN]" if dry_run else "")))

        if not force and not dry_run and _already_ran_today():
            self.stdout.write(self.style.WARNING("Patrol je danas vec pokrenuto. --force za ponovni run."))
            return

        patrol_user, system_company = _ensure_patrol_user()
        all_apps = _get_our_apps()

        if target_app:
            all_apps = [a for a in all_apps if a.label == target_app]
            if not all_apps:
                self.stdout.write(self.style.ERROR(f"App '{target_app}' nije pronadjen"))
                return

        all_apps = sorted(all_apps, key=lambda a: PRIORITY_APPS.index(a.label) if a.label in PRIORITY_APPS else 99)[
            :max_apps
        ]

        total_suggestions = 0
        total_files = 0
        total_tokens_est = 0

        for app_config in all_apps:
            app_path = Path(app_config.path)
            files_to_scan = [app_path / fname for fname in TARGET_FILES if (app_path / fname).exists()]
            if not files_to_scan:
                continue

            for fpath in files_to_scan:
                code = _read_and_trim(fpath)
                if not code or len(code.splitlines()) < 20:
                    continue

                total_files += 1
                tokens_est = len(code) // 4
                total_tokens_est += tokens_est

                self.stdout.write(f"  {app_config.label}/{fpath.name} ({len(code.splitlines())} ln, ~{tokens_est} tok)")

                try:
                    raw = deepseek_direct(
                        prompt=_build_prompt(app_config.label, fpath.name, code),
                        system=_SYSTEM_PROMPT,
                        max_tokens=1200,
                        temperature=0.1,
                    )
                    findings = _parse_findings(raw)
                except Exception as e:
                    logger.error("Patrol error %s/%s: %s", app_config.label, fpath.name, e)
                    self.stdout.write(self.style.ERROR(f"    ERROR: {e}"))
                    continue

                # Filtriraj po prioritetu i dedupliciraj
                findings = [f for f in findings if f.get("priority", 5) <= min_priority]
                findings = _deduplicate(findings, app_config.label, fpath.name)

                for finding in findings:
                    total_suggestions += 1
                    emoji = {1: "KRITIČNO", 2: "VISOKO", 3: "SREDNJE", 4: "NISKO", 5: "INFO"}.get(
                        finding["priority"], "?"
                    )
                    self.stdout.write(f"    [{emoji}][{finding['category']}] {finding['title']}")
                    if not dry_run:
                        _save_finding(finding, app_config.label, fpath.name, patrol_user, system_company)

        cost_usd = total_tokens_est / 1_000_000 * 0.27
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"PATROL DONE: {total_files} fajlova, {total_suggestions} nalaza, "
                f"~{total_tokens_est:,} tokena (~${cost_usd:.4f})"
            )
        )
        if not dry_run and total_suggestions > 0:
            self.stdout.write(f"Trojstvo evaluira {total_suggestions} nalaza u pozadini (Celery)")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_our_apps():
    result = []
    for app_config in apps.get_app_configs():
        if app_config.label in SKIP_LABELS:
            continue
        path = getattr(app_config, "path", "") or ""
        if "venv" in path or "site-packages" in path:
            continue
        result.append(app_config)
    return result


def _read_and_trim(fpath: Path) -> str:
    try:
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return ""
    cleaned = [line.rstrip() for line in lines if line.strip() and not line.strip().startswith("#")]
    if len(cleaned) > MAX_LINES_PER_FILE:
        cleaned = cleaned[:MAX_LINES_PER_FILE]
        cleaned.append(f"# ... {len(lines) - MAX_LINES_PER_FILE} linija izostavljeno")
    return "\n".join(cleaned)


def _build_prompt(app_label: str, filename: str, code: str) -> str:
    return textwrap.dedent(f"""
        App: {app_label} | Fajl: {filename}

        Analiziraj Django kod. Trazi SAMO stvarne probleme (ne stilske preferencije):
        1. N+1 query (ORM bez select_related/prefetch_related u petljama)
        2. Nedostajuci DB indeksi (ForeignKey bez db_index, cesti filteri bez indeksa)
        3. Sigurnosni problemi (missing @login_required, csrf_exempt bez razloga, raw SQL)
        4. Mrtvi kod (funkcije/klase koje se nigdje ne koriste)
        5. Nekonzistentne permission provjere

        Vrati JSON listu (SAMO JSON, bez ikakve prose):
        [
          {{
            "title": "Kratki opis max 100 znakova",
            "description": "Konkretno: linija/funkcija, zasto je problem, kako popraviti",
            "category": "bug|security|performance|code_quality",
            "priority": 1-5,
            "line_hint": "ime funkcije ili ~linija"
          }}
        ]

        Ako nema problema: []

        ```python
        {code}
        ```
    """).strip()


def _parse_findings(raw: str) -> list:
    import json

    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.lstrip("json").strip()
            if part.startswith("["):
                raw = part
                break
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    try:
        findings = json.loads(raw[start:end])
    except json.JSONDecodeError:
        logger.warning("Patrol: JSON parse fail: %s", raw[:200])
        return []

    result = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        title = str(f.get("title", "")).strip()[:200]
        desc = str(f.get("description", "")).strip()[:2000]
        category = f.get("category", "other")
        if category not in VALID_CATEGORIES:
            category = "code_quality"
        priority = max(1, min(5, int(f.get("priority", 3))))
        line_hint = str(f.get("line_hint", "")).strip()[:100]
        if title and desc:
            result.append(
                {
                    "title": title,
                    "description": desc + (f"\n\nLokacija: {line_hint}" if line_hint else ""),
                    "category": category,
                    "priority": priority,
                }
            )
    return result


def _deduplicate(findings: list, app_label: str, filename: str) -> list:
    from datetime import timedelta
    from django.utils import timezone
    from pos.models import ImprovementSuggestion

    recent = set(
        ImprovementSuggestion.objects.filter(
            source="system",
            created_at__gte=timezone.now() - timedelta(days=7),
            admin_note__icontains=f"patrol:{app_label}",
        ).values_list("title", flat=True)
    )
    return [f for f in findings if f["title"] not in recent]


def _save_finding(finding: dict, app_label: str, filename: str, patrol_user, system_company):
    from pos.models import ImprovementSuggestion
    from pos.trojstvo_task import trojstvo_rijesi

    with transaction.atomic():
        s = ImprovementSuggestion.objects.create(
            company=system_company,
            author=patrol_user,
            source="system",
            title=finding["title"],
            description=finding["description"],
            category=finding["category"],
            priority=finding["priority"],
            status="new",
            admin_note=(f"[patrol:{app_label}/{filename}] Auto-generiran — DeepSeek Code Patrol"),
        )
    trojstvo_rijesi.delay(s.pk)
    logger.info("Patrol nalaz #%s: %s", s.pk, finding["title"])


def _ensure_patrol_user():
    from companies.models import Company

    User = get_user_model()
    patrol_user, created = User.objects.get_or_create(
        username="deepseek_patrol",
        defaults={
            "first_name": "DeepSeek",
            "last_name": "Patrol",
            "email": "patrol@limit-connect.com",
            "is_active": True,
            "is_staff": False,
        },
    )
    if created:
        patrol_user.set_unusable_password()
        patrol_user.save()
        logger.info("Kreiran deepseek_patrol user")
    system_company = Company.objects.filter(pk=SYSTEM_COMPANY_ID).first() or Company.objects.first()
    return patrol_user, system_company


def _already_ran_today() -> bool:
    from datetime import date
    from pos.models import ImprovementSuggestion

    return ImprovementSuggestion.objects.filter(
        source="system",
        admin_note__icontains="patrol:",
        created_at__date=date.today(),
    ).exists()
