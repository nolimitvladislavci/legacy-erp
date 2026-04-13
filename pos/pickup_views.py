"""
pos/pickup_views.py — Pekara Pickup QR Flow
Kupac skenira QR > naruci putem > plati online ili gotovinom > pokupi vrecicu
"""
import json
import logging
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('pos.pickup')


def pickup_menu(request, company_slug):
    """QR landing - kupac vidi meni i naruci. BEZ LOGINA."""
    from companies.models import Company
    from inventory.models import InventoryItem

    company = get_object_or_404(Company, booking_slug=company_slug)
    items = InventoryItem.objects.filter(
        company=company, is_active=True
    ).select_related('tax_rate').order_by('category', 'name')

    bag_item = InventoryItem.objects.filter(
        company=company, is_active=True, sku='VRECICA'
    ).first()

    categories = sorted(set(
        getattr(i, 'category', 'ostalo') or 'ostalo' for i in items
    ))

    return render(request, 'pos/pickup_menu.html', {
        'company': company,
        'items': items,
        'categories': categories,
        'bag_item': bag_item,
        'bag_price': bag_item.unit_price if bag_item else Decimal('0.05'),
    })


@csrf_exempt
def pickup_order(request, company_slug):
    """POST: kreiraj pickup narudzbu."""
    from companies.models import Company
    from inventory.models import InventoryItem
    from pos.models import GastroOrder, GastroOrderItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    company = get_object_or_404(Company, booking_slug=company_slug)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    cart = data.get('items', [])
    guest_name = data.get('name', '').strip()
    guest_phone = data.get('phone', '').strip()
    payment_method = data.get('payment', 'cash')
    add_bag = data.get('bag', False)

    if not cart:
        return JsonResponse({'error': 'Kosara je prazna'}, status=400)
    if not guest_name:
        return JsonResponse({'error': 'Ime je obavezno'}, status=400)

    order = GastroOrder.objects.create(
        company=company,
        guest_name=guest_name,
        guest_phone=guest_phone,
        notes='PICKUP | ' + payment_method + (' | +vrecica' if add_bag else ''),
        status='confirmed',
    )

    total = Decimal('0')
    for item_data in cart:
        inv_item = InventoryItem.objects.filter(
            pk=item_data.get('id'), company=company, is_active=True
        ).first()
        if not inv_item:
            continue
        qty = int(item_data.get('qty', 1))
        GastroOrderItem.objects.create(
            order=order,
            inventory_item=inv_item,
            quantity=qty,
            notes=item_data.get('notes', ''),
        )
        price = inv_item.unit_price or Decimal('0')
        total += price * qty

    if add_bag:
        bag = InventoryItem.objects.filter(company=company, sku='VRECICA').first()
        if bag:
            GastroOrderItem.objects.create(
                order=order, inventory_item=bag, quantity=1, notes='Vrecica',
            )
            total += bag.unit_price or Decimal('0.05')

    pay_url = None
    if payment_method == 'online':
        try:
            from payments.services import create_payment
            payment = create_payment(
                company=company,
                amount=total,
                currency='EUR',
                source='pos_pickup',
                method='stripe',
                description='Pickup ' + order.tracking_token[:8],
                metadata={'order_id': order.pk},
            )
            pay_url = payment.get('checkout_url', '')
        except Exception as e:
            logger.warning('Payment init failed: %s', e)

    # WhatsApp potvrda narudzbe
    if guest_phone:
        try:
            from core.whatsapp_tasks import send_whatsapp_text_task
            track_url = 'https://limit-connect.com/pos/pickup/track/' + order.tracking_token + '/'
            msg = 'Narudzba primljena! Vasa vrecica ce biti spremna. Ukupno: ' + str(total) + ' EUR. Placanje: ' + payment_method + '. Pratite: ' + track_url
            send_whatsapp_text_task.delay(guest_phone, msg)
        except Exception:
            pass

    return JsonResponse({
        'ok': True,
        'order_id': order.pk,
        'tracking': order.tracking_token,
        'total': str(total),
        'payment_method': payment_method,
        'pay_url': pay_url,
        'message': 'Narudzba primljena! Vasa vrecica ce biti spremna.',
    })


def pickup_track(request, tracking_token):
    """Kupac prati status narudzbe."""
    from pos.models import GastroOrder
    order = get_object_or_404(GastroOrder, tracking_token=tracking_token)
    items = order.items.select_related('inventory_item').all()

    return render(request, 'pos/pickup_track.html', {
        'order': order,
        'items': items,
    })


def pickup_board(request, company_slug):
    """Pekara tablet - prikaz svih aktivnih narudzbi."""
    from companies.models import Company
    from pos.models import GastroOrder

    company = get_object_or_404(Company, booking_slug=company_slug)
    active = GastroOrder.objects.filter(
        company=company,
        status__in=['new', 'confirmed', 'preparing', 'ready'],
    ).prefetch_related('items__inventory_item').order_by('created_at')

    completed_today = GastroOrder.objects.filter(
        company=company,
        status__in=['paid', 'delivered'],
        created_at__date=timezone.now().date(),
    ).count()

    return render(request, 'pos/pickup_board.html', {
        'company': company,
        'orders': active,
        'completed_today': completed_today,
    })


@csrf_exempt
def pickup_status_update(request, order_id):
    """Pekara mijenja status narudzbe (tablet)."""
    from pos.models import GastroOrder

    if request.method != 'POST':
        return JsonResponse({'error': 'POST'}, status=405)

    order = get_object_or_404(GastroOrder, pk=order_id)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    new_status = data.get('status', '')

    valid_transitions = {
        'new': ['confirmed', 'cancelled'],
        'confirmed': ['preparing', 'cancelled'],
        'preparing': ['ready', 'cancelled'],
        'ready': ['delivered', 'paid'],
        'delivered': ['paid'],
    }

    allowed = valid_transitions.get(order.status, [])
    if new_status not in allowed:
        return JsonResponse({'error': 'Nevalidan prijelaz: ' + order.status + ' -> ' + new_status}, status=400)

    order.status = new_status
    if new_status == 'delivered':
        order.delivered_at = timezone.now()
    order.save()

    # WhatsApp notifikacija za svaki status
    if order.guest_phone:
        wa_messages = {
            'confirmed': 'Narudzba potvrdena! Pripremamo vasu narudzbu.',
            'preparing': 'Vasa narudzba je U PRIPREMI! Uskoro ce biti gotova.',
            'ready': 'Vasa narudzba je SPREMNA! Dodite pokupiti u ' + order.company.name + '.',
            'delivered': 'Hvala na posjetu! Dodite nam opet.',
        }
        msg = wa_messages.get(new_status)
        if msg:
            try:
                from core.whatsapp_tasks import send_whatsapp_text_task
                send_whatsapp_text_task.delay(
                    order.guest_phone,
                    order.company.name + ' - ' + msg + ' #' + order.tracking_token[:8]
                )
            except Exception:
                pass

    return JsonResponse({'ok': True, 'status': order.status})
