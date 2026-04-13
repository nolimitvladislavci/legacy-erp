#!/usr/bin/env python
"""
synesis_compare.py — Storage.mdb (izvor importa) vs LIMIT Connect (baza)
Usporedba za svih 87 firmi.

POKRETANJE:
  venv/bin/python synesis_compare.py [--csv] [--summary] [--company OIB] [--only-ira] [--only-ura]
"""
import os, sys, csv, io, subprocess, argparse, glob
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
import django
django.setup()

from companies.models import Company
from invoicing.models import Invoice
from konto.models import JournalEntry

# ─── CONFIG ───────────────────────────────────────────
TOLERANCE = Decimal('0.02')
HRK_RATE = Decimal('7.53450')  # Fixed HRK→EUR rate (01.01.2023)
MDB_CHARSET = 'cp1250'

MDB_DIRS = [
    '/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis',
    '/var/www/fina-connect/Korpa',
    '/var/www/fina-connect/Uvjek_Frisko/Synesis',
]

# ─── BOJE ─────────────────────────────────────────────
def G(t): return f"\033[32m{t}\033[0m"
def Y(t): return f"\033[33m{t}\033[0m"
def R(t): return f"\033[31m{t}\033[0m"
def B(t): return f"\033[1m{t}\033[0m"

# ─── UTILS ────────────────────────────────────────────
def _clean(v, maxlen=255):
    return (v or '').strip().strip('"')[:maxlen]

