"""Celery tasks for outbound invoice sending — D5 upgrade.

Features:
- Uses OutboundPipeline for generate->validate->route->submit
- Dead Letter Queue for permanently failed messages
- Prometheus metrics
- Bulk send support
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("propter.einvoice.tasks.outbound")

# DLQ threshold — messages with more retries go to DLQ
DLQ_MAX_RETRIES = 5


@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def send_invoice_task(self, message_id):
    """Send a single invoice through transport pipeline."""
    from einvoice.models import AS4Message, MessageStatus
    from einvoice.services.transport_router import TransportRouter
    from einvoice.services.metrics import record_sent, record_retry

    try:
        message = AS4Message.objects.get(id=message_id)
    except AS4Message.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {"error": "Message not found"}

    if message.is_terminal:
        return {"status": message.status}

    # If message has UBL XML, skip generation (pipeline already ran)
    # Just route and submit
    router = TransportRouter()
    decision = router.resolve(
        company_id=str(message.company_id),
        sender_oib=message.sender_oib,
        receiver_oib=message.receiver_oib,
    )
    backend = router.get_backend(decision.transport)
    message.transport = decision.transport
    message.save(update_fields=["transport"])

    logger.info(f"Sending {message.invoice_number} via {decision.backend_name}")

    try:
        external_id = backend.submit(message)
        record_sent(decision.transport, "SUBMITTED")
        return {"status": "submitted", "external_id": external_id}
    except Exception as exc:
        logger.error(f"Send failed for {message.invoice_number}: {exc}")
        record_sent(decision.transport, "FAILED")

        if message.can_retry():
            record_retry(decision.transport)
            delay = [60, 300, 900, 3600, 14400][min(self.request.retries, 4)]
            raise self.retry(exc=exc, countdown=delay)
        else:
            # Move to DLQ
            _move_to_dlq(message, str(exc))
            return {"status": "dlq", "error": str(exc)}


@shared_task
def send_via_pipeline_task(invoice_id, user_id=None, profile="HR"):
    """Full pipeline task: Invoice -> UBL -> Validate -> Route -> Submit."""
    from einvoice.services.outbound_pipeline import OutboundPipeline
    from invoicing.models import Invoice
    from django.contrib.auth.models import User
    from einvoice.services.metrics import record_pipeline_stage
    import time

    try:
        invoice = Invoice.objects.select_related("company").get(id=invoice_id)
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return {"error": "Invoice not found"}

    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    pipeline = OutboundPipeline()
    start = time.time()

    try:
        message = pipeline.process_invoice(invoice, user=user, profile=profile)
        duration = time.time() - start
        record_pipeline_stage("full", duration)

        return {
            "status": message.status,
            "message_id": str(message.id),
            "invoice_number": invoice.number,
            "duration_ms": int(duration * 1000),
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Pipeline failed for Invoice {invoice_id}: {e}")
        return {"error": str(e)}


@shared_task
def bulk_send_task(invoice_ids, user_id=None, profile="HR"):
    """Bulk send multiple invoices through pipeline."""
    from einvoice.services.outbound_pipeline import OutboundPipeline
    from invoicing.models import Invoice
    from django.contrib.auth.models import User

    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    invoices = Invoice.objects.filter(id__in=invoice_ids).select_related("company")
    pipeline = OutboundPipeline()
    results = pipeline.bulk_send(invoices, user=user, profile=profile)

    summary = {
        "total": len(results),
        "success": sum(1 for _, m, e in results if m and not e),
        "failed": sum(1 for _, m, e in results if e),
        "details": [
            {
                "invoice": inv.number,
                "status": msg.status if msg else "ERROR",
                "error": err,
            }
            for inv, msg, err in results
        ],
    }
    logger.info(f"Bulk send: {summary['success']}/{summary['total']} successful")
    return summary


@shared_task
def process_retry_queue():
    """Pick up RETRY messages. Also moves expired retries to DLQ."""
    from einvoice.models import AS4Message, MessageStatus
    from einvoice.services.metrics import update_queue_gauges

    now = timezone.now()

    # Process retryable messages
    retry_ids = list(
        AS4Message.objects.filter(status=MessageStatus.RETRY, next_retry_at__lte=now)
        .values_list("id", flat=True)[:50]
    )
    for msg_id in retry_ids:
        send_invoice_task.delay(str(msg_id))

    # Move permanently failed to DLQ
    dlq_candidates = AS4Message.objects.filter(
        status__in=[MessageStatus.SEND_FAILED, MessageStatus.RETRY],
        retry_count__gte=DLQ_MAX_RETRIES,
    )[:20]
    for message in dlq_candidates:
        _move_to_dlq(message, "Iscrpljeni svi pokusaji nakon DLQ_MAX_RETRIES")

    # Update Prometheus gauges
    update_queue_gauges()

    if retry_ids:
        logger.info(f"Retry queue: {len(retry_ids)} dispatched, {dlq_candidates.count()} to DLQ")


def _move_to_dlq(message, reason):
    """Move a message to Dead Letter Queue (terminal CANCELLED status with DLQ metadata)."""
    from einvoice.services.metrics import record_dlq

    message.metadata = message.metadata or {}
    message.metadata["dlq"] = {
        "reason": reason,
        "moved_at": timezone.now().isoformat(),
        "retry_count": message.retry_count,
        "last_error": message.error_detail[:500],
    }
    message.error_detail = f"DLQ: {reason}"
    message.save(update_fields=["metadata", "error_detail"])

    message.transition_to(
        "CANCELLED",
        detail=f"Prebaceno u Dead Letter Queue: {reason}",
    )
    record_dlq(reason[:50])
    logger.warning(f"Message {message.invoice_number} moved to DLQ: {reason}")
