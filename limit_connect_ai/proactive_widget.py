"""
limit_connect_ai/proactive_widget.py — AI Proactive Dashboard Widget.

Generira instant insights za dashboard bez cekanja na jutarnji email.
Poziva se sinhrono iz dashboard viewa.

v2 (2026-03-23): Knowledge Graph integracija
- RegulatoryUpdate: nove zakonske promjene (zadnjih 7 dana)
- LegalOpportunity + ClientOpportunityMatch: prilike za ustedu
- SupplierRiskAlert: rizici u lancu opskrbe
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import DatabaseError
from django.db.models import Sum

logger = logging.getLogger(__name__)


def get_dashboard_insights(company):
    """
    Generate real-time insights for company dashboard.
    Returns dict of alerts, suggestions, opportunities, and legal_alerts.
    """
    today = date.today()
    alerts = []
    suggestions = []
    opportunities = []
    legal_alerts = []

    # ══════════════════════════════════════════════════════════════
    # SEKCIJA A: Operativni insighti (postojeći)
    # ══════════════════════════════════════════════════════════════

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
    except (ValueError, TypeError):
        pass

    # 2. NIZAK STOCK
    try:
        from django.db.models import F

        from inventory.models import InventoryItem
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
    except DatabaseError:
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
    except DatabaseError:
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
    except DatabaseError:
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
    except (ValueError, TypeError):
        pass

    # 6. POS PROMET DANAS
    try:
        from pos.models import POSReceipt
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
    except (ValueError, TypeError):
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
    except DatabaseError:
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
    except DatabaseError:
        pass

    # ══════════════════════════════════════════════════════════════
    # SEKCIJA B: BORG FENIX Knowledge Graph insighti
    # ══════════════════════════════════════════════════════════════

    # 9. PRONAĐENE PRILIKE ZA UŠTEDU (ClientOpportunityMatch)
    try:
        from limit_connect_ai.models_knowledge_graph import ClientOpportunityMatch
        active_matches = ClientOpportunityMatch.objects.filter(
            company=company,
            status__in=['identified', 'notified', 'interested'],
            opportunity__is_active=True,
        ).select_related('opportunity')[:5]

        total_savings = Decimal('0')
        for match in active_matches:
            total_savings += match.calculated_savings or Decimal('0')

        match_count = len(active_matches)
        if match_count > 0:
            # Glavni insight — ukupna ušteda
            opportunities.append({
                'type': 'success',
                'icon': 'gift',
                'title': f'{match_count} {"prilika" if match_count == 1 else "prilika"} za ustedu',
                'detail': f'Potencijalna usteda: {total_savings:,.2f} EUR',
                'action_url': '/hr/intelligence/',
                'action_text': 'Pregledaj prilike',
            })

            # Top 3 prilike — pojedinačno
            for match in active_matches[:3]:
                opp = match.opportunity
                deadline_str = ''
                if opp.deadline:
                    days_left = (opp.deadline - today).days
                    if days_left <= 14:
                        deadline_str = f' (rok: {opp.deadline:%d.%m.}, jos {days_left} dana!)'
                    elif days_left <= 30:
                        deadline_str = f' (rok: {opp.deadline:%d.%m.})'

                opportunities.append({
                    'type': 'info',
                    'icon': _opportunity_icon(opp.opportunity_type),
                    'title': f'{opp.name[:60]}{deadline_str}',
                    'detail': f'{match.calculated_savings:,.2f} EUR — {opp.get_opportunity_type_display()}',
                    'action_url': opp.url or '/hr/intelligence/',
                    'action_text': 'Detalji',
                })
    except (ValueError, TypeError):
        logger.debug('proactive_widget: opportunity match error', exc_info=True)

    # 10. NOVE ZAKONSKE PROMJENE (RegulatoryUpdate — zadnjih 7 dana)
    try:
        from limit_connect_ai.models_knowledge_graph import RegulatoryUpdate
        week_ago = today - timedelta(days=7)
        recent_updates = RegulatoryUpdate.objects.filter(
            publication_date__gte=week_ago,
            is_processed=True,
            impact_score__gte=5,  # Samo relevantne — ne zagušuj dashboard
        ).order_by('-impact_score', '-publication_date')[:5]

        for update in recent_updates:
            affected = update.affected_modules or []
            if update.is_breaking:
                legal_alerts.append({
                    'type': 'danger',
                    'icon': 'alert-octagon',
                    'title': f'{update.title[:70]}',
                    'detail': f'{update.nn_number or update.get_category_display()} — '
                              f'impact {update.impact_score}/10'
                              f'{" — utjece na: " + ", ".join(affected) if affected else ""}',
                    'action_url': update.url or '/hr/intelligence/',
                    'action_text': 'Procitaj',
                })
            elif update.impact_score >= 7:
                legal_alerts.append({
                    'type': 'warning',
                    'icon': 'book',
                    'title': f'{update.title[:70]}',
                    'detail': f'{update.nn_number or update.get_category_display()} — '
                              f'impact {update.impact_score}/10',
                    'action_url': update.url or '/hr/intelligence/',
                    'action_text': 'Procitaj',
                })
            else:
                legal_alerts.append({
                    'type': 'info',
                    'icon': 'file-text',
                    'title': f'{update.title[:70]}',
                    'detail': f'{update.nn_number or update.get_category_display()}',
                    'action_url': update.url or '/hr/intelligence/',
                    'action_text': 'Procitaj',
                })
    except DatabaseError:
        logger.debug('proactive_widget: regulatory update error', exc_info=True)

    # 11. RIZICI U LANCU OPSKRBE (SupplierRiskAlert)
    try:
        from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert
        active_risks = SupplierRiskAlert.objects.filter(
            company=company,
            is_acknowledged=False,
            risk_level__in=['HIGH', 'CRITICAL'],
        ).order_by('-detected_at')[:3]

        for risk in active_risks:
            alerts.append({
                'type': 'danger' if risk.risk_level == 'CRITICAL' else 'warning',
                'icon': 'shield-off',
                'title': f'Rizik: {risk.supplier_name[:50]}',
                'detail': f'{risk.get_risk_level_display()} — {risk.risk_description[:80]}',
                'action_url': '/hr/intelligence/',
                'action_text': 'Detalji',
            })
    except DatabaseError:
        logger.debug('proactive_widget: supplier risk error', exc_info=True)

    return {
        'alerts': alerts,
        'suggestions': suggestions,
        'opportunities': opportunities,
        'legal_alerts': legal_alerts,
        'total_alerts': len(alerts),
        'total_suggestions': len(suggestions),
        'total_opportunities': len(opportunities),
        'total_legal_alerts': len(legal_alerts),
    }


def _opportunity_icon(opp_type):
    """Vrati Feather icon name za tip prilike."""
    icons = {
        'tax_relief': 'percent',
        'employment_subsidy': 'users',
        'eu_fund': 'globe',
        'depreciation': 'trending-down',
        'vat_exemption': 'slash',
        'regional_aid': 'map-pin',
        'green_incentive': 'sun',
        'digital_voucher': 'smartphone',
    }
    return icons.get(opp_type, 'star')
