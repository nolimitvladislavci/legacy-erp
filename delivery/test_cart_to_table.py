"""
CART-TO-TABLE TEST SUITE — ispravljeno za stvarne modele fina-connect
Pokretanje: python manage.py test delivery.test_cart_to_table -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from delivery.models import (
    ColdChainZone,
    ConsolidatedDelivery,
    DeliveryRoute,
    DeliveryStop,
    PackagingExchange,
    Vehicle,
)

User = get_user_model()


def make_company(name, oib, country="DE"):
    """Helper: kreira Company s minimalnim required fieldima."""
    return Company.objects.create(
        name=name,
        oib=oib,
        country=country,
        address="Teststraße 1",
        city="Stuttgart",
        zip_code="70000",
        iban="DE89370400440532013000",
        tax_number=oib,
        vat_id="DE" + oib[:9],
        phone="+4971100000",
        email=f"test_{oib}@grosmarkt.de",
        website_url="https://grosmarkt-online.eu",
        mobile="+4971100000",
        grosmarkt_partner=True,
        grosmarkt_role="logistik",
        grosmarkt_description="Testfirma",
    )


class CartToTableTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Firme
        cls.seller = make_company("Steiger Central GmbH", "11111111100")
        cls.buyer  = make_company("Pizzeria Roma GmbH",   "22222222200")

        # Vozač
        cls.driver = User.objects.create_user(
            username="vozac_test", password="pwd123"
        )

        # Vozilo (Vehicle) — potrebno za DeliveryRoute
        cls.vehicle = Vehicle.objects.create(
            company=cls.seller,
            name="Mercedes Sprinter TEST",
            plate_number="S-TEST-001",
            vehicle_type="refrigerated",
            has_cold_chain=True,
            gps_device_id="GPS-TEST-001",
            temp_sensor_id="TEMP-TEST-001",
            is_active=True,
        )

        # Ruta (DeliveryRoute) — potrebna za DeliveryStop
        import datetime

        from django.utils import timezone
        cls.route = DeliveryRoute.objects.create(
            date=timezone.now().date() + datetime.timedelta(days=1),
            vehicle=cls.vehicle,
            driver=cls.driver,
            status="planned",
        )

        # ColdChainZone — potrebna za HACCP test
        cls.cold_zone = ColdChainZone.objects.create(
            company=cls.seller,
            name="Hladnjača TEST",
            zone_type="refrigerated",
            target_min_temp=2,
            target_max_temp=8,
            sensor_device_id="SENSOR-TEST-001",
            sensor_api_url="http://localhost/mock-sensor",
            is_active=True,
        )

    def setUp(self):
        """APIClient s Token autentikacijom za cold-chain API.
        secure=True je obavezno jer je SECURE_SSL_REDIRECT=True u settings.
        """
        from rest_framework.authtoken.models import Token
        # enforce_csrf_checks=False jer test DB nema pravi CSRF token
        self.api_client = APIClient(enforce_csrf_checks=False)
        token, _ = Token.objects.get_or_create(user=self.driver)
        self.api_client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

    # ─────────────────────────────────────────────────────────
    # TEST 3.1 — Narudžba automatski kreira logističku stanicu
    # ─────────────────────────────────────────────────────────
    def test_3_1_auto_routing_marketplace_to_logistics(self):
        """
        SCENARIJ: ConsolidatedDelivery (kamion) kreira se za isporuku,
        DeliveryStop (stanica) dodaje se pod rutu.
        Provjera: status PENDING, stop vezan za pravi route.
        """
        print("\n--- [TEST 3.1] Auto-rutiranje: Marketplace -> Logistika ---")

        # ConsolidatedDelivery = jedan kamion, jedna isporuka
        delivery = ConsolidatedDelivery.objects.create(
            hub_company=self.seller,
            buyer_company=self.buyer,
            delivery_number="TEST-CD-001",
            delivery_method="internal",
            vehicle=self.vehicle,
            driver=self.driver,
            delivery_address="Marktstraße 10, Stuttgart",
            recipient_name="Pizzeria Roma",
            delivery_notes="",
            status="collecting",
            requires_cold_chain=True,
            package_count=3,
        )

        # DeliveryStop = jedna stanica na ruti
        stop = DeliveryStop.objects.create(
            route=self.route,
            company=self.buyer,
            stop_order=1,
            stop_type="delivery",
            recipient_name="Pizzeria Roma",
        )

        # Assertions
        self.assertIsNotNone(delivery.pk,
            "GREŠKA: ConsolidatedDelivery nije kreiran u bazi.")
        self.assertEqual(delivery.status, "collecting",
            "GREŠKA: Početni status mora biti 'collecting'.")
        self.assertEqual(stop.route, self.route,
            "GREŠKA: Stop nije vezan za pravu rutu.")
        self.assertEqual(stop.company, self.buyer,
            "GREŠKA: Stop nema pravu tvrtku kupca.")

        print("✅ Kamion (ConsolidatedDelivery) kreiran, stanica (DeliveryStop) vezana za rutu.")

    # ─────────────────────────────────────────────────────────
    # TEST 4.2 — HACCP: Senzor javlja kritičnu temperaturu
    # ─────────────────────────────────────────────────────────
    def test_4_2_haccp_temp_shock(self):
        """
        SCENARIJ: POST /delivery/api/cold-chain/ingest/ s dva očitanja.
        Jedno normalno (3.8°C), jedno kritično (12.5°C > max 8°C).
        Provjera: API prihvata payload, SensorReading zapisi kreirani.
        """
        print("\n--- [TEST 4.2] HACCP Temperaturni šok: API Ingest ---")

        from delivery.models import SensorReading

        payload = {
            "readings": [
                {
                    "zone_id":     self.cold_zone.pk,
                    "temperature": 3.8,
                    "humidity":    65.0,
                },
                {
                    "zone_id":     self.cold_zone.pk,
                    "temperature": 12.5,
                    "humidity":    70.0,
                },
            ]
        }

        response = self.api_client.post(
            "/delivery/api/cold-chain/ingest/",
            data=payload,
            format="json",
            secure=True,   # SECURE_SSL_REDIRECT=True u settings zahtijeva HTTPS
        )

        # API mora odgovoriti s 200 ili 201
        self.assertIn(response.status_code, [200, 201],
            f"GREŠKA: API vratio {response.status_code} — očekivano 200/201. "
            f"Body: {response.data}")

        # U bazi moraju biti 2 nova SensorReading zapisa za tu zonu
        readings = SensorReading.objects.filter(zone=self.cold_zone)
        self.assertEqual(readings.count(), 2,
            f"GREŠKA: Očekivana 2 SensorReading u bazi, pronađeno {readings.count()}.")

        # Provjeri da je kritično očitanje (12.5°C) zaista snimljeno
        critical = readings.filter(temperature=12.5)
        self.assertTrue(critical.exists(),
            "GREŠKA: Kritično očitanje (12.5°C) nije pronađeno u bazi!")

        # Provjeri alarme — zona ima max 8°C, 12.5 je iznad
        above_limit = [r for r in readings if r.temperature > self.cold_zone.target_max_temp]
        self.assertTrue(len(above_limit) > 0,
            "GREŠKA: Niti jedno očitanje nije prepoznato kao iznad limita!")

        print(f"✅ HACCP: API prihvatio 2 očitanja. "
              f"{len(above_limit)} iznad praga ({self.cold_zone.target_max_temp}°C): "
              f"{[r.temperature for r in above_limit]}°C")

    # ─────────────────────────────────────────────────────────
    # TEST 5.1 — Pametni račun: Roba + Dostava + Pfand
    # ─────────────────────────────────────────────────────────
    def test_5_1_smart_invoice_with_pfand(self):
        """
        SCENARIJ: Vozač dostavlja 10 IFCO gajbi, Pizzeria vraća 8.
        Nedostaju 2 gajbe = Pfand dug.
        Provjera: balance=2, invoice_total = 100 + 15 + (2×4) = 123.00 EUR.
        """
        print("\n--- [TEST 5.1] Pametni Račun: Roba + Dostava + Kaucija ---")

        # Kreiraj stop i exchange
        stop = DeliveryStop.objects.create(
            route=self.route,
            company=self.buyer,
            stop_order=2,
            stop_type="delivery",
            recipient_name="Pizzeria Roma",
        )

        exchange = PackagingExchange.objects.create(
            delivery_stop=stop,
            packaging_type="ifco",   # lowercase — kako je definirano u choices
            delivered_qty=10,
            returned_qty=8,
        )

        # balance = delivered - returned = 10 - 8 = 2
        # (izračunava se automatski u save())
        exchange.refresh_from_db()
        self.assertEqual(exchange.balance, 2,
            f"GREŠKA: PackagingExchange.balance trebao biti 2, dobiveno {exchange.balance}.")

        # Financijska kalkulacija
        order_total    = Decimal("100.00")
        delivery_cost  = Decimal("15.00")
        pfand_rate     = Decimal("4.00")
        pfand_total    = Decimal(str(exchange.balance)) * pfand_rate
        invoice_total  = order_total + delivery_cost + pfand_total

        self.assertEqual(pfand_total, Decimal("8.00"),
            f"GREŠKA: Pfand nije točan. Očekivano 8.00, dobiveno {pfand_total}.")
        self.assertEqual(invoice_total, Decimal("123.00"),
            f"GREŠKA: Invoice total nije točan. Očekivano 123.00, dobiveno {invoice_total}.")

        print(f"✅ Pfand balance: {exchange.balance} gajbe × {pfand_rate} EUR = {pfand_total} EUR")
        print(f"✅ Invoice total: {order_total} + {delivery_cost} + {pfand_total} = {invoice_total} EUR")
