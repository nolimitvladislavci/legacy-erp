"""Django signals — auto-send on invoice finalize."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("propter.einvoice.signals")


@receiver(post_save, sender="invoicing.Invoice")
def on_invoice_status_change(sender, instance, **kwargs):
    from einvoice.models import AS4Message, MessageDirection, MessageStatus, TransportConfiguration
    from einvoice.services.transport_router import TransportRouter
    from einvoice.tasks.outbound_tasks import send_invoice_task

    # Trigger on FISCALIZED or SENT status
    if instance.status not in ("FISCALIZED", "SENT"):
        return
    # Skip invoices without company (test/anonymous invoices)
    if instance.company is None:
        return

    try:
        config = TransportConfiguration.objects.get(company=instance.company)
        if not config.auto_send_on_finalize:
            return
    except TransportConfiguration.DoesNotExist:
        pass

    # Don't duplicate
    if (
        AS4Message.objects.filter(
            invoice=instance,
            direction=MessageDirection.OUTBOUND,
        )
        .exclude(status__in=[MessageStatus.CANCELLED, MessageStatus.REJECTED])
        .exists()
    ):
        return

    # Get OIBs
    receiver_oib = instance.client_oib or ""
    sender_oib = instance.company.oib if instance.company else ""

    router = TransportRouter()
    decision = router.resolve(
        company_id=str(instance.company_id),
        sender_oib=sender_oib,
        receiver_oib=receiver_oib,
    )

    # Determine document type
    doc_type = "INVOICE"
    if hasattr(instance, "doc_type") and instance.doc_type in ("STORNO", "CREDIT_NOTE"):
        doc_type = "CREDIT_NOTE"

    message = AS4Message(
        company=instance.company,
        invoice=instance,
        direction=MessageDirection.OUTBOUND,
        transport=decision.transport,
        sender_participant_id=f"9934:{sender_oib}",
        receiver_participant_id=f"9934:{receiver_oib}",
        sender_name=instance.company.name if instance.company else "",
        receiver_name=instance.client_name or "",
        document_type=doc_type,
        invoice_number=instance.number,
        invoice_amount=instance.total,
        invoice_currency=getattr(instance, "currency", "EUR"),
        status=MessageStatus.DRAFT,
        metadata={
            "routing_decision": {
                "transport": decision.transport,
                "reason": decision.reason,
                "backend": decision.backend_name,
            }
        },
    )
    # Note: UBL XML generation will be added in Day 3-4
    # For now, just create the message record without XML
    message.save()
    message.transition_to(MessageStatus.QUEUED, detail=f"Routing: {decision.reason}")

    send_invoice_task.delay(str(message.id))
    logger.info(f"Invoice {instance.number} queued via {decision.backend_name}")
