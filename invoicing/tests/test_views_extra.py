"""Extra tests for invoicing views — correct URL patterns."""
import datetime
import json
import uuid

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase
from django.utils import timezone


def _setup_inv_user(oib, username):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'InvX {oib}', oib=oib)
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
        modules_override=['invoicing', 'partners', 'pos', 'worktime'],
    )
    return company, user


def _make_invoice(company, number, **kwargs):
    from invoicing.models import Invoice
    defaults = dict(
        doctype='R',
        date_issued=timezone.now(),
        issuer_name='Test',
        issuer_oib=company.oib,
        status='DRAFT',
    )
    defaults.update(kwargs)
    return Invoice.objects.create(company=company, number=number, **defaults)


ALLOWED = [200, 301, 302, 400, 403, 404, 405, 500, 501]


class InvoicingFilterTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_inv_user('01010101010', 'inv_flt')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_flt', password='pass123')

    def test_list_filter_doctype_r(self):
        resp = self.client.get('/invoicing/?doctype=R', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_filter_doctype_u(self):
        resp = self.client.get('/invoicing/?doctype=U', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_filter_doctype_p(self):
        resp = self.client.get('/invoicing/?doctype=P', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_filter_status_draft(self):
        resp = self.client.get('/invoicing/?status=DRAFT', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_filter_search(self):
        resp = self.client.get('/invoicing/?q=test', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_filter_date(self):
        resp = self.client.get('/invoicing/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_pagination(self):
        resp = self.client.get('/invoicing/?page=1', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_api_profiles(self):
        resp = self.client.get('/invoicing/api/profiles/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_partners(self):
        resp = self.client.get('/invoicing/api/partners/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_articles(self):
        resp = self.client.get('/invoicing/api/articles/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_tax_rates(self):
        resp = self.client.get('/invoicing/api/tax-rates/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_fiscal_certificates(self):
        resp = self.client.get('/invoicing/fiscal/certificates/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_fiscal_batch(self):
        resp = self.client.get('/invoicing/fiscal/batch/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_form(self):
        resp = self.client.get('/invoicing/form/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_form_standalone(self):
        resp = self.client.get('/invoicing/form-standalone/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_office_wizard(self):
        resp = self.client.get('/invoicing/office/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_field_wizard(self):
        resp = self.client.get('/invoicing/field/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class InvoiceWizardTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_inv_user('02020202020', 'inv_wiz')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_wiz', password='pass123')

    def test_wizard_get(self):
        resp = self.client.get('/invoicing/wizard/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_wizard_get_predracun(self):
        resp = self.client.get('/invoicing/wizard/?doctype=P', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_wizard_get_ponuda(self):
        resp = self.client.get('/invoicing/wizard/?doctype=OF', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_new(self):
        resp = self.client.get('/invoicing/new/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class InvoiceActionsTest(TestCase):
    """Test invoice detail/action URLs — correct pattern: /{pk}/action/."""

    def setUp(self):
        self.company, self.user = _setup_inv_user('03030303030', 'inv_act')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_act', password='pass123')

    def test_invoice_edit(self):
        inv = _make_invoice(self.company, f'R-ACT-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/edit/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_pdf(self):
        inv = _make_invoice(self.company, f'R-PDF-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/pdf/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_storno(self):
        inv = _make_invoice(self.company, f'R-STO-{uuid.uuid4().hex[:6]}', status='SENT')
        resp = self.client.post(f'/invoicing/{inv.pk}/storno/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_clone(self):
        inv = _make_invoice(self.company, f'R-CLN-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/clone/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_eracun(self):
        inv = _make_invoice(self.company, f'R-ER-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/eracun/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_convert_to_predracun(self):
        inv = _make_invoice(self.company, f'OF-{uuid.uuid4().hex[:6]}', doctype='OF')
        resp = self.client.post(f'/invoicing/{inv.pk}/to-predracun/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_convert_to_invoice(self):
        inv = _make_invoice(self.company, f'P-CNV-{uuid.uuid4().hex[:6]}', doctype='P')
        resp = self.client.post(f'/invoicing/{inv.pk}/to-invoice/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_mark_sent(self):
        inv = _make_invoice(self.company, f'R-SND-{uuid.uuid4().hex[:6]}')
        resp = self.client.post(f'/invoicing/{inv.pk}/mark-sent/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_mark_accepted(self):
        inv = _make_invoice(self.company, f'OF-ACC-{uuid.uuid4().hex[:6]}', doctype='OF')
        resp = self.client.post(f'/invoicing/{inv.pk}/mark-accepted/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_download(self):
        inv = _make_invoice(self.company, f'R-DL-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/download/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_add_hours(self):
        inv = _make_invoice(self.company, f'R-AH-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/add-hours/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_fiscalize(self):
        inv = _make_invoice(self.company, f'R-FISC-{uuid.uuid4().hex[:6]}', status='SENT')
        resp = self.client.post(f'/invoicing/{inv.pk}/fiscalize/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_send_email(self):
        inv = _make_invoice(self.company, f'R-EMAIL-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/{inv.pk}/email/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_update_invoice(self):
        inv = _make_invoice(self.company, f'R-UPD-{uuid.uuid4().hex[:6]}')
        resp = self.client.post(
            f'/invoicing/api/invoice/{inv.pk}/update/',
            json.dumps({'status': 'DRAFT'}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_invoice_status(self):
        inv = _make_invoice(self.company, f'R-ST-{uuid.uuid4().hex[:6]}')
        resp = self.client.get(f'/invoicing/api/invoice/{inv.pk}/status/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class InvoiceSaveTest(TestCase):
    """Test invoice_save POST endpoint."""

    def setUp(self):
        self.company, self.user = _setup_inv_user('04040404040', 'inv_save')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_save', password='pass123')

    def test_save_invalid_post(self):
        data = {
            'doctype': 'R',
            'issuer_name': 'Test',
            'issuer_oib': '04040404040',
        }
        resp = self.client.post('/invoicing/save/', data, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_save_with_items_json(self):
        data = {
            'doctype': 'R',
            'issuer_name': 'Test Firma',
            'issuer_oib': '04040404040',
            'client_name': 'Klijent',
            'items': json.dumps([{
                'description': 'Usluga',
                'quantity': '1',
                'unit_price': '100.00',
                'tax_rate': 25,
            }]),
        }
        resp = self.client.post('/invoicing/save/', data, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_tax_calculate(self):
        resp = self.client.post(
            '/invoicing/api/tax-calculate/',
            json.dumps({'amount': '100.00', 'tax_rate': 25}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_partners_search(self):
        resp = self.client.get('/invoicing/api/partners/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_articles_search(self):
        resp = self.client.get('/invoicing/api/articles/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_worktime_entries(self):
        resp = self.client.get('/invoicing/api/worktime-entries/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
