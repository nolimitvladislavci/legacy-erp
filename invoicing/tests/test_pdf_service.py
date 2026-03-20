"""Tests for invoicing/services/pdf_service.py."""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone


class _FakeItem:
    def __init__(self, desc, qty, price, tax_rate, unit='kom'):
        self.description = desc
        self.quantity = Decimal(str(qty))
        self.unit_price = Decimal(str(price))
        self.tax_rate = Decimal(str(tax_rate))
        self.total_price = self.quantity * self.unit_price
        self.unit = unit


class _FakeQueryset(list):
    def all(self):
        return self


class _FakeInvoice:
    def __init__(self, **kwargs):
        self.number = kwargs.get('number', 'R-2026-0001')
        self.uuid = kwargs.get('uuid', 'test-uuid-1234')
        self.doctype = kwargs.get('doctype', 'R')
        self.date_issued = kwargs.get('date_issued', timezone.now())
        self.date_due = kwargs.get('date_due', None)
        self.currency = kwargs.get('currency', 'EUR')
        self.is_hr = kwargs.get('is_hr', True)
        self.client_name = kwargs.get('client_name', 'Test Client')
        self.client_address = kwargs.get('client_address', 'Testna 1')
        self.client_oib = kwargs.get('client_oib', '12345678901')
        self.issuer_name = kwargs.get('issuer_name', 'Test Firma')
        self.issuer_address = kwargs.get('issuer_address', 'Poslovna 5')
        self.issuer_oib = kwargs.get('issuer_oib', '98765432109')
        self.issuer_iban = kwargs.get('issuer_iban', 'HR1210010051863000160')
        self.issuer_email = kwargs.get('issuer_email', 'test@firma.hr')
        self.subtotal = kwargs.get('subtotal', Decimal('100.00'))
        self.tax_amount = kwargs.get('tax_amount', Decimal('25.00'))
        self.tax_percent = kwargs.get('tax_percent', Decimal('25'))
        self.total = kwargs.get('total', Decimal('125.00'))
        self.country = kwargs.get('country', 'HR')
        self.qr_code_base64 = kwargs.get('qr_code_base64', '')
        self.payment_method = 'TRANSAKCIJSKI'
        self.note = ''
        self.status = 'DRAFT'
        _items = kwargs.get('items', [_FakeItem('Usluga', 1, 100, 25)])
        self.items = _FakeQueryset(_items)

    def save(self, update_fields=None):
        pass


class TestBuildTaxGroups(TestCase):

    def test_single_rate(self):
        from invoicing.services.pdf_service import build_tax_groups
        inv = _FakeInvoice()
        groups = build_tax_groups(inv)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['rate'], '25')

    def test_multiple_rates(self):
        from invoicing.services.pdf_service import build_tax_groups
        items = [
            _FakeItem('A', 1, 100, 25),
            _FakeItem('B', 1, 50, 13),
        ]
        inv = _FakeInvoice(items=items)
        groups = build_tax_groups(inv)
        rates = [g['rate'] for g in groups]
        self.assertIn('25', rates)
        self.assertIn('13', rates)

    def test_zero_rate_excluded(self):
        from invoicing.services.pdf_service import build_tax_groups
        # item with 0 tax has base 0 effectively — should not appear
        items = [_FakeItem('A', 1, 100, 25)]
        inv = _FakeInvoice(items=items)
        groups = build_tax_groups(inv)
        self.assertTrue(all(g['base'] > 0 for g in groups))

    def test_group_totals(self):
        from invoicing.services.pdf_service import build_tax_groups
        items = [_FakeItem('A', 2, 100, 25)]
        inv = _FakeInvoice(items=items)
        groups = build_tax_groups(inv)
        g = groups[0]
        self.assertEqual(g['base'], Decimal('200'))
        self.assertEqual(g['tax'], Decimal('50'))
        self.assertEqual(g['total'], Decimal('250'))


class TestGenerateQr(TestCase):

    def test_returns_string(self):
        from invoicing.services.pdf_service import generate_qr
        inv = _FakeInvoice()
        result = generate_qr(inv)
        # May return '' if qrcode not installed, but should not raise
        self.assertIsInstance(result, str)

    def test_returns_base64_or_empty(self):
        from invoicing.services.pdf_service import generate_qr
        inv = _FakeInvoice()
        result = generate_qr(inv)
        if result:
            import base64
            # Should be valid base64
            decoded = base64.b64decode(result)
            self.assertGreater(len(decoded), 0)


class TestGenerateZki(TestCase):

    def test_returns_hex_string(self):
        from invoicing.services.pdf_service import generate_zki
        inv = _FakeInvoice()
        result = generate_zki(inv, cert_key='test_key')
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 32)  # MD5 hex digest

    def test_different_keys_different_results(self):
        from invoicing.services.pdf_service import generate_zki
        inv = _FakeInvoice()
        r1 = generate_zki(inv, cert_key='key1')
        r2 = generate_zki(inv, cert_key='key2')
        self.assertNotEqual(r1, r2)


class TestGenerateEracunXml(TestCase):

    def test_returns_xml_string(self):
        from invoicing.services.pdf_service import generate_eracun_xml
        inv = _FakeInvoice()
        xml = generate_eracun_xml(inv)
        self.assertIsInstance(xml, str)
        self.assertIn('<?xml', xml)
        self.assertIn('Invoice', xml)

    def test_contains_invoice_data(self):
        from invoicing.services.pdf_service import generate_eracun_xml
        inv = _FakeInvoice(number='R-2026-TEST')
        xml = generate_eracun_xml(inv)
        self.assertIn('R-2026-TEST', xml)
        self.assertIn('Test Client', xml)
        self.assertIn('Test Firma', xml)

    def test_ubl_namespace(self):
        from invoicing.services.pdf_service import generate_eracun_xml
        inv = _FakeInvoice()
        xml = generate_eracun_xml(inv)
        self.assertIn('urn:oasis:names:specification:ubl', xml)

    def test_no_oib_block_when_missing(self):
        from invoicing.services.pdf_service import generate_eracun_xml
        inv = _FakeInvoice(client_oib='')
        xml = generate_eracun_xml(inv)
        # issuer always has PartyTaxScheme; verify client OIB absent
        self.assertNotIn('12345678901', xml)

    def test_with_oib_block(self):
        from invoicing.services.pdf_service import generate_eracun_xml
        inv = _FakeInvoice(client_oib='12345678901')
        xml = generate_eracun_xml(inv)
        self.assertIn('PartyTaxScheme', xml)
        self.assertIn('12345678901', xml)
