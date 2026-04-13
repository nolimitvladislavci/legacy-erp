"""Celery tasks for delivery status tracking."""
import logging
from celery import shared_task

logger = logging.getLogger("propter.einvoice.tasks.status")


@shared_task
def check_delivery_statuses():
    from einvoice.models import AS4Message, MessageStatus
    from einvoice.services.posrednik_client import PosrednikClient
    from einvoice.services.archive_service import ArchiveService

    posrednik = PosrednikClient()
    archive_svc = ArchiveService()

    pending = AS4Message.objects.filter(
        direction="OUT",
        status__in=[MessageStatus.SUBMITTED, MessageStatus.SENT],
        external_message_id__gt="",
    ).select_related("company")[:100]

    updated = 0
    for message in pending:
        try:
            result = posrednik.check_status(message.external_message_id)
            new_status = result.get("status")
            if not new_status or new_status == message.status:
                continue

            if new_status in (MessageStatus.DELIVERED, MessageStatus.ACKNOWLEDGED):
                message.transition_to(new_status, detail=f"Dostavljeno: {result.get('delivered_at', 'N/A')}")
                try:
                    archive_svc.archive_message(message)
                except Exception as e:
                    logger.error(f"Archive failed for {message.invoice_number}: {e}")
                updated += 1
            elif new_status in (MessageStatus.SEND_FAILED, MessageStatus.REJECTED):
                message.transition_to(new_status, detail=result.get("error", "Unknown error"))
                updated += 1
            elif new_status != message.status:
                message.transition_to(new_status, detail=f"Status update: {result.get('raw_status')}")
                updated += 1
        except KeyError as e:
            logger.error(f"Status check failed for {message.external_message_id}: {e}")

    posrednik.close()
    if updated:
        logger.info(f"Status check: {updated} messages updated")
