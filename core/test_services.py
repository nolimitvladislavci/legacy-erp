"""Tests for core.services — dashboard stats unit tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.services_dashboard import (
    get_company_dashboard_stats,
    get_superadmin_stats,
    start_impersonation,
    stop_impersonation,
)

User = get_user_model()


class TestCompanyDashboardStats(TestCase):
    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Test Dashboard Co", oib="88888888888")
        self.user = User.objects.create_user("dashtest", password="test123")

    def test_returns_all_keys(self):
        stats = get_company_dashboard_stats(self.company, self.user)
        for key in ["company", "today", "total_invoiced", "unpaid", "total_partners"]:
            self.assertIn(key, stats, f"Missing key: {key}")

    def test_empty_company_returns_zeros(self):
        stats = get_company_dashboard_stats(self.company, self.user)
        self.assertEqual(stats["total_invoiced"], 0)
        self.assertEqual(stats["total_partners"], 0)

    def test_none_company(self):
        stats = get_company_dashboard_stats(None, self.user)
        self.assertIn("today", stats)


class TestSuperadminStats(TestCase):
    def test_returns_expected_keys(self):
        stats = get_superadmin_stats()
        self.assertIn("total_companies", stats)
        self.assertIn("total_users", stats)
        self.assertIn("companies_list", stats)
        self.assertIsInstance(stats["total_companies"], int)


class TestImpersonation(TestCase):
    def setUp(self):
        from companies.models import Company

        self.admin = User.objects.create_user("admin_imp", password="t", is_staff=True)
        self.regular = User.objects.create_user("regular_imp", password="t")
        self.company = Company.objects.create(name="Target Co", oib="99999999991")

    def test_admin_can_impersonate(self):
        result = start_impersonation(self.admin, self.company.pk)
        self.assertEqual(result["impersonate_company_id"], self.company.pk)

    def test_regular_cannot_impersonate(self):
        with self.assertRaises(PermissionError):
            start_impersonation(self.regular, self.company.pk)

    def test_stop_impersonation(self):
        stop_impersonation(self.admin)
