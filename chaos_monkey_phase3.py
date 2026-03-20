"""
FINA-CONNECT CHAOS MONKEY - FAZA 3
Autor: Claude (na temelju analize izvornog koda modela)
Pokretanje: cd /var/www/fina-connect && venv/bin/python /tmp/chaos_monkey_phase3.py

ŠTO OVAJ TEST ZAISTA TESTIRA (i zašto su prethodne faze davale lažne rezultate):

1. Točan side='debit'/'credit' (ne 'DEBIT'/'CREDIT' - ORM je case-sensitive na choices!)
2. Točan source_type='manual' (ne 'MANUAL' - isti problem)
3. unique_together postoji: (company, entry_number) - Faza 2 pokazala FAIL ali je
   zapravo bila na krivom source_type, ne na unique. Ovdje testiramo izolovanо.
4. balance check je u JournalEntry.clean() ali SAMO ako entry ima pk I ima linije.
   bulk_create zaobilazi clean() na LedgerLine ali ne na JournalEntry.save() koji
   se poziva naknadno - key insight za bulk_create bypass test.
5. amount nema MinValueValidator - samo DecimalValidator(14,2). Negativni iznosi
   su DOZVOLJENI na ORM razini. Ovo je pravi financijski rizik.
6. NUMERIC(14,2) u PG roundа 100.005 -> 100.01, 100.004 -> 100.00. Decimalni
   napad stvara razliku TIHO u bazi bez Pythonove greške.
"""

import os
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.apps import apps
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, connection
from konto.models import JournalEntry, LedgerLine, KontoAccount

SEPARATOR = "=" * 70
results = {}


def log(status, msg):
    icons = {'OK': '✅', 'FAIL': '❌', 'WARN': '⚠️', 'INFO': 'ℹ️'}
    print(f"  {icons.get(status, '?')} [{status}] {msg}")


def setup_test_data():
    """Dohvati/kreiraj minimalne podatke za testove. Bez nagađanja."""
    Company = apps.get_model('companies', 'Company')
    company = Company.objects.first()
    if not company:
        print("ABORT: Nema niti jedne Company u bazi.")
        sys.exit(1)

    # Počisti stare test ostatke
    KontoAccount.objects.filter(code__startswith='__CHAOS__').delete()
    JournalEntry.objects.filter(entry_number__startswith='__CHAOS__').delete()

    a1 = KontoAccount.objects.create(
        company=company, code='__CHAOS__D', name='Test Debit Konto',
        account_type='ASSET', is_active=True
    )
    a2 = KontoAccount.objects.create(
        company=company, code='__CHAOS__K', name='Test Kredit Konto',
        account_type='LIABILITY', is_active=True
    )
    return company, a1, a2


def cleanup():
    KontoAccount.objects.filter(code__startswith='__CHAOS__').delete()
    JournalEntry.objects.filter(entry_number__startswith='__CHAOS__').delete()


# ─────────────────────────────────────────────────────────────────────────────
print(SEPARATOR)
print("  FINA-CONNECT CHAOS MONKEY — FAZA 3 (Precizni napad na konto)")
print(SEPARATOR)

company, acc_d, acc_k = setup_test_data()
print(f"\nℹ️  Firma: {company.name}")
print(f"ℹ️  Konto D: {acc_d.code} | Konto K: {acc_k.code}")

# ─── PRE-ANALIZA ──────────────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("  PRE-ANALIZA: Što model zaista štiti")
print(f"{'─'*70}")

# Balance check postoji u clean() ali SAMO za saved entries s linijama
clean_cond = "Postoji JournalEntry.clean() ali SAMO ako entry ima pk I linije"
log('INFO', clean_cond)

# amount nema MinValueValidator
log('WARN', "LedgerLine.amount: NUMERIC(14,2) - nema MinValueValidator! Negativni iznosi ORM-om prolaze.")

# side choices su lowercase
log('INFO', "LedgerLine.side choices: 'debit'/'credit' (lowercase!) — UPPERCASE prolazi ali nije validan choice")

# unique_together
log('INFO', "JournalEntry.unique_together: (company, entry_number) — postoji na Meta razini")

