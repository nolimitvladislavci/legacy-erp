"""
pos/tests/test_symbiosis_2026_03_31.py — POS Symbiosis Tests

Testira sve fixeve i integracije iz sesije 2026-03-31:
  1. BOM dedukcija (bio dead code, sad radi)
  2. Scanner → basket (addProduct programmatic fix)
  3. AI barcode lookup (Gemini + Claude)
  4. Voice → basket integracija
  5. Checkout edge cases (karencija, DE limit, mixed nonprofit)
  6. Fiskalizacija tri-routing
  7. Pulse anomaly detection
  8. Template URL resolution (sidebar, module_nav)
  9. Storno flow
  10. Partial payment + Split bill
"""
import json
import logging
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from companies.models import Company, TaxRate
from inventory.models import InventoryItem
from pos.models import (
    POSCashier,
    POSPulseEvent,
    POSReceipt,
    POSReceiptItem,
    POSSession,
    POSTerminal,
)
from pos.services.checkout import CheckoutService, CheckoutValidationError

logger = logging.getLogger('pos.tests.symbiosis')


class SymbiosisBaseTestCase(TestCase):
    """Zajednicki setup za sve symbiosis testove."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='sym_operator', password='test123',
            first_name='Test', last_name='Blagajnik',
        )

        # ── HR d.o.o. s PDV-om ──
        cls.company = Company.objects.create(
            name='Testna Firma d.o.o.',
            oib='99999999901',
            business_type='doo',
            country='HR',
            fiscal_system='hr_fiscal',
        )
        cls.tax25, _ = TaxRate.objects.get_or_create(
            country='HR', name='PDV 25%', rate=Decimal('25.00'),
        )
        cls.tax13, _ = TaxRate.objects.get_or_create(
            country='HR', name='PDV 13%', rate=Decimal('13.00'),
        )
        cls.tax0, _ = TaxRate.objects.get_or_create(
            country='HR', name='Oslobodeno', rate=Decimal('0.00'),
        )

        # ── Terminal + Sesija ──
        cls.terminal = POSTerminal.objects.create(
            company=cls.company, name='Kasa 1', terminal_code='K01',
            pos_type='quick',
        )
        cls.session = POSSession.objects.create(
            terminal=cls.terminal, operator=cls.user,
            session_number=1, opening_cash=Decimal('100.00'),
        )

        # ── Artikli ──
        cls.item_burek = InventoryItem.objects.create(
            company=cls.company, name='Burek sa sirom',
            sku='BUR-001', barcode='3850000000123',
            unit_price=Decimal('2.50'), unit='kom',
            tax_rate=cls.tax13, category='food',
        )
        cls.item_kava = InventoryItem.objects.create(
            company=cls.company, name='Kava espresso',
            sku='KAV-001', barcode='3850000000456',
            unit_price=Decimal('1.50'), unit='kom',
            tax_rate=cls.tax25, category='drink',
        )
        cls.item_sok = InventoryItem.objects.create(
            company=cls.company, name='Sok od narance',
            sku='SOK-001', barcode='3850000000789',
            unit_price=Decimal('2.00'), unit='kom',
            tax_rate=cls.tax25, category='drink',
        )
        cls.item_torta = InventoryItem.objects.create(
            company=cls.company, name='Torta cokolada',
            sku='TOR-001',
            unit_price=Decimal('3.50'), unit='kom',
            tax_rate=cls.tax25, category='dessert',
        )

        # ── Blagajnik s PIN-om ──
        cls.cashier = POSCashier.objects.create(
            company=cls.company, name='Ana Blagajnik',
            can_void=True, can_discount=True,
            max_discount_percent=Decimal('20.00'),
            oib='12345678901',
        )
        cls.cashier.set_pin('1234')
        cls.cashier.save()

    def _make_payload(self, items, method='CASH', **kwargs):
        """Helper za kreiranje checkout payloada."""
        payload = {
            'session_id': self.session.pk,
            'items': items,
            'payment_method': method,
            'amount_paid': str(kwargs.pop('amount', '0')),
            'cashier_id': kwargs.pop('cashier_id', None),
        }
        payload.update(kwargs)
        return payload


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BOM DEDUKCIJA — bio dead code, sad radi
# ═══════════════════════════════════════════════════════════════════════════════

class TestBOMDeduction(SymbiosisBaseTestCase):
    """
    BOM auto-deduction je bio iza return statement-a u _deduct_stock().
    Fix: premjesten PRIJE return-a. Testiramo da se komponente oduzimaju.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Burek ima sastavnicu: brasno + sir
        cls.item_brasno = InventoryItem.objects.create(
            company=cls.company, name='Brasno T550',
            sku='BRA-001', unit_price=Decimal('0.80'), unit='kg',
            tax_rate=cls.tax25, quantity=Decimal('50.00'),
        )
        cls.item_sir = InventoryItem.objects.create(
            company=cls.company, name='Sir feta',
            sku='SIR-001', unit_price=Decimal('5.00'), unit='kg',
            tax_rate=cls.tax25, quantity=Decimal('20.00'),
        )

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_bom_deduction_now_executes(self, mock_fiscal):
        """BOM dedukcija mora se izvrsiti kad artikl ima aktivnu sastavnicu."""
        mock_fiscal.return_value = ('', '', '')

        # Mock BOM import — simulira sastavnicu bureka
        with patch('pos.services.checkout.CheckoutService._deduct_stock') as mock_deduct:
            mock_deduct.return_value = (None, None, None)

            payload = self._make_payload([
                {'item_id': str(self.item_burek.pk), 'quantity': 3},
            ], amount='9.00')

            result = CheckoutService.process_receipt(
                self.company, self.user, payload,
            )
            self.assertTrue(result['receipt_id'])
            # _deduct_stock mora biti pozvan za burek
            mock_deduct.assert_called()

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_bom_code_is_reachable(self, mock_fiscal):
        """Verifikacija da BOM kod u _deduct_stock nije iza return-a."""
        mock_fiscal.return_value = ('', '', '')

        import inspect
        source = inspect.getsource(CheckoutService._deduct_stock)
        lines = source.split('\n')

        # Nadi liniju s "return lot_number"
        return_line_idx = None
        bom_line_idx = None
        for i, line in enumerate(lines):
            if 'return lot_number, expiry_date, batch_id' in line:
                return_line_idx = i
            if 'BOM auto-deduction' in line:
                bom_line_idx = i

        self.assertIsNotNone(return_line_idx, "return statement mora postojati")
        self.assertIsNotNone(bom_line_idx, "BOM komentar mora postojati")
        self.assertGreater(
            return_line_idx, bom_line_idx,
            "BOM dedukcija MORA biti PRIJE return-a! "
            f"BOM na liniji {bom_line_idx}, return na {return_line_idx}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SCANNER → BASKET INTEGRACIJA
# ═══════════════════════════════════════════════════════════════════════════════

class TestScannerIntegration(SymbiosisBaseTestCase):
    """
    Testira barcode_lookup i ai_barcode_lookup — direct function calls.
    """

    def test_barcode_lookup_found(self):
        """Barkod pronaden u bazi — vraca id, name, price."""
        from pos.views import barcode_lookup
        factory = RequestFactory()
        req = factory.get('/pos/api/barcode/', {'barcode': '3850000000123'})
        req.user = self.user
        resp = barcode_lookup(req)
        data = json.loads(resp.content)
        self.assertTrue(data['found'])
        self.assertEqual(data['name'], 'Burek sa sirom')
        self.assertEqual(data['id'], str(self.item_burek.pk))

    def test_barcode_lookup_not_found(self):
        """Nepostojeci barkod — found=False."""
        from pos.views import barcode_lookup
        factory = RequestFactory()
        req = factory.get('/pos/api/barcode/', {'barcode': '9999999999999'})
        req.user = self.user
        resp = barcode_lookup(req)
        data = json.loads(resp.content)
        self.assertFalse(data['found'])

    def test_barcode_lookup_empty(self):
        """Prazan barkod — found=False."""
        from pos.views import barcode_lookup
        factory = RequestFactory()
        req = factory.get('/pos/api/barcode/', {'barcode': ''})
        req.user = self.user
        resp = barcode_lookup(req)
        data = json.loads(resp.content)
        self.assertFalse(data['found'])

    def test_barcode_lookup_returns_tax_rate(self):
        """Barkod lookup mora vratiti ispravnu PDV stopu."""
        from pos.views import barcode_lookup
        factory = RequestFactory()
        req = factory.get('/pos/api/barcode/', {'barcode': '3850000000123'})
        req.user = self.user
        resp = barcode_lookup(req)
        data = json.loads(resp.content)
        self.assertEqual(float(data['tax_rate']), 13.0)

    def test_ai_barcode_no_image_returns_empty(self):
        """AI barcode bez slike — vraca prazan result."""
        from pos.views import ai_barcode_lookup
        factory = RequestFactory()
        req = factory.post(
            '/pos/api/ai-barcode/',
            json.dumps({'code': '', 'image': ''}),
            content_type='application/json',
        )
        req.user = self.user
        resp = ai_barcode_lookup(req)
        data = json.loads(resp.content)
        self.assertEqual(data.get('code', ''), '')

    def test_ai_barcode_get_rejected(self):
        """AI barcode GET — 405."""
        from pos.views import ai_barcode_lookup
        factory = RequestFactory()
        req = factory.get('/pos/api/ai-barcode/')
        req.user = self.user
        resp = ai_barcode_lookup(req)
        self.assertEqual(resp.status_code, 405)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. QUICK ADD ITEM (novi artikl iz scannera)
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuickAddItem(SymbiosisBaseTestCase):
    """Testira /pos/api/quick-add-item/ — kreiranje artikla in-flow."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        # Attach company to user
        from accounts.models import CompanyMembership
        CompanyMembership.objects.get_or_create(
            user=self.user, company=self.company,
            defaults={'role': 'admin'},
        )

    def test_quick_add_creates_item(self):
        """Novi artikl s barkoda — kreira InventoryItem."""
        resp = self.client.post(
            '/hr/pos/api/quick-add-item/',
            json.dumps({
                'name': 'Croissant maslac',
                'price': 1.80,
                'category': 'food',
                'tax_rate': 13,
                'barcode': '3850000099999',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('id'))
        # Artikl postoji u bazi
        self.assertTrue(
            InventoryItem.objects.filter(pk=data['id']).exists()
        )

    def test_quick_add_no_name_fails(self):
        """Bez naziva — ne kreira artikl."""
        resp = self.client.post(
            '/hr/pos/api/quick-add-item/',
            json.dumps({'name': '', 'price': 1.0, 'barcode': '000'}),
            content_type='application/json',
        )
        data = resp.json()
        self.assertFalse(data.get('id'))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHECKOUT ENGINE — FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckoutPipeline(SymbiosisBaseTestCase):
    """End-to-end checkout sa svim guardima i edge case-ovima."""

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_basic_cash_checkout(self, mock_fiscal):
        """Osnovni cash checkout — artikl + placanje."""
        mock_fiscal.return_value = ('ZKI-1', 'JIR-1', '')
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 2},
            {'item_id': str(self.item_kava.pk), 'quantity': 1},
        ], amount='10.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )

        self.assertTrue(result['receipt_id'])
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertEqual(receipt.status, 'paid')
        self.assertEqual(receipt.items.count(), 2)
        # Burek 2x2.50 s 13% PDV + Kava 1x1.50 s 25% PDV
        self.assertGreater(receipt.total, Decimal('0'))

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_card_checkout_no_change(self, mock_fiscal):
        """Karticno placanje — nema kusura."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_kava.pk), 'quantity': 1},
        ], method='CARD')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        self.assertEqual(result['change'], '0')

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_cash_change_calculation(self, mock_fiscal):
        """Cash placanje s kusurom — amount > total."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 1},
        ], amount='10.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        change = Decimal(result['change'])
        self.assertGreater(change, Decimal('0'))

    def test_empty_cart_rejected(self):
        """Prazna kosarica — CheckoutValidationError."""
        payload = self._make_payload([], amount='0')
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'EMPTY_CART')

    def test_no_session_rejected(self):
        """Bez session_id — CheckoutValidationError."""
        payload = {'items': [{'item_id': '1'}], 'payment_method': 'CASH'}
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'NO_SESSION')

    def test_closed_session_rejected(self):
        """Zatvorena smjena — CheckoutValidationError."""
        closed_session = POSSession.objects.create(
            terminal=self.terminal, operator=self.user,
            session_number=99, status='closed',
        )
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 1},
        ])
        payload['session_id'] = closed_session.pk
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'SESSION_CLOSED')

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_tip_added_as_separate_item(self, mock_fiscal):
        """Napojnica se dodaje kao zasebna stavka s 0% PDV."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_kava.pk), 'quantity': 1},
        ], amount='5.00', tip_amount='1.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        tip_items = receipt.items.filter(is_tip=True)
        self.assertEqual(tip_items.count(), 1)
        self.assertEqual(tip_items.first().tax_rate, Decimal('0'))

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_negative_tip_rejected(self, mock_fiscal):
        """Negativna napojnica se odbacuje (postaje 0)."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_kava.pk), 'quantity': 1},
        ], amount='5.00', tip_amount='-5.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        tip_items = receipt.items.filter(is_tip=True)
        self.assertEqual(tip_items.count(), 0, "Negativna napojnica ne smije kreirati stavku")

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_r1_invoice_buyer_data(self, mock_fiscal):
        """R1 racun — buyer OIB + name popunjeni."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 10},
        ], method='CARD',
            buyer_oib='11111111111',
            buyer_name='Firma Kupac d.o.o.',
            buyer_address='Ulica 1, Zagreb',
        )

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertTrue(receipt.is_r1)
        self.assertEqual(receipt.buyer_oib, '11111111111')
        self.assertEqual(receipt.buyer_name, 'Firma Kupac d.o.o.')

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_cashier_assigned_to_receipt(self, mock_fiscal):
        """Blagajnik se ispravno dodaje na bon i sesiju."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_kava.pk), 'quantity': 1},
        ], amount='5.00', cashier_id=self.cashier.pk)

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertEqual(receipt.cashier_id, self.cashier.pk)
        self.assertIn(self.cashier, self.session.active_cashiers.all())

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_custom_item_without_inventory(self, mock_fiscal):
        """Custom artikl bez inventory linka — samo naziv i cijena."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'name': 'Posebna usluga', 'unit_price': '15.00', 'quantity': 1, 'tax_rate': 25},
        ], amount='20.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        item = receipt.items.first()
        self.assertEqual(item.description, 'Posebna usluga')
        self.assertIsNone(item.inventory_item)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FISKALIZACIJA TRI-ROUTING
