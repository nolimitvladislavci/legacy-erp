"""
Phase 10: Continuous Blind Inventory — Matrica Loma
Test 10.1: Biologski Kalo vs. Kradja (tolerancija 2%)
Test 10.2: Paradoks Slijepe Inventure (zabrana potvrde bez vage)
Test 10.3: FEFO Curenje — prodaja iz HACCP karantene
"""

import datetime
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from companies.models import Company
from inventory.models import InventoryCountLog, InventoryItem, StockBatch

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class KaloVsTheftTests(TestCase):
    """Test 10.1: Biologski Kalo vs. Kradja"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Viskovic Lager", oib="11122233344")
        cls.user = User.objects.create_user(username="skladistar", password="test1234")
        cls.item = InventoryItem.objects.create(
            company=cls.company,
            name="Svjezi sir",
            sku="SIR-001",
            unit="kg",
            quantity=Decimal("100"),
            kalo_percent=Decimal("2.00"),
        )
        cls.batch = StockBatch.objects.create(
            company=cls.company,
            item=cls.item,
            batch_number="LOT-2026-03",
            expected_weight=Decimal("10.000"),
            quantity=Decimal("10"),
        )

    def setUp(self):
        self.client.login(username="skladistar", password="test1234")
        self.url = "/inventory/api/submit-count/"

    def test_natural_kalo_accepted(self):
        """1.5% manjka (9.85 kg od 10 kg) — unutar 2% tolerancije => OK"""
        resp = self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "actual_weight": 9.85}), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200, f"Kalo od 1.5% mora proci! Got: {resp.content}")
        data = resp.json()
        self.assertIn(data["status"], ["ok", "kalo"])

    def test_theft_alert_triggered(self):
        """10% manjka (9.00 kg od 10 kg) — premasuje 2% toleranciju => 409"""
        resp = self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "actual_weight": 9.00}), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 409, "Sustav MORA prijaviti kradju kad je manjak 10% a tolerancija 2%!")
        data = resp.json()
        self.assertIn("kalo", data.get("error", "").lower(), "Poruka greske mora spomenuti kalo/kradju")

    def test_count_logged_in_audit_trail(self):
        """Svako brojanje mora ostaviti trag u InventoryCountLog."""
        self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "actual_weight": 9.90}), content_type="application/json"
        )
        logs = InventoryCountLog.objects.filter(batch=self.batch)
        self.assertTrue(logs.exists(), "Mora postojati zapisnik inventure!")
        log = logs.first()
        self.assertEqual(log.counted_by, self.user)


@override_settings(SECURE_SSL_REDIRECT=False)
class BlindCountEnforcementTests(TestCase):
    """Test 10.2: Paradoks Slijepe Inventure"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Viskovic Kontrola", oib="55566677788")
        cls.user = User.objects.create_user(username="skladistar2", password="test1234")
        cls.item = InventoryItem.objects.create(
            company=cls.company,
            name="Maslinovo ulje",
            sku="OIL-001",
            unit="L",
            quantity=Decimal("50"),
        )
        cls.batch = StockBatch.objects.create(
            company=cls.company,
            item=cls.item,
            batch_number="LOT-OIL-01",
            expected_weight=Decimal("25.000"),
            quantity=Decimal("50"),
        )

    def setUp(self):
        self.client.login(username="skladistar2", password="test1234")
        self.url = "/inventory/api/submit-count/"

    def test_blind_count_without_weight_rejected(self):
        """Skladistar ne smije potvrditi stanje bez unosa tezine s vage."""
        resp = self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "status": "OK"}), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400, "API MORA odbiti potvrdu bez unesene tezine/kolicine!")
        data = resp.json()
        error_lower = data.get("error", "").lower()
        self.assertTrue(
            "količ" in error_lower or "tezin" in error_lower or "težin" in error_lower,
            f"Poruka greske mora spomenuti kolicinu/tezinu. Got: {data.get('error', '')}",
        )

    def test_zero_weight_triggers_alert(self):
        """Tezina 0 vs 25 kg = 100% gubitak => theft alert."""
        resp = self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "actual_weight": 0}), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 409, "0 kg mora biti oznaceno kao kradja/potpuni gubitak!")

    def test_valid_weight_accepted(self):
        """S ispravnom tezinom potvrda mora proci."""
        resp = self.client.post(
            self.url, json.dumps({"batch_id": self.batch.pk, "actual_weight": 25.0}), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class HACCPQuarantineTests(TestCase):
    """Test 10.3: FEFO Curenje — prodaja iz HACCP karantene"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Viskovic HACCP", oib="99988877766")
        cls.user = User.objects.create_user(username="skladistar3", password="test1234")
        cls.item = InventoryItem.objects.create(
            company=cls.company,
            name="Gouda sir 500g",
            sku="SIR-GOUDA",
            unit="kg",
            quantity=Decimal("30"),
        )

    def setUp(self):
        self.client.login(username="skladistar3", password="test1234")
        self.expired_batch = StockBatch.objects.create(
            company=self.company,
            item=self.item,
            batch_number="LOT-EXPIRED",
            expected_weight=Decimal("5.000"),
            quantity=Decimal("10"),
            expiry_date=timezone.now().date() - datetime.timedelta(days=1),
        )
        self.valid_batch = StockBatch.objects.create(
            company=self.company,
            item=self.item,
            batch_number="LOT-FRESH",
            expected_weight=Decimal("5.000"),
            quantity=Decimal("10"),
            expiry_date=timezone.now().date() + datetime.timedelta(days=30),
        )

    def test_expired_batch_blocked_from_dispatch(self):
        """Istekla sarza MORA biti blokirana za otpremu."""
        url = f"/inventory/api/batch/{self.expired_batch.pk}/check-dispatch/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403, "Sustav MORA blokirati otpremu sarze s isteklim rokom!")
        data = resp.json()
        self.assertFalse(data.get("allowed", True))
        self.assertIn("karanten", data.get("error", "").lower(), "Poruka mora spomenuti karantenu")

    def test_expired_batch_auto_quarantined(self):
        """Istekla sarza se automatski prebacuje u HACCP karantenu."""
        url = f"/inventory/api/batch/{self.expired_batch.pk}/check-dispatch/"
        self.client.get(url)
        self.expired_batch.refresh_from_db()
        self.assertEqual(
            self.expired_batch.quarantine_status, "quarantine", "Automatska karantena mora biti aktivirana!"
        )

    def test_valid_batch_allowed_for_dispatch(self):
        """Svjeza sarza MORA proci za otpremu."""
        url = f"/inventory/api/batch/{self.valid_batch.pk}/check-dispatch/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, "Svjeza sarza mora biti odobrena za otpremu!")
        data = resp.json()
        self.assertTrue(data.get("allowed"))

    def test_count_on_expired_batch_blocked(self):
        """Inventura na istekloj sarzi MORA biti odbijena s 403."""
        resp = self.client.post(
            "/inventory/api/submit-count/",
            json.dumps({"batch_id": self.expired_batch.pk, "actual_weight": 4.95}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403, "Inventura na istekloj sarzi mora biti odbijena!")
