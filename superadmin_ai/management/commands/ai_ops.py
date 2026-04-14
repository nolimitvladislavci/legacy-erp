"""
Claude Code ↔ SuperAdmin AI — Operativna naredba.

Korištenje:
    python manage.py ai_ops status          # Pregled svih servisa
    python manage.py ai_ops health          # Django + DB + Redis + Celery health check
    python manage.py ai_ops permissions     # Pregled AI dozvola po modulima
    python manage.py ai_ops diagnose        # Kompletna dijagnostika svih strana
    python manage.py ai_ops logs [--last N] # Zadnjih N AI logova
    python manage.py ai_ops patrol          # Pokreni AI patrol odmah
    python manage.py ai_ops pending         # Prikaži čekajuće akcije
    python manage.py ai_ops exec <module> <action> [--desc "opis"]  # Izvrši akciju kroz gate
    python manage.py ai_ops sites           # Provjeri sve domene/sajtove
"""

import socket
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Claude Code ↔ SuperAdmin AI operativni centar"

    def add_arguments(self, parser):
        parser.add_argument(
            "action", type=str, help="Akcija: status|health|permissions|diagnose|logs|patrol|pending|exec|sites"
        )
        parser.add_argument("args_extra", nargs="*", help="Dodatni argumenti")
        parser.add_argument("--last", type=int, default=20, help="Broj zadnjih logova")
        parser.add_argument("--desc", type=str, default="", help="Opis za exec akciju")

    def handle(self, *args, **options):
        action = options["action"]
        handler = getattr(self, f"_do_{action}", None)
        if not handler:
            raise CommandError(
                f"Nepoznata akcija: {action}. Dostupne: status, health, permissions, diagnose, logs, patrol, pending, exec, sites"
            )
        handler(options)

    # ── STATUS ──────────────────────────────────────────────────
    def _do_status(self, options):
        """Pregled svih systemd servisa i portova."""
        services = [
            "gunicorn-fina",
            "celery-worker",
            "celery-beat",
            "razbibriga-ai",
            "razbibriga-ws",
            "nginx",
            "redis-server",
            "postgresql@16-main",
            "mysql",
            "php8.3-fpm",
        ]
        self.stdout.write(self.style.HTTP_INFO("\n═══ SERVIS STATUS ═══"))
        for svc in services:
            try:
                result = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
                status = result.stdout.strip()
                style = self.style.SUCCESS if status == "active" else self.style.ERROR
                self.stdout.write(f"  {svc:30s} {style(status)}")
            except (ValueError, AttributeError) as e:
                self.stdout.write(f"  {svc:30s} {self.style.ERROR(str(e))}")

        # Ports
        self.stdout.write(self.style.HTTP_INFO("\n═══ PORTOVI ═══"))
        ports = {
            8000: "Gunicorn",
            8001: "Razbibriga AI",
            3001: "WebSocket",
            6379: "Redis",
            5432: "PostgreSQL",
            3306: "MySQL",
            3000: "WAHA",
        }
        for port, name in ports.items():
            alive = self._check_port(port)
            style = self.style.SUCCESS if alive else self.style.WARNING
            status = "OPEN" if alive else "CLOSED"
            self.stdout.write(f"  :{port:<6d} {name:20s} {style(status)}")

    # ── HEALTH ──────────────────────────────────────────────────
    def _do_health(self, options):
        """Django health check — DB, Redis, Celery, migracije, disk."""
        self.stdout.write(self.style.HTTP_INFO("\n═══ HEALTH CHECK ═══"))

        # DB
        try:
            with connection.cursor() as c:
                c.execute("SELECT 1")
            self.stdout.write(f"  PostgreSQL:  {self.style.SUCCESS('OK')}")
        except Exception as e:
            self.stdout.write(f"  PostgreSQL:  {self.style.ERROR(str(e))}")

        # Redis
        try:
            from django.core.cache import cache

            cache.set("_health", "ok", 10)
            val = cache.get("_health")
            status = "OK" if val == "ok" else f"FAIL (got {val})"
            style = self.style.SUCCESS if val == "ok" else self.style.ERROR
            self.stdout.write(f"  Redis/Cache: {style(status)}")
        except ImportError as e:
            self.stdout.write(f"  Redis/Cache: {self.style.ERROR(str(e))}")

        # Celery
        try:
            result = subprocess.run(
                ["/var/www/fina-connect/venv/bin/celery", "-A", "core", "inspect", "ping", "--timeout", "5"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd="/var/www/fina-connect",
            )
            if "pong" in result.stdout.lower():
                self.stdout.write(f"  Celery:      {self.style.SUCCESS('OK (pong)')}")
            else:
                self.stdout.write(f"  Celery:      {self.style.WARNING('NO RESPONSE')}")
        except Exception as e:
            self.stdout.write(f"  Celery:      {self.style.ERROR(str(e))}")

        # Pending migrations
        try:
            from io import StringIO

            from django.core.management import call_command

            out = StringIO()
            call_command("showmigrations", "--plan", stdout=out)
            content = out.getvalue()
            unapplied = [l for l in content.splitlines() if l.strip().startswith("[ ]")]
            if unapplied:
                self.stdout.write(f"  Migracije:   {self.style.WARNING(f'{len(unapplied)} neapplied')}")
                for m in unapplied[:5]:
                    self.stdout.write(f"    {m.strip()}")
            else:
                self.stdout.write(f"  Migracije:   {self.style.SUCCESS('Sve OK')}")
        except ImportError as e:
            self.stdout.write(f"  Migracije:   {self.style.ERROR(str(e))}")

        # Disk
        try:
            result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                usage = parts[4] if len(parts) > 4 else "?"
                avail = parts[3] if len(parts) > 3 else "?"
                pct = int(usage.replace("%", "")) if "%" in usage else 0
                style = self.style.SUCCESS if pct < 80 else self.style.WARNING if pct < 90 else self.style.ERROR
                self.stdout.write(f"  Disk:        {style(f'{usage} used, {avail} free')}")
        except (ValueError, TypeError):
            pass

    # ── PERMISSIONS ─────────────────────────────────────────────
    def _do_permissions(self, options):
        """Pregled AI dozvola."""
        from superadmin_ai.models import AIModulePermission

        perms = AIModulePermission.objects.filter(company=None).order_by("module")
        self.stdout.write(self.style.HTTP_INFO("\n═══ AI MODULE PERMISSIONS (global) ═══"))
        self.stdout.write(f"  {'Modul':<25s} {'R':>3s} {'W':>3s} {'C':>3s} {'M':>3s}  {'Level'}")
        self.stdout.write(f"  {'─' * 25} {'─' * 3} {'─' * 3} {'─' * 3} {'─' * 3}  {'─' * 12}")
        levels = {0: "DISABLED", 1: "READ_ONLY", 2: "ASSISTED", 3: "AUTONOMOUS"}
        for p in perms:
            r = "✓" if p.can_read else "✗"
            w = "✓" if p.can_write else "✗"
            c = "✓" if p.can_create else "✗"
            m = "✓" if p.can_modify else "✗"
            lvl = levels.get(p.access_level, "?")
            self.stdout.write(f"  {p.module:<25s} {r:>3s} {w:>3s} {c:>3s} {m:>3s}  {lvl}")

    # ── DIAGNOSE ────────────────────────────────────────────────
    def _do_diagnose(self, options):
        """Kompletna dijagnostika svih strana."""
        self._do_health(options)
        self._do_status(options)
        self._do_sites(options)
        self._do_pending(options)

        # Quick stats
        from superadmin_ai.models import AIActionLog

        today = timezone.now().date()
        today_count = AIActionLog.objects.filter(timestamp__date=today).count()
        blocked = AIActionLog.objects.filter(timestamp__date=today, outcome="blocked").count()
        self.stdout.write(self.style.HTTP_INFO("\n═══ AI AKTIVNOST DANAS ═══"))
        self.stdout.write(f"  Ukupno operacija: {today_count}")
        self.stdout.write(f"  Blokiranih:       {blocked}")

    # ── LOGS ────────────────────────────────────────────────────
    def _do_logs(self, options):
        """Zadnjih N AI logova."""
        from superadmin_ai.models import AIActionLog

        n = options.get("last", 20)
        logs = AIActionLog.objects.select_related("company", "user").order_by("-timestamp")[:n]
        self.stdout.write(self.style.HTTP_INFO(f"\n═══ ZADNJIH {n} AI LOGOVA ═══"))
        for log in logs:
            ts = log.timestamp.strftime("%d.%m %H:%M")
            user = log.user.username if log.user else "-"
            outcome_style = {
                "allowed": self.style.SUCCESS,
                "blocked": self.style.ERROR,
                "queued": self.style.WARNING,
                "executed": self.style.SUCCESS,
                "failed": self.style.ERROR,
            }.get(log.outcome, self.style.WARNING)
            self.stdout.write(
                f"  {ts} | {log.module:<20s} | {log.action_type:<15s} | {outcome_style(log.outcome):<12s} | {user}"
            )

    # ── PATROL ──────────────────────────────────────────────────
    def _do_patrol(self, options):
        """Pokreni AI patrol odmah."""
        self.stdout.write(self.style.HTTP_INFO("\n═══ POKRETANJE AI PATROLA ═══"))
        try:
            from ai_assistant.patrol import run_patrol
            from companies.models import Company

            companies = Company.objects.all()
            for company in companies:
                self.stdout.write(f"  Patrol za: {company.name}...")
                try:
                    report = run_patrol(company)
                    issues = "⚠ ISSUES" if report.has_issues else "✓ OK"
                    self.stdout.write(
                        f"    → {issues} ({report.finding_count} findings, {report.critical_count} critical)"
                    )
                except Exception as e:
                    self.stdout.write(f"    → {self.style.ERROR(str(e)[:100])}")
            self.stdout.write(self.style.SUCCESS("  Patrol završen."))
        except DatabaseError as e:
            self.stdout.write(self.style.ERROR(f"  Greška: {e}"))

    # ── PENDING ─────────────────────────────────────────────────
    def _do_pending(self, options):
        """Prikaži čekajuće AI akcije."""
        from superadmin_ai.models import PendingAIAction

        actions = PendingAIAction.objects.filter(status="pending").order_by("-created_at")[:20]
        self.stdout.write(self.style.HTTP_INFO(f"\n═══ ČEKAJUĆE AI AKCIJE ({actions.count()}) ═══"))
        if not actions:
            self.stdout.write("  Nema čekajućih akcija.")
            return
        for a in actions:
            ts = a.created_at.strftime("%d.%m %H:%M")
            self.stdout.write(f"  {ts} | {a.module:<20s} | {a.action_type:<15s} | {a.description[:60]}")

    # ── EXEC ────────────────────────────────────────────────────
    def _do_exec(self, options):
        """Izvrši akciju kroz AI Gate."""
        extra = options.get("args_extra", [])
        if len(extra) < 2:
            raise CommandError('Korištenje: ai_ops exec <module> <action> [--desc "opis"]')
        module, action_type = extra[0], extra[1]
        desc = options.get("desc", "") or f"Claude Code exec: {action_type} u {module}"

        from superadmin_ai.services import ai_gate

        result = ai_gate.check(company=None, module=module, action_type=action_type, description=desc)
        if result.allowed:
            self.stdout.write(self.style.SUCCESS(f"✓ ALLOWED: {result.message}"))
        elif result.queued:
            self.stdout.write(self.style.WARNING(f"⏳ QUEUED: {result.message}"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ BLOCKED: {result.message}"))

    # ── SITES ───────────────────────────────────────────────────
    def _do_sites(self, options):
        """Provjeri sve domene — HTTP status + SSL."""
        import ssl
        import urllib.request

        sites = [
            ("https://limit-connect.com", "ERP Primary"),
            ("https://fina-connect.online", "Stara domena (301?)"),
            ("https://viskovic-group.de", "Holding (301?)"),
            ("https://sati.ink", "Dating platforma"),
            ("https://grosmarkt-online.eu", "B2B Tržnica"),
        ]
        self.stdout.write(self.style.HTTP_INFO("\n═══ SITE STATUS ═══"))
        for url, label in sites:
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Claude-AI-Ops/1.0")
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    code = resp.status
                style = self.style.SUCCESS if code in (200, 301, 302) else self.style.WARNING
                self.stdout.write(f"  {url:<40s} {style(str(code))} {label}")
            except urllib.error.HTTPError as e:
                self.stdout.write(f"  {url:<40s} {self.style.WARNING(str(e.code))} {label}")
            except (FileNotFoundError, PermissionError, IOError) as e:
                err = str(e)[:50]
                self.stdout.write(f"  {url:<40s} {self.style.ERROR('FAIL')} {label} ({err})")

    # ── Helpers ─────────────────────────────────────────────────
    def _check_port(self, port, host="127.0.0.1"):
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
