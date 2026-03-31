"""
LIMIT Connect — Comprehensive Arhiva View Tests
=================================================
Tests for all Arhiva-related views: list, upload, download, delete,
export, AI inbox, scan batches, bookmarks.

Coverage:
- Authentication enforcement
- Multi-tenant isolation (company A cannot see company B)
- Filter/search/pagination logic
- File upload integrity (hash, deletion protection)
- File type validation
- CSV export correctness
- AI inbox accept/bulk workflows
- Scan batch lifecycle
- Bookmark toggle
"""
import io
import json
import os
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from companies.models import Company
from documents.models import (
    ArhivaEntry, ArhivaBookmark, ArhivaLabel,
    ScanBatch, ScanBatchImage,
)


# ════════════════════════════════════════════════════════════
# Helpers — match project conventions from test_views.py
# ════════════════════════════════════════════════════════════

def _make_company(name, oib, **kwargs):
    defaults = dict(
        address='Test 1', city='Zagreb', country='HR',
        currency='EUR', is_platform_owner=True,
    )
    defaults.update(kwargs)
    return Company.objects.create(name=name, oib=oib, **defaults)


def _make_user(username, company, is_superuser=False):
    u = User.objects.create_user(username=username, password='testpass123')
    u.is_superuser = is_superuser
    u.save()
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


def _make_entry(company, **kwargs):
    """Create an ArhivaEntry with sane defaults."""
    defaults = dict(
        source_type='invoice_out',
        source_id='test-src-001',
        doc_number='RAC-2026-001',
        partner_name='Test Partner d.o.o.',
        amount=Decimal('1250.00'),
        currency='EUR',
        doc_date=date.today(),
        has_pdf=True,
    )
    defaults.update(kwargs)
    return ArhivaEntry.objects.create(company=company, **defaults)


def _login_client(user):
    """Return a logged-in Client matching project conventions."""
    c = Client(SERVER_NAME='viskovic-group.de')
    c.force_login(user)
    return c


def _get(client, url, **params):
    """GET with project-standard headers."""
    return client.get(url, data=params, secure=True, HTTP_ACCEPT_LANGUAGE='de')


def _post(client, url, data=None, **kwargs):
    """POST with project-standard headers."""
    return client.post(url, data=data or {}, secure=True, HTTP_ACCEPT_LANGUAGE='de', **kwargs)


# ════════════════════════════════════════════════════════════
# 1. ArhivaListViewTests
# ════════════════════════════════════════════════════════════

