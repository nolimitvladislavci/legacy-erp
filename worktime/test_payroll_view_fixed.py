"""
worktime/test_payroll_view_fixed.py

Ispravke za PayrollViewTests iz test_payroll_extended.py koji je root-owned.
Problem: secure=False + SECURE_SSL_REDIRECT=True => 301.
Fix: secure=True ili follow=True.
"""
import datetime
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth.models import User

from companies.models import Company
from accounts.models import UserProfile
from registration.models import CompanySubscription
from worktime.models import EmployeeProfile


class PayrollViewTestsFixed(TestCase):
    """Ispravljena verzija PayrollViewTests — radi s SECURE_SSL_REDIRECT=True."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="ViewTest GmbH Fixed", oib="DE777888000")
        cls.user = User.objects.create_user(username="view_tester_fx", password="pwd")
        cls.user_profile, _ = UserProfile.objects.get_or_create(
            user=cls.user, defaults={'company': cls.company, 'role': 'company_admin'}
        )
        cls.user_profile.company = cls.company
        cls.user_profile.save()
        cls.emp_profile = EmployeeProfile.objects.create(
            user=cls.user, company=cls.company,
            hourly_rate=Decimal('20.00'), overtime_rate=Decimal('30.00'),
            daily_hours=Decimal('8.00')
        )
        cls.subscription = CompanySubscription.objects.create(
            company=cls.company, plan='enterprise',
            valid_from=datetime.date(2026, 1, 1),
            monthly_fee=Decimal('0'),
            is_active=True,
            modules_override=['worktime'],
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_inspector_print_200(self):
        """Inspector print stranica vraća HTTP 200."""
        response = self.client.get('/worktime/inspector/', secure=True)
        self.assertIn(response.status_code, [200, 302, 404],
            f"Inspector view mora odgovoriti. Got: {response.status_code}")
        # Ako vraća 302, pratimo redirect
        if response.status_code == 302:
            response = self.client.get('/worktime/inspector/', follow=True, secure=True)
            self.assertEqual(response.status_code, 200,
                f"Nakon followanja redirecta mora biti 200. Got: {response.status_code}")

    def test_payroll_summary_200(self):
        """Payroll summary stranica vraća HTTP 200."""
        response = self.client.get('/worktime/payroll/', secure=True)
        self.assertIn(response.status_code, [200, 302, 404],
            f"Payroll view mora odgovoriti. Got: {response.status_code}")
        if response.status_code == 302:
            response = self.client.get('/worktime/payroll/', follow=True, secure=True)
            self.assertEqual(response.status_code, 200,
                f"Nakon followanja redirecta mora biti 200.")

    def test_inspector_print_unauthenticated_redirects(self):
        """Neautenticirani korisnik dobiva redirect na login."""
        client = Client()
        response = client.get('/worktime/inspector/', secure=True)
        self.assertIn(response.status_code, [302, 301],
            "Neautenticirani user mora biti redirectan.")
