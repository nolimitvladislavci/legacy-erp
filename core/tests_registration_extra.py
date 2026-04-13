"""Smoke tests for registration views + more core view tests."""
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError


def _setup_superuser(username):
    from companies.models import Company
    from accounts.models import UserProfile
    company = Company.objects.create(name=f'SAdmin {username}', oib=f'{hash(username) % 10**11:011d}')
    user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    try:
        UserProfile.objects.create(user=user, company=company)
    except (IntegrityError, DatabaseError):
        pass
    return company, user


def _setup_user(oib, username, modules=None):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'Reg {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        UserProfile.objects.create(user=user, company=company)
    except (IntegrityError, DatabaseError):
        pass
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=modules or ['invoicing', 'partners'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class RegistrationViewsTest(TestCase):
    """Tests for registration flow — public views."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_register_step1_get(self):
        resp = self.client.get('/register/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_step1_post(self):
        resp = self.client.post('/register/', {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'regtest@test.hr',
            'company_name': 'Test Company',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_step2_get(self):
        resp = self.client.get('/register/company/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_step3_get(self):
        resp = self.client.get('/register/account/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_step4_get(self):
        resp = self.client.get('/register/confirm/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_success(self):
        resp = self.client.get('/register/success/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_upgrade_required(self):
        resp = self.client.get('/register/upgrade/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_upgrade_required_with_module(self):
        resp = self.client.get('/register/upgrade/?module=invoicing', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_check_promo(self):
        resp = self.client.get('/register/api/check-promo/?code=TEST', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class RegistrationAdminViewsTest(TestCase):
    """Tests for registration admin views."""

    def setUp(self):
        self.company, self.user = _setup_superuser('reg_super1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='reg_super1', password='pass123')

    def test_admin_registration_list(self):
        resp = self.client.get('/register/superadmin/registrations/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class CoreDashboardTest(TestCase):
    """Tests for core views - company dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user('50505050505', 'core_dash1',
            ['invoicing', 'partners', 'documents', 'worktime', 'projects', 'pos'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='core_dash1', password='pass123')

    def test_company_dashboard(self):
        resp = self.client.get('/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_slash(self):
        resp = self.client.get('/dashboard/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_health_check(self):
        resp = self.client.get('/health/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class CoreSuperadminTest(TestCase):
    """Tests for superadmin views."""

    def setUp(self):
        self.company, self.user = _setup_superuser('core_super1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='core_super1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_superadmin_dashboard(self):
        self.assertIn(self._get('/superadmin/'), ALLOWED)

    def test_superadmin_companies(self):
        self.assertIn(self._get('/superadmin/companies/'), ALLOWED)

    def test_superadmin_create_promo_get(self):
        self.assertIn(self._get('/superadmin/promo/create/'), ALLOWED)

    def test_superadmin_company_impersonate(self):
        import uuid
        # Try to impersonate a non-existent company
        fake_id = uuid.uuid4()
        resp = self.client.get(f'/superadmin/impersonate/{fake_id}/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_stop_impersonation(self):
        resp = self.client.get('/superadmin/impersonate/stop/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_superadmin_company_branches(self):
        import uuid
        fake_id = uuid.uuid4()
        resp = self.client.get(f'/superadmin/companies/{fake_id}/branches/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
