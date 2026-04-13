"""
synesis/import_p1.py — P1 Import: Fakture (IRA+URA) + Artikli
Za svih 87 firmi iz Synesis MDB baza.

Pokreni: venv/bin/python synesis/import_p1.py
"""
import os, sys, glob, csv, io, subprocess, time, django
from decimal import Decimal
from collections import defaultdict
import logging
logger = logging.getLogger("synesis.import_p1")

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from companies.models import Company

MDB_CHARSET = 'cp1250'

def _mdb(mdb_path, table):
    env = os.environ.copy(); env['MDB_JET3_CHARSET'] = MDB_CHARSET
    try:
        r = subprocess.run(['mdb-export', mdb_path, table], capture_output=True, text=True, timeout=60, env=env)
        if r.returncode != 0: return []
        return list(csv.DictReader(io.StringIO(r.stdout)))
    except (ValueError, TypeError) as e:
        return []

def _dec(val):
    if not val: return Decimal('0')
    try: return Decimal(str(val).strip().replace(',','.').replace('"','')).quantize(Decimal('0.01'))
    except (ValueError, TypeError) as e:
        return Decimal('0')

def _date(val):
    if not val: return None
    val = val.strip().strip('"')
    from datetime import datetime, timedelta, date
    for fmt in ('%m/%d/%y %H:%M:%S','%m/%d/%Y %H:%M:%S','%m/%d/%y','%Y-%m-%d'):
        try: return datetime.strptime(val, fmt).date()
        except (ValueError, TypeError) as e:
            continue
    try:
        s = float(val)
        if 30000 < s < 60000: return date(1899,12,30) + timedelta(days=int(s))
    except (ValueError, TypeError) as e:
        pass
    return None

def _clean(val, maxlen=200):
    return (val or '').strip().strip('"').strip()[:maxlen]


def import_items(company, mdb_path):
    """Import ITEMS + ITEMGROUP → inventory.InventoryItem"""
    from inventory.models import InventoryItem

    groups = {}
    for g in _mdb(mdb_path, 'ITEMGROUP'):
        gid = _clean(g.get('ITEMGROUP_ID',''))
        gname = _clean(g.get('ITEMGROUP_NAME',''))
        if gid: groups[gid] = gname

    rows = _mdb(mdb_path, 'ITEMS')
    created = 0
    for row in rows:
        item_id = _clean(row.get('ITEM_ID',''))
        name = _clean(row.get('ITEM_NAME',''))
        barcode = _clean(row.get('ITEM_BARCODE',''), 100)
        measure = _clean(row.get('ITEM_MEASURE',''), 20)
        gid = _clean(row.get('ITEMGROUP_ID',''))

        if not name: continue

        sku = f'SYN-{item_id}' if item_id else ''

        if sku and InventoryItem.objects.filter(company=company, sku=sku).exists():
            continue
        if not sku and InventoryItem.objects.filter(company=company, name=name).exists():
            continue

        InventoryItem.objects.create(
            company=company,
            name=name[:200],
            sku=sku[:50],
            barcode=barcode[:100],
            unit=measure[:20] or 'kom',
            category=groups.get(gid, '')[:100],
        )
        created += 1
    return created


