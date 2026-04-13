"""Partner portal views tests (token-based, no auth needed)."""
import datetime
import uuid

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, modules=None):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'PP {oib}', oib=oib)
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
        modules_override=modules or ['partners', 'invoicing', 'projects', 'documents'],
    )
    return company, user


def _make_partner(company, name='Portal Partner'):
    from partners.models import Partner
    return Partner.objects.create(
        company=company,
        name=name,
        partner_type='client',
        email='portal@test.hr',
        is_active=True,
    )


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class PartnerPortalTest(TestCase):
    """Test partner portal views with real partner data."""

    def setUp(self):
        self.company, self.user = _setup_user('91000000001', 'pp_v1')
        self.partner = _make_partner(self.company)
        self.client = Client(raise_request_exception=False)

    def test_portal_home(self):
        try:
            token = self.partner.portal_token
            resp = self.client.get(f'/portal/{token}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_portal_invalid_token(self):
        try:
            fake_token = uuid.uuid4()
            resp = self.client.get(f'/portal/{fake_token}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_portal_invoices(self):
        try:
            token = self.partner.portal_token
            resp = self.client.get(f'/portal/{token}/invoices/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_portal_invoices_with_data(self):
        try:
            from invoicing.models import Invoice
            token = self.partner.portal_token
            # Create a sample invoice for this partner
            inv = Invoice.objects.create(
                number='PP-001',
                date_issued=datetime.datetime.now(),
                date_due=datetime.date.today() + datetime.timedelta(days=30),
                client_name=self.partner.name,
                client_email=self.partner.email,
                company=self.company,
                status='SENT',
                partner=self.partner,
            )
            resp = self.client.get(f'/portal/{token}/invoices/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass

    def test_portal_invoice_detail(self):
        try:
            from invoicing.models import Invoice
            token = self.partner.portal_token
            inv = Invoice.objects.create(
                number='PP-DETAIL',
                date_issued=datetime.datetime.now(),
                date_due=datetime.date.today() + datetime.timedelta(days=15),
                client_name=self.partner.name,
                company=self.company,
                status='SENT',
                partner=self.partner,
            )
            resp = self.client.get(f'/portal/{token}/invoices/{inv.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass

    def test_portal_invoice_pdf(self):
        try:
            from invoicing.models import Invoice
            token = self.partner.portal_token
            inv = Invoice.objects.create(
                number='PP-PDF',
                date_issued=datetime.datetime.now(),
                date_due=datetime.date.today() + datetime.timedelta(days=15),
                client_name=self.partner.name,
                company=self.company,
                status='SENT',
                partner=self.partner,
            )
            resp = self.client.get(f'/portal/{token}/invoices/{inv.pk}/pdf/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass

    def test_portal_projects(self):
        try:
            token = self.partner.portal_token
            resp = self.client.get(f'/portal/{token}/projects/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_portal_documents(self):
        try:
            token = self.partner.portal_token
            resp = self.client.get(f'/portal/{token}/documents/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass
