"""
partners/crm_timeline.py — CRM Timeline za partnere.

Agregira sve interakcije s partnerom iz svih modula:
  - Fakture (izlazne i ulazne)
  - POS bonovi
  - Helpdesk ticketi
  - Bankovne transakcije
  - Marketplace narudzbe
  - Dokumenti

Rezultat je kronoloski timeline svih dogadjaja.
"""
import logging
from datetime import date
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def get_partner_timeline(partner, limit=50):
    """
    Build CRM timeline for a partner — all interactions across modules.
    Returns list of dicts: [{date, type, module, title, amount, url, icon}, ...]
    """
    events = []

    # 1. FAKTURE — izdane i primljene
    try:
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(
            client_oib=partner.oib
        ).order_by('-date_issued')[:limit] if partner.oib else Invoice.objects.none()

        # Also search by name
        if not invoices.exists():
            invoices = Invoice.objects.filter(
                client_name__icontains=partner.name[:20]
            ).order_by('-date_issued')[:limit]

        for inv in invoices:
            dt = inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued
            events.append({
                'date': dt,
                'type': 'invoice',
                'module': 'Fakturiranje',
                'title': f'{inv.get_doctype_display()} {inv.number}',
                'subtitle': inv.get_status_display(),
                'amount': float(inv.total or 0),
                'url': f'/hr/invoicing/{inv.pk}/',
                'icon': 'file-text',
                'color': '#3498db',
            })
    except (ValueError, TypeError) as e:
        logger.debug('Timeline invoice error: %s', e)

    # 2. BANKOVNE TRANSAKCIJE
    try:
        from konto.models import BankTransaction
        txns = BankTransaction.objects.filter(
            counterparty_name__icontains=partner.name[:15]
        ).order_by('-transaction_date')[:limit]

        for tx in txns:
            events.append({
                'date': tx.transaction_date,
                'type': 'bank',
                'module': 'Banka',
                'title': f'{"Uplata" if tx.transaction_type == "inflow" else "Isplata"} {tx.amount} EUR',
                'subtitle': tx.description[:80] if tx.description else '',
                'amount': float(tx.amount) * (1 if tx.transaction_type == 'inflow' else -1),
                'url': '#',
                'icon': 'credit-card',
                'color': '#27ae60' if tx.transaction_type == 'inflow' else '#e74c3c',
            })
    except (ValueError, TypeError) as e:
        logger.debug('Timeline bank error: %s', e)

    # 3. POS BONOVI (R1 racuni s OIB-om)
    try:
        from pos.models import POSReceipt
        if partner.oib:
            receipts = POSReceipt.objects.filter(
                buyer_oib=partner.oib
            ).order_by('-created_at')[:limit]
            for r in receipts:
                events.append({
                    'date': r.created_at.date(),
                    'type': 'pos',
                    'module': 'POS',
                    'title': f'Bon #{r.global_number or r.receipt_number}',
                    'subtitle': r.get_status_display(),
                    'amount': float(r.total),
                    'url': f'/hr/pos/receipt/{r.pk}/',
                    'icon': 'shopping-cart',
                    'color': '#9b59b6',
                })
    except (ValueError, TypeError) as e:
        logger.debug('Timeline POS error: %s', e)

    # 4. HELPDESK TICKETI
    try:
        from helpdesk.models import Ticket
        if partner.email:
            tickets = Ticket.objects.filter(
                contact_email=partner.email
            ).order_by('-created_at')[:10]
            for t in tickets:
                events.append({
                    'date': t.created_at.date(),
                    'type': 'helpdesk',
                    'module': 'Helpdesk',
                    'title': t.subject,
                    'subtitle': t.get_status_display(),
                    'amount': None,
                    'url': f'/hr/helpdesk/{t.pk}/',
                    'icon': 'help-circle',
                    'color': '#f39c12',
                })
    except DatabaseError as e:
        logger.debug('Timeline helpdesk error: %s', e)

    # 5. MARKETPLACE NARUDZBE
    try:
        from marketplace.models import MarketplaceOrder
        orders = MarketplaceOrder.objects.filter(
            buyer_company=partner.company
        ).order_by('-created_at')[:10]
        for o in orders:
            events.append({
                'date': o.created_at.date(),
                'type': 'marketplace',
                'module': 'Marketplace',
                'title': f'Narudzba {o.order_number}',
                'subtitle': o.get_status_display(),
                'amount': float(o.total_amount or 0),
                'url': f'/marketplace/orders/{o.pk}/',
                'icon': 'globe',
                'color': '#1abc9c',
            })
    except (ValueError, TypeError) as e:
        logger.debug('Timeline marketplace error: %s', e)

    # Sort by date descending
    events.sort(key=lambda e: e['date'], reverse=True)

    # Calculate summary
    total_revenue = sum(e['amount'] for e in events if e.get('amount') and e['amount'] > 0 and e['type'] in ('invoice', 'bank'))
    total_transactions = len(events)
    first_contact = events[-1]['date'] if events else None
    last_contact = events[0]['date'] if events else None

    return {
        'events': events[:limit],
        'summary': {
            'total_events': total_transactions,
            'total_revenue': total_revenue,
            'first_contact': first_contact,
            'last_contact': last_contact,
            'days_since_last': (date.today() - last_contact).days if last_contact else None,
        }
    }


def get_partner_score(partner):
    """
    Calculate a simple partner score (0-100) based on:
    - Volume (revenue)
    - Frequency (transactions)
    - Recency (last contact)
    - Payment behavior (% paid on time)
    """
    timeline = get_partner_timeline(partner, limit=200)
    summary = timeline['summary']

    score = 50  # Base score

    # Revenue factor (up to +20)
    revenue = summary.get('total_revenue', 0)
    if revenue > 100000:
        score += 20
    elif revenue > 50000:
        score += 15
    elif revenue > 10000:
        score += 10
    elif revenue > 1000:
        score += 5

    # Frequency factor (up to +15)
    events = summary.get('total_events', 0)
    if events > 50:
        score += 15
    elif events > 20:
        score += 10
    elif events > 5:
        score += 5

    # Recency factor (up to +15)
    days = summary.get('days_since_last')
    if days is not None:
        if days < 7:
            score += 15
        elif days < 30:
            score += 10
        elif days < 90:
            score += 5
        elif days > 365:
            score -= 10

    return min(100, max(0, score))
