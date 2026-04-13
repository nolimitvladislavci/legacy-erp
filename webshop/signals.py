"""
Webshop Signals — order lifecycle integrations.

1. Order confirmed → Payment gateway + Inventory reservation
2. Order shipped → Delivery transport order + tracking email
3. Payment completed → auto-confirm order
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='webshop.Order')
def track_order_status_change(sender, instance, **kwargs):
    """Track status changes to detect transitions."""
    instance._old_status = None
    if instance.pk:
        try:
            old = sender.objects.only('status').get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='webshop.Order')
def on_order_confirmed(sender, instance, **kwargs):
    """When order becomes confirmed: reserve inventory, create delivery."""
    old = getattr(instance, '_old_status', None)
    if old == instance.status:
        return

    if instance.status == 'confirmed' and old in (None, 'pending'):
        # 1. Reserve inventory
        _reserve_inventory(instance)
        # 2. Create delivery order if shipping
        if instance.shipping_method != 'osobni_preuzimanje':
            _create_delivery(instance)

    elif instance.status == 'cancelled' and old != 'cancelled':
        # Release inventory
        _release_inventory(instance)


def _reserve_inventory(order):
    """Reserve stock for order items."""
    try:
        from inventory.models import StockMovement
        for item in order.items.select_related('product__inventory_item').all():
            inv_item = getattr(item.product, 'inventory_item', None)
            if inv_item:
                StockMovement.objects.create(
                    item=inv_item,
                    movement_type='reserved',
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    reason=f'Webshop narudžba {order.order_number}',
                )
        logger.info('Inventory reserved for order %s', order.order_number)
    except (IntegrityError, DatabaseError):
        logger.warning('Inventory reservation failed for %s', order.order_number, exc_info=True)


def _release_inventory(order):
    """Release reserved stock on cancellation."""
    try:
        from inventory.models import StockMovement
        for item in order.items.select_related('product__inventory_item').all():
            inv_item = getattr(item.product, 'inventory_item', None)
            if inv_item:
                StockMovement.objects.create(
                    item=inv_item,
                    movement_type='in',
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    reason=f'Otkazana narudžba {order.order_number}',
                )
        logger.info('Inventory released for cancelled order %s', order.order_number)
    except (IntegrityError, DatabaseError):
        logger.warning('Inventory release failed for %s', order.order_number, exc_info=True)


def _create_delivery(order):
    """Create delivery transport order for shipped orders."""
    try:
        from delivery.models import TransportOrder
        company = order.customer.company if hasattr(order.customer, 'company') else None
        if not company:
            return

        TransportOrder.objects.create(
            company=company,
            order_reference=order.order_number,
            recipient_name=order.customer.name,
            recipient_address=order.shipping_address or order.customer.address or '',
            status='pending',
            notes=f'Webshop narudžba {order.order_number}',
        )
        logger.info('Delivery created for order %s', order.order_number)
    except (IntegrityError, DatabaseError):
        logger.warning('Delivery creation failed for %s', order.order_number, exc_info=True)
