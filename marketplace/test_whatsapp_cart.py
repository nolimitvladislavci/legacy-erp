"""
Tests for WhatsApp Concierge — CartSnapshot security scenarios.
Scenario 2.1: Token expiration (403 after 60min)
Scenario 2.2: Race condition / cart_hash mismatch (409)
Scenario 2.3: Meta API timeout (fallback, no crash)
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from companies.models import Company
from marketplace.models import (
    CartSnapshot,
    MarketplaceCategory,
    MarketplaceProduct,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class CartSnapshotSecurityTests(TestCase):
    """TDD: All 3 WhatsApp security scenarios."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Pizzeria Roma', address='Vukovarska 1', country='HR',
        )
        self.user = User.objects.create_user('dispatcher', password='test123')

        # Create profile link
        from accounts.models import UserProfile
        try:
            profile = self.user.profile
            profile.company = self.company
            profile.save()
        except (IntegrityError, DatabaseError):
            UserProfile.objects.create(user=self.user, company=self.company)

        # Subscription
        try:
            from accounts.models import CompanySubscription
            CompanySubscription.objects.create(
                company=self.company, plan='professional', is_active=True,
                modules_override=['marketplace'],
            )
        except (IntegrityError, DatabaseError):
            pass

        # Product
        self.category = MarketplaceCategory.objects.create(name='Voce', slug='voce')
        self.product = MarketplaceProduct.objects.create(
            name='Rajcica', slug='rajcica',
            seller_company=self.company, category=self.category,
            unit_price=Decimal('3.50'), unit='kg',
            is_available=True,
        )

        # Cart snapshot data
        self.cart_data = {
            'items': [
                {'product_id': self.product.pk, 'name': 'Rajcica',
                 'qty': 5.0, 'unit_price': '3.50', 'line_total': '17.50', 'unit': 'kg'},
            ],
            'total': '17.50',
        }
        self.cart_hash = CartSnapshot.compute_hash(self.cart_data)

    def _create_snapshot(self, expires_delta=timedelta(minutes=60)):
        return CartSnapshot.objects.create(
            token=CartSnapshot.generate_token(),
            company=self.company,
            cart_data=self.cart_data,
            cart_hash=self.cart_hash,
            total=Decimal('17.50'),
            expires_at=timezone.now() + expires_delta,
            created_by=self.user,
        )

    def test_scenario_2_1_token_expired(self):
        """
        SCENARIJ 2.1: Link istekao — kupac pokusava otvoriti link nakon 3 sata.
        Ocekivanje: 403 Forbidden.
        """
        print('\n' + '=' * 60)
        print(' [SCENARIJ 2.1] TOKEN EXPIRATION — 403 FORBIDDEN')
        print('=' * 60)

        snapshot = self._create_snapshot(expires_delta=timedelta(minutes=-30))
        self.assertTrue(snapshot.is_expired)

        url = f'/marketplace/checkout/shared/{snapshot.token}/'
        resp = self.client.get(url)

        print(f' -> Token: {snapshot.token[:12]}...')
        print(f' -> Expires at: {snapshot.expires_at}')
        print(f' -> Is expired: {snapshot.is_expired}')
        print(f' -> HTTP status: {resp.status_code}')

        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, 'istekao', status_code=403)
        print(' PASS: Expired link returns 403')

    def test_scenario_2_1_token_valid(self):
        """Valid token should return 200."""
        print('\n' + '=' * 60)
        print(' [SCENARIJ 2.1b] VALID TOKEN — 200 OK')
        print('=' * 60)

        snapshot = self._create_snapshot()
        self.assertFalse(snapshot.is_expired)
        self.assertTrue(snapshot.is_valid)

        url = f'/marketplace/checkout/shared/{snapshot.token}/'
        resp = self.client.get(url)

        print(f' -> HTTP status: {resp.status_code}')
        print(f' -> Is valid: {snapshot.is_valid}')

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rajcica')
        print(' PASS: Valid token shows checkout page')

    def test_scenario_2_2_cart_hash_mismatch(self):
        """
        SCENARIJ 2.2: Race condition — dispatcher changes cart after link sent.
        Ocekivanje: 409 Conflict when hash doesn't match.
        """
        print('\n' + '=' * 60)
        print(' [SCENARIJ 2.2] RACE CONDITION — CART HASH MISMATCH')
        print('=' * 60)

        snapshot = self._create_snapshot()

        # Tamper with cart_data after creation (simulates dispatcher edit)
        snapshot.cart_data['items'][0]['qty'] = 10.0
        snapshot.cart_data['items'][0]['line_total'] = '35.00'
        snapshot.cart_data['total'] = '35.00'
        snapshot.save(update_fields=['cart_data'])
        # Note: cart_hash still has the OLD hash

        url = f'/marketplace/checkout/shared/{snapshot.token}/'

        # POST — try to confirm order with stale hash
        resp = self.client.post(url)

        print(f' -> Original hash: {snapshot.cart_hash[:16]}...')
        print(f' -> Current data hash: {CartSnapshot.compute_hash(snapshot.cart_data)[:16]}...')
        print(f' -> Match: {snapshot.cart_hash == CartSnapshot.compute_hash(snapshot.cart_data)}')
        print(f' -> HTTP status: {resp.status_code}')

        self.assertEqual(resp.status_code, 409)
        self.assertContains(resp, 'promijenilo', status_code=409)
        print(' PASS: Hash mismatch blocks stale payment (409)')

    def test_scenario_2_2_double_submit(self):
        """Double-submit should show 'already used' page."""
        print('\n' + '=' * 60)
        print(' [SCENARIJ 2.2b] DOUBLE SUBMIT — IDEMPOTENT')
        print('=' * 60)

        snapshot = self._create_snapshot()
        url = f'/marketplace/checkout/shared/{snapshot.token}/'

        # First submit — should create order
        resp1 = self.client.post(url)
        snapshot.refresh_from_db()
        self.assertTrue(snapshot.is_used)
        self.assertIsNotNone(snapshot.order)
        print(f' -> First submit: order {snapshot.order.order_number} created')

        # Second submit — should show "already used"
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'vec iskoristen')
        print(' -> Second access: shows "already used" page')
        print(' PASS: Double-submit is idempotent')

    def test_scenario_2_3_whatsapp_api_failure_fallback(self):
        """
        SCENARIJ 2.3: WhatsApp API fails — system doesn't crash, uses fallback.
        """
        print('\n' + '=' * 60)
        print(' [SCENARIJ 2.3] META API TIMEOUT — FALLBACK')
        print('=' * 60)

        from marketplace.notifications import send_cart_link

        snapshot = self._create_snapshot()

        # Mock: WA fails, SMS fails — still returns without crash
        with patch('marketplace.notifications._send_whatsapp') as mock_wa:
            mock_wa.side_effect = Exception('WA API timeout after 10s')

            result = send_cart_link(snapshot, '+385911234567')

            print(' -> WA exception: WA API timeout after 10s')
            print(f' -> Result sent: {result["sent"]}')
            print(f' -> Fallback used: {snapshot.wa_fallback_used}')
            print(' -> Crashed: No')

            snapshot.refresh_from_db()
            self.assertFalse(result['sent'])
            self.assertEqual(snapshot.wa_fallback_used, 'failed')
            print(' PASS: System did NOT crash, fallback recorded')

    def test_snapshot_hash_integrity(self):
        """cart_hash is deterministic and detects any change."""
        print('\n' + '=' * 60)
        print(' [TEST] HASH INTEGRITY')
        print('=' * 60)

        data1 = {'items': [{'id': 1, 'qty': 5}], 'total': '17.50'}
        data2 = {'items': [{'id': 1, 'qty': 5}], 'total': '17.50'}
        data3 = {'items': [{'id': 1, 'qty': 6}], 'total': '21.00'}

        h1 = CartSnapshot.compute_hash(data1)
        h2 = CartSnapshot.compute_hash(data2)
        h3 = CartSnapshot.compute_hash(data3)

        print(f' -> Same data hash match: {h1 == h2}')
        print(f' -> Different data hash match: {h1 == h3}')

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        print(' PASS: Hash is deterministic and detects changes')

    def test_token_uniqueness(self):
        """Generated tokens must be unique."""
        tokens = set(CartSnapshot.generate_token() for _ in range(100))
        self.assertEqual(len(tokens), 100)
        print('\n PASS: 100 generated tokens are all unique')