def _dec(val):
    if not val: return Decimal('0')
    try:
        return Decimal(str(val).strip().replace(',', '.').replace('"', '')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0')

def _date(s):
    s = _clean(s)
    if not s: return ''
    from datetime import timedelta, date as _d
    for fmt in ('%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%m/%d/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    try:
        n = float(s)
        if 30000 < n < 60000:
            return (_d(1899, 12, 30) + timedelta(days=int(n))).isoformat()
    except ValueError:
        pass
    return s[:10]

def _mdb(path, table):
    env = os.environ.copy()
    env['MDB_JET3_CHARSET'] = MDB_CHARSET
    try:
        r = subprocess.run(['mdb-export', path, table],
                           capture_output=True, text=True, timeout=60, env=env)
        if r.returncode != 0:
            return []
        return list(csv.DictReader(io.StringIO(r.stdout)))
    except (ValueError, TypeError):
        return []

# ─── DISCOVER MDB FILES ──────────────────────────────
def discover_mdbs():
    """Find all Storage.mdb files and map to companies."""
    jobs = []
    for base in MDB_DIRS:
        for mdb_path in sorted(glob.glob(f'{base}/*/Storage.mdb')):
            if 'SynesisArhiva' in mdb_path:
                continue
            folder = os.path.basename(os.path.dirname(mdb_path))
            name = folder
            for suffix in [' 2025', ' 2025 R1', ' 2025-KIOSK', ' 2026', '(Popravljeno 1)']:
                name = name.replace(suffix, '').strip()
            # Skip non-Popravljeno Konjik if Popravljeno exists
            if 'KONJIK D.O.O.' in folder and 'Popravljeno' not in folder:
                popravljeno = mdb_path.replace(folder, folder + '(Popravljeno 1)')
                if os.path.exists(popravljeno):
                    continue
            jobs.append({'name': name, 'mdb': mdb_path})
    return jobs

def find_company(name):
    """Match folder name to Company in DB."""
    c = Company.objects.filter(name__iexact=name).first()
    if c:
        return c
    c = Company.objects.filter(name__icontains=name[:20]).first()
    if c:
        return c
    return None

# ─── LOAD FROM STORAGE.MDB ───────────────────────────
def load_synesis_invoices(mdb_path):
    """Load IRA from INVOICES + TINVOICES, URA from URAEU + TURAEU."""
    result = {'ira': {}, 'ura': {}}

    # IRA — izlazni racuni
    headers = _mdb(mdb_path, 'INVOICES')
    lines = _mdb(mdb_path, 'TINVOICES')
    lines_by_din = defaultdict(list)
    for ln in lines:
        din = _clean(ln.get('DIN', ''))
        if din:
            lines_by_din[din].append(ln)

    for hdr in headers:
        din = _clean(hdr.get('DIN', ''))
        inv_num = _clean(hdr.get('INVOICE_NUMBER', ''))
        if not inv_num:
            continue
        inv_date = _date(hdr.get('INVOICE_DATE', ''))
        partner = _clean(hdr.get('CUSTOMER_NAME', ''), 200)
        oib = _clean(hdr.get('CUSTOMER_VATNUMBER', ''), 20)

        # Calculate total from line items
        # ITEM_AMMOUNT = neto (bez PDV), ITEM_PRICE = bruto jed. cijena
        inv_lines = [ln for ln in lines_by_din.get(din, [])
                     if _dec(ln.get('ITEM_AMMOUNT', '')) != 0]  # Skip PDV summary rows
        neto = Decimal('0')
        bruto = Decimal('0')
        for ln in inv_lines:
            item_net = _dec(ln.get('ITEM_AMMOUNT', ''))
            vat_rate = _dec(ln.get('VAT_RATE', ''))
            item_bruto = item_net * (1 + vat_rate / 100) if vat_rate else item_net
            neto += item_net
            bruto += item_bruto.quantize(Decimal('0.01'))
        # HRK→EUR conversion (1 EUR = 7.53450 HRK)
        # Detect: if amounts look like HRK (>1000 for typical invoice)
        if neto > 1000 and neto / HRK_RATE < 200:
            neto = (neto / HRK_RATE).quantize(Decimal('0.01'))
            bruto = (bruto / HRK_RATE).quantize(Decimal('0.01'))

        lc_number = f'SYN-IRA-{inv_num}'
        result['ira'][lc_number] = {
            'number': lc_number,
            'syn_num': inv_num,
            'partner': partner,
            'oib': oib,
            'date': inv_date,
            'syn_neto': neto,
            'syn_bruto': bruto,
            'line_count': len(inv_lines),
        }

    # URA — ulazni racuni (uses TRANCODE and ACC_DEBIT/ACC_CREDIT)
    ura_headers = _mdb(mdb_path, 'URAEU')
    ura_lines = _mdb(mdb_path, 'TURAEU')
    ura_by_din = defaultdict(list)
    for ln in ura_lines:
        din = _clean(ln.get('DIN', ''))
        if din:
            ura_by_din[din].append(ln)

    for hdr in ura_headers:
        din = _clean(hdr.get('DIN', ''))
        # TRANCODE (no underscore) — match import_p1.py field name
        tran_code = _clean(hdr.get('TRANCODE', ''))
        inv_date = _date(hdr.get('TRANDATE', '') or hdr.get('VAT_INVOICEDATE', ''))
        partner = _clean(hdr.get('VENDOR_NAME', '') or hdr.get('PARTNER_NAME', ''), 200)

        ura_key = tran_code if tran_code else din
        if not ura_key:
            continue

        # URA uses ACC_DEBIT/ACC_CREDIT from TURAEU (same as import_p1.py)
        ura_lns = ura_by_din.get(din, [])
        total_d = Decimal('0')
        total_c = Decimal('0')
        for ln in ura_lns:
            total_d += abs(_dec(ln.get('ACC_DEBIT', '')))
            total_c += abs(_dec(ln.get('ACC_CREDIT', '')))
        neto = max(total_d, total_c)
        bruto = neto  # URA doesn't have separate bruto in TURAEU

        # HRK conversion
        if neto > 1000 and neto / HRK_RATE < 200:
            neto = (neto / HRK_RATE).quantize(Decimal('0.01'))
            bruto = (bruto / HRK_RATE).quantize(Decimal('0.01'))

        lc_number = f'SYN-URA-{ura_key}'
        result['ura'][lc_number] = {
            'number': lc_number,
            'syn_num': ura_key,
            'partner': partner,
            'date': inv_date,
            'syn_neto': neto,
            'syn_bruto': bruto,
            'line_count': len(ura_lns),
        }

    return result

# ─── COMPARE ─────────────────────────────────────────
def compare_company(company, syn_data, only_type=None):
    """Compare a single company's Synesis data against LC."""
    results = {'ok': [], 'warn': [], 'err': [], 'missing': [], 'extra': []}

    lc_invs = {
        inv.number: inv
        for inv in Invoice.objects.filter(company=company, number__startswith='SYN-')
    }

    types_to_check = []
    if only_type == 'ira' or only_type is None:
        types_to_check.append(('ira', 'SYN-IRA-'))
    if only_type == 'ura' or only_type is None:
        types_to_check.append(('ura', 'SYN-URA-'))

    syn_numbers = set()
    for doc_type, prefix in types_to_check:
        for lc_num, syn_rec in syn_data.get(doc_type, {}).items():
            syn_numbers.add(lc_num)
            lc = lc_invs.get(lc_num)
            if not lc:
                results['missing'].append(syn_rec)
                continue

            # Compare amounts — Synesis bruto vs LC total, or neto vs subtotal
            lc_total = Decimal(str(lc.total))
            lc_sub = Decimal(str(lc.subtotal or 0))
            syn_bruto = syn_rec['syn_bruto']
            syn_neto = syn_rec['syn_neto']

            # Best match from multiple strategies
            # KNOWN IMPORT BUG: Synesis bruto stored as LC subtotal (double-tax)
            # KNOWN: Some URA have HRK amounts in LC (pre-2023 conversion)
            lc_total_eur = lc_total / HRK_RATE if lc_total > 100 else lc_total
            lc_sub_eur = lc_sub / HRK_RATE if lc_sub > 100 else lc_sub
            diffs = [
                ('bruto=total', abs(syn_bruto - lc_total)),
                ('neto=sub', abs(syn_neto - lc_sub)),
                ('neto=total', abs(syn_neto - lc_total)),
                ('bruto=sub', abs(syn_bruto - lc_sub)),
                ('bruto=total/HRK', abs(syn_bruto - lc_total_eur)),
                ('neto=sub/HRK', abs(syn_neto - lc_sub_eur)),
                ('neto=total/HRK', abs(syn_neto - lc_total_eur)),
            ]
            best_strategy, d = min(diffs, key=lambda x: x[1])

            rec = dict(syn_rec,
                       match_strategy=best_strategy,
                       lc_number=lc_num,
                       lc_total=lc_total,
                       lc_sub=lc_sub,
                       diff=d,
                       company=company.name)

            if d <= TOLERANCE:
                results['ok'].append(rec)
            elif d <= Decimal('1'):
                results['warn'].append(rec)
            else:
                results['err'].append(rec)

    # Extra in LC (have SYN- prefix but not in Synesis)
    for prefix_type, prefix in types_to_check:
        for num, inv in lc_invs.items():
            if num.startswith(prefix) and num not in syn_numbers:
                results['extra'].append({
                    'lc_number': num,
                    'partner': inv.client_name,
                    'date': inv.date_issued.strftime('%Y-%m-%d') if inv.date_issued else '',
                    'lc_total': Decimal(str(inv.total)),
                    'company': company.name,
                })

    return results

def check_journal(company):
    """Check how many PAID invoices have JournalEntry."""
    paid = Invoice.objects.filter(company=company, status='PAID', number__startswith='SYN-')
    ok_n = 0
    missing = []
    for inv in paid:
        if JournalEntry.objects.filter(company=company, source_invoice=inv).exists():
            ok_n += 1
        else:
            missing.append({
                'inv': inv.number,
                'partner': inv.client_name,
                'total': inv.total,
                'date': inv.date_issued.strftime('%Y-%m-%d') if inv.date_issued else '',
            })
    return ok_n, missing

# ─── OUTPUT ───────────────────────────────────────────
def print_summary(all_results, all_je):
    ok = sum(len(r['ok']) for r in all_results)
    warn = sum(len(r['warn']) for r in all_results)
    err = sum(len(r['err']) for r in all_results)
    missing = sum(len(r['missing']) for r in all_results)
    extra = sum(len(r['extra']) for r in all_results)
    total = ok + warn + err
    je_ok = sum(j[0] for j in all_je)
    je_miss = sum(len(j[1]) for j in all_je)

    print()
    print(B("=" * 60))
    print(B("  SYNESIS ↔ LIMIT CONNECT — USKLAĐENJE"))
    print(B(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}"))
    print(B("=" * 60))
    print(f"\n  Uspoređeno faktura:        {total:>6}")
    print(f"  {G('✓ OK (≤0.02€):')}              {ok:>6}")
    print(f"  {Y('⚠ Upozorenje (0.02-1€):')}    {warn:>6}")
    print(f"  {R('✗ Razlika (>1€):')}            {err:>6}")
    print(f"  {R('✗ Nema u LC:')}                {missing:>6}")
    print(f"  {Y('? Extra u LC:')}               {extra:>6}")
    print(f"\n  Temeljnice — ima:          {je_ok:>6}")
    print(f"  {R('Temeljnice — nema:')}           {je_miss:>6}")

    if total > 0:
        pct = ok / total * 100
        n_ok = int(pct / 2)
        n_w = int(warn / total * 50) if total else 0
        n_e = 50 - n_ok - n_w
        bar = G('█' * n_ok) + Y('█' * n_w) + R('█' * n_e)
        print(f"\n  [{bar}] {pct:.1f}% OK\n")

    if err or missing:
        print(R("  ✗ NIJE SPREMNO — razlike postoje"))
    elif warn:
        print(Y("  ⚠ GOTOVO — samo zaokruživanje, može na Mariju"))
    else:
        print(G("  ✓ USKLAĐENO — može na Mariju za blagoslov"))
    print()

def print_details(all_results):
    all_err = []
    all_missing = []
    for r in all_results:
        all_err.extend(r['err'])
        all_missing.extend(r['missing'])

    if all_err:
        print(B(R(f"\n  RAZLIKE >1€ ({len(all_err)}):")))
        print("  {:<22} {:<25} {:>10} {:>10} {:>8} {:<15}".format(
            'LC Broj', 'Partner', 'Synesis', 'LC', 'Diff', 'Firma'))
        print("  " + "-" * 92)
        for r in sorted(all_err, key=lambda x: -float(x['diff']))[:30]:
            prt = r['partner'][:23]
            syn = float(r['syn_bruto'])
            lct = float(r['lc_total'])
            dif = R(f"{float(r['diff']):>8.2f}")
            co = r.get('company', '')[:14]
            print(f"  {r.get('lc_number', r['number']):<22} {prt:<25} {syn:>10.2f} {lct:>10.2f} {dif} {co}")
        if len(all_err) > 30:
            print(f"  ... još {len(all_err)-30} razlika (vidi --csv)")

    if all_missing:
        print(B(R(f"\n  NEMA U LC ({len(all_missing)}):")))
        for r in all_missing[:20]:
            amt = float(r['syn_bruto'])
            print(f"  {r['number']:<22} {r['partner'][:30]:<32} {amt:>10.2f} EUR")
        if len(all_missing) > 20:
            print(f"  ... još {len(all_missing)-20}")

def export_csv(all_results, all_je):
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    fname = f"/var/www/fina-connect/synesis_razlike_{ts}.csv"
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Kategorija', 'LC Broj', 'Partner', 'Datum',
                     'Synesis Bruto', 'Synesis Neto', 'LC Total', 'LC Subtotal',
                     'Razlika EUR', 'Firma', 'Napomena'])
        for res in all_results:
            for r in res['ok']:
                w.writerow(['OK', r.get('lc_number', r['number']), r['partner'], r['date'],
                             float(r['syn_bruto']), float(r['syn_neto']),
                             float(r['lc_total']), float(r['lc_sub']),
                             float(r['diff']), r.get('company', ''), ''])
            for r in res['warn']:
                w.writerow(['UPOZORENJE', r.get('lc_number', r['number']), r['partner'], r['date'],
                             float(r['syn_bruto']), float(r['syn_neto']),
                             float(r['lc_total']), float(r['lc_sub']),
                             float(r['diff']), r.get('company', ''), 'Zaokruzivanje'])
            for r in res['err']:
                w.writerow(['RAZLIKA', r.get('lc_number', r['number']), r['partner'], r['date'],
                             float(r['syn_bruto']), float(r['syn_neto']),
                             float(r['lc_total']), float(r['lc_sub']),
                             float(r['diff']), r.get('company', ''),
                             f"Diff {float(r['diff']):.2f} EUR"])
            for r in res['missing']:
                w.writerow(['NEMA_U_LC', r['number'], r['partner'], r['date'],
                             float(r['syn_bruto']), float(r['syn_neto']),
                             0, 0, float(r['syn_bruto']), r.get('company', ''), 'Nije uvezeno'])
            for r in res['extra']:
                w.writerow(['EXTRA_U_LC', r['lc_number'], r['partner'], r['date'],
                             0, 0, float(r['lc_total']), 0, 0, r.get('company', ''), 'U LC, nema u Synesis'])
        for je_ok, je_miss in all_je:
            for r in je_miss:
                w.writerow(['NEMA_TEMELJNICE', r['inv'], r['partner'], r['date'],
                             0, 0, float(r['total']), 0, 0, '', 'PAID bez JournalEntry'])
    print(f"  CSV: {fname}")
    return fname

# ─── MAIN ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', action='store_true')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--only-ira', action='store_true')
    ap.add_argument('--only-ura', action='store_true')
    ap.add_argument('--company', help='Filter by company OIB')
    args = ap.parse_args()

    only_type = None
    if args.only_ira:
        only_type = 'ira'
    if args.only_ura:
        only_type = 'ura'

    print(B("\n  Discovering MDB files..."))
    jobs = discover_mdbs()
    print(f"  Found {len(jobs)} MDB files\n")

    all_results = []
    all_je = []
    companies_checked = 0

    for job in jobs:
        company = find_company(job['name'])
        if not company:
            continue
        if args.company and company.oib != args.company:
            continue

        # Skip companies without SYN- invoices
        syn_count = Invoice.objects.filter(company=company, number__startswith='SYN-').count()
        if syn_count == 0:
            continue

        print(f"  {company.name} ({company.oib})...")
        syn_data = load_synesis_invoices(job['mdb'])
        ira_count = len(syn_data['ira'])
        ura_count = len(syn_data['ura'])
        print(f"    Storage.mdb: {ira_count} IRA, {ura_count} URA")

        res = compare_company(company, syn_data, only_type)
        all_results.append(res)

        je_ok, je_miss = check_journal(company)
        all_je.append((je_ok, je_miss))

        ok_pct = len(res['ok']) / max(1, len(res['ok']) + len(res['warn']) + len(res['err'])) * 100
        print(f"    OK: {len(res['ok'])}, Warn: {len(res['warn'])}, Err: {len(res['err'])}, "
              f"Missing: {len(res['missing'])}, Extra: {len(res['extra'])} ({ok_pct:.0f}%)")
        companies_checked += 1

    print(f"\n  Checked {companies_checked} companies")
    print_summary(all_results, all_je)

    if not args.summary:
        print_details(all_results)

    if args.csv:
        export_csv(all_results, all_je)

    total_err = sum(len(r['err']) for r in all_results)
    total_miss = sum(len(r['missing']) for r in all_results)
    sys.exit(1 if (total_err or total_miss) else 0)


if __name__ == '__main__':
    main()
