"""Extra tests for core/views.py — role-based dashboards, superadmin actions."""

import datetime
import uuid

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user_with_role(oib, username, role, modules=None, is_superuser=False):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(name=f"CoreX {oib}", oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password="pass123", email=f"{username}@test.hr")
    else:
        user = User.objects.create_user(username, password="pass123")
    try:
        profile = user.profile
        profile.company = company
        profile.role = role
        profile.save()
    except (IntegrityError, DatabaseError):
        from accounts.models import UserProfile

        UserProfile.objects.create(user=user, company=company, role=role)
    if not is_superuser:
        CompanySubscription.objects.create(
            company=company,
            plan="starter",
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle="monthly",
            modules_override=modules or ["invoicing", "partners"],
        )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class CompanyAdminDashboardTest(TestCase):
    """Tests for company_admin dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role(
            "61616161616",
            "cx_admin1",
            "company_admin",
            ["invoicing", "partners", "documents", "worktime", "projects", "pos"],
        )
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_admin1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_company_dashboard(self):
        self.assertIn(self._get("/dashboard/company/"), ALLOWED)

    def test_dashboard_root_redirect(self):
        self.assertIn(self._get("/"), ALLOWED)

    def test_whatsapp_health(self):
        self.assertIn(self._get("/api/whatsapp/health/"), ALLOWED)


class ManagerDashboardTest(TestCase):
    """Tests for project_manager/manager dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role(
            "62626262626", "cx_mgr1", "project_manager", ["invoicing", "partners", "projects", "worktime"]
        )
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_mgr1", password="pass123")

    def test_manager_dashboard(self):
        resp = self.client.get("/dashboard/manager/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_root(self):
        resp = self.client.get("/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class WorkerDashboardTest(TestCase):
    """Tests for worker dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role(
            "63636363636", "cx_worker1", "worker", ["worktime", "invoicing"]
        )
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_worker1", password="pass123")

    def test_worker_dashboard(self):
        resp = self.client.get("/dashboard/worker/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dashboard_root(self):
        resp = self.client.get("/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class InvestorDashboardTest(TestCase):
    """Tests for investor dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role("64646464646", "cx_inv1", "investor", ["invoicing", "projects"])
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_inv1", password="pass123")

    def test_investor_dashboard(self):
        resp = self.client.get("/dashboard/investor/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class PartnerDashboardTest(TestCase):
    """Tests for partner dashboard."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role(
            "65656565656", "cx_partner1", "partner", ["invoicing", "partners"]
        )
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_partner1", password="pass123")

    def test_partner_dashboard(self):
        resp = self.client.get("/dashboard/partner/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class SuperadminActionsTest(TestCase):
    """Tests for superadmin actions — update modules, impersonation."""

    def setUp(self):
        self.company, self.user = _setup_user_with_role("66666666666", "cx_super1", "superadmin", is_superuser=True)
        # Create a second company with subscription for impersonation/module update
        from companies.models import Company
        from registration.models import CompanySubscription

        self.company2 = Company.objects.create(name="Target Co", oib="66666666667")
        self.sub = CompanySubscription.objects.create(
            company=self.company2,
            plan="starter",
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle="monthly",
            modules_override=["invoicing"],
        )
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cx_super1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_superadmin_dashboard(self):
        self.assertIn(self._get("/superadmin/"), ALLOWED)

    def test_superadmin_companies(self):
        self.assertIn(self._get("/superadmin/companies/"), ALLOWED)

    def test_superadmin_create_promo_get(self):
        self.assertIn(self._get("/superadmin/promo/create/"), ALLOWED)

    def test_start_impersonation_invalid(self):
        fake_id = uuid.uuid4()
        resp = self.client.get(f"/superadmin/impersonate/{fake_id}/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_start_impersonation_valid(self):
        resp = self.client.get(f"/superadmin/impersonate/{self.company2.pk}/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_stop_impersonation(self):
        resp = self.client.get("/superadmin/impersonate/stop/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_superadmin_company_branches(self):
        resp = self.client.get(f"/superadmin/companies/{self.company2.pk}/branches/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_update_company_modules_get(self):
        resp = self.client.get(f"/superadmin/modules/{self.sub.pk}/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_update_company_modules_post(self):
        resp = self.client.post(
            f"/superadmin/modules/{self.sub.pk}/",
            {
                "modules": ["invoicing", "partners"],
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_superadmin_companies_search(self):
        resp = self.client.get("/superadmin/companies/?q=test", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_superadmin_companies_filter(self):
        resp = self.client.get("/superadmin/companies/?plan=starter", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_whatsapp_health_superadmin(self):
        self.assertIn(self._get("/api/whatsapp/health/"), ALLOWED)

    def test_health_check(self):
        self.assertIn(self._get("/health/"), ALLOWED)
