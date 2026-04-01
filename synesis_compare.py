#!/usr/bin/env python
"""
synesis_compare.py — Synesis (fiksni) vs LIMIT Connect (baza)
Konjik d.o.o. | OIB: 37590751921
Datum: 01.04.2026

POKRETANJE:
  venv/bin/python synesis_compare.py [--csv] [--summary] [--only-ira] [--only-ura]
"""
import os, sys, csv, io, subprocess, argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
import django
django.setup()

from companies.models import Company
from invoicing.models import Invoice
from konto.models import JournalEntry
from django.db.models import Sum

# ─── CONFIG ───────────────────────────────────────────
KONJIK_OIB  = '37590751921'
JOURNAL_MDB = '/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/Journal.mdb'
TOLERANCE   = Decimal('0.02')

DOC_MAP = {
    'XINVOICESB': {'prefix': 'SYN-IRA', 'label': 'IRA (izlazni)'},
    'URAEU':      {'prefix': 'SYN-URA', 'label': 'URA (ulazni EU)'},
    'NPRIMITAK':  {'prefix': 'SYN-URA', 'label': 'URA (domaći)'},
    'PRIMITAK':   {'prefix': 'SYN-PRI', 'label': 'Primitak'},
}

# ─── BOJE ─────────────────────────────────────────────
def G(t): return f"\033[32m{t}\033[0m"
def Y(t): return f"\033[33m{t}\033[0m"
def R(t): return f"\033[31m{t}\033[0m"
def B(t): return f"\033[1m{t}\033[0m"

# ─── UTILS ────────────────────────────────────────────
def clean(v):
    return (v or '').strip().strip('"').strip()

def parse_date(s):
    s = clean(s)
    if not s: return ''
    for fmt in ('%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S'):
        try: return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except: pass
    return s[:10]

def parse_amt(s):
    s = clean(s).replace(',', '.')
    try: return Decimal(s)
    except: return Decimal('0')

