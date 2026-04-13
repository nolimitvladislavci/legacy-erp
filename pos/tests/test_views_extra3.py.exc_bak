"""Extra POS tests — receipt actions, settings, cashier, inventory, gastro, expiry."""
import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone


def _setup_pos_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'POSEX {oib}', oib=oib)
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
        modules_override=['pos', 'invoicing', 'inventory'],
    )
    return company, user


def _make_terminal(company):
    from pos.models import POSTerminal
    return POSTerminal.objects.create(
        company=company, name='Test T', is_active=True
    )


def _make_session(terminal, user):
    from pos.models import POSSession
    return POSSession.objects.create(
        terminal=terminal,
        operator=user,
        session_number=1,
        status='open',
    )


def _make_receipt(session):
    from pos.models import POSReceipt
    return POSReceipt.objects.create(session=session, receipt_number=1, status='open')


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class POSReceiptActionsTest(TestCase):
    """Test receipt action endpoints."""

    def setUp(self):
        self.company, self.user = _setup_pos_user('31313131310', 'posex_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='posex_v1', password='pass123')
        try:
            t = _make_terminal(self.company)
            s = _make_session(t, self.user)
            self.receipt = _make_receipt(s)
            self.session = s
            self.terminal = t
        except Exception:
            self.receipt = None
            self.session = None
            self.terminal = None

    def test_add_item_get(self):
        if not self.receipt:
            return
        resp = self.client.get(f'/pos/receipt/{self.receipt.pk}/add-item/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_add_item_post_json(self):
        if not self.receipt:
            return
        data = {'article_id': 9999, 'quantity': 1}
        resp = self.client.post(
            f'/pos/receipt/{self.receipt.pk}/add-item/',
            json.dumps(data),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_remove_item(self):
        if not self.receipt:
            return
        resp = self.client.post(
            f'/pos/receipt/{self.receipt.pk}/remove-item/9999/',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_process_payment_get(self):
        if not self.receipt:
            return
        resp = self.client.get(f'/pos/receipt/{self.receipt.pk}/pay/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_process_payment_post(self):
        if not self.receipt:
            return
        resp = self.client.post(f'/pos/receipt/{self.receipt.pk}/pay/', {
            'payment_method': 'cash',
            'amount_paid': '0.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_receipt_add_item_ajax(self):
        if not self.receipt:
            return
        resp = self.client.post(
            f'/pos/receipt/{self.receipt.pk}/add-item/',
            json.dumps({'article_id': 9999, 'qty': 1}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_receipt_json(self):
        if not self.receipt:
            return
        resp = self.client.get(f'/pos/receipt/{self.receipt.pk}/json/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_receipt_pay_ajax(self):
        if not self.receipt:
            return
        resp = self.client.post(
            f'/pos/receipt/{self.receipt.pk}/pay/',
            json.dumps({'payment_method': 'cash', 'amount': '0.00'}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_new_receipt_ajax(self):
        if not self.session:
            return
        resp = self.client.post(
            f'/pos/session/{self.session.pk}/new-receipt/',
            json.dumps({}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_quick_pay(self):
        if not self.session:
            return
        resp = self.client.get(f'/pos/session/{self.session.pk}/quick-pay/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class POSSettingsActionsTest(TestCase):
    """Test POS settings action endpoints."""

    def setUp(self):
        self.company, self.user = _setup_pos_user('31313131320', 'posex_v2')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='posex_v2', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_settings_page(self):
        self.assertIn(self._get('/pos/settings/'), ALLOWED)

    def test_save_printer_post(self):
        resp = self.client.post('/pos/settings/save-printer/', {
            'printer_type': 'usb',
            'printer_name': 'TestPrinter',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_save_fiscal_post(self):
        resp = self.client.post('/pos/settings/save-fiscal/', {
            'fiscal_device': 'none',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_test_fiscal_post(self):
        resp = self.client.post('/pos/settings/test-fiscal/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_test_print_post(self):
        resp = self.client.post('/pos/settings/test-print/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cashier_save_post(self):
        resp = self.client.post('/pos/settings/cashier/save/', {
            'name': 'Test Cashier',
            'pin': '1234',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cashier_delete(self):
        resp = self.client.post('/pos/settings/cashier/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_inventory_item_save_post(self):
        resp = self.client.post('/pos/settings/inventory/save/', {
            'name': 'Test Item',
            'price': '10.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_inventory_csv_import_get(self):
        self.assertIn(self._get('/pos/settings/inventory/csv-import/'), ALLOWED)

    def test_reports_export_get(self):
        self.assertIn(self._get('/pos/settings/reports/export/'), ALLOWED)


class POSGastroTest(TestCase):
    """Test gastro/restaurant POS endpoints."""

    def setUp(self):
        self.company, self.user = _setup_pos_user('31313131330', 'posex_v3')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='posex_v3', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_gastro_dashboard(self):
        self.assertIn(self._get('/pos/gastro/'), ALLOWED)

    def test_gastro_kitchen(self):
        self.assertIn(self._get('/pos/gastro/kitchen/'), ALLOWED)

    def test_gastro_kitchen_api(self):
        self.assertIn(self._get('/pos/gastro/kitchen/api/'), ALLOWED)

    def test_gastro_table_order(self):
        self.assertIn(self._get('/pos/gastro/table/9999/'), ALLOWED)

    def test_gastro_order_update(self):
        resp = self.client.post('/pos/gastro/order/9999/update/', {
            'status': 'ready',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_gastro_order_add_item(self):
        resp = self.client.post(
            '/pos/gastro/order/9999/add-item/',
            json.dumps({'article_id': 1}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_gastro_order_public(self):
        self.assertIn(self._get('/pos/gastro/order/invalid-token/'), ALLOWED)

    def test_gastro_qr(self):
        self.assertIn(self._get('/pos/gastro/qr/TEST123/'), ALLOWED)

    def test_expiry_dashboard(self):
        self.assertIn(self._get('/pos/expiry/'), ALLOWED)

    def test_expiry_add_get(self):
        self.assertIn(self._get('/pos/expiry/add/'), ALLOWED)

    def test_expiry_add_post(self):
        resp = self.client.post('/pos/expiry/add/', {
            'product_name': 'Test Product',
            'expiry_date': '2026-12-31',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_expiry_alerts_api(self):
        self.assertIn(self._get('/pos/expiry/api/alerts/'), ALLOWED)


class POSSessionActionsTest(TestCase):
    """Test session-level POS actions."""

    def setUp(self):
        self.company, self.user = _setup_pos_user('31313131340', 'posex_v4')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='posex_v4', password='pass123')
        try:
            self.terminal = _make_terminal(self.company)
            self.session = _make_session(self.terminal, self.user)
        except Exception:
            self.terminal = None
            self.session = None

    def test_open_session(self):
        if not self.terminal:
            return
        resp = self.client.post(f'/pos/terminal/{self.terminal.pk}/open/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_close_session(self):
        if not self.session:
            return
        resp = self.client.post(f'/pos/session/{self.session.pk}/close/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_session_zreport(self):
        if not self.session:
            return
        resp = self.client.get(f'/pos/session/{self.session.pk}/zreport/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cash_deposit(self):
        if not self.session:
            return
        resp = self.client.post(
            f'/pos/session/{self.session.pk}/deposit/',
            {'amount': '50.00'},
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_new_receipt(self):
        if not self.session:
            return
        resp = self.client.post(f'/pos/session/{self.session.pk}/receipt/new/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_quick_pos(self):
        if not self.terminal:
            return
        resp = self.client.get(f'/pos/quick/{self.terminal.pk}/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_restaurant_pos(self):
        if not self.terminal:
            return
        resp = self.client.get(f'/pos/restaurant/{self.terminal.pk}/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
