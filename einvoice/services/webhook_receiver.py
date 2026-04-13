"""Webhook receiver for posrednik status callbacks.

Instead of polling every 60s, the posrednik can push status updates to us.
Security: HMAC signature verification on every payload.
"""
import hmac
import hashlib
import json
import logging
from django.conf import settings
from einvoice.models import AS4Message, MessageStatus
from einvoice.services.metrics import record_sent, record_delivery_latency

logger = logging.getLogger("propter.einvoice.webhook")


def verify_webhook_signature(payload_body, signature_header, secret=None):
    """
    Verify HMAC-SHA256 signature of webhook payload.

    Args:
        payload_body: raw request body (bytes)
        signature_header: X-Webhook-Signature header value
        secret: webhook secret (from settings if not provided)

    Returns:
        bool: True if signature is valid
    """
    secret = secret or getattr(settings, "EINVOICE_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("EINVOICE_WEBHOOK_SECRET not set — rejecting all webhooks")
        return False

    if not signature_header:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def process_webhook_payload(payload):
    """
    Process a verified webhook payload from posrednik.

    Expected payload format:
    {
        "event": "status_change",
        "messageId": "ext-123",
        "status": "DELIVERED",
        "timestamp": "2026-03-24T10:00:00Z",
        "errorMessage": null
    }
    """
    event_type = payload.get("event", "")
    external_id = payload.get("messageId", "")
    new_status_raw = payload.get("status", "")
    error_msg = payload.get("errorMessage", "")
    timestamp = payload.get("timestamp", "")

    if not external_id:
        logger.warning("Webhook payload missing messageId")
        return {"processed": False, "reason": "missing messageId"}

    # Find the AS4Message
    message = AS4Message.objects.filter(
        external_message_id=external_id,
        direction="OUT",
    ).first()

    if not message:
        logger.warning(f"Webhook for unknown message: {external_id}")
        return {"processed": False, "reason": f"unknown message {external_id}"}

    # Map posrednik status
    status_map = {
        "PENDING": MessageStatus.SUBMITTED,
        "PROCESSING": MessageStatus.SUBMITTED,
        "SENT": MessageStatus.SENT,
        "DELIVERED": MessageStatus.DELIVERED,
        "ACKNOWLEDGED": MessageStatus.ACKNOWLEDGED,
        "ACCEPTED": MessageStatus.DELIVERED,
        "REJECTED": MessageStatus.REJECTED,
        "FAILED": MessageStatus.SEND_FAILED,
        "ERROR": MessageStatus.SEND_FAILED,
    }
    new_status = status_map.get(new_status_raw.upper(), "")

    if not new_status:
        logger.warning(f"Unknown webhook status: {new_status_raw}")
        return {"processed": False, "reason": f"unknown status {new_status_raw}"}

    # Don't downgrade terminal states
    if message.is_terminal:
        logger.info(f"Ignoring webhook for terminal message {external_id} (status={message.status})")
        return {"processed": False, "reason": "message already terminal"}

    # Same status — ignore
    if new_status == message.status:
        return {"processed": False, "reason": "status unchanged"}

    # Apply transition
    detail = f"Webhook: {new_status_raw}"
    if error_msg:
        detail += f" — {error_msg}"
    if timestamp:
        detail += f" @ {timestamp}"

    message.transition_to(new_status, detail=detail)

    # Record metrics
    record_sent(message.transport, new_status)

    # Record delivery latency
    if new_status in (MessageStatus.DELIVERED, MessageStatus.ACKNOWLEDGED):
        if message.submitted_at and message.delivered_at:
            latency = (message.delivered_at - message.submitted_at).total_seconds()
            record_delivery_latency(latency)

        # Archive on delivery
        try:
            from einvoice.services.archive_service import ArchiveService
            ArchiveService().archive_message(message)
        except ImportError as e:
            logger.error(f"Archive failed after webhook delivery: {e}")

    logger.info(f"Webhook processed: {external_id} -> {new_status}")
    return {
        "processed": True,
        "message_id": str(message.id),
        "old_status": message.status,
        "new_status": new_status,
    }
