"""
sales/saldakonti.py — Saldakonti engine

sync_open_items()     — sinkronizira OpenItem iz Invoice/konto
generate_ios()        — generira IOS izvještaj za partnera
aging_summary()       — aging analiza (0-30/31-60/61-90/90+)
auto_close_paid()     — zatvori stavke koje su potpuno plaćene
bulk_ios_generate()   — generiraj IOS za sve partnere s otvorenim stavkama
"""

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import IOSReport, OpenItem

logger = logging.getLogger(__name__)


@transaction.atomic
def sync_open_items(company, user=None):
    """
    Sinkronizira OpenItem iz Invoice.
    Kreira OpenItem za svaki neplaćeni/djelomično plaćeni račun.
    Zatvara OpenItem za plaćene račune.
    """
    from invoicing.models import Invoice

    created, closed, skipped = 0, 0, 0

    # IRA — potraživanja (kupci nam duguju)
    ira_invoices = Invoice.objects.filter(
        company=company,
        direction='outgoing',
        status__in=('sent', 'overdue', 'partially_paid'),
    ).select_related('partner')

    for inv in ira_invoices:
        if not inv.partner:
            skipped += 1
            continue

        item, was_created = OpenItem.objects.get_or_create(
            company=company,
            document_number=inv.number,
            defaults={
                'partner': inv.partner,
                'direction': 'receivable',
                'document_type': inv.invoice_type,
                'document_date': inv.issue_date,
                'due_date': inv.due_date or inv.issue_date,
                'original_amount': inv.total,
                'paid_amount': Decimal('0'),
                'currency': inv.currency,
                'invoice': inv,
            },
        )
        if was_created:
            created += 1

    # Zatvori plaćene
    paid = Invoice.objects.filter(
        company=company, direction='outgoing', status='paid',
    ).values_list('number', flat=True)

    closed = OpenItem.objects.filter(
        company=company, document_number__in=paid, is_closed=False,
    ).update(is_closed=True, closed_at=timezone.now())

    # URA — obveze (mi dugujemo dobavljaču)
    ura_invoices = Invoice.objects.filter(
        company=company,
        direction='incoming',
        status__in=('sent', 'overdue', 'partially_paid'),
    ).select_related('partner')

    for inv in ura_invoices:
        if not inv.partner:
            skipped += 1
            continue

        item, was_created = OpenItem.objects.get_or_create(
            company=company,
            document_number=inv.number,
            defaults={
                'partner': inv.partner,
                'direction': 'payable',
                'document_type': inv.invoice_type,
                'document_date': inv.issue_date,
                'due_date': inv.due_date or inv.issue_date,
                'original_amount': inv.total,
                'paid_amount': Decimal('0'),
                'currency': inv.currency,
                'invoice': inv,
            },
        )
        if was_created:
            created += 1

    logger.info(f'Saldakonti sync: +{created} created, {closed} closed, {skipped} skipped')
    return {'created': created, 'closed': closed, 'skipped': skipped}


def aging_summary(company, direction=None):
    """
    Aging analiza — grupirano po bucketima.
    Returns: dict s bucketima i ukupnim iznosima.
    """
    items = OpenItem.objects.filter(company=company, is_closed=False)
    if direction:
        items = items.filter(direction=direction)

    buckets = {
        'current': Decimal('0'),
        '1-30': Decimal('0'),
        '31-60': Decimal('0'),
        '61-90': Decimal('0'),
        '90+': Decimal('0'),
    }
    partner_breakdown = defaultdict(lambda: {
        'partner': None,
        'current': Decimal('0'), '1-30': Decimal('0'),
        '31-60': Decimal('0'), '61-90': Decimal('0'),
        '90+': Decimal('0'), 'total': Decimal('0'),
        'items_count': 0,
    })

    for item in items.select_related('partner'):
        bucket = item.aging_bucket
        remaining = item.remaining
        buckets[bucket] += remaining

        pb = partner_breakdown[item.partner_id]
        pb['partner'] = item.partner
        pb[bucket] += remaining
        pb['total'] += remaining
        pb['items_count'] += 1

    total = sum(buckets.values())

    # Sort partners by total descending
    partners_sorted = sorted(
        partner_breakdown.values(),
        key=lambda x: -x['total'],
    )

    return {
        'buckets': buckets,
        'total': total,
        'partners': partners_sorted,
        'items_count': items.count(),
    }


@transaction.atomic
def generate_ios(company, partner, report_date=None, user=None):
    """
    Generiraj IOS izvještaj za partnera.
    Zakon o računovodstvu čl. 22.
    """
    if not report_date:
        report_date = date.today()

    items = OpenItem.objects.filter(
        company=company, partner=partner, is_closed=False,
    ).order_by('document_date')

    total_receivable = items.filter(direction='receivable').aggregate(
        s=Sum('original_amount'))['s'] or Decimal('0')
    total_payable = items.filter(direction='payable').aggregate(
        s=Sum('original_amount'))['s'] or Decimal('0')
    paid_receivable = items.filter(direction='receivable').aggregate(
        s=Sum('paid_amount'))['s'] or Decimal('0')
    paid_payable = items.filter(direction='payable').aggregate(
        s=Sum('paid_amount'))['s'] or Decimal('0')

    net_receivable = total_receivable - paid_receivable
    net_payable = total_payable - paid_payable
    net_balance = net_receivable - net_payable

    report = IOSReport.objects.create(
        company=company,
        partner=partner,
        report_date=report_date,
        total_receivable=net_receivable,
        total_payable=net_payable,
        net_balance=net_balance,
        items_count=items.count(),
        created_by=user,
    )

    logger.info(f'IOS generated: {partner.name}, balance={net_balance} EUR, {items.count()} items')
    return report


def bulk_ios_generate(company, user=None):
    """Generiraj IOS za sve partnere s otvorenim stavkama."""
    partner_ids = OpenItem.objects.filter(
        company=company, is_closed=False,
    ).values_list('partner_id', flat=True).distinct()

    from partners.models import Partner
    reports = []
    for pid in partner_ids:
        partner = Partner.objects.get(pk=pid)
        report = generate_ios(company, partner, user=user)
        reports.append(report)

    return reports


@transaction.atomic
def register_payment(open_item, amount, user=None, reference=''):
    """
    Registriraj uplatu na otvorenu stavku.
    Ako je amount >= remaining, zatvori stavku.
    """
    if amount <= 0:
        raise ValueError('Iznos mora biti pozitivan')
    if amount > open_item.remaining:
        raise ValueError(f'Iznos ({amount}) veći od preostalog ({open_item.remaining})')

    open_item.paid_amount += amount
    if open_item.paid_amount >= open_item.original_amount:
        open_item.is_closed = True
        open_item.closed_at = timezone.now()

    open_item.save(update_fields=['paid_amount', 'is_closed', 'closed_at', 'updated_at'])

    logger.info(
        f'Payment registered: {open_item.document_number} +{amount} EUR '
        f'(remaining: {open_item.remaining}, closed: {open_item.is_closed})'
    )
    return open_item
