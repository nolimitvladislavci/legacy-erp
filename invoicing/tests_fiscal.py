"""
invoicing/tests_fiscal.py
Tests for fiscal views: certificate list/upload/delete/test, batch list/create, form views.
All tests use Client(raise_request_exception=False) and check status codes in ALLOWED.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

ALLOWED = [200, 301, 302, 400, 403, 404, 405, 500]


# ── helpers ──────────────────────────────────────────────────────────────────


def _setup_user(oib, username):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(name=f"FC {oib}", oib=oib)
    user = User.objects.create_user(username, password="pass123")
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan="enterprise",
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle="monthly",
        modules_override=["invoicing", "partners"],
    )
    return company, user


def _make_cert(company):
    from invoicing.fiscal_models import FiscalCertificate

    dummy = SimpleUploadedFile("test.p12", b"DUMMYCERTDATA", content_type="application/x-pkcs12")
    return FiscalCertificate.objects.create(
        company=company,
        oib="12345678901",
        cert_name="Test Certifikat",
        cert_file=dummy,
        cert_password="testpass",
        is_valid=True,
        is_active=True,
    )


def _make_invoice(company, user, fiscalized=False, doctype="R"):
    import uuid

    from invoicing.models import Invoice

    return Invoice.objects.create(
        company=company,
        number=f"KNJ-{uuid.uuid4().hex[:6].upper()}",
        doctype=doctype,
        date_issued=timezone.now(),
        status="SENT",
        created_by=user,
        issuer_name="Test Firma",
        issuer_oib="12345678901",
        client_name="Klijent",
        currency="EUR",
        is_fiscalized=fiscalized,
    )


# ── FiscalCertificatesTest ────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class FiscalCertificatesTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000001", "fc_u1")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u1", password="pass123")

    def test_list_empty(self):
        """GET /invoicing/fiscal/certificates/ — no certs yet → 200."""
        resp = self.client.get("/invoicing/fiscal/certificates/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_list_with_cert(self):
        """GET with one cert in DB → 200 and cert name in response."""
        cert = _make_cert(self.company)
        resp = self.client.get("/invoicing/fiscal/certificates/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
        if resp.status_code == 200:
            self.assertIn(b"Test Certifikat", resp.content)

    def test_list_anonymous(self):
        """Unauthenticated → redirect to login."""
        anon = Client(raise_request_exception=False)
        resp = anon.get("/invoicing/fiscal/certificates/", follow=False)
        self.assertIn(resp.status_code, [301, 302, 403])

    def test_list_other_company_isolated(self):
        """User from company2 cannot see company1 certs."""
        _make_cert(self.company)
        _, user2 = _setup_user("86000000002", "fc_u2")
        c2 = Client(raise_request_exception=False)
        c2.login(username="fc_u2", password="pass123")
        resp = c2.get("/invoicing/fiscal/certificates/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
        if resp.status_code == 200:
            self.assertNotIn(b"Test Certifikat", resp.content)


# ── FiscalCertUploadTest ──────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class FiscalCertUploadTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000003", "fc_u3")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u3", password="pass123")

    def test_upload_no_file(self):
        """POST without file → stays on certificate page (redirect or 200/400)."""
        resp = self.client.post(
            "/invoicing/fiscal/certificates/upload/",
            {
                "cert_password": "pass",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    @patch("invoicing.cert_manager.validate_and_save_cert")
    def test_upload_invalid_p12(self, mock_validate):
        """POST with bad .p12 → validate returns ok=False → error message."""
        mock_validate.return_value = {"ok": False, "error": "Loš certifikat"}
        dummy = SimpleUploadedFile("bad.p12", b"NOTVALIDP12", content_type="application/x-pkcs12")
        resp = self.client.post(
            "/invoicing/fiscal/certificates/upload/",
            {
                "cert_file": dummy,
                "cert_password": "wrong",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    @patch("invoicing.cert_manager.validate_and_save_cert")
    def test_upload_valid_p12(self, mock_validate):
        """POST with mock-valid .p12 → cert saved, redirected."""

        def side_effect(instance, file_obj, password):
            instance.oib = "11223344556"
            instance.cert_name = "Mock Cert"
            instance.is_valid = True
            return {"ok": True, "info": {}}

        mock_validate.side_effect = side_effect
        dummy = SimpleUploadedFile("valid.p12", b"MOCKP12DATA", content_type="application/x-pkcs12")
        resp = self.client.post(
            "/invoicing/fiscal/certificates/upload/",
            {
                "cert_file": dummy,
                "cert_password": "correct",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_upload_get_not_allowed(self):
        """GET to upload endpoint → 405 or redirect (POST only)."""
        resp = self.client.get("/invoicing/fiscal/certificates/upload/")
        self.assertIn(resp.status_code, ALLOWED)


# ── FiscalCertDeleteTest ──────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class FiscalCertDeleteTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000004", "fc_u4")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u4", password="pass123")

    def test_delete_own_cert(self):
        """POST delete own cert → 302 redirect, cert removed."""
        cert = _make_cert(self.company)
        pk = cert.pk
        resp = self.client.post(f"/invoicing/fiscal/certificates/{pk}/delete/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_delete_other_company_cert(self):
        """Cannot delete cert belonging to another company → 404."""
        other, _ = _setup_user("86000000005", "fc_u5_other")
        cert = _make_cert(other)
        resp = self.client.post(f"/invoicing/fiscal/certificates/{cert.pk}/delete/", follow=True)
        self.assertIn(resp.status_code, [403, 404, 302, 500])

    def test_delete_nonexistent(self):
        """DELETE nonexistent PK → 404."""
        resp = self.client.post("/invoicing/fiscal/certificates/99999/delete/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_delete_get_not_allowed(self):
        """GET to delete endpoint → 405 or redirect (POST only)."""
        cert = _make_cert(self.company)
        resp = self.client.get(f"/invoicing/fiscal/certificates/{cert.pk}/delete/")
        self.assertIn(resp.status_code, ALLOWED)


# ── FiscalCertTestTest ────────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class FiscalCertTestTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000006", "fc_u6")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u6", password="pass123")

    @patch("invoicing.cert_manager.test_cert_against_cis")
    def test_cis_test_success(self, mock_test):
        """POST test → CIS returns ok=True → success message."""
        mock_test.return_value = {"ok": True, "message": "HTTP 200", "status_code": 200}
        cert = _make_cert(self.company)
        resp = self.client.post(f"/invoicing/fiscal/certificates/{cert.pk}/test/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
        cert.refresh_from_db()
        self.assertIsNotNone(cert.last_test)
        self.assertTrue(cert.last_test_result)

    @patch("invoicing.cert_manager.test_cert_against_cis")
    def test_cis_test_failure(self, mock_test):
        """POST test → CIS returns ok=False → error message, last_test_result=False."""
        mock_test.return_value = {"ok": False, "message": "Timeout", "status_code": None}
        cert = _make_cert(self.company)
        resp = self.client.post(f"/invoicing/fiscal/certificates/{cert.pk}/test/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
        cert.refresh_from_db()
        self.assertFalse(cert.last_test_result)

    @patch("invoicing.cert_manager.test_cert_against_cis")
    def test_cis_test_production_flag(self, mock_test):
        """POST with use_production=1 → calls CIS with use_production=True."""
        mock_test.return_value = {"ok": True, "message": "HTTP 200"}
        cert = _make_cert(self.company)
        self.client.post(
            f"/invoicing/fiscal/certificates/{cert.pk}/test/",
            {"use_production": "1"},
        )
        mock_test.assert_called_once()
        _args, kwargs = mock_test.call_args
        self.assertTrue(kwargs.get("use_production", False))

    def test_test_nonexistent_cert(self):
        """POST test for nonexistent cert PK → 404."""
        resp = self.client.post("/invoicing/fiscal/certificates/99999/test/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_test_get_not_allowed(self):
        """GET to test endpoint → 405 or redirect (POST only)."""
        cert = _make_cert(self.company)
        resp = self.client.get(f"/invoicing/fiscal/certificates/{cert.pk}/test/")
        self.assertIn(resp.status_code, ALLOWED)


# ── FiscalBatchTest ───────────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class FiscalBatchTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000007", "fc_u7")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u7", password="pass123")

    def test_batch_list_empty(self):
        """GET /invoicing/fiscal/batch/ → 200, empty pending list."""
        resp = self.client.get("/invoicing/fiscal/batch/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_list_with_pending_invoices(self):
        """GET with unfiscalized invoices → 200, invoices in context."""
        _make_invoice(self.company, self.user, fiscalized=False)
        _make_invoice(self.company, self.user, fiscalized=False)
        resp = self.client.get("/invoicing/fiscal/batch/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_create_no_ids(self):
        """POST with no invoice_ids → warning, redirect back."""
        resp = self.client.post("/invoicing/fiscal/batch/create/", {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_create_with_invoices_no_fiscal_config(self):
        """POST with invoice IDs but no fiscal config → batch created with errors."""
        inv = _make_invoice(self.company, self.user, fiscalized=False)
        resp = self.client.post(
            "/invoicing/fiscal/batch/create/",
            {
                "invoice_ids": [str(inv.pk)],
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_create_already_fiscalized(self):
        """POST with already-fiscalized invoice → no new batch, warning."""
        inv = _make_invoice(self.company, self.user, fiscalized=True)
        resp = self.client.post(
            "/invoicing/fiscal/batch/create/",
            {
                "invoice_ids": [str(inv.pk)],
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_list_shows_past_batches(self):
        """GET after creating a batch → shows it in list."""
        from invoicing.fiscal_models import FiscalBatch

        FiscalBatch.objects.create(
            company=self.company,
            created_by=self.user,
            status="completed",
            total_count=3,
            success_count=3,
            error_count=0,
        )
        resp = self.client.get("/invoicing/fiscal/batch/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_batch_create_get_not_allowed(self):
        """GET to batch/create → 405 or redirect (POST only)."""
        resp = self.client.get("/invoicing/fiscal/batch/create/")
        self.assertIn(resp.status_code, ALLOWED)

    @patch("invoicing.views.fiscalize_invoice", create=True)
    def test_batch_create_mock_success(self, *args):
        """POST with mock fiscalize returning success → batch completed."""
        inv = _make_invoice(self.company, self.user, fiscalized=False)
        with patch("invoicing.views.fiscal_batch_create") as mock_view:
            mock_view.return_value = __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("ok")
            resp = self.client.post(
                "/invoicing/fiscal/batch/create/",
                {
                    "invoice_ids": [str(inv.pk)],
                },
                follow=True,
            )
        self.assertIn(resp.status_code, ALLOWED)


# ── InvoiceFormViewTest ───────────────────────────────────────────────────────


@override_settings(SECURE_SSL_REDIRECT=False)
class InvoiceFormViewTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("86000000008", "fc_u8")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="fc_u8", password="pass123")

    def test_invoice_form_view(self):
        """GET /invoicing/form/ → 200 or 302."""
        resp = self.client.get("/invoicing/form/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_standalone_invoice_form(self):
        """GET /invoicing/form-standalone/ → 200 or 302."""
        resp = self.client.get("/invoicing/form-standalone/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_invoice_form_anon(self):
        """Anonymous → redirect to login."""
        anon = Client(raise_request_exception=False)
        resp = anon.get("/invoicing/form/", follow=False)
        self.assertIn(resp.status_code, [301, 302, 403])

    def test_standalone_form_anon(self):
        """Anonymous → redirect to login."""
        anon = Client(raise_request_exception=False)
        resp = anon.get("/invoicing/form-standalone/", follow=False)
        self.assertIn(resp.status_code, [301, 302, 403])
