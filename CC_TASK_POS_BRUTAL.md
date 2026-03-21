## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — POS Brutalni Test Suite

## Kontekst
Postojeći testovi: 154 (unit + view testovi)
Što nedostaje: edge cases, race conditions, R1 račun, offline sync,
multi-terminal konflikt, DE TSE routing, negativni scenariji

## OBAVEZNO PRVO — čitaj modele
```bash
grep -n "buyer_oib\|buyer_name\|is_r1\|tse_\|fiscal_exempt\|is_nonprofit" \
  /var/www/fina-connect/pos/models.py | head -30
grep -n "def process_receipt\|def _fiscalize\|def _fiscalize_tse\|def _should_fiscalize" \
  /var/www/fina-connect/pos/services/checkout.py | head -20
grep -n "def quick_pay\|def process_payment" \
  /var/www/fina-connect/pos/services/__init__.py | head -10
```

## Napiši: `/var/www/fina-connect/pos/tests/test_brutal.py`

### Klasa 1: R1 Račun (novi model)
```python
class TestR1Racun(POSTestBase):
    # T-01: R1 s OIB-om → is_r1=True auto
    # T-02: R1 bez OIB-a → is_r1=False
    # T-03: Nevažeći OIB (10 znakova) → ValidationError
    # T-04: R1 bon ima buyer_name i buyer_address u receipt output
    # T-05: FINA XML sadrži <OibKupca> kad is_r1=True
    # T-06: FINA XML nema <OibKupca> kad is_r1=False
```

### Klasa 2: Nonprofit guard (mixing blokada)
```python
class TestNonprofitGuard(POSTestBase):
    # T-07: Samo nonprofit stavke → bypass fiskalizacije
    # T-08: Samo komercijalne stavke → normalna fiskalizacija
    # T-09: Mješanje nonprofit + komercijalno → CheckoutValidationError
    # T-10: fiscal_exempt kompanija → uvijek bypass
    # T-11: Donacija u POS-u → is_nonprofit_activity=True → bypass
```

### Klasa 3: Multi-terminal race condition
```python
class TestMultiTerminal(POSTestBase):
    # T-12: 2 terminala iste firme → neovisne smjene
    # T-13: Isti terminal → ne može otvoriti 2 smjene
    # T-14: 10 paralelnih add_item na isti receipt → atomarno, bez duplikata
    # T-15: Stock deduction race: 5 niti prodaju isti artikl, samo 1 prolazi
    #       ako je quantity=1 i allow_negative=False
    # T-16: receipt_number je unique per session (ne per terminal)
```

### Klasa 4: Plaćanje — edge cases
```python
class TestPaymentEdgeCases(POSTestBase):
    # T-17: Split plaćanje CASH + CARD → suma mora = total
    # T-18: Revolut plaćanje → method=REVOLUT → bon paid
    # T-19: Voucher plaćanje → Voucher.remaining se smanjuje
    # T-20: Voucher expired → CheckoutValidationError
    # T-21: Voucher remaining < total → partial payment, ostatak CASH
    # T-22: Negativni iznos plaćanja → ValidationError
    # T-23: Plaćanje > total → change_given = razlika
    # T-24: Kartica s 0.00 EUR → ne može platiti
```

### Klasa 5: Fiskalizacija routing
```python
class TestFiscalizationRouting(POSTestBase):
    # T-25: company.country='HR', fiscal_exempt=False → FINA put
    # T-26: company.fiscal_exempt=True → bypass (ZKI/JIR prazni)
    # T-27: company.fiscal_system='de_gobd' → TSE put (mock TSE)
    # T-28: company.country='DE' → TSE put (mock TSE)
    # T-29: FINA pada (mock exception) → bon ostaje paid, error logiran
    # T-30: TSE pada → bon ostaje paid, tse_error popunjen
    # T-31: fiscal_retry_count raste na svakom failu (max 3)
```

### Klasa 6: Offline sync
```python
class TestOfflineSync(POSTestBase):
    # T-32: Bon kreiran s client_ip='offline' → status=open, fiscal=pending
    # T-33: sync_offline_receipts() → fiskalizira zaostale bonove
    # T-34: Bon fiskaliziran → fiscal_retry_count=0, jir popunjen
    # T-35: Bon koji već ima JIR → preskočen u syncu
```

### Klasa 7: Z-izvješće i zatvaranje smjene
```python
class TestZReport(POSTestBase):
    # T-36: Z-report na praznoj smjeni → 0 EUR, 0 bonova
    # T-37: Z-report s 5 bonova → točna suma
    # T-38: Z-report s storniranim bonovima → stornirani NE ulaze u zbrojeve
    # T-39: Zatvaranje smjene s otvorenim bonovima → SessionError
    # T-40: Zatvaranje smjene → status=closed, closed_at postavljeno
    # T-41: POSDailyReport kreiran pri zatvaranju → generate_from_session()
```

### Klasa 8: Storno i povrat
```python
class TestStornoRefund(POSTestBase):
    # T-42: Storno plaćenog bona → status=cancelled, zaliha vraćena
    # T-43: Storno otvorenog bona → status=cancelled
    # T-44: Storno dva puta → drugi storno baca error
    # T-45: Povrat (refund) → novi bon s negativnim iznosima
    # T-46: Povrat djelomičan → samo jedna stavka vraćena
```

### Klasa 9: Performansni testovi
```python
class TestPerformance(POSTestBase):
    # T-47: 50 bonova za < 5s (bulk create)
    # T-48: 100 add_item operacija na jednoj smjeni za < 3s
    # T-49: Z-report s 200 bonova generira se za < 2s
    # T-50: Pretraga artikala (300 artikala) za < 500ms
```

## Format svakog testa
```python
def test_XX_naziv(self):
    # ARRANGE
    ...
    # ACT
    ...
    # ASSERT
    self.assertEqual(...)
    # Kratki komentar što testiramo
```

## Pokretanje na kraju
```bash
cd /var/www/fina-connect
venv/bin/python manage.py test pos.tests.test_brutal --verbosity=2 2>&1 | tee /tmp/brutal_results.txt
echo "=== SUMMARY ==="
tail -10 /tmp/brutal_results.txt
```

## Što javljaš
- Broj PASS / FAIL
- Svaki FAIL s točnim traceback-om
- Ukupno trajanje

## PRAVILA
1. ČITAJ modele prije pisanja — ne pretpostavljaj polja
2. Svaki test mora biti izoliran (TestCase = rollback)
3. Mock FINA i TSE pozive — ne šalji pravi zahtjev
4. Ako test otkrije pravi bug — zabilježi ga kao komentar, ne popravljaj
5. django check mora biti 0 issues na kraju
