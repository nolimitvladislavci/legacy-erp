"""
Smoke test suite — Korak 10: Onboarding Provjera
Cijeli flow: register → login → company setup → partner → invoice → PDF → arhiva

Run: pytest core/tests/test_onboarding_smoke.py -v
"""

import uuid

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.test.utils import setup_test_environment

NO_HTTPS = override_settings(SECURE_SSL_REDIRECT=False)


def _make_email():
    return f"onboard_{uuid.uuid4().hex[:8]}@smoke.test"


def _setup_company_user(draft=False):
    """Create test user + company for onboarding tests."""
    from accounts.models import UserProfile
    from companies.models import Company

    oib = f"DRAFT{uuid.uuid4().hex[:5].upper()}"[:11] if draft else "99988877762"
    company = Company.objects.create(
        name="Onboarding Smoke d.o.o.",
        oib=oib,
        country="HR",
        is_draft=draft,
    )
    email = _make_email()
    user = User.objects.create_user(
        username=f"onb_{uuid.uuid4().hex[:8]}",
        email=email,
        password="SmokePass2026!",
    )
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"company": company, "role": "company_admin"},
    )
    return company, user


@NO_HTTPS
class RegistrationFlowSmokeTest(TestCase):
    """10.1 — Registration flow: step1 → quick register → redirect to wizard."""

    def setUp(self):
        from registration.models import PricingPlan

        PricingPlan.objects.get_or_create(
            slug="starter",
            defaults={"name": "Starter", "price_monthly": 0, "is_active": True, "sort_order": 1},
        )
        self.client = Client(enforce_csrf_checks=False)

    def test_register_step1_get(self):
        r = self.client.get("/hr/register/")
        self.assertEqual(r.status_code, 200)

    def test_register_step1_post_plan(self):
        r = self.client.post("/hr/register/", {"plan": "starter"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/register/", r["Location"])

    def test_register_quick_full_flow(self):
        """register → quick form → user created → redirect to setup wizard."""
        email = _make_email()
        self.client.post("/hr/register/", {"plan": "starter"})
        r = self.client.post(
            "/hr/register/company/",
            {
                "first_name": "Test",
                "email": email,
                "password1": "SmokePass2026!",
                "password2": "SmokePass2026!",
            },
            follow=False,
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("setup", r["Location"])
        user = User.objects.filter(email=email).first()
        self.assertIsNotNone(user, "User must be created after quick register")
        self.assertTrue(user.profile.company.is_draft, "Company starts as draft")

    def test_duplicate_oib_returns_error(self):
        """Duplicate OIB in registration must show error, not 500."""
        from companies.models import Company

        Company.objects.get_or_create(oib="11111111119", defaults={"name": "Existing", "country": "HR"})
        self.client.post("/hr/register/", {"plan": "starter"})
        r = self.client.post(
            "/hr/register/company-full/",
            {
                "name": "Test",
                "oib": "11111111119",
                "country": "HR",
                "address": "Test",
                "city": "Zagreb",
                "zip_code": "10000",
                "industry": "it",
                "first_name": "Ivan",
                "email": _make_email(),
                "password1": "SmokePass2026!",
                "password2": "SmokePass2026!",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("errors", r.context or {})
        self.assertIn("oib", r.context.get("errors", {}))

    def test_duplicate_email_returns_error(self):
        """Duplicate email in registration must show error, not 500."""
        existing = User.objects.create_user(
            username=f"dup_{uuid.uuid4().hex[:6]}", email="dup@smoke.test", password="Test123!"
        )
        self.client.post("/hr/register/", {"plan": "starter"})
        r = self.client.post(
            "/hr/register/company-full/",
            {
                "name": "Test",
                "oib": "66666666664",
                "country": "HR",
                "address": "Test",
                "city": "Zagreb",
                "zip_code": "10000",
                "industry": "it",
                "first_name": "Ivan",
                "email": "dup@smoke.test",
                "password1": "SmokePass2026!",
                "password2": "SmokePass2026!",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("email", r.context.get("errors", {}))


@NO_HTTPS
class CompanySetupSmokeTest(TestCase):
    """10.2 — Company setup wizard: OIB, IBAN, contact."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_user(draft=True)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=False)
        self.client.login(username=self.user.username, password="SmokePass2026!")

    def test_setup_wizard_get(self):
        r = self.client.get("/hr/companies/setup/")
        self.assertEqual(r.status_code, 200)

    def test_setup_wizard_company_valid_oib(self):
        r = self.client.post(
            "/hr/companies/setup/company/",
            {
                "name": "Onboarding Firma d.o.o.",
                "oib": "55555555551",
                "address": "Ilica 1",
                "city": "Zagreb",
                "zip_code": "10000",
                "country": "HR",
                "industry": "it",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.oib, "55555555551")
        self.assertFalse(self.company.is_draft)

    def test_setup_wizard_company_invalid_oib_shows_error(self):
        r = self.client.post(
            "/hr/companies/setup/company/",
            {
                "name": "Test",
                "oib": "123",
                "address": "Test",
                "city": "Zagreb",
                "zip_code": "10000",
                "country": "HR",
                "industry": "it",
            },
        )
        self.assertEqual(r.status_code, 200)

    def test_setup_wizard_contact(self):
        r = self.client.post(
            "/hr/companies/setup/contact/",
            {"phone": "+38591234567", "email": "firma@smoke.test"},
        )
        self.assertEqual(r.status_code, 302)

    def test_setup_wizard_fiscal_iban(self):
        r = self.client.post(
            "/hr/companies/setup/fiscal/",
            {"oib": "55555555551", "iban": "HR1210010051863000160"},
        )
        self.assertEqual(r.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.iban, "HR1210010051863000160")


@NO_HTTPS
class InvoiceFlowSmokeTest(TestCase):
    """10.3 — Prva faktura: kreiranje, PDF, client portal."""

    @classmethod
    def setUpTestData(cls):
        from partners.models import Partner

        cls.company, cls.user = _setup_company_user(draft=False)
        cls.partner = Partner.objects.create(
            company=cls.company, name="Kupac d.o.o.", oib="22222222226", partner_type="client"
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=False)
        self.client.login(username=self.user.username, password="SmokePass2026!")

    def test_invoice_list(self):
        r = self.client.get("/hr/invoicing/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_invoice_create_page(self):
        r = self.client.get("/hr/invoicing/new/")
        self.assertEqual(r.status_code, 200)

    def test_invoice_pdf(self):
        from datetime import date

        from invoicing.models import Invoice

        inv = Invoice.objects.create(
            company=self.company,
            partner=self.partner,
            number=f"KNJ-2026-{uuid.uuid4().hex[:4].upper()}",
            date_issued=date(2026, 4, 14),
            date_due=date(2026, 4, 28),
            status="DRAFT",
            doctype="R",
            issuer_name=self.company.name,
            issuer_oib=self.company.oib,
            client_name=self.partner.name,
            currency="EUR",
            subtotal=200.0,
            tax_amount=50.0,
            total=250.0,
        )
        r = self.client.get(f"/hr/invoicing/{inv.pk}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_client_portal_accept(self):
        from datetime import date

        from invoicing.models import Invoice

        inv = Invoice.objects.create(
            company=self.company,
            partner=self.partner,
            number=f"PONUDA-{uuid.uuid4().hex[:4].upper()}",
            date_issued=date(2026, 4, 14),
            date_due=date(2026, 4, 28),
            status="SENT",
            doctype="PO",
            issuer_name=self.company.name,
            issuer_oib=self.company.oib,
            client_name=self.partner.name,
            currency="EUR",
            subtotal=200.0,
            tax_amount=0.0,
            total=200.0,
        )
        anon = Client(enforce_csrf_checks=False)
        with override_settings(SECURE_SSL_REDIRECT=False):
            r = anon.get(f"/hr/ponuda/{inv.client_token}/", follow=True)
        self.assertLess(r.status_code, 500, "Client portal must not 500")
        with override_settings(SECURE_SSL_REDIRECT=False):
            r = anon.post(
                f"/hr/ponuda/{inv.client_token}/prihvati/",
                {},
                SERVER_NAME="testserver",
            )
        self.assertEqual(r.status_code, 200)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "ACCEPTED")


@NO_HTTPS
class ArhivaFlowSmokeTest(TestCase):
    """10.5 — Arhiva: upload → entry created → hash exists."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_user(draft=False)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=False)
        self.client.login(username=self.user.username, password="SmokePass2026!")

    def test_arhiva_list(self):
        r = self.client.get("/hr/documents/arhiva/")
        self.assertEqual(r.status_code, 200)

    def test_arhiva_upload_get(self):
        r = self.client.get("/hr/documents/arhiva/upload/")
        self.assertLess(r.status_code, 500)

    def test_arhiva_upload_post(self):
        from documents.models import ArhivaEntry

        f = SimpleUploadedFile("test.pdf", b"%PDF-1.4 smoke test content", content_type="application/pdf")
        count_before = ArhivaEntry.objects.filter(company=self.company).count()
        r = self.client.post(
            "/hr/documents/arhiva/upload/",
            {"file": f, "source_type": "invoice", "doc_number": "SMOKE-001", "amount": "100.00"},
        )
        self.assertLess(r.status_code, 500)
        count_after = ArhivaEntry.objects.filter(company=self.company).count()
        self.assertGreater(count_after, count_before, "Upload must create ArhivaEntry")
        latest = ArhivaEntry.objects.filter(company=self.company).order_by("-archived_at").first()
        self.assertIsNotNone(latest.integrity_hash, "SHA-256 hash mora biti popunjen")


@NO_HTTPS
class ErrorHandlingSmokeTest(TestCase):
    """10.6 — Error handling: nema 500 za poznate edge case-ove."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_user(draft=False)

    def test_anon_invoicing_redirects_to_login(self):
        r = Client().get("/hr/invoicing/", follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_anon_arhiva_redirects_to_login(self):
        r = Client().get("/hr/documents/arhiva/", follow=False)
        self.assertLess(r.status_code, 500)

    def test_bad_oib_in_company_setup(self):
        c = Client(enforce_csrf_checks=False)
        c.login(username=self.user.username, password="SmokePass2026!")
        r = c.post(
            "/hr/companies/setup/company/",
            {
                "name": "Test",
                "oib": "bad",
                "address": "t",
                "city": "Zagreb",
                "zip_code": "10000",
                "country": "HR",
                "industry": "it",
            },
        )
        self.assertLess(r.status_code, 500)

    def test_user_without_company_no_500(self):
        from accounts.models import UserProfile

        no_co_user = User.objects.create_user(
            username=f"noco_{uuid.uuid4().hex[:6]}", email=_make_email(), password="Test123!"
        )
        UserProfile.objects.update_or_create(user=no_co_user, defaults={"company": None, "role": "worker"})
        c = Client(enforce_csrf_checks=False)
        c.login(username=no_co_user.username, password="Test123!")
        r = c.get("/hr/invoicing/", follow=False)
        self.assertLess(r.status_code, 500)