def read_mdb(path, table):
    r = subprocess.run(['mdb-export', path, table],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(Y("  mdb-export error: " + r.stderr[:80]))
        return []
    return list(csv.DictReader(io.StringIO(r.stdout)))

# ─── UČITAVANJE ───────────────────────────────────────
def load_synesis(only_types=None):
    rows = read_mdb(JOURNAL_MDB, 'Journal')
    docs = {}
    for r in rows:
        dt = clean(r.get('DOCUMENT', ''))
        if only_types and dt not in only_types: continue
        if dt not in DOC_MAP: continue
        if clean(r.get('DOCUMENT_INVALID', '0')) == '1': continue
        key = clean(r.get('DOCUMENT_KEY', ''))
        docs[key] = r
    return docs

def load_lc(company):
    return {
        inv.number: inv
        for inv in Invoice.objects.filter(
            company=company, synesis_id__isnull=False
        )
    }

def expected_num(doc_type, doc_id):
    return doc_id  # LC fakture koriste originalni Synesis broj

# ─── USPOREDBA ────────────────────────────────────────
def compare(syn_docs, lc_invs):
    ok, warn, err, missing, extra = [], [], [], [], []

    expected_nums = set()
    for key, row in syn_docs.items():
        dt  = clean(row.get('DOCUMENT', ''))
        did = clean(row.get('DOCUMENT_ID', ''))
        exp = expected_num(dt, did)
        expected_nums.add(exp)
        base = {
            'syn_key':  key,
            'expected': exp,
            'partner':  clean(row.get('DOCUMENT_PARTNER', '')),
            'date':     parse_date(row.get('DOCUMENT_DATE', '')),
            'syn_amt':  parse_amt(row.get('DOCUMENT_AMMOUNT', '')),
            'doc_type': dt,
        }
        prefixed = DOC_MAP[dt]['prefix'] + '-' + did
        lc = lc_invs.get(exp) or lc_invs.get(prefixed)
        # Fallback: fuzzy match by partner name + approximate amount
        if not lc:
            syn_partner = clean(row.get('DOCUMENT_PARTNER', '')).lower()[:20]
            syn_amt_val = base['syn_amt']
            if syn_partner and syn_amt_val:
                for num, candidate in lc_invs.items():
                    if syn_partner in (candidate.client_name or '').lower()[:20]:
                        c_total = Decimal(str(candidate.total))
                        c_bruto = c_total + Decimal(str(candidate.tax_amount or 0))
                        if (abs(syn_amt_val - c_total) <= Decimal('0.02')
                            or abs(syn_amt_val - c_bruto) <= Decimal('0.02')
                            or abs(syn_amt_val - c_total * Decimal('1.25')) <= Decimal('0.50')):
                            lc = candidate
                            break
        if not lc:
            missing.append(base)
            continue
        amt = Decimal(str(lc.total))
        tax = Decimal(str(lc.tax_amount or 0))
        lc_bruto = amt + tax
        # Synesis DOCUMENT_AMMOUNT = bruto (s PDV)
        # LC total = neto ili bruto ovisno o importu
        # Pokušaj match: direktno, bruto, ili neto×PDV stope
        candidates = [
            abs(base['syn_amt'] - amt),          # direktan match
            abs(base['syn_amt'] - lc_bruto),     # LC total+tax
            abs(base['syn_amt'] - amt * Decimal('1.25')),   # 25% PDV
            abs(base['syn_amt'] - amt * Decimal('1.13')),   # 13% PDV
            abs(base['syn_amt'] - amt * Decimal('1.05')),   # 5% PDV
        ]
        d = min(candidates)
        rec = dict(base, lc_total=amt, diff=d)
        if d <= TOLERANCE:      ok.append(rec)
        elif d <= Decimal('1'): warn.append(rec)
        else:                   err.append(rec)

    syn_pfxs = set(v['prefix'] for v in DOC_MAP.values())
    for num, inv in lc_invs.items():
        if any(num.startswith(p + '-') for p in syn_pfxs) and num not in expected_nums:
            extra.append({
                'lc_num':  num,
                'partner': inv.client_name,
                'date':    inv.date_issued.strftime('%Y-%m-%d') if inv.date_issued else '',
                'lc_total': Decimal(str(inv.total)),
            })
    return ok, warn, err, missing, extra

def check_journal(company):
    paid = Invoice.objects.filter(
        company=company, status='PAID', synesis_id__isnull=False
    )
    ok_n, missing = 0, []
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

# ─── TOTALI ───────────────────────────────────────────
def print_totals(company, syn_docs):
    print(B("\n  TOTALI — cross-check:"))
    hdr = "  {:<25} {:>14} {:>14} {:>10}"
    print(hdr.format('Kategorija', 'Synesis EUR', 'LC EUR', 'Diff'))
    print("  " + "-" * 65)
    all_inv = Invoice.objects.filter(company=company, synesis_id__isnull=False)
    for dt, m in DOC_MAP.items():
        syn_rows = [r for r in syn_docs.values() if clean(r.get('DOCUMENT','')) == dt]
        syn_t = sum(parse_amt(r.get('DOCUMENT_AMMOUNT','')) for r in syn_rows)
        lc_t  = all_inv.filter(number__startswith=m['prefix']+'-').aggregate(t=Sum('total'))['t'] or Decimal('0')
        diff  = syn_t - Decimal(str(lc_t))
        ds    = f"{float(diff):>+10.2f}"
        ds    = G(ds) if abs(diff) < 1 else (Y(ds) if abs(diff) < 100 else R(ds))
        print(f"  {m['label']:<25} {float(syn_t):>14.2f} {float(lc_t):>14.2f} {ds}")
    print()

# ─── ISPIS ────────────────────────────────────────────
def print_summary(ok, warn, err, missing, extra, je_ok, je_miss):
    total = len(ok) + len(warn) + len(err)
    print()
    print(B("═" * 60))
    print(B("  SYNESIS ↔ LIMIT CONNECT — USKLAĐENJE KONJIK d.o.o."))
    print(B(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}"))
    print(B("═" * 60))
    print(f"\n  Uspoređeno faktura:        {total:>6}")
    print(f"  {G('✓ OK (≤0.02€):')}              {len(ok):>6}")
    print(f"  {Y('⚠ Upozorenje (>0.02€):')}     {len(warn):>6}")
    print(f"  {R('✗ Razlika (>1€):')}            {len(err):>6}")
    print(f"  {R('✗ Nema u LC:')}                {len(missing):>6}")
    print(f"  {Y('? Extra u LC:')}               {len(extra):>6}")
    print(f"\n  Temeljnice — ima:          {je_ok:>6}")
    print(f"  {R('Temeljnice — nema:')}           {len(je_miss):>6}")

    if total > 0:
        pct = len(ok) / total * 100
        n_ok = int(pct / 2)
        n_w  = int(len(warn) / total * 50)
        n_e  = 50 - n_ok - n_w
        bar  = G('█' * n_ok) + Y('█' * n_w) + R('█' * n_e)
        print(f"\n  [{bar}] {pct:.1f}% OK\n")

    if err or missing:
        print(R("  ✗ NIJE SPREMNO — razlike postoje"))
    elif warn:
        print(Y("  ⚠ GOTOVO — samo zaokruživanje, može na Mariju"))
    else:
        print(G("  ✓ USKLAĐENO — može na Mariju za blagoslov"))
    print()

def print_details(err, missing, je_miss):
    if err:
        print(B(R(f"\n  RAZLIKE >1€ ({len(err)}):")))
        print("  {:<22} {:<30} {:>10} {:>10} {:>8}".format(
            'LC Broj','Partner','Synesis','LC','Diff'))
        print("  " + "-" * 82)
        for r in err[:25]:
            prt = r['partner'][:28]
            syn = float(r['syn_amt'])
            lct = float(r['lc_total'])
            dif = R(f"{float(r['diff']):>8.2f}")
            print(f"  {r['expected']:<22} {prt:<30} {syn:>10.2f} {lct:>10.2f} {dif}")
        if len(err) > 25:
            print(f"  ... još {len(err)-25} razlika (vidi --csv)")

    if missing:
        print(B(R(f"\n  NEMA U LC ({len(missing)}):")))
        for r in missing[:15]:
            amt = float(r['syn_amt'])
            print(f"  {r['expected']:<22} {r['partner'][:30]:<32} {amt:>10.2f} EUR")
        if len(missing) > 15:
            print(f"  ... još {len(missing)-15}")

    if je_miss:
        print(B(Y(f"\n  FAKTURE BEZ TEMELJNICE ({len(je_miss)}):")))
        for r in je_miss[:15]:
            print(f"  {r['inv']:<22} {r['partner'][:30]:<32} {float(r['total']):>10.2f} EUR")
        if len(je_miss) > 15:
            print(f"  ... još {len(je_miss)-15}")

def export_csv(ok, warn, err, missing, extra, je_miss):
    ts    = datetime.now().strftime('%Y%m%d_%H%M')
    fname = f"/var/www/fina-connect/synesis_razlike_{ts}.csv"
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Kategorija','LC Broj','Partner','Datum',
                    'Synesis EUR','LC EUR','Razlika EUR','Napomena'])
        for r in ok:
            w.writerow(['OK', r['expected'], r['partner'], r['date'],
                        float(r['syn_amt']), float(r['lc_total']), float(r['diff']), ''])
        for r in warn:
            w.writerow(['UPOZORENJE', r['expected'], r['partner'], r['date'],
                        float(r['syn_amt']), float(r['lc_total']), float(r['diff']),
                        'Zaokruživanje'])
        for r in err:
            w.writerow(['RAZLIKA', r['expected'], r['partner'], r['date'],
                        float(r['syn_amt']), float(r['lc_total']), float(r['diff']),
                        f"Diff {float(r['diff']):.2f} EUR"])
        for r in missing:
            w.writerow(['NEMA_U_LC', r['expected'], r['partner'], r['date'],
                        float(r['syn_amt']), 0, float(r['syn_amt']), 'Nije uvezeno'])
        for r in extra:
            w.writerow(['EXTRA_U_LC', r['lc_num'], r['partner'], r['date'],
                        0, float(r['lc_total']), 0, 'U LC, nema u Synesis'])
        for r in je_miss:
            w.writerow(['NEMA_TEMELJNICE', r['inv'], r['partner'], r['date'],
                        0, float(r['total']), 0, 'PAID bez JournalEntry'])
    print(f"  CSV: {fname}")
    return fname

