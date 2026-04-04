# CC_TASK: RIST — 6 Inženjerskih Problema
# Datum: 05.04.2026. | Rok: 07.04.2026. | Prioritet: P0
#
# Gemini je identificirao 7 scenarija. Verificirani iz koda:
# REALNI: G1(round), G2(forex), G3(OIB rate), G4(CT po artiklu), D1(zombi), D2(hash)
# DRAMATIZIRANI: G5(SHA collision), G6(deadlock), G7(OSS) — nisu kod bugovi

PRAVILO: READ models.py/services PRVO. quantize(Decimal('0.01'), ROUND_HALF_UP) za sve novčane izračune.
PRAVILO: select_for_update() za sve stock i konto operacije.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.

---

## G1 — round() → quantize() [KRITIČNO: mathematician's enemy]

### Problem:
```python
# invoicing/models.py InvoiceItem.save():
self.total_price = round(Decimal(str(qty)) * Decimal(str(unit_price)) * ..., 2)
self.gross_total = round(self.total_price * (1 + tax_rate/100), 2)
```
Python `round()` = "banker's rounding": round(2.5)=2, round(3.5)=4
Na N stavki → kumulativna greška ≠ 0

### Provjeri:
```bash
grep -n "round(\|float(" invoicing/models.py invoicing/services/invoice_service.py | grep -v "test\|migr"
grep -rn "round(" konto/services_file.py | head -10
grep -rn "round(" pos/services/checkout.py | head -10
```

### Fix — invoicing/models.py, InvoiceItem.save():
```python
from decimal import ROUND_HALF_UP

def save(self, *args, **kwargs):
    q = Decimal('0.01')
    qty       = Decimal(str(self.quantity or 0))
    up        = Decimal(str(self.unit_price or 0))
    disc      = Decimal(str(self.discount_percent or 0))
    tax_rate  = Decimal(str(self.tax_rate or 0))

    net     = (qty * up * (1 - disc / Decimal('100'))).quantize(q, ROUND_HALF_UP)
    gross   = (net * (1 + tax_rate / Decimal('100'))).quantize(q, ROUND_HALF_UP)

    self.total_price = net
    self.gross_total = gross
    super().save(*args, **kwargs)
```

PROVJERI sve ostale `round()` u istim datotekama — zamijeniti istim patternom.

### Test:
```python
venv/bin/python manage.py shell -c "
from decimal import Decimal, ROUND_HALF_UP

# Banker's rounding test
print('round(2.5):', round(2.5))   # Python: 2 (krivo)
print('round(3.5):', round(3.5))   # Python: 4 (krivo)

# Pravilno:
q = Decimal('0.01')
val = Decimal('2.5')
print('quantize 2.5:', val.quantize(q, ROUND_HALF_UP))  # 2.50 (ispravno)

# Simulacija 1000 stavki po 0.001 EUR:
total = sum(Decimal('0.001').quantize(q, ROUND_HALF_UP) for _ in range(1000))
print('1000 × 0.001 EUR:', total, '(treba biti 1.00)')
"
```

---

## G2 — Forex: tečajna razlika nema konto [P1]

### Problem:
`Invoice.currency` postoji ali nema `exchange_rate` field.
Tečajne razlike idu u "crnu rupu" — niti na 3415 niti na 4700.

### Provjeri:
```bash
grep -n "currency\|exchange_rate\|forex" invoicing/models.py | head -10
grep -n "3415\|4700\|tecaj\|tečaj" konto/ -r --include="*.py" | grep -v "test\|migr|nonprofit" | head -10
```

### Fix — Minimalni (do GO-LIVE):

U `invoicing/models.py`, Invoice klasi DODAJ:
```python
exchange_rate = models.DecimalField(
    max_digits=12, decimal_places=6, default=Decimal('1.000000'),
    verbose_name=_('Tečaj prema EUR'),
    help_text='1.000000 = EUR; za USD/CHF unesi aktualni tečaj HNB-a'
)
```

U `konto/services_file.py`, `book_invoice()` — DODAJ na kraju:
```python
# Tečajna razlika: ako currency != EUR i exchange_rate != 1
if (getattr(invoice, 'currency', 'EUR') != 'EUR' and
        getattr(invoice, 'exchange_rate', Decimal('1')) != Decimal('1')):
    from decimal import ROUND_HALF_UP
    eur_total = (total * invoice.exchange_rate).quantize(Decimal('0.01'), ROUND_HALF_UP)
    forex_diff = abs(eur_total - total)
    if forex_diff > Decimal('0.01'):
        forex_code = '3415' if eur_total > total else '4700'
        forex_name = 'Pozitivne tečajne razlike' if eur_total > total else 'Negativne tečajne razlike'
        forex_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=forex_code,
            defaults={'name': forex_name, 'account_type': 'income' if '3415' in forex_code else 'expense'})
        LedgerLine.objects.create(
            journal_entry=je, account=forex_acct,
            side='credit' if eur_total > total else 'debit',
            amount=float(forex_diff),
            description=f'Tečajna razlika: {invoice.currency}/{invoice.exchange_rate}')
```

