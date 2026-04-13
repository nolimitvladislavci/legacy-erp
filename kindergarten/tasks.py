"""
Kindergarten Celery tasks — automatizacija notifikacija i naplate.

4 taska:
- send_daily_report_notification: email + WhatsApp kad se objavi izvjestaj
- send_absence_alert: "Vase dijete danas odsutno" @ 10:00
- send_billing_reminder: 5 dana prije due_date
- generate_monthly_billings: 1. u mjesecu, automatski za sve aktivne
"""

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("kindergarten.tasks")


@shared_task(name="kindergarten.send_daily_report_notification")
def send_daily_report_notification():
    """Posalji notifikaciju roditeljima kad odgajateljica objavi dnevni izvjestaj."""
    from kindergarten.models import ChildGuardian, DailyReport

    today = timezone.now().date()
    reports = DailyReport.objects.filter(
        date=today,
        is_published=True,
    ).select_related("group", "group__company")

    sent = 0
    for report in reports:
        # Find all children in this group
        children = report.group.children.filter(status="active")
        for child in children:
            # Get guardians
            guardians = ChildGuardian.objects.filter(
                child=child,
                is_primary=True,
            ).select_related("guardian")

            for cg in guardians:
                guardian = cg.guardian
                if guardian.phone:
                    try:
                        from core.whatsapp import send_text

                        msg = (
                            f"*Dnevni izvjestaj — {report.group.name}*\n"
                            f"{report.date.strftime('%d.%m.%Y')}\n\n"
                            f"{report.content[:300]}"
                        )
                        send_text(
                            phone=guardian.phone,
                            message=msg,
                            company_id=str(report.group.company.pk),
                        )
                        sent += 1
                    except ImportError as e:
                        logger.debug("Report notification error: %s", e)

    logger.info("Daily report notifications: %d sent", sent)
    return {"sent": sent}


@shared_task(name="kindergarten.send_absence_alert")
def send_absence_alert():
    """Posalji alert roditeljima cije dijete je danas odsutno. Radni dani 10:00."""
    from kindergarten.models import Attendance, ChildGuardian

    today = timezone.now().date()
    # Skip weekends
    if today.weekday() >= 5:
        return {"skipped": "weekend"}

    absences = Attendance.objects.filter(
        date=today,
        status__in=["sick", "excused", "unexcused"],
    ).select_related("child", "child__group", "child__company")

    sent = 0
    for att in absences:
        guardians = ChildGuardian.objects.filter(
            child=att.child,
            is_primary=True,
        ).select_related("guardian")

        for cg in guardians:
            guardian = cg.guardian
            if guardian.phone:
                try:
                    from core.whatsapp import send_text

                    status_text = att.get_status_display()
                    msg = (
                        f"Postovani {guardian.first_name},\n\n"
                        f"{att.child.first_name} {att.child.last_name} "
                        f"je danas evidentiran/a kao: *{status_text}*."
                    )
                    if att.note:
                        msg += f"\nNapomena: {att.note}"
                    send_text(
                        phone=guardian.phone,
                        message=msg,
                        company_id=str(att.child.company_id),
                    )
                    sent += 1
                except ImportError as e:
                    logger.debug("Absence alert error: %s", e)

    logger.info("Absence alerts: %d sent", sent)
    return {"sent": sent}


@shared_task(name="kindergarten.send_billing_reminder")
def send_billing_reminder():
    """Posalji podsjetnik za placanje 5 dana prije due_date."""
    from kindergarten.models import ChildGuardian, MonthlyBilling

    target_date = timezone.now().date() + timedelta(days=5)
    billings = MonthlyBilling.objects.filter(
        due_date=target_date,
        status__in=["draft", "sent"],
    ).select_related("child", "child__group", "child__company")

    sent = 0
    for billing in billings:
        guardians = ChildGuardian.objects.filter(
            child=billing.child,
            is_billing_contact=True,
        ).select_related("guardian")

        if not guardians.exists():
            guardians = ChildGuardian.objects.filter(
                child=billing.child,
                is_primary=True,
            ).select_related("guardian")

        for cg in guardians:
            guardian = cg.guardian
            if guardian.phone:
                try:
                    from core.whatsapp import send_text

                    msg = (
                        f"Postovani {guardian.first_name},\n\n"
                        f"Podsjecamo na placanje za {billing.child.first_name} "
                        f"({billing.month}/{billing.year}).\n"
                        f"Iznos: *{billing.total_amount} EUR*\n"
                        f"Rok: {billing.due_date.strftime('%d.%m.%Y')}\n"
                        f"Poziv na broj: {billing.payment_reference}"
                    )
                    send_text(
                        phone=guardian.phone,
                        message=msg,
                        company_id=str(billing.child.company_id),
                    )
                    sent += 1
                except ImportError as e:
                    logger.debug("Billing reminder error: %s", e)

    logger.info("Billing reminders: %d sent", sent)
    return {"sent": sent}


