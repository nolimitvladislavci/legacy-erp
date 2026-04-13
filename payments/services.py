"""
Payment gateway service - single interface for Stripe + BTCPay.
Usage from any module:
    from payments.services import create_payment
    payment = create_payment(
        company=company,
        source='gastro_qr',
        source_id=str(order.pk),
        amount=Decimal('25.50'),
        method='stripe',  # or 'btcpay' or 'cash'
        customer_email='guest@example.com',
        description='Narudzba #123 - Stol 5',
        success_url='https://example.com/success/',
        cancel_url='https://example.com/cancel/',
    )
    # payment.external_url -> redirect user here for Stripe/BTCPay
"""
import logging
import requests
from django.utils import timezone
from .models import Payment, PaymentConfig

logger = logging.getLogger(__name__)


def get_config(company):
    """Get or create payment config for company."""
    config, _ = PaymentConfig.objects.get_or_create(company=company)
    return config


def create_payment(company, source, source_id, amount, method,
                   customer_email='', customer_name='', description='',
                   success_url='', cancel_url='', metadata=None):
    """
    Create a payment and initiate gateway flow.
    Returns Payment object with external_url set for redirect-based flows.
    """
    config = get_config(company)
    currency = config.default_currency or 'EUR'

    payment = Payment.objects.create(
        company=company,
        source=source,
        source_id=str(source_id),
        method=method,
        amount=amount,
        currency=currency,
        description=description[:300],
        customer_email=customer_email,
        customer_name=customer_name,
    )

    try:
        if method == 'stripe' and config.stripe_enabled:
            _init_stripe(payment, config, success_url, cancel_url, metadata)
        elif method == 'btcpay' and config.btcpay_enabled:
            _init_btcpay(payment, config, success_url, cancel_url, metadata)
        elif method == 'paypal' and config.paypal_enabled:
            _init_paypal(payment, config, success_url, cancel_url, metadata)
        elif method == 'revolut' and config.revolut_enabled:
            _init_revolut(payment, config, success_url, cancel_url, metadata)
        elif method == 'cash':
            payment.status = 'pending'  # cash = pay later
            payment.save(update_fields=['status'])
        else:
            payment.status = 'failed'
            payment.gateway_data = {'error': f'Method {method} not enabled'}
            payment.save(update_fields=['status', 'gateway_data'])
    except Exception as e:
        logger.error("Payment init failed: %s", e, exc_info=True)
        payment.status = 'failed'
        payment.gateway_data = {'error': str(e)}
        payment.save(update_fields=['status', 'gateway_data'])

    return payment


def _init_stripe(payment, config, success_url, cancel_url, metadata):
    """Create Stripe Checkout Session."""
    import stripe
    stripe.api_key = config.stripe_secret_key

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': payment.currency.lower(),
                'unit_amount': int(payment.amount * 100),  # cents
                'product_data': {
                    'name': payment.description or f'Placanje #{str(payment.id)[:8]}',
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url + '?payment_id=' + str(payment.id),
        cancel_url=cancel_url + '?payment_id=' + str(payment.id),
        customer_email=payment.customer_email or None,
        metadata={
            'payment_id': str(payment.id),
            'source': payment.source,
            'source_id': payment.source_id,
            **(metadata or {}),
        },
    )
    payment.external_id = session.id
    payment.external_url = session.url
    payment.status = 'processing'
    payment.gateway_data = {
        'session_id': session.id,
        'payment_intent': session.payment_intent,
    }
    payment.save(update_fields=['external_id', 'external_url', 'status', 'gateway_data'])