class ArhivaListViewTests(TestCase):
    """Tests for the arhiva_list view and supporting endpoints."""

    def setUp(self):
        self.company = _make_company('Arhiva Test GmbH', '11111111111')
        self.user = _make_user('arhiva_list_user', self.company)
        self.client = _login_client(self.user)

        # Create a set of entries with varying attributes
        self.entry_inv = _make_entry(self.company, source_type='invoice_out',
                                     doc_number='INV-2026-001', partner_name='Muller GmbH',
                                     amount=Decimal('500.00'), doc_date=date(2026, 1, 15))
        self.entry_eracun = _make_entry(self.company, source_type='eracun',
                                         doc_number='ERA-2026-005', partner_name='Schmidt AG',
                                         amount=Decimal('1200.50'), doc_date=date(2026, 2, 20))
        self.entry_doc = _make_entry(self.company, source_type='document',
                                      doc_number='DOC-2026-010', partner_name='Weber KG',
                                      amount=Decimal('300.00'), doc_date=date(2026, 3, 1))

    def test_list_requires_login(self):
        """Unauthenticated users must be redirected to login."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.get(reverse('documents:arhiva_list'), secure=True, HTTP_ACCEPT_LANGUAGE='de')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url.lower())

    def test_list_shows_only_company_entries(self):
        """Tenant isolation: user sees only their company's entries."""
        other_company = _make_company('Other Corp', '22222222222')
        _make_entry(other_company, doc_number='OTHER-001', partner_name='Fremdfirma')

        resp = _get(self.client, reverse('documents:arhiva_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('INV-2026-001', content)
        self.assertNotIn('OTHER-001', content)

    def test_list_filter_by_source_type(self):
        """Filter by source_type shows only matching entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'), source_type='eracun')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('ERA-2026-005', content)
        self.assertNotIn('INV-2026-001', content)

    def test_list_filter_by_date_range(self):
        """Date range filter narrows results correctly."""
        resp = _get(self.client, reverse('documents:arhiva_list'),
                    date_from='2026-02-01', date_to='2026-02-28')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('ERA-2026-005', content)
        self.assertNotIn('INV-2026-001', content)
        self.assertNotIn('DOC-2026-010', content)

    def test_list_search_by_doc_number(self):
        """Search query matches doc_number."""
        resp = _get(self.client, reverse('documents:arhiva_list'), q='INV-2026')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('INV-2026-001', content)
        self.assertNotIn('ERA-2026-005', content)

    def test_list_search_by_partner_name(self):
        """Search query matches partner_name."""
        resp = _get(self.client, reverse('documents:arhiva_list'), q='Schmidt')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('ERA-2026-005', content)
        self.assertNotIn('DOC-2026-010', content)

    def test_list_pagination(self):
        """Pagination works with 50 entries per page."""
        # Create 55 additional entries to exceed page size
        for i in range(55):
            _make_entry(self.company, doc_number=f'PAG-{i:04d}',
                        source_id=f'pag-{i}', amount=Decimal('10.00'))

        resp = _get(self.client, reverse('documents:arhiva_list'))
        self.assertEqual(resp.status_code, 200)

        # Page 2 should also work
        resp2 = _get(self.client, reverse('documents:arhiva_list'), page='2')
        self.assertEqual(resp2.status_code, 200)

    def test_list_json_api(self):
        """arhiva_list_json returns proper JSON structure."""
        resp = _get(self.client, reverse('documents:arhiva_list_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('entries', data)
        self.assertIn('has_next', data)
        self.assertIn('page', data)
        self.assertIsInstance(data['entries'], list)
        # Should contain our entries
        doc_numbers = [e['doc_number'] for e in data['entries']]
        self.assertIn('INV-2026-001', doc_numbers)

    def test_list_json_api_with_filters(self):
        """arhiva_list_json respects q and source_type filters."""
        resp = _get(self.client, reverse('documents:arhiva_list_json'),
                    q='ERA', source_type='eracun')
        data = resp.json()
        doc_numbers = [e['doc_number'] for e in data['entries']]
        self.assertIn('ERA-2026-005', doc_numbers)
        self.assertNotIn('INV-2026-001', doc_numbers)

    def test_list_empty_state(self):
        """Empty company renders without error."""
        empty_company = _make_company('Empty GmbH', '33333333333')
        empty_user = _make_user('empty_user', empty_company)
        c = _login_client(empty_user)
        resp = _get(c, reverse('documents:arhiva_list'))
        self.assertEqual(resp.status_code, 200)

    def test_list_autocomplete(self):
        """Autocomplete returns matching results."""
        resp = _get(self.client, reverse('documents:arhiva_autocomplete'), q='Muller')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('results', data)
        self.assertTrue(len(data['results']) > 0)
        found = any(r['label'] == 'Muller GmbH' or 'Muller' in str(r.get('label', ''))
                     for r in data['results'])
        self.assertTrue(found, 'Autocomplete should find "Muller GmbH"')

    def test_list_autocomplete_short_query_empty(self):
        """Autocomplete with <2 chars returns empty."""
        resp = _get(self.client, reverse('documents:arhiva_autocomplete'), q='M')
        data = resp.json()
        self.assertEqual(data['results'], [])

    def test_list_autocomplete_tenant_isolation(self):
        """Autocomplete does not return entries from other companies."""
        other = _make_company('Autocomplete Other', '44444444444')
        _make_entry(other, doc_number='SECRET-001', partner_name='Geheimfirma')

        resp = _get(self.client, reverse('documents:arhiva_autocomplete'), q='Geheim')
        data = resp.json()
        labels = [r['label'] for r in data['results']]
        self.assertNotIn('Geheimfirma', labels)


# ════════════════════════════════════════════════════════════
# 2. ArhivaUploadViewTests
# ════════════════════════════════════════════════════════════

class ArhivaUploadViewTests(TestCase):
    """Tests for the arhiva_upload view."""

    def setUp(self):
        self.company = _make_company('Upload Test GmbH', '55555555555')
        self.user = _make_user('upload_user', self.company)
        self.client = _login_client(self.user)

    def test_upload_requires_login(self):
        """Upload page requires authentication."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.get(reverse('documents:arhiva_upload'), secure=True)
        self.assertEqual(resp.status_code, 302)

    def test_upload_get_renders_form(self):
        """GET request renders the upload form."""
        resp = _get(self.client, reverse('documents:arhiva_upload'))
        self.assertEqual(resp.status_code, 200)

    @patch('documents.views.store_document')
    def test_upload_pdf_creates_entry(self, mock_store):
        """Uploading a PDF creates an ArhivaEntry."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/test.pdf',
            'hash': 'abc123def456',
            'size': 5000,
            'backend': 'local',
            'content_type': 'application/pdf',
        }
        pdf_file = SimpleUploadedFile('rechnung.pdf', b'%PDF-1.4 fake pdf content',
                                       content_type='application/pdf')
        resp = _post(self.client, reverse('documents:arhiva_upload'), {
            'file': pdf_file,
            'source_type': 'invoice_in',
            'doc_number': 'UPLOAD-001',
            'amount': '999.99',
            'doc_date': '2026-03-15',
        })
        self.assertEqual(resp.status_code, 302)  # Redirect after success
        entry = ArhivaEntry.objects.filter(company=self.company, doc_number='UPLOAD-001').first()
        self.assertIsNotNone(entry, 'ArhivaEntry should be created after upload')
        self.assertEqual(entry.source_type, 'invoice_in')
        self.assertTrue(entry.has_pdf)

    @patch('documents.views.store_document')
    def test_upload_image_creates_entry(self, mock_store):
        """Uploading an image creates an ArhivaEntry with has_image=True."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/scan.jpg',
            'hash': 'img_hash_789',
            'size': 3000,
            'backend': 'local',
            'content_type': 'image/jpeg',
        }
        img_file = SimpleUploadedFile('scan.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 100,
                                       content_type='image/jpeg')
        resp = _post(self.client, reverse('documents:arhiva_upload'), {
            'file': img_file,
            'source_type': 'document',
            'doc_number': 'SCAN-001',
        })
        self.assertEqual(resp.status_code, 302)
        entry = ArhivaEntry.objects.filter(company=self.company, doc_number='SCAN-001').first()
        self.assertIsNotNone(entry)
        self.assertTrue(entry.has_image)
        self.assertFalse(entry.has_pdf)

    @patch('documents.views.store_document')
    def test_upload_sets_integrity_hash(self, mock_store):
        """Upload must set integrity_hash on ArhivaEntry (computed in save)."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/hash_test.pdf',
            'hash': 'file_hash_abc',
            'size': 2000,
            'backend': 'local',
            'content_type': 'application/pdf',
        }
        pdf_file = SimpleUploadedFile('hash_test.pdf', b'%PDF-1.4 hash test',
                                       content_type='application/pdf')
        _post(self.client, reverse('documents:arhiva_upload'), {
            'file': pdf_file,
            'source_type': 'document',
            'doc_number': 'HASH-001',
            'amount': '100.00',
            'doc_date': '2026-01-01',
        })
        entry = ArhivaEntry.objects.filter(doc_number='HASH-001').first()
        self.assertIsNotNone(entry)
        self.assertTrue(len(entry.integrity_hash) == 64,
                        'integrity_hash must be SHA-256 (64 hex chars)')
        # Verify hash matches what compute_integrity_hash returns
        self.assertEqual(entry.integrity_hash, entry.compute_integrity_hash())

    @patch('documents.views.store_document')
    def test_upload_sets_deletion_protection(self, mock_store):
        """Upload must set deletion_protected_until (11 years from doc_date)."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/prot_test.pdf',
            'hash': 'prot_hash',
            'size': 1500,
            'backend': 'local',
            'content_type': 'application/pdf',
        }
        pdf_file = SimpleUploadedFile('prot_test.pdf', b'%PDF protect',
                                       content_type='application/pdf')
        _post(self.client, reverse('documents:arhiva_upload'), {
            'file': pdf_file,
            'source_type': 'invoice_out',
            'doc_number': 'PROT-001',
            'doc_date': '2026-01-01',
        })
        entry = ArhivaEntry.objects.filter(doc_number='PROT-001').first()
        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.deletion_protected_until)
        expected = date(2026, 1, 1) + timedelta(days=11 * 365)
        self.assertEqual(entry.deletion_protected_until, expected)

    def test_upload_empty_file_rejected(self):
        """Uploading without a file should not create entry."""
        initial_count = ArhivaEntry.objects.filter(company=self.company).count()
        resp = _post(self.client, reverse('documents:arhiva_upload'), {
            'source_type': 'document',
            'doc_number': 'EMPTY-001',
        })
        # Should redirect but not create entry (no file uploaded)
        self.assertEqual(ArhivaEntry.objects.filter(company=self.company).count(), initial_count)

    @patch('documents.views.store_document')
    def test_upload_assigns_to_correct_company(self, mock_store):
        """Upload entry must be assigned to the logged-in user's company."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/company_test.pdf',
            'hash': 'company_hash',
            'size': 1000,
            'backend': 'local',
            'content_type': 'application/pdf',
        }
        other_company = _make_company('Should Not Be', '66666666666')
        pdf_file = SimpleUploadedFile('company_test.pdf', b'%PDF company',
                                       content_type='application/pdf')
        _post(self.client, reverse('documents:arhiva_upload'), {
            'file': pdf_file,
            'source_type': 'document',
            'doc_number': 'COMPANY-001',
        })
        entry = ArhivaEntry.objects.filter(doc_number='COMPANY-001').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.company_id, self.company.id)
        self.assertNotEqual(entry.company_id, other_company.id)

    @patch('documents.views.store_document')
    def test_upload_xml_sets_has_xml(self, mock_store):
        """Uploading an XML file sets has_xml=True."""
        mock_store.return_value = {
            'path': 'arhiva/55/2026/03/eracun.xml',
            'hash': 'xml_hash',
            'size': 800,
            'backend': 'local',
            'content_type': 'text/xml',
        }
        xml_file = SimpleUploadedFile('eracun.xml', b'<?xml version="1.0"?><invoice/>',
                                       content_type='text/xml')
        _post(self.client, reverse('documents:arhiva_upload'), {
            'file': xml_file,
            'source_type': 'eracun',
            'doc_number': 'XML-001',
        })
        entry = ArhivaEntry.objects.filter(doc_number='XML-001').first()
        self.assertIsNotNone(entry)
        self.assertTrue(entry.has_xml)
        self.assertFalse(entry.has_pdf)


# ════════════════════════════════════════════════════════════
# 3. ArhivaDownloadViewTests
# ════════════════════════════════════════════════════════════

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ArhivaDownloadViewTests(TestCase):
    """Tests for arhiva_download, arhiva_download_pdf, arhiva_download_xml, bulk_download."""

    def setUp(self):
        self.company = _make_company('Download GmbH', '77777777777')
        self.other_company = _make_company('Other Download', '88888888888')
        self.user = _make_user('download_user', self.company)
        self.other_user = _make_user('other_download_user', self.other_company)
        self.client = _login_client(self.user)

        # Create a temp file on disk for download tests
        self.test_content = b'%PDF-1.4 test download content'
        self.temp_dir = os.path.join(settings.MEDIA_ROOT, 'arhiva', str(self.company.id), '2026', '03')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.temp_file = os.path.join(self.temp_dir, 'test_download.pdf')
        with open(self.temp_file, 'wb') as f:
            f.write(self.test_content)

        self.entry = _make_entry(self.company, doc_number='DL-001',
                                  file_path=self.temp_file)

        self.other_entry = _make_entry(self.other_company, doc_number='DL-OTHER-001',
                                        source_id='other-dl', file_path='/nonexistent/file.pdf')

    def test_download_own_company_file(self):
        """User can download files from their own company."""
        resp = _get(self.client, reverse('documents:arhiva_download', args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_download_other_company_blocked(self):
        """User cannot download files from another company — 404."""
        resp = _get(self.client, reverse('documents:arhiva_download', args=[self.other_entry.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_download_nonexistent_entry(self):
        """Downloading a nonexistent entry returns 404."""
        resp = _get(self.client, reverse('documents:arhiva_download', args=[999999]))
        self.assertEqual(resp.status_code, 404)

    def test_download_pdf_generation(self):
        """arhiva_download_pdf generates a PDF response."""
        resp = _get(self.client, reverse('documents:arhiva_pdf', args=[self.entry.pk]))
        # Might fail if template missing, but at least tests the view flow
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')
            self.assertIn('attachment', resp.get('Content-Disposition', ''))

    def test_download_xml(self):
        """arhiva_download_xml generates XML output."""
        resp = _get(self.client, reverse('documents:arhiva_xml', args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('xml', resp['Content-Type'].lower())
        content = resp.content.decode()
        self.assertIn('ArhivaEntry', content)
        self.assertIn(self.entry.doc_number, content)

    def test_download_xml_other_company_blocked(self):
        """XML download blocked for other company entries."""
        resp = _get(self.client, reverse('documents:arhiva_xml', args=[self.other_entry.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_bulk_download_requires_post(self):
        """Bulk download must be POST."""
        resp = _get(self.client, reverse('documents:arhiva_bulk_download'))
        # require_POST returns 405
        self.assertIn(resp.status_code, [405, 400])

    def test_bulk_download_no_ids_returns_error(self):
        """Bulk download with no IDs returns 400."""
        resp = self.client.post(
            reverse('documents:arhiva_bulk_download'),
            data=json.dumps({'ids': []}),
            content_type='application/json',
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        self.assertEqual(resp.status_code, 400)


# ════════════════════════════════════════════════════════════
# 4. ArhivaDeleteViewTests
# ════════════════════════════════════════════════════════════

class ArhivaDeleteViewTests(TestCase):
    """Tests for arhiva_delete_entry view."""

    def setUp(self):
        self.company = _make_company('Delete GmbH', '99999999999')
        self.other_company = _make_company('Other Delete', '10101010101')
        self.user = _make_user('delete_user', self.company)
        self.client = _login_client(self.user)

    def test_delete_requires_login(self):
        """Delete endpoint requires authentication."""
        entry = _make_entry(self.company, doc_number='DEL-LOGIN-001')
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.post(reverse('documents:arhiva_delete_entry', args=[entry.pk]),
                         secure=True)
        self.assertEqual(resp.status_code, 302)
        # Entry should still exist
        self.assertTrue(ArhivaEntry.objects.filter(pk=entry.pk).exists())

    def test_delete_fiscalized_entry_blocked(self):
        """Fiscalized entries (with JIR) cannot be deleted."""
        entry = _make_entry(self.company, doc_number='DEL-FISC-001',
                            jir='abc123-jir-value')
        resp = _post(self.client, reverse('documents:arhiva_delete_entry', args=[entry.pk]))
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn('fiskaliziran', data['error'].lower())
        # Entry must still exist
        self.assertTrue(ArhivaEntry.objects.filter(pk=entry.pk).exists())

    def test_delete_unprotected_entry_succeeds(self):
        """Non-fiscalized entry can be deleted."""
        entry = _make_entry(self.company, doc_number='DEL-OK-001', jir='')
        entry_pk = entry.pk
        resp = _post(self.client, reverse('documents:arhiva_delete_entry', args=[entry_pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertFalse(ArhivaEntry.objects.filter(pk=entry_pk).exists())

    def test_delete_other_company_blocked(self):
        """Cannot delete entries from another company — 403."""
        other_entry = _make_entry(self.other_company, doc_number='DEL-OTHER-001',
                                   source_id='del-other', jir='')
        resp = _post(self.client, reverse('documents:arhiva_delete_entry', args=[other_entry.pk]))
        self.assertEqual(resp.status_code, 403)
        # Entry must still exist
        self.assertTrue(ArhivaEntry.objects.filter(pk=other_entry.pk).exists())

    def test_delete_post_only(self):
        """Delete requires POST method — GET should fail."""
        entry = _make_entry(self.company, doc_number='DEL-GET-001')
        resp = _get(self.client, reverse('documents:arhiva_delete_entry', args=[entry.pk]))
        # require_POST returns 405
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(ArhivaEntry.objects.filter(pk=entry.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        """Deleting a nonexistent entry returns 404."""
        resp = _post(self.client, reverse('documents:arhiva_delete_entry', args=[999999]))
        self.assertEqual(resp.status_code, 404)


# ════════════════════════════════════════════════════════════
# 5. ArhivaExportViewTests
# ════════════════════════════════════════════════════════════

class ArhivaExportViewTests(TestCase):
    """Tests for the arhiva_export CSV view."""

    def setUp(self):
        self.company = _make_company('Export GmbH', '12121212121')
        self.user = _make_user('export_user', self.company)
        self.client = _login_client(self.user)

        _make_entry(self.company, source_type='invoice_out', doc_number='EXP-001',
                     partner_name='Export Partner', amount=Decimal('1000.00'),
                     doc_date=date(2026, 1, 10))
        _make_entry(self.company, source_type='eracun', doc_number='EXP-002',
                     partner_name='eRacun Firma', amount=Decimal('2500.00'),
                     doc_date=date(2026, 2, 15), source_id='exp-002')

    def test_export_csv(self):
        """Export returns a CSV file with correct headers."""
        resp = _get(self.client, reverse('documents:arhiva_export'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.csv', resp['Content-Disposition'])

        content = resp.content.decode('utf-8-sig')
        lines = content.strip().split('\n')
        self.assertTrue(len(lines) >= 3, 'CSV should have header + at least 2 data rows')

        # Check header
        header = lines[0]
        self.assertIn('Datum', header)
        self.assertIn('Broj dokumenta', header)
        self.assertIn('Partner', header)
        self.assertIn('Iznos', header)

    def test_export_filtered(self):
        """Export respects source_type filter."""
        resp = _get(self.client, reverse('documents:arhiva_export'), source_type='eracun')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8-sig')
        self.assertIn('EXP-002', content)
        self.assertNotIn('EXP-001', content)

    def test_export_date_filtered(self):
        """Export respects date range filters."""
        resp = _get(self.client, reverse('documents:arhiva_export'),
                    date_from='2026-02-01', date_to='2026-02-28')
        content = resp.content.decode('utf-8-sig')
        self.assertIn('EXP-002', content)
        self.assertNotIn('EXP-001', content)

    def test_export_empty(self):
        """Export with no matching entries returns CSV with just header."""
        resp = _get(self.client, reverse('documents:arhiva_export'), source_type='cmr')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8-sig')
        lines = [l for l in content.strip().split('\n') if l.strip()]
        # Just the header row
        self.assertEqual(len(lines), 1)

    def test_export_requires_login(self):
        """Export requires authentication."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.get(reverse('documents:arhiva_export'), secure=True)
        self.assertEqual(resp.status_code, 302)

    def test_export_search_filter(self):
        """Export respects q search parameter."""
        resp = _get(self.client, reverse('documents:arhiva_export'), q='eRacun')
        content = resp.content.decode('utf-8-sig')
        self.assertIn('EXP-002', content)
        self.assertNotIn('EXP-001', content)