def import_invoices_ira(company, mdb_path):
    """Import INVOICES + TINVOICES → invoicing.Invoice (izdani računi)"""
    from invoicing.models import Invoice, InvoiceItem
    from django.utils import timezone

    headers = _mdb(mdb_path, 'INVOICES')
    lines = _mdb(mdb_path, 'TINVOICES')

    # Group lines by DIN
    by_din = defaultdict(list)
    for ln in lines:
        din = _clean(ln.get('DIN',''))
        if din: by_din[din].append(ln)

    created = 0
    for hdr in headers:
        din = _clean(hdr.get('DIN',''))
        inv_num = _clean(hdr.get('INVOICE_NUMBER',''))
        inv_date = _date(hdr.get('INVOICE_DATE',''))
        cust_oib = _clean(hdr.get('CUSTOMER_VATNUMBER',''), 20)
        cust_code = _clean(hdr.get('CUSTOMER_CODE',''))

        if not inv_num: continue

        number = f'SYN-IRA-{inv_num}'
        if Invoice.objects.filter(company=company, number=number).exists():
            continue

        if not inv_date:
            inv_date = timezone.now().date()

        # Calculate totals from lines
        inv_lines = by_din.get(din, [])
        subtotal = Decimal('0')
        tax_total = Decimal('0')

        inv = Invoice.objects.create(
            company=company,
            number=number,
            doctype='R',
            status='PAID',
            date_issued=timezone.make_aware(
                timezone.datetime.combine(inv_date, timezone.datetime.min.time())
            ),
            client_oib=cust_oib,
            client_name=_get_partner_name(company, cust_code, cust_oib),
        )

        for ln in inv_lines:
            item_name = _clean(ln.get('ITEM_NAME',''))
            qty = _dec(ln.get('ITEM_QTY','')) or Decimal('1')
            price = _dec(ln.get('ITEM_PRICE',''))
            vat_rate = _dec(ln.get('VAT_RATE',''))
            total = _dec(ln.get('ITEM_TOTAL',''))
            gross = _dec(ln.get('ITEM_GROSS',''))

            if not item_name and not total: continue

            if total == 0 and price > 0:
                total = (qty * price).quantize(Decimal('0.01'))
            if gross == 0 and total > 0:
                gross = (total * (1 + vat_rate/100)).quantize(Decimal('0.01'))

            tax_amt = gross - total if gross > total else Decimal('0')

            InvoiceItem.objects.create(
                invoice=inv,
                description=item_name[:200] or 'Stavka',
                quantity=qty,
                unit_price=price,
                tax_rate=vat_rate,
                total_price=total,
                gross_total=gross if gross > 0 else total,
            )
            subtotal += total
            tax_total += tax_amt

        inv.subtotal = subtotal
        inv.tax_amount = tax_total
        inv.total = subtotal + tax_total
        inv.save(update_fields=['subtotal', 'tax_amount', 'total'])
        created += 1

    return created


def import_invoices_ura(company, mdb_path):
    """Import URAEU + TURAEU → invoicing.Invoice (ulazni računi)"""
    from invoicing.models import Invoice
    from django.utils import timezone

    headers = _mdb(mdb_path, 'URAEU')
    lines = _mdb(mdb_path, 'TURAEU')

    by_din = defaultdict(list)
    for ln in lines:
        din = _clean(ln.get('DIN',''))
        if din: by_din[din].append(ln)

    created = 0
    for hdr in headers:
        din = _clean(hdr.get('DIN',''))
        tran_code = _clean(hdr.get('TRANCODE',''))
        tran_date = _date(hdr.get('TRANDATE',''))
        vendor_name = _clean(hdr.get('VENDOR_NAME',''))
        vendor_oib = _clean(hdr.get('PARTNER_VATNUMBER',''), 20)
        inv_number = _clean(hdr.get('INVOICENUMBER','') or hdr.get('VENDOR_INVOICENUMBER',''))

        number = f'SYN-URA-{tran_code}' if tran_code else f'SYN-URA-{din}'
        if Invoice.objects.filter(company=company, number=number).exists():
            continue

        if not tran_date:
            tran_date = timezone.now().date()

        ura_lines = by_din.get(din, [])

        # Aggregate amounts from lines
        total_d = Decimal('0')
        total_p = Decimal('0')
        for ln in ura_lines:
            total_d += abs(_dec(ln.get('ACC_DEBIT','')))
            total_p += abs(_dec(ln.get('ACC_CREDIT','')))

        total_amount = max(total_d, total_p)
        if total_amount == 0:
            # Try header fields
            total_amount = _dec(hdr.get('TOTAL','')) or _dec(hdr.get('TOTALAMMOUNT',''))

        inv = Invoice.objects.create(
            company=company,
            number=number,
            doctype='URA',
            status='PAID',
            date_issued=timezone.make_aware(
                timezone.datetime.combine(tran_date, timezone.datetime.min.time())
            ),
            client_name=vendor_name[:200] or 'Dobavljač',
            client_oib=vendor_oib,
            total=total_amount,
            subtotal=total_amount,
        )
        created += 1

    return created


