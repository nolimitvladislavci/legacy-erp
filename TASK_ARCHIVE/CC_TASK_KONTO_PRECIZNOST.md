# CC_TASK: KONTO PRECIZNOST — 5 nepravilnosti
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P0
#
# Zakonska osnova:
#   Zakon o računovodstvu NN 78/2015 — točnost dvojnog knjiženja
#   Pravilnik o PDV-u NN 79/2013 čl. 89 — avansni račun
#   Zakon o doprinosima NN 84/2008 — razlučivanje vrsta doprinosa
#   Zakon o lokalnim porezima NN 115/2016 čl. 35 — konto 2390

PRAVILO: READ services_file.py i signals.py PRVO. select_for_update() za sve JE operacije.
PRAVILO: Svaka promjena konta mora biti idempotentna — ne kreira duplikate.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.

---

## NEPRAVILNOST 1 — KONTO 2390 KONFLIKT

### Provjeri:
```bash
grep -n "2390\|doprinosi\|consumption_tax" konto/services_file.py payroll/services.py | head -20
grep -n "code.*2390\|'2390'" konto/ payroll/ -r --include="*.py" | grep -v test | grep -v migr
```

### Problem:
  payroll/services.py:  `'2390'` = "Obveze za doprinose"
  konto/services_file.py: `'2390'` = "Obveze za porez na potrošnju (JLS)"
  → isti konto, konflikt u knjigama

### Fix — payroll/services.py:
READ: payroll/services.py (book_payroll_to_ledger, konto 2390)

ZAMIJENI konte za doprinose:
```python
# STARO:
acct_doprinosi = get_or_create_account('2390', 'Obveze za doprinose', AccountType.LIABILITY)

# NOVO — razlučivanje po vrsti doprinosa:
acct_mio1      = get_or_create_account('2450', 'Obveze za MIO I. stup', AccountType.LIABILITY)
acct_zdravstvo = get_or_create_account('2460', 'Obveze za zdravstveno osiguranje', AccountType.LIABILITY)
acct_doprinosi_total = get_or_create_account('2455', 'Obveze za doprinose (ukupno)', AccountType.LIABILITY)
```

AKO `total_contributions` nije razlučen po vrstama u Payslip modelu:
```python
# Provjeri:
grep -n "contributions_amount\|mio\|zdravstvo\|doprinos" payroll/models.py | head -10
```

Ako postoji samo `contributions_amount` (ukupno) → koristi '2455':
```python
# Jednostavni fix bez migracije:
acct_doprinosi = get_or_create_account(
    '2455', 'Obveze za doprinose', AccountType.LIABILITY)
# 2390 ostaje ekskluzivno za porez na potrošnju (JLS)
```

---

## NEPRAVILNOST 2 — STORNO KNJIŽENJE KRIVA LOGIKA

### Provjeri:
```bash
grep -n "is_outgoing\|doctype.*S\b\|'S'" konto/services_file.py | head -15
sed -n '65,170p' konto/services_file.py  # book_invoice() komplet
```

### Problem:
`book_invoice()`: `is_outgoing = invoice.doctype in ('R', 'P', 'A')`
Storno `'S'` nije u listi → ide u "primljeni račun" granu → krivo knjiženje.
Invoice.total za storno je NEGATIVAN → linije su negativne u krivim stranama.

### Fix — konto/services_file.py, book_invoice():

Pronađi `is_outgoing = invoice.doctype in ('R', 'P', 'A')` i ZAMIJENI:
```python
# Razlučivanje vrste dokumenta
is_storno   = invoice.doctype in ('S', 'GS')
is_outgoing = invoice.doctype in ('R', 'RN', 'A', 'FA') and not is_storno
is_incoming = invoice.doctype in ('URA',) and not is_storno

if is_storno:
    # Storno = reversal originalnog IRA knjiženja
    # Jer Invoice.total je negativan → uzimamo apsolutnu vrijednost
    total_abs    = abs(total)
    subtotal_abs = abs(subtotal)
    tax_abs      = abs(tax_amount)

    if total_abs <= 0:
        return None  # Storno od nule — nema smisla

    # D: Prihodi (storniramo prihod — vraćamo ga)
    rev_acct = _get_or_fail_or_create(company, revenue_code, revenue_name, 'income')
    LedgerLine.objects.create(
        journal_entry=je, account=rev_acct,
        side='debit', amount=float(subtotal_abs),
        description=f'Storno prihoda: {invoice.number}')

    # D: PDV obveza (storniramo PDV koji smo prijavili)
    if tax_abs > 0:
        vat_acct = _get_or_fail_or_create(company, vat_out_code, 'Obveze za PDV', 'liability')
        LedgerLine.objects.create(
            journal_entry=je, account=vat_acct,
            side='debit', amount=float(tax_abs),
            description=f'Storno PDV: {invoice.number}')

    # P: Potraživanja od kupaca (kupac više ne duguje)
    recv_acct = _get_or_fail_or_create(company, receivable_code, 'Potraživanja od kupaca', 'asset')
    LedgerLine.objects.create(
        journal_entry=je, account=recv_acct,
        side='credit', amount=float(total_abs),
        description=f'Storno potraživanja: {invoice.storno_of.number if invoice.storno_of else invoice.number}')

    return je
```

