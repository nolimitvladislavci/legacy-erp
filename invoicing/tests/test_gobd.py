"""Tests for invoicing/gobd_compliance.py — GoBD compliance checks."""
from django.test import TestCase
from django.utils import timezone


class _FakeItems:
    def __init__(self, count=1):
        self._count = count

    def exists(self):
        return self._count > 0


class _FakeInvoice:
    def __init__(self, **kwargs):
        self.client_name = kwargs.get('client_name', 'Test GmbH')
        self.client_address = kwargs.get('client_address', 'Teststr. 1, 10115 Berlin')
        self.number = kwargs.get('number', 'R-2026-0001')
        self.date_issued = kwargs.get('date_issued', timezone.now())
        self.date_delivery = kwargs.get('date_delivery', None)
        self.issuer_oib = kwargs.get('issuer_oib', 'DE123456789')
        self.invoice_profile = kwargs.get('invoice_profile', None)
        self.items = _FakeItems(kwargs.get('item_count', 1))


class TestCheckPflichtangaben(TestCase):

    def test_full_invoice_no_warnings(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice()
        warnings = check_pflichtangaben(inv)
        self.assertEqual(warnings, [])

    def test_missing_client_name(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(client_name='')
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('Kundenname' in w for w in warnings))

    def test_missing_client_address(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(client_address='')
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('Kundenadresse' in w for w in warnings))

    def test_missing_number(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(number='')
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('Rechnungsnummer' in w for w in warnings))

    def test_missing_date(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(date_issued=None)
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('Rechnungsdatum' in w for w in warnings))

    def test_no_items(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(item_count=0)
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('Leistungsbeschreibung' in w for w in warnings))

    def test_missing_tax_id(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(issuer_oib='')
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('USt-IdNr' in w for w in warnings))

    def test_multiple_missing(self):
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = _FakeInvoice(client_name='', number='', issuer_oib='')
        warnings = check_pflichtangaben(inv)
        self.assertGreaterEqual(len(warnings), 3)


class TestCheckFortlaufendeNummer(TestCase):

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name="GoBD Test GmbH", oib="77777777777")

    def test_no_invoices(self):
        from invoicing.gobd_compliance import check_fortlaufende_nummer
        result = check_fortlaufende_nummer(self.company)
        self.assertTrue(result['ok'])
        self.assertEqual(result['gaps'], [])

    def test_sequential_invoices_ok(self):
        from invoicing.gobd_compliance import check_fortlaufende_nummer
        from invoicing.models import Invoice
        for i in range(1, 4):
            Invoice.objects.create(
                company=self.company,
                doctype='R',
                number=f'R-2026-{i:04d}',
                date_issued=timezone.now(),
                status='PAID',
                issuer_name='Test',
                issuer_oib='77777777777',
            )
        result = check_fortlaufende_nummer(self.company, year=timezone.now().year)
        self.assertTrue(result['ok'])
        self.assertEqual(result['gaps'], [])

    def test_gap_detected(self):
        from invoicing.gobd_compliance import check_fortlaufende_nummer
        from invoicing.models import Invoice
        for i in [1, 2, 5]:  # gap at 3,4
            Invoice.objects.create(
                company=self.company,
                doctype='R',
                number=f'R-2026-{i:04d}',
                date_issued=timezone.now(),
                status='PAID',
                issuer_name='Test',
                issuer_oib='77777777777',
            )
        result = check_fortlaufende_nummer(self.company, year=timezone.now().year)
        self.assertFalse(result['ok'])
        self.assertGreater(len(result["gaps"]), 0)


class TestGetGobdReport(TestCase):

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name="GoBD Report GmbH", oib="88888888888")

    def test_empty_report(self):
        from invoicing.gobd_compliance import get_gobd_report
        report = get_gobd_report(self.company)
        self.assertEqual(report['total_invoices'], 0)
        self.assertEqual(report['issues_count'], 0)
        self.assertTrue(report['compliant'])

    def test_report_with_invoices(self):
        from invoicing.gobd_compliance import get_gobd_report
        from invoicing.models import Invoice
        Invoice.objects.create(
            company=self.company,
            doctype='R',
            number='R-2026-0001',
            date_issued=timezone.now(),
            status='PAID',
            client_name='Test Kunde',
            client_address='Str. 1',
            issuer_name='Test',
            issuer_oib='88888888888',
        )
        report = get_gobd_report(self.company, year=timezone.now().year)
        self.assertEqual(report['total_invoices'], 1)
        self.assertIn('compliant', report)
        self.assertIn('nummer_check', report)
