"""Celery tasks for inbound invoice processing."""
import logging
from celery import shared_task
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger("propter.einvoice.tasks.inbound")


@shared_task
def poll_inbox():
    from einvoice.models import (
        AS4Message, TransportConfiguration,
        MessageDirection, MessageStatus, TransportType,
    )
    from einvoice.services.posrednik_client import PosrednikClient
    from einvoice.services.smart_mailbox import SmartMailboxService

    posrednik = PosrednikClient()
    mailbox = SmartMailboxService()

    configs = TransportConfiguration.objects.filter(
        primary_transport="FINA", smart_mailbox_enabled=True,
    ).select_related("company")

    total_received = 0
    for config in configs:
        if not config.fina_participant_id:
            continue
        try:
            pending = posrednik.poll_inbox(config.fina_participant_id)
            for msg_summary in pending:
                ext_id = msg_summary.get("messageId", "")
                if AS4Message.objects.filter(external_message_id=ext_id, direction=MessageDirection.INBOUND).exists():
                    continue

                ubl_bytes = posrednik.download(ext_id)
                message = AS4Message(
                    company=config.company,
                    direction=MessageDirection.INBOUND,
                    transport=TransportType.FINA_POSREDNIK,
                    sender_participant_id=msg_summary.get("senderParticipantId", ""),
                    receiver_participant_id=config.fina_participant_id,
                    sender_name=msg_summary.get("senderName", ""),
                    receiver_name=config.company.name,
                    invoice_number=msg_summary.get("invoiceNumber", ""),
                    external_message_id=ext_id,
                    status=MessageStatus.RECEIVED,
                )
                message.set_ubl_xml(ubl_bytes.decode("utf-8"))
                message.save()
                message.transition_to(MessageStatus.RECEIVED, detail=f"Primljeno od FINA posrednika: {ext_id}")

                try:
                    mailbox.process_incoming(message)
                    total_received += 1
                    # Push notification for new invoice
                    try:
                        from push_notifications.push import send_company_push
                        send_company_push(
                            config.company.id,
                            title="Nova ulazna faktura",
                            body=f"{msg_summary.get('senderName', 'Nepoznat')} — {msg_summary.get('invoiceNumber', '')}",
                            url="/einvoice/inbox/",
                        )
                    except ImportError:
                        pass
                except ImportError as e:
                    logger.error(f"Smart Mailbox failed for {ext_id}: {e}")
                    message.transition_to(MessageStatus.VALIDATION_FAILED, detail=str(e))

                posrednik.acknowledge(ext_id)
        except (IntegrityError, DatabaseError) as e:
            logger.error(f"Inbox poll failed for {config.company.name}: {e}")

    if total_received:
        logger.info(f"Inbox poll: {total_received} new invoices")
    posrednik.close()