def _init_btcpay(payment, config, success_url, cancel_url, metadata):
    """Create BTCPay Server invoice."""
    url = f'{config.btcpay_url.rstrip("/")}/api/v1/stores/{config.btcpay_store_id}/invoices'
    headers = {
        'Authorization': f'token {config.btcpay_api_key}',
        'Content-Type': 'application/json',
    }
    body = {
        'amount': str(payment.amount),
        'currency': payment.currency,
        'metadata': {
            'payment_id': str(payment.id),
            'source': payment.source,
            'source_id': payment.source_id,
            'orderId': payment.source_id,
            **(metadata or {}),
        },
        'checkout': {
            'redirectURL': success_url + '?payment_id=' + str(payment.id),
            'redirectAutomatically': True,
            'defaultLanguage': 'hr',
        },
        'receipt': {
            'enabled': True,
        },
    }
    if payment.customer_email:
        body['metadata']['buyerEmail'] = payment.customer_email

    resp = requests.post(url, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    payment.external_id = data.get('id', '')
    payment.external_url = data.get('checkoutLink', '')
    payment.status = 'processing'
    payment.gateway_data = {
        'invoice_id': data.get('id'),
        'checkout_link': data.get('checkoutLink'),
        'status': data.get('status'),
    }
    payment.save(update_fields=['external_id', 'external_url', 'status', 'gateway_data'])


def complete_payment(payment, gateway_data=None):
    """Mark payment as completed."""
    payment.status = 'completed'
    payment.completed_at = timezone.now()
    if gateway_data:
        payment.gateway_data.update(gateway_data)
    payment.save(update_fields=['status', 'completed_at', 'gateway_data', 'updated_at'])
    logger.info("Payment %s completed: %s %s", payment.id, payment.amount, payment.currency)
    return payment


def check_btcpay_status(payment, config=None):
    """Poll BTCPay invoice status."""
    if not config:
        config = get_config(payment.company)
    if not payment.external_id:
        return payment.status

    url = f'{config.btcpay_url.rstrip("/")}/api/v1/stores/{config.btcpay_store_id}/invoices/{payment.external_id}'
    headers = {'Authorization': f'token {config.btcpay_api_key}'}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        btc_status = data.get('status', '')

        if btc_status in ('Settled', 'Complete'):
            if payment.status != 'completed':
                # Get crypto details
                crypto_info = data.get('cryptoInfo', [{}])
                if crypto_info:
                    ci = crypto_info[0] if isinstance(crypto_info, list) else crypto_info
                    payment.crypto_currency = ci.get('cryptoCode', '')
                    payment.crypto_amount = ci.get('due', '')
                    payment.crypto_address = ci.get('address', '')
                complete_payment(payment, {'btcpay_status': btc_status, 'raw': data})
        elif btc_status in ('Expired', 'Invalid'):
            payment.status = 'failed'
            payment.gateway_data.update({'btcpay_status': btc_status})
            payment.save(update_fields=['status', 'gateway_data'])
        return btc_status
    except requests.RequestException as e:
        logger.warning("BTCPay status check failed: %s", e)
        return payment.status


def _init_revolut(payment, config, success_url, cancel_url, metadata):
    """Create Revolut payment order via Merchant API."""
    mode = config.revolut_mode or 'sandbox'
    base = (
        'https://merchant.revolut.com/api/1.0'
        if mode == 'production'
        else 'https://sandbox-merchant.revolut.com/api/1.0'
    )

    amount_cents = int(payment.amount * 100)
    description = payment.description[:140] if payment.description else 'Placanje #%s' % str(payment.id)[:8]

    resp = requests.post(
        '%s/orders' % base,
        headers={
            'Authorization': 'Bearer %s' % config.revolut_api_key,
            'Content-Type': 'application/json',
            'Revolut-Api-Version': '2024-09-01',
        },
        json={
            'amount': amount_cents,
            'currency': payment.currency,
            'description': description,
            'merchant_order_ext_ref': 'LC-%s' % str(payment.id)[:12],
            'customer_email': payment.customer_email or '',
        },
        timeout=(5, 15),
    )
    resp.raise_for_status()
    data = resp.json()

    order_id = data.get('id', '')
    checkout_url = data.get('checkout_url', '')
    if not checkout_url:
        checkout_url = 'https://checkout.revolut.com/pay/%s' % order_id

    payment.external_id = order_id
    payment.external_url = checkout_url
    payment.status = 'processing'
    payment.gateway_data = {
        'revolut_order_id': order_id,
        'checkout_url': checkout_url,
        'mode': mode,
    }
    payment.save(update_fields=['external_id', 'external_url', 'status', 'gateway_data'])


def check_revolut_status(payment, config=None):
    """Poll Revolut order status."""
    if not config:
        config = get_config(payment.company)
    if not payment.external_id:
        return payment.status

    mode = config.revolut_mode or 'sandbox'
    base = (
        'https://merchant.revolut.com/api/1.0'
        if mode == 'production'
        else 'https://sandbox-merchant.revolut.com/api/1.0'
    )

    try:
        resp = requests.get(
            '%s/orders/%s' % (base, payment.external_id),
            headers={
                'Authorization': 'Bearer %s' % config.revolut_api_key,
                'Revolut-Api-Version': '2024-09-01',
            },
            timeout=(5, 15),
        )
        if resp.status_code == 200:
            data = resp.json()
            rev_status = data.get('state', '').lower()
            if rev_status == 'completed':
                if payment.status != 'completed':
                    complete_payment(payment, {'revolut_status': rev_status, 'raw': data})
            elif rev_status in ('failed', 'cancelled'):
                payment.status = 'failed'
                payment.gateway_data.update({'revolut_status': rev_status})
                payment.save(update_fields=['status', 'gateway_data'])
            return rev_status
    except requests.RequestException as e:
        logger.warning('Revolut status check failed: %s', e)
    return payment.status


def _get_paypal_token(config):
    """Get PayPal OAuth2 access token."""
    base = 'https://api-m.paypal.com' if config.paypal_mode == 'live' else 'https://api-m.sandbox.paypal.com'
    resp = requests.post(
        f'{base}/v1/oauth2/token',
        auth=(config.paypal_client_id, config.paypal_secret),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['access_token'], base


def _init_paypal(payment, config, success_url, cancel_url, metadata):
    """Create PayPal order."""
    token, base_url = _get_paypal_token(config)
    body = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'reference_id': str(payment.id),
            'description': payment.description[:127] if payment.description else f'Placanje #{str(payment.id)[:8]}',
            'amount': {
                'currency_code': payment.currency,
                'value': str(payment.amount),
            },
            'custom_id': f'{payment.source}:{payment.source_id}',
        }],
        'payment_source': {
            'paypal': {
                'experience_context': {
                    'payment_method_preference': 'IMMEDIATE_PAYMENT_REQUIRED',
                    'landing_page': 'LOGIN',
                    'user_action': 'PAY_NOW',
                    'return_url': success_url + '?payment_id=' + str(payment.id),
                    'cancel_url': cancel_url + '?payment_id=' + str(payment.id),
                }
            }
        },
    }

    resp = requests.post(
        f'{base_url}/v2/checkout/orders',
        json=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'PayPal-Request-Id': str(payment.id),
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # Find approval URL
    approve_url = ''
    for link in data.get('links', []):
        if link.get('rel') == 'payer-action':
            approve_url = link.get('href', '')
            break

    payment.external_id = data.get('id', '')
    payment.external_url = approve_url
    payment.status = 'processing'
    payment.gateway_data = {
        'paypal_order_id': data.get('id'),
        'status': data.get('status'),
    }
    payment.save(update_fields=['external_id', 'external_url', 'status', 'gateway_data'])


def capture_paypal(payment, config=None):
    """Capture an approved PayPal order."""
    if not config:
        config = get_config(payment.company)
    token, base_url = _get_paypal_token(config)

    resp = requests.post(
        f'{base_url}/v2/checkout/orders/{payment.external_id}/capture',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get('status') == 'COMPLETED':
        complete_payment(payment, {'paypal_capture': data})
    return data