@shared_task(name="kindergarten.generate_monthly_billings")
def generate_monthly_billings():
    """
    Generiraj mjesecne naplate za sve aktivne djece.
    Pokrece se 1. u mjesecu za prethodni mjesec.
    Automatski kreira Invoice u invoicing modulu.
    """
    from kindergarten.models import Child, MonthlyBilling

    now = timezone.now()
    # Previous month
    if now.month == 1:
        bill_month, bill_year = 12, now.year - 1
    else:
        bill_month, bill_year = now.month - 1, now.year

    children = Child.objects.filter(
        status="active",
        group__isnull=False,
    ).select_related("group", "company")

    created = 0
    invoiced = 0

    for child in children:
        # Skip if billing already exists
        if MonthlyBilling.objects.filter(child=child, year=bill_year, month=bill_month).exists():
            continue

        billing = MonthlyBilling(
            child=child,
            year=bill_year,
            month=bill_month,
        )
        billing.calculate()
        billing.due_date = now.date().replace(day=15)
        billing.status = "sent"
        billing.save()
        created += 1

        # Create Invoice
        invoice = _create_invoice_from_billing(billing)
        if invoice:
            billing.invoice = invoice
            billing.save(update_fields=["invoice"])
            invoiced += 1

    logger.info(
        "Monthly billings generated: %d created, %d invoiced (for %d/%d)",
        created,
        invoiced,
        bill_month,
        bill_year,
    )
    return {"created": created, "invoiced": invoiced, "month": bill_month, "year": bill_year}


def _create_invoice_from_billing(billing):
    """Create invoicing.Invoice from MonthlyBilling."""
    try:
        from invoicing.models import Invoice, InvoiceItem
        from kindergarten.models import ChildGuardian

        child = billing.child
        company = child.company

        # Find billing contact guardian
        cg = (
            ChildGuardian.objects.filter(
                child=child,
                is_billing_contact=True,
            )
            .select_related("guardian")
            .first()
        )

        if not cg:
            cg = (
                ChildGuardian.objects.filter(
                    child=child,
                    is_primary=True,
                )
                .select_related("guardian")
                .first()
            )

        if not cg:
            return None

        guardian = cg.guardian

        invoice = Invoice.objects.create(
            company=company,
            number=f"VRT-{billing.year}{billing.month:02d}-{child.pk}",
            date_issued=timezone.now(),
            date_due=billing.due_date,
            client_name=f"{guardian.first_name} {guardian.last_name}",
            client_oib=guardian.oib or "",
            client_email=guardian.email or "",
            client_address=guardian.address or "",
            subtotal=billing.total_amount,
            tax_percent=Decimal("25"),
            tax_amount=billing.total_amount * Decimal("0.25"),
            total=billing.total_amount * Decimal("1.25"),
            status="SENT",
            payment_method="TRANSAKCIJSKI",
            reference_number=billing.payment_reference,
            doctype="R",
            note=f"Vrtic: {child.first_name} {child.last_name}, {billing.month}/{billing.year}",
        )

        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"Boravak u vrticu — {child.first_name} {child.last_name} ({billing.month}/{billing.year})",
            quantity=1,
            unit_price=billing.base_amount,
            tax_rate=Decimal("25"),
            total_price=billing.base_amount,
        )

        if billing.meal_deduction > 0:
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Odbitak obroka ({billing.days_absent} dana izostanka)",
                quantity=1,
                unit_price=-billing.meal_deduction,
                tax_rate=Decimal("25"),
                total_price=-billing.meal_deduction,
            )

        return invoice

    except (ValueError, TypeError) as e:
        logger.warning("Invoice creation from billing failed: %s", e)
        return None
