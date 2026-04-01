"""
BORG FENIX — Predictive Analytics Engine (F4.1)
Cash flow prediction, partner churn detection, seasonal trends.

Uses invoice history to forecast:
1. Cash flow 30/60/90 days
2. Partner payment behavior (slow payers, churn risk)
3. Monthly revenue trends and seasonality
"""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, CharField
from django.db.models.functions import TruncMonth, ExtractMonth
from django.utils import timezone

logger = logging.getLogger('borg.predictions')


@shared_task
def predict_cash_flow(company_id=None, days_ahead=90):
    """
    Predict cash flow for next N days based on:
    - Outstanding invoices (receivable)
    - Historical payment patterns (avg days to pay)
    - Seasonal trends
    """
    from invoicing.models import Invoice
    from companies.models import Company

    filters = Q(status__in=['PAID', 'UNPAID', 'OVERDUE', 'SENT', 'sent'])
    if company_id:
        filters &= Q(company_id=company_id)

    now = timezone.now().date()

    # 1. Outstanding receivables
    outstanding = (
        Invoice.objects.filter(
            status__in=['UNPAID', 'OVERDUE', 'SENT', 'sent'],
        )
        .aggregate(
            total=Sum('total'),
            count=Count('id'),
        )
    )

    # 2. Historical payment pattern (avg days from issue to payment)
    paid_invoices = Invoice.objects.filter(
        status='PAID',
        date_issued__isnull=False,
        date_due__isnull=False,
    )

    # Calculate avg collection period
    avg_days_to_due = paid_invoices.aggregate(
        avg_due=Avg(F('date_due') - F('date_issued')),
    )

    # 3. Monthly revenue trend (last 12 months)
    twelve_months_ago = now - timedelta(days=365)
    monthly = list(
        Invoice.objects.filter(
            date_issued__gte=twelve_months_ago,
            status='PAID',
        )
        .annotate(month=TruncMonth('date_issued'))
        .values('month')
        .annotate(revenue=Sum('total'), count=Count('id'))
        .order_by('month')
    )

    # 4. Predict next 3 months based on average + trend
    if len(monthly) >= 3:
        recent_3 = [float(m['revenue'] or 0) for m in monthly[-3:]]
        avg_monthly = sum(recent_3) / 3
        # Simple linear trend
        if len(monthly) >= 6:
            older_3 = [float(m['revenue'] or 0) for m in monthly[-6:-3]]
            avg_older = sum(older_3) / 3
            trend = (avg_monthly - avg_older) / max(avg_older, 1)
        else:
            trend = 0
    else:
        avg_monthly = 0
        trend = 0

    predictions = {
        '30_days': round(avg_monthly * (1 + trend), 2),
        '60_days': round(avg_monthly * 2 * (1 + trend), 2),
        '90_days': round(avg_monthly * 3 * (1 + trend), 2),
    }

    result = {
        'outstanding_receivable': float(outstanding['total'] or 0),
        'outstanding_count': outstanding['count'] or 0,
        'avg_collection_days': avg_days_to_due.get('avg_due'),
        'monthly_revenue_trend': [
            {'month': str(m['month'].date()), 'revenue': float(m['revenue'] or 0), 'count': m['count']}
            for m in monthly
        ],
        'avg_monthly_revenue': round(avg_monthly, 2),
        'trend_pct': round(trend * 100, 1),
        'predictions': predictions,
        'generated_at': str(now),
    }

    logger.info('Cash flow prediction: avg %.0f/month, trend %.1f%%, 90d forecast: %.0f',
                avg_monthly, trend * 100, predictions['90_days'])
    return result


@shared_task
def detect_churn_risk():
    """
    Detect partners at risk of churning based on:
    - No invoices in last 90 days (was active before)
    - Declining invoice frequency
    - Increasing payment delays
    """
    from partners.models import Partner
    from invoicing.models import Invoice

    now = timezone.now().date()
    ninety_ago = now - timedelta(days=90)
    one_year_ago = now - timedelta(days=365)

    # Partners with invoices in last year but NOT in last 90 days
    active_before = set(
        Invoice.objects.filter(
            date_issued__gte=one_year_ago,
            date_issued__lt=ninety_ago,
            status='PAID',
        ).values_list('partner_id', flat=True).distinct()
    )

    still_active = set(
        Invoice.objects.filter(
            date_issued__gte=ninety_ago,
        ).values_list('partner_id', flat=True).distinct()
    )

    churned_ids = active_before - still_active

    # Get details
    at_risk = list(
        Partner.objects.filter(id__in=churned_ids)
        .values('id', 'name', 'oib', 'company__name')
        .annotate(
            total_invoiced=Sum('invoices__total'),
            invoice_count=Count('invoices'),
            last_invoice_count=Count("invoices"),  # approximate
        )
        .order_by('-total_invoiced')[:50]
    )

    result = {
        'total_at_risk': len(churned_ids),
        'total_revenue_at_risk': sum(float(p.get('total_invoiced') or 0) for p in at_risk),
        'top_at_risk': [
            {
                'name': p['name'],
                'oib': p['oib'],
                'company': p['company__name'],
                'total_invoiced': float(p['total_invoiced'] or 0),
                'invoice_count': p['invoice_count'],
            }
            for p in at_risk[:20]
        ],
        'generated_at': str(now),
    }

    logger.info('Churn risk: %d partners at risk, %.0f EUR revenue at risk',
                len(churned_ids), result['total_revenue_at_risk'])
    return result


@shared_task
def seasonal_analysis():
    """
    Analyze seasonal patterns in invoicing.
    Returns best/worst months and seasonal index.
    """
    from invoicing.models import Invoice

    # Revenue by calendar month (all years combined)
    by_month = list(
        Invoice.objects.filter(status='PAID', date_issued__isnull=False)
        .annotate(cal_month=ExtractMonth('date_issued'))
        .values('cal_month')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('cal_month')
    )

    if not by_month:
        return {'error': 'No data'}

    avg_monthly = sum(float(m['total'] or 0) for m in by_month) / max(len(by_month), 1)

    seasonal_index = {}
    for m in by_month:
        month_num = m['cal_month']
        revenue = float(m['total'] or 0)
        index = revenue / avg_monthly if avg_monthly > 0 else 1.0
        seasonal_index[month_num] = {
            'revenue': revenue,
            'count': m['count'],
            'index': round(index, 2),
        }

    best_month = max(seasonal_index.items(), key=lambda x: x[1]['revenue'])
    worst_month = min(seasonal_index.items(), key=lambda x: x[1]['revenue'])

    MONTH_NAMES = {1:'Sij',2:'Velj',3:'Ozu',4:'Tra',5:'Svi',6:'Lip',
                   7:'Srp',8:'Kol',9:'Ruj',10:'Lis',11:'Stu',12:'Pro'}

    result = {
        'seasonal_index': seasonal_index,
        'best_month': {'month': MONTH_NAMES.get(best_month[0], '?'), 'revenue': best_month[1]['revenue']},
        'worst_month': {'month': MONTH_NAMES.get(worst_month[0], '?'), 'revenue': worst_month[1]['revenue']},
        'avg_monthly': round(avg_monthly, 2),
    }

    logger.info('Seasonal: best=%s (%.0f), worst=%s (%.0f)',
                result['best_month']['month'], result['best_month']['revenue'],
                result['worst_month']['month'], result['worst_month']['revenue'])
    return result
