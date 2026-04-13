"""
rental/invoice_service.py — Automatski račun iz Bookinga

Kreira Invoice iz bookinga, veže za RentalInvoice,
dodaje u ArhivaEntry za 11-godišnju zaštitu.
"""

import logging
from decimal import Decimal

from django.db import DatabaseError, IntegrityError

logger = logging.getLogger(__name__)


def create_rental_invoice(booking) -> "RentalInvoice":
    """
    Kreira Invoice iz bookinga i veže ga za RentalInvoice.
    Koristi postojeći invoicing.Invoice model.
    """
    from invoicing.models import Invoice, InvoiceItem
    from rental.models import RentalInvoice

    nights = (booking.check_out - booking.check_in).days
    if nights < 1:
        nights = 1

    acc_total = booking.price_per_night * nights

    guest_count = booking.guests.count() if hasattr(booking, "guests") else booking.guest_count
    if not guest_count:
        guest_count = 1

    tt_total = booking.rental_property.tourist_tax * guest_count * nights
    cleaning = booking.rental_property.cleaning_fee or Decimal("0")
    total = acc_total + tt_total + cleaning

    # Kreira Invoice
    company = booking.rental_property.company
    invoice = Invoice.objects.create(
        company=company,
        doctype="R",
        client_name=booking.guest_name,
        client_email=booking.guest_email or "",
        date_issued=booking.actual_check_out.date() if booking.actual_check_out else booking.check_out,
        date_due=booking.actual_check_out.date() if booking.actual_check_out else booking.check_out,
        subtotal=acc_total + cleaning,
        tax_amount=Decimal("0"),
        total=total,
        tax_percent=Decimal("0"),
        currency="EUR",
        note=f"Boravak: {booking.check_in} — {booking.check_out} | {booking.rental_property.name}",
    )

    # Stavke
    InvoiceItem.objects.create(
        invoice=invoice,
        description=f"Smještaj {booking.rental_property.name} ({nights} noći × {booking.price_per_night}€)",
        quantity=nights,
        unit="noć",
        unit_price=booking.price_per_night,
        total_price=acc_total,
        tax_rate=Decimal("0"),
    )

    if tt_total > 0:
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"Boravišna pristojba ({guest_count} os. × {nights} noći × {booking.rental_property.tourist_tax}€)",
            quantity=1,
            unit="pau",
            unit_price=tt_total,
            total_price=tt_total,
            tax_rate=Decimal("0"),
        )

    if cleaning > 0:
        InvoiceItem.objects.create(
            invoice=invoice,
            description="Naknada za čišćenje",
            quantity=1,
            unit="pau",
            unit_price=cleaning,
            total_price=cleaning,
            tax_rate=Decimal("0"),
        )

    # RentalInvoice
    ri = RentalInvoice.objects.create(
        booking=booking,
        invoice=invoice,
        accommodation_total=acc_total,
        tourist_tax_total=tt_total,
        cleaning_fee=cleaning,
        total=total,
    )

    # TrafficRecord (EP Obrazac)
    from rental.models import TrafficRecord

    TrafficRecord.objects.create(
        company=company,
        rental_property=booking.rental_property,
        booking=booking,
        date=invoice.date_issued,
        invoice_number=invoice.number or f"R-{invoice.pk}",
        guest_name=booking.guest_name,
        amount=acc_total + cleaning,
        tourist_tax=tt_total,
        total=total,
    )

    # ArhivaEntry
    try:
        from documents.models import ArhivaEntry

        ArhivaEntry.objects.create(
            company=company,
            source_type="rental_invoice",
            source_id=str(invoice.pk),
            doc_number=invoice.number or f"R-{invoice.pk}",
            doc_date=invoice.date_issued,
            partner_name=booking.guest_name,
            amount=total,
            currency="EUR",
        )
    except (IntegrityError, DatabaseError) as e:
        logger.warning("ArhivaEntry creation failed for rental invoice: %s", e)

    logger.info(
        "RentalInvoice created: %s — %s, %d noći, %.2f EUR",
        booking.guest_name,
        booking.rental_property.name,
        nights,
        float(total),
    )

    return ri
