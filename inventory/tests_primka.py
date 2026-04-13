"""DIO 7: Inventory tests — article search, GoodsReceiptItem calc, confirm stock, StockMovement type=in"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase

from inventory.models import GoodsReceipt, GoodsReceiptItem, InventoryItem, StockMovement


def _make_company(oib="12345678901"):
    from companies.models import Company

    return Company.objects.create(name="TestCo_" + oib, oib=oib)


def _make_item(company, name="Artikl A", sku="SKU001", qty=10, pp=5, up=9):
    return InventoryItem.objects.create(
        company=company,
        name=name,
        sku=sku,
        quantity=Decimal(str(qty)),
        purchase_price=Decimal(str(pp)),
        unit_price=Decimal(str(up)),
        unit="kom",
    )


def _make_superuser_with_company(company):
    """Create superuser with company — bypasses subscription middleware."""
    from accounts.models import UserProfile

    u = User.objects.create_superuser(username="supertest_inv", password="pass", email="")
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


def _make_user(company):
    from accounts.models import UserProfile

    u = User.objects.create_user(username="user_inv", password="pass")
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


class ArticleSearchAPITest(TestCase):
    """Test GET /pos/api/articles/search/?q= returns correct company items."""

    def setUp(self):
        self.company = _make_company("12345678901")
        # Use superuser to bypass subscription/module middleware
        self.user = _make_superuser_with_company(self.company)
        self.item = _make_item(self.company, name="Testni artikl", sku="TEST-001")
        self.client = Client()
        self.client.force_login(self.user)

    def test_article_search_returns_company_items(self):
        resp = self.client.get("/hr/pos/api/articles/search/?q=Testni", secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("articles", data)
        names = [a["name"] for a in data["articles"]]
        self.assertIn("Testni artikl", names)

    def test_article_search_json_fields(self):
        resp = self.client.get("/hr/pos/api/articles/search/?q=TEST", secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("articles", data)
        if data["articles"]:
            a = data["articles"][0]
            for field in ("id", "name", "sku", "price", "purchase_price", "tax_rate", "unit", "stock_qty"):
                self.assertIn(field, a, f"Field '{field}' missing from article search response")

    def test_article_search_excludes_other_company(self):
        from companies.models import Company

        other = Company.objects.create(name="OtherCo", oib="99999999999")
        _make_item(other, name="Tuđi artikl", sku="OTHER-001")
        resp = self.client.get("/hr/pos/api/articles/search/?q=", secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [a["name"] for a in data["articles"]]
        self.assertNotIn("Tuđi artikl", names)


class GoodsReceiptItemCalculationTest(TestCase):
    def setUp(self):
        self.company = _make_company("22222222222")
        self.user = _make_user(self.company)
        self.item = _make_item(self.company)
        self.receipt = GoodsReceipt.objects.create(
            company=self.company,
            receipt_number="PRIMKA-2026-0001",
            date="2026-03-01",
            created_by=self.user,
            status="draft",
        )

    def test_calculation_cost_price(self):
        ri = GoodsReceiptItem(
            receipt=self.receipt,
            inventory_item=self.item,
            quantity=Decimal("10"),
            purchase_price_unit=Decimal("5.0000"),
            dependent_costs_unit=Decimal("0.5000"),
            margin_percent=Decimal("30"),
            tax_rate=Decimal("25"),
        )
        ri.calculate()
        self.assertEqual(ri.cost_price_unit, Decimal("5.5000"))

    def test_calculation_selling_gross(self):
        ri = GoodsReceiptItem(
            receipt=self.receipt,
            inventory_item=self.item,
            quantity=Decimal("10"),
            purchase_price_unit=Decimal("5.0000"),
            dependent_costs_unit=Decimal("0.5000"),
            margin_percent=Decimal("30"),
            tax_rate=Decimal("25"),
        )
        ri.calculate()
        # cp=5.5, ma=1.65, sn=7.15, vat=1.7875, sg=8.9375
        self.assertEqual(ri.selling_price_net, Decimal("7.1500"))
        self.assertAlmostEqual(float(ri.selling_price_gross), 8.9375, places=3)

    def test_calculation_totals(self):
        ri = GoodsReceiptItem(
            receipt=self.receipt,
            inventory_item=self.item,
            quantity=Decimal("10"),
            purchase_price_unit=Decimal("5.0000"),
            dependent_costs_unit=Decimal("0.5000"),
            margin_percent=Decimal("30"),
            tax_rate=Decimal("25"),
        )
        ri.calculate()
        self.assertEqual(ri.total_cost_price, Decimal("55.00"))  # 5.5 × 10
        self.assertAlmostEqual(float(ri.total_selling_gross), 89.375, places=2)


class GoodsReceiptConfirmUpdatesStockTest(TestCase):
    def setUp(self):
        self.company = _make_company("33333333333")
        self.user = _make_user(self.company)
        self.item = _make_item(self.company, qty=5, pp=5, up=9)
        self.receipt = GoodsReceipt.objects.create(
            company=self.company,
            receipt_number="PRIMKA-2026-0002",
            date="2026-03-01",
            created_by=self.user,
            status="draft",
        )
        GoodsReceiptItem.objects.create(
            receipt=self.receipt,
            inventory_item=self.item,
            quantity=Decimal("10"),
            purchase_price_unit=Decimal("6.0000"),
            margin_percent=Decimal("30"),
            tax_rate=Decimal("25"),
        )

    def test_confirm_increases_stock(self):
        qty_before = self.item.quantity
        self.receipt.confirm()
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, qty_before + Decimal("10"))

    def test_confirm_updates_purchase_price(self):
        self.receipt.confirm()
        self.item.refresh_from_db()
        self.assertEqual(self.item.purchase_price, Decimal("6.00"))

    def test_confirm_sets_status(self):
        self.receipt.confirm()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "confirmed")


class StockMovementTypeInOnConfirmTest(TestCase):
    def setUp(self):
        self.company = _make_company("44444444444")
        self.user = _make_user(self.company)
        self.item = _make_item(self.company)
        self.receipt = GoodsReceipt.objects.create(
            company=self.company,
            receipt_number="PRIMKA-2026-0003",
            date="2026-03-01",
            created_by=self.user,
            status="draft",
        )
        GoodsReceiptItem.objects.create(
            receipt=self.receipt,
            inventory_item=self.item,
            quantity=Decimal("7"),
            purchase_price_unit=Decimal("4.0000"),
            margin_percent=Decimal("25"),
            tax_rate=Decimal("25"),
        )

    def test_stock_movement_created_with_type_in(self):
        before = StockMovement.objects.filter(item=self.item).count()
        self.receipt.confirm()
        after = StockMovement.objects.filter(item=self.item).count()
        self.assertEqual(after, before + 1)
        sm = StockMovement.objects.filter(item=self.item).order_by("-created_at").first()
        self.assertEqual(sm.movement_type, "in")
        self.assertEqual(sm.quantity, Decimal("7"))

    def test_price_change_record_created(self):
        from inventory.models import PriceChange

        before = PriceChange.objects.filter(inventory_item=self.item).count()
        self.receipt.confirm()
        after = PriceChange.objects.filter(inventory_item=self.item).count()
        self.assertEqual(after, before + 1)