Migracija:
```bash
venv/bin/python manage.py makemigrations invoicing --name="add_exchange_rate"
venv/bin/python manage.py migrate 2>&1 | tail -3
```

---

## G3 — OIB Lookup: rate limit [P0, sigurnost]

### Problem:
`partner_oib_lookup` = @login_required ali nema throttling.
Sudreg/ePorezna ima rate limit po IP-u — korisnik može upaliti skript i slati 1000 zahtjeva.

### Provjeri:
```bash
grep -n "def partner_oib_lookup\|rate_limit\|throttl" partners/views.py | head -5
cat memio_pet/security.py | head -50
```

### Fix — partners/views.py:

```python
import time
from django.core.cache import cache

@login_required
def partner_oib_lookup(request):
    # Rate limit: max 30 zahtjeva u 60 sekundi po korisniku
    cache_key = f'oib_lookup_rate_{request.user.pk}'
    current = cache.get(cache_key, 0)
    if current >= 30:
        return JsonResponse({
            'error': 'Previše zahtjeva. Pričekajte minutu.',
            'retry_after': 60,
        }, status=429)
    cache.set(cache_key, current + 1, timeout=60)

    oib = request.GET.get('oib', '').strip()
    # ... ostatak koda nepromjenjen
```

DODAJ isti rate limit na sve javne OIB/VAT lookup endpointe:
```bash
grep -rn "def.*oib_lookup\|def.*vat_lookup\|def.*sudreg" --include="*.py" | grep -v "test\|migr\|venv" | head -10
```

---

## G4 — Consumption Tax: po artiklu, ne po bonu [P0, zakonski]

### Problem:
Porez na potrošnju se obračunava na `receipt.subtotal` — na SVE stavke.
Zakon o lokalnim porezima NN 115/2016, čl. 35: porez se plaća na "pružanje ugostiteljskih usluga".
Roba (takeaway, preprodaja) nije ugostiteljska usluga.

### Provjeri:
```bash
grep -n "consumption_tax_amount\|ct_rate\|subtotal.*ct\|ct.*subtotal" pos/services/checkout.py | head -10
grep -n "is_service\|service.*item\|item.*service\|TaxCategory\|ct_applicable" pos/models.py | head -10
```

### Fix — dvije razine:

**Razina 1 (brzo, bez migracije):** Dodaj `ct_excluded` flag na POSSettings:
```python
# pos/models.py, POSSettings:
ct_applies_to_all = models.BooleanField(
    default=True,
    verbose_name='CT na sve stavke',
    help_text='Iskljuci za mješovite POS (roba + usluge)'
)
```

**Razina 2 (ispravno, migracija):** Dodaj `ct_applicable` na InventoryItem ili POSReceiptItem:
```bash
grep -n "class POSReceiptItem\|class InventoryItem" pos/models.py inventory/models.py | head -5
```

U POSReceiptItem.save() ili CheckoutService:
```python
# Izračunaj CT samo na stavke koje podliježu
ct_base = sum(
    item.total_price for item in receipt.items.all()
    if getattr(item, 'ct_applicable', True)  # default True = na sve (current behavior)
)
ct_amount = (ct_base * ct_rate).quantize(Decimal('0.01'), ROUND_HALF_UP)
```

Za sada: dodaj `ct_applicable = True` default, ostavi current behavior ali s dokumentacijom:
```python
# TODO: Zakon o lokalnim porezima čl.35 — CT se primjenjuje samo na ugostiteljske usluge.
# Za POS koji miješa robu (takeaway) i usluge: postaviti ct_applicable=False na robne artikle.
# Trenutno: ct_applies_to_all=True za sve firme (konzervativno — bolje više platiti nego manje).
```

---

## D1 — Zombi zaposlenik: nema provjere aktivnosti [P1]

### Problem:
`payroll/services.py` filtrira `TimeEntry(status='APPROVED')` ali ne provjerava:
- Je li radnik aktivan u tom periodu?
- Je li radnik na bolovanju?
- Je li radnik primio otkaz?

### Provjeri:
```bash
grep -n "class EmployeeProfile\|is_active\|termination\|sick_leave\|bolovanje\|end_date" worktime/models.py | head -15
grep -n "def calculate_hr_payslip\|filter.*TimeEntry\|TimeEntry.*filter" payroll/services.py payroll/joppd.py | head -10
```

