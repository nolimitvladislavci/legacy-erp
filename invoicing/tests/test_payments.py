"""
payments/tests/test_payments.py
Service layer i model testovi za payments app.
Pokriva: PaymentConfig CRUD, Payment model logika,
create_payment (cash + gateway), complete_payment, check_btcpay_status.
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from payments.models import Payment, PaymentConfig
from payments.services import (
    get_config, create_payment, complete_payment, check_btcpay_status,
)


def _company(oib='98765432100', name='Pay Test d.o.o.'):
    return Company.objects.create(name=name, oib=oib)


# ─────────────────────────────────────────────────────────────
# PaymentConfig
# ─────────────────────────────────────────────────────────────
class TestPaymentConfig(TestCase):

    def setUp(self):
        self.company = _company()

    def test_get_config_creates_on_first_call(self):
        """get_config() kreira config ako ne postoji."""
        config = get_config(self.company)
        self.assertIsNotNone(config.pk)
        self.assertEqual(config.company, self.company)

    def test_get_config_idempotent(self):
        """Drugi poziv vraća isti objekt."""
        c1 = get_config(self.company)
        c2 = get_config(self.company)
        self.assertEqual(c1.pk, c2.pk)

    def test_default_currency_eur(self):
        config = get_config(self.company)
        self.assertEqual(config.default_currency, 'EUR')

    def test_all_gateways_disabled_by_default(self):
        config = get_config(self.company)
        self.assertFalse(config.stripe_enabled)
        self.assertFalse(config.btcpay_enabled)
        self.assertFalse(config.paypal_enabled)

    def test_str_shows_gotovina_when_none_enabled(self):
        config = get_config(self.company)
        self.assertIn('Samo gotovina', str(config))

    def test_str_shows_stripe_when_enabled(self):
        config = get_config(self.company)
        config.stripe_enabled = True
        config.save()
        self.assertIn('Stripe', str(config))

    def test_str_shows_multiple_gateways(self):
        config = get_config(self.company)
        config.stripe_enabled = True
        config.btcpay_enabled = True
        config.save()
        s = str(config)
        self.assertIn('Stripe', s)
        self.assertIn('BTCPay', s)


# ─────────────────────────────────────────────────────────────
# Payment model
# ─────────────────────────────────────────────────────────────
class TestPaymentModel(TestCase):

    def setUp(self):
        self.company = _company('11223344556', 'Model Co')

    def _payment(self, status='pending', method='cash', amount=Decimal('50.00')):
        return Payment.objects.create(
            company=self.company,
            source='invoice',
            source_id='123',
            method=method,
            status=status,
            amount=amount,
        )

    def test_payment_pk_is_uuid(self):
        p = self._payment()
        self.assertIsInstance(p.pk, uuid.UUID)

    def test_is_completed_true(self):
        p = self._payment(status='completed')
        self.assertTrue(p.is_completed)

    def test_is_completed_false_for_pending(self):
        p = self._payment(status='pending')
        self.assertFalse(p.is_completed)

    def test_is_pending_true_for_processing(self):
        p = self._payment(status='processing')
        self.assertTrue(p.is_pending)

    def test_is_pending_false_for_completed(self):
        p = self._payment(status='completed')
        self.assertFalse(p.is_pending)

    def test_str_contains_amount(self):
        p = self._payment(amount=Decimal('99.99'))
        self.assertIn('99.99', str(p))

    def test_ordering_newest_first(self):
        p1 = self._payment()
        p2 = self._payment()
        qs = Payment.objects.filter(company=self.company)
        self.assertEqual(qs.first().pk, p2.pk)

    def test_gateway_data_default_empty_dict(self):
        p = self._payment()
        self.assertEqual(p.gateway_data, {})

    def test_failed_status_property(self):
        p = self._payment(status='failed')
        self.assertFalse(p.is_completed)
        self.assertFalse(p.is_pending)


# ─────────────────────────────────────────────────────────────
# create_payment — cash
# ─────────────────────────────────────────────────────────────
class TestCreatePaymentCash(TestCase):

    def setUp(self):
        self.company = _company('22334455667', 'Cash Co')

    def test_cash_payment_created(self):
        p = create_payment(
            company=self.company,
            source='invoice',
            source_id='42',
            amount=Decimal('100.00'),
            method='cash',
        )
        self.assertIsNotNone(p.pk)
        self.assertEqual(p.method, 'cash')

    def test_cash_status_is_pending(self):
        p = create_payment(
            company=self.company, source='pos', source_id='1',
            amount=Decimal('20.00'), method='cash',
        )
        self.assertEqual(p.status, 'pending')

    def test_cash_no_external_url(self):
        p = create_payment(
            company=self.company, source='pos', source_id='1',
            amount=Decimal('20.00'), method='cash',
        )
        self.assertEqual(p.external_url, '')

    def test_cash_stores_customer_email(self):
        p = create_payment(
            company=self.company, source='invoice', source_id='5',
            amount=Decimal('50.00'), method='cash',
            customer_email='klijent@example.com',
        )
        self.assertEqual(p.customer_email, 'klijent@example.com')

    def test_cash_stores_description(self):
        p = create_payment(
            company=self.company, source='invoice', source_id='7',
            amount=Decimal('75.00'), method='cash',
            description='Plaćanje računa R-2026-001',
        )
        self.assertIn('R-2026-001', p.description)

    def test_disabled_gateway_sets_failed(self):
        """Stripe nije omogućen → status failed."""
        p = create_payment(
            company=self.company, source='invoice', source_id='8',
            amount=Decimal('30.00'), method='stripe',
        )
        self.assertEqual(p.status, 'failed')
        self.assertIn('not enabled', p.gateway_data.get('error', ''))

    def test_currency_comes_from_config(self):
        config = get_config(self.company)
        config.default_currency = 'USD'
        config.save()
        p = create_payment(
            company=self.company, source='pos', source_id='9',
            amount=Decimal('10.00'), method='cash',
        )
        self.assertEqual(p.currency, 'USD')

    def test_source_id_stored_as_string(self):
        p = create_payment(
            company=self.company, source='invoice', source_id=999,
            amount=Decimal('1.00'), method='cash',
        )
        self.assertEqual(p.source_id, '999')

    def test_description_truncated_at_300(self):
        long_desc = 'A' * 400
        p = create_payment(
            company=self.company, source='pos', source_id='x',
            amount=Decimal('1.00'), method='cash',
            description=long_desc,
        )
        self.assertLessEqual(len(p.description), 300)


# ─────────────────────────────────────────────────────────────
# create_payment — Stripe mock
# ─────────────────────────────────────────────────────────────
class TestCreatePaymentStripe(TestCase):

    def setUp(self):
        self.company = _company('33445566778', 'Stripe Co')
        config = get_config(self.company)
        config.stripe_enabled = True
        config.stripe_secret_key = 'sk_test_fake'
        config.save()

    @patch('payments.services._init_stripe')
    def test_stripe_payment_sets_processing(self, mock_init_stripe):
        """Mock _init_stripe → payment dobiva processing status."""
        def fake_stripe(payment, config, su, cu, md):
            payment.status = 'processing'
            payment.external_id = 'cs_test_abc'
            payment.external_url = 'https://checkout.stripe.com/pay/cs_test_abc'
            payment.gateway_data = {'session_id': 'cs_test_abc'}
            payment.save(update_fields=['status', 'external_id', 'external_url', 'gateway_data'])
        mock_init_stripe.side_effect = fake_stripe

        p = create_payment(
            company=self.company, source='invoice', source_id='10',
            amount=Decimal('200.00'), method='stripe',
            success_url='https://example.com/success/',
            cancel_url='https://example.com/cancel/',
        )
        p.refresh_from_db()
        self.assertEqual(p.status, 'processing')
        self.assertEqual(p.external_url, 'https://checkout.stripe.com/pay/cs_test_abc')
        self.assertEqual(p.external_id, 'cs_test_abc')

    @patch('payments.services._init_stripe')
    def test_stripe_gateway_data_stored(self, mock_init):
        def fake_init(payment, config, success_url, cancel_url, metadata):
            payment.status = 'processing'
            payment.external_id = 'cs_test_xyz'
            payment.external_url = 'https://checkout.stripe.com/pay/cs_test_xyz'
            payment.gateway_data = {'session_id': 'cs_test_xyz'}
            payment.save()
        mock_init.side_effect = fake_init

        p = create_payment(
            company=self.company, source='invoice', source_id='11',
            amount=Decimal('50.00'), method='stripe',
        )
        self.assertIn('session_id', p.gateway_data)

    @patch('payments.services._init_stripe')
    def test_stripe_exception_sets_failed(self, mock_init):
        mock_init.side_effect = Exception('Stripe API down')

        p = create_payment(
            company=self.company, source='invoice', source_id='12',
            amount=Decimal('50.00'), method='stripe',
        )
        self.assertEqual(p.status, 'failed')
        self.assertIn('Stripe API down', p.gateway_data.get('error', ''))


# ─────────────────────────────────────────────────────────────
# complete_payment
# ─────────────────────────────────────────────────────────────
class TestCompletePayment(TestCase):

    def setUp(self):
        self.company = _company('44556677889', 'Complete Co')

    def _make(self, status='processing'):
        return Payment.objects.create(
            company=self.company, source='invoice', source_id='1',
            method='cash', status=status, amount=Decimal('100.00'),
        )

    def test_complete_sets_status(self):
        p = self._make()
        complete_payment(p)
        p.refresh_from_db()
        self.assertEqual(p.status, 'completed')

    def test_complete_sets_completed_at(self):
        p = self._make()
        complete_payment(p)
        p.refresh_from_db()
        self.assertIsNotNone(p.completed_at)

    def test_complete_merges_gateway_data(self):
        p = self._make()
        p.gateway_data = {'existing': 'value'}
        p.save()
        complete_payment(p, gateway_data={'new_key': 'new_val'})
        p.refresh_from_db()
        self.assertEqual(p.gateway_data.get('existing'), 'value')
        self.assertEqual(p.gateway_data.get('new_key'), 'new_val')

    def test_complete_returns_payment(self):
        p = self._make()
        result = complete_payment(p)
        self.assertEqual(result.pk, p.pk)

    def test_complete_sets_is_completed_true(self):
        p = self._make()
        complete_payment(p)
        self.assertTrue(p.is_completed)


# ─────────────────────────────────────────────────────────────
# check_btcpay_status
# ─────────────────────────────────────────────────────────────
class TestCheckBtcpayStatus(TestCase):

    def setUp(self):
        self.company = _company('55667788990', 'BTC Co')
        self.config = get_config(self.company)
        self.config.btcpay_enabled = True
        self.config.btcpay_url = 'https://btcpay.example.com'
        self.config.btcpay_store_id = 'store123'
        self.config.btcpay_api_key = 'api_key_test'
        self.config.save()

    def _payment(self, external_id='btcpay_inv_1'):
        return Payment.objects.create(
            company=self.company, source='invoice', source_id='20',
            method='btcpay', status='processing', amount=Decimal('0.005'),
            external_id=external_id,
        )

    def test_no_external_id_returns_current_status(self):
        p = Payment.objects.create(
            company=self.company, source='invoice', source_id='21',
            method='btcpay', status='processing', amount=Decimal('1.00'),
            external_id='',
        )
        result = check_btcpay_status(p, config=self.config)
        self.assertEqual(result, 'processing')

    @patch('payments.services.requests.get')
    def test_settled_status_completes_payment(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'status': 'Settled',
            'cryptoInfo': [{'cryptoCode': 'BTC', 'due': '0.0001', 'address': '1A2B3C'}],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        p = self._payment()
        result = check_btcpay_status(p, config=self.config)
        p.refresh_from_db()
        self.assertEqual(p.status, 'completed')
        self.assertEqual(result, 'Settled')

    @patch('payments.services.requests.get')
    def test_expired_status_sets_failed(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'Expired'}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        p = self._payment('btcpay_inv_2')
        check_btcpay_status(p, config=self.config)
        p.refresh_from_db()
        self.assertEqual(p.status, 'failed')

    @patch('payments.services.requests.get')
    def test_network_error_returns_current_status(self, mock_get):
        mock_get.side_effect = Exception('Connection timeout')
        p = self._payment('btcpay_inv_3')
        result = check_btcpay_status(p, config=self.config)
        self.assertEqual(result, 'processing')  # nema promjene

    @patch('payments.services.requests.get')
    def test_already_completed_not_completed_again(self, mock_get):
        """Ako je već completed, ne poziva complete_payment opet."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'Settled', 'cryptoInfo': []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        p = self._payment('btcpay_inv_4')
        p.status = 'completed'
        p.completed_at = timezone.now()
        p.save()

        check_btcpay_status(p, config=self.config)
        p.refresh_from_db()
        # completed_at se ne mijenja
        self.assertEqual(p.status, 'completed')


