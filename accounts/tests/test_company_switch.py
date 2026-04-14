"""
accounts/tests/test_company_switch.py
Critical path: company switch view.

Napomena: SECURE_SSL_REDIRECT=True → koristimo secure=True.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CompanyMembership, UserProfile
from companies.models import Company

User = get_user_model()

# Validirani OIB (ISO 7064 checksum)
VALID_OIB_SWITCH = "22222222226"


class CompanySwitchTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="switchtest",
            password="Test1234!",
            email="switchtest@test.com",
        )
        self.company = Company.objects.create(
            name="Switch Test d.o.o.",
            oib=VALID_OIB_SWITCH,
        )
        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            role="worker",
            is_active=True,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.company = self.company
        profile.save()

    def test_switch_company_requires_login(self):
        """POST switch_company bez logina → redirect na login"""
        resp = self.client.post(
            reverse("accounts:switch_company"),
            {"membership_id": self.membership.pk},
            secure=True,
        )
        self.assertIn(resp.status_code, [301, 302])
        loc = resp.get("Location", "")
        self.assertTrue("login" in loc or loc == "/")

    def test_switch_company_with_valid_membership(self):
        """POST switch_company s membership_id → 302"""
        self.client.login(username="switchtest", password="Test1234!")
        resp = self.client.post(
            reverse("accounts:switch_company"),
            {"membership_id": self.membership.pk},
            secure=True,
        )
        self.assertEqual(resp.status_code, 302)

    def test_switch_company_session_updated(self):
        """POST switch_company → session sadrži active_membership_id"""
        self.client.login(username="switchtest", password="Test1234!")
        self.client.post(
            reverse("accounts:switch_company"),
            {"membership_id": self.membership.pk},
            secure=True,
        )
        session = self.client.session
        self.assertEqual(session.get("active_membership_id"), self.membership.pk)

    def test_switch_company_without_data_redirects(self):
        """POST switch_company bez membership_id → 302 (error case)"""
        self.client.login(username="switchtest", password="Test1234!")
        resp = self.client.post(
            reverse("accounts:switch_company"),
            {},
            secure=True,
        )
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_on_company_route_redirects(self):
        """AnonymousUser GET /hr/companies/ → redirect"""
        resp = self.client.get("/hr/companies/", secure=True)
        self.assertIn(resp.status_code, [301, 302])
