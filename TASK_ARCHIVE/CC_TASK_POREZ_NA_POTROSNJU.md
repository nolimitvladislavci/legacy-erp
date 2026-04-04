# CC_TASK_POREZ_NA_POTROSNJU.md
# Za: CC Code
# Datum: 2026-03-31
# Rok: 10.04.2026.
# Prioritet: P1 — zakonska obaveza za ugostiteljstvo
# Otkrivač: Marija Brtan (knjigovodstvo Konjik d.o.o.)

---

## ZAKONSKI OKVIR

**Zakon o lokalnim porezima** (NN 115/16, 101/17, 114/22)
- čl. 30-38: Porez na potrošnju
- Predmet: pružanje usluga hrane i pića u ugostiteljskim objektima
- Obveznik: ugostitelj (fizička ili pravna osoba)
- Osnovica: ukupan prihod od prodaje **bez PDV-a**
- Stopa: **do 3%** — određuje svaka JLS (Grad/Općina) posebnom odlukom
- Rok prijave: do 20. u mjesecu za prethodni mjesec (Obrazac PP-MI-PO)
- Uplata: na žiro račun JLS
- NE prikazuje se na računu kupcu (nije PDV!)
- Ali mora biti evidentiran u poslovnim knjigama

**Tko je obveznik:**
- NKD 55.xx (smještaj), 56.xx (restorani, kafići, barovi)
- Svaki ugostitelj bez obzira na veličinu
- I udruge ako naplaćuju konzumaciju (npr. KUD, DVD)

**Stope po gradovima (primjeri):**
- Osijek: 3%
- Đakovo: 3%
- Zagreb: 3%
- Čepin: 3% (Grad Đakovo)
- Vladislavci: provjeri odluku Općine Vladislavci

---

## TRENUTNO STANJE SUSTAVA

- `TaxRate` model postoji ali samo za PDV (HR 5/13/25/26%, DE, oslobođeno)
- **NEMA polja za porez na potrošnju**
- POS ne bilježi niti jedan podatak koji bi omogućio PP-MI-PO obrazac
- `POSSettings` nema `consumption_tax_rate` polje
- Računi ne pokazuju razdvojen iznos PP-a

---

## ŠTO TREBA IMPLEMENTIRATI

### 1. Model — POSSettings proširenje

```python
# pos/models.py — u klasi POSSettings
consumption_tax_active = models.BooleanField(
    default=False,
    verbose_name='Porez na potrošnju aktivan',
    help_text='Primjenjuje se za ugostitelje (NKD 56.xx)'
)
consumption_tax_rate = models.DecimalField(
    max_digits=4, decimal_places=2, default=Decimal('3.00'),
    verbose_name='Stopa PP (%)',
    help_text='Lokalna stopa — provjeri odluku JLS (obično 3%)'
)
consumption_tax_account = models.CharField(
    max_length=50, blank=True,
    verbose_name='Žiro račun JLS za uplatu PP',
    help_text='Npr. HR1210010051700029997'
)
```

Migracija: `python manage.py makemigrations pos && python manage.py migrate`

### 2. POSReceipt — evidencija PP-a

```python
# pos/models.py — u klasi POSReceipt
consumption_tax_base = models.DecimalField(
    max_digits=10, decimal_places=2, default=Decimal('0'),
    verbose_name='Osnovica za PP (bez PDV-a)'
)
consumption_tax_amount = models.DecimalField(
    max_digits=10, decimal_places=2, default=Decimal('0'),
    verbose_name='Iznos poreza na potrošnju'
)
```

### 3. Kalkulator u checkout

```python
# pos/services/checkout.py — u _calculate_receipt() ili process_payment()
def _apply_consumption_tax(receipt, settings):
    """
    Primijeni porez na potrošnju ako je aktivan.
    PP se ne prikazuje kupcu — interni je porez tvrtke.
    Osnovica = ukupno - PDV (iznos bez PDV-a)
    """
    if not settings.consumption_tax_active:
        return
    rate = settings.consumption_tax_rate / Decimal('100')
    base = receipt.subtotal  # iznos bez PDV-a
    pp_amount = (base * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    receipt.consumption_tax_base = base
    receipt.consumption_tax_amount = pp_amount
    receipt.save(update_fields=['consumption_tax_base', 'consumption_tax_amount'])
```

### 4. Izvještaj PP-MI-PO (Obrazac)

```python
# pos/views.py ili nova views_reports.py
@login_required
def consumption_tax_report(request):
    """
    Mesečni izvještaj za PP-MI-PO obrazac.
    Grupira: ukupna osnovica po stopi, iznos PP-a, za svaki terminal.
    """
    # Parametri: month, year
    # Output: HTML + PDF download
    # Polja: naziv poduzetnika, OIB, adresa, JLS, stopa, osnovica, iznos PP
```

**URL:** `/hr/pos/reports/consumption-tax/`

### 5. Postavke u POS Settings (UI)

U `/hr/pos/settings/` dodati tab ili sekciju **"Porez na potrošnju"**:
- Toggle: Aktivan / Neaktivan
- Polje: Stopa % (default 3.00)
- Polje: Žiro račun JLS
- Link: Pregled mesečnog izvještaja

### 6. Z-izvještaj proširenje

U Z-izvještaj (session_zreport) dodati redak:
```
Porez na potrošnju:
  Osnovica: X,XX €
  PP (3%): X,XX €
```

---

## PROVJERA OBVEZNIKA

Kreirati management command za provjeru koja tvrtka u sustavu
ima NKD 56.xx i nije aktivirala PP:

```bash
venv/bin/python manage.py check_consumption_tax_obligors
```

Output: lista firmi s NKD ugostiteljstvo bez aktivnog PP-a → WhatsApp upozorenje vlasniku.

---

## TESTNI SLUČAJ

```python
# pos/tests/test_consumption_tax.py
class ConsumptionTaxTest(TestCase):
    def test_pp_calculation(self):
        # Račun 100 EUR, PDV 25% = subtotal 80 EUR
        # PP 3% od 80 EUR = 2.40 EUR
        # Kupac plaća: 100 EUR (PP je trošak tvrtke, ne kupca)
        receipt = create_test_receipt(total=100, vat=25)
        settings = create_pos_settings(consumption_tax_active=True, rate=3)
        _apply_consumption_tax(receipt, settings)
        assert receipt.consumption_tax_amount == Decimal('2.40')
        assert receipt.consumption_tax_base == Decimal('80.00')
```

---

## NAPOMENE ZA CC

1. **PP se NE dodaje na cijenu kupcu** — to je pogrešna praksa!
   PP je trošak ugostitelja, plaća se JLS-u iz vlastite marže.

2. **PP nije PDV** — ne smije se miješati u PDV evidenciju.
   Poseban redak u financijskim izvještajima.

3. Najprije provjeri koji klijenti u sustavu imaju NKD 56.xx:
   ```sql
   SELECT name, nkd_code_id FROM companies_company
   WHERE nkd_code_id LIKE '56%' OR nkd_code_id LIKE '55%';
   ```

4. **Prioritet za Mariju Brtan** (KS Limit Knjigovodstvo) —
   ona vodi knjige klijentima koji su u ugostiteljstvu.
   Treba joj izvještaj PP-MI-PO automatski generiran iz POS podataka.

5. Javi Sonnet kad su migracije i checkout logika gotovi.
