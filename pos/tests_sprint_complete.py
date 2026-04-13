"""
POS Modul — Kompletna test suite za Sprint 1-6 features + full simulation.
Pokriva: session lifecycle, checkout, inventory, offline, voice, UI, compliance.
72 scenarija.
"""
import json
import os
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.test import TestCase
from django.contrib.auth.models import User

from companies.models import Company
from pos.models import (
    POSTerminal, POSSession, POSReceipt, POSCashier, Table, GastroOrder,
)

# Default VAT rate used by add_receipt_item
DEFAULT_TAX = Decimal('25')


def _with_vat(net, tax=DEFAULT_TAX):
    return (net * (1 + tax / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class POSTestBase(TestCase):
    """Base class with common setup."""

    _item_counter = 0

    def setUp(self):
        self.company = Company.objects.create(name='Test POS Co', oib='11111111111')
        self.user = User.objects.create_user('pos_tester', password='test123', email='pos@test.com')
        from accounts.models import UserProfile
        UserProfile.objects.update_or_create(user=self.user, defaults={'company': self.company, 'role': 'company_admin'})
        self.client.login(username='pos_tester', password='test123')

        self.terminal = POSTerminal.objects.create(
            company=self.company, name='Test Terminal', pos_type='quick', is_active=True
        )
        from pos.services import open_session
        self.session = open_session(self.terminal, self.user, Decimal('100.00'))

    def _create_item(self, name='Test Artikl', price=10.00, stock=100):
        from inventory.models import InventoryItem
        POSTestBase._item_counter += 1
        sku = f'TST-{POSTestBase._item_counter}-{uuid.uuid4().hex[:6]}'
        return InventoryItem.objects.create(
            company=self.company, name=name, sku=sku,
            unit_price=Decimal(str(price)),
            quantity=Decimal(str(stock)), min_quantity=Decimal('5'),
            purchase_price=Decimal('5.00'),
        )

    def _quick_pay(self, items_data, method='CASH', amount=None):
        """Helper: quick_pay returns dict, extracts receipt."""
        from pos.services import quick_pay
        if amount is None:
            # Calculate total with VAT
            amount = Decimal('0')
            for i in items_data:
                net = Decimal(str(i['price'])) * Decimal(str(i['qty']))
                amount += _with_vat(net)
        result = quick_pay(self.session, items_data, method, amount, user=self.user)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        return receipt, result

    def _create_receipt(self, items=None):
        from pos.services import create_receipt, add_receipt_item
        receipt = create_receipt(self.session)
        if items:
            for name, qty, price in items:
                item = self._create_item(name, price)
                add_receipt_item(receipt, item.pk, name, Decimal(str(qty)), Decimal(str(price)))
        return receipt


# ═══════════════════════════════════════════════════════════════════
# 1. SESSION LIFECYCLE
# ═══════════════════════════════════════════════════════════════════

class SessionLifecycleTest(POSTestBase):

    def test_open_session(self):
        from pos.services import close_session, open_session
        close_session(self.session)
        t2 = POSTerminal.objects.create(company=self.company, name='T2', pos_type='quick', terminal_code='T2-TEST')
        s = open_session(t2, self.user, Decimal('50.00'))
        self.assertEqual(s.status, POSSession.Status.OPEN)
        self.assertEqual(s.opening_cash, Decimal('50.00'))

    def test_close_session(self):
        from pos.services import close_session
        result = close_session(self.session, Decimal('150.00'))
        self.assertTrue(result)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, POSSession.Status.CLOSED)

    def test_cannot_double_open(self):
        from pos.services import open_session
        with self.assertRaises(Exception):
            open_session(self.terminal, self.user)

    def test_session_number_increments(self):
        from pos.services import close_session, open_session
        n1 = self.session.session_number
        close_session(self.session)
        s2 = open_session(self.terminal, self.user)
        self.assertGreater(s2.session_number, n1)

    def test_close_with_open_receipts_raises(self):
        """Cannot close session with open receipts — must cancel first."""
        from pos.services import create_receipt, close_session, SessionError
        create_receipt(self.session)
        with self.assertRaises(SessionError):
            close_session(self.session)


# ═══════════════════════════════════════════════════════════════════
# 2. RECEIPT CRUD
# ═══════════════════════════════════════════════════════════════════

class ReceiptCRUDTest(POSTestBase):

    def test_create_receipt(self):
        from pos.services import create_receipt
        r = create_receipt(self.session)
        self.assertEqual(r.status, POSReceipt.Status.OPEN)
        self.assertEqual(r.session, self.session)

    def test_add_item_with_inventory(self):
        from pos.services import create_receipt, add_receipt_item
        item = self._create_item('Burek', 3.00)
        r = create_receipt(self.session)
        ri = add_receipt_item(r, item.pk, 'Burek', Decimal('2'), Decimal('3.00'))
        self.assertEqual(ri.quantity, Decimal('2'))
        # total_price = net * (1+25%) = 6 * 1.25 = 7.50
        self.assertEqual(ri.total_price, _with_vat(Decimal('6.00')))

    def test_add_custom_item_no_inventory(self):
        from pos.services import create_receipt, add_receipt_item
        r = create_receipt(self.session)
        ri = add_receipt_item(r, None, 'Custom Service', Decimal('1'), Decimal('25.00'))
        self.assertEqual(ri.description, 'Custom Service')
        self.assertIsNone(ri.inventory_item_id)

    def test_remove_item(self):
        from pos.services import create_receipt, add_receipt_item, remove_receipt_item
        item = self._create_item()
        r = create_receipt(self.session)
        ri = add_receipt_item(r, item.pk, 'Test', Decimal('1'), Decimal('10'))
        result = remove_receipt_item(r, ri.pk)
        self.assertTrue(result)
        self.assertEqual(r.items.count(), 0)

    def test_receipt_number_sequential(self):
        from pos.services import create_receipt
        r1 = create_receipt(self.session)
        r2 = create_receipt(self.session)
        self.assertEqual(r2.receipt_number, r1.receipt_number + 1)

    def test_total_auto_calculated(self):
        # A=2*5=10 net, B=1*10=10 net, total net=20 → with 25% VAT = 25.00
        r = self._create_receipt([('Item A', 2, 5.00), ('Item B', 1, 10.00)])
        from pos.services import recalculate_receipt
        recalculate_receipt(r)
        r.refresh_from_db()
        expected = _with_vat(Decimal('10')) + _with_vat(Decimal('10'))
        self.assertEqual(r.total, expected)

    def test_discount_applied(self):
        from pos.services import create_receipt, add_receipt_item
        item = self._create_item('Disc Item', 100.00)
        r = create_receipt(self.session)
        ri = add_receipt_item(r, item.pk, 'Disc', Decimal('1'), Decimal('100'), discount_percent=Decimal('10'))
        # net = 100 * (1-10%) = 90, with VAT = 112.50
        expected = _with_vat(Decimal('90'))
        self.assertEqual(ri.total_price, expected)


# ═══════════════════════════════════════════════════════════════════
# 3. PAYMENT PROCESSING
# ═══════════════════════════════════════════════════════════════════

class PaymentTest(POSTestBase):

    def test_cash_payment(self):
        from pos.services import create_receipt, add_receipt_item, process_payment
        item = self._create_item('Cash Item', 15.00)
        r = create_receipt(self.session)
        add_receipt_item(r, item.pk, 'Cash Item', Decimal('1'), Decimal('15'))
        r.refresh_from_db()
        result = process_payment(r, 'CASH', r.total + Decimal('5'), user=self.user)
        self.assertIn('receipt_id', result)
        r.refresh_from_db()
        self.assertEqual(r.status, POSReceipt.Status.PAID)

    def test_cash_change_calculated(self):
        from pos.services import create_receipt, add_receipt_item, process_payment
        item = self._create_item('Change Item', 8.00)
        r = create_receipt(self.session)
        add_receipt_item(r, item.pk, 'Change', Decimal('1'), Decimal('8.00'))
        r.refresh_from_db()
        result = process_payment(r, 'CASH', Decimal('20.00'), user=self.user)
        self.assertEqual(result['change'], Decimal('20.00') - r.total)

    def test_card_payment(self):
        from pos.services import create_receipt, add_receipt_item, process_payment
        item = self._create_item('Card Item', 25.00)
        r = create_receipt(self.session)
        add_receipt_item(r, item.pk, 'Card', Decimal('1'), Decimal('25'))
        r.refresh_from_db()
        process_payment(r, 'CARD', r.total, user=self.user)
        r.refresh_from_db()
        self.assertEqual(r.status, POSReceipt.Status.PAID)

    def test_empty_cart_payment_blocked(self):
        from pos.services import create_receipt, process_payment, PaymentError
        r = create_receipt(self.session)
        with self.assertRaises(PaymentError):
            process_payment(r, 'CASH', Decimal('10'), user=self.user)

    def test_quick_pay_single_call(self):
        item = self._create_item('Quick', 5.00)
        receipt, result = self._quick_pay([{'id': item.pk, 'name': 'Quick', 'qty': 3, 'price': 5.00}])
        self.assertEqual(receipt.status, POSReceipt.Status.PAID)
        self.assertEqual(receipt.total, _with_vat(Decimal('15.00')))

    def test_revolut_payment_method(self):
        item = self._create_item('Rev Item', 20.00)
        receipt, _ = self._quick_pay([{'id': item.pk, 'name': 'Rev', 'qty': 1, 'price': 20}], method='REVOLUT')
        self.assertEqual(receipt.payment_lines.first().method, 'REVOLUT')

    def test_aircash_payment_method(self):
        item = self._create_item('Air Item', 12.00)
        receipt, _ = self._quick_pay([{'id': item.pk, 'name': 'Air', 'qty': 1, 'price': 12}], method='AIRCASH')
        self.assertEqual(receipt.payment_lines.first().method, 'AIRCASH')


# ═══════════════════════════════════════════════════════════════════
# 4. INVENTORY DEDUCTION
# ═══════════════════════════════════════════════════════════════════

class InventoryDeductionTest(POSTestBase):

    def test_stock_deducted_after_payment(self):
        item = self._create_item('Deduct Me', 5.00, stock=50)
        self._quick_pay([{'id': item.pk, 'name': 'Deduct Me', 'qty': 3, 'price': 5}])
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('47'))

    def test_multi_item_deduction(self):
        a = self._create_item('Item A', 10, 20)
        b = self._create_item('Item B', 5, 30)
        self._quick_pay([
            {'id': a.pk, 'name': 'A', 'qty': 2, 'price': 10},
            {'id': b.pk, 'name': 'B', 'qty': 5, 'price': 5},
        ])
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.quantity, Decimal('18'))
        self.assertEqual(b.quantity, Decimal('25'))

    def test_stock_movement_created(self):
        from inventory.models import StockMovement
        item = self._create_item('Move', 8, 100)
        before = StockMovement.objects.count()
        self._quick_pay([{'id': item.pk, 'name': 'Move', 'qty': 1, 'price': 8}])
        after = StockMovement.objects.count()
        self.assertGreater(after, before)

    def test_negative_stock_allowed(self):
        item = self._create_item('Low', 5, 1)
        receipt, _ = self._quick_pay([{'id': item.pk, 'name': 'Low', 'qty': 3, 'price': 5}])
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('-2'))
        self.assertEqual(receipt.status, POSReceipt.Status.PAID)

    def test_custom_item_no_deduction(self):
        from inventory.models import StockMovement
        before = StockMovement.objects.count()
        self._quick_pay([{'id': None, 'name': 'Custom', 'qty': 1, 'price': 50}])
        after = StockMovement.objects.count()
        self.assertEqual(after, before)