# ─── NAPAD 1: PRAVI BALANCE CHECK TEST ────────────────────────────────────────
print(f"\n{'─'*70}")
print("  [1] Pravi balance check: clean() s ispravnim podacima")
print(f"      Razlog: Faze 1 i 2 koristile 'MANUAL'/'DEBIT' (uppercase) pa je ValidationError")
print(f"      bio zbog krivog choice, ne zbog balance logike. Ovdje koristimo ispravne vrijednosti.")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        entry = JournalEntry(
            company=company,
            entry_number='__CHAOS__BAL-001',
            date=timezone.now().date(),
            description='Balance check test',
            source_type='manual',
            is_posted=False,
            created_by=None
        )
        entry.save()

        LedgerLine.objects.create(
            journal_entry=entry, account=acc_d,
            side='debit', amount=Decimal('100.00')
        )
        LedgerLine.objects.create(
            journal_entry=entry, account=acc_k,
            side='credit', amount=Decimal('99.99')
        )

        # Ovo je jedini ispravan način da se okine clean() s linijama u bazi
        entry.is_posted = True
        entry.full_clean()
        entry.save()

        log('FAIL', 'Asimetrična temeljnica (100.00 vs 99.99) PRIHVAĆENA! clean() ne baca grešku.')
        results[1] = 'FAIL'
        entry.delete()

except ValidationError as e:
    msg = str(e)
    if 'razlika' in msg.lower() or 'uravnotežen' in msg.lower() or 'duguje' in msg.lower():
        log('OK', f'Balance check radi ispravno: {msg[:120]}')
        results[1] = 'OK'
    else:
        log('FAIL', f'ValidationError ali NIJE zbog balance (drugi razlog): {msg[:200]}')
        results[1] = 'FAIL-WRONG-REASON'
except Exception as e:
    log('FAIL', f'Neočekivana greška: {type(e).__name__}: {str(e)[:200]}')
    results[1] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__BAL-001').delete()


# ─── NAPAD 2: BULK_CREATE BYPASS ──────────────────────────────────────────────
print(f"\n{'─'*70}")
print("  [2] bulk_create bypass: clean() se ne poziva na bulk_create")
print(f"      Redoslijed: entry(is_posted=False) → bulk_create linije → is_posted=True → save()")
print(f"      Jedini pravi redoslijed koji zaobilazi clean() na linijama.")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        entry_bulk = JournalEntry(
            company=company,
            entry_number='__CHAOS__BULK-001',
            date=timezone.now().date(),
            description='bulk_create bypass test',
            source_type='manual',
            is_posted=False,
            created_by=None
        )
        entry_bulk.save()

        # bulk_create ne zove .save() ni .clean() na svakom objektu
        LedgerLine.objects.bulk_create([
            LedgerLine(journal_entry=entry_bulk, account=acc_d, side='debit', amount=Decimal('100.00')),
            LedgerLine(journal_entry=entry_bulk, account=acc_k, side='credit', amount=Decimal('90.00')),
        ])

        # Sada okini full_clean na entryu — balance check se TREBA okidati ovdje
        entry_bulk.is_posted = True
        entry_bulk.full_clean()  # clean() ima pk I linije sada
        entry_bulk.save()

        log('FAIL', 'bulk_create bypass USPIO! Nebalansirana temeljnica (100 vs 90) proknjižena.')
        results[2] = 'FAIL'
        entry_bulk.delete()

except ValidationError as e:
    msg = str(e)
    if 'razlika' in msg.lower() or 'uravnotežen' in msg.lower() or 'duguje' in msg.lower():
        log('OK', f'bulk_create bypass blokiran clean() na entry.full_clean(): {msg[:100]}')
        results[2] = 'OK'
    else:
        log('WARN', f'Blokiran ali zbog drugog razloga: {msg[:200]}')
        results[2] = 'WARN'
except Exception as e:
    log('FAIL', f'{type(e).__name__}: {str(e)[:200]}')
    results[2] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__BULK-001').delete()


# ─── NAPAD 3: NEGATIVNI IZNOS BEZ full_clean ──────────────────────────────────
print(f"\n{'─'*70}")
print("  [3] Negativan iznos direktno u bazu (bez full_clean na LedgerLine)")
print(f"      NUMERIC(14,2) prihvaća negativne — nema DB CHECK constrainta.")
print(f"      ORM-om (bez full_clean): hoće li proći?")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        e3 = JournalEntry(
            company=company, entry_number='__CHAOS__NEG-001',
            date=timezone.now().date(), description='Negativni iznos test',
            source_type='manual', is_posted=False, created_by=None
        )
        e3.save()

        # Direktno save() bez full_clean — zaobilazi ORM validaciju
        ll = LedgerLine(
            journal_entry=e3, account=acc_d,
            side='debit', amount=Decimal('-500.00')
        )
        ll.save()  # NE full_clean — ovo je realni attack vektor

        log('FAIL', 'Negativan iznos (-500.00) PRIHVAĆEN direktnim save()! Nema DB CHECK constrainta.')
        results[3] = 'FAIL'

        # Provjeri i je li balance check prevario (negativni iznos može "uravnotežiti")
        LedgerLine.objects.create(
            journal_entry=e3, account=acc_k,
            side='credit', amount=Decimal('-500.00')
        )
        e3.is_posted = True
        e3.full_clean()
        e3.save()
        log('FAIL', 'Bonus: Dvije negativne linije prošle kao "uravnotežena" temeljnica (-500 = -500)!')
        e3.delete()

