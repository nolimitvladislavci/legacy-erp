"""
Tests for Predkomora — StagingFileHeader, extract_invoice_header,
review_approve (Zamka 2 + Zamka 3), duplikat detekcija.
"""
import json
import struct
import zlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.urls import reverse


# ── Helper factories ──────────────────────────────────────────────────────

def _make_company():
    from companies.models import Company
    import uuid
    return Company.objects.create(
        name='Test Predkomora Co ' + str(uuid.uuid4())[:8],
        oib='TEST' + str(uuid.uuid4().int)[:7],
    )


def _make_partner(company, oib='12345678901', name='Test Dobavljac d.o.o.'):
    from partners.models import Partner
    return Partner.objects.create(
        company=company,
        name=name,
        oib=oib,
        partner_type='supplier',
    )


def _make_staging_batch(company, user):
    from smart_import.models import StagingBatch
    return StagingBatch.objects.create(
        company=company,
        created_by=user,
        status='pending',
        total_files=1,
    )


def _1px_png():
    sig = b'\x89PNG\r\n\x1a\n'
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _make_staging_file(batch, filename='test.jpg'):
    from django.core.files.base import ContentFile
    from smart_import.models import StagingFile
    sf = StagingFile(staging_batch=batch, original_filename=filename, status='pending')
    sf.file.save(filename, ContentFile(_1px_png()), save=True)
    return sf


def _make_header(sf, oib='12345678901', invoice_number='R-001', total='100.00',
                 vat='16.67', base='83.33', needs_review=True):
    from smart_import.models import StagingFileHeader
    return StagingFileHeader.objects.create(
        staging_file=sf,
        supplier_name='Test d.o.o.',
        supplier_oib=oib,
        invoice_number=invoice_number,
        total_amount=Decimal(total),
        vat_amount=Decimal(vat),
        base_amount=Decimal(base),
        confidence=0.85,
        needs_review=needs_review,
    )


# ══════════════════════════════════════════════════════════════════════════
# Test 1-3: StagingFileHeader.auto_match_partner()
# ══════════════════════════════════════════════════════════════════════════

