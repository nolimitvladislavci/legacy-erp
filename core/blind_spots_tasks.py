"""
core/blind_spots_tasks.py — Adversarial Blind Spots Audit

Nočni Celery job (02:30): pronađi što korisnici traže ali ne nalaze.
Zero-result upiti → fuzzy klasteriranje → BlindSpotReport.
Tjedni digest → WhatsApp Ivanu ponedjeljkom 08:00.

Ovo je "sustav koji ispituje sebe" — adversarial self-audit.
"""

import logging
import uuid
from difflib import SequenceMatcher

from celery import shared_task
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class BlindSpotReport(models.Model):
    """
    Klaster zero-result upita koji čekaju akciju.
    Admin može označiti kao resolved nakon što doda odgovarajuće zapise.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        related_name="blind_spot_reports",
    )
    cluster_query = models.CharField(max_length=300, help_text="Reprezentativni upit klastera")
    hit_count = models.PositiveIntegerField(default=0, help_text="Broj zero-result upita u klasteru")
    sample_queries = models.JSONField(default=list, help_text="Do 10 primjernih upita iz klastera")
    suggested_action = models.TextField(blank=True, help_text="AI prijedlog akcije")
    reported_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=100, blank=True)

    class Meta:
        app_label = "core"
        verbose_name = "Blind Spot Report"
        verbose_name_plural = "Blind Spot Reports"
        ordering = ["-reported_at"]
        indexes = [
            models.Index(fields=["resolved", "reported_at"]),
        ]

    def __str__(self):
        status = "✅" if self.resolved else "🔴"
        return f"{status} '{self.cluster_query[:40]}' ({self.hit_count} pogodaka)"

    def mark_resolved(self, resolved_by: str = "") -> None:
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.save(update_fields=["resolved", "resolved_at", "resolved_by"])


@shared_task(name="core.blind_spots_audit", bind=True, max_retries=1)
def blind_spots_audit_task(self):
    """
    Nočni audit — 02:30 svaki dan.
    Pronađi zero-result klastere iz zadnjih 30 dana i spremi BlindSpotReport.
    """
    from datetime import timedelta

    from companies.models import Company

    from .search_audit_models import SearchAuditLog

    since_30d = timezone.now() - timedelta(days=30)
    total_reports = 0

    companies = Company.objects.filter(is_active=True).values_list("pk", flat=True)
    for company_pk in companies:
        try:
            n = _audit_company(company_pk, since_30d, SearchAuditLog)
            total_reports += n
        except Exception as exc:
            logger.warning("Blind spots audit failed for company %s: %s", company_pk, exc)

    logger.info("Blind spots audit complete: %d new reports created", total_reports)
    return {"reports_created": total_reports}


def _audit_company(company_pk, since, SearchAuditLog) -> int:
    """Audit jedna firma."""
    from django.db.models import Count

    # Zero-result upiti zadnjih 30 dana
    zero_queries = list(
        SearchAuditLog.objects.filter(
            company_id=company_pk,
            result_count=0,
            searched_at__gte=since,
        )
        .values("query")
        .annotate(cnt=Count("id"))
        .filter(cnt__gte=2)  # min 2 pokušaja — jedan može biti typo
        .order_by("-cnt")[:50]  # max 50 clustera
    )

    if not zero_queries:
        return 0

    # Fuzzy klasteriranje — SequenceMatcher
    clusters = _cluster_queries([(r["query"], r["cnt"]) for r in zero_queries])

    reports_created = 0
    for cluster_q, count, samples in clusters:
        if count < 3:
            continue  # premali klaster
        # Provjeri postoji li već neriješeni report
        existing = BlindSpotReport.objects.filter(
            company_id=company_pk,
            cluster_query=cluster_q,
            resolved=False,
        ).first()
        if existing:
            existing.hit_count = count
            existing.sample_queries = samples
            existing.save(update_fields=["hit_count", "sample_queries"])
        else:
            BlindSpotReport.objects.create(
                company_id=company_pk,
                cluster_query=cluster_q,
                hit_count=count,
                sample_queries=samples,
                suggested_action=_suggest_action(cluster_q),
            )
            reports_created += 1

    return reports_created


def _cluster_queries(query_counts: list[tuple]) -> list[tuple]:
    """
    Grupiraj slične upite u klastere.
    Vraća listu (representative_query, total_count, sample_list).
    """
    clusters = []  # [(rep, total_count, [samples])]
    used = set()

    for i, (q1, c1) in enumerate(query_counts):
        if q1 in used:
            continue
        cluster = [(q1, c1)]
        used.add(q1)

        for j, (q2, c2) in enumerate(query_counts):
            if j <= i or q2 in used:
                continue
            sim = SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
            if sim >= 0.65:
                cluster.append((q2, c2))
                used.add(q2)

        total = sum(c for _, c in cluster)
        rep = max(cluster, key=lambda x: x[1])[0]  # najčešći = representativni
        samples = [q for q, _ in cluster[:10]]
        clusters.append((rep, total, samples))

    clusters.sort(key=lambda x: x[1], reverse=True)
    return clusters[:10]  # top 10


def _suggest_action(query: str) -> str:
    """Rule-based prijedlog akcije bez AI troška."""
    q = query.lower()
    if any(w in q for w in ["faktur", "račun", "invoice"]):
        return "Korisnici traže fakturu koja ne postoji ili nije uknjižena. Provjeri arhivu i eRačune."
    if any(w in q for w in ["ugovor", "contract", "sporazum"]):
        return "Nedostaje ugovor u arhivi. Dodaj ugovor za ovog partnera."
    if any(w in q for w in ["partner", "dobavljač", "supplier", "klijent", "client"]):
        return "Ovaj partner/klijent nije u sustavu. Dodaj tvrtku u komitente."
    if any(w in q for w in ["zaposleni", "radnik", "employee", "djelatnik"]):
        return "Traženi zaposlenik nije u HR modulu. Provjeri evidenciju radnika."
    if any(w in q for w in ["pdv", "porez", "tax"]):
        return "PDV/porezni dokument nije u arhivi. Dodaj odgovarajući dokument."
    return f"'{query[:50]}' nije pronađeno. Provjeri postoji li odgovarajući zapis ili dodaj nedostajući sadržaj."


@shared_task(name="core.blind_spots_weekly_digest", bind=True, max_retries=1)
def blind_spots_weekly_digest_task(self):
    """
    Tjedni digest — ponedjeljak 08:00.
    Šalje WhatsApp poruku Ivanu s top 5 slijepih točaka.
    """
    from datetime import timedelta

    since_week = timezone.now() - timedelta(days=7)
    top_reports = BlindSpotReport.objects.filter(
        resolved=False,
        reported_at__gte=since_week,
    ).order_by("-hit_count")[:5]

    if not top_reports:
        logger.info("Blind spots digest: nema novih izvještaja ovog tjedna")
        return {"sent": False, "reason": "no_reports"}

    lines = ["🔍 *Blind Spots tjedni pregled* — TOP slijepe točke:"]
    for i, r in enumerate(top_reports, 1):
        lines.append(f"\n{i}. *{r.cluster_query[:40]}* ({r.hit_count}× bez rezultata)")
        if r.suggested_action:
            lines.append(f"   → {r.suggested_action[:80]}")

    lines.append("\n\nPogledaj sve: https://fina-connect.online/hr/admin/blind-spots/")
    message = "\n".join(lines)

    # WhatsApp via WAHA
    try:
        import requests as _req

        _req.post(
            "http://localhost:3000/api/sendText",
            json={
                "chatId": "385989999999@c.us",  # Ivan — zamijeni s pravim brojem
                "text": message,
                "session": "default",
            },
            timeout=10,
        )
        logger.info("Blind spots digest sent via WhatsApp")
        return {"sent": True, "reports": len(top_reports)}
    except Exception as exc:
        logger.warning("WhatsApp send failed: %s", exc)
        return {"sent": False, "reason": str(exc)}
