"""
limit_connect_ai/proactive_widget.py — AI Proactive Dashboard Widget.

Generira instant insights za dashboard bez cekanja na jutarnji email.
Poziva se sinhrono iz dashboard viewa.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


def get_dashboard_insights(company):
    """
    Generate real-time insights for company dashboard.
    Returns dict of alerts, suggestions, and stats.
    """
    today = date.today()
    alerts = []
    suggestions = []

    # 1. DOSPJELE FAKTURE
    try:
        from invoicing.models import Invoice
        overdue = Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'UNPAID', 'OVERDUE'],
            date_due__lt=today,
        )
        overdue_count = overdue.count()
        overdue_total = sum(float(i.total or 0) for i in overdue)
        if overdue_count > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'alert-triangle',
                'title': f'{overdue_count} dospjelih faktura',
                'detail': f'Ukupno {overdue_total:,.2f} EUR neplaceno',
                'action_url': '/hr/konto/#receivables',
                'action_text': 'Pogledaj saldakonti',
            })
    except Exception:
        pass

    # 2. NIZAK STOCK
    try:
        from inventory.models import InventoryItem
        from django.db.models import F
        low_stock = InventoryItem.objects.filter(
            company=company,
            quantity__lte=F('reorder_level'),
            reorder_level__gt=0,
        ).count()
        if low_stock > 0:
            alerts.append({
                'type': 'danger',
                'icon': 'package',
                'title': f'{low_stock} artikala ispod min. zalihe',
                'detail': 'Potrebna narudzba za dopunu',
                'action_url': '/hr/inventory/',
                'action_text': 'Pregledaj zalihe',
            })
    except Exception:
        pass

    # 3. NEUPAREN BANK IZVOD
    try:
        from konto.models import BankTransaction
        unmatched = BankTransaction.objects.filter(
            company=company, status='unmatched'
        ).count()
        if unmatched > 0:
            alerts.append({
                'type': 'info',
                'icon': 'credit-card',
                'title': f'{unmatched} neuparenih transakcija',
                'detail': 'Bankovni izvod ceka pariranje',
                'action_url': '/hr/konto/bank/',
                'action_text': 'Pariraj transakcije',
            })
    except Exception:
        pass

    # 4. OTVORENI HELPDESK TICKETI
    try:
        from helpdesk.models import Ticket
        open_tickets = Ticket.objects.filter(
            company=company,
            status__in=['open', 'in_progress'],
        ).count()
        if open_tickets > 0:
            alerts.append({
                'type': 'info',
                'icon': 'help-circle',
                'title': f'{open_tickets} otvorenih ticketa',
                'detail': 'Cekaju odgovor',
                'action_url': '/hr/helpdesk/',
                'action_text': 'Pogledaj tickete',
            })
    except Exception:
        pass

    # 5. DANAS IZDANE FAKTURE
    try:
        from invoicing.models import Invoice
        today_invoices = Invoice.objects.filter(
            company=company,
            date_issued__date=today,
        ).count()
        today_total = sum(float(i.total or 0) for i in Invoice.objects.filter(
            company=company, date_issued__date=today))
        if today_invoices > 0:
            suggestions.append({
                'type': 'success',
                'icon': 'trending-up',
                'title': f'Danas: {today_invoices} faktura ({today_total:,.2f} EUR)',
                'detail': '',
            })
    except Exception:
        pass

    # 6. POS PROMET DANAS
    try:
        from pos.models import POSReceipt
        from django.db.models import Sum
        pos_today = POSReceipt.objects.filter(
            session__terminal__company=company,
            created_at__date=today,
            status='paid',
        ).aggregate(total=Sum('total'), count=Sum('receipt_number'))
        if pos_today['total']:
            suggestions.append({
                'type': 'success',
                'icon': 'shopping-cart',
                'title': f'POS danas: {float(pos_today["total"]):,.2f} EUR',
                'detail': '',
            })
    except Exception:
        pass

    # 7. PREDLOZI
    try:
        from konto.models import JournalEntry
        unposted = JournalEntry.objects.filter(
            company=company, is_posted=False
        ).count()
        if unposted > 0:
            suggestions.append({
                'type': 'info',
                'icon': 'book-open',
                'title': f'{unposted} neproknjizenih temeljnica',
                'detail': 'Pregledaj i potvrdi prije zakljucivanja perioda',
                'action_url': '/hr/konto/entries/',
                'action_text': 'Otvori',
            })
    except Exception:
        pass

    # 8. LICENCE / PRETPLATE KOJE ISTICU
    try:
        from registration.models import CompanySubscription
        week_ahead = today + timedelta(days=7)
        expiring = CompanySubscription.objects.filter(
            company=company,
            valid_until__lte=week_ahead,
            valid_until__gte=today,
        ).count()
        if expiring > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'clock',
                'title': f'Pretplata istice za {expiring} firmu/e',
                'detail': 'Obnovite prije isteka',
                'action_url': '/hr/companies/subscription/',
                'action_text': 'Obnovi',
            })
    except Exception:
        pass

    return {
        'alerts': alerts,
        'suggestions': suggestions,
        'total_alerts': len(alerts),
        'total_suggestions': len(suggestions),
    }
