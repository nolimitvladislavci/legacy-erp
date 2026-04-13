"""
BORG Morning Briefing — agregacija dnevnih akcija za tenante.

Koristi se iz Celery taska morning_briefing().
Agregira: overdue invoices, compliance deadlines, BorgTask queue,
inventory alerts, NN regulatory alerts.
Rankira po: urgency x financial_impact.
"""
import logging
from datetime import timedelta

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger('borg.briefing')


def collect_briefing_items(company, config):
    """
    Prikupi sve relevantne stavke za morning briefing.
    Returns: list of dicts sorted by priority score (highest first).
    Each dict: {priority_score, emoji, title, detail}
    """
    items = []
    now = timezone.now()
    today = now.date()

    # 1. Overdue invoices (financial)
    if config.include_financial:
        items.extend(_collect_overdue_invoices(company, today))

    # 2. Compliance deadlines (tax, fiscal)
    if config.include_compliance:
        items.extend(_collect_compliance_deadlines(company, today))
        items.extend(_collect_nn_alerts(company))

    # 3. Operational — pending BorgTasks, inventory
    if config.include_operational:
        items.extend(_collect_pending_tasks(company))
        items.extend(_collect_inventory_alerts(company, today))

    # Sort by priority score (highest = most urgent)
    items.sort(key=lambda x: x['priority_score'], reverse=True)

    return items[:config.max_items]


def format_briefing_message(items, company_name):
    """Format items into WhatsApp message."""
    today_str = timezone.now().strftime('%d.%m.%Y')
    lines = [f'*BORG Jutarnji Briefing — {today_str}*']
    lines.append(f'_{company_name}_')
    lines.append('')

    if not items:
        lines.append('Sve pod kontrolom. Nema urgentnih stavki.')
        return '\n'.join(lines)

    for i, item in enumerate(items, 1):
        lines.append(f'{i}. {item["emoji"]} {item["title"]}')
        if item.get('detail'):
            lines.append(f'   {item["detail"]}')

    lines.append('')
    lines.append('_Odgovori brojem za detalje._')
    return '\n'.join(lines)


def _collect_overdue_invoices(company, today):
    """Find overdue unpaid invoices."""
    items = []
    try:
        from invoicing.models import Invoice
        overdue = Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'OVERDUE', 'UNPAID'],
            date_due__lt=today,
        ).order_by('date_due')[:10]

        for inv in overdue:
            days = (today - inv.date_due).days
            score = float(inv.total or 0) * min(days, 90)  # EUR * days
            items.append({
                'priority_score': score,
                'emoji': '\u26a0\ufe0f',
                'title': f'Racun {inv.number} kasni {days} dana ({inv.total} EUR)',
                'detail': f'Klijent: {inv.client_name}',
            })
    except (ValueError, TypeError) as e:
        logger.debug('Overdue invoices skip: %s', e)

    return items


def _collect_compliance_deadlines(company, today):
    """Find upcoming tax/compliance deadlines."""
    items = []
    try:
        from tax_wizard.models import TaxDeadline
        upcoming = TaxDeadline.objects.filter(
            company=company,
            deadline_date__gte=today,
            deadline_date__lte=today + timedelta(days=7),
            is_completed=False,
        ).order_by('deadline_date')[:5]

        for deadline in upcoming:
            days_left = (deadline.deadline_date - today).days
            score = 10000 / max(days_left, 1)  # Closer = higher
            items.append({
                'priority_score': score,
                'emoji': '\U0001f4cb',
                'title': f'{deadline.name} — rok: {deadline.deadline_date.strftime("%d.%m.")}',
                'detail': f'Preostalo {days_left} dana',
            })
    except DatabaseError as e:
        logger.debug('Tax deadlines skip: %s', e)

    return items


def _collect_nn_alerts(company):
    """Find unreviewed regulatory alerts for this company."""
    items = []
    try:
        from limit_connect_ai.models_knowledge_graph import RegulatoryUpdate
        # Recent unprocessed regulatory updates that affect this company's modules
        recent = RegulatoryUpdate.objects.filter(
            is_processed=True,
            is_breaking=True,
            publication_date__gte=timezone.now().date() - timedelta(days=7),
        )[:3]

        for update in recent:
            items.append({
                'priority_score': update.impact_score * 1000,
                'emoji': '\u2696\ufe0f',
                'title': f'NN: {update.title[:60]}',
                'detail': update.ai_summary[:100] if update.ai_summary else '',
            })
    except DatabaseError as e:
        logger.debug('NN alerts skip: %s', e)

    return items


def _collect_pending_tasks(company):
    """Find high-priority pending BorgTasks."""
    items = []
    try:
        from borg_ops.models import BorgTask
        tasks = BorgTask.objects.filter(
            company=company,
            status__in=['pending', 'in_progress'],
            priority__lte=2,  # Kriticno + Visoko
        ).order_by('priority', '-created_at')[:5]

        for task in tasks:
            score = (5 - task.priority) * 500  # P1=2000, P2=1500
            items.append({
                'priority_score': score,
                'emoji': '\U0001f534' if task.priority == 1 else '\U0001f7e0',
                'title': task.title[:60],
                'detail': f'[P{task.priority}] {task.get_task_type_display()}',
            })
    except DatabaseError as e:
        logger.debug('Pending tasks skip: %s', e)

    return items


def _collect_inventory_alerts(company, today):
    """Find expiring LOT batches and low stock."""
    items = []
    try:
        from inventory.models import StockBatch
        expiring = StockBatch.objects.filter(
            item__company=company,
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=7),
            expiry_date__gt=today,
            quantity__gt=0,
        ).select_related('item').order_by('expiry_date')[:5]

        for batch in expiring:
            days_left = (batch.expiry_date - today).days
            score = 800 / max(days_left, 1)
            items.append({
                'priority_score': score,
                'emoji': '\U0001f4e6',
                'title': f'{batch.item.name} LOT istjece za {days_left} dana',
                'detail': f'{batch.quantity} kom na stanju',
            })
    except DatabaseError as e:
        logger.debug('Inventory alerts skip: %s', e)

    return items