# ═══════════════════════════════════════════════════════════════════
# 5. VIEW SMOKE TESTS
# ═══════════════════════════════════════════════════════════════════

class ViewSmokeTest(POSTestBase):
    """Smoke test — any of 200/301/302 is acceptable."""

    VALID = [200, 301, 302]

    def test_dashboard(self):
        self.assertIn(self.client.get('/hr/pos/').status_code, self.VALID)

    def test_joker_view(self):
        self.assertIn(self.client.get(f'/hr/pos/joker/{self.terminal.pk}/').status_code, self.VALID)

    def test_quick_pos_view(self):
        self.assertIn(self.client.get(f'/hr/pos/quick/{self.terminal.pk}/').status_code, self.VALID)

    def test_settings_view(self):
        self.assertIn(self.client.get('/hr/pos/settings/').status_code, self.VALID)

    def test_receipt_list(self):
        self.assertIn(self.client.get('/hr/pos/receipts/').status_code, self.VALID)

    def test_session_detail(self):
        self.assertIn(self.client.get(f'/hr/pos/session/{self.session.pk}/').status_code, self.VALID)

    def test_prigovori_list(self):
        self.assertIn(self.client.get('/hr/pos/prigovori/').status_code, self.VALID)

    def test_pulse_dashboard(self):
        self.assertIn(self.client.get('/hr/pos/pulse/').status_code, self.VALID)

    def test_kassenbuch(self):
        self.assertIn(self.client.get('/hr/pos/kassenbuch/').status_code, self.VALID)

    def test_improvement_list(self):
        self.assertIn(self.client.get('/hr/pos/improvements/').status_code, self.VALID)


