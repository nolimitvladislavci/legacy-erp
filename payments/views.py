import json
import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.company_utils import get_user_company
from .models import Payment, PaymentConfig
from . import services
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


@login_required
def payment_settings(request):
    """Payment gateway configuration page."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    config, _ = PaymentConfig.objects.get_or_create(company=company)

    if request.method == 'POST':
        config.stripe_enabled = request.POST.get('stripe_enabled') == 'on'
        config.stripe_public_key = request.POST.get('stripe_public_key', '').strip()
        config.stripe_secret_key = request.POST.get('stripe_secret_key', '').strip()
        config.stripe_webhook_secret = request.POST.get('stripe_webhook_secret', '').strip()
        config.btcpay_enabled = request.POST.get('btcpay_enabled') == 'on'
        config.btcpay_url = request.POST.get('btcpay_url', '').strip()
        config.btcpay_store_id = request.POST.get('btcpay_store_id', '').strip()
        config.btcpay_api_key = request.POST.get('btcpay_api_key', '').strip()
        config.paypal_enabled = request.POST.get('paypal_enabled') == 'on'
        config.paypal_client_id = request.POST.get('paypal_client_id', '').strip()
        config.paypal_secret = request.POST.get('paypal_secret', '').strip()
        config.paypal_mode = request.POST.get('paypal_mode', 'live').strip()
        config.revolut_enabled = request.POST.get('revolut_enabled') == 'on'
        config.revolut_api_key = request.POST.get('revolut_api_key', '').strip()
        config.revolut_merchant_id = request.POST.get('revolut_merchant_id', '').strip()
        config.revolut_webhook_secret = request.POST.get('revolut_webhook_secret', '').strip()
        config.revolut_mode = request.POST.get('revolut_mode', 'sandbox').strip()
        config.default_currency = request.POST.get('default_currency', 'EUR').strip()
        config.save()
        from django.contrib import messages
        from django.utils.translation import gettext as _
        messages.success(request, _('Postavke placanja spremljene.'))
        return redirect('payments:settings')

    payments_recent = Payment.objects.filter(company=company).order_by('-created_at')[:20]
    return render(request, 'payments/settings.html', {
        'config': config,
        'payments': payments_recent,
    })


@login_required
def payment_list(request):
    """Payment history/transactions."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    payments = Payment.objects.filter(company=company).order_by('-created_at')[:100]
    stats = {
        'total': payments.count(),
        'completed': sum(1 for p in payments if p.status == 'completed'),
        'pending': sum(1 for p in payments if p.status in ('pending', 'processing')),
    }
    return render(request, 'payments/list.html', {
        'payments': payments,
        'stats': stats,
    })


def create_payment_api(request):
    """API endpoint to create a payment from any module (no login for QR)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    company_id = data.get('company_id')
    if not company_id:
        return JsonResponse({'error': 'company_id required'}, status=400)

    from companies.models import Company
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return JsonResponse({'error': 'Company not found'}, status=404)

    method = data.get('method', 'cash')
    amount = data.get('amount')
    if not amount:
        return JsonResponse({'error': 'amount required'}, status=400)

    from decimal import Decimal, InvalidOperation
    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        return JsonResponse({'error': 'Invalid amount'}, status=400)

    base_url = request.build_absolute_uri('/').rstrip('/')
    success_url = data.get('success_url', base_url + '/payments/success/')
    cancel_url = data.get('cancel_url', base_url + '/payments/cancel/')

    payment = services.create_payment(
        company=company,
        source=data.get('source', 'gastro_qr'),
        source_id=data.get('source_id', ''),
        amount=amount,
        method=method,
        customer_email=data.get('customer_email', ''),
        customer_name=data.get('customer_name', ''),
        description=data.get('description', ''),
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=data.get('metadata'),
    )

    return JsonResponse({
        'ok': True,
        'payment_id': str(payment.id),
        'status': payment.status,
        'external_url': payment.external_url,
        'method': payment.method,
    })


def payment_status_api(request, payment_id):
    """Check payment status (for polling from frontend)."""
    try:
        payment = Payment.objects.get(pk=payment_id)
    except Payment.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    # If BTCPay and still processing, check live status
    if payment.method == 'btcpay' and payment.status == 'processing':
        services.check_btcpay_status(payment)
    elif payment.method == 'revolut' and payment.status == 'processing':
        services.check_revolut_status(payment)

    return JsonResponse({
        'ok': True,
        'status': payment.status,
        'method': payment.method,
        'amount': str(payment.amount),
        'completed': payment.is_completed,
        'crypto_currency': payment.crypto_currency,
        'crypto_amount': payment.crypto_amount,
    })


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe webhook endpoint."""
    import stripe
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    # Try to find the right config
    try:
        event_data = json.loads(payload)
        session_data = event_data.get('data', {}).get('object', {})
        payment_id = session_data.get('metadata', {}).get('payment_id', '')

        if payment_id:
            payment = Payment.objects.get(pk=payment_id)
            config = services.get_config(payment.company)
        else:
            logger.warning("Stripe webhook: no payment_id in metadata")
            return HttpResponse(status=200)

        # Verify signature
        if config.stripe_webhook_secret:
            stripe.api_key = config.stripe_secret_key
            event = stripe.Webhook.construct_event(payload, sig_header, config.stripe_webhook_secret)
        else:
            event = event_data

        event_type = event.get('type', '') if isinstance(event, dict) else event.type

        if event_type == 'checkout.session.completed':
            session = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event.data.object
            pid = session.get('metadata', {}).get('payment_id') if isinstance(session, dict) else session.metadata.get('payment_id')
            if pid:
                p = Payment.objects.get(pk=pid)
                pi = session.get('payment_intent') if isinstance(session, dict) else session.payment_intent
                services.complete_payment(p, {
                    'stripe_session_id': session.get('id') if isinstance(session, dict) else session.id,
                    'payment_intent': pi,
                })
                # Update source (e.g., mark gastro order as paid)
                _on_payment_completed(p)

    except Payment.DoesNotExist:
        logger.warning("Stripe webhook: payment not found")
    except ObjectDoesNotExist as e:
        logger.error("Stripe webhook error: %s", e, exc_info=True)

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def btcpay_webhook(request):
    """BTCPay Server webhook/IPN endpoint."""
    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoiceId', '')
        if not invoice_id:
            return HttpResponse(status=200)

        payment = Payment.objects.filter(external_id=invoice_id).first()
        if not payment:
            logger.warning("BTCPay webhook: payment not found for invoice %s", invoice_id)
            return HttpResponse(status=200)

        event_type = data.get('type', '')
        if event_type in ('InvoiceSettled', 'InvoicePaymentSettled'):
            config = services.get_config(payment.company)
            services.check_btcpay_status(payment, config)
            _on_payment_completed(payment)
        elif event_type in ('InvoiceExpired', 'InvoiceInvalid'):
            payment.status = 'failed'
            payment.gateway_data.update({'webhook_event': event_type})
            payment.save(update_fields=['status', 'gateway_data'])

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("BTCPay webhook error: %s", e, exc_info=True)

    return HttpResponse(status=200)


