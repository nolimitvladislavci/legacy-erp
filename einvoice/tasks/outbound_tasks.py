"""Celery tasks for outbound invoice sending."""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("propter.einvoice.tasks.outbound")


@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def send_invoice_task(self, message_id):
    from einvoice.models import AS4Message, MessageStatus
    from einvoice.services.transport_router import TransportRouter

    try:
        message = AS4Message.objects.get(id=message_id)
    except AS4Message.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {"error": "Message not found"}

    if message.is_terminal:
        return {"status": message.status}

    router = TransportRouter()
    decision = router.resolve(
        company_id=str(message.company_id),
        sender_oib=message.sender_oib,
        receiver_oib=message.receiver_oib,
    )
    backend = router.get_backend(decision.transport)
    message.transport = decision.transport
    message.save(update_fields=["transport"])

    logger.info(f"Sending {message.invoice_number} via {decision.backend_name}: {decision.reason}")

    try:
        external_id = backend.submit(message)
        return {"status": "submitted", "external_id": external_id, "transport": decision.transport}
    except Exception as exc:
        logger.error(f"Send failed for {message.invoice_number}: {exc}")
        if message.can_retry():
            delay = [60, 300, 900, 3600, 14400][min(self.request.retries, 4)]
            raise self.retry(exc=exc, countdown=delay)
        else:
            message.transition_to(MessageStatus.SEND_FAILED, detail=f"Iscrpljeni svi pokusaji: {exc}")
            return {"status": "failed", "error": str(exc)}


@shared_task
def process_retry_queue():
    from einvoice.models import AS4Message, MessageStatus
    now = timezone.now()
    retry_ids = list(
        AS4Message.objects.filter(status=MessageStatus.RETRY, next_retry_at__lte=now)
        .values_list("id", flat=True)[:50]
    )
    for msg_id in retry_ids:
        send_invoice_task.delay(str(msg_id))
    if retry_ids:
        logger.info(f"Retry queue: dispatched {len(retry_ids)} messages")