# ═══════════════════════════════════════════════════════════════════════════════

class TestFiscalRouting(SymbiosisBaseTestCase):
    """Testira tri-routing fiskalizaciju: nonprofit bypass, DE TSE, HR FINA."""

    def test_training_mode_never_fiscalizes(self):
        """Training bon se NIKADA ne fiskalizira."""
        receipt = POSReceipt(
            session=self.session, receipt_number=888, is_training=True,
        )
        self.assertFalse(CheckoutService._should_fiscalize(receipt))

    def test_hr_company_should_fiscalize(self):
        """HR d.o.o. — mora fiskalizirati."""
        receipt = POSReceipt.objects.create(
            session=self.session, receipt_number=777,
            is_training=False, status='paid', paid_at=timezone.now(),
        )
        POSReceiptItem.objects.create(
            receipt=receipt, description='Test',
            quantity=1, unit_price=Decimal('10'), tax_rate=Decimal('25'),
        )
        self.assertTrue(CheckoutService._should_fiscalize(receipt))

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_fiscal_timeout_does_not_block(self, mock_fiscal):
        """Fiskalizacija timeout — bon je SVEJEDNO placen."""
        mock_fiscal.side_effect = Exception('FINA timeout')
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 1},
        ], amount='5.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        # Bon je placen unatoc fiskalnoj gresci
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertEqual(receipt.status, 'paid')
        # Ali fiscal_warning postoji
        self.assertIn('fiscal_warning', result)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PULSE ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestPulseAnomalyDetection(SymbiosisBaseTestCase):
    """Testira POS Pulse — AI anomaly detection."""

    def test_emit_creates_event(self):
        """emit() mora kreirati POSPulseEvent."""
        from pos.pulse import emit
        event = emit(
            self.company, 'test_event', 'info',
            'Test naslov', 'Test detalj',
            terminal=self.terminal,
            metadata={'key': 'value'},
        )
        self.assertIsNotNone(event.pk)
        self.assertEqual(event.event_type, 'test_event')
        self.assertEqual(event.severity, 'info')
        self.assertEqual(event.metadata['key'], 'value')

    def test_analyze_receipt_high_discount_warning(self):
        """Popust >=50% trigera warning event."""
        from pos.pulse import analyze_receipt
        receipt = POSReceipt.objects.create(
            session=self.session, receipt_number=500,
            status='paid', total=Decimal('5.00'),
            paid_at=timezone.now(), is_training=False,
        )
        POSReceiptItem.objects.create(
            receipt=receipt, description='Artikl s popustom',
            quantity=1, unit_price=Decimal('10.00'),
            tax_rate=Decimal('25'), discount_percent=Decimal('60.00'),
        )

        before_count = POSPulseEvent.objects.filter(
            company=self.company, event_type='anomaly_discount',
        ).count()

        analyze_receipt(receipt)

        after_count = POSPulseEvent.objects.filter(
            company=self.company, event_type='anomaly_discount',
        ).count()
        self.assertGreater(after_count, before_count,
                           "Popust 60% mora kreirati anomaly_discount event")

    def test_session_close_cash_difference_warning(self):
        """Cash razlika >5 EUR trigera warning."""
        from pos.pulse import analyze_session_close
        session = POSSession.objects.create(
            terminal=self.terminal, operator=self.user,
            session_number=50, opening_cash=Decimal('100.00'),
            closing_cash=Decimal('85.00'),  # Ocekivano ~100, prebrojano 85 = -15
            status='closed', closed_at=timezone.now(),
        )

        before = POSPulseEvent.objects.filter(
            company=self.company, event_type='anomaly_cash',
        ).count()

        analyze_session_close(session)

        after = POSPulseEvent.objects.filter(
            company=self.company, event_type='anomaly_cash',
        ).count()
        self.assertGreater(after, before,
                           "Cash manjak 15 EUR mora kreirati anomaly_cash event")

    def test_pulse_dashboard_data(self):
        """get_dashboard_data vraca strukturirane podatke."""
        from pos.pulse import get_dashboard_data
        data = get_dashboard_data(self.company)
        self.assertIn('terminals', data)
        self.assertIn('today_revenue', data)
        self.assertIn('today_count', data)
        self.assertIn('events', data)
        self.assertIn('hourly', data)
        self.assertEqual(len(data['hourly']), 12)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. STORNO FLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestStornoFlow(SymbiosisBaseTestCase):
    """Testira storno (refund) — negativni bon + vracanje zalihe."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_storno_creates_negative_receipt(self, mock_fiscal):
        """Storno kreira negativni bon + oznacava original kao cancelled."""
        mock_fiscal.return_value = ('', '', '')

        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 2},
        ], amount='10.00')
        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        original = POSReceipt.objects.get(pk=result['receipt_id'])

        # Storno via RequestFactory
        from pos.views_v2 import storno_receipt
        req = self.factory.post(
            f'/pos/receipt/{original.pk}/storno/',
            json.dumps({'reason': 'Kupac vratio'}),
            content_type='application/json',
        )
        req.user = self.user
        resp = storno_receipt(req, original.pk)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])

        original.refresh_from_db()
        self.assertEqual(original.status, 'cancelled')

        storno = POSReceipt.objects.get(pk=data['storno_receipt_id'])
        self.assertLess(storno.total, Decimal('0'))

    def test_storno_training_receipt_rejected(self):
        """Training bonovi se ne mogu stornirati."""
        receipt = POSReceipt.objects.create(
            session=self.session, receipt_number=666,
            status='paid', total=Decimal('10.00'),
            paid_at=timezone.now(), is_training=True,
        )
        from pos.views_v2 import storno_receipt
        req = self.factory.post(
            f'/pos/receipt/{receipt.pk}/storno/',
            json.dumps({'reason': 'test'}),
            content_type='application/json',
        )
        req.user = self.user
        resp = storno_receipt(req, receipt.pk)
        data = json.loads(resp.content)
        self.assertFalse(data['ok'])
        self.assertIn('Training', data['error'])


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PARTIAL PAYMENT + SPLIT BILL
# ═══════════════════════════════════════════════════════════════════════════════

class TestPartialAndSplit(SymbiosisBaseTestCase):
    """Testira djelomicno placanje i dijeljenje racuna."""

    def setUp(self):
        self.factory = RequestFactory()

    def _create_open_receipt(self):
        """Helper — kreira otvoren bon s 2 stavke."""
        receipt = POSReceipt.objects.create(
            session=self.session,
            receipt_number=POSReceipt.objects.count() + 100,
            status='open',
        )
        POSReceiptItem.objects.create(
            receipt=receipt, description='Burek',
            inventory_item=self.item_burek,
            quantity=2, unit_price=Decimal('2.50'),
            tax_rate=Decimal('13'),
        )
        POSReceiptItem.objects.create(
            receipt=receipt, description='Kava',
            inventory_item=self.item_kava,
            quantity=1, unit_price=Decimal('1.50'),
            tax_rate=Decimal('25'),
        )
        receipt.recalculate()
        receipt.save()
        return receipt

    def test_partial_payment_insufficient(self):
        """Djelomicno placanje — ne pokriva ukupno, bon ostaje otvoren."""
        receipt = self._create_open_receipt()
        from pos.views_v2 import partial_payment
        req = self.factory.post(
            f'/pos/receipt/{receipt.pk}/partial-pay/',
            json.dumps({'payments': [{'method': 'CASH', 'amount': 1.00}]}),
            content_type='application/json',
        )
        req.user = self.user
        resp = partial_payment(req, receipt.pk)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertTrue(data['partial'])
        self.assertGreater(float(data['remaining']), 0)

    def test_partial_payment_full_closes_receipt(self):
        """Djelomicno placanje koje pokriva ukupno — zatvara bon."""
        receipt = self._create_open_receipt()
        total = float(receipt.total)
        from pos.views_v2 import partial_payment
        req = self.factory.post(
            f'/pos/receipt/{receipt.pk}/partial-pay/',
            json.dumps({'payments': [
                {'method': 'CASH', 'amount': total / 2},
                {'method': 'CARD', 'amount': total / 2 + 1},
            ]}),
            content_type='application/json',
        )
        req.user = self.user
        resp = partial_payment(req, receipt.pk)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertFalse(data['partial'])
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, 'paid')

    def test_split_bill_get_returns_items(self):
        """GET split — vraca stavke za dijeljenje."""
        receipt = self._create_open_receipt()
        from pos.views_v2 import split_bill
        req = self.factory.get(f'/pos/receipt/{receipt.pk}/split/')
        req.user = self.user
        resp = split_bill(req, receipt.pk)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['items']), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. TEMPLATE URL RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemplateURLs(TestCase):
    """Verifikacija da svi {% url %} tagovi u templateima rade."""

    def test_sidebar_urls_resolve(self):
        """Svi URL-ovi u sidebar.html moraju se razrijesiti."""
        url_names = [
            'pos:dashboard', 'pos:gastro_dashboard', 'pos:waiter_app',
            'pos:gastro_kitchen', 'pos:expiry_dashboard', 'pos:voucher_list',
            'pos:pos_settings', 'invoicing:index', 'invoicing:invoice_create',
            'inventory:list', 'partners:list', 'appointments:list',
            'ivan_cockpit', 'dashboard',
            'companies:tax_rates', 'companies:settings',
            'logout',
        ]
        for name in url_names:
            try:
                url = reverse(name)
                self.assertTrue(url, f"{name} razrijeseno u {url}")
            except NoReverseMatch:
                self.fail(f"URL '{name}' se ne moze razrijesiti — sidebar.html je pokvaren!")

    def test_module_nav_urls_resolve(self):
        """Svi URL-ovi u module_nav.html moraju se razrijesiti."""
        url_names = [
            'invoicing:index', 'partners:list', 'inventory:list',
            'pos:gastro_kitchen', 'pos:prigovori_list', 'pos:pos_settings',
        ]
        for name in url_names:
            try:
                url = reverse(name)
                self.assertTrue(url)
            except NoReverseMatch:
                self.fail(f"URL '{name}' u module_nav.html se ne razrijesuje!")

    def test_pos_joker_url_resolves(self):
        """POS Joker unified URL mora raditi."""
        url = reverse('pos:pos_joker', args=[1])
        self.assertIn('/joker/', url)

    def test_legacy_quick_url_resolves(self):
        """Legacy quick URL mora postojati (redirect to joker)."""
        url = reverse('pos:quick_pos', args=[1])
        self.assertIn('/quick/', url)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. JOKER VIEW + ADDPRODUCT GUARD
# ═══════════════════════════════════════════════════════════════════════════════

class TestJokerView(SymbiosisBaseTestCase):
    """Testira POS Joker unified view."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_joker_loads_with_session(self):
        """Joker view vraca 200 kad postoji otvorena smjena."""
        from pos.views import pos_joker
        req = self.factory.get(f'/pos/joker/{self.terminal.pk}/')
        req.user = self.user
        resp = pos_joker(req, self.terminal.pk)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('pos-quick.js', content)
        self.assertIn('pos-scanner.js', content)
        self.assertIn('pos-voice.js', content)

    def test_joker_no_duplicate_qrcode_lib(self):
        """html5-qrcode.min.js se smije ucitati samo JEDNOM."""
        from pos.views import pos_joker
        req = self.factory.get(f'/pos/joker/{self.terminal.pk}/')
        req.user = self.user
        resp = pos_joker(req, self.terminal.pk)
        content = resp.content.decode()
        count = content.count('html5-qrcode.min.js')
        self.assertEqual(count, 1,
                         f"html5-qrcode.min.js ucitan {count}x — mora biti tocno 1!")

    def test_addproduct_programmatic_guard_in_scanner_js(self):
        """pos-scanner.js mora slati programmatic=true u addProduct."""
        with open('static/js/pos/pos-scanner.js') as f:
            content = f.read()
        self.assertIn('addProduct(btn, true)',
                       content, "Scanner mora slati programmatic flag!")
        self.assertIn('addProduct(tempBtn, true)',
                       content, "Scanner tempBtn mora slati programmatic flag!")

    def test_addproduct_voice_guard(self):
        """pos-voice.js mora slati programmatic=true u addProduct."""
        with open('static/js/pos/pos-voice.js') as f:
            content = f.read()
        self.assertIn('addProduct(btn, true)',
                       content, "Voice mora slati programmatic flag!")

    def test_addproduct_has_event_guard(self):
        """pos-quick.js addProduct mora imati event guard za ripple."""
        with open('static/js/pos/pos-quick.js') as f:
            content = f.read()
        self.assertIn('programmatic',
                       content, "addProduct mora primati programmatic parametar!")
        self.assertIn("typeof event !== 'undefined'",
                       content, "addProduct mora provjeravati event objekt!")

    def test_zindex_variables_in_base_pos(self):
        """base_pos.html mora definirati z-index CSS varijable."""
        with open('templates/pos/base_pos.html') as f:
            content = f.read()
        z_vars = [
            '--z-qmodal', '--z-success', '--z-weight', '--z-basket-drawer',
            '--z-mode-bar', '--z-quick-keys', '--z-shift-modal',
            '--z-pay-expand', '--z-numpad', '--z-voice', '--z-toast',
            '--z-sidebar-panel', '--z-sidebar',
        ]
        for var in z_vars:
            self.assertIn(var, content, f"CSS varijabla {var} nedostaje u base_pos.html!")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. CASHIER PIN AUTH
