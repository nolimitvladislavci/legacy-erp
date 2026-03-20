"""Tests for Document views."""
from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from companies.models import Company
from partners.models import Partner
from documents.models import Document
from accounts.models import UserProfile


def _make_company(name, oib):
    return Company.objects.create(
        name=name, oib=oib, address='Test 1', city='Zagreb',
        country='HR', currency='EUR', is_platform_owner=True,
    )


def _make_user(username, company):
    u = User.objects.create_user(username=username, password='testpass123')
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


class DocumentListViewTest(TestCase):
    def setUp(self):
        self.company = _make_company('DocView Co', '44444444444')
        self.user = _make_user('docviewuser', self.company)
        self.client = Client(SERVER_NAME='viskovic-group.de')
        self.client.force_login(self.user)

    def _get(self, url):
        return self.client.get(url, secure=True, HTTP_ACCEPT_LANGUAGE='de')

    def test_list_200(self):
        resp = self._get('/documents/')
        self.assertEqual(resp.status_code, 200)

    def test_list_shows_own_docs(self):
        Document.objects.create(
            company=self.company, doc_type='invoice',
            doc_number='MY-DOC-001', date_issued=date.today(),
        )
        resp = self._get('/documents/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'MY-DOC-001')

    def test_list_filter_by_type(self):
        Document.objects.create(
            company=self.company, doc_type='invoice',
            doc_number='INV-001', date_issued=date.today(),
        )
        Document.objects.create(
            company=self.company, doc_type='offer',
            doc_number='OFF-001', date_issued=date.today(),
        )
        resp = self.client.get('/documents/?doc_type=invoice', secure=True, HTTP_ACCEPT_LANGUAGE='de')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'INV-001')
        self.assertNotContains(resp, 'OFF-001')

    def test_create_get_200(self):
        resp = self._get('/documents/new/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_200(self):
        doc = Document.objects.create(
            company=self.company, doc_type='invoice',
            doc_number='DET-001', date_issued=date.today(),
        )
        resp = self._get(f'/documents/{doc.pk}/')
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        c = Client(SERVER_NAME='viskovic-group.de')
        resp = c.get('/documents/', secure=True, HTTP_ACCEPT_LANGUAGE='de')
        self.assertEqual(resp.status_code, 302)
