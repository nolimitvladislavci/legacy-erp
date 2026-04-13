"""
POS End-to-End Tests — pokriva cijeli POS workflow.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from companies.models import Company
from pos.models import POSPaymentLine, POSReceipt, POSSession, POSTerminal

User = get_user_model()


class POSEndToEndTests(TestCase):
    """E2E testovi: terminal -> sesija -> bon -> artikl -> naplata -> Z-report."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("testpos", "test@test.com", "Test1234!")
        self.user.is_staff = True
        self.user.save()

        self.company = Company.objects.create(
            name="Test POS d.o.o.",
            oib="12345678901",
            address="Testna 1",
        )
        # Profile
        from accounts.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.company = self.company
        profile.save()

        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name="Blagajna Test",
            pos_type="receipt",
        )
        self.client.login(username="testpos", password="Test1234!")

    def test_full_pos_workflow(self):
        """Kompletan workflow: otvori sesiju -> novi bon -> dodaj artikl -> plati -> zatvori."""
        # 1. Open session
        resp = self.client.post(
            f"/hr/pos/terminal/{self.terminal.pk}/open/",
            {
                "opening_cash": "100.00",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        session = POSSession.objects.filter(terminal=self.terminal).order_by("-pk").first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, "open")

        # 2. New receipt
        resp = self.client.post(f"/hr/pos/session/{session.pk}/receipt/new/", follow=True)
        self.assertIn(resp.status_code, [200, 301, 302])
        receipt = POSReceipt.objects.filter(session=session).first()
        self.assertIsNotNone(receipt)

        # 3. Add item
        resp = self.client.post(
            f"/hr/pos/receipt/{receipt.pk}/add-item/",
            {
                "description": "Test artikl",
                "quantity": "2",
                "unit_price": "10.00",
                "tax_rate": "25",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(receipt.items.count(), 1)
        item = receipt.items.first()
        self.assertEqual(item.quantity, Decimal("2"))
        self.assertEqual(item.unit_price, Decimal("10.00"))

        # 4. Pay
        resp = self.client.post(
            f"/hr/pos/receipt/{receipt.pk}/pay/",
            {
                "payment_method": "CASH",
                "tendered": "25.00",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "paid")

        # 5. Close session
        resp = self.client.post(
            f"/hr/pos/session/{session.pk}/close/",
            {
                "closing_cash": "120.00",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        session.refresh_from_db()
        self.assertEqual(session.status, "closed")

    def test_payment_methods(self):
        """Test da svi payment metodi rade."""
        for method in ["CASH", "CARD", "CRYPTO", "REVOLUT", "AIRCASH"]:
            self.assertIn(method, dict(POSPaymentLine.Method.choices))

    def test_device_token_create(self):
        """Test kreiranja DeviceToken."""
        resp = self.client.post(
            "/hr/pos/device-token/create/",
            {
                "device_name": "Test mobitel",
            },
        )
        # May redirect (301 trailing slash) - handle both
        if resp.status_code == 301:
            resp = self.client.post(resp.url, {"device_name": "Test mobitel"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("barcode_data", data)
        self.assertTrue(data["barcode_data"].startswith("LC-DEV-"))

    def test_device_token_panic(self):
        """Test panic button deaktivacije."""
        from accounts.models import DeviceToken

        dt = DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="Panic test",
        )
        self.assertTrue(dt.is_active)
        resp = self.client.post(f"/hr/pos/device-token/{dt.pk}/panic/")
        if resp.status_code == 301:
            resp = self.client.post(resp.url)
        self.assertEqual(resp.status_code, 200)
        dt.refresh_from_db()
        self.assertFalse(dt.is_active)

    def test_device_token_list(self):
        """Test liste tokena."""
        from accounts.models import DeviceToken

        DeviceToken.objects.create(
            user=self.user,
            company=self.company,
            device_name="List test",
        )
        resp = self.client.get("/hr/pos/device-token/list/", follow=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data["tokens"]), 0)

    def test_daily_reports_view(self):
        """Test da daily reports stranica radi."""
        resp = self.client.get("/hr/pos/reports/daily/")
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_improvement_suggestion(self):
        """Test knjige boljitaka."""
        resp = self.client.post(
            "/hr/pos/improvements/",
            {
                "title": "Dodati tamni mod",
                "description": "Blagajnici zele tamni mod za nocnu smjenu.",
                "category": "ux",
                "priority": "2",
            },
            follow=True,
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        from pos.models import ImprovementSuggestion

        s = ImprovementSuggestion.objects.filter(company=self.company).first()
        self.assertIsNotNone(s)
        self.assertEqual(s.title, "Dodati tamni mod")

    def test_onboarding_wizard(self):
        """Test onboarding wizard."""
        resp = self.client.get("/hr/pos/onboarding/")
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_pos_item_api(self):
        """Test API za dohvat artikla."""
        from inventory.models import InventoryItem

        item = InventoryItem.objects.create(
            company=self.company,
            name="API Test Artikl",
            sku="API001",
            unit_price=Decimal("5.00"),
            unit="kom",
            is_active=True,
        )
        resp = self.client.get(f"/hr/pos/api/item/{item.pk}/", follow=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], "API Test Artikl")
