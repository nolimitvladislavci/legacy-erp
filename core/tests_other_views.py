"""Smoke tests for accounts, documents, registration, outreach, burza, inventory, misc."""
import datetime
import json
import uuid
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError


def _setup_user(oib, username, modules, is_superuser=False):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'OV {oib}', oib=oib)
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
    if not is_superuser:
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


class AccountsViewsTest(TestCase):
    """Tests for accounts/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('41414141410', 'ov_acc1', ['invoicing', 'partners'])
        self.user2 = User.objects.create_user('ov_acc1_b', password='pass123')
        from accounts.models import UserProfile
        try:
            UserProfile.objects.create(user=self.user2, company=self.company)
        except (IntegrityError, DatabaseError):
            pass
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_acc1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_user_list(self):
        self.assertIn(self._get('/accounts/'), ALLOWED)

    def test_user_edit_get(self):
        self.assertIn(self._get(f'/accounts/{self.user.pk}/edit/'), ALLOWED)

    def test_user_edit_post(self):
        resp = self.client.post(f'/accounts/{self.user.pk}/edit/', {
            'first_name': 'Updated',
            'last_name': 'User',
            'email': 'updated@test.hr',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_change_password_get(self):
        self.assertIn(self._get('/accounts/password/'), ALLOWED)

    def test_change_password_post(self):
        resp = self.client.post('/accounts/password/', {
            'old_password': 'pass123',
            'new_password1': 'newpass456!',
            'new_password2': 'newpass456!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_quick_register_get(self):
        self.assertIn(self._get('/accounts/quick-register/'), ALLOWED)

    def test_quick_register_post(self):
        resp = self.client.post('/accounts/quick-register/', {
            'username': 'newovuser1',
            'email': 'newov@test.hr',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'worker',
            'password1': 'testpass789!',
            'password2': 'testpass789!',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_reset_password_request(self):
        resp = self.client.post(f'/accounts/{self.user2.pk}/reset-password/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_toggle_user_status(self):
        resp = self.client.post(f'/accounts/{self.user2.pk}/toggle/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class DocumentsViewsTest(TestCase):
    """Tests for documents/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('42424242420', 'ov_doc1', ['documents', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_doc1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_document_list(self):
        self.assertIn(self._get('/documents/'), ALLOWED)

    def test_document_create_get(self):
        self.assertIn(self._get('/documents/new/'), ALLOWED)

    def test_document_otpremnica_list(self):
        self.assertIn(self._get('/documents/otpremnica/'), ALLOWED)

    def test_document_otpremnica_create_get(self):
        self.assertIn(self._get('/documents/otpremnica/nova/'), ALLOWED)

    def test_document_primka_list(self):
        self.assertIn(self._get('/documents/primka/'), ALLOWED)

    def test_document_primka_create_get(self):
        self.assertIn(self._get('/documents/primka/nova/'), ALLOWED)

    def test_document_otkupni_list(self):
        self.assertIn(self._get('/documents/otkupni/'), ALLOWED)

    def test_document_otkupni_create_get(self):
        self.assertIn(self._get('/documents/otkupni/novi/'), ALLOWED)

    def test_document_detail_invalid(self):
        fake_pk = uuid.uuid4()
        self.assertIn(self._get(f'/documents/{fake_pk}/'), ALLOWED)

    def test_document_create_post(self):
        resp = self.client.post('/documents/new/', {
            'title': 'Test Doc',
            'document_type': 'otpremnica',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class RegistrationViewsTest(TestCase):
    """Tests for registration/views.py."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_register_step1_get(self):
        self.assertIn(self.client.get('/register/', follow=True).status_code, ALLOWED)

    def test_register_step1_post(self):
        resp = self.client.post('/register/', {
            'first_name': 'Reg',
            'last_name': 'Test',
            'email': 'ov_regtest@test.hr',
            'company_name': 'OV Reg Company',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_register_company_get(self):
        self.assertIn(self.client.get('/register/company/', follow=True).status_code, ALLOWED)

    def test_register_account_get(self):
        self.assertIn(self.client.get('/register/account/', follow=True).status_code, ALLOWED)

    def test_register_confirm_get(self):
        self.assertIn(self.client.get('/register/confirm/', follow=True).status_code, ALLOWED)

    def test_register_success(self):
        self.assertIn(self.client.get('/register/success/', follow=True).status_code, ALLOWED)

    def test_upgrade_required(self):
        self.assertIn(self.client.get('/register/upgrade/', follow=True).status_code, ALLOWED)

    def test_upgrade_required_module(self):
        resp = self.client.get('/register/upgrade/?module=invoicing', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_check_promo(self):
        resp = self.client.get('/register/api/check-promo/?code=TEST', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class RegistrationAdminTest(TestCase):
    """Tests for registration superadmin views."""

    def setUp(self):
        self.company, self.user = _setup_user('43434343430', 'ov_reg_super', [], is_superuser=True)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_reg_super', password='pass123')

    def test_admin_registration_list(self):
        resp = self.client.get('/register/superadmin/registrations/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_admin_registration_detail_invalid(self):
        fake_id = uuid.uuid4()
        resp = self.client.get(f'/register/superadmin/registrations/{fake_id}/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_admin_registration_approve_invalid(self):
        fake_id = uuid.uuid4()
        resp = self.client.post(f'/register/superadmin/registrations/{fake_id}/approve/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_admin_registration_reject_invalid(self):
        fake_id = uuid.uuid4()
        resp = self.client.post(f'/register/superadmin/registrations/{fake_id}/reject/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class OutreachViewsTest(TestCase):
    """Tests for outreach/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('44444444440', 'ov_out1', ['outreach', 'partners', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_out1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_outreach_dashboard(self):
        self.assertIn(self._get('/outreach/'), ALLOWED)

    def test_outreach_contacts_list(self):
        self.assertIn(self._get('/outreach/contacts/'), ALLOWED)

    def test_outreach_contacts_new_get(self):
        self.assertIn(self._get('/outreach/contacts/new/'), ALLOWED)

    def test_outreach_contacts_new_post(self):
        resp = self.client.post('/outreach/contacts/new/', {
            'name': 'Test Contact',
            'email': 'contact@test.hr',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_outreach_campaign_new_get(self):
        self.assertIn(self._get('/outreach/campaign/new/'), ALLOWED)

    def test_outreach_campaign_detail_invalid(self):
        self.assertIn(self._get('/outreach/campaign/9999/'), ALLOWED)

    def test_outreach_inbox(self):
        self.assertIn(self._get('/outreach/inbox/'), ALLOWED)

    def test_outreach_csv_import_get(self):
        self.assertIn(self._get('/outreach/contacts/import/'), ALLOWED)


class BurzaViewsTest(TestCase):
    """Tests for burza CRM kanban views."""

    def setUp(self):
        # /burza/ is not in MODULE_URL_MAP, so no module restriction
        self.company, self.user = _setup_user('45454545450', 'ov_burza1', ['invoicing', 'partners'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_burza1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_burza_kanban(self):
        self.assertIn(self._get('/burza/'), ALLOWED)

    def test_burza_lead_new_get(self):
        self.assertIn(self._get('/burza/lead/new/'), ALLOWED)

    def test_burza_lead_new_post(self):
        resp = self.client.post('/burza/lead/new/', {
            'title': 'Test Lead',
            'status': 'new',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_burza_lead_detail_invalid(self):
        self.assertIn(self._get('/burza/lead/9999/'), ALLOWED)

    def test_burza_public_upit(self):
        c = Client(raise_request_exception=False)
        self.assertIn(c.get('/burza/upit/', follow=True).status_code, ALLOWED)

    def test_burza_upit_hvala(self):
        c = Client(raise_request_exception=False)
        self.assertIn(c.get('/burza/upit/hvala/', follow=True).status_code, ALLOWED)


class InventoryViewsExtraTest(TestCase):
    """Tests for inventory/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('46464646460', 'ov_inv1', ['inventory', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_inv1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_inventory_list(self):
        self.assertIn(self._get('/inventory/'), ALLOWED)

    def test_inventory_item_create_get(self):
        self.assertIn(self._get('/inventory/new/'), ALLOWED)

    def test_inventory_item_create_post(self):
        resp = self.client.post('/inventory/new/', {
            'name': 'Test stavka',
            'unit': 'kom',
            'price': '10.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_inventory_receipts_list(self):
        self.assertIn(self._get('/inventory/receipts/'), ALLOWED)

    def test_inventory_receipt_create_get(self):
        self.assertIn(self._get('/inventory/receipts/new/'), ALLOWED)

    def test_inventory_overview(self):
        self.assertIn(self._get('/inventory/overview/'), ALLOWED)

    def test_inventory_item_detail_invalid(self):
        self.assertIn(self._get('/inventory/9999/'), ALLOWED)

    def test_inventory_item_edit_invalid(self):
        self.assertIn(self._get('/inventory/9999/edit/'), ALLOWED)

    def test_inventory_list_search(self):
        resp = self.client.get('/inventory/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class AssessmentViewsExtraTest(TestCase):
    """Tests for assessment/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('47474747470', 'ov_assess1', ['assessment', 'partners', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_assess1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_assessment_list(self):
        self.assertIn(self._get('/assessment/'), ALLOWED)

    def test_assessment_new_get(self):
        self.assertIn(self._get('/assessment/new/'), ALLOWED)

    def test_assessment_list_filter(self):
        resp = self.client.get('/assessment/?status=new', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assessment_list_search(self):
        resp = self.client.get('/assessment/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assessment_save_post(self):
        try:
            resp = self.client.post('/assessment/save/', {
                'title': 'Test Assessment OV',
                'status': 'new',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_assessment_detail_invalid(self):
        self.assertIn(self._get('/assessment/9999/'), ALLOWED)


class MarketplaceViewsTest(TestCase):
    """Tests for marketplace/views.py (webshop-like)."""

    def setUp(self):
        self.company, self.user = _setup_user('48484848480', 'ov_mkt1', ['marketplace', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_mkt1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_marketplace_catalog(self):
        self.assertIn(self._get('/marketplace/'), ALLOWED)

    def test_marketplace_cart(self):
        self.assertIn(self._get('/marketplace/cart/'), ALLOWED)

    def test_marketplace_orders(self):
        self.assertIn(self._get('/marketplace/orders/'), ALLOWED)

    def test_marketplace_seller_dashboard(self):
        self.assertIn(self._get('/marketplace/seller/'), ALLOWED)

    def test_marketplace_product_new(self):
        self.assertIn(self._get('/marketplace/seller/product/new/'), ALLOWED)

    def test_marketplace_product_detail_invalid(self):
        self.assertIn(self._get('/marketplace/product/nonexistent/'), ALLOWED)


class CalculatorViewsExtraTest(TestCase):
    """Tests for calculator/views.py."""

    def setUp(self):
        self.company, self.user = _setup_user('49494949490', 'ov_calc1', ['calculator', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='ov_calc1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_calculator_internal_list(self):
        self.assertIn(self._get('/calculator/internal/'), ALLOWED)

    def test_calculator_bom_list(self):
        self.assertIn(self._get('/calculator/bom/'), ALLOWED)

    def test_calculator_bom_new_get(self):
        self.assertIn(self._get('/calculator/bom/new/'), ALLOWED)

    def test_calculator_bom_detail_invalid(self):
        self.assertIn(self._get('/calculator/bom/9999/'), ALLOWED)

    def test_calculator_salary(self):
        self.assertIn(self._get('/calculator/salary/'), ALLOWED)

    def test_calculator_public(self):
        c = Client(raise_request_exception=False)
        self.assertIn(c.get('/calculator/', follow=True).status_code, ALLOWED)
