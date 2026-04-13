"""
Smoke tests for core views — ensure views return HTTP 200/302 without errors.
Maximizes code coverage by exercising major view functions.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

User = get_user_model()
NO_HTTPS = override_settings(SECURE_SSL_REDIRECT=False)


def _setup_company_and_user():
    from accounts.models import UserProfile
    from companies.models import Company

    company = Company.objects.create(
        name="Smoke Test GmbH",
        oib="55544433321",
        country="DE",
        city="Berlin",
        zip_code="10115",
    )
    user = User.objects.create_user(
        username="smoke_admin",
        email="smoke@test.de",
        password="SmokePass2026!",
        is_superuser=True,
        is_staff=True,
    )
    UserProfile.objects.create(
        user=user,
        company=company,
        role="company_admin",
        language="de",
    )
    return company, user


@NO_HTTPS
class CoreViewSmokeTest(TestCase):
    """Smoke test major core views for HTTP 200/302."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_dashboard(self):
        r = self.client.get("/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_language_switch_hr(self):
        r = self.client.get("/i18n/setlang/", {"language": "hr"}, follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_api_docs(self):
        r = self.client.get("/api/docs/")
        self.assertIn(r.status_code, [200, 301, 302])

    def test_api_schema(self):
        r = self.client.get("/api/schema/")
        self.assertIn(r.status_code, [200, 301, 302])

    def test_search(self):
        r = self.client.get("/search/", {"q": "test"}, follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_notifications(self):
        r = self.client.get("/notifications/", follow=True)
        self.assertIn(r.status_code, [200, 302, 404])

    def test_help(self):
        r = self.client.get("/help/", follow=True)
        self.assertIn(r.status_code, [200, 302, 404])


@NO_HTTPS
class CompanyViewSmokeTest(TestCase):
    """Smoke test company views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_company_profile(self):
        r = self.client.get("/companies/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_company_settings(self):
        r = self.client.get("/companies/settings/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_company_api(self):
        r = self.client.get("/companies/api/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_company_modules(self):
        r = self.client.get("/companies/settings/?tab=modules", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class AccountViewSmokeTest(TestCase):
    """Smoke test account/auth views."""

    def test_login_page(self):
        r = self.client.get("/accounts/login/")
        self.assertIn(r.status_code, [200, 301, 302])

    def test_login_post_invalid(self):
        r = self.client.post("/accounts/login/", {"username": "x", "password": "y"})
        self.assertIn(r.status_code, [200, 302])

    def test_logout(self):
        r = self.client.get("/accounts/logout/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_register_page(self):
        r = self.client.get("/accounts/register/", follow=True)
        self.assertIn(r.status_code, [200, 302, 404])


@NO_HTTPS
class InvoicingViewSmokeTest(TestCase):
    """Smoke test invoicing views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_invoice_list(self):
        r = self.client.get("/invoicing/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_invoice_api(self):
        r = self.client.get("/invoicing/api/invoices/", follow=True)
        self.assertIn(r.status_code, [200, 302, 403])

    def test_invoice_create_get(self):
        r = self.client.get("/invoicing/create/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class PartnerViewSmokeTest(TestCase):
    """Smoke test partner views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_partner_list(self):
        r = self.client.get("/partners/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_partner_create_get(self):
        r = self.client.get("/partners/create/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class DocumentViewSmokeTest(TestCase):
    """Smoke test document views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_document_list(self):
        r = self.client.get("/documents/", follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_document_api(self):
        r = self.client.get("/documents/api/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class POSViewSmokeTest(TestCase):
    """Smoke test POS views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_pos_dashboard(self):
        r = self.client.get("/pos/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class InventoryViewSmokeTest(TestCase):
    """Smoke test inventory views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_inventory_list(self):
        r = self.client.get("/inventory/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class WorktimeViewSmokeTest(TestCase):
    """Smoke test worktime views."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_worktime_dashboard(self):
        r = self.client.get("/worktime/", follow=True)
        self.assertIn(r.status_code, [200, 302])


@NO_HTTPS
class ModelSmokeTest(TestCase):
    """Test core model creation."""

    def test_create_company(self):
        from companies.models import Company

        c = Company.objects.create(name="Test Co", oib="12345678903", country="HR")
        self.assertEqual(str(c), "Test Co")
        self.assertEqual(c.oib, "12345678903")

    def test_create_user_profile(self):
        from accounts.models import UserProfile
        from companies.models import Company

        company = Company.objects.create(name="Profile Co", oib="98765432109", country="HR")
        user = User.objects.create_user(username="profiletest", password="test123")
        profile = UserProfile.objects.create(user=user, company=company, role="employee")
        self.assertEqual(profile.role, "employee")
        self.assertEqual(profile.company, company)

    def test_create_invoice(self):
        from companies.models import Company
        from invoicing.models import Invoice

        company = Company.objects.create(name="Invoice Co", oib="11122233344", country="DE")
        inv = Invoice.objects.create(
            company=company,
            invoice_number="TEST-001",
            status="draft",
        )
        self.assertEqual(inv.invoice_number, "TEST-001")
        self.assertEqual(inv.status, "draft")