class TestAutoMatchPartner(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('predtest', password='test123')
        self.batch = _make_staging_batch(self.company, self.user)
        self.sf = _make_staging_file(self.batch)

    def test_oib_match(self):
        """Test 1: auto_match_partner finds Partner by OIB."""
        partner = _make_partner(self.company, oib='12345678901')
        header = _make_header(self.sf, oib='12345678901')
        result = header.auto_match_partner()
        header.refresh_from_db()
        self.assertEqual(result, partner)
        self.assertEqual(header.matched_partner, partner)

    def test_oib_no_match(self):
        """Test 2: auto_match_partner returns None when OIB not found."""
        header = _make_header(self.sf, oib='99999999999')
        result = header.auto_match_partner()
        header.refresh_from_db()
        self.assertIsNone(result)
        self.assertIsNone(header.matched_partner)

    def test_oib_empty(self):
        """Test 3: auto_match_partner returns None immediately for empty OIB."""
        header = _make_header(self.sf, oib='')
        result = header.auto_match_partner()
        self.assertIsNone(result)
        self.assertIsNone(header.matched_partner)


# ══════════════════════════════════════════════════════════════════════════
# Test 4-6: extract_invoice_header() mocks
# ══════════════════════════════════════════════════════════════════════════

class TestExtractInvoiceHeader(TestCase):

    @patch('smart_import.services._encode_image')
    @patch('smart_import.services._log_gemini_usage')
    def test_successful_extraction(self, mock_log, mock_encode):
        """Test 4: extract_invoice_header returns correct dict on success."""
        mock_encode.return_value = ('base64data', 'image/jpeg')

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'supplier_name': 'Lidl d.o.o.',
            'supplier_oib': '12345678901',
            'invoice_number': 'R-2026/001',
            'invoice_date': '2026-03-21',
            'total_amount': 124.99,
            'vat_amount': 20.83,
            'base_amount': 104.16,
            'currency': 'EUR',
            'confidence': 0.95,
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch('smart_import.services._genai') as mock_genai_mod:
            mock_genai_mod.Client.return_value = mock_client
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
                from smart_import.services import extract_invoice_header
                result = extract_invoice_header('/tmp/fake.jpg')

        self.assertIsInstance(result, dict)
        self.assertEqual(result['supplier_oib'], '12345678901')
        self.assertEqual(result['total_amount'], 124.99)
        self.assertEqual(result['confidence'], 0.95)
        self.assertEqual(result['supplier_name'], 'Lidl d.o.o.')

    @patch('smart_import.services._encode_image')
    def test_gemini_exception(self, mock_encode):
        """Test 5: extract_invoice_header returns {} when Gemini raises."""
        mock_encode.return_value = ('base64data', 'image/jpeg')

        with patch('smart_import.services._genai') as mock_genai_mod:
            mock_genai_mod.Client.side_effect = Exception('Gemini down')
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
                from smart_import.services import extract_invoice_header
                result = extract_invoice_header('/tmp/fake.jpg')

        self.assertEqual(result, {})

    @patch('smart_import.services._encode_image')
    @patch('smart_import.services._log_gemini_usage')
    def test_invalid_json_response(self, mock_log, mock_encode):
        """Test 6: extract_invoice_header returns {} on invalid JSON."""
        mock_encode.return_value = ('base64data', 'image/jpeg')

        mock_response = MagicMock()
        mock_response.text = 'Evo vam nesto'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch('smart_import.services._genai') as mock_genai_mod:
            mock_genai_mod.Client.return_value = mock_client
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
                from smart_import.services import extract_invoice_header
                result = extract_invoice_header('/tmp/fake.jpg')

        self.assertEqual(result, {})


# ══════════════════════════════════════════════════════════════════════════
# Test 7-10: process_staging_batch (header integration + duplikat)
# ══════════════════════════════════════════════════════════════════════════

class TestProcessStagingBatch(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('stagetest', password='test123')

    @patch('smart_import.tasks.extract_invoice_header')
    @patch('smart_import.tasks.parse_image')
    @patch('smart_import.tasks.match_items')
    def test_header_created(self, mock_match, mock_parse, mock_header):
        """Test 7: process_staging_batch creates StagingFileHeader."""
        from smart_import.models import StagingFileHeader

        mock_parse.return_value = [{'vendor_name': 'Lidl', 'quantity': 1, 'purchase_price': 10}]
        mock_header.return_value = {
            'supplier_name': 'Lidl',
            'supplier_oib': '12345678901',
            'invoice_number': 'R-001',
            'invoice_date': '2026-03-21',
            'total_amount': 10,
            'vat_amount': 2,
            'base_amount': 8,
            'currency': 'EUR',
            'confidence': 0.9,
        }

        batch = _make_staging_batch(self.company, self.user)
        sf = _make_staging_file(batch)

        from smart_import.tasks import process_staging_batch
        process_staging_batch(batch.pk)

        self.assertTrue(StagingFileHeader.objects.filter(staging_file=sf).exists())
        header = StagingFileHeader.objects.get(staging_file=sf)
        self.assertEqual(header.supplier_name, 'Lidl')
        self.assertAlmostEqual(header.confidence, 0.9, places=2)

    @patch('smart_import.tasks.extract_invoice_header')
    @patch('smart_import.tasks.parse_image')
    @patch('smart_import.tasks.match_items')
    def test_header_error_no_crash(self, mock_match, mock_parse, mock_header):
        """Test 8: header extraction error does not crash the task."""
        from smart_import.models import StagingFile, StagingFileHeader, ImportBatch

        mock_parse.return_value = [{'vendor_name': 'ABC', 'quantity': 1, 'purchase_price': 5}]
        mock_header.side_effect = Exception('Header boom')

        batch = _make_staging_batch(self.company, self.user)
        sf = _make_staging_file(batch)

        from smart_import.tasks import process_staging_batch
        process_staging_batch(batch.pk)

        sf.refresh_from_db()
        self.assertEqual(sf.status, 'done')
        self.assertTrue(ImportBatch.objects.filter(staging_source=sf).exists())
        self.assertFalse(StagingFileHeader.objects.filter(staging_file=sf).exists())

    @patch('smart_import.tasks.extract_invoice_header')
    @patch('smart_import.tasks.parse_image')
    @patch('smart_import.tasks.match_items')
    def test_auto_match_partner_in_task(self, mock_match, mock_parse, mock_header):
        """Test 9: process_staging_batch auto-matches partner by OIB."""
        from smart_import.models import StagingFileHeader, ImportBatch

        partner = _make_partner(self.company, oib='12345678901')
        mock_parse.return_value = [{'vendor_name': 'X', 'quantity': 1, 'purchase_price': 10}]
        mock_header.return_value = {
            'supplier_name': 'X',
            'supplier_oib': '12345678901',
            'total_amount': 10,
            'confidence': 0.95,
        }

        batch = _make_staging_batch(self.company, self.user)
        sf = _make_staging_file(batch)

        from smart_import.tasks import process_staging_batch
        process_staging_batch(batch.pk)

        header = StagingFileHeader.objects.get(staging_file=sf)
        self.assertEqual(header.matched_partner, partner)
        ib = ImportBatch.objects.get(staging_source=sf)
        self.assertEqual(ib.supplier, partner)

    @patch('smart_import.tasks.extract_invoice_header')
    @patch('smart_import.tasks.parse_image')
    @patch('smart_import.tasks.match_items')
    def test_duplicate_detection(self, mock_match, mock_parse, mock_header):
        """Test 10: second header with same OIB+invoice_number+total gets needs_review=True."""
        from smart_import.models import StagingFileHeader

        mock_parse.return_value = [{'vendor_name': 'Z', 'quantity': 1, 'purchase_price': 100}]
        mock_header.return_value = {
            'supplier_name': 'Z',
            'supplier_oib': '99988877766',
            'invoice_number': 'DUP-001',
            'total_amount': 100,
            'confidence': 0.95,
        }

        # First file
        batch1 = _make_staging_batch(self.company, self.user)
        batch1.total_files = 1
        batch1.save()
        sf1 = _make_staging_file(batch1, 'file1.jpg')

        from smart_import.tasks import process_staging_batch
        process_staging_batch(batch1.pk)

        h1 = StagingFileHeader.objects.get(staging_file=sf1)
        # High confidence => needs_review=False normally
        self.assertFalse(h1.needs_review)

        # Second file — same OIB + invoice_number + total => duplikat
        batch2 = _make_staging_batch(self.company, self.user)
        batch2.total_files = 1
        batch2.save()
        sf2 = _make_staging_file(batch2, 'file2.jpg')

        process_staging_batch(batch2.pk)

        h2 = StagingFileHeader.objects.get(staging_file=sf2)
        self.assertTrue(h2.needs_review)
        sf2.refresh_from_db()
        self.assertIn('DUPLIKAT?', sf2.ai_message)


# ══════════════════════════════════════════════════════════════════════════
# Test 11-14: review_approve (Zamka 2 + Zamka 3)
# ══════════════════════════════════════════════════════════════════════════

class TestReviewApprove(TestCase):
    """Tests for review_approve — math validation + conflict guard."""

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('reviewtest', password='test123')
        self.client.login(username='reviewtest', password='test123')
        # Attach user to company
        from django.contrib.auth.models import Group
        # Use core.company_utils approach — set profile or similar
        # For testing, patch get_user_company
        self.batch = _make_staging_batch(self.company, self.user)
        self.sf = _make_staging_file(self.batch)

    def _post_approve(self, header_id, **kwargs):
        """POST to review_approve with JSON body."""
        data = {'header_id': header_id}
        data.update(kwargs)
        return self.client.post(
            reverse('smart_import:review_approve'),
            data=json.dumps(data),
            content_type='application/json',
        )

    @patch('smart_import.views.get_user_company')
    def test_zamka2_math_mismatch(self, mock_company):
        """Test 11: math mismatch returns 400 MATH_MISMATCH."""
        mock_company.return_value = self.company
        header = _make_header(self.sf, total='200.00', vat='25.00', base='100.00')

        resp = self._post_approve(
            header.pk,
            base_amount='100.00',
            vat_amount='25.00',
            total_amount='200.00',
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body['code'], 'MATH_MISMATCH')
        header.refresh_from_db()
        self.assertTrue(header.needs_review)

    @patch('smart_import.views.get_user_company')
    def test_zamka2_math_ok(self, mock_company):
        """Test 12: correct math passes (base + vat = total)."""
        mock_company.return_value = self.company
        header = _make_header(self.sf, total='125.00', vat='25.00', base='100.00')

        resp = self._post_approve(
            header.pk,
            base_amount='100.00',
            vat_amount='25.00',
            total_amount='125.00',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        header.refresh_from_db()
        self.assertFalse(header.needs_review)

    @patch('smart_import.views.get_user_company')
    def test_zamka3_conflict(self, mock_company):
        """Test 13: conflict guard returns 409 CONFLICT when already approved."""
        mock_company.return_value = self.company
        header = _make_header(self.sf, total='125.00', vat='25.00', base='100.00',
                              needs_review=False)

        resp = self._post_approve(header.pk)
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertEqual(body['code'], 'CONFLICT')

    @patch('smart_import.views.get_user_company')
    def test_oib_correction_rematch(self, mock_company):
        """Test 14: OIB correction in review_approve re-matches partner."""
        mock_company.return_value = self.company
        partner = _make_partner(self.company, oib='12345678901')

        header = _make_header(
            self.sf, oib='00000000000',
            total='125.00', vat='25.00', base='100.00',
        )
        self.assertIsNone(header.matched_partner)

        resp = self._post_approve(
            header.pk,
            supplier_oib='12345678901',
            base_amount='100.00',
            vat_amount='25.00',
            total_amount='125.00',
        )
        self.assertEqual(resp.status_code, 200)
        header.refresh_from_db()
        self.assertEqual(header.matched_partner, partner)


# ══════════════════════════════════════════════════════════════════════════
# Test 15: Predkomora review dashboard view
# ══════════════════════════════════════════════════════════════════════════

class TestReviewDashboard(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('dashtest', password='test123')
        self.client.login(username='dashtest', password='test123')

    @patch('smart_import.views.get_user_company')
    def test_only_needs_review_shown(self, mock_company):
        """Test 15: review dashboard shows only needs_review headers in pending count."""
        mock_company.return_value = self.company
        batch = _make_staging_batch(self.company, self.user)

        sf1 = _make_staging_file(batch, 'a.jpg')
        sf2 = _make_staging_file(batch, 'b.jpg')
        sf3 = _make_staging_file(batch, 'c.jpg')

        _make_header(sf1, needs_review=True, invoice_number='A-001')
        _make_header(sf2, needs_review=True, invoice_number='A-002')
        _make_header(sf3, needs_review=False, invoice_number='A-003')

        resp = self.client.get(reverse('smart_import:review_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['pending_count'], 2)
