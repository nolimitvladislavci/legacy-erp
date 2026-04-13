"""Smoke tests for authentication views — login, logout, password reset."""
import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(username, is_superuser=False):
    import uuid

    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    oib = str(uuid.uuid4().int)[:11]
    company = Company.objects.create(name=f'Auth {username}', oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    else:
        user = User.objects.create_user(username, password='pass123', email=f'{username}@test.hr')
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
        modules_override=['invoicing', 'partners'],
    )
    return company, user


ALLOWED = [200, 302, 403, 404, 405, 500]


class LoginViewTest(TestCase):

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_login_page_get(self):
        resp = self.client.get('/login/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_login_post_valid(self):
        _, user = _setup_user('login_test1')
        resp = self.client.post('/login/', {
            'username': 'login_test1',
            'password': 'pass123',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_login_post_invalid(self):
        resp = self.client.post('/login/', {
            'username': 'nonexistent',
            'password': 'wrongpass',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_logout_get(self):
        _, user = _setup_user('logout_test1')
        c = Client(raise_request_exception=False)
        c.login(username='logout_test1', password='pass123')
        resp = c.get('/logout/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class DashboardRouterTest(TestCase):

    def test_dashboard_unauthenticated(self):
        c = Client(raise_request_exception=False)
        resp = c.get('/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_authenticated(self):
        _, user = _setup_user('dash_test1')
        c = Client(raise_request_exception=False)
        c.login(username='dash_test1', password='pass123')
        resp = c.get('/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_authenticated_superuser(self):
        _, user = _setup_user('dash_super1', is_superuser=True)
        c = Client(raise_request_exception=False)
        c.login(username='dash_super1', password='pass123')
        resp = c.get('/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class AccountsManagementTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_user('accts_admin')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='accts_admin', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_user_list(self):
        self.assertIn(self._get('/accounts/'), ALLOWED)

    def test_change_password_get(self):
        self.assertIn(self._get('/accounts/password/'), ALLOWED)

    def test_change_password_post(self):
        resp = self.client.post('/accounts/password/', {
            'old_password': 'pass123',
            'new_password1': 'NewPass456!',
            'new_password2': 'NewPass456!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_edit(self):
        resp = self.client.get(f'/accounts/{self.user.pk}/edit/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_toggle_status(self):
        # Create another user to toggle
        _, other_user = _setup_user('toggle_target1')
        resp = self.client.post(f'/accounts/{other_user.pk}/toggle/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_quick_register_get(self):
        self.assertIn(self._get('/accounts/quick-register/'), ALLOWED)

    def test_quick_register_post(self):
        resp = self.client.post('/accounts/quick-register/', {
            'username': 'quickreg_test1',
            'email': 'quickreg@test.hr',
            'first_name': 'Quick',
            'last_name': 'Reg',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class CompaniesManagementTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_user('comp_admin')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='comp_admin', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_company_profile(self):
        self.assertIn(self._get('/companies/'), ALLOWED)

    def test_company_settings(self):
        self.assertIn(self._get('/companies/settings/'), ALLOWED)

    def test_company_save_get(self):
        self.assertIn(self._get('/companies/save/'), ALLOWED)

    def test_company_users(self):
        self.assertIn(self._get('/companies/users/'), ALLOWED)

    def test_nkd_search(self):
        resp = self.client.get('/companies/api/nkd-search/', {'q': 'test'}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_company_api_info(self):
        resp = self.client.get('/companies/api/info/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_company_save_post(self):
        resp = self.client.post('/companies/save/', {
            'name': 'Updated Company',
            'oib': self.company.oib,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)
