"""
invoicing/services/confirm.py
Invoice confirmation and locking logic.
"""

from .events import log_invoice_event
from .fiscalize import lock_invoice


def confirm_invoice(invoice, user=None, ip_address=None):
    """
    Confirm a draft invoice — sets status, locks if fiscalized.

    Returns:
        dict: {success: bool, message: str}
    """
    if invoice.status not in ("DRAFT", "draft"):
        return {"success": False, "message": f"Racun nije u DRAFT statusu (status={invoice.status})"}

    invoice.status = "CONFIRMED"
    lock_invoice(invoice)
    invoice.save(update_fields=["status", "is_locked", "deletion_protected_until"])

    log_invoice_event(
        invoice,
        event_type="confirmed",
        title="Racun potvrdjen",
        actor=user,
        ip_address=ip_address,
    )

    return {"success": True, "message": f"Racun {invoice.number} potvrdjen"}
