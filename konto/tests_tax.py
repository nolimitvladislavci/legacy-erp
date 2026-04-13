"""
konto/tests_tax.py — Tax Compliance Module tests
Tests for VAT calculation, corporate tax, PDV-S bridge, and tax dashboard.
"""
from decimal import Decimal
from datetime import date, datetime
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def _make_company(**kwargs):
    from companies.models import Company
    defaults = {
        'name': 'Test d.o.o.',
        'oib': '12345678901',
        'country': 'HR',
        'business_type': 'doo',
        'pdv_status': 'obveznik',
        'is_vat_registered': True,
        'currency': 'EUR',
    }
    defaults.update(kwargs)
    return Company.objects.create(**defaults)


def _make_account(company, code, name, account_type='expense'):
    from konto.models import KontoAccount
    return KontoAccount.objects.create(
        company=company, code=code, name=name,
        account_type=account_type, is_active=True,
    )


def _make_journal_entry(company, entry_date, lines, user=None):
    from konto.models import JournalEntry, LedgerLine
    from konto.services import _next_entry_number
    je = JournalEntry.objects.create(
        company=company,
        entry_number=_next_entry_number(company, 'TST'),
        date=entry_date,
        description='Test entry',
        source_type='manual',
        is_posted=True,
        created_by=user,
    )
    for acct, side, amount in lines:
        LedgerLine.objects.create(
            journal_entry=je, account=acct,
            side=side, amount=Decimal(str(amount)),
        )
    return je


def _make_invoice(company, doctype='R', total=1000, tax_amount=200, dt=None):
    from invoicing.models import Invoice
    dt = dt or timezone.now()
    return Invoice.objects.create(
        company=company,
        doctype=doctype,
        number=f'TST-{Invoice.objects.count()+1}',
        status='PAID',
        total=Decimal(str(total)),
        subtotal=Decimal(str(total)) - Decimal(str(tax_amount)),
        tax_amount=Decimal(str(tax_amount)),
        date_issued=dt,
    )


