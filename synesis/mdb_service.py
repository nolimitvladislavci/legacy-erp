"""
Synesis MDB Reader — reads Storage.mdb via pyodbc or subprocess mdb-export.
Server-side: uses mdbtools (apt install mdbtools) since no ODBC driver on Linux.
"""
import subprocess
import csv
import io
import os
import json
import tempfile
from decimal import Decimal


def _mdb_export(mdb_path, table_name):
    """Export a table from MDB using mdb-export (mdbtools)."""
    try:
        result = subprocess.run(
            ['mdb-export', mdb_path, table_name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
        reader = csv.DictReader(io.StringIO(result.stdout))
        return list(reader)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _mdb_tables(mdb_path):
    """List tables in MDB file."""
    try:
        result = subprocess.run(
            ['mdb-tables', '-1', mdb_path],
            capture_output=True, text=True, timeout=10
        )
        return [t.strip() for t in result.stdout.strip().split('\n') if t.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def read_mdb_summary(mdb_path):
    """Get summary of key tables in Storage.mdb."""
    tables = _mdb_tables(mdb_path)
    counts = {}
    key_tables = ['PARTNERS', 'ITEMS', 'INVOICES', 'TINVOICES', 'ACCOUNTING',
                  'TACCOUNTING', 'EMPLOYEES', 'IRAEU', 'TIRAEU', 'URAEU', 'TURAEU',
                  'RETAIL', 'TRETAIL', 'PAYROLL2', 'TPAYROLL2']
    for t in key_tables:
        if t in tables:
            rows = _mdb_export(mdb_path, t)
            counts[t] = len(rows)
        else:
            counts[t] = 0
    return counts


def read_partners(mdb_path):
    """Read partners from Storage.mdb."""
    rows = _mdb_export(mdb_path, 'PARTNERS')
    partners = []
    for r in rows:
        partners.append({
            'synesis_id': r.get('PARTNER_ID', '').strip(),
            'name': r.get('PARTNER_NAME', '').strip(),
            'city': r.get('CITY_NAME', '').strip(),
            'zip_code': r.get('CITY_ZIPCODE', '').strip(),
            'street': r.get('PARTNER_STREET', '').strip(),
            'oib': r.get('PARTNER_VATNUMBER', '').strip(),
            'mb': r.get('PARTNER_MB', '').strip(),
            'iban': r.get('PARTNER_IBAN', '').strip(),
            'email': r.get('PARTNER_EMAIL', '').strip(),
            'phone': r.get('PARTNER_PHONE', '').strip() or r.get('PARTNER_MOBILE', '').strip(),
        })
    return partners


def read_items(mdb_path):
    """Read items/articles from Storage.mdb."""
    rows = _mdb_export(mdb_path, 'ITEMS')
    items = []
    for r in rows:
        items.append({
            'code': r.get('ITEM_ID', '').strip(),
            'name': r.get('ITEM_NAME', '').strip(),
            'unit': r.get('ITEM_MEASURE', '').strip(),
            'barcode': r.get('ITEM_BARCODE', '').strip(),
            'vat_rate': r.get('VAT_RATE', '').strip(),
            'net_price': r.get('ITEM_NETPRICE', '').strip(),
            'gross_price': r.get('ITEM_PRICE', '').strip(),
            'group': r.get('ITEMGROUP_NAME', '').strip(),
        })
    return items


def read_invoices(mdb_path):
    """Read issued invoices from Storage.mdb."""
    headers_raw = _mdb_export(mdb_path, 'INVOICES')
    lines_raw = _mdb_export(mdb_path, 'TINVOICES')

    headers = {}
    for r in headers_raw:
        din = r.get('DIN', '').strip()
        headers[din] = {
            'din': din,
            'number': r.get('INVOICE_NUMBER', '').strip(),
            'date': r.get('INVOICE_DATE', '').strip()[:10],
            'customer_name': r.get('CUSTOMER_NAME', '').strip(),
            'customer_oib': r.get('CUSTOMER_VATNUMBER', '').strip(),
            'lines': [],
            'total': 0,
        }

    for r in lines_raw:
        din = r.get('DIN', '').strip()
        if din in headers:
            try:
                amt = float(r.get('ITEM_AMMOUNT', '0') or '0')
            except ValueError:
                amt = 0
            headers[din]['lines'].append({
                'item_name': r.get('ITEM_NAME', '').strip(),
                'amount': amt,
            })
            headers[din]['total'] += amt

    return sorted(headers.values(), key=lambda x: x.get('date', ''))


def import_partners_to_erp(mdb_path, company):
    """Import partners from MDB into ERP Partner model."""
    from partners.models import Partner
    partners = read_partners(mdb_path)
    created = 0
    skipped = 0
    for p in partners:
        if not p['name']:
            continue
        oib = p['oib'][:20] if p['oib'] else ''
        # Check if exists by OIB or name
        exists = False
        if oib and len(oib) >= 11:
            exists = Partner.objects.filter(company=company, oib=oib).exists()
        if not exists:
            exists = Partner.objects.filter(company=company, name=p['name']).exists()
        if exists:
            skipped += 1
            continue
        Partner.objects.create(
            company=company,
            name=p['name'],
            oib=oib,
            city=p['city'],
            zip_code=p['zip_code'],
            address=p['street'],
            email=p['email'],
            phone=p['phone'],
            iban=p['iban'],
            partner_type='both',
        )
        created += 1
    return {'created': created, 'skipped': skipped, 'total': len(partners)}


def import_items_to_erp(mdb_path, company):
    """Import items from MDB into ERP InventoryItem model."""
    from inventory.models import InventoryItem
    items = read_items(mdb_path)
    created = 0
    skipped = 0
    for item in items:
        if not item['name']:
            continue
        code = item['code'].strip()
        if InventoryItem.objects.filter(company=company, sku=code).exists():
            skipped += 1
            continue
        try:
            price = Decimal(str(item['net_price'] or '0'))
        except (ValueError, TypeError):
            price = Decimal('0')
        InventoryItem.objects.create(
            company=company,
            name=item['name'],
            sku=code,
            unit=item['unit'] or 'KOM',
            purchase_price=price,
            barcode=item['barcode'] or '',
            category='other',
        )
        created += 1
    return {'created': created, 'skipped': skipped, 'total': len(items)}


# ═══ JSON Import Support ═══════════════════════════════════════════════
# Synesis sync script exports JSON — accept that directly too.

def read_json_file(json_path):
    """
    Čita JSON export iz Synesis sync skripte.
    Podržava formate:
      - {"type": "partners", "data": [...]}
      - {"partners": [...], "items": [...]}
      - [{"PARTNER_NAME": ...}, ...] (raw array)
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    result = {'partners': [], 'items': [], 'pos': [], 'invoices': []}

    if isinstance(raw, list):
        # Detect type from first item keys
        if raw and 'PARTNER_NAME' in raw[0]:
            result['partners'] = raw
        elif raw and 'ITEM_NAME' in raw[0]:
            result['items'] = raw
        elif raw and 'RECEIPT_ID' in raw[0]:
            result['pos'] = raw
        return result

    if isinstance(raw, dict):
        if 'type' in raw and 'data' in raw:
            # Single-type format: {"type": "partners", "data": [...]}
            result[raw['type']] = raw['data']
        else:
            # Multi-type: {"partners": [...], "items": [...]}
            for key in ('partners', 'items', 'pos', 'invoices'):
                if key in raw and isinstance(raw[key], list):
                    result[key] = raw[key]

    return result


def json_summary(json_path):
    """Preview summary of JSON file."""
    data = read_json_file(json_path)
    return {
        'PARTNERS': len(data.get('partners', [])),
        'ITEMS': len(data.get('items', [])),
        'POS': len(data.get('pos', [])),
        'INVOICES': len(data.get('invoices', [])),
    }


def json_partners_preview(json_path):
    """Preview partners from JSON."""
    data = read_json_file(json_path)
    partners = []
    for r in data.get('partners', []):
        partners.append({
            'synesis_id': str(r.get('PARTNER_ID', '')).strip(),
            'name': (r.get('PARTNER_NAME') or '').strip(),
            'city': (r.get('CITY_NAME') or '').strip(),
            'zip_code': (r.get('CITY_ZIPCODE') or '').strip(),
            'street': (r.get('PARTNER_STREET') or '').strip(),
            'oib': (r.get('PARTNER_VATNUMBER') or '').strip(),
            'email': (r.get('PARTNER_EMAIL') or '').strip(),
            'phone': (r.get('PARTNER_PHONE') or r.get('PARTNER_MOBILE') or '').strip(),
        })
    return partners


def json_items_preview(json_path):
    """Preview items from JSON."""
    data = read_json_file(json_path)
    items = []
    for r in data.get('items', []):
        items.append({
            'code': str(r.get('ITEM_ID', '')).strip(),
            'name': (r.get('ITEM_NAME') or '').strip(),
            'unit': (r.get('ITEM_MEASURE') or '').strip(),
            'barcode': (r.get('ITEM_BARCODE') or '').strip(),
            'vat_rate': str(r.get('VAT_RATE', '')).strip(),
            'net_price': str(r.get('ITEM_NETPRICE', '')).strip(),
            'gross_price': str(r.get('ITEM_PRICE', '')).strip(),
            'group': (r.get('ITEMGROUP_NAME') or '').strip(),
        })
    return items


def import_json_to_erp(json_path, company):
    """Import all data from JSON file into ERP using existing import functions."""
    from synesis.views import _import_partners, _import_items, _import_pos

    data = read_json_file(json_path)
    results = {}

    if data.get('partners'):
        results['partners'] = _import_partners(company, data['partners'])

    if data.get('items'):
        results['items'] = _import_items(company, data['items'])

    if data.get('pos'):
        results['pos'] = _import_pos(company, data['pos'])

    return results