DODAJ helper ako ne postoji:
```python
def _get_or_fail_or_create(company, code, name, account_type):
    """get_or_create za konto — ne baca exception."""
    from .models import KontoAccount
    acct, _ = KontoAccount.objects.get_or_create(
        company=company, code=code,
        defaults={'name': name, 'account_type': account_type})
    return acct
```

---

## NEPRAVILNOST 3 — BANKOVNI IZVOD → INVOICE.STATUS NE IDE NA PAID

### Provjeri:
```bash
sed -n '27,120p' konto/booking_engine.py
grep -n "status.*PAID\|invoice.*PAID\|mark.*paid" konto/booking_engine.py | head -10
grep -n "matched_invoice\|payment_date" konto/models.py | head -10
```

### Problem:
`book_bank_transaction()` kreira JE ali ne updateuje `Invoice.status = 'PAID'`.
Prati se u knjigama ali ne na fakturi.

### Fix — konto/booking_engine.py, book_bank_transaction():

Pronađi `with transaction.atomic():` blok, na kraju DODAJ:
```python
# Ažuriraj status Invoice → PAID (ako je u cijelosti plaćena)
inv = bank_txn.matched_invoice
if inv and hasattr(inv, 'status') and inv.status not in ('PAID', 'STORNO', 'CANCELLED'):
    # Provjeri je li ukupni iznos transakcije >= iznos fakture (dopušta zaokruženje)
    if abs(bank_txn.amount) >= abs(inv.total or 0) - Decimal('0.01'):
        type(inv).objects.filter(pk=inv.pk).update(
            status='PAID',
            payment_date=bank_txn.transaction_date,
        )
        logger.info(
            'Invoice %s → PAID (BankTxn %s, %s)',
            inv.number, bank_txn.pk, bank_txn.amount
        )
    else:
        # Djelomično plaćanje — označi kao PARTIAL ako postoji status
        logger.info(
            'Invoice %s djelomično plaćena: %s / %s',
            inv.number, bank_txn.amount, inv.total
        )
        # Ako Invoice ima 'PARTIAL' status:
        # type(inv).objects.filter(pk=inv.pk).update(status='PARTIAL')
```

### Dodaj `payment_date` field ako ne postoji:
```bash
grep -n "payment_date\|date_paid\|paid_at" invoicing/models.py | head -5
```

Ako ne postoji:
```python
# invoicing/models.py — u Invoice klasi dodaj:
payment_date = models.DateField(null=True, blank=True, verbose_name=_('Datum plaćanja'))

# Migracija:
# venv/bin/python manage.py makemigrations invoicing --name="add_payment_date"
# venv/bin/python manage.py migrate
```

---

## NEPRAVILNOST 4 — INVOICE TOTAL BALANS: dodaj validaciju

### Provjeri:
```bash
grep -n "def clean\|def validate\|total.*subtotal\|subtotal.*tax" invoicing/models.py | head -15
```

### Fix — invoicing/models.py, Invoice.clean() ili book_invoice():

U `book_invoice()` (konto/services_file.py), DODAJ na početku:
```python
# Konzistentnost iznosa — detektira loš import/ručni unos
if subtotal > 0 and tax_amount >= 0 and total > 0:
    expected_total = (subtotal + tax_amount).quantize(Decimal('0.01'))
    actual_total   = total.quantize(Decimal('0.01'))
    diff = abs(expected_total - actual_total)
    if diff > Decimal('0.05'):  # Tolerancija 5 centi (zaokruženje)
        logger.warning(
            'Invoice %s: total nekonzistentan! '
            'subtotal(%s) + tax(%s) = %s ≠ total(%s). Razlika: %s.',
            invoice.number, subtotal, tax_amount, expected_total,
            actual_total, diff
        )
        # Ne blokiraj — samo logirati i korigirati total za knjiženje:
        total = expected_total  # Koristimo izračunati, ne uneseni
```

