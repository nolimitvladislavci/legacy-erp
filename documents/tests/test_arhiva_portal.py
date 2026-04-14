"""Tests for ARHIVA-2 Magic Link portal."""

import uuid

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from companies.models import Company
from documents.models import ArhivaAccessToken, ArhivaEntry


@override_settings(SECURE_SSL_REDIRECT=False)
class ArhivaPortalTests(TestCase):
    """ARHIVA-2: Magic Link read-only portal tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("marija", "m@test.com", "test1234")
        cls.company = Company.objects.create(
            name="Gasic Ivan Test",
            oib="12345678903",
        )
        cls.access_token = ArhivaAccessToken.objects.create(
            company=cls.company,
            created_by=cls.user,
            label="Pristup arhivi",
        )
        # Create some test entries
        from datetime import date

        for i in range(3):
            ArhivaEntry.objects.create(
                company=cls.company,
                source_type="receipt_scan",
                source_id=f"test-{i}",
                doc_number=f"TEST-{i:03d}",
                amount=10 + i,
                doc_date=date(2026, 4, 14),
                file_path=f"/tmp/test-{i}.pdf",
            )

    def _portal_url(self, token):
        return f"/hr/arhiva-portal/{token}/"

    def test_portal_valid_access(self):
        """Happy path: valid token shows company archive."""
        resp = self.client.get(self._portal_url(self.access_token.token))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Gasic Ivan Test")
        self.assertContains(resp, "Digitalna Arhiva")
        self.assertContains(resp, "3")  # total_count

    def test_portal_shows_entries(self):
        """Portal shows archived entries."""
        resp = self.client.get(self._portal_url(self.access_token.token))
        self.assertContains(resp, "TEST-000")
        self.assertContains(resp, "TEST-001")

    def test_portal_invalid_token(self):
        """Invalid token shows expired page."""
        resp = self.client.get(self._portal_url(uuid.uuid4()))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "nije valjan")

    def test_portal_expired_token(self):
        """Expired token shows expired page."""
        expired = ArhivaAccessToken.objects.create(
            company=self.company,
            created_by=self.user,
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        resp = self.client.get(self._portal_url(expired.token))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "nije valjan")

    def test_portal_deactivated_token(self):
        """Deactivated token shows expired page."""
        inactive = ArhivaAccessToken.objects.create(
            company=self.company,
            created_by=self.user,
            is_active=False,
        )
        resp = self.client.get(self._portal_url(inactive.token))
        self.assertContains(resp, "nije valjan")

    def test_portal_public_route(self):
        """Portal works without login."""
        resp = self.client.get(self._portal_url(self.access_token.token))
        self.assertEqual(resp.status_code, 200)

    def test_portal_access_count(self):
        """Access count increments."""
        initial = ArhivaAccessToken.objects.get(pk=self.access_token.pk).access_count
        self.client.get(self._portal_url(self.access_token.token))
        updated = ArhivaAccessToken.objects.get(pk=self.access_token.pk)
        self.assertEqual(updated.access_count, initial + 1)
        self.assertIsNotNone(updated.last_accessed_at)

    def test_portal_zor_info(self):
        """Portal shows ZOR 11-year info."""
        resp = self.client.get(self._portal_url(self.access_token.token))
        self.assertContains(resp, "11 godina")
