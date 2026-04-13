"""
BORG FENIX — Cross-Company Anomaly Detector (F3.4)
Detects inconsistencies across companies sharing the same OIB.

Anomalies:
1. Same OIB, different buyer_type across companies
2. Same OIB, total unpaid > threshold
3. Same OIB, different names (data quality)
"""
import logging

from celery import shared_task
from django.db import connection
from django.utils import timezone

logger = logging.getLogger('borg.anomaly')


@shared_task
def detect_cross_company_anomalies(debt_threshold_eur=10000):
    """
    Run all anomaly detections and return structured results.
    """
    results = {
        'type_mismatches': detect_buyer_type_mismatches(),
        'high_debtors': detect_high_cross_company_debt(debt_threshold_eur),
        'name_mismatches': detect_name_mismatches(),
        'run_at': str(timezone.now()),
    }

    total = sum(len(v) for v in results.values() if isinstance(v, list))
    logger.info('Anomaly scan: %d total anomalies found', total)
    return results


def detect_buyer_type_mismatches():
    """Find OIBs that have different buyer_types across companies."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT p.oib, array_agg(DISTINCT buyer_type) as types,
                   array_agg(DISTINCT c.name) as companies,
                   COUNT(DISTINCT buyer_type) as type_count
            FROM partners_partner p
            JOIN companies_company c ON p.company_id = c.id
            WHERE p.oib ~ '^\\d{11}$'
              AND p.buyer_type IS NOT NULL AND p.buyer_type != ''
            GROUP BY p.oib
            HAVING COUNT(DISTINCT buyer_type) > 1
            ORDER BY COUNT(DISTINCT buyer_type) DESC
            LIMIT 50
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    logger.info('Buyer type mismatches: %d OIBs', len(rows))
    return rows


def detect_high_cross_company_debt(threshold_eur=10000):
    """Find OIBs with total unpaid invoices > threshold across all companies."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT p.oib, p.name,
                   COUNT(DISTINCT p.company_id) as in_companies,
                   COUNT(i.id) as invoice_count,
                   COALESCE(SUM(i.total), 0) as total_invoiced,
                   COALESCE(SUM(CASE WHEN i.status IN ('UNPAID', 'OVERDUE') THEN i.total ELSE 0 END), 0) as total_unpaid
            FROM partners_partner p
            LEFT JOIN invoicing_invoice i ON i.partner_id = p.id
            WHERE p.oib ~ '^\\d{11}$'
            GROUP BY p.oib, p.name
            HAVING COALESCE(SUM(CASE WHEN i.status IN ('UNPAID', 'OVERDUE') THEN i.total ELSE 0 END), 0) > %s
            ORDER BY total_unpaid DESC
            LIMIT 50
        """, [threshold_eur])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    logger.info('High debtors (>%d EUR): %d OIBs', threshold_eur, len(rows))
    return rows


def detect_name_mismatches():
    """Find OIBs that have different names across companies (data quality issue)."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT oib,
                   array_agg(DISTINCT name) as names,
                   COUNT(DISTINCT name) as name_count,
                   COUNT(DISTINCT company_id) as in_companies
            FROM partners_partner p
            WHERE p.oib ~ '^\\d{11}$'
              AND p.name IS NOT NULL AND name != ''
            GROUP BY p.oib
            HAVING COUNT(DISTINCT name) > 1
            ORDER BY COUNT(DISTINCT name) DESC
            LIMIT 100
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    logger.info('Name mismatches: %d OIBs', len(rows))
    return rows