def _get_partner_name(company, code, oib):
    """Lookup partner name by code or OIB."""
    from partners.models import Partner
    if oib:
        p = Partner.objects.filter(company=company, oib__icontains=oib.strip()[:11]).first()
        if p: return p.name
    return f'Kupac {code}'


# ═══════════════════════════════════════════════════
#  BULK P1 IMPORT
# ═══════════════════════════════════════════════════

def find_company(name):
    clean = name.strip()
    c = Company.objects.filter(name__iexact=clean).first()
    if c: return c
    c = Company.objects.filter(name__icontains=clean[:20]).first()
    if c: return c
    special = {
        'FAST': 'Fast d.o.o.', 'ŠARKEZI TIHOMIR R1': 'Šarkezi Tihomir',
        'ĐURĐEVIĆ SLOBODAN': 'Đurđević Slobodan', 'ĐURĐEVIĆ SRĐAN': 'Đurđević Srđan',
        'SREĆKO PO': 'Srećko Po', 'UVIJEK FRIŠKO': 'UVIJEK FRIŠKO',
    }
    if special.get(clean):
        return Company.objects.filter(name__icontains=special[clean][:20]).first()
    return None


if __name__ == '__main__':
    base = '/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis'
    korpa = '/var/www/fina-connect/Korpa'
    frisko = '/var/www/fina-connect/Uvjek_Frisko/Synesis'

    jobs = []
    for d in sorted(glob.glob(f'{base}/*/Storage.mdb')):
        name = os.path.basename(os.path.dirname(d))
        for s in [' 2025',' 2025 R1',' 2025-KIOSK',' 2026','(Popravljeno 1)']:
            name = name.replace(s,'').strip()
        if 'KONJIK D.O.O. 2025/' in d and 'Popravljeno' not in d: continue
        jobs.append({'name': name, 'mdb': d})
    for d in sorted(glob.glob(f'{korpa}/*/Storage.mdb')):
        if 'SynesisArhiva' in d: continue
        name = os.path.basename(os.path.dirname(d)).replace(' 2025','').replace(' 2026','').strip()
        jobs.append({'name': name, 'mdb': d})
    for d in sorted(glob.glob(f'{frisko}/*/Storage.mdb')):
        name = os.path.basename(os.path.dirname(d)).replace('-KNJIGA','').replace(' 2026','').strip()
        jobs.append({'name': name, 'mdb': d})

    print(f"{'='*75}")
    print(f"P1 IMPORT — Fakture (IRA+URA) + Artikli — {len(jobs)} MDB files")
    print(f"{'='*75}\n")

    total_items = total_ira = total_ura = 0

    for i, job in enumerate(jobs):
        company = find_company(job['name'])
        if not company:
            print(f"[{i+1:2d}/{len(jobs)}] SKIP  {job['name']:40s}")
            continue

        t0 = time.time()
        try:
            items = import_items(company, job['mdb'])
            ira = import_invoices_ira(company, job['mdb'])
            ura = import_invoices_ura(company, job['mdb'])

            total_items += items
            total_ira += ira
            total_ura += ura

            elapsed = time.time() - t0
            print(f"[{i+1:2d}/{len(jobs)}] OK    {company.name:40s} Items={items:>5d} IRA={ira:>5d} URA={ura:>5d} ({elapsed:.1f}s)")
        except (ValueError, TypeError) as e:
            print(f"[{i+1:2d}/{len(jobs)}] ERROR {job['name']:40s} — {str(e)[:60]}")

    print(f"\n{'='*75}")
    print("P1 REZULTAT")
    print(f"{'='*75}")
    print(f"Artikli:  {total_items:>8,d}")
    print(f"IRA:      {total_ira:>8,d}")
    print(f"URA:      {total_ura:>8,d}")
    print(f"UKUPNO:   {total_items + total_ira + total_ura:>8,d} novih zapisa")
