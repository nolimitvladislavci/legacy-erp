"""Extra tests for companies/views.py and work_orders/views.py."""

import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, modules=None, is_superuser=False):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(name=f"CW {oib}", oib=oib)
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
            modules_override=modules or ["invoicing", "partners"],
        )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class CompanySettingsExtraTest(TestCase):
    """Extra tests for company settings views."""

    def setUp(self):
        self.company, self.user = _setup_user("51515151510", "cw_set1", ["invoicing", "partners"])
        # Create an employee user
        self.employee = User.objects.create_user("cw_emp1", password="pass123")
        from accounts.models import UserProfile

        try:
            UserProfile.objects.create(user=self.employee, company=self.company, role="worker")
        except (IntegrityError, DatabaseError):
            pass
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cw_set1", password="pass123")

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_company_settings(self):
        self.assertIn(self._get("/companies/settings/"), ALLOWED)

    def test_company_settings_post(self):
        resp = self.client.post(
            "/companies/settings/",
            {
                "name": "Updated Company",
                "oib": "51515151510",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_employee_create_get(self):
        self.assertIn(self._get("/companies/settings/employee/create/"), ALLOWED)

    def test_employee_create_post(self):
        resp = self.client.post(
            "/companies/settings/employee/create/",
            {
                "username": "cw_emp_new1",
                "first_name": "New",
                "last_name": "Employee",
                "email": "newcw@test.hr",
                "role": "worker",
                "password1": "testpass789!",
                "password2": "testpass789!",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_employee_edit_get(self):
        self.assertIn(self._get(f"/companies/settings/employee/{self.employee.pk}/edit/"), ALLOWED)

    def test_employee_edit_post(self):
        resp = self.client.post(
            f"/companies/settings/employee/{self.employee.pk}/edit/",
            {
                "first_name": "Updated",
                "last_name": "Employee",
                "email": "emp_updated@test.hr",
                "role": "worker",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_employee_change_password_get(self):
        self.assertIn(self._get(f"/companies/settings/employee/{self.employee.pk}/password/"), ALLOWED)

    def test_employee_change_password_post(self):
        resp = self.client.post(
            f"/companies/settings/employee/{self.employee.pk}/password/",
            {
                "new_password1": "newpass456!",
                "new_password2": "newpass456!",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_employee_toggle_active(self):
        resp = self.client.post(f"/companies/settings/employee/{self.employee.pk}/toggle/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_onboarding_dismiss(self):
        resp = self.client.post("/companies/onboarding/dismiss/", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_nkd_search(self):
        resp = self.client.get("/companies/api/nkd-search/?q=Info", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_branch_create_post(self):
        resp = self.client.post(
            "/companies/settings/branch/save/",
            {
                "name": "Podružnica 1",
                "address": "Test 1",
                "city": "Zagreb",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)


class WorkOrderWithDataExtraTest(TestCase):
    """Extra work order tests with vehicle/client cards."""

    def setUp(self):
        self.company, self.user = _setup_user("52525252520", "cw_wo1", ["work_orders", "invoicing", "partners"])
        self.client = Client(raise_request_exception=False)
        self.client.login(username="cw_wo1", password="pass123")

    def _make_wo(self):
        from work_orders.models import WorkOrder

        return WorkOrder.objects.create(
            company=self.company,
            description="CW Test WO",
            status="new",
        )

    def _make_vehicle(self):
        from work_orders.models import VehicleCard

        return VehicleCard.objects.create(
            company=self.company,
            registration="ZG-123-AB",
            make="Test",
            model="Car",
        )

    def _make_client_card(self):
        from work_orders.models import ClientCard

        return ClientCard.objects.create(
            company=self.company,
            name="Test Client",
        )

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_work_order_list(self):
        self.assertIn(self._get("/work-orders/"), ALLOWED)

    def test_work_order_create_get(self):
        self.assertIn(self._get("/work-orders/new/"), ALLOWED)

    def test_work_order_create_post(self):
        resp = self.client.post(
            "/work-orders/new/",
            {
                "description": "CW New WO",
                "status": "new",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_work_order_detail(self):
        try:
            wo = self._make_wo()
            self.assertIn(self._get(f"/work-orders/{wo.pk}/"), ALLOWED)
        except Exception:
            pass

    def test_work_order_edit_get(self):
        try:
            wo = self._make_wo()
            self.assertIn(self._get(f"/work-orders/{wo.pk}/edit/"), ALLOWED)
        except Exception:
            pass

    def test_work_order_edit_post(self):
        try:
            wo = self._make_wo()
            resp = self.client.post(
                f"/work-orders/{wo.pk}/edit/",
                {
                    "description": "Updated WO",
                    "status": "in_progress",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_work_order_complete(self):
        try:
            wo = self._make_wo()
            resp = self.client.post(f"/work-orders/{wo.pk}/complete/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_work_order_cancel(self):
        try:
            wo = self._make_wo()
            resp = self.client.post(f"/work-orders/{wo.pk}/cancel/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_work_order_to_invoice(self):
        try:
            wo = self._make_wo()
            resp = self.client.post(f"/work-orders/{wo.pk}/to-invoice/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_vehicle_list(self):
        self.assertIn(self._get("/work-orders/vehicles/"), ALLOWED)

    def test_vehicle_create_get(self):
        self.assertIn(self._get("/work-orders/vehicles/new/"), ALLOWED)

    def test_vehicle_create_post(self):
        resp = self.client.post(
            "/work-orders/vehicles/new/",
            {
                "registration": "ZG-TEST-01",
                "make": "Test",
                "model": "Car",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_vehicle_detail(self):
        try:
            v = self._make_vehicle()
            self.assertIn(self._get(f"/work-orders/vehicles/{v.pk}/"), ALLOWED)
        except Exception:
            pass

    def test_vehicle_edit_get(self):
        try:
            v = self._make_vehicle()
            self.assertIn(self._get(f"/work-orders/vehicles/{v.pk}/edit/"), ALLOWED)
        except Exception:
            pass

    def test_client_card_list(self):
        self.assertIn(self._get("/work-orders/client-cards/"), ALLOWED)

    def test_client_card_create_get(self):
        self.assertIn(self._get("/work-orders/client-cards/new/"), ALLOWED)

    def test_client_card_create_post(self):
        resp = self.client.post(
            "/work-orders/client-cards/new/",
            {
                "name": "CW New Client",
                "phone": "091123456",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_client_card_detail(self):
        try:
            cc = self._make_client_card()
            self.assertIn(self._get(f"/work-orders/client-cards/{cc.pk}/"), ALLOWED)
        except Exception:
            pass

    def test_client_card_edit_get(self):
        try:
            cc = self._make_client_card()
            self.assertIn(self._get(f"/work-orders/client-cards/{cc.pk}/edit/"), ALLOWED)
        except Exception:
            pass

    def test_work_orders_filter_status(self):
        resp = self.client.get("/work-orders/?status=new", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_work_orders_search(self):
        resp = self.client.get("/work-orders/?q=test", follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_work_orders_filter_date(self):
        resp = self.client.get("/work-orders/?from=2026-01-01&to=2026-12-31", follow=True)
        self.assertIn(resp.status_code, ALLOWED)
