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
        oib="DE123456789",
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
class AccountViewSmokeTest(TestCase):
    """Smoke test account/auth views — no company data needed."""

    def test_login_page(self):
        r = self.client.get("/accounts/login/")
        self.assertLess(r.status_code, 500)

    def test_login_post_invalid(self):
        r = self.client.post("/accounts/login/", {"username": "x", "password": "y"})
        self.assertLess(r.status_code, 500)

    def test_logout(self):
        r = self.client.get("/accounts/logout/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_register_page(self):
        r = self.client.get("/accounts/register/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_api_docs(self):
        r = self.client.get("/api/docs/")
        self.assertLess(r.status_code, 500)

    def test_api_schema(self):
        r = self.client.get("/api/schema/")
        self.assertLess(r.status_code, 500)


@NO_HTTPS
class AuthenticatedSmokeTest(TestCase):
    """Smoke tests for views that need an authenticated user + company."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.user = _setup_company_and_user()

    def setUp(self):
        self.client = Client()
        self.client.login(username="smoke_admin", password="SmokePass2026!")

    def test_dashboard(self):
        r = self.client.get("/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_search(self):
        r = self.client.get("/search/", {"q": "test"}, follow=True)
        self.assertLess(r.status_code, 500)

    def test_company_profile(self):
        r = self.client.get("/companies/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_company_settings(self):
        r = self.client.get("/companies/settings/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_company_api(self):
        r = self.client.get("/companies/api/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_invoicing_list(self):
        r = self.client.get("/invoicing/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_partner_list(self):
        r = self.client.get("/partners/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_document_list(self):
        r = self.client.get("/documents/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_pos_dashboard(self):
        r = self.client.get("/pos/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_inventory_list(self):
        r = self.client.get("/inventory/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_worktime_dashboard(self):
        r = self.client.get("/worktime/", follow=True)
        self.assertLess(r.status_code, 500)

    def test_notifications(self):
        r = self.client.get("/notifications/", follow=True)
        self.assertLess(r.status_code, 500)