### Fix — payroll/services.py, na početku calculate_hr_payslip():
```python
def calculate_hr_payslip(user, company, year, month, ...):
    from worktime.models import EmployeeProfile, TimeEntry
    import datetime

    # Provjeri je li radnik aktivan za taj period
    period_end = datetime.date(year, month, __import__('calendar').monthrange(year, month)[1])
    period_start = datetime.date(year, month, 1)

    try:
        emp = user.employeeprofile
        # Provjeri datum otkaza
        if hasattr(emp, 'termination_date') and emp.termination_date:
            if emp.termination_date < period_start:
                raise ValueError(
                    f'Radnik {user.get_full_name()} ima otkaz od {emp.termination_date} '
                    f'— ne može imati plaću za {month:02d}/{year}')

        # Provjeri je li aktivan
        if not getattr(emp, 'is_active', True):
            raise ValueError(f'Radnik {user.get_full_name()} nije aktivan')

    except user.employeeprofile.RelatedObjectDoesNotExist:
        pass  # Nema profila = ok za sada, samo nema benefita

    # Nastavak originalnog koda
    entries = TimeEntry.objects.filter(
        user=user, status='APPROVED',
        date__year=year, date__month=month,
    )
    # ...
```

---

## D2 — Integrity Hash Mutable [P1]

### Problem:
`ArhivaEntry.save()`: `Always recompute hash — detects tampering on update`
Ovo znači: promijeniš dokument → hash se osvježi → stari hash izgubljen.
Arhiva JE auditabilna (audit log), ali NIJE immutable (hash se mijenja).

### Provjeri:
```bash
grep -n "integrity_hash\|compute_integrity_hash\|Always recompute\|immutable\|deletion_protected" documents/models.py | head -15
grep -n "ArhivaEntry.*update\|save.*update_fields" documents/views_arhiva.py | head -10
```

### Fix:
```python
# documents/models.py, ArhivaEntry.save():

# STARO: Always recompute hash
# self.integrity_hash = self.compute_integrity_hash()

# NOVO: Postavi hash samo pri prvom save (creation) — immutable nakon toga
if not self.integrity_hash:
    self.integrity_hash = self.compute_integrity_hash()
else:
    # Verifikacija: provjeri nije li netko promijenio sadržaj bez promjene hasha
    new_hash = self.compute_integrity_hash()
    if new_hash != self.integrity_hash:
        # Sadržaj se promijenio — logiraj i zadrži STARI hash za integritet
        import logging
        logging.getLogger('documents.integrity').warning(
            'ArhivaEntry %s: sadržaj promijenjen! '
            'Stari hash: %s, novi: %s — čuvam stari hash za reviziju.',
            self.pk, self.integrity_hash, new_hash
        )
        # BITNO: NE recompute hash — audit log već bilježi promjenu
        # Stari hash ostaje kao "originalni" fingerprint
```

NAPOMENA: Ovo je promjena ponašanja — stariji audit patch je namjerno stavio "always recompute".
Provjeri je li to bila namjerna odluka:
```bash
git log --oneline --follow documents/models.py | grep "audit\|hash\|immutable" | head -5
```

---

## VERIFIKACIJA SVIH 6

```bash
cd /var/www/fina-connect

# G1: Banker's rounding gone?
grep -n "round(" invoicing/models.py | grep -v "#\|test" | head -5

# G2: exchange_rate postoji?
venv/bin/python manage.py shell -c "from invoicing.models import Invoice; print(hasattr(Invoice(), 'exchange_rate'))"

# G3: Rate limit na OIB lookup?
grep -n "rate\|429\|cache.get\|cache.set" partners/views.py | head -5

# G4: CT flag postoji?
grep -n "ct_applicable\|ct_applies_to_all" pos/models.py | head -5

# D1: Zombi check?
grep -n "termination_date\|is_active.*emp" payroll/services.py | head -5

# D2: Hash immutable?
grep -n "if not self.integrity_hash" documents/models.py | head -3

venv/bin/python manage.py check 2>&1 | tail -3
venv/bin/python manage.py migrate 2>&1 | tail -5

git add -A
git commit -m "fix(rist): round→quantize, forex konto, OIB rate limit, CT po artiklu, zombi payroll, hash immutable"
```

---

## DONE KRITERIJI — RIST 10/10:

Matematika:
- [ ] InvoiceItem.save(): round() → quantize(ROUND_HALF_UP)
- [ ] Svi novčani izračuni: Decimal, ne float, ne round()

Sigurnost:
- [ ] OIB lookup: 30 req/60 sek po korisniku (Redis cache)
- [ ] Integrity hash: nepromjenjiv nakon prvog save

Zakon:
- [ ] Exchange rate field na Invoice
- [ ] Forex razlika → konto 3415/4700
- [ ] Consumption tax: dokumentirano na kojim artiklima se primjenjuje
- [ ] Zombi zaposlenik: provjera termination_date pri obračunu plaće

manage.py check: 0 errora
