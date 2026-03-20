"""Tests for marketplace views."""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import Company
from marketplace.models import MarketplaceCategory, MarketplaceProduct


def _company(name, oib):
    return Company.objects.create(
        name=name, oib=oib, address='Test 1', city='Zagreb',
        country='HR', currency='EUR', is_platform_owner=True,
    )


def _user(username, company):
    u = User.objects.create_user(username=username, password='pass')
    p, _ = UserProfile.objects.get_or_create(user=u)
    p.company = company
    p.save()
    return u


class CatalogViewTest(TestCase):
    def setUp(self):
        self.company = _company('OPG Cat', '10000000001')
        self.user = _user('catuser1', self.company)
        self.cat = MarketplaceCategory.objects.create(
            name='Voće', slug='voce-v', is_active=True,
        )
        MarketplaceProduct.objects.create(
            name='Jabuka', slug='jabuka-v',
            seller_company=self.company, category=self.cat,
            unit_price=Decimal('2.50'), unit='kg',
            available_qty=100, is_available=True,
        )
        self.client = Client()

    def test_requires_login(self):
        resp = self.client.get('/marketplace/', secure=True)
        self.assertEqual(resp.status_code, 302)

    def test_catalog_loads(self):
        self.client.force_login(self.user)
        resp = self.client.get('/marketplace/', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jabuka')

    def test_search(self):
        self.client.force_login(self.user)
        resp = self.client.get('/marketplace/?q=Jabuka', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jabuka')

    def test_filter_by_category(self):
        self.client.force_login(self.user)
        resp = self.client.get('/marketplace/?category=voce-v', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jabuka')


class ProductDetailViewTest(TestCase):
    def setUp(self):
        self.company = _company('OPG Detail', '10000000002')
        self.user = _user('detuser1', self.company)
        self.cat = MarketplaceCategory.objects.create(
            name='Povrće', slug='povrce-d',
        )
        MarketplaceProduct.objects.create(
            name='Rajčica', slug='rajcica-d',
            seller_company=self.company, category=self.cat,
            unit_price=Decimal('3.00'), unit='kg',
            available_qty=50, is_available=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_detail_200(self):
        resp = self.client.get('/marketplace/product/rajcica-d/', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rajčica')

    def test_detail_404(self):
        resp = self.client.get('/marketplace/product/ne-postoji/', secure=True)
        self.assertEqual(resp.status_code, 404)


class CartViewTest(TestCase):
    def setUp(self):
        self.company = _company('OPG Cart', '10000000003')
        self.user = _user('cartuser1', self.company)
        self.cat = MarketplaceCategory.objects.create(
            name='Voće', slug='voce-c2',
        )
        self.product = MarketplaceProduct.objects.create(
            name='Kruška', slug='kruska-c',
            seller_company=self.company, category=self.cat,
            unit_price=Decimal('3.50'), unit='kg',
            available_qty=50, is_available=True,
            min_order_qty=Decimal('1'),
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_cart_view_200(self):
        resp = self.client.get('/marketplace/cart/', secure=True)
        self.assertEqual(resp.status_code, 200)

    def test_add_to_cart(self):
        resp = self.client.post('/marketplace/cart/add/', {
            'product_id': self.product.pk, 'qty': 5,
        }, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_cart_add_get_rejected(self):
        resp = self.client.get('/marketplace/cart/add/', secure=True)
        self.assertEqual(resp.status_code, 405)
