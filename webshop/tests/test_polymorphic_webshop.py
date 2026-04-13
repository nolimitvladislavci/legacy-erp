"""
Phase 11: Polymorphic E-commerce — Matrica Loma
Test 11.1: Universal Cart Lock (Race Condition na zadnjem komadu)
Test 11.2: Grosmarkt (Hrana) — HACCP + Volumetrija ambalaze
Test 11.3: Optika — Medicinski atributi (SPH/CYL obavezni)

All tests use the SAME webshop.Product model — zero duplication.
"""
import datetime
import json
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from companies.models import Company
from webshop.models import Product, CartItem

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class UniversalCartLockTests(TransactionTestCase):
    """Test 11.1: Race Condition — zadnji komadi optike"""

    def setUp(self):
        self.company = Company.objects.create(name="Viskovic Omni", oib="12345678901")
        self.buyer1 = User.objects.create_user(username="kupac1", password="test1234")
        self.buyer2 = User.objects.create_user(username="kupac2", password="test1234")
        self.lens = Product.objects.create(
            company=self.company, sku="LENS-001", name="Zeiss Leca -2.00",
            category='OPTICS', price=Decimal("150.00"),
            available_qty=2,
            domain_attrs={"requires_sph": True},
        )

    def test_race_condition_last_items(self):
        """Dva kupca istovremeno traze 2 komada — samo jedan smije proci."""
        results = []
        errors = []

        def buy(username):
            try:
                from django.test import Client
                c = Client()
                c.login(username=username, password="test1234")
                resp = c.post('/webshop/api/cart/add/',
                    json.dumps({
                        'product_id': self.lens.pk,
                        'qty': 2,
                        'attributes': {'sph': '-2.00'}
                    }),
                    content_type='application/json')
                results.append(resp.status_code)
            except ImportError as e:
                errors.append(str(e))
            finally:
                connection.close()

        t1 = threading.Thread(target=buy, args=("kupac1",))
        t2 = threading.Thread(target=buy, args=("kupac2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(results), 2, f"Oba threada moraju zavrsiti. Errors: {errors}")
        self.assertIn(200, results, "Barem jedan kupac MORA uspjeti!")
        self.assertIn(409, results,
            "Drugi kupac MORA dobiti 409 — select_for_update mora sprijeciti dvostruku prodaju!")
        self.lens.refresh_from_db()
        self.assertGreaterEqual(self.lens.available_qty, 0, "Zaliha ne smije biti negativna!")

    def test_sequential_stock_depletion(self):
        """Sekvencijalni: prvi uzima sve, drugi dobiva 409."""
        self.client.login(username="kupac1", password="test1234")
        resp1 = self.client.post('/webshop/api/cart/add/',
            json.dumps({
                'product_id': self.lens.pk, 'qty': 2,
                'attributes': {'sph': '-2.00'}
            }),
            content_type='application/json')
        self.assertEqual(resp1.status_code, 200)

        self.client.login(username="kupac2", password="test1234")
        resp2 = self.client.post('/webshop/api/cart/add/',
            json.dumps({
                'product_id': self.lens.pk, 'qty': 1,
                'attributes': {'sph': '-1.50'}
            }),
            content_type='application/json')
        self.assertEqual(resp2.status_code, 409, "Nema vise zalihe — mora biti 409!")


@override_settings(SECURE_SSL_REDIRECT=False)
class GrosmarktDomainTests(TestCase):
    """Test 11.2: Hrana — HACCP + Volumetrija"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Viskovic Grosmarkt", oib="22233344455")
        cls.user = User.objects.create_user(username="kupac_food", password="test1234")
        cls.expired_cheese = Product.objects.create(
            company=cls.company, sku="SIR-EXP", name="Sir Gouda (istekao)",
            category='FOOD', price=Decimal("5.99"),
            available_qty=50,
            packaging_unit="IFCO_10", packaging_capacity_kg=Decimal("10"),
            expiry_date=timezone.now().date() - datetime.timedelta(days=1),
        )
        cls.fresh_cheese = Product.objects.create(
            company=cls.company, sku="SIR-OK", name="Sir Gouda (svjez)",
            category='FOOD', price=Decimal("5.99"),
            available_qty=50,
            packaging_unit="IFCO_10", packaging_capacity_kg=Decimal("10"),
            expiry_date=timezone.now().date() + datetime.timedelta(days=30),
        )

    def setUp(self):
        self.client.login(username="kupac_food", password="test1234")

    def test_expired_food_blocked(self):
        """Hrana s isteklim rokom MORA biti blokirana (403 HACCP)."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({'product_id': self.expired_cheese.pk, 'qty': 5}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 403,
            "Sustav MORA blokirati prodaju hrane s isteklim rokom!")
        self.assertEqual(resp.json().get('code'), 'HACCP_EXPIRED')

    def test_packaging_overflow_blocked(self):
        """Kolicina premašuje kapacitet ambalaze — 400."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({'product_id': self.fresh_cheese.pk, 'qty': 15}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 400,
            "Sustav MORA blokirati cijepanje veleprodajne ambalaze!")
        self.assertEqual(resp.json().get('code'), 'PACKAGING_OVERFLOW')

    def test_valid_food_order_succeeds(self):
        """Ispravna narudzba hrane (svjeza, unutar kapaciteta) — 200."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({'product_id': self.fresh_cheese.pk, 'qty': 8}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), 'ok')


@override_settings(SECURE_SSL_REDIRECT=False)
class OpticsDomainTests(TestCase):
    """Test 11.3: Optika — Medicinski atributi"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Viskovic Optika", oib="33344455566")
        cls.user = User.objects.create_user(username="kupac_optics", password="test1234")
        cls.lens = Product.objects.create(
            company=cls.company, sku="LENS-ZS1", name="Zeiss SmartLife -1.50",
            category='OPTICS', price=Decimal("220.00"),
            available_qty=10,
            domain_attrs={"requires_sph": True, "requires_cyl": False},
        )

    def setUp(self):
        self.client.login(username="kupac_optics", password="test1234")

    def test_optics_without_sph_rejected(self):
        """Kupnja lece bez SPH dioptrije MORA biti odbijena."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({'product_id': self.lens.pk, 'qty': 1}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 400,
            "API MORA odbiti lecu bez SPH dioptrije!")
        self.assertIn('sph', resp.json().get('error', '').lower())

    def test_optics_with_sph_accepted(self):
        """Ispravna kupnja lece s dioptrijom — 200."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({
                'product_id': self.lens.pk, 'qty': 1,
                'attributes': {'sph': '-1.50', 'cyl': '-0.50'}
            }),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    def test_optics_skips_haccp(self):
        """Optika NE smije biti blokirana HACCP pravilima."""
        resp = self.client.post('/webshop/api/cart/add/',
            json.dumps({
                'product_id': self.lens.pk, 'qty': 1,
                'attributes': {'sph': '-2.00'}
            }),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200,
            "Optika ne smije biti blokirana HACCP logikom!")