except ValidationError as e:
    log('OK', f'Negativan iznos blokiran: {str(e)[:120]}')
    results[3] = 'OK'
except (IntegrityError, Exception) as e:
    log('FAIL', f'{type(e).__name__}: {str(e)[:200]}')
    results[3] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__NEG-001').delete()


# ─── NAPAD 4: DECIMALNA PRECIZNOST (PG ROUNDING) ──────────────────────────────
print(f"\n{'─'*70}")
print("  [4] Decimalni napad: PostgreSQL NUMERIC(14,2) tiho roundа")
print(f"      100.005 → PG roundа na 100.01 | 100.004 → PG roundа na 100.00")
print(f"      Python vidi Decimal('100.005'), baza sprema 100.01. Razlika nastaje TIHO.")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        e4 = JournalEntry(
            company=company, entry_number='__CHAOS__DEC-001',
            date=timezone.now().date(), description='Decimalni napad test',
            source_type='manual', is_posted=False, created_by=None
        )
        e4.save()

        LedgerLine.objects.create(
            journal_entry=e4, account=acc_d,
            side='debit', amount=Decimal('100.005')  # PG će roundati na 100.01
        )
        LedgerLine.objects.create(
            journal_entry=e4, account=acc_k,
            side='credit', amount=Decimal('100.004')  # PG će roundati na 100.00
        )

        # Provjeri što je stvarno u bazi
        cursor = connection.cursor()
        cursor.execute(
            "SELECT side, amount FROM konto_ledgerline WHERE journal_entry_id = %s",
            [e4.pk]
        )
        db_rows = cursor.fetchall()

        db_debit = next((Decimal(str(r[1])) for r in db_rows if r[0] == 'debit'), Decimal('0'))
        db_credit = next((Decimal(str(r[1])) for r in db_rows if r[0] == 'credit'), Decimal('0'))

        print(f"      Python unio:  debit=100.005, credit=100.004")
        print(f"      Baza sprema:  debit={db_debit}, credit={db_credit}")
        print(f"      Razlika u bazi: {abs(db_debit - db_credit)}")

        if db_debit != db_credit:
            # Provjeri prolazi li clean() s ovom razlikom iz baze
            e4.is_posted = True
            try:
                e4.full_clean()
                e4.save()
                log('FAIL', f'Decimalni napad USPIO! Tiha razlika {abs(db_debit-db_credit)} prihvaćena kao proknjižena temeljnica.')
                results[4] = 'FAIL'
            except ValidationError as ve:
                log('OK', f'clean() uhvatio razliku iz baze: {str(ve)[:120]}')
                results[4] = 'OK'
        else:
            log('OK', 'PostgreSQL roundao obje vrijednosti identično — nema razlike u bazi.')
            results[4] = 'OK-NO-DIFF'

        e4.delete()

except Exception as e:
    log('FAIL', f'{type(e).__name__}: {str(e)[:200]}')
    results[4] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__DEC-001').delete()


# ─── NAPAD 5: UNIQUE_TOGETHER IZOLOVAN TEST ───────────────────────────────────
print(f"\n{'─'*70}")
print("  [5] unique_together (company, entry_number) — izolovani test")
print(f"      Bez miješanja s krivim choices. Čisti test DB constrainta.")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        JournalEntry.objects.create(
            company=company, entry_number='__CHAOS__DUPE-001',
            date=timezone.now().date(), description='Duplikat 1',
            source_type='manual', created_by=None
        )
        JournalEntry.objects.create(
            company=company, entry_number='__CHAOS__DUPE-001',
            date=timezone.now().date(), description='Duplikat 2',
            source_type='manual', created_by=None
        )
        log('FAIL', 'Duplikat entry_number u istoj firmi PRIHVAĆEN — unique_together ne radi!')
        results[5] = 'FAIL'
except IntegrityError:
    log('OK', 'unique_together (company, entry_number) blokirao duplikat — DB constraint aktivan.')
    results[5] = 'OK'
except Exception as e:
    log('FAIL', f'Neočekivano: {type(e).__name__}: {str(e)[:200]}')
    results[5] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__DUPE-001').delete()


# ─── NAPAD 6: CASE-SENSITIVITY (SAMO ako napad 5 prolazi) ─────────────────────
print(f"\n{'─'*70}")
print("  [6] Case-sensitivity: '__CHAOS__DUPE' vs '__chaos__dupe'")
print(f"      Relevantan SAMO ako unique_together postoji (Napad 5 = OK).")
print(f"{'─'*70}")

