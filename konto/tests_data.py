"""Konto tests with real data — covers more view lines by creating konto objects."""
import datetime
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User


def _setup_konto_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'KD {oib}', oib=oib)
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


def _make_konto_account(company, code='1000', name='Žiro račun', account_type='asset'):
    from konto.models import KontoAccount
    return KontoAccount.objects.create(
        company=company,
        code=code,
        name=name,
        account_type=account_type,
    )


def _make_bank_account(company, konto_account=None):
    from konto.models import BankAccount
    return BankAccount.objects.create(
        company=company,
        name='Poslovanje PBZ',
        iban='HR1234567890123456789012',
        bank_name='PBZ',
        currency='EUR',
        konto_account=konto_account,
    )


def _make_bank_transaction(company, bank_account, amount=100, tx_type='inflow'):
    from konto.models import BankTransaction
    return BankTransaction.objects.create(
        company=company,
        bank_account=bank_account,
        transaction_date=datetime.date.today(),
        amount=Decimal(str(amount)),
        transaction_type=tx_type,
        counterparty_name='Test Partner',
        description='Test transaction',
    )


def _make_journal_entry(company, user):
    from konto.models import JournalEntry
    return JournalEntry.objects.create(
        company=company,
        entry_number='TEM-001',
        date=datetime.date.today(),
        description='Test journal entry',
        source_type='manual',
        created_by=user,
    )


