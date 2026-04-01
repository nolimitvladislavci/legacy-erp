"""
Tests for SAF-T HR Generator.
"""
from datetime import date
from decimal import Decimal
from lxml import etree

from django.test import TestCase
from django.utils import timezone


class SAFTGeneratorTest(TestCase):
    """Test SAF-T XML generation."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(
            name='SAF-T Test d.o.o.', oib='12345678901',
            address='Testna 1', city='Zagreb', zip_code='10000',
        )

    def _generate(self, period_from=None, period_to=None):
        from konto.saft_generator import SAFTGenerator
        pf = period_from or date(2026, 1, 1)
        pt = period_to or date(2026, 3, 31)
        gen = SAFTGenerator(self.company, pf, pt)
        xml_str = gen.generate()
        return xml_str, etree.fromstring(xml_str.encode('utf-8'))

    def test_header_structure(self):
        """Header contains required SAF-T fields."""
        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        header = root.find('s:Header', ns)
        self.assertIsNotNone(header)
        self.assertEqual(header.find('s:AuditFileVersion', ns).text, '2.0')
        self.assertEqual(header.find('s:CompanyID', ns).text, 'HR12345678901')
        self.assertEqual(header.find('s:CurrencyCode', ns).text, 'EUR')
        self.assertEqual(header.find('s:FiscalYear', ns).text, '2026')

    def test_masterfiles_section_exists(self):
        """MasterFiles section is present in XML."""
        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        mf = root.find('s:MasterFiles', ns)
        self.assertIsNotNone(mf)

    def test_gl_accounts_from_konto(self):
        """GeneralLedgerAccounts populated from KontoAccount."""
        from konto.models import KontoAccount
        KontoAccount.objects.create(
            company=self.company, code='1000', name='Ziro racun', account_type='asset')
        KontoAccount.objects.create(
            company=self.company, code='2200', name='Dobavljaci', account_type='liability')

        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        accounts = root.findall('.//s:Account', ns)
        self.assertEqual(len(accounts), 2)
        codes = [a.find('s:AccountID', ns).text for a in accounts]
        self.assertIn('1000', codes)
        self.assertIn('2200', codes)

    def test_customers_from_sales_invoices(self):
        """Customers populated from partners with sales invoices."""
        from partners.models import Partner
        from invoicing.models import Invoice
        partner = Partner.objects.create(
            company=self.company, name='Kupac d.o.o.', oib='99988877766',
            buyer_type='b2b_vat',
        )
        Invoice.objects.create(
            company=self.company, partner=partner, number='R-2026-001',
            date_issued=timezone.now(), client_name='Kupac d.o.o.',
            subtotal=Decimal('1000'), tax_amount=Decimal('250'),
            total=Decimal('1250'), doctype='R',
        )

        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        customers = root.findall('.//s:Customer', ns)
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].find('s:TaxID', ns).text, '99988877766')

    def test_general_ledger_entries(self):
        """GL entries populated from JournalEntry + LedgerLine."""
        from konto.models import KontoAccount, JournalEntry, LedgerLine
        acc1 = KontoAccount.objects.create(
            company=self.company, code='1200', name='Kupci', account_type='asset')
        acc2 = KontoAccount.objects.create(
            company=self.company, code='7000', name='Prihodi', account_type='income')
        je = JournalEntry.objects.create(
            company=self.company, entry_number='T-001',
            date=date(2026, 2, 15), description='Test booking', is_posted=True,
        )
        LedgerLine.objects.create(
            journal_entry=je, account=acc1, side='debit', amount=Decimal('500'))
        LedgerLine.objects.create(
            journal_entry=je, account=acc2, side='credit', amount=Decimal('500'))

        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        entries = root.findall('.//s:Entry', ns)
        self.assertEqual(len(entries), 1)
        lines = entries[0].findall('s:Line', ns)
        self.assertEqual(len(lines), 2)

    def test_source_documents_sales(self):
        """SalesInvoices populated from invoicing.Invoice."""
        from invoicing.models import Invoice, InvoiceItem
        inv = Invoice.objects.create(
            company=self.company, number='R-2026-TEST',
            date_issued=timezone.now(), client_name='Test',
            subtotal=Decimal('100'), tax_amount=Decimal('25'),
            total=Decimal('125'), doctype='R',
        )
        InvoiceItem.objects.create(
            invoice=inv, description='Usluga', quantity=1,
            unit_price=Decimal('100'), tax_rate=Decimal('25'),
            total_price=Decimal('100'),
        )

        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        invoices = root.findall('.//s:SalesInvoices/s:Invoice', ns)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0].find('s:InvoiceNo', ns).text, 'R-2026-TEST')

    def test_xml_well_formed(self):
        """Generated XML is well-formed and parseable."""
        xml_str, root = self._generate()
        self.assertTrue(xml_str.startswith("<?xml version='1.0'"))
        self.assertIn('AuditFile', root.tag)

    def test_empty_company_no_crash(self):
        """Empty company (no data) generates valid XML without crashing."""
        xml_str, root = self._generate()
        ns = {'s': 'urn:OECD:StandardAuditFile-Tax:HR_2.0'}
        header = root.find('s:Header', ns)
        self.assertIsNotNone(header)
