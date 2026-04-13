"""Integration tests for zero-coverage modules."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase


class IntegrationTestBase(TestCase):
    def setUp(self):
        from accounts.models import UserProfile
        from companies.models import Company

        self.company = Company.objects.create(name="IntTest GmbH", oib="55555555551")
        self.user = User.objects.create_user("inttest", password="test123")
        UserProfile.objects.update_or_create(
            user=self.user, defaults={"company": self.company, "role": "company_admin"}
        )
        self.c = Client()
        self.c.login(username="inttest", password="test123")


class TestWorkOrderViews(IntegrationTestBase):
    def test_list(self):
        self.assertIn(self.c.get("/work-orders/").status_code, [200, 301, 302])

    def test_create_page(self):
        self.assertIn(self.c.get("/work-orders/create/").status_code, [200, 301, 302])

    def test_vehicle_cards(self):
        self.assertIn(self.c.get("/work-orders/vehicles/").status_code, [200, 301, 302])

    def test_client_cards(self):
        self.assertIn(self.c.get("/work-orders/clients/").status_code, [200, 301, 302])


class TestWorkOrderModels(IntegrationTestBase):
    def test_create_wo(self):
        from work_orders.models import WorkOrder

        wo = WorkOrder.objects.create(
            company=self.company,
            order_number="WO-M1",
            status="draft",
        )
        self.assertEqual(wo.status, "draft")

    def test_wo_lifecycle(self):
        from work_orders.models import WorkOrder

        wo = WorkOrder.objects.create(company=self.company, order_number="WO-M2", status="draft")
        wo.status = "in_progress"
        wo.save()
        wo.status = "completed"
        wo.save()
        wo.refresh_from_db()
        self.assertEqual(wo.status, "completed")


class TestCompanyModels(IntegrationTestBase):
    def test_oib(self):
        self.assertEqual(self.company.oib, "55555555551")

    def test_fields(self):
        self.assertTrue(hasattr(self.company, "name"))


class TestCompanyViews(IntegrationTestBase):
    def test_dashboard(self):
        self.assertIn(self.c.get("/").status_code, [200, 301, 302])


class TestProjectViews(IntegrationTestBase):
    def test_list(self):
        self.assertIn(self.c.get("/projects/").status_code, [200, 301, 302])

    def test_create_and_detail(self):
        from projects.models import Project

        p = Project.objects.create(company=self.company, name="Proj1", status="active")
        self.assertIn(self.c.get(f"/projects/{p.pk}/").status_code, [200, 301, 302])


class TestProjectModels(IntegrationTestBase):
    def test_create(self):
        from projects.models import Project

        p = Project.objects.create(company=self.company, name="P1", status="active")
        self.assertEqual(p.name, "P1")

    def test_budget(self):
        from projects.models import Project

        p = Project.objects.create(company=self.company, name="BP", status="active", budget=Decimal("50000"))
        self.assertEqual(p.budget, Decimal("50000"))


class TestCalculatorViews(IntegrationTestBase):
    def test_page(self):
        self.assertIn(self.c.get("/calculator/").status_code, [200, 301, 302])


class TestBurzaViews(IntegrationTestBase):
    def test_list(self):
        self.assertIn(self.c.get("/burza/").status_code, [200, 301, 302])


class TestBurzaModels(IntegrationTestBase):
    def test_create_lead(self):
        from burza.models import ProjectLead

        lead = ProjectLead.objects.create(
            title="Renovacija",
            description="100m2",
            company=self.company,
            created_by=self.user,
        )
        self.assertEqual(lead.title, "Renovacija")


class TestWorktimeViews(IntegrationTestBase):
    def test_page(self):
        self.assertIn(self.c.get("/worktime/").status_code, [200, 301, 302])


class TestFinanceViews(IntegrationTestBase):
    def test_page(self):
        self.assertIn(self.c.get("/finance/").status_code, [200, 301, 302])


class TestCrossCompanyIsolation(TestCase):
    def setUp(self):
        from accounts.models import UserProfile
        from companies.models import Company

        self.co_a = Company.objects.create(name="Co A", oib="11111111111")
        self.co_b = Company.objects.create(name="Co B", oib="22222222222")
        self.user_b = User.objects.create_user("iso_b", password="test123")
        UserProfile.objects.update_or_create(user=self.user_b, defaults={"company": self.co_b, "role": "company_admin"})

    def test_partner_isolation(self):
        from partners.models import Partner

        p = Partner.objects.create(company=self.co_a, name="Secret")
        c = Client()
        c.login(username="iso_b", password="test123")
        self.assertIn(c.get(f"/partners/edit/{p.pk}/").status_code, [403, 404, 301, 302])

    def test_project_isolation(self):
        from projects.models import Project

        proj = Project.objects.create(company=self.co_a, name="Secret", status="active")
        c = Client()
        c.login(username="iso_b", password="test123")
        self.assertIn(c.get(f"/projects/{proj.pk}/").status_code, [403, 404, 301, 302])
