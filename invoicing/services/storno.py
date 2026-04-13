"""
invoicing/services/storno.py
Storno (cancellation) logic — creates reverse invoice.
"""

from django.db import transaction
from django.utils import timezone

from .events import log_invoice_event


@transaction.atomic
def create_storno(original, user=None, ip_address=None, cancel_reason=""):
    """
    Create a storno invoice for the original.

    Returns:
        dict: {success: bool, storno_invoice: Invoice, message: str}
    """
    from invoicing.models import Invoice, InvoiceItem

    if original.status == "STORNO":
        return {"success": False, "message": "Racun je vec storniran"}

    storno = Invoice.objects.create(
        company=original.company,
        doctype="S",
        country=original.country,
        number=f"S-{original.number}",
        date_issued=timezone.now(),
        client_name=original.client_name,
        client_address=original.client_address,
        client_oib=original.client_oib,
        client_email=original.client_email,
        payment_method=original.payment_method,
        currency=original.currency,
        issuer_name=original.issuer_name,
        issuer_address=original.issuer_address,
        issuer_oib=original.issuer_oib,
        issuer_iban=original.issuer_iban,
        issuer_email=original.issuer_email,
        subtotal=-original.subtotal,
        tax_percent=original.tax_percent,
        tax_amount=-original.tax_amount,
        total=-original.total,
        note=f"Storno racuna {original.number}",
        storno_of=original,
        status="DRAFT",
        created_by=user,
        cancel_reason=cancel_reason,
    )

    for item in original.items.all():
        InvoiceItem.objects.create(
            invoice=storno,
            description=f"[STORNO] {item.description}",
            quantity=-item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            total_price=-item.total_price,
            tax_rate=item.tax_rate,
        )

    original.status = "STORNO"
    original.cancel_reason = cancel_reason
    original.save(update_fields=["status", "cancel_reason"])

    log_invoice_event(
        original,
        "storno",
        f"Storniran — kreiran {storno.number}",
        detail=cancel_reason,
        actor=user,
        ip_address=ip_address,
    )
    log_invoice_event(storno, "created", f"Storno kreiran za {original.number}", actor=user, ip_address=ip_address)

    return {"success": True, "storno_invoice": storno, "message": f"Storno {storno.number} kreiran"}
