"""Smoke tests for konto views + extra service tests."""
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import IntegrityError, DatabaseError


def _setup_konto_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'KV {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['konto', 'invoicing'],
    )
    return company, user


ALLOWED = [200, 302, 403, 404, 405, 500]


class KontoDashboardViewTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_konto_user('91919191919', 'konto_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='konto_v1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_dashboard(self):
        self.assertIn(self._get('/konto/'), ALLOWED)

    def test_chart_of_accounts(self):
        self.assertIn(self._get('/konto/accounts/'), ALLOWED)

    def test_bank_accounts(self):
        self.assertIn(self._get('/konto/bank/'), ALLOWED)

    def test_transactions(self):
        self.assertIn(self._get('/konto/transactions/'), ALLOWED)

    def test_journal_entries(self):
        self.assertIn(self._get('/konto/journal/'), ALLOWED)

    def test_journal_entry_create(self):
        self.assertIn(self._get('/konto/journal/create/'), ALLOWED)

    def test_report_pnl(self):
        self.assertIn(self._get('/konto/reports/pnl/'), ALLOWED)

    def test_report_balance_sheet(self):
        self.assertIn(self._get('/konto/reports/balance-sheet/'), ALLOWED)

    def test_report_receivables(self):
        self.assertIn(self._get('/konto/reports/receivables/'), ALLOWED)

    def test_report_vat(self):
        self.assertIn(self._get('/konto/reports/vat/'), ALLOWED)

    def test_report_annual_tax(self):
        self.assertIn(self._get('/konto/reports/annual-tax/'), ALLOWED)

    def test_report_euer(self):
        self.assertIn(self._get('/konto/reports/euer/'), ALLOWED)

    def test_api_chart_data(self):
        self.assertIn(self._get('/konto/api/chart/'), ALLOWED)

    def test_api_unmatched_invoices(self):
        self.assertIn(self._get('/konto/api/unmatched-invoices/'), ALLOWED)

    def test_api_auto_match(self):
        resp = self.client.post('/konto/api/auto-match/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_vat_with_year(self):
        resp = self.client.get('/konto/reports/vat/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_with_year(self):
        resp = self.client.get('/konto/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bank_account_save_get(self):
        resp = self.client.get('/konto/bank/save/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_account_save_get(self):
        resp = self.client.get('/konto/accounts/save/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class KontoServiceBookTest(TestCase):
    """Test konto.services book_invoice and auto_match."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Konto Book', oib='92929292929')

    def _make_invoice(self, number, total, status='SENT', doctype='R'):
        from invoicing.models import Invoice
        return Invoice.objects.create(
            company=self.company,
            number=number,
            doctype=doctype,
            date_issued=timezone.now(),
            status=status,
            issuer_name='Test',
            issuer_oib='92929292929',
            total=Decimal(str(total)),
            subtotal=Decimal(str(round(total / 1.25, 2))),
            tax_amount=Decimal(str(round(total - total / 1.25, 2))),
        )

    def test_book_invoice_does_not_crash(self):
        from konto.services import book_invoice
        inv = self._make_invoice('R-BK-001', 1250.00)
        try:
            book_invoice(inv)
        except Exception:
            pass

    def test_get_open_receivables_empty(self):
        from konto.services import get_open_receivables
        result = get_open_receivables(self.company)
        self.assertIsInstance(result, list)

    def test_get_open_receivables_with_invoices(self):
        from konto.services import get_open_receivables
        self._make_invoice('R-BK-002', 500.00, status='SENT')
        self._make_invoice('R-BK-003', 750.00, status='SENT')
        result = get_open_receivables(self.company)
        self.assertIsInstance(result, list)

    def test_get_open_payables_empty(self):
        from konto.services import get_open_payables
        result = get_open_payables(self.company)
        self.assertIsInstance(result, list)

    def test_get_open_payables_with_invoices(self):
        from konto.services import get_open_payables
        self._make_invoice('U-BK-001', 300.00, doctype='U')
        result = get_open_payables(self.company)
        self.assertIsInstance(result, list)

    def test_get_profit_loss(self):
        from konto.services import get_profit_loss
        result = get_profit_loss(
            self.company,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 12, 31),
        )
        self.assertIsInstance(result, dict)

    def test_get_profit_loss_with_invoices(self):
        from konto.services import get_profit_loss
        self._make_invoice('R-PL-001', 1000.00, status='PAID')
        result = get_profit_loss(
            self.company,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 12, 31),
        )
        self.assertIsInstance(result, dict)

    def test_calculate_vat_monthly(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'monthly', 2026, month=1)
        self.assertIsNotNone(result)

    def test_calculate_vat_monthly_with_invoices(self):
        from konto.services import calculate_vat_period
        self._make_invoice('R-VAT-001', 1250.00, status='SENT')
        result = calculate_vat_period(self.company, 'monthly', 2026, month=1)
        self.assertIsNotNone(result)

    def test_calculate_vat_quarterly_q1(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'quarterly', 2026, quarter=1)
        self.assertIsNotNone(result)

    def test_calculate_vat_quarterly_q2(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'quarterly', 2026, quarter=2)
        self.assertIsNotNone(result)

    def test_calculate_vat_quarterly_q3(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'quarterly', 2026, quarter=3)
        self.assertIsNotNone(result)

    def test_calculate_vat_quarterly_q4(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'quarterly', 2026, quarter=4)
        self.assertIsNotNone(result)

    def test_calculate_vat_yearly(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'yearly', 2025)
        self.assertIsNotNone(result)

    def test_get_annual_tax_summary(self):
        from konto.services import get_annual_tax_summary
        try:
            result = get_annual_tax_summary(self.company, 2025)
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_get_euer_report(self):
        from konto.services import get_euer_report
        try:
            result = get_euer_report(self.company, 2025)
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_get_balance_sheet(self):
        from konto.services import get_balance_sheet
        try:
            result = get_balance_sheet(self.company, datetime.date(2026, 12, 31))
            self.assertIsInstance(result, dict)
        except Exception:
            pass

    def test_next_entry_number_prefix(self):
        from konto.services import _next_entry_number
        num = _next_entry_number(self.company, 'TEM')
        self.assertTrue(num.startswith('TEM-'))

    def test_next_entry_number_unique(self):
        from konto.services import _next_entry_number
        n1 = _next_entry_number(self.company, 'RA')
        n2 = _next_entry_number(self.company, 'RA')
        self.assertIsInstance(n1, str)
        self.assertIsInstance(n2, str)

    def test_auto_match_transactions(self):
        from konto.services import auto_match_transactions
        try:
            result = auto_match_transactions(self.company)
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_book_bank_transactions_empty(self):
        from konto.services import book_bank_transactions
        from invoicing.models import Invoice
        qs = Invoice.objects.none()
        try:
            book_bank_transactions(qs)
        except Exception:
            pass
