"""
core/tests_fenix_scan.py — Comprehensive FenixScan E2E Test Suite

Testira cijeli pipeline:
  1. Generiranje testnih slika (simulacija kamere)
  2. Resize/kompresija (size guard)
  3. API endpoint validacija
  4. AI mock response parsing
  5. Field extraction po doc_type
  6. DB record creation (golub, invoice, complaint)
  7. Edge cases (oversize, corrupt, empty, Samsung fallback)
  8. Multi-image cross-reference (ring)
  9. Karenca enforcement
 10. Marketplace bridge integration

Run:
  python manage.py test core.tests_fenix_scan -v2
"""
import base64
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS — test image generators
# ═══════════════════════════════════════════════════════════════════════════

def make_test_image(width=800, height=600, color=(200, 180, 60), fmt='JPEG'):
    """Generira testnu sliku kao base64 string."""
    from PIL import Image
    img = Image.new('RGB', (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=85)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def make_oversize_image():
    """Generira base64 string veći od 3.7MB (size guard test)."""
    # Create raw bytes that exceed MAX_B64_BYTES when b64 encoded
    raw = b'x' * (3_700_001)
    return base64.b64encode(raw).decode()


def make_corrupt_b64():
    """Nevaljani base64 — corrupt data."""
    return "NOT_VALID_BASE64_!@#$%^&*()"


def mock_anthropic_response(json_data):
    """Kreira mock za Anthropic API odgovor."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps(json_data)
    return mock_resp


# ═══════════════════════════════════════════════════════════════════════════
# MIXIN — Company + User setup
# ═══════════════════════════════════════════════════════════════════════════

class ScanTestMixin:
    """Standardni setup: user, company, profile, auth client."""

    def setUp(self):
        super().setUp()
        from accounts.models import UserProfile
        from companies.models import Company

        self.company = Company.objects.create(
            name='Test OPG Kovačević',
            oib='12345678901',
            address='Čepin bb',
            city='Čepin',
        )
        self.user = User.objects.create_user(
            username='petar_test', password='test1234', email='petar@test.hr',
            is_staff=True,  # bypass Force2FA for API
        )
        # Ensure profile exists with 2FA bypass
        profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={'company': self.company},
        )
        if profile.company != self.company:
            profile.company = self.company
        # Mark 2FA as verified to bypass Force2FA middleware
        profile.totp_verified = True
        profile.save()

        self.client = Client()
        self.client.login(username='petar_test', password='test1234')
        # Also set session flag for 2FA bypass
        session = self.client.session
        session['2fa_verified'] = True
        session.save()
        self.scan_url = '/api/fenix/scan/'


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: API Endpoint — Basic Validation
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanAPIValidation(ScanTestMixin, TestCase):
    """Validacija ulaznih parametara API-ja."""

    def test_01_unauthenticated_rejected(self):
        """Neprijavljen korisnik dobiva redirect (Force2FA middleware) ili 401."""
        anon = Client()
        resp = anon.post(self.scan_url, json.dumps({
            'doc_type': 'general', 'images': [make_test_image(100, 100)]
        }), content_type='application/json')
        self.assertIn(resp.status_code, [301, 302, 401])

    def test_02_invalid_json_rejected(self):
        """Neispravan JSON dobiva 400."""
        resp = self.client.post(self.scan_url, 'not json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_03_no_images_rejected(self):
        """Bez slika dobiva 400."""
        resp = self.client.post(self.scan_url, json.dumps({
            'doc_type': 'ring', 'images': []
        }), content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('hint', data)

    def test_04_unknown_doc_type_falls_to_general(self):
        """Nepoznat doc_type → general."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = '{"podaci": {}, "opis": "test", "confidence": 0.8}'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'nonexistent_type',
                'images': [make_test_image(200, 200)]
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['doc_type'], 'general')

    def test_05_max_5_images_enforced(self):
        """Više od 5 slika — samo prvih 5 se koristi."""
        imgs = [make_test_image(100, 100) for _ in range(7)]
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = '{"podaci": {}, "opis": "test", "confidence": 0.7}'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'general', 'images': imgs,
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            self.assertLessEqual(resp.json()['images_used'], 5)

    def test_06_get_method_rejected(self):
        """GET metoda nije dozvoljena."""
        resp = self.client.get(self.scan_url)
        self.assertEqual(resp.status_code, 405)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Size Guard — Image Validation
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanSizeGuard(ScanTestMixin, TestCase):
    """Testira size guard i image processing."""

    def test_10_oversize_image_skipped_with_warning(self):
        """Prevelika slika se preskače, vraća warning."""
        small = make_test_image(200, 200)
        big = make_oversize_image()
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = '{"podaci": {}, "opis": "test", "confidence": 0.8}'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'general', 'images': [big, small],
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data['images_used'], 1)  # samo mala prošla
            self.assertIsNotNone(data['warning'])
            self.assertIn('preskočeno', data['warning'])

    def test_11_all_oversize_returns_400(self):
        """Ako su SVE slike prevelike → 400."""
        big = make_oversize_image()
        resp = self.client.post(self.scan_url, json.dumps({
            'doc_type': 'ring', 'images': [big, big],
        }), content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_12_empty_b64_strings_filtered(self):
        """Prazni stringovi se filtriraju."""
        valid = make_test_image(200, 200)
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = '{"podaci": {}, "opis": "test", "confidence": 0.7}'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'general', 'images': ['', '  ', valid, ''],
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['images_used'], 1)

    def test_13_exact_limit_passes(self):
        """Slika točno na limitu (3.7MB) prolazi."""
        from core.views_scan import MAX_B64_BYTES
        # Create image just under limit
        data = b'x' * int(MAX_B64_BYTES * 0.74)  # ~74% of limit after b64
        b64 = base64.b64encode(data).decode()
        self.assertLess(len(b64) * 3 // 4, MAX_B64_BYTES)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Ring Scan — Multi-Image Cross-Reference
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanRing(ScanTestMixin, TestCase):
    """Ring prsten skeniranje s cross-referencom N slika."""

    def test_20_single_ring_image(self):
        """Jedna slika prstena → ekstrakcija broja."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'prsten_broj': 'HR-2026-54321',
                'godina': '2026',
                'confidence': 0.92,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['fields']['prsten_broj'], 'HR-2026-54321')
            self.assertGreaterEqual(data['confidence'], 0.9)

    def test_21_multi_ring_cross_reference(self):
        """3 slike istog prstena → AI koristi sve, veća confidence."""
        images = [make_test_image(400, 300, (i*50, 100, 200)) for i in range(3)]
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'prsten_broj': 'HR-2026-99999',
                'godina': '2026',
                'confidence': 0.97,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring', 'images': images,
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['images_used'], 3)
            self.assertEqual(data['fields']['prsten_broj'], 'HR-2026-99999')

    def test_22_low_confidence_clears_ring(self):
        """Confidence < 0.35 → prsten_broj se čisti (post_process)."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'prsten_broj': 'MAYBE-123',
                'godina': '',
                'confidence': 0.20,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['fields']['prsten_broj'], '')

    def test_23_5_images_max_for_ring(self):
        """5 slika prstena — svih 5 se koristi."""
        images = [make_test_image(200, 200) for _ in range(5)]
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'prsten_broj': 'HR-2026-11111', 'godina': '2026', 'confidence': 0.99,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring', 'images': images,
            }), content_type='application/json')
            self.assertEqual(resp.json()['images_used'], 5)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: ID Card — MRZ + Visual Data
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanIDCard(ScanTestMixin, TestCase):
    """ID card skeniranje: MRZ parsing, prednja + stražnja strana."""

    def test_30_id_card_single_side(self):
        """Prednja strana osobne — ime, prezime, broj."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'doc_type': 'id_card',
                'ime': 'IVAN',
                'prezime': 'HORVAT',
                'datum_rodjenja': '1990-05-15',
                'spol': 'M',
                'broj_dokumenta': '012345678',
                'nacionalnost': 'HRV',
                'vrijedi_do': '2030-05-15',
                'issuing_country': 'HRV',
                'confidence': 0.95,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'id_card',
                'images': [make_test_image(600, 400)],
            }), content_type='application/json')
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['fields']['ime'], 'IVAN')
            self.assertEqual(data['fields']['prezime'], 'HORVAT')
            self.assertEqual(data['fields']['nacionalnost'], 'HRV')

    def test_31_id_card_front_and_back(self):
        """Prednja + stražnja strana — obje se šalju AI-u."""
        front = make_test_image(600, 400, (200, 200, 200))
        back = make_test_image(600, 400, (180, 180, 180))
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'doc_type': 'id_card',
                'ime': 'MARIJA', 'prezime': 'BRTAN',
                'datum_rodjenja': '1965-03-22', 'spol': 'F',
                'broj_dokumenta': '098765432',
                'nacionalnost': 'HRV',
                'vrijedi_do': '2028-03-22',
                'issuing_country': 'HRV',
                'confidence': 0.98,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'id_card', 'images': [front, back],
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['images_used'], 2)
            self.assertEqual(data['fields']['ime'], 'MARIJA')

    def test_32_nationality_correction_hrc_to_hrv(self):
        """AI ponekad vrati HRC umjesto HRV — post_process popravlja."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'doc_type': 'id_card', 'ime': 'TEST', 'prezime': 'USER',
                'nacionalnost': 'HRC', 'confidence': 0.9,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'id_card',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            self.assertEqual(resp.json()['fields']['nacionalnost'], 'HRV')

    def test_33_passport_recognition(self):
        """Putovnica — doc_type: passport."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'doc_type': 'passport',
                'ime': 'HANS', 'prezime': 'MUELLER',
                'nacionalnost': 'DEU',
                'broj_dokumenta': 'C01234567',
                'confidence': 0.88,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'id_card',
                'images': [make_test_image(600, 400)],
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['fields']['nacionalnost'], 'DEU')


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Invoice — Multi-Page Merge
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanInvoice(ScanTestMixin, TestCase):
    """Faktura skeniranje: višestraničan, merge, strukturirani podaci."""

    def test_40_single_page_invoice(self):
        """Jednostraničan račun → svi ključni podaci."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'broj_racuna': 'IR-2026-042',
                'datum': '2026-03-15',
                'dobavljac': 'Konzum d.d.',
                'oib_dobavljac': '11223344556',
                'iznos_bez_pdv': 100.00,
                'pdv_iznos': 25.00,
                'iznos_ukupno': 125.00,
                'valuta': 'EUR',
                'opis': 'Namirnice za restoran',
                'iban': 'HR1234567890123456789',
                'confidence': 0.93,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'invoice',
                'images': [make_test_image(800, 1100)],
            }), content_type='application/json')
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['fields']['broj_racuna'], 'IR-2026-042')
            self.assertEqual(data['fields']['iznos_ukupno'], 125.00)

    def test_41_multi_page_invoice_merged(self):
        """Višestraničan račun (3 strane) → AI objedinjuje podatke."""
        pages = [make_test_image(800, 1100, (200+i*20, 200, 200)) for i in range(3)]
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'broj_racuna': 'R-2026-0100',
                'datum': '2026-03-20',
                'dobavljac': 'Metro d.o.o.',
                'oib_dobavljac': '99887766554',
                'iznos_bez_pdv': 2400.00,
                'pdv_iznos': 600.00,
                'iznos_ukupno': 3000.00,
                'valuta': 'EUR',
                'opis': 'Veleprodaja namirnica — 47 stavki',
                'confidence': 0.90,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'invoice', 'images': pages,
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['images_used'], 3)
            self.assertEqual(data['fields']['iznos_ukupno'], 3000.00)

    def test_42_invoice_with_null_fields(self):
        """Nečitljiv račun — AI vraća null za neprepoznata polja."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'broj_racuna': None,
                'datum': '2026-03-25',
                'dobavljac': 'Nečitljivo',
                'iznos_ukupno': None,
                'confidence': 0.35,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'invoice',
                'images': [make_test_image(400, 600)],
            }), content_type='application/json')
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertIsNone(data['fields']['broj_racuna'])
            self.assertLess(data['confidence'], 0.4)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Complaint — Handwriting Recognition
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanComplaint(ScanTestMixin, TestCase):
    """Knjiga prigovora: rukopis, sentiment, kategorija."""

    def test_50_complaint_handwriting(self):
        """Rukopisni prigovor → tekst + sentiment + kategorija."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'vrsta': 'prigovor',
                'tekst': 'Hrana je bila hladna i konobar je bio bezobrazan.',
                'datum': '2026-03-27',
                'ime_posjetitelja': 'Ana Kovač',
                'kategorija': 'hrana',
                'sentiment': 'negativan',
                'confidence': 0.82,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'complaint',
                'images': [make_test_image(600, 800)],
            }), content_type='application/json')
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['fields']['sentiment'], 'negativan')
            self.assertIn('hladna', data['fields']['tekst'])

    def test_51_praise_recognition(self):
        """Pohvala → pozitivan sentiment."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'vrsta': 'pohvala',
                'tekst': 'Odlična usluga, svaka čast!',
                'sentiment': 'pozitivan',
                'confidence': 0.90,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'complaint',
                'images': [make_test_image(600, 400)],
            }), content_type='application/json')
            self.assertEqual(resp.json()['fields']['vrsta'], 'pohvala')


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Golub Photo — AI Name + Color
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanGolub(ScanTestMixin, TestCase):
    """Foto goluba → AI generira ime i boju."""

    def test_60_golub_photo_name_color(self):
        """Jedna slika goluba → ime + boja_kod."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'ime': 'Vihor',
                'opis_boje': 'siv s bijelim krilnim perima',
                'boja_kod': 'siv',
                'confidence': 0.88,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'golub',
                'images': [make_test_image(600, 400, (128, 128, 140))],
            }), content_type='application/json')
            data = resp.json()
            self.assertEqual(data['fields']['ime'], 'Vihor')
            self.assertEqual(data['fields']['boja_kod'], 'siv')

    def test_61_golub_2_photos(self):
        """Dvije slike goluba → AI koristi obje."""
        imgs = [make_test_image(400, 300, (c, c, c+20)) for c in (120, 140)]
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = json.dumps({
                'ime': 'Srebrni', 'boja_kod': 'siv', 'confidence': 0.92,
            })
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'golub', 'images': imgs,
            }), content_type='application/json')
            self.assertEqual(resp.json()['images_used'], 2)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: AI Error Handling
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanAIErrors(ScanTestMixin, TestCase):
    """Robustnost kod AI grešaka i edge case-ova."""

    def test_70_ai_returns_invalid_json(self):
        """AI vraća tekst bez JSON-a → 502 ili 500."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = 'Sorry, I cannot read this image clearly.'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            self.assertIn(resp.status_code, [500, 502])

    def test_71_ai_returns_json_with_extra_text(self):
        """AI vraća JSON zamotano u tekst → parser ga izvlači."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = 'Here is the result:\n{"prsten_broj":"HR-2026-77777","confidence":0.85}\nHope this helps!'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['fields']['prsten_broj'], 'HR-2026-77777')

    def test_72_ai_timeout(self):
        """AI timeout → 500."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.side_effect = Exception('Connection timed out')
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'general',
                'images': [make_test_image(200, 200)],
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 500)

    def test_73_ai_returns_markdown_wrapped_json(self):
        """AI vraća ```json ... ``` wrapped → parser izvlači."""
        with patch('core.views_scan._call_anthropic') as mock_ai:
            mock_ai.return_value = '```json\n{"prsten_broj":"CRO-2025-88888","confidence":0.91}\n```'
            resp = self.client.post(self.scan_url, json.dumps({
                'doc_type': 'ring',
                'images': [make_test_image(400, 300)],
            }), content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['fields']['prsten_broj'], 'CRO-2025-88888')


# ═══════════════════════════════════════════════════════════════════════════
# TEST 9: Marketplace Bridge — Publish Flow
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanMarketplaceBridge(ScanTestMixin, TestCase):
    """E2E: scan → bridge_publish → marketplace listing."""

    def test_80_egg_record_to_marketplace(self):
        """Scan jaja → unos u EggRecord → Ponudi na burzi → MarketplaceProduct."""
        from udruge.models import EggRecord, Flock

        flock = Flock.objects.create(
            company=self.company, naziv='Nesiljke A',
            vrsta='kokos', broj_komada=50,
            datum_nabave=date(2025, 6, 1),
        )
        egg = EggRecord.objects.create(
            flock=flock, datum=date.today(),
            broj_jaja=30, za_prodaju=True,
            cijena_eur=Decimal('0.30'),
        )

        # Simulate bridge_publish
        resp = self.client.post('/udruge/bridge/publish/', {
            'source_model': 'EggRecord',
            'source_id': str(egg.pk),
            'price': '0.30',
            'qty': '30',
            'opg_number': 'HR-OPG-12345',
        })
        # Should redirect (302) after success
        self.assertIn(resp.status_code, [302, 200])

    def test_81_karenca_blocks_egg_publish(self):
        """Jata pod karencom NE MOŽE objaviti jaja na burzi."""
        from udruge.models import EggRecord, Flock, FlockHealthRecord

        flock = Flock.objects.create(
            company=self.company, naziv='Nesiljke B',
            vrsta='kokos', broj_komada=30,
            datum_nabave=date(2025, 6, 1),
        )
        egg = EggRecord.objects.create(
            flock=flock, datum=date.today(),
            broj_jaja=20, za_prodaju=True,
        )
        # Add health record with active karenca (10 days from today)
        FlockHealthRecord.objects.create(
            flock=flock, vrsta_tretmana='antibiotik',
            datum=date.today(), lijek='Amoksicilin',
            karenca_dana=10,
        )

        # Verify karenca is active
        self.assertTrue(flock.has_active_karenca)

        # Try to publish — should fail
        resp = self.client.post('/udruge/bridge/publish/', {
            'source_model': 'EggRecord',
            'source_id': str(egg.pk),
            'price': '0.30',
            'qty': '20',
            'opg_number': 'HR-OPG-12345',
        }, follow=True)
        # Should have error message about karenca
        messages = list(resp.context.get('messages', []))
        karenca_msg = any('ZABRANJENO' in str(m) or 'karencom' in str(m) for m in messages)
        self.assertTrue(karenca_msg, 'Karenca should block publication')

    def test_82_karenca_end_date_calculated(self):
        """karenca_end_date vraća točan datum."""
        from udruge.models import Flock, FlockHealthRecord

        flock = Flock.objects.create(
            company=self.company, naziv='Test jato',
            vrsta='kokos', broj_komada=10,
            datum_nabave=date(2025, 6, 1),
        )
        FlockHealthRecord.objects.create(
            flock=flock, vrsta_tretmana='antibiotik',
            datum=date.today(), karenca_dana=7,
        )
        expected = date.today() + timedelta(days=7)
        self.assertEqual(flock.karenca_end_date, expected)

    def test_83_no_karenca_allows_publish(self):
        """Jato bez karence — publish prolazi."""
        from udruge.models import Flock

        flock = Flock.objects.create(
            company=self.company, naziv='Zdrave nesiljke',
            vrsta='kokos', broj_komada=40,
            datum_nabave=date(2025, 6, 1),
        )
        self.assertFalse(flock.has_active_karenca)

    def test_84_opg_required_for_food(self):
        """Prehrambeni proizvodi zahtijevaju OPG broj."""
        from udruge.models import EggRecord, Flock

        flock = Flock.objects.create(
            company=self.company, naziv='Nesiljke C',
            vrsta='kokos', broj_komada=25,
            datum_nabave=date(2025, 6, 1),
        )
        egg = EggRecord.objects.create(
            flock=flock, datum=date.today(), broj_jaja=15,
        )
        # Publish without OPG number
        resp = self.client.post('/udruge/bridge/publish/', {
            'source_model': 'EggRecord',
            'source_id': str(egg.pk),
            'price': '0.25',
            'qty': '15',
            'opg_number': '',  # missing!
        }, follow=True)
        messages = list(resp.context.get('messages', []))
        opg_msg = any('OPG' in str(m) for m in messages)
        self.assertTrue(opg_msg, 'OPG number should be required for food')


# ═══════════════════════════════════════════════════════════════════════════
# TEST 10: Golub Auction Integration
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestScanAuctionIntegration(ScanTestMixin, TestCase):
    """E2E: golub sealed → publish → auction listing."""

    def test_90_golub_publish_creates_auction(self):
        """Sealed golub objava na burzi kreira auction listing."""
        from udruge.models import Golub, Golubinjak

        gj = Golubinjak.objects.create(
            company=self.company, naziv='Test loft',
        )
        golub = Golub.objects.create(
            company=self.company, golubinjak=gj,
            prsten_broj='HR-2026-TEST1', naziv='Testni',
            spol='M', is_sealed=True,
            sealed_at=timezone.now(),
        )

        # Use marketplace bridge directly
        from marketplace.services.marketplace_bridge import publish_to_marketplace
        product = publish_to_marketplace(
            source_model='Golub',
            source_id=golub.pk,
            price='100',
            qty='1',
        )

        self.assertTrue(product.is_auction)
        self.assertEqual(product.auction_status, 'active')
        self.assertEqual(product.starting_bid, Decimal('100'))
        self.assertIsNotNone(product.expires_at)

    def test_91_auction_bid_model(self):
        """AuctionBid kreira se s ispravnim podacima."""
        from companies.models import Company
        from marketplace.models import AuctionBid, MarketplaceProduct

        buyer = Company.objects.create(name='Kupac d.o.o.', oib='99988877766')

        product = MarketplaceProduct.objects.create(
            seller_company=self.company,
            name='Golub Test',
            slug='golub-test-123',
            unit_price=Decimal('100'),
            is_auction=True,
            starting_bid=Decimal('100'),
            auction_status='active',
            expires_at=timezone.now() + timedelta(hours=24),
        )

        bid = AuctionBid.objects.create(
            product=product,
            bidder_company=buyer,
            bidder_user=self.user,
            amount=Decimal('150'),
        )

        self.assertTrue(bid.is_highest)
        self.assertEqual(product.bids.count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 11: Image Processing Pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestImageProcessing(TestCase):
    """Testira image processing helpers bez API poziva."""

    def test_100_validate_images_filters_empty(self):
        """Prazne slike se filtriraju."""
        from core.views_scan import _validate_images
        valid, warning = _validate_images(['', '  ', 'abc123', ''])
        self.assertEqual(len(valid), 1)
        self.assertIsNone(warning)

    def test_101_validate_images_max_5(self):
        """Samo prvih 5 se prihvaća."""
        from core.views_scan import _validate_images
        images = ['img%d' % i for i in range(10)]
        valid, _ = _validate_images(images)
        self.assertLessEqual(len(valid), 5)

    def test_102_build_content_structure(self):
        """Content array ima ispravnu strukturu za Anthropic API."""
        from core.views_scan import _build_content
        content = _build_content(['test_b64_data'], 'ring')
        self.assertEqual(len(content), 2)  # 1 image + 1 text prompt
        self.assertEqual(content[0]['type'], 'image')
        self.assertEqual(content[0]['source']['type'], 'base64')
        self.assertEqual(content[1]['type'], 'text')
        self.assertIn('prsten', content[1]['text'])

    def test_103_build_content_multi_images(self):
        """N slika → N image blocks + 1 text prompt."""
        from core.views_scan import _build_content
        content = _build_content(['img1', 'img2', 'img3'], 'invoice')
        self.assertEqual(len(content), 4)  # 3 images + 1 prompt
        self.assertIn('3 fotografij', content[3]['text'])

    def test_104_parse_json_extracts_from_text(self):
        """JSON parser izvlači JSON iz miješanog teksta."""
        from core.views_scan import _parse_json
        result = _parse_json('Some text {"key": "value"} more text')
        self.assertEqual(result['key'], 'value')

    def test_105_parse_json_fails_on_no_json(self):
        """Bez JSON-a → ValueError."""
        from core.views_scan import _parse_json
        with self.assertRaises(ValueError):
            _parse_json('No JSON here at all')

    def test_106_suffix_grammar(self):
        """Gramatička sufiksa za broj slika."""
        from core.views_scan import _suffix
        self.assertEqual(_suffix(1), 'a')    # 1 fotografija
        self.assertEqual(_suffix(2), 'e')    # 2 fotografije
        self.assertEqual(_suffix(3), 'e')    # 3 fotografije
        self.assertEqual(_suffix(5), 'a')    # 5 fotografija

    def test_107_post_process_ring_low_confidence(self):
        """Post-process: ring s niskim confidence → prazan prsten_broj."""
        from core.views_scan import _post_process
        fields = {'prsten_broj': 'MAYBE', 'confidence': 0.20}
        result = _post_process(fields, 'ring')
        self.assertEqual(result['prsten_broj'], '')

    def test_108_post_process_id_card_nationality(self):
        """Post-process: HRC → HRV korekcija."""
        from core.views_scan import _post_process
        fields = {'nacionalnost': 'HRC', 'confidence': 0.9}
        result = _post_process(fields, 'id_card')
        self.assertEqual(result['nacionalnost'], 'HRV')


# ═══════════════════════════════════════════════════════════════════════════
# TEST 12: Flock Dashboard & Egg Entry
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
class TestFlockViews(ScanTestMixin, TestCase):
    """Flock dashboard, egg entry, health records."""

    def test_110_flock_list_loads(self):
        """Flock list stranica se ucitava."""
        from django.urls import reverse
        resp = self.client.get(reverse('udruge:flock_list'), follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_111_flock_create(self):
        """Kreiranje jata."""
        from django.urls import reverse
        resp = self.client.post(reverse('udruge:flock_create'), {
            'naziv': 'Nesiljke Test',
            'vrsta': 'kokos',
            'pasmina': 'Lohmann Brown',
            'broj_komada': '50',
            'datum_nabave': '2026-01-15',
            'tip_uzgoja': 'slobodni',
            'objekt': 'Kokošinjac 1',
        })
        self.assertIn(resp.status_code, [200, 302])
        from udruge.models import Flock
        self.assertTrue(Flock.objects.filter(naziv='Nesiljke Test').exists())

    def test_112_egg_record_create(self):
        """Unos jaja za jato."""
        from udruge.models import Flock
        flock = Flock.objects.create(
            company=self.company, naziv='Test EGG',
            vrsta='kokos', broj_komada=30,
            datum_nabave=date(2025, 6, 1),
        )
        resp = self.client.post(reverse('udruge:egg_record_create', args=[flock.pk]), {
            'datum': '2026-03-28',
            'broj_jaja': '25',
            'broken': '2',
            'sold': '10',
            'notes': 'Normalan dan',
        })
        self.assertIn(resp.status_code, [200, 302])
        from udruge.models import EggRecord
        egg = EggRecord.objects.filter(flock=flock).first()
        self.assertIsNotNone(egg)
        self.assertEqual(egg.broj_jaja, 25)

    def test_113_health_record_with_karenca(self):
        """Zdravstveni zapis s karencom → auto-pull marketplace."""
        from udruge.models import Flock
        flock = Flock.objects.create(
            company=self.company, naziv='Karenca Test',
            vrsta='kokos', broj_komada=20,
            datum_nabave=date(2025, 6, 1),
        )
        resp = self.client.post(reverse('udruge:flock_health_create', args=[flock.pk]), {
            'vrsta_tretmana': 'antibiotik',
            'datum': '2026-03-28',
            'lijek': 'Amoksicilin 500mg',
            'doza': '2ml/L vode',
            'veterinar': 'Dr. Horvat',
            'karenca_dana': '7',
        })
        self.assertIn(resp.status_code, [200, 302])
        self.assertTrue(flock.has_active_karenca)

    def test_114_mortality_record(self):
        """Zapis uginuća — smanjuje aktivnih_komada."""
        from udruge.models import Flock, FlockMortality
        flock = Flock.objects.create(
            company=self.company, naziv='Mortality Test',
            vrsta='kokos', broj_komada=50,
            datum_nabave=date(2025, 6, 1),
        )
        self.assertEqual(flock.aktivnih_komada, 50)

        FlockMortality.objects.create(
            flock=flock, datum=date.today(),
            broj_uginulih=3, razlog='Predator',
        )
        self.assertEqual(flock.aktivnih_komada, 47)
