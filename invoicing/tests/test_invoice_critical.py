"""
invoicing/tests/test_invoice_critical.py
Critical path: kreiranje fakture i klijentski portal (kupčeva soba).

Napomena: SECURE_SSL_REDIRECT=True → koristimo secure=True na svim requestima.
client_portal je PUBLIC ruta u RouteRegistry → 200 bez logina.
"""

import uuid

from django.test import Client, TestCase
from django.utils import timezone

from invoicing.models import Invoice


class InvoiceCriticalTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _make_invoice(self, **kwargs):
        defaults = {
            "number": f"TEST-{uuid.uuid4().hex[:8].upper()}",
            "client_name": "Test Klijent d.o.o.",
            "date_issued": timezone.now(),
            "status": "DRAFT",
            "total": "100.00",
            "subtotal": "80.00",
            "tax_amount": "20.00",
        }
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)

    # ── Model tests ─────────────────────────────────────────────

    def test_invoice_default_status_is_draft(self):
        """Kreiranje Invoice → status DRAFT"""
        inv = self._make_invoice()
        self.assertEqual(inv.status, "DRAFT")

    def test_invoice_status_change_to_sent(self):
        """Invoice DRAFT → SENT (update_fields bypass lock guard)"""
        inv = self._make_invoice()
        inv.status = "SENT"
        inv.save(update_fields=["status"])
        inv.refresh_from_db()
        self.assertEqual(inv.status, "SENT")

    def test_invoice_has_uuid_client_token(self):
        """Invoice ima client_token UUID za kupčevu sobu"""
        inv = self._make_invoice()
        self.assertIsNotNone(inv.client_token)
        self.assertIsInstance(inv.client_token, uuid.UUID)

    def test_invoice_number_is_unique(self):
        """Dva Invoice-a ne mogu imati isti broj"""
        num = f"UNIQUE-{uuid.uuid4().hex[:6].upper()}"
        self._make_invoice(number=num)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            self._make_invoice(number=num)

    # ── Client portal (PUBLIC ruta) ─────────────────────────────

    def test_client_portal_get_is_public(self):
        """GET /hr/ponuda/<token>/ bez logina → 200 (PUBLIC u RouteRegistry)"""
        inv = self._make_invoice()
        resp = self.client.get(f"/hr/ponuda/{inv.client_token}/", secure=True)
        self.assertEqual(resp.status_code, 200)

    def test_client_portal_post_accept(self):
        """POST action=accept na SENT ponudu → status ACCEPTED"""
        inv = self._make_invoice(status="SENT")
        self.client.post(
            f"/hr/ponuda/{inv.client_token}/",
            {"action": "accept"},
            secure=True,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.status, "ACCEPTED")

    def test_client_portal_post_reject(self):
        """POST action=reject na SENT ponudu → status REJECTED"""
        inv = self._make_invoice(status="SENT")
        self.client.post(
            f"/hr/ponuda/{inv.client_token}/",
            {"action": "reject"},
            secure=True,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.status, "REJECTED")

    def test_client_portal_404_for_invalid_token(self):
        """GET /hr/ponuda/<random-uuid>/ → 404"""
        resp = self.client.get(f"/hr/ponuda/{uuid.uuid4()}/", secure=True)
        self.assertEqual(resp.status_code, 404)

    def test_client_portal_accept_on_draft(self):
        """POST accept na DRAFT → ACCEPTED"""
        inv = self._make_invoice(status="DRAFT")
        self.client.post(
            f"/hr/ponuda/{inv.client_token}/",
            {"action": "accept"},
            secure=True,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.status, "ACCEPTED")
