"""
Partner Intelligence — cross-company aggregation without breaking tenant isolation.

All queries use raw SQL with GROUP BY oib for performance.
No FK rewiring, no cross-tenant data mutation — read-only aggregation.
"""
import logging
from django.db import connection

logger = logging.getLogger(__name__)


def get_intelligence_stats(company_ids: list) -> dict:
    """
    Aggregate partner intelligence across multiple companies.
    company_ids: list of UUID company IDs (umbrella children).
    """
    if not company_ids:
        return _empty_stats()

    placeholders = ','.join(['%s'] * len(company_ids))
    ids = [str(c) for c in company_ids]

    stats = {}
    stats.update(_top_partners(placeholders, ids))
    stats.update(_buyer_type_distribution(placeholders, ids))
    stats.update(_anomalies(placeholders, ids))
    stats.update(_vat_overview(placeholders, ids))
    stats.update(_data_quality(placeholders, ids))
    return stats


def search_partner_global(oib: str, company_ids: list) -> list:
    """Search for a partner by OIB across all companies."""
    if not company_ids or not oib:
        return []

    placeholders = ','.join(['%s'] * len(company_ids))
    ids = [str(c) for c in company_ids]

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT p.id, p.name, p.oib, p.city, p.buyer_type,
                   p.is_vat_registered, p.cached_balance, p.email, p.phone, p.iban,
                   c.name as company_name, c.id as company_id,
                   (SELECT COUNT(*) FROM invoicing_invoice i WHERE i.partner_id = p.id) as invoice_count,
                   (SELECT COALESCE(SUM(i.total), 0) FROM invoicing_invoice i
                    WHERE i.partner_id = p.id AND i.status IN ('UNPAID','OVERDUE')) as unpaid_total
            FROM partners_partner p
            JOIN companies_company c ON c.id = p.company_id
            WHERE p.oib = %s AND p.company_id IN ({placeholders})
            ORDER BY c.name
        """, [oib] + ids)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _top_partners(placeholders, ids):
    """Top 15 partners by aggregated unpaid balance across companies."""
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT p.oib, p.name,
                   COUNT(DISTINCT p.company_id) as in_companies,
                   COALESCE(SUM(inv.unpaid), 0) as total_unpaid,
                   COALESCE(SUM(inv.total_invoiced), 0) as total_invoiced,
                   COUNT(DISTINCT inv.inv_count) as invoice_count
            FROM partners_partner p
            LEFT JOIN LATERAL (
                SELECT
                    SUM(CASE WHEN i.status IN ('UNPAID','OVERDUE') THEN i.total ELSE 0 END) as unpaid,
                    SUM(CASE WHEN i.status IN ('SENT','PAID','UNPAID','OVERDUE') THEN i.total ELSE 0 END) as total_invoiced,
                    COUNT(*) as inv_count
                FROM invoicing_invoice i
                WHERE i.partner_id = p.id AND i.doctype = 'R'
            ) inv ON true
            WHERE p.company_id IN ({placeholders})
              AND p.oib ~ '^\\d{{11}}$'
            GROUP BY p.oib, p.name
            HAVING COALESCE(SUM(inv.total_invoiced), 0) > 0
            ORDER BY total_unpaid DESC
            LIMIT 15
        """, ids)
        cols = [c[0] for c in cur.description]
        top_debtors = [dict(zip(cols, row)) for row in cur.fetchall()]

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT p.oib, p.name,
                   COUNT(DISTINCT p.company_id) as in_companies,
                   COALESCE(SUM(inv.total_invoiced), 0) as total_invoiced
            FROM partners_partner p
            LEFT JOIN LATERAL (
                SELECT SUM(i.total) as total_invoiced
                FROM invoicing_invoice i
                WHERE i.partner_id = p.id AND i.doctype = 'R'
                  AND i.status IN ('SENT','PAID','UNPAID','OVERDUE')
            ) inv ON true
            WHERE p.company_id IN ({placeholders})
              AND p.oib ~ '^\\d{{11}}$'
            GROUP BY p.oib, p.name
            HAVING COALESCE(SUM(inv.total_invoiced), 0) > 0
            ORDER BY total_invoiced DESC
            LIMIT 15
        """, ids)
        cols = [c[0] for c in cur.description]
        top_by_volume = [dict(zip(cols, row)) for row in cur.fetchall()]

    return {'top_debtors': top_debtors, 'top_by_volume': top_by_volume}


def _buyer_type_distribution(placeholders, ids):
    """Buyer type distribution across all companies."""
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT buyer_type, COUNT(*) as cnt,
                   ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) as pct
            FROM partners_partner
            WHERE company_id IN ({placeholders})
            GROUP BY buyer_type
            ORDER BY cnt DESC
        """, ids)
        cols = [c[0] for c in cur.description]
        return {'buyer_types': [dict(zip(cols, row)) for row in cur.fetchall()]}


