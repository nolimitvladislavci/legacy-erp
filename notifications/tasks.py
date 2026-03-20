"""Notification Celery Tasks — automatsko čišćenje."""
import logging
from celery import shared_task
from datetime import timedelta
from django.utils import timezone as tz

logger = logging.getLogger('notifications')


@shared_task
def cleanup_old_notifications():
    """
    Dnevno: briši pročitane starije od 30 dana, označi nepročitane starije od 14 dana.
    Sprječava nakupljanje stotina notifikacija po korisniku.
    """
    from notifications.models import Notification
    now = tz.now()

    # 1. Briši pročitane starije od 30 dana
    deleted, _ = Notification.objects.filter(
        is_read=True,
        created_at__lt=now - timedelta(days=30),
    ).delete()

    # 2. Auto-mark-read nepročitane starije od 14 dana
    marked = Notification.objects.filter(
        is_read=False,
        created_at__lt=now - timedelta(days=14),
    ).update(is_read=True)

    # 3. Per-user cap: ako netko ima > 50 nepročitanih, zadrži samo 20 najnovijih
    from django.db.models import Count
    heavy_users = (
        Notification.objects
        .filter(is_read=False)
        .values('recipient_id')
        .annotate(c=Count('id'))
        .filter(c__gt=50)
    )
    capped = 0
    for row in heavy_users:
        keep_ids = list(
            Notification.objects
            .filter(recipient_id=row['recipient_id'], is_read=False)
            .order_by('-created_at')[:20]
            .values_list('id', flat=True)
        )
        capped += Notification.objects.filter(
            recipient_id=row['recipient_id'], is_read=False,
        ).exclude(id__in=keep_ids).update(is_read=True)

    if deleted or marked or capped:
        logger.info(
            '[NOTIFICATIONS] Cleanup: %d deleted, %d auto-read, %d capped',
            deleted, marked, capped,
        )

    return {'deleted': deleted, 'marked_read': marked, 'capped': capped}