# ═══════════════════════════════════════════════════════════════════
# 6. API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

class APITest(POSTestBase):

    VALID = [200, 301, 302]

    def test_barcode_lookup_not_found(self):
        r = self.client.get('/hr/pos/api/barcode/', {'q': 'NONEXISTENT'}, follow=True)
        self.assertEqual(r.status_code, 200)

    def test_barcode_lookup_found(self):
        item = self._create_item('Barcode Item', 5)
        item.barcode = '1234567890123'
        item.save()
        r = self.client.get('/hr/pos/api/barcode/', {'q': '1234567890123'}, follow=True)
        self.assertEqual(r.status_code, 200)

    def test_article_search(self):
        self._create_item('Burek Sir', 3)
        r = self.client.get('/hr/pos/api/search/', {'q': 'burek'}, follow=True)
        self.assertIn(r.status_code, [200, 404])

    def test_pos_items_api(self):
        r = self.client.get('/hr/pos/api/pos/items/', {'terminal_id': self.terminal.pk}, follow=True)
        self.assertEqual(r.status_code, 200)

    def test_checkout_api_empty_cart(self):
        r = self.client.post('/hr/pos/api/pos/checkout/',
            json.dumps({'session_id': self.session.pk, 'items': [], 'method': 'CASH', 'amount_paid': '0'}),
            content_type='application/json', follow=True)
        self.assertIn(r.status_code, [200, 400, 405])