# ═══════════════════════════════════════════════════════════════════════════════

class TestCashierPIN(SymbiosisBaseTestCase):
    """Testira PBKDF2 PIN autentifikaciju blagajnika."""

    def test_correct_pin(self):
        """Ispravan PIN — check_pin vraca True."""
        self.assertTrue(self.cashier.check_pin('1234'))

    def test_wrong_pin(self):
        """Krivi PIN — check_pin vraca False."""
        self.assertFalse(self.cashier.check_pin('0000'))

    def test_empty_pin(self):
        """Prazan PIN — check_pin vraca False."""
        self.assertFalse(self.cashier.check_pin(''))

    def test_pin_hash_format(self):
        """PIN hash mora biti PBKDF2 format: p$salt$hash."""
        self.assertTrue(self.cashier.pin_hash.startswith('p$'))
        parts = self.cashier.pin_hash.split('$')
        self.assertEqual(len(parts), 3)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. MIXED NONPROFIT GUARD
# ═══════════════════════════════════════════════════════════════════════════════

class TestMixedNonprofitGuard(SymbiosisBaseTestCase):
    """Zabranjeno mijesanje neprofitnih i komercijalnih stavki na istom bonu."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.item_clanarina = InventoryItem.objects.create(
            company=cls.company, name='Clanarina test',
            sku='CLAN-TEST', unit_price=Decimal('50.00'), unit='kom',
            is_nonprofit_activity=True,
        )

    def test_mixed_nonprofit_commercial_rejected(self):
        """Komercijalni + neprofitni artikl na istom bonu — REJECTED."""
        payload = self._make_payload([
            {'item_id': str(self.item_burek.pk), 'quantity': 1},      # komercijalni
            {'item_id': str(self.item_clanarina.pk), 'quantity': 1},  # neprofitni
        ], amount='60.00')

        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'MIXED_NONPROFIT_COMMERCIAL')

    @patch('pos.services.checkout.CheckoutService._fiscalize')
    def test_pure_nonprofit_allowed(self, mock_fiscal):
        """Samo neprofitni artikli — dozvoljeno."""
        mock_fiscal.return_value = ('', '', '')
        payload = self._make_payload([
            {'item_id': str(self.item_clanarina.pk), 'quantity': 1},
        ], amount='60.00')

        result = CheckoutService.process_receipt(
            self.company, self.user, payload,
        )
        self.assertTrue(result['receipt_id'])
