"""
production/signals.py — Automatski logiranje promjena na radnim nalozima.
"""

import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import ProductionOrder, ProductionLog

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ProductionOrder, dispatch_uid='production_order_status_log')
def log_status_change(sender, instance, **kwargs):
    """Logira promjenu statusa radnog naloga."""
    if not instance.pk:
        return  # New object — will be logged on post_save via view

    try:
        old = ProductionOrder.objects.get(pk=instance.pk)
    except ProductionOrder.DoesNotExist:
        return

    if old.status != instance.status:
        action_map = {
            'confirmed': 'confirmed',
            'in_progress': 'started',
            'done': 'completed',
            'cancelled': 'cancelled',
        }
        action = action_map.get(instance.status)
        if action:
            ProductionLog.objects.create(
                order=instance,
                action=action,
                description=f'Status: {old.status} → {instance.status}',
                metadata={'old_status': old.status, 'new_status': instance.status},
            )

    if old.produced_quantity != instance.produced_quantity:
        diff = instance.produced_quantity - old.produced_quantity
        if diff > 0:
            ProductionLog.objects.create(
                order=instance,
                action='produced',
                quantity=diff,
                description=f'Proizvedeno +{diff} (ukupno: {instance.produced_quantity})',
            )

    if old.scrap_quantity != instance.scrap_quantity:
        diff = instance.scrap_quantity - old.scrap_quantity
        if diff > 0:
            ProductionLog.objects.create(
                order=instance,
                action='scrap',
                quantity=diff,
                description=f'Škart +{diff} (ukupno: {instance.scrap_quantity})',
            )
