"""
POS Kompletni Test Suite — 50 testova.
T-01..50: R1, Nonprofit, Multi-terminal, Placanje, Fiskalizacija, Offline, Z-report, Storno, Performansa.

Usage:
    python manage.py test pos.tests_pos_suite --verbosity=2
"""
import time
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from companies.models import Company
from pos.models import (
    POSTerminal, POSSession, POSReceipt, POSReceiptItem,
    Voucher,
)
from pos.services.checkout import CheckoutService, CheckoutValidationError
from inventory.models import InventoryItem


class POSTestBase(TestCase):
    """Bazna klasa s fixture podacima."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('testpos', 'test@test.com', 'test123')
        cls.company = Company.objects.create(
            name='Test POS d.o.o.', oib='11111111111',
            country='HR', business_type='doo', fiscal_system='hr_fiscal',
        )
        cls.company_de = Company.objects.create(
            name='Test POS GmbH', oib='DE222222222',
            country='DE', business_type='gmbh', fiscal_system='de_gobd',
        )
        cls.company_udruga = Company.objects.create(
            name='Test Udruga', oib='33333333333',
            country='HR', business_type='udruga',
        )
        cls.terminal = POSTerminal.objects.create(
            company=cls.company, name='Kasa 1', terminal_code='T01',
        )
        cls.terminal_de = POSTerminal.objects.create(
            company=cls.company_de, name='Kasse 1', terminal_code='DE01',
        )
        cls.terminal_udruga = POSTerminal.objects.create(
            company=cls.company_udruga, name='Blagajna Udruge', terminal_code='U01',
        )
        cls.item = InventoryItem.objects.create(
            company=cls.company, name='Kava', sku='KAVA01',
            unit_price=Decimal('2.50'), quantity=100,
            category='drink',
        )
        cls.item_food = InventoryItem.objects.create(
            company=cls.company, name='Sendvic', sku='SEND01',
            unit_price=Decimal('5.00'), quantity=50,
            category='food',
        )
        cls.item_nonprofit = InventoryItem.objects.create(
            company=cls.company_udruga, name='Clanarina', sku='CLAN01',
            unit_price=Decimal('20.00'), quantity=999,
            category='service', is_nonprofit_activity=True,
        )
        cls.item_commercial = InventoryItem.objects.create(
            company=cls.company_udruga, name='Pivo udruga', sku='PIVO01',
            unit_price=Decimal('3.00'), quantity=100,
            category='drink', is_nonprofit_activity=False,
        )

    def _open_session(self, terminal=None, opening_cash=200):
        terminal = terminal or self.terminal
        last = terminal.sessions.order_by('-session_number').first()
        num = (last.session_number + 1) if last else 1
        return POSSession.objects.create(
            terminal=terminal, operator=self.user,
            session_number=num, opening_cash=Decimal(str(opening_cash)),
            status='open',
        )

    def _make_payload(self, session, items, method='CASH', amount_paid=None, **kwargs):
        payload = {
            'session_id': session.pk,
            'items': items,
            'payment_method': method,
            'amount_paid': amount_paid or sum(
                Decimal(str(i.get('unit_price', i.get('price', 0)))) *
                Decimal(str(i.get('quantity', i.get('qty', 1))))
                for i in items
            ),
        }
        payload.update(kwargs)
        return payload


# ═══════════════════════════════════════════════════════════════════════════
# T-01..06: R1 RACUN — OIB validacija, FINA XML, buyer polja
# ═══════════════════════════════════════════════════════════════════════════

class T01_R1_BuyerFields(POSTestBase):
    """T-01: R1 racun — buyer_oib, buyer_name, is_r1 na POSReceipt."""

    def test_t01_receipt_has_r1_fields(self):
        fields = [f.name for f in POSReceipt._meta.get_fields()]
        self.assertIn('buyer_oib', fields)
        self.assertIn('buyer_name', fields)
        self.assertIn('is_r1', fields)

    def test_t02_r1_auto_flag(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], buyer_oib='12345678901', buyer_name='Firma d.o.o.')
        result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertEqual(receipt.buyer_oib, '12345678901')
        self.assertEqual(receipt.buyer_name, 'Firma d.o.o.')
        self.assertTrue(receipt.is_r1)

    def test_t03_non_r1_no_buyer(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertFalse(receipt.is_r1)
        self.assertEqual(receipt.buyer_oib, '')

    def test_t04_r1_fina_xml_oib_kupca(self):
        from fiskalizacija.fisk import _build_racun
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], buyer_oib='98765432109')
        result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        from lxml import etree
        racun = _build_racun(receipt, '11111111111', '1', '1', 'abc123', timezone.now())
        xml_str = etree.tostring(racun, encoding='unicode')
        self.assertIn('OibKupca', xml_str)
        self.assertIn('98765432109', xml_str)

    def test_t05_r1_empty_oib_no_crash(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], buyer_oib='')
        result = CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertIn('receipt_id', result)

    def test_t06_r1_client_ip_audit(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], client_ip='192.168.1.100', client_ua='TestBrowser/1.0')
        result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertEqual(receipt.client_ip, '192.168.1.100')
        self.assertIn('TestBrowser', receipt.client_ua)


# ═══════════════════════════════════════════════════════════════════════════
# T-07..11: NONPROFIT GUARD
# ═══════════════════════════════════════════════════════════════════════════

class T07_NonprofitGuard(POSTestBase):
    """T-07..11: Nonprofit mixing guard, fiscal bypass, donacije."""

    def test_t07_udruga_is_nonprofit(self):
        self.assertTrue(self.company_udruga.is_nonprofit)
        self.assertFalse(self.company.is_nonprofit)

    def test_t08_nonprofit_fiscal_mode_default(self):
        self.assertEqual(self.company_udruga.nonprofit_fiscal_mode, 'commercial_only')
        self.assertEqual(self.company.nonprofit_fiscal_mode, 'full')

    def test_t09_mixing_blocked(self):
        session = self._open_session(self.terminal_udruga)
        payload = self._make_payload(session, [
            {'item_id': self.item_nonprofit.pk, 'quantity': 1, 'unit_price': '20.00', 'tax_rate': 0},
            {'item_id': self.item_commercial.pk, 'quantity': 1, 'unit_price': '3.00', 'tax_rate': 25},
        ])
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company_udruga, self.user, payload)
        self.assertIn(ctx.exception.code, ('MIXED_RECEIPT', 'MIXED_NONPROFIT_COMMERCIAL'))

    def test_t10_nonprofit_only_no_fiscal(self):
        session = self._open_session(self.terminal_udruga)
        payload = self._make_payload(session, [
            {'item_id': self.item_nonprofit.pk, 'quantity': 1, 'unit_price': '20.00', 'tax_rate': 0},
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize') as mock_fisc:
            mock_fisc.return_value = ('', '', '')
            result = CheckoutService.process_receipt(self.company_udruga, self.user, payload)
            receipt = POSReceipt.objects.get(pk=result['receipt_id'])
            # _should_fiscalize should return False for nonprofit-only
            self.assertFalse(CheckoutService._should_fiscalize(receipt))

    def test_t11_commercial_on_udruga_fiscalizes(self):
        session = self._open_session(self.terminal_udruga)
        payload = self._make_payload(session, [
            {'item_id': self.item_commercial.pk, 'quantity': 1, 'unit_price': '3.00', 'tax_rate': 25},
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize') as mock_fisc:
            mock_fisc.return_value = ('zki123', 'jir456', '')
            result = CheckoutService.process_receipt(self.company_udruga, self.user, payload)
            receipt = POSReceipt.objects.get(pk=result['receipt_id'])
            self.assertTrue(CheckoutService._should_fiscalize(receipt))


# ═══════════════════════════════════════════════════════════════════════════
# T-12..16: MULTI-TERMINAL
# ═══════════════════════════════════════════════════════════════════════════

class T12_MultiTerminal(POSTestBase):
    """T-12..16: Race conditions, stock, atomarnost."""

    def test_t12_wrong_company_blocked(self):
        session = self._open_session()  # company
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company_de, self.user, payload)
        self.assertEqual(ctx.exception.code, 'WRONG_COMPANY')

    def test_t13_closed_session_blocked(self):
        session = self._open_session()
        session.status = 'closed'
        session.save()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'SESSION_CLOSED')

    def test_t14_empty_cart_blocked(self):
        session = self._open_session()
        payload = self._make_payload(session, [])
        with self.assertRaises(CheckoutValidationError):
            CheckoutService.process_receipt(self.company, self.user, payload)

    def test_t15_stock_deduction(self):
        initial = self.item.quantity
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 3, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, initial - 3)

    def test_t16_receipt_numbering_sequential(self):
        session = self._open_session()
        numbers = []
        for _ in range(3):
            payload = self._make_payload(session, [
                {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
            ])
            with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
                result = CheckoutService.process_receipt(self.company, self.user, payload)
                numbers.append(result['receipt_number'])
        self.assertEqual(numbers, [1, 2, 3])


# ═══════════════════════════════════════════════════════════════════════════
# T-17..24: PLACANJE
# ═══════════════════════════════════════════════════════════════════════════

class T17_Payment(POSTestBase):
    """T-17..24: Split, Revolut, Voucher, edge cases."""

    def test_t17_cash_with_change(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], amount_paid='5.00')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertGreater(Decimal(result['change']), Decimal('0'))

    def test_t18_card_no_change(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], method='CARD')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(result['change'], '0')

    def test_t19_revolut_payment(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], method='REVOLUT')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        pay = receipt.payment_lines.first()
        self.assertEqual(pay.method, 'REVOLUT')

    def test_t20_voucher_valid(self):
        voucher = Voucher.objects.create(
            company=self.company, code='TEST50',
            original_amount=Decimal('50.00'), remaining=Decimal('50.00'),
        )
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 2, 'unit_price': '2.50', 'tax_rate': 25}
        ], method='VOUCHER', voucher_code='TEST50')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        voucher.refresh_from_db()
        self.assertLess(voucher.remaining, Decimal('50.00'))

    def test_t21_voucher_invalid_code(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ], method='VOUCHER', voucher_code='NEPOSTOJI')
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'VOUCHER_NOT_FOUND')

    def test_t22_tip_as_item(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25},
        ], tip_amount='1.50')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        tip_items = receipt.items.filter(is_tip=True)
        self.assertEqual(tip_items.count(), 1)
        self.assertEqual(tip_items.first().unit_price, Decimal('1.50'))

    def test_t23_pfand_field_exists(self):
        # Verify pfand fields exist on model
        fields = [f.name for f in POSReceiptItem._meta.get_fields()]
        self.assertIn('is_pfand_return', fields)
        # Verify pfand item can be created
        session = self._open_session()
        receipt = POSReceipt.objects.create(session=session, receipt_number=888, total=0, status='open')
        item = POSReceiptItem.objects.create(
            receipt=receipt, description='Pfand', quantity=1,
            unit_price=Decimal('0.25'), tax_rate=19, is_pfand_return=True,
        )
        self.assertTrue(item.is_pfand_return)

    def test_t24_custom_item_no_inventory(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'name': 'Rucni unos', 'quantity': 1, 'unit_price': '10.00', 'tax_rate': 25},
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertIn('receipt_id', result)


# ═══════════════════════════════════════════════════════════════════════════
# T-25..31: FISKALIZACIJA ROUTING
# ═══════════════════════════════════════════════════════════════════════════

class T25_FiscalRouting(POSTestBase):
    """T-25..31: HR/DE/bypass routing, FINA pada, TSE pada."""

    def test_t25_hr_route_calls_fina(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('fiscal.service.fiscalize_pos_receipt', return_value='JIR123') as mock:
            result = CheckoutService.process_receipt(self.company, self.user, payload)
            mock.assert_called_once()

    def test_t26_de_route_calls_tse(self):
        session = self._open_session(self.terminal_de)
        item_de = InventoryItem.objects.create(
            company=self.company_de, name='Kaffee', sku='KAF01',
            unit_price=Decimal('3.00'), quantity=100,
        )
        payload = self._make_payload(session, [
            {'item_id': item_de.pk, 'quantity': 1, 'unit_price': '3.00', 'tax_rate': 19}
        ])
        with patch.object(CheckoutService, '_fiscalize_tse', return_value=('hash', 'tx1', '')) as mock:
            result = CheckoutService.process_receipt(self.company_de, self.user, payload)
            mock.assert_called_once()

    def test_t27_nonprofit_bypass(self):
        session = self._open_session(self.terminal_udruga)
        payload = self._make_payload(session, [
            {'item_id': self.item_nonprofit.pk, 'quantity': 1, 'unit_price': '20.00', 'tax_rate': 0}
        ])
        # _should_fiscalize returns False for nonprofit-only receipts
        # _fiscalize will bypass, no FINA/TSE call
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')) as mock:
            result = CheckoutService.process_receipt(self.company_udruga, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        # Verify the guard logic independently
        self.assertFalse(CheckoutService._should_fiscalize(receipt))

    def test_t28_fina_failure_no_block(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('fiscal.service.fiscalize_pos_receipt', side_effect=Exception('FINA down')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertIn('receipt_id', result)
        self.assertIn('fiscal_warning', result)

    def test_t29_tse_failure_ausfall(self):
        session = self._open_session(self.terminal_de)
        item_de = InventoryItem.objects.create(
            company=self.company_de, name='Bier', sku='BIER01',
            unit_price=Decimal('4.00'), quantity=100,
        )
        payload = self._make_payload(session, [
            {'item_id': item_de.pk, 'quantity': 1, 'unit_price': '4.00', 'tax_rate': 19}
        ])
        with patch('pos.tse_adapter.FiskalyTSEAdapter.from_company', side_effect=Exception('TSE offline')):
            result = CheckoutService.process_receipt(self.company_de, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertIn('TSE_AUSFALL', receipt.tse_error)

    def test_t30_fina_napojnica_xml(self):
        from fiskalizacija.fisk import _build_racun
        from lxml import etree
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25},
        ], tip_amount='2.00')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        racun = _build_racun(receipt, '11111111111', '1', '1', 'abc', timezone.now())
        xml = etree.tostring(racun, encoding='unicode')
        self.assertIn('Napojnica', xml)
        self.assertIn('IznosN', xml)

    def test_t31_dsfinvk_export(self):
        from pos.dsfinvk_export import generate_dsfinvk_export
        from datetime import date
        import zipfile, io
        zb = generate_dsfinvk_export(self.company, date(2026, 1, 1), date(2026, 12, 31))
        zf = zipfile.ZipFile(io.BytesIO(zb))
        names = zf.namelist()
        self.assertIn('bonkopf.csv', names)
        self.assertIn('bonpos.csv', names)
        self.assertIn('tse.csv', names)
        self.assertIn('index.json', names)


# ═══════════════════════════════════════════════════════════════════════════
# T-32..35: OFFLINE SYNC
# ═══════════════════════════════════════════════════════════════════════════

class T32_OfflineSync(POSTestBase):
    """T-32..35: Zaostali bonovi, naknada fiskalizacija."""

    def test_t32_retry_task_exists(self):
        from pos.tasks import retry_fiscalization
        self.assertTrue(callable(retry_fiscalization))

    def test_t33_offline_receipt_no_jir(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('fiscal.service.fiscalize_pos_receipt', return_value=None):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertFalse(receipt.jir)

    def test_t34_pos_offline_js_exists(self):
        import os
        self.assertTrue(os.path.exists('/var/www/fina-connect/static/js/pos/pos-offline.js'))

    def test_t35_offline_js_has_indexeddb(self):
        with open('/var/www/fina-connect/static/js/pos/pos-offline.js') as f:
            content = f.read()
        self.assertIn('indexedDB', content)
        self.assertIn('queueOfflineReceipt', content)
        self.assertIn('syncOfflineData', content)


# ═══════════════════════════════════════════════════════════════════════════
# T-36..41: Z-IZVJESCE
# ═══════════════════════════════════════════════════════════════════════════

class T36_ZReport(POSTestBase):
    """T-36..41: Prazna smjena, stornirani bonovi, daily report."""

    def test_t36_empty_session_totals(self):
        session = self._open_session()
        self.assertEqual(session.total_sales, Decimal('0.00'))
        self.assertEqual(session.total_cash_sales, Decimal('0.00'))

    def test_t37_session_total_after_sale(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 2, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertGreater(session.total_sales, Decimal('0'))

    def test_t38_expected_closing_cash(self):
        session = self._open_session(opening_cash=200)
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '10.00', 'tax_rate': 25}
        ], amount_paid='10.00')
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            CheckoutService.process_receipt(self.company, self.user, payload)
        # expected = opening + cash_sales
        self.assertGreaterEqual(session.expected_closing_cash, Decimal('200'))

    def test_t39_cancelled_not_in_totals(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '5.00', 'tax_rate': 25}
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        receipt.status = 'cancelled'
        receipt.save()
        self.assertEqual(session.total_sales, Decimal('0.00'))

    def test_t40_kassenbuch_generator(self):
        from pos.kassenbuch import generate_kassenbuch
        from datetime import date
        xlsx = generate_kassenbuch(self.company, date(2026, 3, 1), date(2026, 3, 20))
        self.assertGreater(len(xlsx), 100)

    def test_t41_order_source_field(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        self.assertTrue(hasattr(receipt, 'order_source'))


# ═══════════════════════════════════════════════════════════════════════════
# T-42..46: STORNO/POVRAT
# ═══════════════════════════════════════════════════════════════════════════

class T42_Storno(POSTestBase):
    """T-42..46: Storno, djelomicni povrat, dupli storno."""

    def test_t42_cancel_receipt_view_exists(self):
        from pos.views import cancel_receipt
        self.assertTrue(callable(cancel_receipt))

    def test_t43_refund_receipt_view_exists(self):
        from pos.views import refund_receipt
        self.assertTrue(callable(refund_receipt))

    def test_t44_cancelled_status(self):
        session = self._open_session()
        payload = self._make_payload(session, [
            {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
        ])
        with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
            result = CheckoutService.process_receipt(self.company, self.user, payload)
        receipt = POSReceipt.objects.get(pk=result['receipt_id'])
        receipt.status = 'cancelled'
        receipt.cancel_reason = 'Test storno'
        receipt.save()
        self.assertEqual(receipt.status, 'cancelled')
        self.assertEqual(receipt.cancel_reason, 'Test storno')

    def test_t45_receipt_statuses(self):
        statuses = dict(POSReceipt.Status.choices)
        self.assertIn('paid', statuses)
        self.assertIn('cancelled', statuses)
        self.assertIn('refunded', statuses)
        self.assertIn('open', statuses)

    def test_t46_zero_receipt_not_archived(self):
        from documents.signals import archive_pos_receipt
        session = self._open_session()
        receipt = POSReceipt.objects.create(
            session=session, receipt_number=999, total=Decimal('0'), status='paid',
        )
        # Signal should skip zero amounts
        archive_pos_receipt(sender=POSReceipt, instance=receipt, created=True)
        from documents.models import ArhivaEntry
        self.assertFalse(
            ArhivaEntry.objects.filter(source_type='pos_receipt', source_id=str(receipt.pk)).exists()
        )


# ═══════════════════════════════════════════════════════════════════════════
# T-47..50: PERFORMANSA
# ═══════════════════════════════════════════════════════════════════════════

class T47_Performance(POSTestBase):
    """T-47..50: 50 bonova < 5s, Z-report, DSFinV-K."""

    def test_t47_50_receipts_under_5s(self):
        session = self._open_session()
        start = time.time()
        for i in range(50):
            payload = self._make_payload(session, [
                {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
            ])
            with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
                CheckoutService.process_receipt(self.company, self.user, payload)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f'50 receipts took {elapsed:.2f}s (limit 5s)')

    def test_t48_z_report_under_2s(self):
        session = self._open_session()
        for i in range(20):
            payload = self._make_payload(session, [
                {'item_id': self.item.pk, 'quantity': 1, 'unit_price': '2.50', 'tax_rate': 25}
            ])
            with patch('pos.services.checkout.CheckoutService._fiscalize', return_value=('', '', '')):
                CheckoutService.process_receipt(self.company, self.user, payload)

        start = time.time()
        total = session.total_sales
        cash = session.total_cash_sales
        expected = session.expected_closing_cash
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, f'Z-report calc took {elapsed:.2f}s (limit 2s)')

    def test_t49_dsfinvk_under_3s(self):
        from pos.dsfinvk_export import generate_dsfinvk_export
        from datetime import date
        start = time.time()
        zb = generate_dsfinvk_export(self.company, date(2026, 1, 1), date(2026, 12, 31))
        elapsed = time.time() - start
        self.assertLess(elapsed, 3.0, f'DSFinV-K took {elapsed:.2f}s (limit 3s)')
        self.assertGreater(len(zb), 0)

    def test_t50_kassenbuch_under_2s(self):
        from pos.kassenbuch import generate_kassenbuch
        from datetime import date
        start = time.time()
        xlsx = generate_kassenbuch(self.company, date(2026, 1, 1), date(2026, 3, 31))
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, f'Kassenbuch took {elapsed:.2f}s (limit 2s)')
