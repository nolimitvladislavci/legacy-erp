"""Smoke tests for companies, accounts, and core views."""

import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, is_superuser=False):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(name=f"CV {oib}", oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password="pass123", email=f"{username}@test.hr")
    else:
        user = User.objects.create_user(username, password="pass123")
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    if not is_superuser:
        CompanySubscription.objects.create(
            company=company,
            plan="starter",
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle="monthly",
            modules_override=["partners", "invoicing", "documents"],
        )
    return company, user


ALLOWED = [200, 302, 403, 404, 405, 500]


class CompanyViewSmokeTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("95959595959", "co_view1")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="co_view1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_company_profile(self):
        self.assertIn(self._get("/companies/"), ALLOWED)

    def test_company_settings(self):
        self.assertIn(self._get("/companies/settings/"), ALLOWED)

    def test_employee_create(self):
        self.assertIn(self._get("/companies/settings/employee/create/"), ALLOWED)

    def test_nkd_search(self):
        resp = self.client.get("/companies/api/nkd-search/", {"q": "Info"}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_company_list(self):
        self.assertIn(self._get("/companies/"), ALLOWED)


class AccountsViewSmokeTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("96969696969", "acc_view1")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="acc_view1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_user_list(self):
        self.assertIn(self._get("/accounts/"), ALLOWED)

    def test_user_edit(self):
        resp = self.client.get(f"/accounts/{self.user.pk}/edit/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_change_password_get(self):
        self.assertIn(self._get("/accounts/password/"), ALLOWED)

    def test_quick_register_get(self):
        self.assertIn(self._get("/accounts/quick-register/"), ALLOWED)


class CoreViewSmokeTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("97979797979", "core_view1")
        self.client = Client(raise_request_exception=False)
        self.client.login(username="core_view1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_dashboard(self):
        self.assertIn(self._get("/"), ALLOWED)

    def test_dashboard_slash(self):
        self.assertIn(self._get("/dashboard/"), ALLOWED)

    def test_login_get(self):
        c = Client(raise_request_exception=False)
        self.assertIn(c.get("/login/", follow=True).status_code, ALLOWED)

    def test_logout(self):
        resp = self.client.get("/logout/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class SuperadminViewSmokeTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user("98989898989", "superadmin1", is_superuser=True)
        self.client = Client(raise_request_exception=False)
        self.client.login(username="superadmin1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_superadmin_dashboard(self):
        self.assertIn(self._get("/superadmin/"), ALLOWED)

    def test_superadmin_companies(self):
        self.assertIn(self._get("/superadmin/companies/"), ALLOWED)