# ─── MAIN ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv',      action='store_true')
    ap.add_argument('--summary',  action='store_true')
    ap.add_argument('--only-ira', action='store_true')
    ap.add_argument('--only-ura', action='store_true')
    args = ap.parse_args()

    print(B("\n  Učitavam Konjik d.o.o..."))
    try:
        company = Company.objects.get(oib=KONJIK_OIB)
    except Company.DoesNotExist:
        print(R(f"  ✗ Company OIB {KONJIK_OIB} nije u bazi!")); sys.exit(1)
    print(f"  ✓ {company.name}")

    only = None
    if args.only_ira: only = {'XINVOICESB'}
    if args.only_ura: only = {'URAEU', 'NPRIMITAK'}

    print("  Učitavam Synesis Journal.mdb...")
    syn_docs = load_synesis(only)
    print(f"  ✓ {len(syn_docs)} dokumenata")

    print("  Učitavam LC fakture...")
    lc_invs = load_lc(company)
    print(f"  ✓ {len(lc_invs)} faktura\n")

    ok, warn, err, missing, extra = compare(syn_docs, lc_invs)
    je_ok, je_miss = check_journal(company)

    print_summary(ok, warn, err, missing, extra, je_ok, je_miss)
    print_totals(company, syn_docs)

    if not args.summary:
        print_details(err, missing, je_miss)

    if args.csv:
        export_csv(ok, warn, err, missing, extra, je_miss)

    sys.exit(1 if (err or missing) else 0)

if __name__ == '__main__':
    main()
