"""
invoicing/services/events.py
Audit trail za Invoice lifecycle — InvoiceEvent kreiranje.
"""
import logging

logger = logging.getLogger(__name__)


def log_invoice_event(invoice, event_type, title, detail='', metadata=None, actor=None, ip_address=None):
    """
    Log an audit event on an invoice.

    Args:
        invoice: Invoice instance
        event_type: str (created, fiscalized, sent, storno, etc.)
        title: str - human-readable title
        detail: str - detailed info
        metadata: dict - JSON-serializable extra data
        actor: User instance
        ip_address: str
    """
    try:
        from invoicing.models import InvoiceEvent
        InvoiceEvent.objects.create(
            invoice=invoice,
            event_type=event_type,
            title=title,
            detail=detail,
            metadata=metadata or {},
            actor=actor,
            updated_by=actor,
            client_ip=ip_address,
        )
    except Exception as e:
        logger.warning(f'InvoiceEvent {event_type} failed: {e}')
