"""
/tmp/test_warehouse_phase6.py
════════════════════════════════════════════════════════════════════
Faza 6 — Matrica Loma: 4 warehouse sigurnosne blokade

Testovi koji moraju proći FAIL → PASS:
  1. FEFO Blokada       — zabrana skeniranja novije šarže
  2. IoT Vaga           — blokada izvan tolerancije ±20%
  3. Anti-Crush         — zabrana teških iznad krhkih
  4. Genesis Scan       — blokada bez IFCO ambalaže
"""

import datetime
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

# ═══════════════════════════════════════════════════════
# PURE FUNCTION TESTOVI (ne trebaju DB)
# ═══════════════════════════════════════════════════════


class Test61_FEFO_Blokada(SimpleTestCase):
    """6.1: Zabrana skeniranja novije sarze ako starija postoji."""

    def _fake_product(self, name):
        class FakeProd:
            pass

        p = FakeProd()
        p.name = name
        return p

    def test_FAIL_novija_sarza_blokirana(self):
        """MORA BITI BLOKIRAN: Skenirana novija sarza dok postoji starija."""
        from delivery.warehouse_safety import _check_fefo

        p = self._fake_product("Jagoda 250g")
        ok, err = _check_fefo(p, scanned_expiry=datetime.date(2025, 6, 1), oldest_available=datetime.date(2025, 3, 1))
        assert not ok, "FAIL — FEFO mora blokirati noviju sarzu!"
        assert "FEFO" in err, "FAIL — Greska mora sadrzati 'FEFO'"
        print("  [PASS] FEFO blokada radi: %s" % err[:60])

    def test_PASS_najstarija_sarza_dozvoljena(self):
        from delivery.warehouse_safety import _check_fefo

        p = self._fake_product("Jagoda 250g")
        ok, err = _check_fefo(p, scanned_expiry=datetime.date(2025, 3, 1), oldest_available=datetime.date(2025, 3, 1))
        assert ok, "FAIL — Najstarija sarza mora biti dozvoljena!"
        print("  [PASS] FEFO dozvoljava najstariju sarzu")

    def test_PASS_nema_starije_sarze(self):
        from delivery.warehouse_safety import _check_fefo

        p = self._fake_product("Jagoda 250g")
        ok, err = _check_fefo(p, scanned_expiry=datetime.date(2025, 6, 1), oldest_available=None)
        assert ok, "FAIL — Bez starije sarze mora biti dozvoljeno!"
        print("  [PASS] FEFO dozvoljava kad nema starije sarze")


class Test62_IoT_Vaga_Tolerancija(SimpleTestCase):
    """6.2: Blokada mjerenja izvan +/-20% tolerancije."""

    def test_FAIL_prekoracenje_blokirano(self):
        """MORA BITI BLOKIRAN: 25% vise od narucenog."""
        from delivery.warehouse_safety import _check_weight_tolerance

        ok, err = _check_weight_tolerance(Decimal("6.25"), Decimal("5.0"))
        assert not ok, "FAIL — Prekoracenje mora biti blokirano!"
        assert "tolerancija" in err.lower(), "FAIL — Greska mora sadrzati 'tolerancija'"
        print("  [PASS] Vaga blokada radi: %s" % err[:60])

    def test_FAIL_premalo_blokirano(self):
        """MORA BITI BLOKIRAN: 30% manje od narucenog."""
        from delivery.warehouse_safety import _check_weight_tolerance

        ok, err = _check_weight_tolerance(Decimal("3.5"), Decimal("5.0"))
        assert not ok, "FAIL — Premalo mora biti blokirano!"
        print("  [PASS] Vaga blokada radi za premalo")

    def test_FAIL_fat_finger_3x_blokiran(self):
        """MORA BITI BLOKIRAN: Fat finger — upisano 3x vise."""
        from delivery.warehouse_safety import _check_weight_tolerance

        ok, err = _check_weight_tolerance(Decimal("15.25"), Decimal("5.0"))
        assert not ok, "FAIL — Fat finger 3x mora biti blokiran!"
        print("  [PASS] Fat finger blokada radi")

    def test_PASS_unutar_tolerancije(self):
        from delivery.warehouse_safety import _check_weight_tolerance

        ok, err = _check_weight_tolerance(Decimal("5.5"), Decimal("5.0"))
        assert ok, "FAIL — 10% unutar tolerancije mora proci!"
        print("  [PASS] Tocno mjerenje prolazi")

    def test_PASS_nulta_kolicina(self):
        from delivery.warehouse_safety import _check_weight_tolerance

        ok, err = _check_weight_tolerance(Decimal("1.0"), Decimal("0"))
        assert ok, "FAIL — Nulta narucena kolicina ne smije crashati!"
        print("  [PASS] Nulta kolicina ne crasha")


# ═══════════════════════════════════════════════════════
# DB TESTOVI (trebaju modele)
# ═══════════════════════════════════════════════════════