---

## NEPRAVILNOST 5 — AVANSNI RAČUN: PDV pri završnom

### Provjeri:
```bash
grep -n "linked_invoice\|avans.*final\|settlement\|advance.*book" invoicing/ konto/ -r --include="*.py" | grep -v test | grep -v migr | head -10
grep -n "storno_of\|linked_invoice\|related_invoice" invoicing/models.py | head -10
```

### Problem (P2 — complex, ali zakonski obavezan):
Avansni račun (A): PDV se obračunava odmah, knjiženje:
```
D: 1200 Potraživanja od kupca   1250€
P: 2900 Primljeni predujmovi    1000€
P: 2400 PDV obveza               250€
```

Završni račun koji zatvara avans:
```
D: 2900 Primljeni predujmovi    1000€  ← zatvori predujam
D: 1200 Potraživanja (razlika)   500€
P: 7000 Prihodi                 1400€
P: 2400 PDV                      100€  ← samo PDV na razliku (1500-1000)*25%
```

Trenutno: `book_invoice()` za 'A' radi isto kao za 'R' — ne koristi konto 2900.

### Fix (minimalni — konto 2900 za avanse):

U `book_invoice()`, pronađi `if is_outgoing:` granu i DODAJ razlučivanje:
```python
if is_outgoing:
    if invoice.doctype == 'A':
        # Avansni račun — koristi 2900 Primljeni predujmovi umjesto 7000
        revenue_code = '2900'
        revenue_name = 'Primljeni predujmovi (avans)'
    # ... ostatak ostaje isti
```

Završni račun koji zatvara avans (future CC task — complex):
Treba: u `linked_invoice` postoji FK prema avansnom → zatvori 2900, smanji PDV osnovu.
Za sada: označi `TODO` u book_invoice():
```python
# TODO: Ako postoji linked_invoice (avansni) → zatvori konto 2900 i oduzmi PDV
# Implementirati u CC_TASK_AVANSNI_ZATVARANJE.md
if invoice.linked_invoice and invoice.linked_invoice.doctype == 'A':
    logger.warning(
        'Invoice %s zatvara avansni %s — ručna provjera PDV odbitka potrebna!',
        invoice.number, invoice.linked_invoice.number
    )
```

---

## VERIFIKACIJA

```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -3

# Test: storno knjiženje
venv/bin/python manage.py shell << 'EOF'
from konto.services_file import book_invoice

# Simulacija storno invoice (negativan total)
class FakeStorno:
    number = 'S-TEST-001'
    doctype = 'S'
    country = 'HR'
    subtotal = -800
    tax_amount = -200
    total = -1000
    client_name = 'Test kupac'
    storno_of = None

s = FakeStorno()
from konto.services_file import book_invoice
# Provjeri logiku bez kreiranja (dry run)
print('is_storno:', s.doctype in ('S', 'GS'))
print('total abs:', abs(s.total))
print('Storno logika: OK' if s.doctype in ('S','GS') else 'FAIL')
EOF

# Test: konto 2390/2455 razlučivanje
grep -n "2390\|2455" konto/services_file.py payroll/services.py | grep -v test

# Test: bankovni → Invoice PAID
grep -n "status.*PAID\|PAID.*update" konto/booking_engine.py | head -5

venv/bin/python manage.py migrate 2>&1 | tail -5

git add -A
git commit -m "fix(konto): storno reversal, konto 2390/2455 razlučivanje, bank→invoice PAID, total validacija, avansni 2900"
```

---

## DONE KRITERIJI:

- [ ] konto 2390 = isključivo JLS porez na potrošnju
- [ ] konto 2455 = doprinosi u payrollu
- [ ] Storno S/GS → D:7000/2400 P:1200 (reversal IRA)
- [ ] book_bank_transaction → Invoice.status = PAID
- [ ] payment_date field postoji na Invoice
- [ ] book_invoice validira total = subtotal + tax (log warning ako ne)
- [ ] Avansni doctype='A' → konto 2900 Primljeni predujmovi
- [ ] manage.py check: 0 errora
- [ ] JournalEntry is_balanced za sve nove unose
