"""Tests for marketplace models."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from companies.models import Company
from marketplace.models import (
    MarketplaceCategory,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceProduct,
)


def _company(name, oib):
    return Company.objects.create(
        name=name, oib=oib, address='Test 1', city='Zagreb',
        country='HR', currency='EUR',
    )


class CategoryModelTest(TestCase):
    def test_str_includes_name(self):
        cat = MarketplaceCategory.objects.create(
            name='Voće', slug='voce-m', icon='🍎',
        )
        self.assertIn('Voće', str(cat))

    def test_parent_child(self):
        parent = MarketplaceCategory.objects.create(
            name='Voće', slug='voce-p', icon='🍎',
        )
        child = MarketplaceCategory.objects.create(
            name='Jagodičasto', slug='jagod', icon='🍓', parent=parent,
        )
        self.assertEqual(child.parent, parent)


class ProductModelTest(TestCase):
    def setUp(self):
        self.seller = _company('OPG Marić', '20000000001')
        self.cat = MarketplaceCategory.objects.create(
            name='Povrće', slug='povrce-m',
        )
        self.product = MarketplaceProduct.objects.create(
            name='Rajčica cherry', slug='rajcica-cherry-m',
            seller_company=self.seller, category=self.cat,
            unit_price=Decimal('4.50'), unit='kg',
            min_order_qty=Decimal('2'), available_qty=Decimal('150'),
            is_available=True, is_organic=True, origin_region='Dalmacija',
        )

    def test_str_contains_name(self):
        self.assertIn('Rajčica', str(self.product))

    def test_price(self):
        self.assertEqual(self.product.unit_price, Decimal('4.50'))

    def test_organic_flag(self):
        self.assertTrue(self.product.is_organic)

    def test_is_in_season_no_dates(self):
        self.assertTrue(self.product.is_in_season)

    def test_available(self):
        self.assertTrue(self.product.is_available)


class OrderModelTest(TestCase):
    def setUp(self):
        self.buyer = _company('Restaurant Plavi', '20000000002')
        self.seller = _company('OPG Kovač', '20000000003')
        self.user = User.objects.create_user(username='buyer_m', password='x')
        self.cat = MarketplaceCategory.objects.create(
            name='Meso', slug='meso-m',
        )
        self.product = MarketplaceProduct.objects.create(
            name='Piletina', slug='piletina-m',
            seller_company=self.seller, category=self.cat,
            unit_price=Decimal('8.00'), unit='kg',
            available_qty=50, is_available=True,
        )
        self.order = MarketplaceOrder.objects.create(
            buyer_company=self.buyer, buyer_user=self.user,
            delivery_address='Ilica 100, Zagreb',
        )
        self.item = MarketplaceOrderItem.objects.create(
            order=self.order, product=self.product,
            seller_company=self.seller,
            quantity=Decimal('10'), unit_price=Decimal('8.00'),
        )

    def test_order_number_auto(self):
        self.assertTrue(self.order.order_number.startswith('MKT-'))

    def test_order_has_items(self):
        self.assertEqual(self.order.items.count(), 1)

    def test_order_item_total(self):
        self.assertEqual(self.item.total, Decimal('80.00'))

    def test_order_status_default(self):
        self.assertEqual(self.order.status, 'pending')

    def test_recalculate(self):
        self.order.recalculate()
        self.assertEqual(self.order.subtotal, Decimal('80.00'))
