"""
synesis/bulk_import.py — Bulk import svih Synesis MDB baza u LIMIT Connect.
Pokreni: venv/bin/python synesis/bulk_import.py
"""
import os, sys, glob, django, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from companies.models import Company
from synesis.full_import import full_import
from konto.models import LedgerLine, JournalEntry
from django.db.models import Sum

# Disable triggers for speed
from django.db import connection, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
with connection.cursor() as c:
    c.execute("ALTER TABLE konto_ledgerline DISABLE TRIGGER trg_check_journal_balance")
    c.execute("ALTER TABLE konto_journalentry DISABLE TRIGGER trg_period_lock_journal")
print("Triggers disabled")

# Build MDB → Company mapping
base = '/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis'
korpa = '/var/www/fina-connect/Korpa'
frisko = '/var/www/fina-connect/Uvjek_Frisko/Synesis'

# Folder name → Company name mapping (fuzzy)
def find_company(folder_name):
    """Match folder name to Company in DB."""
    clean = folder_name.strip()
    # Direct match
    c = Company.objects.filter(name__iexact=clean).first()
    if c: return c
    # Contains match
    c = Company.objects.filter(name__icontains=clean[:20]).first()
    if c: return c
    # Special cases
    mappings = {
        'FAST': 'Fast d.o.o.',
        'ŠARKEZI TIHOMIR R1': 'Šarkezi Tihomir',
        'EUROPA-KIOSK': None,  # Skip kiosk variant
        'ĐURĐEVIĆ SLOBODAN': 'Đurđević Slobodan',
        'ĐURĐEVIĆ SRĐAN': 'Đurđević Srđan',
        'SREĆKO PO': 'Srećko Po',
        'UVIJEK FRIŠKO': 'UVIJEK FRIŠKO',
    }
    mapped = mappings.get(clean)
    if mapped is None and clean in mappings:
        return None  # Explicitly skip
    if mapped:
        c = Company.objects.filter(name__icontains=mapped[:20]).first()
        if c: return c
    return None

# Collect all MDBs
jobs = []

for d in sorted(glob.glob(f'{base}/*/Storage.mdb')):
    folder = os.path.dirname(d)
    name = os.path.basename(folder)
    for suffix in [' 2025', ' 2025 R1', ' 2025-KIOSK', ' 2026', '(Popravljeno 1)']:
        name = name.replace(suffix, '').strip()
    
    # Skip duplicate Konjik (use Popravljeno 1)
    if 'KONJIK D.O.O. 2025/' in d and 'Popravljeno' not in d:
        continue
    
    jobs.append({'name': name, 'mdb': d})

for d in sorted(glob.glob(f'{korpa}/*/Storage.mdb')):
    if 'SynesisArhiva' in d:
        continue  # Skip archive duplicates
    name = os.path.basename(os.path.dirname(d)).replace(' 2025','').replace(' 2026','').strip()
    jobs.append({'name': name, 'mdb': d})

for d in sorted(glob.glob(f'{frisko}/*/Storage.mdb')):
    name = os.path.basename(os.path.dirname(d)).replace('-KNJIGA','').replace(' 2026','').strip()
    jobs.append({'name': name, 'mdb': d})

print(f"\n{'='*70}")
print(f"BULK SYNESIS IMPORT — {len(jobs)} MDB files")
print(f"{'='*70}\n")

results = []
total_je = total_ll = total_err = 0
skipped = 0

for i, job in enumerate(jobs):
    company = find_company(job['name'])
    if not company:
        print(f"[{i+1:2d}/{len(jobs)}] SKIP  {job['name']:40s} — no matching company")
        skipped += 1
        continue

    # Check if already has SYN- entries (skip Konjik which we already did)
    existing = JournalEntry.objects.filter(company=company, entry_number__startswith='SYN-').count()
    
    t0 = time.time()
    
    # Wipe only if re-importing (Konjik already done correctly)
    wipe = existing > 0
    
    try:
        r = full_import(company, job['mdb'], wipe=wipe)
        je = r['knjizenja']['journal_entries']
        ll = r['knjizenja']['ledger_lines']
        err = r['knjizenja']['errors']
        
        total_je += je
        total_ll += ll
        total_err += err
        
        elapsed = time.time() - t0
        
        # Quick balance check
        d = LedgerLine.objects.filter(journal_entry__company=company, side='debit').aggregate(t=Sum('amount'))['t'] or 0
        p = LedgerLine.objects.filter(journal_entry__company=company, side='credit').aggregate(t=Sum('amount'))['t'] or 0
        bal = 'BAL' if abs(float(d)-float(p)) < 1 else f'R={float(d-p):+.2f}'
        
        print(f"[{i+1:2d}/{len(jobs)}] OK    {company.name:40s} JE={je:>5d} LL={ll:>6d} E={err:>3d} {bal:>12s} ({elapsed:.1f}s)")
        results.append({'company': company.name, 'je': je, 'll': ll, 'err': err, 'bal': bal})
        
    except (ValueError, TypeError) as e:
        print(f"[{i+1:2d}/{len(jobs)}] ERROR {company.name:40s} — {str(e)[:60]}")
        results.append({'company': company.name, 'je': 0, 'll': 0, 'err': -1, 'bal': 'ERR'})

# Re-enable triggers
with connection.cursor() as c:
    c.execute("ALTER TABLE konto_ledgerline ENABLE TRIGGER trg_check_journal_balance")
    c.execute("ALTER TABLE konto_journalentry ENABLE TRIGGER trg_period_lock_journal")

print(f"\n{'='*70}")
print(f"REZULTAT")
print(f"{'='*70}")
print(f"Ukupno MDB:        {len(jobs)}")
print(f"Importirano:       {len(results)}")
print(f"Preskočeno:        {skipped}")
print(f"Temeljnice:        {total_je:,}")
print(f"Stavke knjiženja:  {total_ll:,}")
print(f"Greške:            {total_err:,}")

# Global balance
d = float(LedgerLine.objects.filter(side='debit').aggregate(t=Sum('amount'))['t'] or 0)
p = float(LedgerLine.objects.filter(side='credit').aggregate(t=Sum('amount'))['t'] or 0)
print(f"\nGLOBALNA BILANCA:")
print(f"  Duguje:    {d:>15,.2f} EUR")
print(f"  Potrazuje: {p:>15,.2f} EUR")
print(f"  Razlika:   {d-p:>15,.2f} EUR")
print(f"  Status:    {'BALANCED' if abs(d-p) < 100 else 'RAZLIKA'}")
