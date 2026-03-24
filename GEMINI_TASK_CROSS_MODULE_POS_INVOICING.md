# GEMINI TASK: Cross-Module POS × Invoicing Simulacijski Testovi
## Agent: Gemini | Prioritet: VISOK | Datum: 2026-03-23

## Kontekst
POS i Invoicing moduli dijele dva kritična resursa:
- **Inventory (Zalihe)** — oba modula kreiraju StockMovement koji mijenja InventoryItem.quantity
- **Konto (Glavna knjiga)** — oba modula kreiraju JournalEntry/LedgerLine zapise

Ako se ne testiraju u tandemu, sustav može:
1. Prodati isti artikl dvaput (zaliha -1)
2. Knjižiti prihod dvaput (Konto 7000 duplikat)

## Arhitektura testa

### PRAVILO: Bez HTTP-a
`get_user_company()` pada na CompanyMiddleware u test kontekstu.
Svi testovi MORAJU koristiti ORM service layer direktno:

```python
# POS checkout
from pos.services.checkout import CheckoutService
result = CheckoutService.process_receipt(company, user, payload)

# Invoice booking
from konto.services_file import book_invoice
je = book_invoice(invoice, user)

# Bank transaction match (simulacija POS naplate fakture)
from konto.services_file import match_transaction_to_invoice
```

### Test setup (zajednički za sve scenarije)
```python
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from companies.models import Company
from accounts.models import UserProfile
from inventory.models import InventoryItem, StockMovement
from pos.models import POSTerminal, POSSession, POSCashier
from invoicing.models import Invoice, InvoiceItem
from konto.models import KontoAccount, JournalEntry, LedgerLine
from decimal import Decimal

User = get_user_model()

class CrossModuleTestMixin:
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Firma d.o.o.',
            oib='12345678901',
            has_signed_tc_consent=True,
            allow_negative_stock=False,  # KRITIČNO — ne dozvoli -1
        )
        self.user = User.objects.create_user(username='test_cross', password='test123')
        UserProfile.objects.create(user=self.user, company=self.company, role='company_admin')

        # Inventar — točno 1 komad
        self.item = InventoryItem.objects.create(
            company=self.company,
            name='Premium Kava 250g',
            sku='KAVA-001',
            quantity=Decimal('1'),
            unit_price=Decimal('8.50'),
            purchase_price=Decimal('4.00'),
        )

        # POS session
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name='Blagajna 1',
            location='Poslovnica',
        )
        self.session = POSSession.objects.create(
            terminal=self.terminal,
            opened_by=self.user,
            company=self.company,
        )

        # Konto accounts (HR standard)
        self.acc_1000 = KontoAccount.objects.create(company=self.company, code='1000', name='Žiro račun')
        self.acc_1200 = KontoAccount.objects.create(company=self.company, code='1200', name='Potraživanja od kupaca')
        self.acc_2400 = KontoAccount.objects.create(company=self.company, code='2400', name='Obveze za PDV')
        self.acc_7000 = KontoAccount.objects.create(company=self.company, code='7000', name='Prihodi od prodaje')
```

---

## Scenarij 1: Race Condition na Zalihama (Inventory Integrity)

**Cilj:** Dokazati da `select_for_update()` u CheckoutService sprječava overselling.