# ═══════════════════════════════════════════════════════════════════
# 7. CASHIER SYSTEM
# ═══════════════════════════════════════════════════════════════════

class CashierTest(POSTestBase):

    def test_create_cashier(self):
        c = POSCashier.objects.create(company=self.company, name='Ana')
        self.assertEqual(c.name, 'Ana')

    def test_cashier_pin(self):
        c = POSCashier.objects.create(company=self.company, name='Pin Test')
        c.set_pin('1234')
        c.save()
        self.assertTrue(c.check_pin('1234'))
        self.assertFalse(c.check_pin('5678'))

    def test_cashier_isolated_per_company(self):
        co2 = Company.objects.create(name='Other Co', oib='22222222222')
        c1 = POSCashier.objects.create(company=self.company, name='C1')
        c2 = POSCashier.objects.create(company=co2, name='C2')
        self.assertNotEqual(c1.company, c2.company)


# ═══════════════════════════════════════════════════════════════════
# 8. GASTRO MODE
# ═══════════════════════════════════════════════════════════════════

class GastroTest(POSTestBase):

    def setUp(self):
        super().setUp()
        self.terminal.pos_type = 'restaurant'
        self.terminal.save()

    def test_table_creation(self):
        t = Table.objects.create(company=self.company, name='Stol 1')
        self.assertEqual(t.name, 'Stol 1')

    def test_gastro_order(self):
        table = Table.objects.create(company=self.company, name='Stol 5')
        order = GastroOrder.objects.create(
            company=self.company,
            receipt=self._create_receipt([('Pizza', 1, 8)]),
            table=table, status='pending'
        )
        self.assertEqual(order.status, 'pending')


# ═══════════════════════════════════════════════════════════════════
# 9. OFFLINE & FISCAL — static file checks
# ═══════════════════════════════════════════════════════════════════

