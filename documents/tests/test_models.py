"""Tests for Document model."""
from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User
from companies.models import Company
from partners.models import Partner
from documents.models import Document
from accounts.models import UserProfile
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def _make_company(name, oib):
    return Company.objects.create(
        name=name, oib=oib, address='Test 1', city='Zagreb',
        country='HR', currency='EUR',
    )


def _make_user(username, company):
    u = User.objects.create_user(username=username, password='testpass123')
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


class DocumentModelTest(TestCase):
    def setUp(self):
        self.company = _make_company('Doc Test Co', '77777777771')
        self.partner = Partner.objects.create(
            company=self.company, name='Test Partner',
            oib='66666666662', is_active=True,
        )

    def test_create_invoice_doc(self):
        doc = Document.objects.create(
            company=self.company,
            partner=self.partner,
            doc_type='invoice',
            doc_number='DOC-2026-0001',
            date_issued=date.today(),
            total_amount='1500.00',
        )
        self.assertIn('DOC-2026-0001', str(doc))
        self.assertFalse(doc.is_paid)

    def test_create_offer_doc(self):
        doc = Document.objects.create(
            company=self.company,
            doc_type='offer',
            doc_number='PON-2026-0001',
            date_issued=date.today(),
            total_amount='500.00',
        )
        self.assertEqual(doc.doc_type, 'offer')

    def test_create_contract_doc(self):
        doc = Document.objects.create(
            company=self.company,
            doc_type='contract',
            doc_number='UGO-2026-0001',
            date_issued=date.today(),
        )
        self.assertEqual(doc.doc_type, 'contract')

    def test_is_paid_toggle(self):
        doc = Document.objects.create(
            company=self.company,
            doc_type='bill',
            doc_number='RAC-2026-0001',
            date_issued=date.today(),
            total_amount='200.00',
        )
        self.assertFalse(doc.is_paid)
        doc.is_paid = True
        doc.save()
        doc.refresh_from_db()
        self.assertTrue(doc.is_paid)

    def test_company_isolation(self):
        other = _make_company('Other Co', '55555555553')
        Document.objects.create(
            company=self.company, doc_type='invoice',
            doc_number='ISO-A-001', date_issued=date.today(),
        )
        Document.objects.create(
            company=other, doc_type='invoice',
            doc_number='ISO-B-001', date_issued=date.today(),
        )
        company_docs = Document.objects.filter(company=self.company)
        self.assertEqual(company_docs.count(), 1)
        self.assertEqual(company_docs.first().doc_number, 'ISO-A-001')