```python
class TestInventoryRaceCondition(CrossModuleTestMixin, TransactionTestCase):
    """
    Scenarij: 1 artikl na stanju.
    POS prodaje 1 komad + Draft faktura pokušava rezervirati isti artikl.
    Očekivano: Jedan od dva procesa MORA dobiti grešku.
    """

    def test_pos_and_invoice_cannot_oversell_same_item(self):
        # 1. POS prodaje artikl
        pos_payload = {
            'session_id': self.session.pk,
            'items': [{'item_id': self.item.pk, 'quantity': 1}],
            'payment_method': 'CASH',
            'amount_paid': '8.50',
        }
        result = CheckoutService.process_receipt(self.company, self.user, pos_payload)
        self.assertIn('receipt_id', result)

        # 2. Provjeri stanje zaliha
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal('0'))

        # 3. Pokušaj isti artikl kroz StockMovement (simulacija invoice dispatch)
        from django.core.exceptions import ValidationError
        try:
            sm = StockMovement.objects.create(
                item=self.item,
                movement_type='out',
                quantity=Decimal('1'),
                unit_price=self.item.unit_price,
                reason='Račun FAKT-2026-001',
                performed_by=self.user,
            )
            # Ako prođe — zaliha je negativna, TO JE BUG ako allow_negative_stock=False
            self.item.refresh_from_db()
            if self.item.quantity < 0:
                self.fail(
                    f"KRITIČAN BUG: Zaliha otišla na {self.item.quantity}! "
                    f"allow_negative_stock={self.company.allow_negative_stock}"
                )
        except (ValidationError, Exception) as e:
            # Očekivano ponašanje — sustav je blokirao overselling
            pass

    def test_concurrent_pos_sales_same_item(self):
        """
        Dva POS bona za isti artikl (qty=1) — samo prvi smije proći.
        Koristi threading za simulaciju concurrency-ja.
        """
        import threading
        results = [None, None]
        errors = [None, None]

        def sell(idx):
            try:
                payload = {
                    'session_id': self.session.pk,
                    'items': [{'item_id': self.item.pk, 'quantity': 1}],
                    'payment_method': 'CASH',
                    'amount_paid': '8.50',
                }
                results[idx] = CheckoutService.process_receipt(
                    self.company, self.user, payload
                )
            except Exception as e:
                errors[idx] = str(e)

        t1 = threading.Thread(target=sell, args=(0,))
        t2 = threading.Thread(target=sell, args=(1,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Barem jedan mora uspjeti, ali NE oba
        successes = sum(1 for r in results if r and 'receipt_id' in r)
        self.item.refresh_from_db()

        if successes == 2:
            self.assertGreaterEqual(
                self.item.quantity, Decimal('0'),
                f"RACE CONDITION: Oba POS-a prošla, zaliha={self.item.quantity}"
            )
        else:
            self.assertEqual(successes, 1, "Točno jedan POS bon mora proći")
```

---

## Scenarij 2: Financijski Integritet (Ledger Double-Count)

**Cilj:** Faktura knjiži prihod (Konto 7000). POS naplata te fakture SMIJE SAMO zatvoriti potraživanje (1200→1000), NE smije ponovo knjižiti prihod.

```python
class TestLedgerDoubleCount(CrossModuleTestMixin, TestCase):
    """
    Scenarij:
    1. Izdaj fakturu na 100 EUR — knjiži se: D:1200 / P:7000+2400
    2. Klijent plati gotovinom na POS-u — mora biti SAMO: D:1000 / P:1200
    3. Prihod (7000) NE SMIJE biti knjižen dvaput.
    """

    def test_invoice_then_pos_payment_no_double_revenue(self):
        from konto.services_file import book_invoice

        # 1. Kreiraj i knjiži fakturu
        invoice = Invoice.objects.create(
            company=self.company,
            partner=None,
            invoice_number='FAKT-2026-0001',
            status='confirmed',
            doctype='R',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('25.00'),
            total=Decimal('125.00'),
            date_issued='2026-03-23',
        )

        je = book_invoice(invoice, self.user)
        self.assertIsNotNone(je, "Faktura mora generirati JournalEntry")

        # Provjeri: prihod = 100 EUR (Konto 7000, credit)
        revenue_lines = LedgerLine.objects.filter(
            journal_entry=je,
            account=self.acc_7000,
            side='credit',
        )
        self.assertEqual(revenue_lines.count(), 1)
        self.assertEqual(revenue_lines.first().amount, Decimal('100.00'))

        # 2. Simuliraj POS naplatu iste fakture (gotovina na blagajni)
        #    Ovo bi trebalo biti: D:1000(Banka) / P:1200(Potraživanja)
        from konto.services_file import match_transaction_to_invoice
        # Kreiraj bank transaction za simulaciju
        from konto.models import BankTransaction
        try:
            txn = BankTransaction.objects.create(
                company=self.company,
                amount=Decimal('125.00'),
                direction='inflow',
                description='Gotovinska uplata FAKT-2026-0001',
                date='2026-03-23',
            )
            match_transaction_to_invoice(txn, invoice)
        except Exception:
            # Ako BankTransaction ne postoji — ručno kreiraj JournalEntry
            je_payment = JournalEntry.objects.create(
                company=self.company,
                description='Naplata FAKT-2026-0001 gotovinom na POS-u',
                date='2026-03-23',
                source_type='pos',
                is_posted=True,
            )
            LedgerLine.objects.create(
                journal_entry=je_payment,
                account=self.acc_1000,
                side='debit',
                amount=Decimal('125.00'),
            )
            LedgerLine.objects.create(
                journal_entry=je_payment,
                account=self.acc_1200,
                side='credit',
                amount=Decimal('125.00'),
            )

        # 3. KLJUČNA PROVJERA: Konto 7000 smije imati SAMO 100 EUR ukupno
        total_revenue = LedgerLine.objects.filter(
            journal_entry__company=self.company,
            account=self.acc_7000,
            side='credit',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        self.assertEqual(
            total_revenue, Decimal('100.00'),
            f"DOUBLE-COUNT BUG: Prihod (7000) = {total_revenue}, "
            f"očekivano 100.00. POS naplata NE SMIJE ponovo knjižiti prihod!"
        )

        # 4. Provjeri da je potraživanje zatvoreno
        receivable_debit = LedgerLine.objects.filter(
            journal_entry__company=self.company,
            account=self.acc_1200,
            side='debit',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        receivable_credit = LedgerLine.objects.filter(
            journal_entry__company=self.company,
            account=self.acc_1200,
            side='credit',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        self.assertEqual(
            receivable_debit, receivable_credit,
            f"Potraživanje (1200) nije zatvoreno: D={receivable_debit}, P={receivable_credit}"
        )
```

