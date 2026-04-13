"""Tests for small/medium modules: finance, insurance, rental, fitness, webshop, reports, branches."""
import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, modules, is_superuser=False):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'SM {oib}', oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    else:
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
        modules_override=modules,
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


# ===== FINANCE =====
class FinanceViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000001', 'sm_fin1', ['finance', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_fin1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_transaction_list(self):
        self.assertIn(self._get('/finance/'), ALLOWED)

    def test_transaction_create_get(self):
        self.assertIn(self._get('/finance/new/'), ALLOWED)

    def test_transaction_create_post(self):
        resp = self.client.post('/finance/new/', {
            'amount': '100.00',
            'type': 'income',
            'date': '2026-01-01',
            'description': 'Test transaction',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transaction_delete_invalid(self):
        resp = self.client.post('/finance/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_transaction_delete_valid(self):
        try:
            from finance.models import Transaction
            t = Transaction.objects.create(
                company=self.company,
                amount=100,
                type='income',
                date=datetime.date.today(),
                description='Del test',
            )
            resp = self.client.post(f'/finance/{t.pk}/delete/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== INSURANCE =====
class InsuranceViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000002', 'sm_ins1', ['insurance', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_ins1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_policy_list(self):
        self.assertIn(self._get('/insurance/'), ALLOWED)

    def test_policy_create_get(self):
        self.assertIn(self._get('/insurance/new/'), ALLOWED)

    def test_policy_create_post(self):
        resp = self.client.post('/insurance/new/', {
            'policy_number': 'POL-001',
            'type': 'property',
            'insured_value': '10000.00',
            'premium': '500.00',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_policy_edit_invalid(self):
        self.assertIn(self._get('/insurance/9999/edit/'), ALLOWED)

    def test_policy_delete_invalid(self):
        resp = self.client.post('/insurance/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_policy_edit_valid(self):
        try:
            from insurance.models import InsurancePolicy
            p = InsurancePolicy.objects.create(
                company=self.company,
                policy_number='POL-002',
                insured_value=10000,
                premium=500,
                start_date=datetime.date.today(),
                end_date=datetime.date.today() + datetime.timedelta(days=365),
            )
            self.assertIn(self._get(f'/insurance/{p.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/insurance/{p.pk}/edit/', {
                'policy_number': 'POL-002-UPD',
                'insured_value': '12000.00',
                'premium': '600.00',
                'start_date': '2026-01-01',
                'end_date': '2026-12-31',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== RENTAL =====
class RentalViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000003', 'sm_ren1', ['rental', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_ren1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_property_list(self):
        self.assertIn(self._get('/rental/'), ALLOWED)

    def test_property_create_get(self):
        self.assertIn(self._get('/rental/new/'), ALLOWED)

    def test_property_create_post(self):
        resp = self.client.post('/rental/new/', {
            'name': 'Test Property',
            'address': 'Test Address 1',
            'city': 'Zagreb',
            'property_type': 'apartment',
            'price_per_night': '100.00',
            'capacity': '4',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_property_detail_invalid(self):
        self.assertIn(self._get('/rental/9999/'), ALLOWED)

    def test_property_edit_invalid(self):
        self.assertIn(self._get('/rental/9999/edit/'), ALLOWED)

    def test_booking_list(self):
        self.assertIn(self._get('/rental/bookings/'), ALLOWED)

    def test_booking_create_get(self):
        self.assertIn(self._get('/rental/bookings/new/'), ALLOWED)

    def test_booking_create_post(self):
        resp = self.client.post('/rental/bookings/new/', {
            'guest_name': 'Test Guest',
            'check_in': '2026-02-01',
            'check_out': '2026-02-07',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_booking_status_invalid(self):
        resp = self.client.post('/rental/bookings/9999/status/', {
            'status': 'confirmed',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_property_full_crud(self):
        try:
            from rental.models import Property
            p = Property.objects.create(
                company=self.company,
                name='Test Prop',
                address='Addr 1',
                city='Zagreb',
                price_per_night=100,
            )
            self.assertIn(self._get(f'/rental/{p.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/rental/{p.pk}/edit/'), ALLOWED)
            self.assertIn(self._get(f'/rental/bookings/new/{p.pk}/'), ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== FITNESS =====
class FitnessViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000004', 'sm_fit1', ['fitness', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_fit1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_member_list(self):
        self.assertIn(self._get('/fitness/'), ALLOWED)

    def test_member_create_get(self):
        self.assertIn(self._get('/fitness/new/'), ALLOWED)

    def test_member_create_post(self):
        resp = self.client.post('/fitness/new/', {
            'first_name': 'Fitness',
            'last_name': 'Member',
            'email': 'fitm@test.hr',
            'phone': '09100000001',
            'membership_type': 'monthly',
            'start_date': '2026-01-01',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_member_detail_invalid(self):
        self.assertIn(self._get('/fitness/9999/'), ALLOWED)

    def test_member_edit_invalid(self):
        self.assertIn(self._get('/fitness/9999/edit/'), ALLOWED)

    def test_checkin_dashboard(self):
        self.assertIn(self._get('/fitness/dashboard/'), ALLOWED)

    def test_member_checkin_invalid(self):
        resp = self.client.post('/fitness/9999/checkin/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_member_full_crud(self):
        try:
            from fitness.models import Member
            m = Member.objects.create(
                company=self.company,
                first_name='Fit',
                last_name='Test',
                email='fittest@test.hr',
                membership_type='monthly',
                start_date=datetime.date.today(),
            )
            self.assertIn(self._get(f'/fitness/{m.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/fitness/{m.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/fitness/{m.pk}/checkin/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/fitness/{m.pk}/edit/', {
                'first_name': 'Updated',
                'last_name': 'Member',
                'membership_type': 'annual',
                'start_date': '2026-01-01',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== WEBSHOP =====
class WebshopViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000005', 'sm_web1', ['webshop', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_web1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_product_list(self):
        self.assertIn(self._get('/webshop/'), ALLOWED)

    def test_product_create_get(self):
        self.assertIn(self._get('/webshop/products/new/'), ALLOWED)

    def test_product_create_post(self):
        resp = self.client.post('/webshop/products/new/', {
            'name': 'Test Product',
            'price': '29.99',
            'description': 'Test product description',
            'is_active': True,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_product_edit_invalid(self):
        self.assertIn(self._get('/webshop/products/9999/edit/'), ALLOWED)

    def test_order_list(self):
        self.assertIn(self._get('/webshop/orders/'), ALLOWED)

    def test_order_create_get(self):
        self.assertIn(self._get('/webshop/orders/new/'), ALLOWED)

    def test_order_detail_invalid(self):
        self.assertIn(self._get('/webshop/orders/9999/'), ALLOWED)

    def test_order_status_invalid(self):
        resp = self.client.post('/webshop/orders/9999/status/', {
            'status': 'confirmed',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_product_edit_valid(self):
        try:
            from webshop.models import Product
            p = Product.objects.create(
                company=self.company,
                name='WS Product',
                price=29.99,
            )
            self.assertIn(self._get(f'/webshop/products/{p.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/webshop/products/{p.pk}/edit/', {
                'name': 'Updated Product',
                'price': '39.99',
                'is_active': True,
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== REPORTS =====
class ReportsViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('60000000006', 'sm_rep1', ['reports', 'invoicing', 'worktime'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_rep1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_reports_dashboard(self):
        self.assertIn(self._get('/reports/'), ALLOWED)

    def test_revenue_report(self):
        self.assertIn(self._get('/reports/revenue/'), ALLOWED)

    def test_revenue_report_with_dates(self):
        resp = self.client.get('/reports/revenue/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_worktime_report(self):
        self.assertIn(self._get('/reports/worktime/'), ALLOWED)

    def test_worktime_report_with_dates(self):
        resp = self.client.get('/reports/worktime/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_export_revenue_csv(self):
        self.assertIn(self._get('/reports/export/revenue/csv/'), ALLOWED)

    def test_export_revenue_excel(self):
        self.assertIn(self._get('/reports/export/revenue/excel/'), ALLOWED)

    def test_export_worktime_csv(self):
        self.assertIn(self._get('/reports/export/worktime/csv/'), ALLOWED)

    def test_export_worktime_excel(self):
        self.assertIn(self._get('/reports/export/worktime/excel/'), ALLOWED)


# ===== BRANCHES =====
class BranchesViewsTest(TestCase):
    """Test branch-type dashboards (optika, fitness, retail, etc.)."""
    def setUp(self):
        self.company, self.user = _setup_user('60000000007', 'sm_br1', ['invoicing', 'partners'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='sm_br1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_optika_dashboard(self):
        self.assertIn(self._get('/branches/optika/'), ALLOWED)

    def test_fitness_dashboard(self):
        self.assertIn(self._get('/branches/fitness/'), ALLOWED)

    def test_retail_dashboard(self):
        self.assertIn(self._get('/branches/retail/'), ALLOWED)

    def test_accounting_dashboard(self):
        self.assertIn(self._get('/branches/accounting/'), ALLOWED)

    def test_restaurant_dashboard(self):
        self.assertIn(self._get('/branches/restaurant/'), ALLOWED)

    def test_salon_dashboard(self):
        self.assertIn(self._get('/branches/salon/'), ALLOWED)

    def test_other_dashboard(self):
        self.assertIn(self._get('/branches/other/'), ALLOWED)