class Test63_AntiCrush(TestCase):
    """6.3: Teski artikli ne smiju ici u rollwagen s krhkim."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        from companies.models import Company
        from marketplace.models import MarketplaceCategory, MarketplaceProduct

        User = get_user_model()

        cls.company = Company.objects.create(name="AntiCrush Hub", oib="88888888801")
        cls.buyer = Company.objects.create(name="AntiCrush Buyer", oib="88888888811")
        cls.user = User.objects.create_user(username="crush_packer", password="test")
        cat = MarketplaceCategory.objects.create(name="ACat", slug="acat")
        cls.salata = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name="Salata",
            slug="ac-salata",
            unit_price=Decimal("2.50"),
            is_fragile=True,
            is_heavy=False,
            category=cat,
        )
        cls.krumpir = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name="Krumpir 25kg",
            slug="ac-krumpir",
            unit_price=Decimal("1.20"),
            is_fragile=False,
            is_heavy=True,
            category=cat,
        )
        cls.mlijeko = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name="Mlijeko",
            slug="ac-mlijeko",
            unit_price=Decimal("1.50"),
            is_fragile=False,
            is_heavy=False,
            category=cat,
        )

    def _rollwagen_s_krhkim(self):
        from django.utils import timezone

        from delivery.models import ConsolidatedDelivery, Rollwagen
        from marketplace.models import MarketplaceOrder, MarketplaceOrderItem

        order = MarketplaceOrder.objects.create(buyer_company=self.buyer, status="confirmed")
        MarketplaceOrderItem.objects.create(
            order=order,
            product=self.salata,
            seller_company=self.company,
            quantity=Decimal("2"),
            unit_price=Decimal("2.50"),
            total=Decimal("5.00"),
            packed_at=timezone.now(),
            packed_by=self.user,
        )
        cd = ConsolidatedDelivery.objects.create(hub_company=self.company, buyer_company=self.buyer)
        rw = Rollwagen.objects.create(consolidated_delivery=cd, qr_code="RW-AC-TEST", bound_order=order)
        return rw

    def test_FAIL_teski_iznad_krhkog_blokiran(self):
        """MORA BITI BLOKIRAN: Teski artikl iznad krhkih u rollwagenu."""
        from delivery.warehouse_safety import _check_anti_crush

        rw = self._rollwagen_s_krhkim()
        ok, err = _check_anti_crush(rw, self.krumpir)
        assert not ok, "FAIL — Teski na krhki mora biti blokiran!"
        assert "ANTI-CRUSH" in err, "FAIL — Greska mora sadrzati 'ANTI-CRUSH'"
        print("  [PASS] Anti-crush blokada radi: %s" % err[:60])

    def test_PASS_lagan_na_krhki_dozvoljen(self):
        from delivery.warehouse_safety import _check_anti_crush

        rw = self._rollwagen_s_krhkim()
        ok, err = _check_anti_crush(rw, self.mlijeko)
        assert ok, "FAIL — Lagan artikl na krhki mora biti dozvoljen!"
        print("  [PASS] Lagan artikl prolazi anti-crush provjeru")


class Test64_GenesisScan_IFCO_Lock(TestCase):
    """6.4: Blokada zaključavanja narudzbe bez IFCO ambalaže."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company

        cls.company = Company.objects.create(name="Genesis Hub", oib="77777777701")
        cls.buyer = Company.objects.create(name="Genesis Buyer", oib="77777777711")

    def _rollwagen(self, qr, ifco_count=0):
        from delivery.models import ConsolidatedDelivery, Rollwagen
        from marketplace.models import MarketplaceOrder

        order = MarketplaceOrder.objects.create(buyer_company=self.buyer, status="confirmed")
        cd = ConsolidatedDelivery.objects.create(hub_company=self.company, buyer_company=self.buyer)
        pkg = {"ifco": ifco_count} if ifco_count > 0 else {}
        rw = Rollwagen.objects.create(
            consolidated_delivery=cd,
            qr_code=qr,
            bound_order=order,
            packaging_count=pkg,
        )
        return rw

    def test_FAIL_bez_ifco_blokiran(self):
        """MORA BITI BLOKIRAN: Nema skeniranog IFCO."""
        from delivery.warehouse_safety import _check_genesis_packaging

        rw = self._rollwagen("RW-GEN-NO-IFCO", ifco_count=0)
        ok, err = _check_genesis_packaging(rw, required_ifco_count=1)
        assert not ok, "FAIL — Bez IFCO mora biti blokiran!"
        assert "GENESIS SCAN" in err, "FAIL — Greska mora sadrzati 'GENESIS SCAN'"
        print("  [PASS] Genesis scan blokada radi: %s" % err[:60])

    def test_PASS_s_ifco_dozvoljen(self):
        from delivery.warehouse_safety import _check_genesis_packaging

        rw = self._rollwagen("RW-GEN-WITH-IFCO", ifco_count=2)
        ok, err = _check_genesis_packaging(rw, required_ifco_count=1)
        assert ok, "FAIL — S IFCO mora biti dozvoljen!"
        print("  [PASS] Genesis scan prolazi kad je IFCO skeniran")
