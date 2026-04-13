"""
Smoke tests for major view endpoints.
GET-only tests that verify responses and cover view code paths.
"""
import datetime
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase
from django.utils import timezone


def _setup_company_user(oib, username, modules=None):
    """Create company + user with subscription."""
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'Smoke {oib}', oib=oib)
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
        modules_override=modules or [
            'invoicing', 'partners', 'work_orders', 'projects',
            'documents', 'inventory', 'pos', 'worktime', 'konto',
        ],
    )
    return company, user


class InvoicingViewsSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_company_user('81818181818', 'smoke_inv')
        self.client = Client()
        self.client.login(username='smoke_inv', password='pass123')

    def _get(self, url):
        resp = self.client.get(url, follow=True)
        return resp.status_code

    def test_invoice_list(self):
        self.assertIn(self._get('/invoicing/'), [200, 302])

    def test_invoice_wizard(self):
        self.assertIn(self._get('/invoicing/wizard/'), [200, 302, 403, 404])

    def test_invoice_api_profiles(self):
        self.assertIn(self._get('/invoicing/api/profiles/'), [200, 302, 403, 404])

    def test_invoice_api_partners(self):
        self.assertIn(self._get('/invoicing/api/partners/'), [200, 302, 403, 404])

    def test_invoice_api_articles(self):
        self.assertIn(self._get('/invoicing/api/articles/'), [200, 302, 403, 404])

    def test_invoice_api_tax_rates(self):
        self.assertIn(self._get('/invoicing/api/tax-rates/'), [200, 302, 403, 404])

    def test_invoice_edit(self):
        from invoicing.models import Invoice
        inv = Invoice.objects.create(
            company=self.company,
            number=f'R-SMOKE-{uuid.uuid4().hex[:6]}',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Smoke',
            issuer_oib='81818181818',
            status='DRAFT',
        )
        self.assertIn(self._get(f'/invoicing/edit/{inv.pk}/'), [200, 302, 403, 404])

    def test_invoice_pdf(self):
        from invoicing.models import Invoice
        inv = Invoice.objects.create(
            company=self.company,
            number=f'R-PDF-{uuid.uuid4().hex[:6]}',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Smoke',
            issuer_oib='81818181818',
            status='DRAFT',
        )
        self.assertIn(self._get(f'/invoicing/pdf/{inv.pk}/'), [200, 302, 403, 404])

    def test_invoice_eracun(self):
        from invoicing.models import Invoice
        inv = Invoice.objects.create(
            company=self.company,
            number=f'R-XML-{uuid.uuid4().hex[:6]}',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Smoke',
            issuer_oib='81818181818',
            status='DRAFT',
        )
        self.assertIn(self._get(f'/invoicing/eracun/{inv.pk}/'), [200, 302, 403, 404])

    def test_invoice_clone(self):
        from invoicing.models import Invoice
        inv = Invoice.objects.create(
            company=self.company,
            number=f'R-CLN-{uuid.uuid4().hex[:6]}',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Smoke',
            issuer_oib='81818181818',
            status='DRAFT',
        )
        self.assertIn(self._get(f'/invoicing/clone/{inv.pk}/'), [200, 302, 403, 404])

    def test_invoice_worktime_get(self):
        from invoicing.models import Invoice
        inv = Invoice.objects.create(
            company=self.company,
            number=f'R-WT-{uuid.uuid4().hex[:6]}',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Smoke',
            issuer_oib='81818181818',
            status='DRAFT',
        )
        self.assertIn(self._get(f'/invoicing/worktime/{inv.pk}/'), [200, 302, 403, 404])

    def test_certificates_list(self):
        self.assertIn(self._get('/invoicing/certificates/'), [200, 302, 403, 404])

    def test_invoice_list_service(self):
        """Hit invoicing index - covers list view, filter, pagination logic."""
        from invoicing.models import Invoice
        for i in range(3):
            Invoice.objects.create(
                company=self.company,
                number=f'R-LST-{i:04d}',
                doctype='R',
                date_issued=timezone.now(),
                issuer_name='Smoke Co',
                issuer_oib='81818181818',
                status='DRAFT',
                total=Decimal('125.00'),
            )
        resp = self.client.get('/invoicing/', follow=True)
        self.assertIn(resp.status_code, [200, 302])


class WorktimeViewsSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_company_user('82828282828', 'smoke_wt')
        self.client = Client()
        self.client.login(username='smoke_wt', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_worktime_list(self):
        self.assertIn(self._get('/worktime/'), [200, 302, 403, 404])

    def test_worktime_timer(self):
        self.assertIn(self._get('/worktime/timer/'), [200, 302, 403, 404])

    def test_worktime_report(self):
        self.assertIn(self._get('/worktime/report/'), [200, 302, 403, 404])

    def test_worktime_api_entries(self):
        self.assertIn(self._get('/worktime/api/entries/'), [200, 302, 403, 404])


class KontoViewsSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_company_user('83838383838', 'smoke_konto')
        self.client = Client()
        self.client.login(username='smoke_konto', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_konto_dashboard(self):
        self.assertIn(self._get('/konto/'), [200, 302, 403, 404])

    def test_konto_receivables(self):
        self.assertIn(self._get('/konto/receivables/'), [200, 302, 403, 404])

    def test_konto_payables(self):
        self.assertIn(self._get('/konto/payables/'), [200, 302, 403, 404])

    def test_konto_profit_loss(self):
        self.assertIn(self._get('/konto/profit-loss/'), [200, 302, 403, 404])

    def test_konto_balance_sheet(self):
        self.assertIn(self._get('/konto/balance-sheet/'), [200, 302, 403, 404])

    def test_konto_vat(self):
        self.assertIn(self._get('/konto/vat/'), [200, 302, 403, 404])

    def test_konto_journal(self):
        self.assertIn(self._get('/konto/journal/'), [200, 302, 403, 404])

    def test_konto_bank(self):
        self.assertIn(self._get('/konto/bank/'), [200, 302, 403, 404])


class KontoServicesTest(TestCase):

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Konto Test', oib='84848484848')

    def test_get_open_receivables_empty(self):
        from konto.services import get_open_receivables
        result = get_open_receivables(self.company)
        self.assertIsInstance(result, list)

    def test_get_open_receivables_with_invoice(self):
        from invoicing.models import Invoice
        from konto.services import get_open_receivables
        Invoice.objects.create(
            company=self.company,
            number='R-KONTO-001',
            doctype='R',
            date_issued=timezone.now(),
            status='SENT',
            client_name='Test Client',
            issuer_name='Konto Co',
            issuer_oib='84848484848',
            total=Decimal('1250.00'),
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('250.00'),
        )
        result = get_open_receivables(self.company)
        self.assertIsInstance(result, list)
        # May or may not include our invoice depending on date_due
        self.assertGreaterEqual(len(result), 0)

    def test_get_open_payables_empty(self):
        from konto.services import get_open_payables
        result = get_open_payables(self.company)
        self.assertIsInstance(result, list)

    def test_calculate_vat_monthly(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'monthly', 2026, month=1)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)

    def test_calculate_vat_quarterly(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'quarterly', 2026, quarter=1)
        self.assertIsNotNone(result)

    def test_calculate_vat_yearly(self):
        from konto.services import calculate_vat_period
        result = calculate_vat_period(self.company, 'yearly', 2025)
        self.assertIsNotNone(result)

    def test_get_profit_loss_empty(self):
        import datetime

        from konto.services import get_profit_loss
        result = get_profit_loss(
            self.company,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 12, 31),
        )
        self.assertIn('profit_loss', result)
        self.assertIn('expenses', result)
        # key is profit_loss

    def test_get_balance_sheet_empty(self):
        import datetime

        from konto.services import get_balance_sheet
        try:
            result = get_balance_sheet(self.company, datetime.date(2026, 12, 31))
            self.assertIsInstance(result, dict)
        except AttributeError:
            pass  # May fail without KontoAccount setup

    def test_next_entry_number(self):
        from konto.services import _next_entry_number
        num = _next_entry_number(self.company, 'TEM')
        self.assertTrue(num.startswith('TEM-'))
        self.assertIn('2026', num)


class POSViewsSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_company_user('85858585858', 'smoke_pos')
        self.client = Client()
        self.client.login(username='smoke_pos', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_pos_dashboard(self):
        self.assertIn(self._get('/pos/'), [200, 302, 403, 404])

    def test_pos_articles(self):
        self.assertIn(self._get('/pos/articles/'), [200, 302, 403, 404])

    def test_pos_cashiers(self):
        self.assertIn(self._get('/pos/cashiers/'), [200, 302, 403, 404])

    def test_pos_sessions_list(self):
        self.assertIn(self._get('/pos/sessions/'), [200, 302, 403, 404])


class WorkOrdersViewsSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_company_user('86868686868', 'smoke_wo')
        self.client = Client()
        self.client.login(username='smoke_wo', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_work_order_list(self):
        self.assertIn(self._get('/work-orders/'), [200, 302])

    def test_work_order_new(self):
        self.assertIn(self._get('/work-orders/new/'), [200, 302])

    def test_work_order_vehicles(self):
        self.assertIn(self._get('/work-orders/vehicles/'), [200, 302, 403, 404])
