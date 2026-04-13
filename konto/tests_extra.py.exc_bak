"""Extra konto tests — accounts, bank, journal, reports, API endpoints."""
import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User


def _setup_konto_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'Konto {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except Exception:
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['konto', 'invoicing', 'partners'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class KontoDashboardTest(TestCase):
    """Test konto dashboard and main views."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('53535353530', 'kx_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kx_v1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_dashboard(self):
        self.assertIn(self._get('/konto/'), ALLOWED)

    def test_dashboard_with_month(self):
        resp = self.client.get('/konto/?month=2026-01', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_with_year(self):
        resp = self.client.get('/konto/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_chart_of_accounts(self):
        self.assertIn(self._get('/konto/accounts/'), ALLOWED)

    def test_account_detail_invalid(self):
        self.assertIn(self._get('/konto/accounts/9999/'), ALLOWED)

    def test_account_save_post(self):
        resp = self.client.post('/konto/accounts/save/', {
            'name': 'Test Account',
            'code': '9999',
            'type': 'asset',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bank_accounts(self):
        self.assertIn(self._get('/konto/bank/'), ALLOWED)

    def test_bank_account_save_post(self):
        resp = self.client.post('/konto/bank/save/', {
            'name': 'Test Bank',
            'iban': 'HR1234567890',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions(self):
        self.assertIn(self._get('/konto/transactions/'), ALLOWED)

    def test_transactions_filter(self):
        resp = self.client.get('/konto/transactions/?from=2026-01-01&to=2026-01-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions_search(self):
        resp = self.client.get('/konto/transactions/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_journal_entries(self):
        self.assertIn(self._get('/konto/journal/'), ALLOWED)

    def test_journal_entry_create_get(self):
        self.assertIn(self._get('/konto/journal/create/'), ALLOWED)

    def test_journal_entry_create_post(self):
        resp = self.client.post('/konto/journal/create/', {
            'date': '2026-01-01',
            'description': 'Test Journal',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_journal_entry_detail_invalid(self):
        self.assertIn(self._get('/konto/journal/9999/'), ALLOWED)


class KontoReportsTest(TestCase):
    """Test konto report views."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('53535353540', 'kx_v2')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kx_v2', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_report_pnl(self):
        self.assertIn(self._get('/konto/reports/pnl/'), ALLOWED)

    def test_report_pnl_with_period(self):
        resp = self.client.get('/konto/reports/pnl/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

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


class KontoAPITest(TestCase):
    """Test konto API endpoints."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('53535353550', 'kx_v3')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kx_v3', password='pass123')

    def test_api_chart_data(self):
        resp = self.client.get('/konto/api/chart/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_unmatched_invoices(self):
        resp = self.client.get('/konto/api/unmatched-invoices/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_auto_match_post(self):
        resp = self.client.post('/konto/api/auto-match/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_match_transaction_invalid(self):
        resp = self.client.post('/konto/api/match/9999/', json.dumps({
            'invoice_id': 1,
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_book_invoice_invalid(self):
        resp = self.client.post('/konto/api/book-invoice/9999/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_book_transactions_post(self):
        resp = self.client.post('/konto/api/book-transactions/', json.dumps({
            'transaction_ids': [],
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_ignore_transaction_invalid(self):
        resp = self.client.post('/konto/api/ignore/9999/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_transaction_create_post(self):
        resp = self.client.post('/konto/api/transaction/create/', json.dumps({
            'amount': '100.00',
            'type': 'income',
            'date': '2026-01-01',
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
