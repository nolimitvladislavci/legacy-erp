"""
invoicing/tests.py

Faza 10B test suite: OIB validacija, VAT validacija, FiscalLog, FiscalBatch, PDV izracun.
"""
from django.test import TestCase
from django.contrib.auth.models import User


class OIBValidationTests(TestCase):
    """ISO 7064 MOD 11,10 OIB validacija."""

    def setUp(self):
        from core.oib_validator import validate_oib_hr, validate_vat_id, format_oib_display
        self.validate_hr = validate_oib_hr
        self.validate_vat = validate_vat_id
        self.fmt = format_oib_display

    def test_valid_oib(self):
        self.assertTrue(self.validate_hr('12345678903'))

    def test_invalid_checksum(self):
        self.assertFalse(self.validate_hr('12345678901'))

    def test_too_short(self):
        self.assertFalse(self.validate_hr('1234567890'))

    def test_non_digit(self):
        self.assertFalse(self.validate_hr('1234567890a'))

    def test_empty(self):
        self.assertFalse(self.validate_hr(''))

    def test_all_zeros(self):
        self.assertFalse(self.validate_hr('00000000000'))


class VATValidationTests(TestCase):
    """VAT validacija za DE, AT, SI formate."""

    def setUp(self):
        from core.oib_validator import validate_vat_id
        self.v = validate_vat_id

    def test_de_valid(self):
        self.assertTrue(self.v('DE123456789', 'DE'))

    def test_de_invalid_length(self):
        self.assertFalse(self.v('DE12345678', 'DE'))

    def test_de_no_prefix(self):
        self.assertFalse(self.v('123456789', 'DE'))

    def test_at_valid(self):
        self.assertTrue(self.v('ATU12345678', 'AT'))

    def test_at_invalid(self):
        self.assertFalse(self.v('AT12345678', 'AT'))

    def test_si_valid(self):
        self.assertTrue(self.v('SI12345678', 'SI'))

    def test_hr_via_vat(self):
        self.assertTrue(self.v('12345678903', 'HR'))

    def test_generic_fallback(self):
        self.assertTrue(self.v('FR12345', 'FR'))

    def test_generic_too_short(self):
        self.assertFalse(self.v('FR1', 'FR'))


class VIESLookupMockTests(TestCase):
    """Mock VIES XML response parsing."""

    def _make_vies_response(self, valid='true', name='Test D.O.O.', address='ILICA 1, ZAGREB, 10000 Zagreb'):
        ns = 'urn:ec.europa.eu:taxud:vies:services:checkVat:types'
        return (
            '<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
            '<env:Body>'
            '<ns2:checkVatResponse xmlns:ns2="' + ns + '">'
            '<ns2:countryCode>HR</ns2:countryCode>'
            '<ns2:vatNumber>85821130368</ns2:vatNumber>'
            '<ns2:valid>' + valid + '</ns2:valid>'
            '<ns2:name>' + name + '</ns2:name>'
            '<ns2:address>' + address + '</ns2:address>'
            '</ns2:checkVatResponse>'
            '</env:Body>'
            '</env:Envelope>'
        )

    def test_parse_valid_response(self):
        from partners.hr_registry import VIESLookup
        vies = VIESLookup()
        xml = self._make_vies_response(valid='true', name='Test D.O.O.', address='ILICA 10, ZAGREB, 10000 Zagreb')
        result = vies._parse(xml, 'HR')
        self.assertTrue(result['valid'])
        self.assertEqual(result['name'], 'Test D.O.O.')
        self.assertEqual(result['city'], 'Zagreb')
        self.assertEqual(result['zip_code'], '10000')
        self.assertEqual(result['address'], 'Ilica 10')

    def test_parse_invalid_response(self):
        from partners.hr_registry import VIESLookup
        vies = VIESLookup()
        xml = self._make_vies_response(valid='false', name='---', address='---')
        result = vies._parse(xml, 'HR')
        self.assertFalse(result['valid'])
        self.assertEqual(result['name'], '')

    def test_parse_soap_fault(self):
        from partners.hr_registry import VIESLookup
        vies = VIESLookup()
        xml = (
            '<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
            '<env:Body><env:Fault><faultstring>INVALID_INPUT</faultstring></env:Fault></env:Body>'
            '</env:Envelope>'
        )
        result = vies._parse(xml, 'HR')
        self.assertFalse(result['valid'])
        self.assertIn('registru', result['error'])

    def test_address_with_district(self):
        from partners.hr_registry import _parse_address
        r = _parse_address('AVENIJA V. HOLJEVCA 10, ZAGREB, 10020 Zagreb-Novi Zagreb')
        self.assertEqual(r['zip_code'], '10020')
        self.assertIn('Zagreb', r['city'])
        self.assertIn('Avenija', r['address'])

    def test_address_empty(self):
        from partners.hr_registry import _parse_address
        r = _parse_address('')
        self.assertEqual(r['address'], '')
        self.assertEqual(r['city'], '')

    def test_address_dashes(self):
        from partners.hr_registry import _parse_address
        r = _parse_address('---')
        self.assertEqual(r['address'], '')