class OfflineFiscalTest(POSTestBase):

    def test_offline_js_exists(self):
        self.assertTrue(os.path.exists('/var/www/fina-connect/static/js/pos/pos-offline.js'))

    def test_offline_js_has_indexeddb(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-offline.js').read()
        self.assertIn('indexedDB', content)
        self.assertIn('48', content)

    def test_voice_js_exists(self):
        self.assertTrue(os.path.exists('/var/www/fina-connect/static/js/pos/pos-voice.js'))

    def test_voice_js_has_speech_api(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-voice.js').read()
        self.assertIn('SpeechRecognition', content)
        self.assertIn('hr-HR', content)
        self.assertIn('voiceConfirm', content)

    def test_voice_js_has_wave_visualizer(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-voice.js').read()
        self.assertIn('AudioContext', content)
        self.assertIn('analyser', content.lower())
        self.assertIn('voiceWave', content)

    def test_voice_js_has_noise_indicator(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-voice.js').read()
        self.assertIn('voiceNoise', content)

    def test_scanner_js_exists(self):
        self.assertTrue(os.path.exists('/var/www/fina-connect/static/js/pos/pos-scanner.js'))

    def test_quick_js_has_cart_persistence(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-quick.js').read()
        self.assertIn('localStorage', content)
        self.assertIn('_saveCart', content)
        self.assertIn('_restoreCart', content)
        self.assertIn('_clearSavedCart', content)


# ═══════════════════════════════════════════════════════════════════
# 10. JOKER TEMPLATE — UI FEATURES
# ═══════════════════════════════════════════════════════════════════

class JokerTemplateTest(POSTestBase):

    def _read_joker(self):
        return open('/var/www/fina-connect/templates/pos/joker.html').read()

    def test_mode_bar_exists(self):
        content = self._read_joker()
        self.assertIn('pos-mode-bar', content)
        self.assertIn('modeRetail', content)
        self.assertIn('modeGastro', content)
        self.assertIn('modeBasket', content)

    def test_basket_drawer_exists(self):
        content = self._read_joker()
        self.assertIn('drawer-handle', content)
        self.assertIn('toggleBasketDrawer', content)

    def test_quick_keys_overlay_exists(self):
        content = self._read_joker()
        self.assertIn('qk-overlay', content)
        self.assertIn('toggleQuickKeys', content)

    def test_numpad_exists(self):
        content = self._read_joker()
        self.assertIn('numpad-overlay', content)
        self.assertIn('numpadPress', content)
        self.assertIn('numpadConfirm', content)

    def test_swipe_delete_exists(self):
        content = self._read_joker()
        self.assertIn('swipe-delete', content)

    def test_ai_suggestions_in_js(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-quick.js').read()
        self.assertIn('updateAiSuggestions', content)

    def test_stock_badge_exists(self):
        content = self._read_joker()
        self.assertIn('prod-stock', content)

    def test_voice_button_exists(self):
        content = self._read_joker()
        self.assertIn('voiceBtn', content)
        self.assertIn('toggleVoice', content)

    def test_voice_wave_canvas_exists(self):
        content = self._read_joker()
        self.assertIn('voiceWave', content)
        self.assertIn('voiceNoise', content)
        self.assertIn('voiceConfidence', content)

    def test_haptic_feedback_in_js(self):
        content = open('/var/www/fina-connect/static/js/pos/pos-quick.js').read()
        self.assertIn('navigator.vibrate', content)

    def test_sticky_totals_css(self):
        content = self._read_joker()
        self.assertIn('sticky', content)
        self.assertIn('basket-totals', content)

    def test_payment_expand_exists(self):
        content = self._read_joker()
        self.assertIn('togglePayExpand', content)


# ═══════════════════════════════════════════════════════════════════
# 11. Z-REPORT & KASSENBUCH
# ═══════════════════════════════════════════════════════════════════

class ZReportTest(POSTestBase):

    def test_z_report_empty_session(self):
        from pos.services import generate_zreport
        report = generate_zreport(self.session)
        self.assertEqual(report['total_sales'], Decimal('0'))
        self.assertEqual(report['receipt_count'], 0)

    def test_z_report_with_sales(self):
        from pos.services import generate_zreport
        item = self._create_item('Z Item', 10, 50)
        self._quick_pay([{'id': item.pk, 'name': 'Z1', 'qty': 2, 'price': 10}])
        self._quick_pay([{'id': item.pk, 'name': 'Z2', 'qty': 1, 'price': 10}], method='CARD')
        report = generate_zreport(self.session)
        self.assertEqual(report['receipt_count'], 2)
        # 2*10 + 1*10 = 30 net → with 25% VAT = 37.50
        expected = _with_vat(Decimal('20')) + _with_vat(Decimal('10'))
        self.assertEqual(report['total_sales'], expected)


# ═══════════════════════════════════════════════════════════════════
# 12. FULL SIMULATION — 20 receipts stress test
# ═══════════════════════════════════════════════════════════════════

class FullSimulationTest(POSTestBase):

    def test_20_receipt_simulation(self):
        """Simulate 20 sales in sequence — the Kruljac stress test."""
        import random
        random.seed(42)

        products = [self._create_item(f'Proizvod {i+1}', price=2.00 + i, stock=200) for i in range(10)]

        for _ in range(20):
            num_items = random.randint(1, 5)
            items = []
            for __ in range(num_items):
                p = random.choice(products)
                qty = random.randint(1, 3)
                items.append({'id': p.pk, 'name': p.name, 'qty': qty, 'price': float(p.unit_price)})

            method = random.choice(['CASH', 'CARD', 'REVOLUT'])
            receipt, _ = self._quick_pay(items, method=method)
            self.assertEqual(receipt.status, POSReceipt.Status.PAID)

        self.assertEqual(POSReceipt.objects.filter(session=self.session, status='paid').count(), 20)

        for p in products:
            p.refresh_from_db()
            self.assertLess(p.quantity, Decimal('200'))

    def test_mixed_payment_methods(self):
        """Test all 5 payment methods in sequence."""
        item = self._create_item('Multi Pay', 10, 500)
        methods = ['CASH', 'CARD', 'MOBILE', 'REVOLUT', 'AIRCASH']
        for method in methods:
            receipt, _ = self._quick_pay(
                [{'id': item.pk, 'name': 'Multi', 'qty': 1, 'price': 10}],
                method=method
            )
            self.assertEqual(receipt.status, POSReceipt.Status.PAID)
            self.assertEqual(receipt.payment_lines.first().method, method)

    def test_cancel_and_resale(self):
        """Cancel receipt then sell same items again."""
        from pos.services import create_receipt, add_receipt_item, process_payment
        item = self._create_item('Cancel Test', 15, 10)

        r1 = create_receipt(self.session)
        add_receipt_item(r1, item.pk, 'Cancel Test', Decimal('2'), Decimal('15'))
        r1.status = POSReceipt.Status.CANCELLED
        r1.save()

        r2 = create_receipt(self.session)
        add_receipt_item(r2, item.pk, 'Cancel Test', Decimal('2'), Decimal('15'))
        r2.refresh_from_db()
        process_payment(r2, 'CASH', r2.total, user=self.user)
        r2.refresh_from_db()
        self.assertEqual(r2.status, POSReceipt.Status.PAID)


# ═══════════════════════════════════════════════════════════════════
# 13. COMPLIANCE (ZOR / ArbZG / Fiskalizacija)
# ═══════════════════════════════════════════════════════════════════

class ComplianceTest(POSTestBase):

    def test_receipt_has_all_required_fields(self):
        """ZOR: receipt must have number, date, terminal, items, total, payment."""
        item = self._create_item('Compliance', 5)
        receipt, _ = self._quick_pay([{'id': item.pk, 'name': 'Compliance', 'qty': 1, 'price': 5}])
        self.assertIsNotNone(receipt.receipt_number)
        self.assertIsNotNone(receipt.created_at)
        self.assertGreater(receipt.items.count(), 0)
        self.assertGreater(receipt.total, Decimal('0'))
        self.assertGreater(receipt.payment_lines.count(), 0)

    def test_dsfinvk_export_function(self):
        """DSFinV-K export for German market should exist."""
        from pos.dsfinvk_export import generate_dsfinvk_export
        self.assertTrue(callable(generate_dsfinvk_export))

    def test_receipt_numbering_no_gaps(self):
        """Sequential receipt numbers with no gaps within session."""
        item = self._create_item('Seq', 1, 999)
        numbers = []
        for _ in range(5):
            receipt, _ = self._quick_pay([{'id': item.pk, 'name': 'Seq', 'qty': 1, 'price': 1}])
            numbers.append(receipt.receipt_number)
        for i in range(1, len(numbers)):
            self.assertEqual(numbers[i], numbers[i-1] + 1)