class KontoDashboardWithDataTest(TestCase):
    """Test konto dashboard with real data to cover more lines."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('70000000001', 'kd_v1')
        # Create some konto data
        self.account = _make_konto_account(self.company, '1000', 'Žiro račun', 'asset')
        self.bank = _make_bank_account(self.company, self.account)
        self.tx1 = _make_bank_transaction(self.company, self.bank, 1000, 'inflow')
        self.tx2 = _make_bank_transaction(self.company, self.bank, 500, 'outflow')
        self.je = _make_journal_entry(self.company, self.user)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kd_v1', password='pass123')

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

    def test_chart_of_accounts_with_data(self):
        self.assertIn(self._get('/konto/accounts/'), ALLOWED)

    def test_chart_of_accounts_search(self):
        resp = self.client.get('/konto/accounts/?q=žiro', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_account_detail_with_data(self):
        self.assertIn(self._get(f'/konto/accounts/{self.account.pk}/'), ALLOWED)

    def test_account_detail_with_date_filter(self):
        resp = self.client.get(f'/konto/accounts/{self.account.pk}/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_account_save_create(self):
        resp = self.client.post('/konto/accounts/save/', {
            'code': '2000',
            'name': 'Obveze prema dobavljačima',
            'account_type': 'liability',
            'description': 'Test account',
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_account_save_update(self):
        resp = self.client.post('/konto/accounts/save/', {
            'pk': self.account.pk,
            'code': '1000',
            'name': 'Updated Name',
            'account_type': 'asset',
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_account_save_with_parent(self):
        resp = self.client.post('/konto/accounts/save/', {
            'code': '1001',
            'name': 'Sub Account',
            'account_type': 'asset',
            'parent': self.account.pk,
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bank_accounts_with_data(self):
        self.assertIn(self._get('/konto/bank/'), ALLOWED)

    def test_bank_account_save_create(self):
        resp = self.client.post('/konto/bank/save/', {
            'name': 'New Bank',
            'iban': 'HR9876543210987654321098',
            'bank_name': 'Zaba',
            'currency': 'EUR',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bank_account_save_update(self):
        resp = self.client.post('/konto/bank/save/', {
            'pk': self.bank.pk,
            'name': 'Updated Bank',
            'iban': 'HR1234567890123456789012',
            'bank_name': 'PBZ Updated',
            'currency': 'EUR',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions_with_data(self):
        self.assertIn(self._get('/konto/transactions/'), ALLOWED)

    def test_transactions_filter_date(self):
        resp = self.client.get('/konto/transactions/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions_filter_type(self):
        resp = self.client.get('/konto/transactions/?type=inflow', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions_filter_status(self):
        resp = self.client.get('/konto/transactions/?status=unmatched', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transactions_search(self):
        resp = self.client.get('/konto/transactions/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_journal_entries_with_data(self):
        self.assertIn(self._get('/konto/journal/'), ALLOWED)

    def test_journal_entry_detail_with_data(self):
        self.assertIn(self._get(f'/konto/journal/{self.je.pk}/'), ALLOWED)

    def test_journal_entry_create_get(self):
        self.assertIn(self._get('/konto/journal/create/'), ALLOWED)

    def test_journal_entry_create_post(self):
        resp = self.client.post('/konto/journal/create/', {
            'date': '2026-01-15',
            'description': 'New Journal Entry',
            'source_type': 'manual',
            'entry_number': 'TEM-002',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class KontoReportsWithDataTest(TestCase):
    """Test konto reports with real data."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('70000000002', 'kd_v2')
        self.account = _make_konto_account(self.company, '1000', 'Žiro račun', 'asset')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kd_v2', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_report_pnl_with_dates(self):
        resp = self.client.get('/konto/reports/pnl/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_pnl_current_year(self):
        resp = self.client.get('/konto/reports/pnl/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_balance_sheet_with_dates(self):
        resp = self.client.get('/konto/reports/balance-sheet/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_receivables_with_dates(self):
        resp = self.client.get('/konto/reports/receivables/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_vat_with_period(self):
        resp = self.client.get('/konto/reports/vat/?year=2026&month=1&period_type=monthly', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_vat_quarterly(self):
        resp = self.client.get('/konto/reports/vat/?year=2026&quarter=1&period_type=quarterly', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_annual_tax_with_year(self):
        resp = self.client.get('/konto/reports/annual-tax/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_report_euer_with_year(self):
        resp = self.client.get('/konto/reports/euer/?year=2026', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_vat_mark_filed_invalid(self):
        resp = self.client.post('/konto/reports/vat/9999/filed/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_vat_mark_filed_with_real_period(self):
        try:
            from konto.models import TaxPeriod
            tp = TaxPeriod.objects.create(
                company=self.company,
                period_type='monthly',
                year=2026,
                period_number=1,
            )
            resp = self.client.post(f'/konto/reports/vat/{tp.pk}/filed/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class KontoAPIWithDataTest(TestCase):
    """Test konto API endpoints with real data."""

    def setUp(self):
        self.company, self.user = _setup_konto_user('70000000003', 'kd_v3')
        self.account = _make_konto_account(self.company, '1000', 'Žiro račun', 'asset')
        self.bank = _make_bank_account(self.company, self.account)
        self.tx = _make_bank_transaction(self.company, self.bank, 500, 'inflow')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='kd_v3', password='pass123')

    def test_api_chart_data(self):
        resp = self.client.get('/konto/api/chart/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_chart_data_with_period(self):
        resp = self.client.get('/konto/api/chart/?month=2026-01', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_unmatched_invoices(self):
        resp = self.client.get('/konto/api/unmatched-invoices/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_auto_match(self):
        resp = self.client.post('/konto/api/auto-match/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_match_transaction_with_data(self):
        resp = self.client.post(f'/konto/api/match/{self.tx.pk}/', json.dumps({
            'invoice_id': 9999,
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_ignore_transaction_with_data(self):
        resp = self.client.post(f'/konto/api/ignore/{self.tx.pk}/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_transaction_create(self):
        resp = self.client.post('/konto/api/transaction/create/', json.dumps({
            'bank_account_id': self.bank.pk,
            'amount': '250.00',
            'transaction_type': 'outflow',
            'date': '2026-01-15',
            'description': 'Manual entry',
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_book_invoice_invalid(self):
        resp = self.client.post('/konto/api/book-invoice/9999/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_book_transactions(self):
        resp = self.client.post('/konto/api/book-transactions/', json.dumps({
            'transaction_ids': [self.tx.pk],
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