class FiscalLogTests(TestCase):
    """FiscalLog kreiranje i query."""

    def setUp(self):
        from companies.models import Company
        self.user = User.objects.create_user('testuser_fl', password='pass')
        self.company = Company.objects.create(name='Test Firma')
        from invoicing.models import Invoice
        from django.utils import timezone
        self.invoice = Invoice.objects.create(
            number='TEST-001',
            doctype='R',
            status='DRAFT',
            company=self.company,
            client_name='Klijent Test',
            date_issued=timezone.now(),
        )

    def test_create_log(self):
        from invoicing.fiscal_models import FiscalLog
        log = FiscalLog.log(
            invoice=self.invoice,
            action='sign',
            status='success',
            message='ZKI generiran',
            user=self.user,
        )
        self.assertEqual(log.action, 'sign')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.invoice, self.invoice)
        self.assertEqual(log.created_by, self.user)

    def test_query_by_invoice(self):
        from invoicing.fiscal_models import FiscalLog
        FiscalLog.log(invoice=self.invoice, action='send', status='error', message='CIS nedostupan')
        FiscalLog.log(invoice=self.invoice, action='retry', status='success', message='OK')
        logs = self.invoice.fiscal_logs.all()
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.filter(status='success').count(), 1)

    def test_str(self):
        from invoicing.fiscal_models import FiscalLog
        log = FiscalLog.log(invoice=self.invoice, action='error', status='error')
        self.assertIn('error', str(log))


class FiscalBatchTests(TestCase):
    """FiscalBatch kreiranje i statistike."""

    def setUp(self):
        from companies.models import Company
        self.user = User.objects.create_user('testuser_fb', password='pass')
        self.company = Company.objects.create(name='Test Firma Batch')

    def test_create_batch(self):
        from invoicing.fiscal_models import FiscalBatch
        batch = FiscalBatch.objects.create(
            company=self.company,
            created_by=self.user,
            status='pending',
            total_count=5,
            success_count=3,
            error_count=2,
        )
        self.assertEqual(batch.success_rate, 60)
        self.assertEqual(str(batch.success_count), '3')

    def test_batch_status_choices(self):
        from invoicing.fiscal_models import FiscalBatch
        batch = FiscalBatch.objects.create(
            company=self.company, created_by=self.user,
            status='completed', total_count=10, success_count=10, error_count=0,
        )
        self.assertEqual(batch.success_rate, 100)
        self.assertIsNone(batch.duration_seconds)

    def test_batch_str(self):
        from invoicing.fiscal_models import FiscalBatch
        batch = FiscalBatch.objects.create(
            company=self.company, created_by=self.user,
            status='partial', total_count=4, success_count=2, error_count=2,
        )
        self.assertIn('2', str(batch))


class PDVCalculationTests(TestCase):
    """PDV izracun: 25%, 13%, 5%, 0%."""

    def _calc(self, net, rate_pct):
        from decimal import Decimal
        net = Decimal(str(net))
        rate = Decimal(str(rate_pct)) / Decimal('100')
        tax = (net * rate).quantize(Decimal('0.01'))
        gross = net + tax
        return {'net': net, 'tax': tax, 'gross': gross}

    def test_pdv_25(self):
        r = self._calc(100, 25)
        from decimal import Decimal
        self.assertEqual(r['tax'], Decimal('25.00'))
        self.assertEqual(r['gross'], Decimal('125.00'))

    def test_pdv_13(self):
        r = self._calc(100, 13)
        from decimal import Decimal
        self.assertEqual(r['tax'], Decimal('13.00'))

    def test_pdv_5(self):
        r = self._calc(100, 5)
        from decimal import Decimal
        self.assertEqual(r['tax'], Decimal('5.00'))

    def test_pdv_0(self):
        r = self._calc(100, 0)
        from decimal import Decimal
        self.assertEqual(r['tax'], Decimal('0.00'))
        self.assertEqual(r['gross'], Decimal('100.00'))

    def test_pdv_25_fractional(self):
        r = self._calc('49.99', 25)
        from decimal import Decimal
        self.assertEqual(r['tax'], Decimal('12.50'))
        self.assertEqual(r['gross'], Decimal('62.49'))


class NKDSearchTests(TestCase):
    """NKD pretrazivanje."""

    def setUp(self):
        from companies.models import NKDCode
        self.user = User.objects.create_user('testuser_nkd', password='pass')
        NKDCode.objects.create(code='62.01', level='class', section='J', name_hr='Racunalno programiranje', is_active=True)
        NKDCode.objects.create(code='62.02', level='class', section='J', name_hr='Savjetovanje u vezi s racunalima', is_active=True)
        NKDCode.objects.create(code='56.10', level='class', section='I', name_hr='Restorani i ostali objekti za pripremu i usluzivanjepolja', is_active=True)

    def test_search_by_name(self):
        from companies.models import NKDCode
        from django.db.models import Q
        qs = NKDCode.objects.filter(is_active=True).filter(
            Q(name_hr__icontains='programiranje') | Q(code__icontains='programiranje')
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().code, '62.01')

    def test_search_by_code(self):
        from companies.models import NKDCode
        from django.db.models import Q
        qs = NKDCode.objects.filter(is_active=True).filter(
            Q(name_hr__icontains='62.01') | Q(code__icontains='62.01')
        )
        self.assertEqual(qs.count(), 1)

    def test_search_no_results(self):
        from companies.models import NKDCode
        from django.db.models import Q
        qs = NKDCode.objects.filter(is_active=True).filter(
            Q(name_hr__icontains='nepostojeci_xyzxyz')
        )
        self.assertEqual(qs.count(), 0)
