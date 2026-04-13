"""Propter Celery taskovi."""

import logging

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger("propter.tasks")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="propter.tasks.auto_close_billing_periods")
def auto_close_billing_periods(self):
    """Zatvori OPEN periode prethodnog mj. i kreiraj zbirne racune.
    Celery beat: 1. u mj. u 06:00.
    """
    try:
        from propter.services.aggregate import auto_close_previous

        results = auto_close_previous()
        ok = [r for r in results if r.get("status") == "OK"]
        err = [r for r in results if r.get("status") == "ERROR"]
        logger.info("auto_close: %d OK, %d ERROR", len(ok), len(err))
        return {"ok": len(ok), "errors": len(err), "results": results}
    except ImportError as exc:
        logger.error("auto_close_billing_periods: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="propter.tasks.send_zbirni_eracun")
def send_zbirni_eracun(billing_period_id, user_pk=None):
    """Posalji zbirni e-Racun na FINA CIS async."""
    try:
        from eracun.models import ERacun
        from eracun.services.engine import process_eracun
        from propter.models import BillingPeriod

        period = BillingPeriod.objects.get(pk=billing_period_id)
        if not period.zbirni_eracun_id:
            return {"success": False, "message": "Period nema zbirni e-Racun"}

        eracun = ERacun.objects.get(pk=period.zbirni_eracun_id)
        user = None
        if user_pk:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(pk=user_pk).first()

        success, message = process_eracun(eracun, user=user)
        return {"success": success, "message": message, "eracun": eracun.invoice_number}
    except ObjectDoesNotExist as exc:
        logger.error("send_zbirni_eracun: %s", exc)
        return {"success": False, "message": str(exc)}


@shared_task(name="propter.tasks.recalculate_eko_stats")
def recalculate_eko_stats(billing_period_id):
    """Recalculate EkoStats za period (npr. nakon korekcije otpremnica)."""
    try:
        from propter.models import BillingPeriod, EkoStats

        period = BillingPeriod.objects.get(pk=billing_period_id)
        eko = EkoStats.calculate(period)
        return {"badge": eko.badge_level, "co2_saved": float(eko.co2_saved_grams)}
    except ObjectDoesNotExist as exc:
        logger.error("recalculate_eko_stats: %s", exc)
        return {"error": str(exc)}


@shared_task(name="propter.generate_monthly_sammelrechnung", bind=True, max_retries=2)
def generate_monthly_sammelrechnung(self):
    """
    Pokreće se 1. u mjesecu u 06:00.
    Za svaku firmu s otvorenim BillingPeriod-om prošlog mjeseca:
    1. Grupira Otpremnice po partneru (recipient_oib)
    2. Kreira Invoice doctype='ZR' (Zbirni Račun / Sammelrechnung)
    3. Stavke: popis svih OTP-a s datumima
    4. Zatvara BillingPeriod
    """
    import datetime

    from django.db.models import Count, Sum
    from django.utils import timezone

    from invoicing.models import Invoice
    from propter.models import BillingPeriod, Otpremnica

    # Prošli mjesec
    today = timezone.now().date()
    if today.month == 1:
        target_year, target_month = today.year - 1, 12
    else:
        target_year, target_month = today.year, today.month - 1

    periods = BillingPeriod.objects.filter(
        year=target_year,
        month=target_month,
        status=BillingPeriod.Status.OPEN,
        otpremnica_count__gt=0,
    ).select_related("company")

    generated = 0

    for period in periods:
        try:
            otps = Otpremnica.objects.filter(
                billing_period=period,
                status=Otpremnica.Status.ISSUED,
            ).order_by("issue_date")

            if not otps.exists():
                period.status = BillingPeriod.Status.CLOSED
                period.closed_at = timezone.now()
                period.save(update_fields=["status", "closed_at"])
                continue

            # Grupiraj po partneru
            partners = otps.values("recipient_oib", "recipient_name").distinct()

            for partner in partners:
                partner_otps = otps.filter(
                    recipient_oib=partner["recipient_oib"],
                    recipient_name=partner["recipient_name"],
                )

                totals = partner_otps.aggregate(
                    subtotal=Sum("subtotal"),
                    tax=Sum("tax_amount"),
                    total=Sum("total"),
                    count=Count("id"),
                )

                company = period.company

                # Generiraj broj
                zr_count = (
                    Invoice.objects.filter(
                        company=company,
                        doctype="ZR",
                    ).count()
                    + 1
                )
                zr_num = "ZR-%d-%04d" % (target_year, zr_count)

                # Popis OTP-a
                otp_lines = "\n".join(
                    [
                        "OTP-%s (isporuka: %s) — %s EUR"
                        % (otp.number, (otp.delivery_date or otp.issue_date).strftime("%d.%m.%Y"), otp.total)
                        for otp in partner_otps
                    ]
                )

                # Datum isporuke: najraniji i najkasniji iz otpremnica
                delivery_dates = [otp.delivery_date or otp.issue_date for otp in partner_otps]
                first_delivery = min(delivery_dates)
                last_delivery = max(delivery_dates)
                supply_period = "%s — %s" % (
                    first_delivery.strftime("%d.%m.%Y"),
                    last_delivery.strftime("%d.%m.%Y"),
                )

                note = (
                    "Zbirni racun / Sammelrechnung za period %02d/%d\n"
                    "Razdoblje isporuke (Date of Supply): %s\n"
                    "Ukljucuje %d otpremnica:\n%s"
                ) % (target_month, target_year, supply_period, totals["count"], otp_lines)

                # Datum isporuke = zadnji dan prethodnog mjeseca (zakonski: Date of Supply)
                import calendar

                last_day = calendar.monthrange(target_year, target_month)[1]
                date_of_supply = datetime.date(target_year, target_month, last_day)

                # Kreiraj Invoice ZR (skip fiscal check)
                zr = Invoice(
                    company=company,
                    doctype="ZR",
                    number=zr_num,
                    date_issued=timezone.now(),
                    date_delivery=date_of_supply,
                    date_due=timezone.now().date() + datetime.timedelta(days=30),
                    client_name=partner["recipient_name"] or "Razni kupci",
                    client_oib=partner["recipient_oib"] or "",
                    subtotal=totals["subtotal"] or 0,
                    tax_amount=totals["tax"] or 0,
                    total=totals["total"] or 0,
                    status="DRAFT",
                    note=note,
                    internal_note="[Auto-generated] BillingPeriod %s, Supply: %s" % (period.pk, supply_period),
                    country=getattr(company, "country", "HR") or "HR",
                )
                zr._skip_fiscal_check = True
                zr.save()

                # OTP-i → AGGREGATED
                partner_otps.update(status=Otpremnica.Status.AGGREGATED)

                generated += 1
                logger.info("ZR %s kreiran za %s (%s OTP)", zr_num, company.name, totals["count"])

            # Zatvori period
            period.status = BillingPeriod.Status.INVOICED
            period.invoiced_at = timezone.now()
            period.save(update_fields=["status", "invoiced_at"])

        except (IntegrityError, DatabaseError) as e:
            logger.error("Sammelrechnung failed for period %s: %s", period.pk, e)
            continue

    return {"generated": generated, "periods_processed": periods.count()}