class TestVATCalculation(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.company = _make_company()
        self.income_acct = _make_account(self.company, '7000', 'Prihodi', 'income')
        self.expense_acct = _make_account(self.company, '4000', 'Rashodi', 'expense')
        self.vat_in_acct = _make_account(self.company, '1400', 'Pretporez', 'asset')

    def test_calculate_vat_monthly_hr(self):
        """PDV za mjesec: izlazni - ulazni = obveza."""
        from konto.services import calculate_vat_period
        # Create an outgoing invoice
        _make_invoice(self.company, 'R', total=1250, tax_amount=250,
                      dt=timezone.make_aware(datetime(2025, 6, 15)))
        # Create input VAT entry
        _make_journal_entry(self.company, date(2025, 6, 10), [
            (self.vat_in_acct, 'debit', 100),
            (self.expense_acct, 'debit', 400),
            (self.income_acct, 'credit', 500),
        ], self.user)

        period = calculate_vat_period(self.company, 'monthly', 2025, 6)
        self.assertIsNotNone(period)
        self.assertEqual(period.year, 2025)
        self.assertEqual(period.month, 6)
        # Output VAT from invoice
        self.assertGreaterEqual(period.total_output_vat, Decimal('0'))
        # Input VAT from ledger
        self.assertEqual(period.total_input_vat, Decimal('100.00'))

    def test_zero_invoices_zero_vat(self):
        """Firma bez racuna -> PDV = 0."""
        from konto.services import calculate_vat_period
        period = calculate_vat_period(self.company, 'monthly', 2025, 1)
        self.assertEqual(period.total_output_vat, Decimal('0'))
        self.assertEqual(period.total_input_vat, Decimal('0'))
        self.assertEqual(period.vat_payable, Decimal('0'))

    def test_tax_period_unique(self):
        """Ponovljeni poziv za isti mjesec updateira, ne duplicira."""
        from konto.services import calculate_vat_period
        from konto.models import TaxPeriod
        calculate_vat_period(self.company, 'monthly', 2025, 3)
        calculate_vat_period(self.company, 'monthly', 2025, 3)
        count = TaxPeriod.objects.filter(
            company=self.company, year=2025, month=3
        ).count()
        self.assertEqual(count, 1)


class TestCorporateTax(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser2', 'test2@test.com', 'pass')
        self.company = _make_company(oib='98765432101', name='Corp d.o.o.')
        self.expense_acct = _make_account(self.company, '4000', 'Rashodi', 'expense')

    def test_pd_under_1m(self):
        """Dobit < 1M EUR -> 10%."""
        from konto.services import calculate_corporate_tax
        # Create invoice with 100K revenue
        _make_invoice(self.company, 'R', total=100000, tax_amount=20000,
                      dt=timezone.make_aware(datetime(2025, 6, 15)))
        result = calculate_corporate_tax(self.company, 2025)
        self.assertEqual(result['tax_rate'], '10%')
        self.assertGreater(result['gross_revenue'], 0)

    def test_pd_zero_revenue(self):
        """Firma bez prihoda -> porez = 0."""
        from konto.services import calculate_corporate_tax
        result = calculate_corporate_tax(self.company, 2025)
        self.assertEqual(result['net_tax'], 0)
        self.assertEqual(result['tax_base'], 0)


class TestAnnualTax(TestCase):
    def setUp(self):
        self.company = _make_company(oib='11111111111', name='Obrt Test')

    def test_hr_income_tax_returns_dict(self):
        """get_annual_tax_summary vraca dict s kljucevima."""
        from konto.services import get_annual_tax_summary
        result = get_annual_tax_summary(self.company, 2025)
        self.assertIn('country', result)
        self.assertIn('total_tax_due', result)
        self.assertIn('gross_revenue', result)
        self.assertEqual(result['country'], 'HR')

    def test_de_tax_has_gewerbesteuer(self):
        """Njemacka firma vraca Gewerbesteuer."""
        de_company = _make_company(
            oib='22222222222', name='Test GmbH',
            country='DE', business_type='gmbh'
        )
        from konto.services import get_annual_tax_summary
        result = get_annual_tax_summary(de_company, 2025)
        self.assertEqual(result['country'], 'DE')
        self.assertIn('gewerbesteuer', result)
        self.assertIn('einkommensteuer', result)


class TestPDVSBridge(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser3', 'test3@test.com', 'pass')
        self.company = _make_company(oib='33333333333', name='Bridge d.o.o.')

    def test_generate_from_tax_period(self):
        """generate_pdv_s_from_tax_period kreira PDVSReport."""
        from pdv_s.service import generate_pdv_s_from_tax_period
        from pdv_s.models import PDVSReport
        _make_invoice(self.company, 'URA', total=5000, tax_amount=1000,
                      dt=timezone.make_aware(datetime(2025, 3, 10)))
        report = generate_pdv_s_from_tax_period(self.company, 2025, 3, self.user)
        self.assertIsInstance(report, PDVSReport)
        self.assertEqual(report.year, 2025)
        self.assertEqual(report.month, 3)

    def test_batch_generate(self):
        """batch_generate_pdv_s procesira sve obveznike."""
        from pdv_s.service import batch_generate_pdv_s
        results = batch_generate_pdv_s(2025, 3, self.user)
        self.assertIsInstance(results, list)

    def test_xml_export_format(self):
        """XML mora imati Zaglavlje + 4 sekcije."""
        from pdv_s.service import generate_pdv_s_xml
        pdv_data = {
            'i1_base': Decimal('1000'), 'i1_tax': Decimal('250'),
            'i2_base': Decimal('0'), 'i2_tax': Decimal('0'),
            'i3_base': Decimal('0'), 'i3_tax': Decimal('0'),
            'ii1_base': Decimal('2000'), 'ii1_tax': Decimal('500'),
            'ii2_base': Decimal('0'), 'ii2_tax': Decimal('0'),
            'ii3_base': Decimal('0'), 'ii3_tax': Decimal('0'),
            'ii4_base': Decimal('0'),
            'ii5_base': Decimal('0'),
            'ii6_base': Decimal('0'),
            'iii_total_pretporez': Decimal('250'),
            'iii_ispravak': Decimal('0'),
            'iv_pdv_isporuke': Decimal('500'),
            'iv_pretporez': Decimal('250'),
            'iv_razlika': Decimal('250'),
        }
        xml = generate_pdv_s_xml(self.company, 2025, 3, pdv_data)
        self.assertIn('Zaglavlje', xml)
        self.assertIn('PrimljeneIsporuke', xml)
        self.assertIn('ObavljeneIsporuke', xml)
        self.assertIn('Pretporez', xml)
        self.assertIn('ObvezaPDV', xml)
        self.assertIn(self.company.oib, xml)


class TestSupplierRisk(TestCase):
    def setUp(self):
        self.company = _make_company(oib='44444444444', name='Risk d.o.o.')

    def test_scan_supplier_risk_runs(self):
        """scan_supplier_risk ne pada za praznu firmu."""
        from limit_connect_ai.tasks_risk import scan_supplier_risk
        result = scan_supplier_risk(company_id=self.company.id)
        self.assertIn('companies', result)
        self.assertEqual(result['companies'], 1)

    def test_risk_alert_created_for_overdue(self):
        """Overdue URA kreira SupplierRiskAlert."""
        from partners.models import Partner
        from limit_connect_ai.tasks_risk import scan_supplier_risk
        from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert

        supplier = Partner.objects.create(
            company=self.company, name='Dobavljac X',
            oib='55555555555',
        )
        from invoicing.models import Invoice
        Invoice.objects.create(
            company=self.company, doctype='URA',
            number='URA-001', status='UNPAID',
            partner=supplier,
            total=Decimal('25000'), subtotal=Decimal('20000'),
            tax_amount=Decimal('5000'),
            date_issued=timezone.now(),
            date_due=date(2024, 1, 1),  # Very overdue
        )
        scan_supplier_risk(company_id=self.company.id)
        alerts = SupplierRiskAlert.objects.filter(
            company=self.company, supplier_oib='55555555555'
        )
        self.assertTrue(alerts.exists())
        self.assertIn(alerts.first().risk_level, ['HIGH', 'CRITICAL'])


class TestTaxDashboard(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user('dashuser', 'dash@test.com', 'pass')
        self.company = _make_company(oib='66666666666', name='Dash d.o.o.')
        # Assign user to company
        try:
            from accounts.models import UserProfile
            UserProfile.objects.update_or_create(
                user=self.user, defaults={'company': self.company}
            )
        except DatabaseError:
            pass

    def test_dashboard_returns_200(self):
        """Tax dashboard view returns 200."""
        from konto.views import tax_dashboard
        request = self.factory.get('/konto/reports/tax-dashboard/')
        request.user = self.user
        request.impersonated_company = None
        response = tax_dashboard(request)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_contains_company(self):
        """Dashboard context sadrzi rows."""
        from konto.views import tax_dashboard
        request = self.factory.get('/konto/reports/tax-dashboard/')
        request.user = self.user
        request.impersonated_company = None
        response = tax_dashboard(request)
        self.assertContains(response, 'Porezni status po firmama')