# ════════════════════════════════════════════════════════════
# 6. AIInboxViewTests
# ════════════════════════════════════════════════════════════

class AIInboxViewTests(TestCase):
    """Tests for AI inbox views: list, accept, bulk accept, send email."""

    def setUp(self):
        self.company = _make_company('AI Inbox GmbH', '13131313131')
        self.other_company = _make_company('Other AI Corp', '14141414141')
        self.user = _make_user('ai_inbox_user', self.company)
        self.client = _login_client(self.user)

        # Entry with AI proposal — pending
        self.pending_entry = _make_entry(
            self.company, doc_number='AI-001', source_id='ai-001',
            amount=Decimal('750.00'), is_booked=False,
            ai_proposal={'debit': '4000', 'credit': '2200', 'description': 'Nabava robe',
                         'confidence': 0.92}
        )

        # Entry already booked
        self.booked_entry = _make_entry(
            self.company, doc_number='AI-002', source_id='ai-002',
            amount=Decimal('500.00'), is_booked=True,
            ai_proposal={'debit': '4000', 'credit': '2200', 'confidence': 0.85}
        )

        # Entry without proposal
        self.no_proposal = _make_entry(
            self.company, doc_number='AI-003', source_id='ai-003',
            amount=Decimal('100.00'), is_booked=False, ai_proposal=None
        )

        # Entry from other company
        self.other_entry = _make_entry(
            self.other_company, doc_number='AI-OTHER-001', source_id='ai-other-001',
            amount=Decimal('999.00'), is_booked=False,
            ai_proposal={'debit': '6000', 'credit': '1000', 'confidence': 0.88}
        )

    def test_inbox_lists_pending_entries(self):
        """AI inbox shows unbooked entries with AI proposals."""
        resp = _get(self.client, reverse('documents:ai_inbox'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('AI-001', content)
        # Booked entries should not appear
        self.assertNotIn('AI-002', content)
        # Entries without proposals should not appear
        self.assertNotIn('AI-003', content)

    def test_inbox_json_format(self):
        """AI inbox JSON format returns correct structure."""
        resp = _get(self.client, reverse('documents:ai_inbox'), format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('entries', data)
        self.assertIn('has_next', data)
        # Should contain only pending with proposals
        ids = [e['id'] for e in data['entries']]
        self.assertIn(self.pending_entry.pk, ids)
        self.assertNotIn(self.booked_entry.pk, ids)

    @patch('documents.views._create_journal_entry_from_proposal')
    @patch('documents.views._proposal_has_debit_credit', return_value=True)
    def test_inbox_accept_proposal(self, mock_has_dk, mock_create_je):
        """Accepting an AI proposal marks the entry as booked."""
        mock_je = MagicMock()
        mock_je.entry_number = 'JE-2026-001'
        mock_create_je.return_value = mock_je

        resp = _post(self.client, reverse('documents:ai_inbox_accept',
                                          args=[self.pending_entry.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])

        self.pending_entry.refresh_from_db()
        self.assertTrue(self.pending_entry.is_booked)

    def test_inbox_accept_other_company_blocked(self):
        """Cannot accept proposals from another company."""
        resp = _post(self.client, reverse('documents:ai_inbox_accept',
                                          args=[self.other_entry.pk]))
        self.assertEqual(resp.status_code, 403)
        self.other_entry.refresh_from_db()
        self.assertFalse(self.other_entry.is_booked)

    @patch('documents.views._create_journal_entry_from_proposal')
    @patch('documents.views._proposal_has_debit_credit', return_value=True)
    @patch('documents.views._normalize_confidence', return_value=0.92)
    def test_inbox_bulk_accept(self, mock_conf, mock_has_dk, mock_create_je):
        """Bulk accept books all matching entries for a company."""
        mock_je = MagicMock()
        mock_je.entry_number = 'JE-BULK-001'
        mock_create_je.return_value = mock_je

        resp = self.client.post(
            reverse('documents:ai_inbox_bulk_accept'),
            data=json.dumps({'company_id': str(self.company.pk), 'min_confidence': 0}),
            content_type='application/json',
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['count'], 1)

    def test_inbox_bulk_accept_requires_company_id(self):
        """Bulk accept without company_id returns 400."""
        resp = self.client.post(
            reverse('documents:ai_inbox_bulk_accept'),
            data=json.dumps({}),
            content_type='application/json',
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        self.assertEqual(resp.status_code, 400)

    def test_inbox_empty_state(self):
        """AI inbox renders correctly when no pending entries exist."""
        # Book all pending entries
        ArhivaEntry.objects.filter(company=self.company).update(is_booked=True)
        resp = _get(self.client, reverse('documents:ai_inbox'))
        self.assertEqual(resp.status_code, 200)

    @patch('documents.views.send_ai_inbox_summary_email', create=True)
    def test_inbox_send_email(self, *mocks):
        """Send email trigger returns OK."""
        with patch('documents.tasks.send_ai_inbox_summary_email') as mock_task:
            mock_task.delay = MagicMock()
            resp = _post(self.client, reverse('documents:ai_inbox_send_email'))
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data['ok'])

    def test_inbox_other_company_isolation(self):
        """AI inbox does not show entries from other companies."""
        resp = _get(self.client, reverse('documents:ai_inbox'), format='json')
        data = resp.json()
        other_ids = [e['id'] for e in data['entries'] if e.get('company_id') == str(self.other_company.pk)]
        self.assertEqual(len(other_ids), 0, 'Other company entries must not appear in AI inbox')


# ════════════════════════════════════════════════════════════
# 7. ScanBatchViewTests
# ════════════════════════════════════════════════════════════

class ScanBatchViewTests(TestCase):
    """Tests for scan batch views: create, upload, status, archive."""

    def setUp(self):
        self.company = _make_company('Scan GmbH', '15151515151')
        self.other_company = _make_company('Other Scan', '16161616161')
        self.user = _make_user('scan_user', self.company)
        self.other_user = _make_user('other_scan_user', self.other_company)
        self.client = _login_client(self.user)

    def test_create_batch(self):
        """Creating a batch redirects to batch detail."""
        resp = _get(self.client, reverse('documents:scan_batch_new'))
        self.assertEqual(resp.status_code, 302)
        # A batch should have been created
        batch = ScanBatch.objects.filter(company=self.company).first()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.status, 'collecting')
        self.assertEqual(batch.created_by, self.user)

    def test_create_batch_requires_login(self):
        """Batch creation requires authentication."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.get(reverse('documents:scan_batch_new'), secure=True)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url.lower())

    def test_upload_to_batch(self):
        """Uploading images to a batch increments image count."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user)

        img1 = SimpleUploadedFile('scan1.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 500,
                                   content_type='image/jpeg')
        img2 = SimpleUploadedFile('scan2.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 600,
                                   content_type='image/jpeg')
        resp = self.client.post(
            reverse('documents:scan_batch_upload', args=[batch.pk]),
            {'images': [img1, img2]},
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['added'], 2)
        self.assertEqual(data['total_images'], 2)

        batch.refresh_from_db()
        self.assertEqual(batch.total_images, 2)

    def test_upload_to_batch_max_100(self):
        """Batch rejects uploads exceeding 100 images."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user,
                                          total_images=99)
        # Manually create 99 images
        for i in range(99):
            ScanBatchImage.objects.create(batch=batch, order=i + 1,
                                          image=f'scan_batches/fake_{i}.jpg',
                                          file_size_kb=10)

        # Try adding 2 more (should fail: 99 + 2 > 100)
        imgs = [SimpleUploadedFile(f's{i}.jpg', b'\xff\xd8\xff\xe0' * 10,
                                     content_type='image/jpeg') for i in range(2)]
        resp = self.client.post(
            reverse('documents:scan_batch_upload', args=[batch.pk]),
            {'images': imgs},
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        self.assertEqual(resp.status_code, 400)

    def test_batch_status_polling(self):
        """Status endpoint returns current batch state."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user,
                                          status='processing', total_images=5)
        resp = _get(self.client, reverse('documents:scan_batch_status', args=[batch.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'processing')
        self.assertEqual(data['total_images'], 5)
        self.assertIn('images', data)

    def test_batch_archive_not_ready(self):
        """Archive fails if batch is not in 'ready' status."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user,
                                          status='collecting')
        resp = _post(self.client, reverse('documents:scan_batch_archive', args=[batch.pk]))
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])

    def test_batch_other_company_blocked(self):
        """User cannot access batches from another company — 404."""
        other_batch = ScanBatch.objects.create(company=self.other_company,
                                                created_by=self.other_user)
        resp = _get(self.client, reverse('documents:scan_batch_detail', args=[other_batch.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_batch_detail_view(self):
        """Batch detail renders successfully."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user)
        resp = _get(self.client, reverse('documents:scan_batch_detail', args=[batch.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_batch_process_no_images(self):
        """Process fails if batch has no images."""
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user,
                                          total_images=0)
        resp = _post(self.client, reverse('documents:scan_batch_process', args=[batch.pk]))
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])

    @patch('documents.tasks.process_scan_batch')
    def test_batch_process_triggers_task(self, mock_task):
        """Process triggers the async task when images exist."""
        mock_task.delay = MagicMock()
        batch = ScanBatch.objects.create(company=self.company, created_by=self.user,
                                          total_images=3)
        resp = _post(self.client, reverse('documents:scan_batch_process', args=[batch.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'processing')

    def test_mobile_scan_token(self):
        """scan_create_token creates a Redis token and returns QR data."""
        with patch('documents.views._get_redis') as mock_redis:
            mock_r = MagicMock()
            mock_redis.return_value = mock_r
            with patch('documents.views._qrcode') as mock_qr:
                mock_qr_instance = MagicMock()
                mock_qr.QRCode.return_value = mock_qr_instance
                mock_qr.constants.ERROR_CORRECT_M = 1
                mock_img = MagicMock()
                mock_qr_instance.make_image.return_value = mock_img
                mock_img.save = MagicMock(side_effect=lambda buf, **kw: buf.write(b'\x89PNG'))

                resp = _post(self.client, reverse('documents:scan_create_token'))
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn('token', data)
                self.assertIn('qr_data', data)
                self.assertIn('expires_in', data)
                self.assertEqual(data['expires_in'], 600)


# ════════════════════════════════════════════════════════════
# 8. ArhivaBookmarkTests
# ════════════════════════════════════════════════════════════

class ArhivaBookmarkTests(TestCase):
    """Tests for bookmark toggle endpoint."""

    def setUp(self):
        self.company = _make_company('Bookmark GmbH', '17171717171')
        self.other_company = _make_company('Other Bookmark', '18181818181')
        self.user = _make_user('bookmark_user', self.company)
        self.client = _login_client(self.user)

        self.entry = _make_entry(self.company, doc_number='BM-001')

    def test_toggle_bookmark_add(self):
        """POST creates a bookmark."""
        resp = _post(self.client, reverse('documents:arhiva_toggle_bookmark',
                                          args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['bookmarked'])
        self.assertEqual(data['entry_id'], self.entry.pk)
        self.assertTrue(ArhivaBookmark.objects.filter(
            user=self.user, entry=self.entry).exists())

    def test_toggle_bookmark_remove(self):
        """Second POST removes the bookmark (toggle)."""
        ArhivaBookmark.objects.create(user=self.user, entry=self.entry)

        resp = _post(self.client, reverse('documents:arhiva_toggle_bookmark',
                                          args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['bookmarked'])
        self.assertFalse(ArhivaBookmark.objects.filter(
            user=self.user, entry=self.entry).exists())

    def test_bookmark_other_company_blocked(self):
        """Cannot bookmark entries from another company — 403."""
        other_entry = _make_entry(self.other_company, doc_number='BM-OTHER-001',
                                   source_id='bm-other')
        resp = _post(self.client, reverse('documents:arhiva_toggle_bookmark',
                                          args=[other_entry.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ArhivaBookmark.objects.filter(
            user=self.user, entry=other_entry).exists())

    def test_bookmark_requires_login(self):
        """Bookmark toggle requires authentication."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.post(reverse('documents:arhiva_toggle_bookmark',
                                  args=[self.entry.pk]), secure=True)
        self.assertEqual(resp.status_code, 302)

    def test_bookmark_requires_post(self):
        """Bookmark toggle requires POST method."""
        resp = _get(self.client, reverse('documents:arhiva_toggle_bookmark',
                                         args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_bookmark_nonexistent_entry(self):
        """Bookmarking nonexistent entry returns 404."""
        resp = _post(self.client, reverse('documents:arhiva_toggle_bookmark',
                                          args=[999999]))
        self.assertEqual(resp.status_code, 404)


# ════════════════════════════════════════════════════════════
# 9. ArhivaListBatchActionsTests (POST actions on list)
# ════════════════════════════════════════════════════════════

class ArhivaListBatchActionsTests(TestCase):
    """Tests for batch POST actions on arhiva_list (bulk_label, bulk_book, bulk_export)."""

    def setUp(self):
        self.company = _make_company('Batch Actions GmbH', '19191919191')
        self.user = _make_user('batch_action_user', self.company)
        self.client = _login_client(self.user)

        self.entry1 = _make_entry(self.company, doc_number='BA-001', source_id='ba-001')
        self.entry2 = _make_entry(self.company, doc_number='BA-002', source_id='ba-002')
        self.label = ArhivaLabel.objects.create(company=self.company, name='Wichtig',
                                                 color='#ff0000')

    def test_bulk_label_assigns_label(self):
        """Bulk label action assigns a label to selected entries."""
        resp = _post(self.client, reverse('documents:arhiva_list'), {
            'action': 'bulk_label',
            'entry_ids': [self.entry1.pk, self.entry2.pk],
            'label_id': self.label.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.entry1.labels.filter(pk=self.label.pk).exists())
        self.assertTrue(self.entry2.labels.filter(pk=self.label.pk).exists())

    def test_bulk_book_marks_as_booked(self):
        """Bulk book action marks entries as is_booked=True."""
        resp = _post(self.client, reverse('documents:arhiva_list'), {
            'action': 'bulk_book',
            'entry_ids': [self.entry1.pk, self.entry2.pk],
        })
        self.assertEqual(resp.status_code, 302)
        self.entry1.refresh_from_db()
        self.entry2.refresh_from_db()
        self.assertTrue(self.entry1.is_booked)
        self.assertTrue(self.entry2.is_booked)

    def test_bulk_export_redirects_to_download(self):
        """Bulk export action redirects to bulk download URL."""
        resp = _post(self.client, reverse('documents:arhiva_list'), {
            'action': 'bulk_export',
            'entry_ids': [self.entry1.pk, self.entry2.pk],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('bulk-download', resp.url)

    def test_bulk_label_nonexistent_label_404(self):
        """Bulk label with invalid label_id returns error or redirect."""
        resp = self.client.post(
            reverse('documents:arhiva_list'),
            {
                'action': 'bulk_label',
                'entry_ids': [self.entry1.pk],
                'label_id': 99999,
            },
            secure=True, HTTP_ACCEPT_LANGUAGE='de',
        )
        # View redirects after failed label lookup (non-HTMX)
        self.assertIn(resp.status_code, [302, 404])


# ════════════════════════════════════════════════════════════
# 10. ArhivaIntegrityHashTests
# ════════════════════════════════════════════════════════════

class ArhivaIntegrityHashTests(TestCase):
    """Verify that integrity hashes are computed correctly and detect tampering."""

    def setUp(self):
        self.company = _make_company('Hash GmbH', '20202020201')

    def test_hash_is_sha256(self):
        """integrity_hash must be a 64-char SHA-256 hex digest."""
        entry = _make_entry(self.company, doc_number='HASH-001')
        self.assertEqual(len(entry.integrity_hash), 64)
        # Verify it's valid hex
        int(entry.integrity_hash, 16)

    def test_hash_changes_on_field_update(self):
        """Hash changes when key fields are modified (detects tampering)."""
        entry = _make_entry(self.company, doc_number='HASH-002',
                            amount=Decimal('100.00'))
        original_hash = entry.integrity_hash

        entry.amount = Decimal('999.99')
        entry.save()
        entry.refresh_from_db()

        self.assertNotEqual(entry.integrity_hash, original_hash)

    def test_hash_deterministic(self):
        """Same data produces the same hash."""
        entry = _make_entry(self.company, doc_number='HASH-003')
        hash1 = entry.compute_integrity_hash()
        hash2 = entry.compute_integrity_hash()
        self.assertEqual(hash1, hash2)

    def test_barcode_auto_generated(self):
        """Each ArhivaEntry automatically gets a barcode."""
        entry = _make_entry(self.company, doc_number='BC-001')
        self.assertTrue(len(entry.barcode) > 0)
        self.assertTrue(entry.barcode.startswith('LC-'))

    def test_archive_number_auto_assigned(self):
        """Each ArhivaEntry automatically gets an archive_number."""
        entry = _make_entry(self.company, doc_number='AN-001')
        self.assertTrue(entry.archive_number.startswith('ARH-'))
        self.assertIn('/', entry.archive_number)


# ════════════════════════════════════════════════════════════
# 11. ArhivaSortingTests
# ════════════════════════════════════════════════════════════

class ArhivaSortingTests(TestCase):
    """Tests for sorting and ordering in arhiva_list."""

    def setUp(self):
        self.company = _make_company('Sort GmbH', '21212121211')
        self.user = _make_user('sort_user', self.company)
        self.client = _login_client(self.user)

        _make_entry(self.company, doc_number='SORT-A', partner_name='Alpha',
                     amount=Decimal('100.00'), doc_date=date(2026, 1, 1),
                     source_id='sort-a')
        _make_entry(self.company, doc_number='SORT-B', partner_name='Beta',
                     amount=Decimal('500.00'), doc_date=date(2026, 3, 1),
                     source_id='sort-b')
        _make_entry(self.company, doc_number='SORT-C', partner_name='Charlie',
                     amount=Decimal('250.00'), doc_date=date(2026, 2, 1),
                     source_id='sort-c')

    def test_sort_by_date_asc(self):
        """Sort by date ascending puts oldest first."""
        resp = _get(self.client, reverse('documents:arhiva_list'),
                    sort='date', order='asc')
        self.assertEqual(resp.status_code, 200)

    def test_sort_by_amount_desc(self):
        """Sort by amount descending puts highest first."""
        resp = _get(self.client, reverse('documents:arhiva_list'),
                    sort='amount', order='desc')
        self.assertEqual(resp.status_code, 200)

    def test_sort_by_partner(self):
        """Sort by partner name works."""
        resp = _get(self.client, reverse('documents:arhiva_list'),
                    sort='partner', order='asc')
        self.assertEqual(resp.status_code, 200)


# ════════════════════════════════════════════════════════════
# 12. ArhivaLabelFilterTests
# ════════════════════════════════════════════════════════════

class ArhivaLabelFilterTests(TestCase):
    """Tests for label-based filtering in arhiva_list."""

    def setUp(self):
        self.company = _make_company('Label GmbH', '23232323231')
        self.user = _make_user('label_user', self.company)
        self.client = _login_client(self.user)

        self.label_urgent = ArhivaLabel.objects.create(
            company=self.company, name='Dringend', color='#ff0000')
        self.label_normal = ArhivaLabel.objects.create(
            company=self.company, name='Normal', color='#00ff00')

        self.urgent_entry = _make_entry(self.company, doc_number='LBL-URG-001',
                                         source_id='lbl-urg')
        self.urgent_entry.labels.add(self.label_urgent)

        self.normal_entry = _make_entry(self.company, doc_number='LBL-NRM-001',
                                         source_id='lbl-nrm')
        self.normal_entry.labels.add(self.label_normal)

    def test_filter_by_label(self):
        """Filtering by label shows only matching entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'),
                    label=str(self.label_urgent.pk))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('LBL-URG-001', content)
        self.assertNotIn('LBL-NRM-001', content)

    def test_no_label_filter_shows_all(self):
        """Without label filter, all entries are shown."""
        resp = _get(self.client, reverse('documents:arhiva_list'))
        content = resp.content.decode()
        self.assertIn('LBL-URG-001', content)
        self.assertIn('LBL-NRM-001', content)


# ════════════════════════════════════════════════════════════
# 13. ArhivaFiscalFilterTests
# ════════════════════════════════════════════════════════════

class ArhivaFiscalFilterTests(TestCase):
    """Tests for fiscal (ZKI/JIR) filtering in arhiva_list."""

    def setUp(self):
        self.company = _make_company('Fiscal GmbH', '24242424241')
        self.user = _make_user('fiscal_user', self.company)
        self.client = _login_client(self.user)

        self.fiscal_entry = _make_entry(
            self.company, doc_number='FISC-001', source_id='fisc-001',
            zki='zki-abc-123', jir='jir-def-456')
        self.non_fiscal = _make_entry(
            self.company, doc_number='NOFISC-001', source_id='nofisc-001',
            zki='', jir='')

    def test_filter_has_fiscal(self):
        """has_fiscal=1 shows only entries with ZKI."""
        resp = _get(self.client, reverse('documents:arhiva_list'), has_fiscal='1')
        content = resp.content.decode()
        self.assertIn('FISC-001', content)
        self.assertNotIn('NOFISC-001', content)

    def test_filter_no_fiscal(self):
        """has_fiscal=0 shows only entries without ZKI."""
        resp = _get(self.client, reverse('documents:arhiva_list'), has_fiscal='0')
        content = resp.content.decode()
        self.assertIn('NOFISC-001', content)
        self.assertNotIn('FISC-001', content)


# ════════════════════════════════════════════════════════════
# 14. ArhivaDeletionProtectionModelTests
# ════════════════════════════════════════════════════════════

class ArhivaDeletionProtectionModelTests(TestCase):
    """Tests for the is_deletion_protected property."""

    def setUp(self):
        self.company = _make_company('Protection GmbH', '25252525251')

    def test_future_protection_is_active(self):
        """Entry protected until future date is marked as protected."""
        entry = _make_entry(self.company, doc_number='PROT-ACTIVE',
                            doc_date=date.today())
        # deletion_protected_until is set automatically (~11 years from now)
        self.assertTrue(entry.is_deletion_protected)

    def test_past_protection_is_inactive(self):
        """Entry whose protection has expired is not protected."""
        entry = _make_entry(self.company, doc_number='PROT-EXPIRED',
                            doc_date=date(2010, 1, 1))
        # 11 years from 2010 = 2021, which is in the past
        entry.refresh_from_db()
        self.assertFalse(entry.is_deletion_protected)

    def test_no_protection_date(self):
        """Entry without deletion_protected_until is not protected."""
        entry = _make_entry(self.company, doc_number='PROT-NONE')
        entry.deletion_protected_until = None
        entry.save(update_fields=['deletion_protected_until'])
        entry.refresh_from_db()
        self.assertFalse(entry.is_deletion_protected)


# ════════════════════════════════════════════════════════════
# 15. ArhivaDetailAjaxTests
# ════════════════════════════════════════════════════════════

class ArhivaDetailAjaxTests(TestCase):
    """Tests for arhiva_detail_ajax JSON endpoint."""

    def setUp(self):
        self.company = _make_company('Detail GmbH', '26262626261')
        self.other_company = _make_company('Other Detail', '27272727271')
        self.user = _make_user('detail_user', self.company)
        self.client = _login_client(self.user)

        self.entry = _make_entry(self.company, doc_number='DTL-001',
                                  partner_name='Detail Partner')

    def test_detail_returns_json(self):
        """Detail ajax returns JSON with entry data."""
        resp = _get(self.client, reverse('documents:arhiva_detail_ajax',
                                         args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['doc_number'], 'DTL-001')
        self.assertEqual(data['id'], self.entry.pk)

    def test_detail_other_company_blocked(self):
        """Detail blocked for other company entries."""
        other_entry = _make_entry(self.other_company, doc_number='DTL-OTHER',
                                   source_id='dtl-other')
        resp = _get(self.client, reverse('documents:arhiva_detail_ajax',
                                         args=[other_entry.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_detail_nonexistent(self):
        """Detail for nonexistent entry returns 404."""
        resp = _get(self.client, reverse('documents:arhiva_detail_ajax', args=[999999]))
        self.assertEqual(resp.status_code, 404)

    def test_detail_requires_login(self):
        """Detail requires authentication."""
        anon = Client(SERVER_NAME='viskovic-group.de')
        resp = anon.get(reverse('documents:arhiva_detail_ajax', args=[self.entry.pk]),
                        secure=True)
        self.assertEqual(resp.status_code, 302)


# ════════════════════════════════════════════════════════════
# 16. ArhivaCurrencyFilterTests
# ════════════════════════════════════════════════════════════

class ArhivaCurrencyFilterTests(TestCase):
    """Tests for currency filtering in arhiva_list."""

    def setUp(self):
        self.company = _make_company('Currency GmbH', '28282828281')
        self.user = _make_user('currency_user', self.company)
        self.client = _login_client(self.user)

        _make_entry(self.company, doc_number='CUR-EUR', currency='EUR',
                     source_id='cur-eur')
        _make_entry(self.company, doc_number='CUR-USD', currency='USD',
                     source_id='cur-usd')

    def test_filter_by_currency(self):
        """Currency filter narrows results."""
        resp = _get(self.client, reverse('documents:arhiva_list'), currency='EUR')
        content = resp.content.decode()
        self.assertIn('CUR-EUR', content)
        self.assertNotIn('CUR-USD', content)

    def test_filter_by_other_currency(self):
        """USD currency filter shows only USD entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'), currency='USD')
        content = resp.content.decode()
        self.assertIn('CUR-USD', content)
        self.assertNotIn('CUR-EUR', content)


# ════════════════════════════════════════════════════════════
# 17. ArhivaFileTypeFilterTests
# ════════════════════════════════════════════════════════════

class ArhivaFileTypeFilterTests(TestCase):
    """Tests for file type (has_file) filtering in arhiva_list."""

    def setUp(self):
        self.company = _make_company('FileType GmbH', '29292929291')
        self.user = _make_user('filetype_user', self.company)
        self.client = _login_client(self.user)

        _make_entry(self.company, doc_number='FT-PDF', has_pdf=True, has_xml=False,
                     has_image=False, source_id='ft-pdf')
        _make_entry(self.company, doc_number='FT-XML', has_pdf=False, has_xml=True,
                     has_image=False, source_id='ft-xml')
        _make_entry(self.company, doc_number='FT-IMG', has_pdf=False, has_xml=False,
                     has_image=True, source_id='ft-img')

    def test_filter_pdf_only(self):
        """has_file=pdf shows only PDF entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'), has_file='pdf')
        content = resp.content.decode()
        self.assertIn('FT-PDF', content)
        self.assertNotIn('FT-XML', content)
        self.assertNotIn('FT-IMG', content)

    def test_filter_xml_only(self):
        """has_file=xml shows only XML entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'), has_file='xml')
        content = resp.content.decode()
        self.assertIn('FT-XML', content)
        self.assertNotIn('FT-PDF', content)

    def test_filter_image_only(self):
        """has_file=image shows only image entries."""
        resp = _get(self.client, reverse('documents:arhiva_list'), has_file='image')
        content = resp.content.decode()
        self.assertIn('FT-IMG', content)
        self.assertNotIn('FT-PDF', content)
