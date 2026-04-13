"""
payments/integrations.py
Bridge functions for connecting Payments gateway to various modules.
Usage: from payments.integrations import pay_webshop_order, pay_rental_booking, pay_fitness_subscription
"""
import logging
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


def pay_webshop_order(order, method='stripe', request=None):
    """Create payment for webshop order. Returns Payment object."""
    from .services import create_payment
    company = order.customer.company if hasattr(order.customer, 'company') else None
    if not company:
        from companies.models import Company
        company = Company.objects.first()

    base_url = request.build_absolute_uri('/').rstrip('/') if request else ''
    payment = create_payment(
        company=company,
        source='webshop',
        source_id=str(order.pk),
        amount=Decimal(str(order.total_amount or 0)),
        method=method,
        customer_email=getattr(order.customer, 'email', ''),
        customer_name=order.customer.name,
        description=f'Webshop narudžba {order.order_number}',
        success_url=base_url + f'/webshop/orders/{order.pk}/',
        cancel_url=base_url + f'/webshop/orders/{order.pk}/',
    )
    return payment


def pay_fitness_subscription(subscription, method='stripe', request=None):
    """Create payment for fitness subscription. Returns Payment object."""
    from .services import create_payment
    member = subscription.member
    plan = subscription.plan

    company = member.company if hasattr(member, 'company') else None
    if not company:
        from companies.models import Company
        company = Company.objects.first()

    base_url = request.build_absolute_uri('/').rstrip('/') if request else ''
    payment = create_payment(
        company=company,
        source='fitness',
        source_id=str(subscription.pk),
        amount=Decimal(str(plan.price or 0)),
        method=method,
        customer_email=member.email or '',
        customer_name=f'{member.first_name} {member.last_name}',
        description=f'Fitness članarina: {plan.name}',
        success_url=base_url + f'/fitness/members/{member.pk}/',
        cancel_url=base_url + f'/fitness/members/{member.pk}/',
    )
    return payment


def pay_appointment(appointment, method='stripe', request=None):
    """Create payment for appointment/booking. Returns Payment object."""
    from .services import create_payment
    company = appointment.company if hasattr(appointment, 'company') else None
    if not company:
        from companies.models import Company
        company = Company.objects.first()

    base_url = request.build_absolute_uri('/').rstrip('/') if request else ''
    amount = Decimal(str(getattr(appointment, 'total_price', 0) or 0))
    if amount <= 0:
        return None

    payment = create_payment(
        company=company,
        source='appointment',
        source_id=str(appointment.pk),
        amount=amount,
        method=method,
        customer_email=getattr(appointment, 'client_email', ''),
        customer_name=getattr(appointment, 'client_name', ''),
        description=f'Termin {appointment}',
        success_url=base_url + '/appointments/',
        cancel_url=base_url + '/appointments/',
    )
    return payment


def handle_payment_completed(payment):
    """
    Webhook handler — when payment is confirmed by gateway.
    Updates source module status based on payment.source.
    """
    source = payment.source
    source_id = payment.source_id

    try:
        if source == 'webshop':
            from webshop.models import Order
            order = Order.objects.get(pk=int(source_id))
            if order.status == 'pending':
                order.status = 'confirmed'
                order.save(update_fields=['status'])
                logger.info('Webshop order %s auto-confirmed after payment', order.order_number)

        elif source == 'rental':
            from rental.models import Booking
            booking = Booking.objects.get(pk=int(source_id))
            booking.payment_status = 'paid'
            booking.save(update_fields=['payment_status'])
            logger.info('Rental booking %s marked paid', booking.booking_number)

        elif source == 'fitness':
            from fitness.models import MemberSubscription
            sub = MemberSubscription.objects.get(pk=int(source_id))
            sub.status = 'active'
            sub.save(update_fields=['status'])
            logger.info('Fitness subscription %s activated', sub.pk)

        elif source == 'appointment':
            from appointments.models import Appointment
            apt = Appointment.objects.get(pk=int(source_id))
            apt.payment_status = 'paid'
            apt.save(update_fields=['payment_status'])
            logger.info('Appointment %s marked paid', apt.pk)

        elif source == 'marketplace':
            from marketplace.models import MarketplaceOrder
            order = MarketplaceOrder.objects.get(pk=int(source_id))
            order.payment_status = 'paid'
            order.save(update_fields=['payment_status'])
            logger.info('Marketplace order %s paid', order.pk)

    except ObjectDoesNotExist:
        logger.warning('Payment completion handler failed: source=%s id=%s', source, source_id, exc_info=True)
