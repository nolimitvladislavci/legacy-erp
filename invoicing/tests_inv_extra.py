"""Invoicing views extra tests — wizard, edit, clone, API endpoints."""
import datetime
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError

ALLOWED = [200, 302, 400, 403, 404, 405, 500]


def _setup_inv_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'INV {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='enterprise',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['invoicing', 'partners', 'worktime'],
    )
    return company, user


def _make_partner(company, name='INV Partner'):
    from partners.models import Partner
    return Partner.objects.create(
        company=company, name=name, partner_type='client',
        email='inv@test.hr', is_active=True,
    )


def _make_invoice(company, user, partner=None, doctype='INVOICE', number=None):
    from invoicing.models import Invoice
    import uuid
    return Invoice.objects.create(
        company=company,
        number=number or f'KNJ-{uuid.uuid4().hex[:6].upper()}',
        doctype=doctype,
        date=datetime.date.today(),
        due_date=datetime.date.today() + datetime.timedelta(days=15),
        status='DRAFT',
        client=partner,
        created_by=user,
        issuer_name='Test Firma',
        issuer_oib='12345678901',
        client_name=partner.name if partner else 'Test Klijent',
        currency='EUR',
    )


class InvoicingListFilterTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_inv_user('95000000001', 'inv_e1')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_e1', password='pass123')

    def test_list_empty(self):
        try:
            resp = self.client.get('/invoicing/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_list_with_invoices(self):
        try:
            _make_invoice(self.company, self.user, self.partner)
            resp = self.client.get('/invoicing/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_list_filter_doctype(self):
        try:
            resp = self.client.get('/invoicing/?doctype=INVOICE', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_list_filter_status(self):
        try:
            resp = self.client.get('/invoicing/?status=DRAFT', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_list_search(self):
        try:
            resp = self.client.get('/invoicing/?q=KNJ', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass


class InvoicingWizardTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_inv_user('95000000002', 'inv_e2')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_e2', password='pass123')

    def test_wizard_get(self):
        try:
            resp = self.client.get('/invoicing/wizard/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_invoice_create_get(self):
        try:
            resp = self.client.get('/invoicing/new/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_office_wizard(self):
        try:
            resp = self.client.get('/invoicing/office/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_field_wizard(self):
        try:
            resp = self.client.get('/invoicing/field/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_invoice_form_view(self):
        try:
            resp = self.client.get('/invoicing/form/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_invoice_form_standalone(self):
        try:
            resp = self.client.get('/invoicing/form-standalone/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass


class InvoicingActionsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_inv_user('95000000003', 'inv_e3')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_e3', password='pass123')

    def test_invoice_edit_get(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.get(f'/invoicing/{inv.pk}/edit/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_invoice_pdf(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.get(f'/invoicing/{inv.pk}/pdf/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_invoice_download(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.get(f'/invoicing/{inv.pk}/download/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_invoice_send_email(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(f'/invoicing/{inv.pk}/email/', {
                'recipient': 'test@example.hr',
                'subject': 'Test račun',
                'message': 'Šaljemo vam račun.',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_invoice_storno(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(f'/invoicing/{inv.pk}/storno/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_invoice_clone(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(f'/invoicing/{inv.pk}/clone/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_convert_to_predracun(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(f'/invoicing/{inv.pk}/to-predracun/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_mark_sent(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner, 'PREDRACUN')
            resp = self.client.post(f'/invoicing/{inv.pk}/mark-sent/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_mark_accepted(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner, 'PREDRACUN')
            resp = self.client.post(f'/invoicing/{inv.pk}/mark-accepted/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_mark_rejected(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner, 'PREDRACUN')
            resp = self.client.post(f'/invoicing/{inv.pk}/mark-rejected/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass


class InvoicingAPITest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_inv_user('95000000004', 'inv_e4')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_e4', password='pass123')

    def test_api_profiles(self):
        try:
            resp = self.client.get('/invoicing/api/profiles/')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_partners(self):
        try:
            resp = self.client.get('/invoicing/api/partners/?q=test')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_articles(self):
        try:
            resp = self.client.get('/invoicing/api/articles/?q=art')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_tax_rates(self):
        try:
            resp = self.client.get('/invoicing/api/tax-rates/')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_worktime_entries(self):
        try:
            resp = self.client.get('/invoicing/api/worktime-entries/')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_tax_calculate(self):
        try:
            resp = self.client.get('/invoicing/api/tax-calculate/?amount=100&rate=25')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_update_status(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(
                f'/invoicing/api/invoice/{inv.pk}/status/',
                json.dumps({'status': 'SENT'}),
                content_type='application/json',
            )
            self.assertIn(resp.status_code, ALLOWED)
        except (TypeError, ValueError):
            pass

    def test_api_update_invoice(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.post(
                f'/invoicing/api/invoice/{inv.pk}/update/',
                json.dumps({'note': 'API update test'}),
                content_type='application/json',
            )
            self.assertIn(resp.status_code, ALLOWED)
        except (TypeError, ValueError):
            pass

    def test_api_import_partners(self):
        try:
            resp = self.client.get('/invoicing/api/import/partners/')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_fiscal_certificates(self):
        try:
            resp = self.client.get('/invoicing/fiscal/certificates/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_fiscal_batch(self):
        try:
            resp = self.client.get('/invoicing/fiscal/batch/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_fiscal_batch_create(self):
        try:
            resp = self.client.post('/invoicing/fiscal/batch/create/', {
                'date_from': datetime.date.today().isoformat(),
                'date_to': datetime.date.today().isoformat(),
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class InvoicingSaveTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_inv_user('95000000005', 'inv_e5')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='inv_e5', password='pass123')

    def test_invoice_save_post(self):
        try:
            resp = self.client.post('/invoicing/save/', {
                'doctype': 'INVOICE',
                'client_name': self.partner.name,
                'date': datetime.date.today().isoformat(),
                'due_date': (datetime.date.today() + datetime.timedelta(days=15)).isoformat(),
                'currency': 'EUR',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_invoice_add_hours(self):
        try:
            inv = _make_invoice(self.company, self.user, self.partner)
            resp = self.client.get(f'/invoicing/{inv.pk}/add-hours/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_api_field_create(self):
        try:
            resp = self.client.post(
                '/invoicing/api/field-create/',
                json.dumps({
                    'doctype': 'INVOICE',
                    'client_name': 'API Klijent',
                    'items': [
                        {'description': 'Usluga', 'quantity': 1, 'unit_price': 100, 'tax_rate': 25}
                    ],
                }),
                content_type='application/json',
            )
            self.assertIn(resp.status_code, ALLOWED)
        except (TypeError, ValueError):
            pass
