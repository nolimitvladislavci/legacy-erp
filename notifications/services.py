"""Notification helpers — create DB notification + Web Push."""

import logging

from .models import Notification

logger = logging.getLogger(__name__)


def notify(recipient, notification_type, title, message, url="", sender=None, company=None):
    """Create a Notification and send a Web Push."""
    notif = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        company=company,
    )
    # Web Push (best-effort)
    try:
        from push_notifications.push import send_push_to_user

        send_push_to_user(recipient, title, message, url=url or "/")
    except ImportError as e:
        logger.debug(f"Push skipped: {e}")
    return notif


def notify_bulk(recipients, notification_type, title, message, url="", sender=None, company=None):
    """Send notification to multiple users."""
    results = []
    for user in recipients:
        results.append(notify(user, notification_type, title, message, url, sender, company))
    return results
