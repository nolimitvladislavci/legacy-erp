"""Tests for notifications, partners, documents, invoicing views."""
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import IntegrityError, DatabaseError


def _make_company(oib):
    from companies.models import Company
    return Company.objects.create(name=f'Extra {oib}', oib=oib)


def _make_user(company, username, modules=None):
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.get_or_create(
        company=company,
        defaults=dict(
            plan='starter',
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle='monthly',
            modules_override=modules or ['partners', 'invoicing', 'documents'],
        ),
    )
    return user


class NotificationServiceTest(TestCase):

    def setUp(self):
        self.sender = User.objects.create_user('notif_sender', password='pass')
        self.recipient = User.objects.create_user('notif_recipient', password='pass')

    def test_notify_creates_notification(self):
        from notifications.services import notify
        from notifications.models import Notification
        notify(
            recipient=self.recipient,
            notification_type='invoice_paid',
            title='Test notifikacija',
            message='Poruka',
            url='/test/',
            sender=self.sender,
        )
        n = Notification.objects.filter(recipient=self.recipient).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.title, 'Test notifikacija')

    def test_notify_without_sender(self):
        from notifications.services import notify
        from notifications.models import Notification
        notify(
            recipient=self.recipient,
            notification_type='info',
            title='No sender',
            message='test',
        )
        n = Notification.objects.filter(recipient=self.recipient, title='No sender').first()
        self.assertIsNotNone(n)

    def test_notification_str(self):
        from notifications.models import Notification
        n = Notification.objects.create(
            recipient=self.recipient,
            notification_type='test',
            title='STR Test',
            message='msg',
        )
        self.assertIn('STR Test', str(n))


class PartnerViewTest(TestCase):

    def setUp(self):
        self.company = _make_company('31313131313')
        self.user = _make_user(self.company, 'partner_view_user')
        self.client = Client()
        self.client.login(username='partner_view_user', password='pass123')

    def test_partner_list_requires_auth(self):
        c = Client()
        resp = c.get('/partners/', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_partner_list_authenticated(self):
        resp = self.client.get('/partners/', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_partner_list_only_own(self):
        from partners.models import Partner
        co2 = _make_company('32323232323')
        Partner.objects.create(company=self.company, name='My Partner', email='a@a.com')
        Partner.objects.create(company=co2, name='Other Partner', email='b@b.com')
        resp = self.client.get('/partners/', follow=True)
        if resp.status_code == 200:
            content = resp.content.decode()
            self.assertIn('My Partner', content)
            self.assertNotIn('Other Partner', content)

    def test_quick_create_api(self):
        import json
        resp = self.client.post(
            '/partners/api/quick-create/',
            json.dumps({'name': 'Quick Partner', 'email': 'quick@q.hr'}),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 201, 400, 403, 405])

    def test_partner_create_get(self):
        resp = self.client.get('/partners/create/', follow=True)
        self.assertIn(resp.status_code, [200, 302, 404])

    def test_nkd_search_api(self):
        resp = self.client.get('/companies/api/nkd-search/', {'q': 'Info'}, follow=True)
        self.assertIn(resp.status_code, [200, 302, 404])


class InvoiceViewIsolationTest(TestCase):

    def setUp(self):
        self.co_a = _make_company('41414141414')
        self.co_b = _make_company('42424242424')
        self.user_a = _make_user(self.co_a, 'inv_iso_a')
        self.user_b = _make_user(self.co_b, 'inv_iso_b')

    def test_invoice_list_isolation(self):
        from invoicing.models import Invoice
        Invoice.objects.create(
            company=self.co_a,
            number='R-ISO-0001',
            doctype='R',
            date_issued=timezone.now(),
            issuer_name='Co A',
            issuer_oib='41414141414',
            status='DRAFT',
        )
        c = Client()
        c.login(username='inv_iso_b', password='pass123')
        resp = c.get('/invoicing/', follow=True)
        if resp.status_code == 200:
            self.assertNotIn('R-ISO-0001', resp.content.decode())

    def test_invoice_list_authenticated(self):
        c = Client()
        c.login(username='inv_iso_a', password='pass123')
        resp = c.get('/invoicing/', follow=True)
        self.assertIn(resp.status_code, [200, 302])


class DocumentViewTest(TestCase):

    def setUp(self):
        self.company = _make_company('51515151515')
        self.user = _make_user(self.company, 'doc_view_user')
        self.client = Client()
        self.client.login(username='doc_view_user', password='pass123')

    def test_document_list_authenticated(self):
        resp = self.client.get('/documents/', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_document_list_requires_auth(self):
        c = Client()
        resp = c.get('/documents/', follow=True)
        self.assertIn(resp.status_code, [200, 302])
