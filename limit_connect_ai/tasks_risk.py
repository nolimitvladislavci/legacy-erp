"""
limit_connect_ai/tasks_risk.py — Supplier Risk Scoring
Analyses payment behavior from URA invoices to populate SupplierRiskAlert.
"""
from celery import shared_task
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q, F
import json
import logging

logger = logging.getLogger('borg_fenix')


@shared_task(bind=True, max_retries=1, default_retry_delay=120, time_limit=600)
def scan_supplier_risk(self, company_id=None):
    """
    Scan all companies (or one) for supplier payment risk.

    Risk scoring based on:
    - Average payment delay (date_due vs status change to PAID)
    - Total outstanding debt (unpaid URA)
    - Debt trend (growing or shrinking)

    Levels:
    - LOW: pays on time, debt < 5K EUR
    - MEDIUM: 30+ days late OR debt 5-20K EUR
    - HIGH: 60+ days late OR debt > 20K EUR
    - CRITICAL: 90+ days late OR debt > 50K EUR
    """
    from companies.models import Company
    from invoicing.models import Invoice
    from partners.models import Partner
    from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert

    if company_id:
        companies = Company.objects.filter(id=company_id)
    else:
        companies = Company.objects.all()

    stats = {'companies': 0, 'suppliers_scanned': 0, 'alerts_created': 0, 'alerts_updated': 0}
    now = timezone.now()

    for company in companies:
        stats['companies'] += 1

        # Find all suppliers (partners with URA invoices)
        supplier_oibs = (
            Invoice.objects.filter(company=company, doctype='URA')
            .exclude(partner__isnull=True)
            .exclude(partner__oib__isnull=True)
            .exclude(partner__oib='')
            .values_list('partner__oib', flat=True)
            .distinct()
        )

        for oib in supplier_oibs:
            stats['suppliers_scanned'] += 1
            partner = Partner.objects.filter(company=company, oib=oib).first()
            if not partner:
                continue

            # Get all URA for this supplier
            uras = Invoice.objects.filter(
                company=company, doctype='URA', partner=partner
            ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO'])

            total_count = uras.count()
            if total_count == 0:
                continue

            # Outstanding debt (unpaid URA)
            unpaid = uras.exclude(status='PAID')
            outstanding_debt = unpaid.aggregate(
                total=Sum('total')
            )['total'] or Decimal('0')

            # Overdue invoices
            overdue = unpaid.filter(date_due__lt=now.date())
            overdue_count = overdue.count()

            # Max overdue days
            max_overdue_days = 0
            if overdue.exists():
                oldest = overdue.order_by('date_due').first()
                if oldest and oldest.date_due:
                    max_overdue_days = (now.date() - oldest.date_due).days

            # Determine risk level
            risk_level = 'LOW'
            reasons = []

            if max_overdue_days >= 90 or outstanding_debt > Decimal('50000'):
                risk_level = 'CRITICAL'
                if max_overdue_days >= 90:
                    reasons.append(f'{max_overdue_days} dana kašnjenja')
                if outstanding_debt > Decimal('50000'):
                    reasons.append(f'dug {outstanding_debt:.2f} EUR')
            elif max_overdue_days >= 60 or outstanding_debt > Decimal('20000'):
                risk_level = 'HIGH'
                if max_overdue_days >= 60:
                    reasons.append(f'{max_overdue_days} dana kašnjenja')
                if outstanding_debt > Decimal('20000'):
                    reasons.append(f'dug {outstanding_debt:.2f} EUR')
            elif max_overdue_days >= 30 or outstanding_debt > Decimal('5000'):
                risk_level = 'MEDIUM'
                if max_overdue_days >= 30:
                    reasons.append(f'{max_overdue_days} dana kašnjenja')
                if outstanding_debt > Decimal('5000'):
                    reasons.append(f'dug {outstanding_debt:.2f} EUR')
            else:
                reasons.append('plaća na vrijeme')

            risk_description = '; '.join(reasons) if reasons else 'Nizak rizik'

            source_data = {
                'total_ura': total_count,
                'unpaid_count': unpaid.count(),
                'overdue_count': overdue_count,
                'outstanding_debt': str(outstanding_debt),
                'max_overdue_days': max_overdue_days,
                'scan_date': now.isoformat(),
            }

            # Create or update alert
            alert, created = SupplierRiskAlert.objects.update_or_create(
                company=company,
                supplier_oib=oib,
                defaults={
                    'supplier_name': partner.name[:255],
                    'risk_level': risk_level,
                    'risk_description': risk_description,
                    'source_data': source_data,
                }
            )

            if created:
                stats['alerts_created'] += 1
            else:
                stats['alerts_updated'] += 1

    logger.info(f"SupplierRisk scan complete: {stats}")
    return stats


@shared_task(bind=True, max_retries=0)
def scan_all_supplier_risk(self):
    """Convenience task to scan ALL companies. Schedule via celery-beat."""
    return scan_supplier_risk()
