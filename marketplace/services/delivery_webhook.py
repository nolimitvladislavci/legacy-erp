"""
marketplace/services/delivery_webhook.py — Auto-create DeliveryStops from Marketplace orders.

Problem: Roba je prodana na Marketplaceu, ali nitko nije javio vozacu hladnjace
da mora stati na OPG Kovacevic.

Rjesenje: Kad se MarketplaceOrder potvrdi (status='confirmed'), ovaj servis
automatski kreira DeliveryRoute + DeliveryStop za svakog sellera i kupca.

Flow:
  MarketplaceOrder(confirmed) → create_delivery_stops()
    → Pickup stop per SellerSubOrder (OPG address)
    → Delivery stop (buyer address)
    → WhatsApp notification to driver

Trigger: Signal na MarketplaceOrder.save() ili poziv iz checkout viewa.
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('delivery')


class DeliveryWebhookError(Exception):
    pass


@transaction.atomic
def create_delivery_stops(order_id, driver_user=None):
    """
    Kreira delivery rutu i stopove za potvrdjenu Marketplace narudzbu.

    Args:
        order_id: MarketplaceOrder.pk
        driver_user: Optional User — assigned driver

    Returns:
        dict s route_id, stops_count, pickup_count, delivery_count
    """
    from marketplace.models import MarketplaceOrder, SellerSubOrder
    from delivery.models import DeliveryRoute, DeliveryStop, Vehicle

    order = MarketplaceOrder.objects.select_related(
        'buyer_company'
    ).prefetch_related(
        'sub_orders__seller_company'
    ).get(pk=order_id)

    if order.status not in ('confirmed', 'collecting'):
        raise DeliveryWebhookError(
            'Order %s nije potvrdjen (status: %s). Delivery se kreira tek nakon potvrde.' % (
                order.order_number, order.status
            )
        )

    # Check if route already exists
    existing = DeliveryRoute.objects.filter(
        marketplace_order=order
    ).first()
    if existing:
        logger.info('Route already exists for order %s: route #%d', order.order_number, existing.pk)
        return {
            'route_id': existing.pk,
            'already_existed': True,
        }

    # Find available vehicle (cold chain if needed)
    vehicle = None
    if order.requires_cold_chain:
        vehicle = Vehicle.objects.filter(
            is_active=True, has_cold_chain=True
        ).first()
    if not vehicle:
        vehicle = Vehicle.objects.filter(is_active=True).first()

    # Create route
    route = DeliveryRoute.objects.create(
        marketplace_order=order,
        vehicle=vehicle,
        driver=driver_user or order.assigned_driver,
        date=order.delivery_date_requested or timezone.now().date(),
        status='planned',
        notes='Auto-created from Marketplace order %s' % order.order_number,
    )

    stop_order = 1
    pickup_count = 0
    delivery_count = 0

    # Pickup stops — one per seller (OPG)
    sub_orders = SellerSubOrder.objects.filter(
        marketplace_order=order
    ).select_related('seller_company')

    for sub in sub_orders:
        seller = sub.seller_company
        DeliveryStop.objects.create(
            route=route,
            stop_order=stop_order,
            stop_type='pickup',
            seller_suborder=sub,
            company=seller,
            address=sub.pickup_address or getattr(seller, 'address', '') or '',
            contact_name=seller.name,
            contact_phone=getattr(seller, 'phone', '') or '',
            status='pending',
        )
        stop_order += 1
        pickup_count += 1

    # Delivery stop — buyer
    buyer = order.buyer_company
    DeliveryStop.objects.create(
        route=route,
        stop_order=stop_order,
        stop_type='delivery',
        marketplace_order=order,
        company=buyer,
        address=order.delivery_address or getattr(buyer, 'address', '') or '',
        contact_name=order.delivery_notes[:100] if order.delivery_notes else buyer.name,
        contact_phone=getattr(buyer, 'phone', '') or '',
        status='pending',
        estimated_arrival=None,  # Will be calculated by route optimizer
    )
    delivery_count += 1

    # WhatsApp notification to driver
    driver = route.driver
    if driver:
        try:
            from core.whatsapp import send_text
            from accounts.models import UserProfile
            profile = UserProfile.objects.filter(user=driver).first()
            phone = getattr(profile, 'phone', '') if profile else ''
            if phone:
                send_text(
                    phone=phone,
                    message=(
                        'Nova ruta: %s\n'
                        '%d preuzimanja + %d dostava\n'
                        'Datum: %s\n'
                        '%s'
                    ) % (
                        order.order_number,
                        pickup_count, delivery_count,
                        route.date.strftime('%d.%m.%Y'),
                        'HLADNI LANAC — koristiti hladnjacu!' if order.requires_cold_chain else '',
                    ),
                    company_id=str(buyer.pk),
                )
        except Exception as e:
            logger.warning('Driver WhatsApp notification failed: %s', e)

    logger.info(
        '[DELIVERY WEBHOOK] Route #%d created for order %s: %d pickups, %d deliveries',
        route.pk, order.order_number, pickup_count, delivery_count
    )

    return {
        'route_id': route.pk,
        'stops_count': pickup_count + delivery_count,
        'pickup_count': pickup_count,
        'delivery_count': delivery_count,
    }


def notify_cold_chain_breach(stop_id, temp_reading, threshold=8.0):
    """
    Alert: ako IoT senzor detektira prekid hladnog lanca na delivery stopu.
    Salje WhatsApp alert driver + seller + buyer.
    """
    from delivery.models import DeliveryStop
    stop = DeliveryStop.objects.select_related(
        'route__marketplace_order__buyer_company',
        'company'
    ).get(pk=stop_id)

    if temp_reading > threshold:
        logger.critical(
            'COLD CHAIN BREACH: Stop #%d, temp: %.1f°C (threshold: %.1f°C)',
            stop_id, temp_reading, threshold
        )

        try:
            from core.whatsapp import send_text
            msg = (
                'UPOZORENJE: Prekid hladnog lanca!\n'
                'Temperatura: %.1f°C (max dozvoljeno: %.1f°C)\n'
                'Stanica: %s\n'
                'Roba: %s'
            ) % (
                temp_reading, threshold,
                stop.address,
                stop.route.marketplace_order.order_number if stop.route.marketplace_order else '?',
            )

            # Notify all relevant parties
            phones = set()
            if stop.contact_phone:
                phones.add(stop.contact_phone)
            if stop.route.driver:
                from accounts.models import UserProfile
                dp = UserProfile.objects.filter(user=stop.route.driver).first()
                if dp and getattr(dp, 'phone', ''):
                    phones.add(dp.phone)

            for phone in phones:
                send_text(phone=phone, message=msg, company_id=str(stop.company.pk))

        except Exception as e:
            logger.error('Cold chain alert failed: %s', e)

        return True
    return False
