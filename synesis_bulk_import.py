#!/usr/bin/env python
"""Bulk import Synesis data for all firms from KONJIK_ARHIVA."""
import os, sys, csv, io, subprocess, re, logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Suppress debug noise
logging.disable(logging.DEBUG)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fina_connect.settings')
import django
django.setup()

from django.db import IntegrityError, transaction
from companies.models import Company
from invoicing.models import Invoice
from konto.models import KontoAccount
from django.utils import timezone

ARCHIVE = '/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis'
SKIP_FOLDERS = ['FAST 2025', 'KONJIK D.O.O. 2025(Popravljeno 1)']

def clean_name(folder_name):
    n = folder_name.strip()
    n = re.sub(r'\s+2025.*$', '', n)
    return n.strip()

def mdb_export(mdb_path, table):
    if not os.path.exists(mdb_path):
        return []
    try:
        result = subprocess.run(
            ['mdb-export', mdb_path, table],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
        reader = csv.DictReader(io.StringIO(result.stdout))
        return list(reader)
    except Exception as e:
        print(f"  ERROR mdb-export {table}: {e}")
        return []

def parse_date(s):
    if not s or not s.strip():
        return None
    s = s.strip().strip('"')
    for fmt in ['%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%Y-%m-%d', '%m/%d/%y']:
        try:
            dt = datetime.strptime(s, fmt)
            return timezone.make_aware(dt)
        except:
            continue
    return None

def parse_decimal(s):
    if not s or not s.strip():
        return Decimal('0')
    try:
        return Decimal(s.strip().strip('"'))
    except (InvalidOperation, ValueError):
        return Decimal('0')

def match_company(folder_name):
    clean = clean_name(folder_name)
    try:
        return Company.objects.get(name__iexact=clean)
    except Company.DoesNotExist:
        pass
    except Company.MultipleObjectsReturned:
        return Company.objects.filter(name__iexact=clean).first()
    
    try:
        return Company.objects.get(name__icontains=clean)
    except (Company.DoesNotExist, Company.MultipleObjectsReturned):
        pass
    
    mappings = {
        'EUROPA': 'Europa', 'EUROPA-KIOSK': 'Europa',
        'ĐURĐEVIĆ SLOBODAN': 'Đurđević Slobodan',
        'ĐURĐEVIĆ SRĐAN': 'Đurđević Srđan',
        'ŠARKEZI TIHOMIR': 'Šarkezi Tihomir',
        'ŽIVKOVIĆ ZDRAVKO': 'Živković Zdravko',
        'KONJIK D.O.O.': 'Konjik d.o.o.',
        'SATUS-PLAST D.O.O.': 'SATUS-PLAST d.o.o.',
        'SOLAR ECO D.O.O.': 'SOLAR ECO d.o.o.',
        'SOLVER-ING J.D.O.O.': 'SOLVER-ING j.d.o.o.',
        'SOLVERMAX J.D.O.O.': 'SOLVERMAX j.d.o.o.',
        'M-TEAM D.O.O.': 'M-Team D.O.O.',
        'FITOFARMING J.D.O.O.': 'Fitofarming J.D.O.O.',
        'NEBES TOMISLAV-DRAUCODE': 'Nebes Tomislav-Draucode',
        'ODVJ.URED BANDIĆ LUTONSKI': 'Odvj.Ured Bandić Lutonski',
        'KRUG VL.MILAN ZIMONJA': 'Krug Vl.Milan Zimonja',
        'BZ PANONSKI CVIJET': 'Bz Panonski Cvijet',
        'SREĆKO PO': 'Srećko Po',
    }
    mapped = mappings.get(clean.upper(), mappings.get(clean, clean))
    try:
        return Company.objects.get(name__iexact=mapped)
    except (Company.DoesNotExist, Company.MultipleObjectsReturned):
        pass
    return None

def safe_create_invoice(company, **kwargs):
    """Create invoice, handle number uniqueness by appending suffix if needed."""
    number = kwargs.get('number', '')
    for attempt in range(5):
        try:
            with transaction.atomic():
                inv = Invoice.objects.create(company=company, **kwargs)
                return inv
        except IntegrityError as e:
            if 'invoicing_invoice_company_number' in str(e):
                suffix = f"-{attempt+2}"
                kwargs['number'] = f"{number}{suffix}"
                kwargs['internal_id'] = kwargs['number']
                continue
            elif 'client_token' in str(e) or 'uuid' in str(e):
                # UUID collision, just retry
                from uuid import uuid4
                kwargs['uuid'] = uuid4()
                kwargs['client_token'] = uuid4()
                continue
            else:
                raise
    return None

def import_invoices_from_storage(company, mdb_path):
    rows = mdb_export(mdb_path, 'INVOICES')
    created = skipped = errors = 0
    for row in rows:
        din = row.get('DIN', '').strip()
        if not din: continue
        synesis_id = f"INV-{din}"
        if Invoice.objects.filter(company=company, synesis_id=synesis_id).exists():
            skipped += 1; continue
        
        inv_number = row.get('INVOICE_NUMBER', '').strip().strip('"')
        inv_date = parse_date(row.get('INVOICE_DATE', ''))
        due_date = parse_date(row.get('INVOICE_DUEDATE', ''))
        customer_name = row.get('CUSTOMER_NAME', '').strip().strip('"').strip()
        city = row.get('CITY_NAME', '').strip().strip('"').strip()
        zipcode = row.get('CITY_ZIPCODE', '').strip().strip('"').strip()
        street = row.get('PARTNER_STREET', '').strip().strip('"').strip()
        oib = row.get('PARTNER_VATNUMBER', '').strip().strip('"').strip()
        subtotal = parse_decimal(row.get('VAT_INVOICENETAMMOUNT', '0'))
        tax = parse_decimal(row.get('VAT_AMMOUNT', '0'))
        total = parse_decimal(row.get('VAT_INVOICEAMMOUNT', '0'))
        
        num = f"R-{inv_number}" if inv_number else f"R-SYN-{din}"
        result = safe_create_invoice(company,
            source='synesis', synesis_id=synesis_id, synesis_year=2025,
            doctype='R', invoice_type='racun',
            number=num, internal_id=num,
            date_issued=inv_date or timezone.make_aware(datetime(2025, 1, 1)),
            date_due=due_date.date() if due_date else None,
            client_name=customer_name or 'Nepoznat',
            client_address=street, client_city=f"{zipcode} {city}".strip(),
            client_oib=oib, subtotal=subtotal, tax_amount=tax, total=total,
            status='PAID', is_locked=True, currency='EUR',
        )
        if result: created += 1
        else: errors += 1
    return created, skipped, errors

def import_iraeu(company, mdb_path):
    rows = mdb_export(mdb_path, 'IRAEU')
    created = skipped = errors = 0
    for row in rows:
        din = row.get('DIN', '').strip()
        if not din: continue
        synesis_id = f"IRAEU-{din}"
        if Invoice.objects.filter(company=company, synesis_id=synesis_id).exists():
            skipped += 1; continue
        
        inv_number = row.get('VAT_INVOICENUMBER', '').strip().strip('"').strip()
        inv_date = parse_date(row.get('VAT_INVOICEDATE', '') or row.get('TRANDATE', ''))
        due_date = parse_date(row.get('DUE_DATE', ''))
        customer_name = row.get('CUSTOMER_NAME', '').strip().strip('"').strip()
        city = row.get('CITY_NAME', '').strip().strip('"').strip()
        zipcode = row.get('CITY_ZIPCODE', '').strip().strip('"').strip()
        street = row.get('PARTNER_STREET', '').strip().strip('"').strip()
        oib = row.get('PARTNER_VATNUMBER', '').strip().strip('"').strip()
        total = parse_decimal(row.get('VAT_INVOICEAMMOUNT', '0'))
        net = parse_decimal(row.get('VAT_INVOICENETAMMOUNT', '0'))
        tax = total - net if total > net else Decimal('0')
        
        num = f"IRA-{inv_number}" if inv_number else f"IRA-SYN-{din}"
        result = safe_create_invoice(company,
            source='synesis', synesis_id=synesis_id, synesis_year=2025,
            doctype='IRA', invoice_type='ira',
            number=num, internal_id=num,
            date_issued=inv_date or timezone.make_aware(datetime(2025, 1, 1)),
            date_due=due_date.date() if due_date else None,
            client_name=customer_name or 'Nepoznat',
            client_address=street, client_city=f"{zipcode} {city}".strip(),
            client_oib=oib, subtotal=net, tax_amount=tax, total=total,
            status='PAID', is_locked=True, currency='EUR',
        )
        if result: created += 1
        else: errors += 1
    return created, skipped, errors

def import_uraeu(company, mdb_path):
    rows = mdb_export(mdb_path, 'URAEU')
    created = skipped = errors = 0
    for row in rows:
        din = row.get('DIN', '').strip()
        if not din: continue
        synesis_id = f"URAEU-{din}"
        if Invoice.objects.filter(company=company, synesis_id=synesis_id).exists():
            skipped += 1; continue
        
        inv_number = row.get('VAT_INVOICENUMBER', '').strip().strip('"').strip()
        inv_date = parse_date(row.get('VAT_INVOICEDATE', '') or row.get('TRANDATE', ''))
        due_date = parse_date(row.get('DUE_DATE', ''))
        vendor_name = row.get('VENDOR_NAME', '').strip().strip('"').strip()
        city = row.get('CITY_NAME', '').strip().strip('"').strip()
        zipcode = row.get('CITY_ZIPCODE', '').strip().strip('"').strip()
        street = row.get('PARTNER_STREET', '').strip().strip('"').strip()
        oib = row.get('PARTNER_VATNUMBER', '').strip().strip('"').strip()
        total = parse_decimal(row.get('VAT_INVOICEAMMOUNT', '0'))
        net = parse_decimal(row.get('VAT_INVOICENETAMMOUNT', '0'))
        tax = parse_decimal(row.get('VAT_DEDUCTABLE', '0'))
        
        num = f"URA-{inv_number}" if inv_number else f"URA-SYN-{din}"
        result = safe_create_invoice(company,
            source='synesis', synesis_id=synesis_id, synesis_year=2025,
            doctype='URA', invoice_type='ura',
            number=num, internal_id=num,
            date_issued=inv_date or timezone.make_aware(datetime(2025, 1, 1)),
            date_due=due_date.date() if due_date else None,
            client_name=vendor_name or 'Nepoznat',
            client_address=street, client_city=f"{zipcode} {city}".strip(),
            client_oib=oib, subtotal=net, tax_amount=tax, total=total,
            status='PAID', is_locked=True, currency='EUR',
        )
        if result: created += 1
        else: errors += 1
    return created, skipped, errors

def import_smallinv(company, mdb_path):
    rows = mdb_export(mdb_path, 'SMALLINV')
    created = skipped = errors = 0
    for row in rows:
        din = row.get('DIN', '').strip()
        if not din: continue
        synesis_id = f"SMALLINV-{din}"
        if Invoice.objects.filter(company=company, synesis_id=synesis_id).exists():
            skipped += 1; continue
        
        inv_name = row.get('SMALLINV_NAME', '').strip().strip('"').strip()
        inv_date = parse_date(row.get('TRANDATE', ''))
        purchase_val = parse_decimal(row.get('SMALLINV_PURCHASEVALUE', '0'))
        doc_number = row.get('DOCUMENT_NUMBER', '').strip().strip('"').strip()
        vendor = row.get('INV_VENDOR', '').strip().strip('"').strip()
        
        if not inv_name and purchase_val == 0: continue
        
        num = f"SI-{doc_number}" if doc_number else f"SI-SYN-{din}"
        result = safe_create_invoice(company,
            source='synesis', synesis_id=synesis_id, synesis_year=2025,
            doctype='URA', invoice_type='sitni_inventar',
            number=num, internal_id=num,
            date_issued=inv_date or timezone.make_aware(datetime(2025, 1, 1)),
            client_name=vendor or inv_name or 'Sitni inventar',
            client_address='', client_city='', client_oib='',
            subtotal=purchase_val, tax_amount=Decimal('0'), total=purchase_val,
            status='PAID', is_locked=True, currency='EUR',
            note=f"Sitni inventar: {inv_name}",
        )
        if result: created += 1
        else: errors += 1
    return created, skipped, errors

def import_accounts(company, mdb_path):
    rows = mdb_export(mdb_path, 'ACCOUNTS')
    created = skipped = 0
    for row in rows:
        code = row.get('ACC_NUMBER', '').strip().strip('"').strip()
        if not code: continue
        name = row.get('ACC_NAME', '').strip().strip('"').strip()
        acc_class = row.get('ACC_CLASS', '').strip().strip('"').strip()
        
        if KontoAccount.objects.filter(company=company, code=code).exists():
            skipped += 1; continue
        
        type_map = {'0': 'asset', '1': 'asset', '2': 'liability', '3': 'equity',
                     '4': 'expense', '5': 'expense', '6': 'expense',
                     '7': 'revenue', '8': 'revenue', '9': 'equity'}
        account_type = type_map.get(acc_class, 'asset')
        
        try:
            KontoAccount.objects.create(
                company=company, code=code, name=name or f"Konto {code}",
                account_type=account_type, is_active=True,
            )
            created += 1
        except IntegrityError:
            skipped += 1
    return created, skipped

def process_batch(folders, batch_num):
    print(f"\n{'='*60}")
    print(f"BATCH {batch_num}: Processing {len(folders)} firms")
    print(f"{'='*60}")
    
    stats = {'inv': 0, 'ira': 0, 'ura': 0, 'si': 0, 'acc': 0,
             'inv_skip': 0, 'ira_skip': 0, 'ura_skip': 0, 'si_skip': 0, 'acc_skip': 0,
             'errors': 0, 'no_match': []}
    
    for folder in folders:
        folder_path = os.path.join(ARCHIVE, folder)
        storage_mdb = os.path.join(folder_path, 'Storage.mdb')
        
        company = match_company(folder)
        if not company:
            print(f"  SKIP {folder} — no matching company")
            stats['no_match'].append(folder)
            continue
        
        print(f"  {folder} → {company.name}")
        
        try:
            c, s, e = import_invoices_from_storage(company, storage_mdb)
            stats['inv'] += c; stats['inv_skip'] += s; stats['errors'] += e
            if c: print(f"    INV: +{c} ({s} skip, {e} err)")
            
            c, s, e = import_iraeu(company, storage_mdb)
            stats['ira'] += c; stats['ira_skip'] += s; stats['errors'] += e
            if c: print(f"    IRA: +{c} ({s} skip, {e} err)")
            
            c, s, e = import_uraeu(company, storage_mdb)
            stats['ura'] += c; stats['ura_skip'] += s; stats['errors'] += e
            if c: print(f"    URA: +{c} ({s} skip, {e} err)")
            
            c, s, e = import_smallinv(company, storage_mdb)
            stats['si'] += c; stats['si_skip'] += s; stats['errors'] += e
            if c: print(f"    SI: +{c} ({s} skip, {e} err)")
            
            c, s = import_accounts(company, storage_mdb)
            stats['acc'] += c; stats['acc_skip'] += s
            if c: print(f"    ACC: +{c} ({s} skip)")
            
        except Exception as e:
            print(f"    FATAL: {e}")
            stats['errors'] += 1
    
    print(f"\nBATCH {batch_num} TOTALS: INV +{stats['inv']} | IRA +{stats['ira']} | URA +{stats['ura']} | SI +{stats['si']} | ACC +{stats['acc']} | Errors: {stats['errors']}")
    if stats['no_match']:
        print(f"  Unmatched: {stats['no_match']}")
    return stats

if __name__ == '__main__':
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    all_folders = sorted([d for d in os.listdir(ARCHIVE) 
                         if os.path.isdir(os.path.join(ARCHIVE, d)) and d not in SKIP_FOLDERS])
    
    print(f"Total folders: {len(all_folders)}")
    
    batch_size = 10
    batches = [all_folders[i:i+batch_size] for i in range(0, len(all_folders), batch_size)]
    
    if batch_num == 0:
        grand = {'inv': 0, 'ira': 0, 'ura': 0, 'si': 0, 'acc': 0, 'errors': 0}
        for i, batch in enumerate(batches, 1):
            s = process_batch(batch, i)
            for k in grand:
                grand[k] += s.get(k, 0)
        print(f"\n{'='*60}")
        print(f"GRAND TOTAL: INV +{grand['inv']} | IRA +{grand['ira']} | URA +{grand['ura']} | SI +{grand['si']} | ACC +{grand['acc']} | Errors: {grand['errors']}")
    else:
        if batch_num <= len(batches):
            process_batch(batches[batch_num-1], batch_num)
        else:
            print(f"Batch {batch_num} not found (max {len(batches)})")