if results.get(5) == 'OK':
    try:
        with transaction.atomic():
            JournalEntry.objects.create(
                company=company, entry_number='__CHAOS__CASE',
                date=timezone.now().date(), description='Case upper',
                source_type='manual', created_by=None
            )
            JournalEntry.objects.create(
                company=company, entry_number='__chaos__case',
                date=timezone.now().date(), description='Case lower',
                source_type='manual', created_by=None
            )
            log('WARN', 'Case-insensitive duplikat PRIHVAĆEN. Moguć logički duplikat knjige.')
            results[6] = 'WARN'
    except IntegrityError:
        log('OK', 'DB collation je case-insensitive — case duplikat blokiran.')
        results[6] = 'OK'
    except Exception as e:
        log('FAIL', f'{type(e).__name__}: {str(e)[:200]}')
        results[6] = 'ERROR'
    finally:
        JournalEntry.objects.filter(entry_number__in=['__CHAOS__CASE', '__chaos__case']).delete()
else:
    log('INFO', 'Preskočen — unique_together nije ni aktivan, ovaj test nema smisla.')
    results[6] = 'SKIPPED'


# ─── NAPAD 7: INTEGRITY_HASH — MOŽE LI SE UPISATI BEZ HASHA ─────────────────
print(f"\n{'─'*70}")
print("  [7] integrity_hash: blank=True, default='' — GoBD audit rupa")
print(f"      Ako se LedgerLine može kreirati bez hasha, GoBD audit lanac je pokidan.")
print(f"{'─'*70}")

try:
    with transaction.atomic():
        e7 = JournalEntry(
            company=company, entry_number='__CHAOS__HASH-001',
            date=timezone.now().date(), description='Hash test',
            source_type='manual', created_by=None
        )
        e7.save()
        ll7 = LedgerLine.objects.create(
            journal_entry=e7, account=acc_d,
            side='debit', amount=Decimal('1.00'),
            integrity_hash=''  # eksplicitno prazno
        )
        if ll7.integrity_hash == '':
            log('WARN', 'LedgerLine kreiran bez integrity_hash! GoBD audit lanac nije automatski popunjen.')
            results[7] = 'WARN'
        else:
            log('OK', f'integrity_hash automatski popunjen: {ll7.integrity_hash[:20]}...')
            results[7] = 'OK'
        e7.delete()
except Exception as e:
    log('FAIL', f'{type(e).__name__}: {str(e)[:200]}')
    results[7] = 'ERROR'
finally:
    JournalEntry.objects.filter(entry_number='__CHAOS__HASH-001').delete()


# ─── CLEANUP ──────────────────────────────────────────────────────────────────
cleanup()


# ─── FINALNI IZVJEŠTAJ ────────────────────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  FINALNI IZVJEŠTAJ — PREPORUKE ZA POPRAVAK")
print(SEPARATOR)

status_map = {
    'OK': ('✅', 'Zaštićeno'),
    'OK-NO-DIFF': ('✅', 'Zaštićeno (PG nema razlike)'),
    'FAIL': ('❌', 'RANJIVO — potreban fix'),
    'FAIL-WRONG-REASON': ('⚠️', 'Blokiran ali iz krivog razloga'),
    'WARN': ('⚠️', 'Upozorenje'),
    'SKIPPED': ('—', 'Preskočen'),
    'ERROR': ('?', 'Neočekivana greška'),
}

attack_names = {
    1: 'Balance check (ispravni podaci)',
    2: 'bulk_create bypass',
    3: 'Negativan iznos (bez full_clean)',
    4: 'Decimalni napad (PG rounding)',
    5: 'unique_together izolovano',
    6: 'Case-sensitivity duplikat',
    7: 'integrity_hash prazan',
}

for i in range(1, 8):
    r = results.get(i, 'ERROR')
    icon, label = status_map.get(r, ('?', r))
    print(f"  {icon} Napad {i} — {attack_names[i]}: {label}")

print()
fails = [i for i, r in results.items() if r in ('FAIL', 'WARN', 'FAIL-WRONG-REASON')]
if fails:
    print("  PREPORUČENI POPRAVCI (po prioritetu):")
    if 3 in fails:
        print("  1. LedgerLine.amount: dodati MinValueValidator(Decimal('0.01'))")
        print("     -> migrations + validator u modelu")
    if 1 in fails or 2 in fails:
        print("  2. JournalEntry.clean(): balance check ne radi ili ne okinuta nigdje osim full_clean()")
        print("     -> Razmisli o post_save signalu ili pre_save hooku koji provjerava balance")
    if 7 in fails:
        print("  3. integrity_hash: dodati post_save signal koji automatski popunjava hash")
        print("     -> SHA-256 od (entry_id + account + side + amount + prethodni hash)")
    if 6 in fails:
        print("  4. Case-insensitive unique: dodati __iexact provjeru u clean() ili citext extension")
else:
    print("  Svi testovi prošli — sustav je dobro zaštićen.")

print(SEPARATOR)
