"""
Propter agregacijski servis.

Pipeline:
    POS/Invoice/Synesis --> Otpremnica --> BillingPeriod --> zbirni ERacun --> FINA CIS

Kljucni tokovi:
    create_from_pos_receipt()  -- auto-kreira otpremnicu iz POS bona
    create_from_invoice()      -- auto-kreira otpremnicu iz fakture
    close_period()             -- zakljucaj period, izracunaj iznose
    aggregate_to_eracun()      -- kreiraj zbirni e-Racun iz perioda
    auto_close_previous()      -- Celery: 1. u mj. zatvori prethodni
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("propter.aggregate")


def create_from_pos_receipt(receipt):
    """Kreira Otpremnicu iz PAID POS bona. Idempotentno."""
    from propter.models import Otpremnica, OtpremnicaItem, BillingPeriod

    # Idempotentno -- provjeri postoji li vec
    existing = Otpremnica.objects.filter(pos_receipt_id=str(receipt.pk)).first()
    if existing:
        return existing

    company = receipt.session.terminal.company

    with transaction.atomic():
        otp = Otpremnica(
            company=company,
            pos_receipt_id=str(receipt.pk),
            issue_date=timezone.now().date(),
            recipient_name=getattr(receipt, "customer_name", "") or "Gotovinska prodaja",
            recipient_oib=getattr(receipt, "customer_oib", "") or "",
            subtotal=receipt.subtotal,
            tax_amount=receipt.tax_amount,
            total=receipt.total,
            source=Otpremnica.Source.POS,
            status=Otpremnica.Status.ISSUED,
            note="Auto iz POS bona #{}".format(receipt.receipt_number),
        )
        otp.save()

        for idx, item in enumerate(receipt.items.all(), 1):
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                line_number=idx,
                description=item.description,
                quantity=item.quantity,
                unit=getattr(item, "unit", "EA") or "EA",
                unit_price=item.unit_price,
                tax_rate=item.tax_rate or Decimal("25"),
                line_total=item.total_price,
            )

    logger.info("Otpremnica %s iz POS bona %s", otp.number, receipt.receipt_number)
    return otp


def create_from_invoice(invoice):
    """Kreira Otpremnicu iz LIMIT Connect Invoice. Idempotentno."""
    from propter.models import Otpremnica, OtpremnicaItem

    existing = Otpremnica.objects.filter(invoice_id=str(invoice.pk)).first()
    if existing:
        return existing

    with transaction.atomic():
        otp = Otpremnica(
            company=invoice.company,
            invoice_id=str(invoice.pk),
            issue_date=getattr(invoice, "date_issued", timezone.now()).date()
                       if hasattr(invoice, "date_issued") else timezone.now().date(),
            delivery_date=getattr(invoice, "date_delivery", None),
            recipient_name=invoice.client_name or "",
            recipient_oib=invoice.client_oib or "",
            recipient_address=invoice.client_address or "",
            subtotal=invoice.subtotal or Decimal("0"),
            tax_amount=invoice.tax_amount or Decimal("0"),
            total=invoice.total or Decimal("0"),
            source=Otpremnica.Source.INVOICE,
            status=Otpremnica.Status.ISSUED,
            note="Auto iz fakture {}".format(getattr(invoice, "number", invoice.pk)),
        )
        otp.save()

        for idx, item in enumerate(invoice.items.all(), 1):
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                line_number=idx,
                description=item.description,
                quantity=item.quantity or Decimal("1"),
                unit="EA",
                unit_price=item.unit_price or Decimal("0"),
                tax_rate=item.tax_rate or Decimal("25"),
                line_total=item.total_price or Decimal("0"),
            )

    logger.info("Otpremnica %s iz fakture %s", otp.number, invoice.pk)
    return otp


def close_period(period, user=None):
    """Zakljucaj period: izracunaj iznose, postavi CLOSED."""
    from propter.models import Otpremnica

    if period.status not in (period.Status.OPEN, period.Status.CLOSING):
        raise ValueError("Period {} nije OPEN/CLOSING (je: {})".format(period, period.status))

    with transaction.atomic():
        qs = period.otpremnice.filter(
            status__in=(Otpremnica.Status.ISSUED, Otpremnica.Status.DRAFT)
        )
        total_net   = sum(o.subtotal for o in qs) or Decimal("0")
        total_tax   = sum(o.tax_amount for o in qs) or Decimal("0")
        total_gross = sum(o.total for o in qs) or Decimal("0")

        period.total_net        = total_net
        period.total_tax        = total_tax
        period.total_with_tax   = total_gross
        period.otpremnica_count = qs.count()
        period.status           = period.Status.CLOSED
        period.closed_at        = timezone.now()
        period.save()

    logger.info("Period %s zatvoren: %d otp, %.2f EUR bruto",
                period, period.otpremnica_count, period.total_with_tax)
    return period


def aggregate_to_eracun(period, user=None):
    """
    Iz CLOSED perioda kreira zbirni e-Racun i salje na FINA CIS.

    Novi zakon: otpremnice kroz mjesec, jedan zajednicki racun
    jednom mjesecno kroz pristupnu tocku.
    Svaki klijent potpisuje VLASTITIM certifikatom.
    """
    from propter.models import Otpremnica, EkoStats
    from eracun.models import ERacun, ERacunItem, ERacunTaxSummary

    # Idempotentno: ako je vec INVOICED, vrati postojeci e-Racun
    if period.zbirni_eracun_id:
        logger.warning("Period %s vec ima zbirni e-Racun", period)
        return ERacun.objects.filter(pk=period.zbirni_eracun_id).first()

    company = period.company
    otpremnice = period.otpremnice.filter(
        status__in=(Otpremnica.Status.ISSUED, Otpremnica.Status.DRAFT)
    ).prefetch_related("items")

    if not otpremnice.exists():
        raise ValueError("Nema otpremnica u periodu za agregaciju")

    import calendar
    period_name = "{} {}".format(calendar.month_name[period.month], period.year)

    with transaction.atomic():
        eracun = ERacun.objects.create(
            company=company,
            doc_type="380",
            invoice_number="ZBIRNI-{}-{:02d}-{}".format(
                period.year, period.month, company.oib
            ),
            issue_date=timezone.now().date(),
            currency="EUR",
            issuer_name=company.name,
            issuer_oib=company.oib,
            issuer_address=getattr(company, "address", "") or "",
            recipient_name=company.name,
            recipient_oib=company.oib,
            subtotal=period.total_net,
            tax_amount=period.total_tax,
            total=period.total_with_tax,
            payment_means_code="30",
            note="Zbirni e-Racun za period: {}. Otpremnica: {}.".format(
                period_name, period.otpremnica_count
            ),
            created_by=user,
        )

        line_num = 1
        tax_groups = {}

        for otp in otpremnice:
            for item in otp.items.all():
                ERacunItem.objects.create(
                    eracun=eracun,
                    line_number=line_num,
                    description="{} (OTP {})".format(item.description, otp.number),
                    quantity=item.quantity,
                    unit_code=item.unit or "EA",
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    tax_category="S",
                    tax_rate=item.tax_rate,
                )
                line_num += 1
                key = float(item.tax_rate)
                if key not in tax_groups:
                    tax_groups[key] = {"taxable": Decimal("0"), "tax": Decimal("0")}
                tax_groups[key]["taxable"] += item.line_total
                tax_groups[key]["tax"] += item.line_total * item.tax_rate / 100

        for rate, amounts in tax_groups.items():
            ERacunTaxSummary.objects.create(
                eracun=eracun,
                tax_category="S",
                tax_rate=Decimal(str(rate)),
                taxable_amount=amounts["taxable"].quantize(Decimal("0.01")),
                tax_amount=amounts["tax"].quantize(Decimal("0.01")),
            )

        # Povezi period
        period.zbirni_eracun_id      = str(eracun.pk)
        period.zbirni_invoice_number = eracun.invoice_number
        period.status                = period.Status.INVOICED
        period.invoiced_at           = timezone.now()
        period.save(update_fields=[
            "zbirni_eracun_id", "zbirni_invoice_number",
            "status", "invoiced_at"
        ])

        # Oznaci otpremnice
        otpremnice.update(status=Otpremnica.Status.AGGREGATED)

        # Izracunaj eko statistiku
        try:
            EkoStats.calculate(period)
        except Exception as e:
            logger.warning("EkoStats greska za %s: %s", period, e)

    logger.info("Zbirni e-Racun %s kreiran za %s (%d stavki, %.2f EUR)",
                eracun.invoice_number, period, line_num - 1, float(eracun.total))

    # Async posalji na FINA CIS
    try:
        from propter.tasks import send_zbirni_eracun
        send_zbirni_eracun.delay(period.pk)
        logger.info("send_zbirni_eracun task pokrenut za period %s", period.pk)
    except Exception as e:
        logger.warning("Nije moguce pokrenuti send_zbirni_eracun: %s", e)

    return eracun


def auto_close_previous():
    """
    Zatvori OPEN periode prethodnog mjeseca i kreiraj zbirne racune.
    Poziva Celery beat: 1. u mj. u 06:00.
    """
    from propter.models import BillingPeriod

    now = timezone.now()
    prev_year  = now.year if now.month > 1 else now.year - 1
    prev_month = now.month - 1 if now.month > 1 else 12

    open_periods = BillingPeriod.objects.filter(
        year=prev_year, month=prev_month,
        status__in=(BillingPeriod.Status.OPEN, BillingPeriod.Status.CLOSING)
    ).select_related("company")

    results = []
    for period in open_periods:
        try:
            close_period(period)
            eracun = aggregate_to_eracun(period)
            results.append({
                "company": period.company.name,
                "period": str(period),
                "eracun": eracun.invoice_number,
                "total": float(eracun.total),
                "status": "OK",
            })
        except Exception as e:
            logger.error("Greska pri zatvaranju perioda %s: %s", period, e)
            results.append({
                "company": period.company.name,
                "period": str(period),
                "status": "ERROR",
                "error": str(e),
            })

    logger.info("auto_close_previous: %d perioda obradjeno", len(results))
    return results
