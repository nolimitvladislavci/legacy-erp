"""
companies/tasks.py — Celery tasks za data quality.
"""

import logging

from celery import shared_task

logger = logging.getLogger("companies.tasks")


@shared_task(name="companies.async_fill_company_address", bind=True, max_retries=1, soft_time_limit=30)
def async_fill_company_address(self, company_pk):
    """Auto-fill prazne adrese iz partnera ili VIES-a."""
    from django.db.models import Q

    from companies.models import Company
    from partners.models import Partner

    try:
        company = Company.objects.get(pk=company_pk)
    except Company.DoesNotExist:
        return

    if company.address and company.city:
        return  # Već popunjeno

    oib = (company.oib or "").strip()
    if not oib or len(oib) != 11:
        return

    # 1. Iz partnera
    partner = (
        Partner.objects.filter(oib=oib).exclude(Q(address__isnull=True) | Q(address="")).order_by("-updated_at").first()
    )

    if partner:
        updated = []
        if not company.address and partner.address:
            company.address = partner.address
            updated.append("address")
        if not company.city and partner.city:
            company.city = partner.city
            updated.append("city")
        if not company.zip_code and partner.zip_code:
            company.zip_code = partner.zip_code
            updated.append("zip_code")
        if updated:
            updated.append("updated_at")
            company.save(update_fields=updated)
            logger.info("Auto-fill %s from partner: %s", company.name, ", ".join(updated))
        return

    # 2. VIES lookup
    try:
        from core.business_lookup import lookup_business

        result = lookup_business(oib, "HR")
        if result.found and result.address:
            updated = []
            if not company.address:
                company.address = result.address
                updated.append("address")
            if not company.city and result.city:
                company.city = result.city
                updated.append("city")
            if not company.zip_code and result.zip_code:
                company.zip_code = result.zip_code
                updated.append("zip_code")
            if updated:
                updated.append("updated_at")
                company.save(update_fields=updated)
                logger.info("Auto-fill %s from VIES: %s", company.name, ", ".join(updated))
    except ImportError as e:
        logger.warning("VIES auto-fill failed for %s: %s", company.name, e)


@shared_task(name="companies.nightly_data_quality", bind=True, max_retries=0, soft_time_limit=120)
def nightly_data_quality(self):
    """Noćna provjera kvalitete podataka — popuni rupe + alertiraj."""
    from io import StringIO

    from django.core.management import call_command

    # 1. Pokušaj popuniti iz partnera
    out = StringIO()
    call_command("fill_company_addresses", stdout=out)
    out.getvalue()

    # 2. Izračunaj score
    from companies.data_quality import check_data_quality_report

    report = check_data_quality_report()

    # 3. Alert ako ima rupa
    if report["no_address"] > 0:
        from core.notify import notify

        notify(
            "INFO",
            (
                f"📊 *Data Quality Report*\n\n"
                f"Score: *{report['quality_score']}%*\n"
                f"Ukupno firmi: {report['total']}\n"
                f"Bez adrese: {report['no_address']}\n"
                f"Bez grada: {report['no_city']}\n"
                f"Bez ZIP: {report['no_zip']}\n"
                f"Bez emaila: {report['no_email']}\n\n"
                f"Auto-fill pokrenuo."
            ),
        )

    return report


@shared_task(name="companies.check_license_tokens", bind=True, max_retries=0, soft_time_limit=60)
def check_license_tokens(self):
    """
    Svakih 6h provjerava LicenseToken status.
    - Istekao valid_until → prebaci u grace (14 dana)
    - Istekao grace_until → prebaci u suspended
    - Suspended → označi WhiteLabel kao neaktivan
    """
    from datetime import timedelta

    from django.utils import timezone

    from companies.models import LicenseToken

    now = timezone.now()
    results = {"checked": 0, "to_grace": 0, "to_suspended": 0}

    for token in LicenseToken.objects.exclude(status__in=("cancelled",)):
        results["checked"] += 1

        if token.status == "active" and now > token.valid_until:
            # Active → Grace (14 dana)
            token.status = "grace"
            token.grace_until = now + timedelta(days=14)
            token.save(update_fields=["status", "grace_until", "updated_at"])
            results["to_grace"] += 1
            logger.warning("License %s → GRACE (14d). Brand: %s", token.pk, token.white_label.brand_name)

        elif token.status == "grace" and token.grace_until and now > token.grace_until:
            # Grace → Suspended
            token.status = "suspended"
            token.save(update_fields=["status", "updated_at"])
            results["to_suspended"] += 1
            logger.warning("License %s → SUSPENDED. Brand: %s", token.pk, token.white_label.brand_name)

            # Označi WL kao neaktivan
            wl = token.white_label
            if hasattr(wl, "is_active"):
                wl.is_active = False
                wl.save(update_fields=["is_active"])

    if results["to_grace"] or results["to_suspended"]:
        from core.notify import notify

        notify(
            "WARN",
            (
                f"⚠️ *License Check*\n"
                f"Provjereno: {results['checked']}\n"
                f"→ Grace: {results['to_grace']}\n"
                f"→ Suspended: {results['to_suspended']}"
            ),
        )

    logger.info("License check: %s", results)
    return results