def _anomalies(placeholders, ids):
    """
    Detect inconsistencies: same OIB with different buyer_types or names.
    """
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT oib,
                   array_agg(DISTINCT name) as names,
                   array_agg(DISTINCT buyer_type) as buyer_types,
                   COUNT(DISTINCT buyer_type) as type_count,
                   COUNT(DISTINCT company_id) as in_companies
            FROM partners_partner
            WHERE company_id IN ({placeholders})
              AND oib ~ '^\\d{{11}}$'
            GROUP BY oib
            HAVING COUNT(DISTINCT buyer_type) > 1
            ORDER BY COUNT(DISTINCT buyer_type) DESC
            LIMIT 20
        """, ids)
        cols = [c[0] for c in cur.description]
        type_mismatches = [dict(zip(cols, row)) for row in cur.fetchall()]

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT oib,
                   array_agg(DISTINCT name ORDER BY name) as names,
                   COUNT(DISTINCT name) as name_count,
                   COUNT(DISTINCT company_id) as in_companies
            FROM partners_partner
            WHERE company_id IN ({placeholders})
              AND oib ~ '^\\d{{11}}$'
            GROUP BY oib
            HAVING COUNT(DISTINCT name) > 1
            ORDER BY COUNT(DISTINCT name) DESC
            LIMIT 20
        """, ids)
        cols = [c[0] for c in cur.description]
        name_mismatches = [dict(zip(cols, row)) for row in cur.fetchall()]

    return {
        'type_mismatches': type_mismatches,
        'type_mismatch_count': len(type_mismatches),
        'name_mismatches': name_mismatches,
        'name_mismatch_count': len(name_mismatches),
    }


def _vat_overview(placeholders, ids):
    """VAT registration overview by unique OIB."""
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT
                COUNT(DISTINCT oib) as total_unique_oib,
                COUNT(DISTINCT CASE WHEN is_vat_registered THEN oib END) as vat_registered,
                COUNT(DISTINCT CASE WHEN NOT is_vat_registered THEN oib END) as not_vat_registered,
                COUNT(DISTINCT CASE WHEN vat_id != '' THEN oib END) as has_vat_id,
                COUNT(DISTINCT CASE WHEN buyer_type = 'b2g' THEN oib END) as budget_users,
                COUNT(DISTINCT CASE WHEN buyer_type LIKE 'b2b%%' THEN oib END) as b2b_total,
                COUNT(DISTINCT CASE WHEN buyer_type = 'b2c' THEN oib END) as b2c_total
            FROM partners_partner
            WHERE company_id IN ({placeholders})
              AND oib ~ '^\\d{{11}}$'
        """, ids)
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return {'vat_overview': dict(zip(cols, row)) if row else {}}


def _data_quality(placeholders, ids):
    """Data completeness metrics."""
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN email != '' THEN 1 ELSE 0 END) as has_email,
                SUM(CASE WHEN phone != '' THEN 1 ELSE 0 END) as has_phone,
                SUM(CASE WHEN address != '' THEN 1 ELSE 0 END) as has_address,
                SUM(CASE WHEN iban != '' THEN 1 ELSE 0 END) as has_iban,
                SUM(CASE WHEN oib ~ '^\\d{{11}}$' THEN 1 ELSE 0 END) as has_valid_oib,
                SUM(CASE WHEN oib LIKE 'SYN-%%' THEN 1 ELSE 0 END) as synesis_oib
            FROM partners_partner
            WHERE company_id IN ({placeholders})
        """, ids)
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        dq = dict(zip(cols, row)) if row else {}

    total = dq.get('total', 1) or 1
    dq['email_pct'] = round(dq.get('has_email', 0) * 100 / total, 1)
    dq['phone_pct'] = round(dq.get('has_phone', 0) * 100 / total, 1)
    dq['address_pct'] = round(dq.get('has_address', 0) * 100 / total, 1)
    dq['iban_pct'] = round(dq.get('has_iban', 0) * 100 / total, 1)
    dq['oib_pct'] = round(dq.get('has_valid_oib', 0) * 100 / total, 1)

    return {'data_quality': dq}


def _empty_stats():
    return {
        'top_debtors': [], 'top_by_volume': [],
        'buyer_types': [],
        'type_mismatches': [], 'type_mismatch_count': 0,
        'name_mismatches': [], 'name_mismatch_count': 0,
        'vat_overview': {},
        'data_quality': {},
    }
