"""Tests for ARHIVA-1 ScanToken mobile scan portal."""

import io
import uuid

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from companies.models import Company
from documents.models import ArhivaEntry, ScanToken


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MEDIA_ROOT="/tmp/test_scan_media",
    DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
)
class ScanTokenTests(TestCase):
    """ARHIVA-1: ScanToken mobile scan portal tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("marija", "m@test.com", "test1234")
        cls.company = Company.objects.create(
            name="Konjik Test d.o.o.",
            oib="12345678903",
        )
        cls.scan_token = ScanToken.objects.create(
            company=cls.company,
            created_by=cls.user,
            label="Gasic Ivan - gorivo",
        )

    def _scan_url(self, token):
        """Toplevel /scan/{token}/ path — van i18n."""
        return f"/hr/scan/{token}/"

    def _upload_url(self, token):
        """Toplevel /scan/{token}/upload/ path — van i18n."""
        return f"/hr/scan/{token}/upload/"

    def _make_image(self, name="racun.png"):
        """Kreiraj minimalni PNG za upload."""
        img = io.BytesIO(
            b"\x89PNG\r\n\x1a\n"  # PNG header
            + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            + b"\x08\x02\x00\x00\x00\x90wS\xde"
            + b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
            + b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img.name = name
        return img

    def test_scan_token_valid_upload(self):
        """Happy path: slika -> ArhivaEntry kreiran."""
        url = self._upload_url(self.scan_token.token)
        img = self._make_image()
        resp = self.client.post(url, {"file": img}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("entry_id", data)
        self.assertIn("archive_number", data)

        entry = ArhivaEntry.objects.get(pk=data["entry_id"])
        self.assertEqual(entry.company_id, self.company.id)
        self.assertEqual(entry.source_type, "receipt_scan")
        self.assertEqual(entry.content_category, "scan")
        self.assertIn("scan_token_", entry.session_key)

    def test_scan_token_expired(self):
        """Token istekao -> 410 error."""
        expired_token = ScanToken.objects.create(
            company=self.company,
            created_by=self.user,
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        resp = self.client.post(
            self._upload_url(expired_token.token),
            {"file": self._make_image()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 410)

    def test_scan_token_invalid(self):
        """Krivi UUID -> 410."""
        fake_uuid = uuid.uuid4()
        resp = self.client.post(
            self._upload_url(fake_uuid),
            {"file": self._make_image()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 410)

    def test_scan_token_public_route(self):
        """Mobile page mora raditi bez logina."""
        url = self._scan_url(self.scan_token.token)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Konjik Test d.o.o.")
        self.assertContains(resp, str(self.scan_token.token))

    def test_scan_token_use_count(self):
        """use_count se povecava nakon uploada."""
        initial_count = ScanToken.objects.get(pk=self.scan_token.pk).use_count
        resp = self.client.post(
            self._upload_url(self.scan_token.token),
            {"file": self._make_image("racun2.png")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        updated = ScanToken.objects.get(pk=self.scan_token.pk)
        self.assertEqual(updated.use_count, initial_count + 1)

    def test_scan_token_max_uses(self):
        """Token s max_uses=1 prestaje raditi nakon jednog koristenja."""
        limited_token = ScanToken.objects.create(
            company=self.company,
            created_by=self.user,
            max_uses=1,
            use_count=1,
        )
        resp = self.client.post(
            self._upload_url(limited_token.token),
            {"file": self._make_image()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 410)

    def test_scan_token_deactivated(self):
        """Deaktivirani token -> 410."""
        inactive_token = ScanToken.objects.create(
            company=self.company,
            created_by=self.user,
            is_active=False,
        )
        resp = self.client.post(
            self._upload_url(inactive_token.token),
            {"file": self._make_image()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 410)

    def test_scan_create_token_requires_login(self):
        """Token kreiranje zahtijeva login."""
        resp = self.client.post("/hr/documents/scan/create-token/")
        self.assertIn(resp.status_code, [301, 302])  # redirect to login

    def test_expired_token_shows_expired_page(self):
        """Istekli token na GET prikazuje expired stranicu."""
        expired_token = ScanToken.objects.create(
            company=self.company,
            created_by=self.user,
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        url = self._scan_url(expired_token.token)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Slikaj racun")
