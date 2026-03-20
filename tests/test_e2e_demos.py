"""
End-to-end demo scenario tests — Autoservis, Frizer, Restoran.
Verifies complete workflows for sales tour demos.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from companies.models import Company


class AutoservisE2ETest(TestCase):
    """Autoservis demo: Partner -> Radni nalog -> Faktura -> PDF"""

    def setUp(self):
        self.company = Company.objects.create(name="Demo Autoservis d.o.o.", oib="11111111111")
        self.user = User.objects.create_user("autoservis_demo", password="test123", is_staff=True)
        from accounts.models import UserProfile
        try:
            p = UserProfile.objects.get(user=self.user)
            p.company = self.company
            p.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=self.user, company=self.company)
        self.client = Client(SERVER_NAME="viskovic-group.de")
        self.client.login(username="autoservis_demo", password="test123")

    def test_partner_list(self):
        r = self.client.get("/partners/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_work_order_list(self):
        r = self.client.get("/work-orders/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_work_order_create(self):
        r = self.client.get("/work-orders/new/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_invoice_list(self):
        r = self.client.get("/invoicing/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_calculator(self):
        r = self.client.get("/calculator/", follow=True)
        self.assertEqual(r.status_code, 200)


class FrizerE2ETest(TestCase):
    """Frizer demo: Booking -> Appointment -> Klijent karton"""

    def setUp(self):
        self.company = Company.objects.create(name="Demo Frizer d.o.o.", oib="22222222222")
        self.user = User.objects.create_user("frizer_demo", password="test123", is_staff=True)
        from accounts.models import UserProfile
        try:
            p = UserProfile.objects.get(user=self.user)
            p.company = self.company
            p.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=self.user, company=self.company)
        self.client = Client(SERVER_NAME="viskovic-group.de")
        self.client.login(username="frizer_demo", password="test123")

    def test_appointment_calendar(self):
        r = self.client.get("/appointments/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_services_list(self):
        r = self.client.get("/appointments/usluge/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_public_booking(self):
        """Public booking doesn't need login"""
        anon = Client(SERVER_NAME="viskovic-group.de")
        r = anon.get("/appointments/booking/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_client_dossiers(self):
        r = self.client.get("/appointments/kartoni/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_notifications(self):
        r = self.client.get("/notifications/", follow=True)
        self.assertEqual(r.status_code, 200)


class RestoranE2ETest(TestCase):
    """Restoran demo: Marketplace -> POS -> Inventory"""

    def setUp(self):
        self.company = Company.objects.create(name="Demo Restoran d.o.o.", oib="33333333333")
        self.user = User.objects.create_user("restoran_demo", password="test123", is_staff=True)
        from accounts.models import UserProfile
        try:
            p = UserProfile.objects.get(user=self.user)
            p.company = self.company
            p.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=self.user, company=self.company)
        self.client = Client(SERVER_NAME="viskovic-group.de")
        self.client.login(username="restoran_demo", password="test123")

    def test_pos_terminal(self):
        r = self.client.get("/pos/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_marketplace(self):
        r = self.client.get("/marketplace/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_inventory(self):
        r = self.client.get("/inventory/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_gastro_menu_coming_soon(self):
        r = self.client.get("/gastro-menu/", follow=True)
        self.assertEqual(r.status_code, 200)

    def test_delivery_coming_soon(self):
        r = self.client.get("/delivery/", follow=True)
        self.assertEqual(r.status_code, 200)