# ─────────────────────────────────────────────────────────────
# Integracija: create → complete flow
# ─────────────────────────────────────────────────────────────
class TestPaymentLifecycle(TestCase):

    def setUp(self):
        self.company = _company('66778899001', 'Lifecycle Co')

    def test_full_cash_lifecycle(self):
        """Kreiraj → dovrši → provjeri."""
        p = create_payment(
            company=self.company, source='invoice', source_id='99',
            amount=Decimal('250.00'), method='cash',
            description='Test faktura',
        )
        self.assertEqual(p.status, 'pending')
        self.assertFalse(p.is_completed)

        complete_payment(p)
        p.refresh_from_db()
        self.assertTrue(p.is_completed)
        self.assertIsNotNone(p.completed_at)

    def test_multiple_sources(self):
        """Različiti source tipovi mogu koegzistirati."""
        sources = ['invoice', 'pos', 'gastro_qr', 'webshop', 'rental', 'booking']
        for i, src in enumerate(sources):
            create_payment(
                company=self.company, source=src, source_id=str(i),
                amount=Decimal('10.00'), method='cash',
            )
        count = Payment.objects.filter(company=self.company).count()
        self.assertEqual(count, len(sources))

    def test_refunded_status(self):
        p = create_payment(
            company=self.company, source='pos', source_id='77',
            amount=Decimal('100.00'), method='cash',
        )
        p.status = 'refunded'
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.status, 'refunded')
        self.assertFalse(p.is_completed)
        self.assertFalse(p.is_pending)
