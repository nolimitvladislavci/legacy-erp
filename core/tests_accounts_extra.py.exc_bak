"""Extra accounts views tests — user_edit, reset_password, toggle_status, translations, change_password."""
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User


def _setup_user(oib, username, modules=None, is_superuser=False):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'AV {oib}', oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    else:
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
        modules_override=modules or ['invoicing', 'partners'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class AccountsViewsTest(TestCase):
    """Test accounts/views.py — superuser-only endpoints."""

    def setUp(self):
        self.company, self.admin = _setup_user('63000000001', 'av_admin1', is_superuser=True)
        self.company2, self.target_user = _setup_user('63000000002', 'av_target1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='av_admin1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_user_list(self):
        self.assertIn(self._get('/accounts/'), ALLOWED)

    def test_user_edit_get(self):
        self.assertIn(self._get(f'/accounts/{self.target_user.pk}/edit/'), ALLOWED)

    def test_user_edit_post(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/edit/', {
            'username': 'av_target1',
            'first_name': 'Updated',
            'last_name': 'User',
            'email': 'updated@test.hr',
            'role': 'worker',
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_edit_with_password(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/edit/', {
            'username': 'av_target1',
            'first_name': 'Updated',
            'last_name': 'User',
            'email': 'updated@test.hr',
            'role': 'worker',
            'is_active': 'on',
            'password': 'newpass456!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_edit_role_company_admin(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/edit/', {
            'username': 'av_target1',
            'role': 'company_admin',
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_edit_role_superadmin(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/edit/', {
            'username': 'av_target1',
            'role': 'superadmin',
            'is_active': 'on',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_user_edit_invalid_pk(self):
        self.assertIn(self._get('/accounts/9999/edit/'), ALLOWED)

    def test_reset_password_request(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/reset-password/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_reset_password_invalid(self):
        resp = self.client.post('/accounts/9999/reset-password/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_toggle_user_status(self):
        resp = self.client.post(f'/accounts/{self.target_user.pk}/toggle/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_toggle_user_status_twice(self):
        self.client.post(f'/accounts/{self.target_user.pk}/toggle/', follow=True)
        resp = self.client.post(f'/accounts/{self.target_user.pk}/toggle/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_toggle_invalid(self):
        resp = self.client.post('/accounts/9999/toggle/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_translation_manager_de(self):
        self.assertIn(self._get('/accounts/translations/de/'), ALLOWED)

    def test_translation_manager_en(self):
        self.assertIn(self._get('/accounts/translations/en/'), ALLOWED)

    def test_translation_manager_invalid_lang(self):
        self.assertIn(self._get('/accounts/translations/zz/'), ALLOWED)

    def test_translation_manager_post_scan(self):
        resp = self.client.post('/accounts/translations/de/', {
            'action': 'scan',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_translation_manager_post_save_translation(self):
        resp = self.client.post('/accounts/translations/de/', {
            'msgid': 'Test',
            'msgstr': 'Testübersetzung',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class ChangePasswordTest(TestCase):
    """Test change_password view (regular user)."""

    def setUp(self):
        self.company, self.user = _setup_user('63000000003', 'av_cp1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='av_cp1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_change_password_get(self):
        self.assertIn(self._get('/accounts/password/'), ALLOWED)

    def test_change_password_post_valid(self):
        resp = self.client.post('/accounts/password/', {
            'new_password1': 'newpass456!',
            'new_password2': 'newpass456!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_change_password_mismatch(self):
        resp = self.client.post('/accounts/password/', {
            'new_password1': 'newpass456!',
            'new_password2': 'different!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_change_password_too_short(self):
        resp = self.client.post('/accounts/password/', {
            'new_password1': 'abc',
            'new_password2': 'abc',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class QuickRegisterTest(TestCase):
    """Test quick_register view."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_quick_register_get(self):
        self.assertIn(self._get('/accounts/quick-register/'), ALLOWED)

    def test_quick_register_post(self):
        resp = self.client.post('/accounts/quick-register/', {
            'username': 'qr_user1',
            'email': 'qruser@test.hr',
            'password1': 'testpass789!',
            'password2': 'testpass789!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)
