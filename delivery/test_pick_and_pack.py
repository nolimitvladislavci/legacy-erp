"""
delivery/tests/test_pick_and_pack.py — Warehouse safety tests
6.2 Scale Tolerance, 6.3 Anti-Crush, 6.4 Packaging Lock
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class WeightToleranceTest(TestCase):
    """6.2: Block weighing that deviates more than +/-20% from ordered quantity."""

    def test_within_tolerance_passes(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('5.5'), Decimal('5.0'))
        self.assertTrue(ok, 'Weight within 10% should pass')
        self.assertEqual(err, '')

    def test_exact_match_passes(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('5.0'), Decimal('5.0'))
        self.assertTrue(ok)

    def test_at_boundary_passes(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('6.0'), Decimal('5.0'))
        self.assertTrue(ok, '20% deviation is at boundary, should pass')

    def test_over_tolerance_blocked(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('6.25'), Decimal('5.0'))
        self.assertFalse(ok, 'Weight 25% over should be blocked')
        self.assertIn('tolerancija', err.lower())

    def test_under_tolerance_blocked(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('3.5'), Decimal('5.0'))
        self.assertFalse(ok, 'Weight 30% under should be blocked')

    def test_fat_finger_triple_blocked(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('15.25'), Decimal('5.0'))
        self.assertFalse(ok, 'Fat finger 3x should be blocked')

    def test_zero_ordered_passes(self):
        from delivery.warehouse_views import _check_weight_tolerance
        ok, err = _check_weight_tolerance(Decimal('1.0'), Decimal('0'))
        self.assertTrue(ok, 'Zero ordered should not crash')


class AntiCrushTest(TestCase):
    """6.3: Heavy items cannot go into rollwagen with fragile items."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from marketplace.models import MarketplaceProduct, MarketplaceCategory

        cls.company = Company.objects.create(name='Test Warehouse Co', oib='99999999901')
        cls.buyer = Company.objects.create(name='Test Buyer Co', oib='99999999911')
        cls.user = User.objects.create_user(username='packer1', password='test123')

        cat = MarketplaceCategory.objects.create(name='Test Cat', slug='test-cat')

        cls.salad = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name='Salata', slug='test-salata',
            unit_price=Decimal('2.50'),
            is_fragile=True, is_heavy=False, category=cat,
        )
        cls.potatoes = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name='Krumpir 25kg', slug='test-krumpir-25kg',
            unit_price=Decimal('1.20'),
            is_fragile=False, is_heavy=True, category=cat,
        )
        cls.milk = MarketplaceProduct.objects.create(
            seller_company=cls.company,
            name='Mlijeko', slug='test-mlijeko',
            unit_price=Decimal('1.50'),
            is_fragile=False, is_heavy=False, category=cat,
        )

    def _make_order_with_rollwagen(self, qr_code, packed_product=None):
        from marketplace.models import MarketplaceOrder, MarketplaceOrderItem
        from delivery.models import Rollwagen, ConsolidatedDelivery

        order = MarketplaceOrder.objects.create(
            buyer_company=self.buyer,
            status='confirmed',
        )
        if packed_product:
            MarketplaceOrderItem.objects.create(
                order=order,
                product=packed_product,
                seller_company=self.company,
                quantity=Decimal('5.0'),
                unit_price=packed_product.unit_price,
                total=Decimal('12.50'),
                packed_at=timezone.now(),
                packed_by=self.user,
            )

        cd = ConsolidatedDelivery.objects.create(
            hub_company=self.company,
            buyer_company=self.buyer,
        )
        rw = Rollwagen.objects.create(
            consolidated_delivery=cd,
            qr_code=qr_code,
            bound_order=order,
        )
        return order, rw

    def test_heavy_on_fragile_blocked(self):
        from delivery.warehouse_views import _check_anti_crush
        order, rw = self._make_order_with_rollwagen('RW-CRUSH-TEST', self.salad)
        ok, err = _check_anti_crush(rw, self.potatoes)
        self.assertFalse(ok, 'Heavy on fragile should be blocked')
        self.assertIn('ANTI-CRUSH', err)

    def test_light_on_fragile_allowed(self):
        from delivery.warehouse_views import _check_anti_crush
        order, rw = self._make_order_with_rollwagen('RW-LIGHT-TEST', self.salad)
        ok, err = _check_anti_crush(rw, self.milk)
        self.assertTrue(ok, 'Non-heavy item on fragile should be allowed')

    def test_heavy_on_empty_rollwagen_allowed(self):
        from delivery.warehouse_views import _check_anti_crush
        from delivery.models import Rollwagen, ConsolidatedDelivery

        cd = ConsolidatedDelivery.objects.create(
            hub_company=self.company,
            buyer_company=self.buyer,
        )
        rw = Rollwagen.objects.create(
            consolidated_delivery=cd,
            qr_code='RW-EMPTY-TEST',
            bound_order=None,
        )
        ok, err = _check_anti_crush(rw, self.potatoes)
        self.assertTrue(ok, 'Heavy on empty rollwagen should be allowed')


class PackagingLockTest(TestCase):
    """6.4: Cannot dispatch order without rollwagen/packaging binding."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        cls.company = Company.objects.create(name='Lock Test Co', oib='99999999902')
        cls.buyer = Company.objects.create(name='Lock Buyer Co', oib='99999999912')
        cls.user = User.objects.create_user(username='driver1', password='test123')

    def test_order_without_rollwagen_has_no_packaging(self):
        from marketplace.models import MarketplaceOrder
        from delivery.models import Rollwagen

        order = MarketplaceOrder.objects.create(
            buyer_company=self.buyer, status='confirmed',
        )
        has_rollwagen = Rollwagen.objects.filter(bound_order=order).exists()
        self.assertFalse(has_rollwagen, 'Order should have no rollwagen initially')

    def test_order_with_rollwagen_has_packaging(self):
        from marketplace.models import MarketplaceOrder
        from delivery.models import Rollwagen, ConsolidatedDelivery

        order = MarketplaceOrder.objects.create(
            buyer_company=self.buyer, status='confirmed',
        )
        cd = ConsolidatedDelivery.objects.create(
            hub_company=self.company,
            buyer_company=self.buyer,
        )
        Rollwagen.objects.create(
            consolidated_delivery=cd,
            qr_code='RW-PKG-LOCK',
            bound_order=order,
            packaging_count={'ifco': 3},
        )
        has_rollwagen = Rollwagen.objects.filter(bound_order=order).exists()
        self.assertTrue(has_rollwagen, 'Order with bound rollwagen should pass')