def _on_payment_completed(payment):
    """Callback when payment is completed - update source records."""
    try:
        # Gastro QR (legacy handler)
        if payment.source == 'gastro_qr' and payment.source_id:
            from pos.models import GastroOrder
            order = GastroOrder.objects.filter(pk=int(payment.source_id)).first()
            if order and order.status != 'paid':
                order.status = 'paid'
                order.save(update_fields=['status'])
                logger.info("GastroOrder %s marked as paid via %s", order.pk, payment.method)
        elif payment.source == 'invoice' and payment.source_id:
            from invoicing.models import Invoice
            inv = Invoice.objects.filter(pk=int(payment.source_id)).first()
            if inv:
                inv.status = 'PAID'
                inv.save(update_fields=['status'])

        # Universal handler for all modules (webshop, rental, fitness, etc.)
        from payments.integrations import handle_payment_completed
        handle_payment_completed(payment)

    except (ValueError, TypeError) as e:
        logger.warning("_on_payment_completed error: %s", e)


def payment_success(request):
    """Success redirect page after payment."""
    payment_id = request.GET.get('payment_id', '')
    payment = None
    if payment_id:
        try:
            payment = Payment.objects.get(pk=payment_id)
        except Payment.DoesNotExist:
            pass
    return render(request, 'payments/success.html', {'payment': payment})


def paypal_return(request):
    """PayPal redirects here after approval - capture the payment."""
    payment_id = request.GET.get('payment_id', '')
    token = request.GET.get('token', '')  # PayPal order token

    if payment_id:
        try:
            payment = Payment.objects.get(pk=payment_id)
            if payment.method == 'paypal' and payment.status == 'processing':
                from . import services
                services.capture_paypal(payment)
                _on_payment_completed(payment)
                return render(request, 'payments/success.html', {'payment': payment})
        except Payment.DoesNotExist:
            pass
        except ObjectDoesNotExist as e:
            logger.error("PayPal capture failed: %s", e, exc_info=True)

    return redirect('payments:success')


def payment_cancel(request):
    """Cancel redirect page."""
    payment_id = request.GET.get('payment_id', '')
    payment = None
    if payment_id:
        try:
            payment = Payment.objects.get(pk=payment_id)
            if payment.status == 'processing':
                payment.status = 'cancelled'
                payment.save(update_fields=['status'])
        except Payment.DoesNotExist:
            pass
    return render(request, 'payments/cancel.html', {'payment': payment})


@login_required
def payment_dashboard(request):
    """Payment analytics dashboard."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from django.db.models import Sum, Count, Q
    from datetime import timedelta
    from django.utils import timezone

    now = timezone.now()
    last_30 = now - timedelta(days=30)

    payments = Payment.objects.filter(company=company)
    stats = payments.filter(created_at__gte=last_30).aggregate(
        total_amount=Sum('amount', filter=Q(status='completed')),
        total_count=Count('id', filter=Q(status='completed')),
        stripe_amount=Sum('amount', filter=Q(status='completed', method='stripe')),
        stripe_count=Count('id', filter=Q(status='completed', method='stripe')),
        paypal_amount=Sum('amount', filter=Q(status='completed', method='paypal')),
        paypal_count=Count('id', filter=Q(status='completed', method='paypal')),
        btcpay_amount=Sum('amount', filter=Q(status='completed', method='btcpay')),
        btcpay_count=Count('id', filter=Q(status='completed', method='btcpay')),
        revolut_amount=Sum('amount', filter=Q(status='completed', method='revolut')),
        revolut_count=Count('id', filter=Q(status='completed', method='revolut')),
        cash_amount=Sum('amount', filter=Q(status='completed', method='cash')),
        cash_count=Count('id', filter=Q(status='completed', method='cash')),
        pending_count=Count('id', filter=Q(status__in=('pending', 'processing'))),
        failed_count=Count('id', filter=Q(status='failed')),
    )

    recent = payments.order_by('-created_at')[:50]
    config, _ = PaymentConfig.objects.get_or_create(company=company)

    return render(request, 'payments/dashboard.html', {
        'stats': stats,
        'recent': recent,
        'config': config,
    })
