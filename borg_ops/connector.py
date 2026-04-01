"""
BORG FENIX — Ops Connector (F3.3)
Connects CardActivity workflow to work_orders, invoicing, and POS modules.
Auto-creates cards from new work orders and invoices.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q

logger = logging.getLogger('borg.ops')


@shared_task
def sync_ops_cards():
    """
    Sync BORG Ops cards with actual business events:
    1. New overdue invoices → CardActivity (type=followup)
    2. New work orders → CardActivity (type=work_order)
    3. Update SLA timestamps
    """
    from borg_ops.models import CardActivity, StatusTimestamp

    stats = {'invoices_synced': 0, 'work_orders_synced': 0}

    # 1. Overdue invoices → ops cards
    try:
        from invoicing.models import Invoice
        overdue = Invoice.objects.filter(
            status='UNPAID',
            date_due__lt=timezone.now().date(),
        ).exclude(
            number__in=CardActivity.objects.values_list('reference_id', flat=True),
        )[:50]

        for inv in overdue:
            card = CardActivity.objects.create(
                card_type='followup',
                reference_id=inv.number,
                title=f"Naplata: {inv.number} - {inv.client_name or 'N/A'}",
                description=f"Faktura {inv.number} dospjela {inv.date_due}. Iznos: {inv.total} EUR.",
                status='pending',
                priority='high' if inv.total > 1000 else 'normal',
            )
            StatusTimestamp.objects.create(
                card=card,
                from_status='',
                to_status='pending',
            )
            stats['invoices_synced'] += 1
    except Exception as e:
        logger.warning('Invoice sync failed: %s', e)

    # 2. Open work orders → ops cards
    try:
        from work_orders.models import WorkOrder
        open_wo = WorkOrder.objects.filter(
            status__in=['draft', 'in_progress'],
        ).exclude(
            id__in=[
                int(ref) for ref in
                CardActivity.objects.filter(card_type='work_order')
                .values_list('reference_id', flat=True)
                if ref.isdigit()
            ],
        )[:50]

        for wo in open_wo:
            card = CardActivity.objects.create(
                card_type='work_order',
                reference_id=str(wo.id),
                title=f"RN: {wo.number or wo.id} - {getattr(wo, 'client', 'N/A')}",
                description=f"Radni nalog {getattr(wo, 'number', wo.id)}.",
                status='in_progress',
                priority='normal',
            )
            stats['work_orders_synced'] += 1
    except Exception as e:
        logger.warning('Work order sync failed: %s', e)

    logger.info('Ops sync: %s', stats)
    return stats


@shared_task
def ops_sla_check():
    """Check SLA breaches for all active ops cards."""
    from borg_ops.models import CardActivity, StatusTimestamp

    active = CardActivity.objects.filter(
        status__in=['pending', 'in_progress'],
    )

    sla_breaches = 0
    now = timezone.now()

    for card in active:
        # Calculate time in current status
        last_ts = StatusTimestamp.objects.filter(card=card).order_by('-timestamp').first()
        if not last_ts:
            continue

        hours_in_status = (now - last_ts.timestamp).total_seconds() / 3600

        # SLA thresholds
        sla_hours = {
            'high': 4,
            'urgent': 1,
            'normal': 24,
            'low': 72,
        }

        threshold = sla_hours.get(getattr(card, 'priority', 'normal'), 24)
        if hours_in_status > threshold:
            sla_breaches += 1

    logger.info('SLA check: %d active cards, %d breaches', active.count(), sla_breaches)
    return {'active': active.count(), 'sla_breaches': sla_breaches}
