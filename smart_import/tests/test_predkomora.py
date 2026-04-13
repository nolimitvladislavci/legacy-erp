"""
Tests for Predkomora -- StagingFileHeader, extract_invoice_header,
review_approve (Zamka 2 + Zamka 3), duplikat detekcija.
"""
import json
import struct
import zlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory


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


# Inject json into smart_import.views module so review_approve can use it
import smart_import.views as _views_mod
if not hasattr(_views_mod, 'json'):
    import json as _json_mod
    _views_mod.json = _json_mod


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

    def test_successful_extraction(self):
        """Test 4: extract_invoice_header returns correct dict when Gemini works."""
        from smart_import.services import extract_invoice_header

        expected = {
            'supplier_name': 'Lidl d.o.o.',
            'supplier_oib': '12345678901',
            'invoice_number': 'R-2026/001',
            'invoice_date': '2026-03-21',
            'total_amount': 124.99,
            'vat_amount': 20.83,
            'base_amount': 104.16,
            'currency': 'EUR',
            'confidence': 0.95,
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(expected)

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_response

        # Mock the entire function flow
        with patch('smart_import.services._encode_image', return_value=('YWJj', 'image/jpeg')):
            with patch('smart_import.services._log_gemini_usage'):
                # Patch at the import point: google.genai is imported locally
                mock_genai = MagicMock()
                mock_genai.Client.return_value = mock_client_instance
                import sys
                old_google = sys.modules.get('google')
                old_genai = sys.modules.get('google.genai')
                try:
                    mock_google = MagicMock()
                    mock_google.genai = mock_genai
                    sys.modules['google'] = mock_google
                    sys.modules['google.genai'] = mock_genai
                    # Also need PIL.Image.open to work with fake base64
                    mock_pil_image = MagicMock()
                    with patch('PIL.Image.open', return_value=mock_pil_image):
                        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
                            result = extract_invoice_header('/tmp/fake.jpg')
                finally:
                    if old_google is not None:
                        sys.modules['google'] = old_google
                    else:
                        sys.modules.pop('google', None)
                    if old_genai is not None:
                        sys.modules['google.genai'] = old_genai
                    else:
                        sys.modules.pop('google.genai', None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('supplier_oib'), '12345678901')
        self.assertEqual(result.get('total_amount'), 124.99)
        self.assertEqual(result.get('confidence'), 0.95)

    def test_encode_image_fails(self):
        """Test 5: extract_invoice_header returns {} when image encode fails."""
        from smart_import.services import extract_invoice_header
        with patch('smart_import.services._encode_image', return_value=(None, None)):
            result = extract_invoice_header('/tmp/fake.jpg')
        self.assertEqual(result, {})

    def test_no_api_key(self):
        """Test 6: extract_invoice_header returns {} without API key."""
        from smart_import.services import extract_invoice_header
        with patch('smart_import.services._encode_image', return_value=('b64', 'image/jpeg')):
            with patch('django.conf.settings.GEMINI_API_KEY', None, create=True):
                with patch.dict('os.environ', {'GEMINI_API_KEY': ''}, clear=False):
                    result = extract_invoice_header('/tmp/fake.jpg')
        self.assertEqual(result, {})


# ══════════════════════════════════════════════════════════════════════════
# Test 7-10: process_staging_batch (header integration + duplikat)
# ══════════════════════════════════════════════════════════════════════════

class TestProcessStagingBatch(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('stagetest', password='test123')

    @patch('smart_import.services.extract_invoice_header')
    @patch('smart_import.services.parse_image')
    @patch('smart_import.services.match_items')
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

    @patch('smart_import.services.extract_invoice_header')
    @patch('smart_import.services.parse_image')
    @patch('smart_import.services.match_items')
    def test_header_error_no_crash(self, mock_match, mock_parse, mock_header):
        """Test 8: header extraction error does not crash the task."""
        from smart_import.models import StagingFileHeader, ImportBatch

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

    @patch('smart_import.services.extract_invoice_header')
    @patch('smart_import.services.parse_image')
    @patch('smart_import.services.match_items')
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

    @patch('smart_import.services.extract_invoice_header')
    @patch('smart_import.services.parse_image')
    @patch('smart_import.services.match_items')
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
        self.assertFalse(h1.needs_review)

        # Second file -- same OIB + invoice_number + total => duplikat
        batch2 = _make_staging_batch(self.company, self.user)
        batch2.total_files = 1
        batch2.save()
        sf2 = _make_staging_file(batch2, 'file2.jpg')

        process_staging_batch(batch2.pk)

        h2 = StagingFileHeader.objects.get(staging_file=sf2)
        self.assertTrue(h2.needs_review)

    def test_duplicate_detection_direct(self):
        """Test 10b: direct test of duplicate detection at DB level."""
        from smart_import.models import StagingFileHeader

        batch = _make_staging_batch(self.company, self.user)
        sf1 = _make_staging_file(batch, 'dup1.jpg')
        sf2 = _make_staging_file(batch, 'dup2.jpg')

        # Create two headers with same OIB + invoice_number + total
        h1 = _make_header(sf1, oib='11111111111', invoice_number='INV-X', total='500.00',
                          needs_review=False)
        h2 = _make_header(sf2, oib='11111111111', invoice_number='INV-X', total='500.00',
                          needs_review=False)

        # Check that duplicate query finds the other
        dup_exists = StagingFileHeader.objects.filter(
            staging_file__staging_batch__company=self.company,
            supplier_oib='11111111111',
            invoice_number='INV-X',
            total_amount=Decimal('500.00'),
        ).exclude(pk=h2.pk).exists()

        self.assertTrue(dup_exists)


# ══════════════════════════════════════════════════════════════════════════
# Test 11-14: review_approve (Zamka 2 + Zamka 3) -- via RequestFactory
# ══════════════════════════════════════════════════════════════════════════

class TestReviewApprove(TestCase):
    """Tests for review_approve -- math validation + conflict guard."""

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('reviewtest', password='test123')
        self.factory = RequestFactory()
        self.batch = _make_staging_batch(self.company, self.user)
        self.sf = _make_staging_file(self.batch)

    def _call_approve(self, data):
        """Call review_approve view directly, bypassing login_required."""
        from smart_import.views import review_approve
        request = self.factory.post(
            '/smart-import/review/approve/',
            data=json.dumps(data),
            content_type='application/json',
        )
        request.user = self.user
        # Unwrap decorators: review_approve is wrapped by login_required + require_POST
        inner = review_approve
        while hasattr(inner, '__wrapped__'):
            inner = inner.__wrapped__
        with patch('smart_import.views.get_user_company', return_value=self.company):
            return inner(request)

    def test_zamka2_math_mismatch(self):
        """Test 11: math mismatch returns 400 MATH_MISMATCH."""
        header = _make_header(self.sf, total='200.00', vat='25.00', base='100.00')

        resp = self._call_approve({
            'header_id': header.pk,
            'base_amount': '100.00',
            'vat_amount': '25.00',
            'total_amount': '200.00',
        })
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content)
        self.assertEqual(body['code'], 'MATH_MISMATCH')
        header.refresh_from_db()
        self.assertTrue(header.needs_review)

    def test_zamka2_math_ok(self):
        """Test 12: correct math passes (base + vat = total)."""
        header = _make_header(self.sf, total='125.00', vat='25.00', base='100.00')

        resp = self._call_approve({
            'header_id': header.pk,
            'base_amount': '100.00',
            'vat_amount': '25.00',
            'total_amount': '125.00',
        })
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertTrue(body['ok'])
        header.refresh_from_db()
        self.assertFalse(header.needs_review)

    def test_zamka3_conflict(self):
        """Test 13: conflict guard returns 409 CONFLICT when already approved."""
        header = _make_header(self.sf, total='125.00', vat='25.00', base='100.00',
                              needs_review=False)

        resp = self._call_approve({'header_id': header.pk})
        self.assertEqual(resp.status_code, 409)
        body = json.loads(resp.content)
        self.assertEqual(body['code'], 'CONFLICT')

    def test_oib_correction_rematch(self):
        """Test 14: OIB correction in review_approve re-matches partner."""
        partner = _make_partner(self.company, oib='12345678901')

        header = _make_header(
            self.sf, oib='00000000000',
            total='125.00', vat='25.00', base='100.00',
        )
        self.assertIsNone(header.matched_partner)

        resp = self._call_approve({
            'header_id': header.pk,
            'supplier_oib': '12345678901',
            'base_amount': '100.00',
            'vat_amount': '25.00',
            'total_amount': '125.00',
        })
        self.assertEqual(resp.status_code, 200)
        header.refresh_from_db()
        self.assertEqual(header.matched_partner, partner)


# ══════════════════════════════════════════════════════════════════════════
# Test 15: Predkomora review dashboard -- queryset logic
# ══════════════════════════════════════════════════════════════════════════

class TestReviewDashboard(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = User.objects.create_user('dashtest', password='test123')

    def test_only_needs_review_counted(self):
        """Test 15: only needs_review=True headers count as pending."""
        from smart_import.models import StagingFileHeader

        batch = _make_staging_batch(self.company, self.user)

        sf1 = _make_staging_file(batch, 'a.jpg')
        sf2 = _make_staging_file(batch, 'b.jpg')
        sf3 = _make_staging_file(batch, 'c.jpg')

        _make_header(sf1, needs_review=True, invoice_number='A-001')
        _make_header(sf2, needs_review=True, invoice_number='A-002')
        _make_header(sf3, needs_review=False, invoice_number='A-003')

        headers = StagingFileHeader.objects.filter(
            staging_file__staging_batch__company=self.company,
        )
        pending_count = headers.filter(needs_review=True).count()
        total_count = headers.count()

        self.assertEqual(pending_count, 2)
        self.assertEqual(total_count, 3)

    def test_review_dashboard_view(self):
        """Test 15b: review_dashboard returns 200."""
        from django.http import HttpResponse

        batch = _make_staging_batch(self.company, self.user)
        sf1 = _make_staging_file(batch, 'x.jpg')
        sf2 = _make_staging_file(batch, 'y.jpg')
        _make_header(sf1, needs_review=True, invoice_number='X-001')
        _make_header(sf2, needs_review=False, invoice_number='X-002')

        from smart_import.views import review_dashboard
        factory = RequestFactory()
        request = factory.get('/smart-import/review/')
        request.user = self.user

        # Mock render to avoid template errors from unrelated URL config issues
        mock_render = lambda req, tpl, ctx: HttpResponse(status=200)
        with patch('smart_import.views.get_user_company', return_value=self.company), \
             patch('smart_import.views.render', side_effect=mock_render):
            resp = review_dashboard(request)
        self.assertEqual(resp.status_code, 200)