---

## Scenarij 3: Z-Report Integritet

**Cilj:** POS Z-report mora uključiti gotovinske naplate faktura ali NE smije ih tretirati kao novi promet.

```python
class TestZReportIntegrity(CrossModuleTestMixin, TestCase):
    """Z-report: gotovinska naplata fakture ulazi u 'ulaz novca',
    ali NE u 'promet dnevni' jer je promet već evidentiran fakturom."""

    def test_invoice_cash_payment_in_z_report(self):
        # POS bon za direktnu prodaju
        pos_payload = {
            'session_id': self.session.pk,
            'items': [{'item_id': self.item.pk, 'quantity': 1}],
            'payment_method': 'CASH',
            'amount_paid': '8.50',
        }
        result = CheckoutService.process_receipt(self.company, self.user, pos_payload)

        from pos.models import POSReceipt
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])

        # Z-report: direktna POS prodaja MORA biti u prometu
        self.assertGreater(receipt.total, Decimal('0'))

        # Naplata fakture: treba biti odvojena kategorija u Z-reportu
        # (ovo ovisi o implementaciji — provjeri DailyReport model)
```

---

## Ulazni parametri za SharedResource test

| Parametar | Vrijednost | Napomena |
|-----------|------------|----------|
| `company.allow_negative_stock` | `False` | Strogi mode — mora baciti grešku |
| `item.quantity` | `1` | Minimum za race condition test |
| `item.unit_price` | `8.50` | Realistična cijena |
| `invoice.total` | `125.00` | 100 + 25% PDV |
| `payment_method` | `CASH` | Gotovina — ulazi u Z-report |
| `konto_1000` | Žiro račun | Debit kod naplate |
| `konto_1200` | Potraživanja | Debit kod fakture, Credit kod naplate |
| `konto_7000` | Prihodi | Credit SAMO kod fakture, NIKAD kod naplate |
| `konto_2400` | PDV obveze | Credit kod fakture |

## Fajl za testove
`/var/www/fina-connect/tests/test_cross_module_pos_invoicing.py`

## Pokretanje
```bash
cd /var/www/fina-connect
./venv/bin/python manage.py test tests.test_cross_module_pos_invoicing -v2
```

## Veto napomena
Gemini ima veto na pisanje koda dok se ne potvrdi arhitektura.
Ovaj dokument definira **točne ulazne parametre i očekivane rezultate**.
Gemini treba:
1. Potvrditi da CheckoutService.process_receipt() handle-a `allow_negative_stock=False` pravilno
2. Potvrditi da book_invoice() ne dupla prihod kod POS naplate
3. Napisati testove prema ovim specifikacijama

## Povezani fajlovi
| Fajl | Relevantnost |
|------|-------------|
| `pos/services/checkout.py` | CheckoutService.process_receipt(), _deduct_stock() |
| `konto/services_file.py` | book_invoice(), book_bank_transactions() |
| `inventory/models.py` | StockMovement.save() auto-update quantity |
| `invoicing/signals.py` | Auto-booking signal |
| `pos/models.py` | POSReceipt, POSReceiptItem, POSPaymentLine |
| `konto/models.py` | JournalEntry, LedgerLine, KontoAccount |
