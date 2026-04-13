"""Accounts Celery Tasks — token cleanup."""
import logging

from celery import shared_task
from django.utils import timezone as tz

logger = logging.getLogger('accounts')


@shared_task
def deactivate_expired_tokens():
    """
    B-20: Svakih 30 min deaktiviraj istekle device tokene.
    Za volonterske tokene s expires_at.
    """
    from accounts.models import DeviceToken
    expired = DeviceToken.objects.filter(
        is_active=True,
        expires_at__isnull=False,
        expires_at__lt=tz.now(),
    )
    count = expired.update(is_active=False)
    if count:
        logger.info('[ACCOUNTS] Deactivated %d expired device tokens', count)
    return {'deactivated': count}
