"""
Gastro Menu views — digital menu, ordering, kitchen display, admin panel.
"""
import json
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.company_utils import get_user_company
from .models import DigitalMenu, MenuCategory, MenuItem, TableQR, TableOrder
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError

logger = logging.getLogger('gastro_menu')


# ── Public Menu (QR) ──────────────────────────────────────────────

def public_menu(request, slug):
    """Public digital menu — gosti skeniraju QR kod."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    categories = MenuCategory.objects.filter(
        menu=menu, is_active=True
    ).prefetch_related('items').order_by('sort_order')

    for cat in categories:
        cat.available_items = cat.items.filter(is_available=True).order_by('sort_order')

    table = request.GET.get('table', '')

    return render(request, 'gastro_menu/public_menu.html', {
        'menu': menu,
        'categories': categories,
        'table': table,
    })


# ── Public Order ──────────────────────────────────────────────────

# CSRF exempt: public booking endpoint — uses BookingSignature
@csrf_exempt
@require_POST
def public_order(request, slug):
    """Gost salje narudzbu s public menija (bez logina)."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Neispravan zahtjev'}, status=400)

    table_number = data.get('table', '').strip()
    items = data.get('items', [])
    guest_name = data.get('name', '').strip()

    if not items:
        return JsonResponse({'ok': False, 'error': 'Kosaricu je prazna'}, status=400)

    table_qr = TableQR.objects.filter(
        company=menu.company, table_number=table_number
    ).first()

    order_items = []
    total = Decimal('0')
    for item_data in items:
        mi = MenuItem.objects.filter(
            pk=item_data.get('id'), is_available=True,
            category__menu=menu,
        ).first()
        if mi:
            qty = max(1, int(item_data.get('qty', 1)))
            order_items.append({
                'menu_item_id': mi.pk,
                'name': mi.name,
                'price': str(mi.price),
                'qty': qty,
                'notes': item_data.get('notes', '')[:200],
            })
            total += mi.price * qty

    if not order_items:
        return JsonResponse({'ok': False, 'error': 'Nema dostupnih stavki'}, status=400)

    order = TableOrder.objects.create(
        table_qr=table_qr,
        company=menu.company,
        status='new',
        items=order_items,
        total=total,
    )

    # WhatsApp notifikacija
    try:
        from core.whatsapp import send_text
        items_text = '\n'.join(
            f"  {i['qty']}x {i['name']}" + (f" ({i['notes']})" if i.get('notes') else '')
            for i in order_items
        )
        msg = (
            f'NOVA NARUDZBA #{order.pk}\n'
            f'Stol: {table_number or "?"}\n'
            f'Gost: {guest_name or "-"}\n'
            f'{items_text}\n'
            f'Ukupno: {total} EUR'
        )
        send_text(phone='385913912621', message=msg, company_id=str(menu.company.pk))
    except ImportError as e:
        logger.debug('Order WhatsApp failed: %s', e)

    return JsonResponse({
        'ok': True,
        'order_id': order.pk,
        'total': str(total),
        'message': f'Narudzba #{order.pk} primljena!',
    })


# ── Kitchen Display ───────────────────────────────────────────────

@login_required
def kitchen_display(request):
    """Kuhinjski display — nove narudzbe u realnom vremenu."""
    company = get_user_company(request)
    return render(request, 'gastro_menu/kitchen_display.html', {
        'company': company,
    })


@login_required
def kitchen_orders_fragment(request):
    """HTMX fragment — aktivne narudzbe za kuhinju."""
    company = get_user_company(request)
    orders = TableOrder.objects.filter(
        company=company,
        status__in=['new', 'accepted', 'preparing'],
    ).order_by('created_at')

    return render(request, 'gastro_menu/_kitchen_orders.html', {
        'orders': orders,
    })


@login_required
@require_POST
def kitchen_update_status(request):
    """AJAX: promijeni status narudzbe iz kuhinje."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')

        if new_status not in ('accepted', 'preparing', 'ready', 'served', 'paid'):
            return JsonResponse({'ok': False, 'error': 'Nevaljan status'}, status=400)

        order = TableOrder.objects.get(pk=order_id, company=company)
        order.status = new_status
        if new_status == 'accepted':
            order.accepted_at = timezone.now()
        elif new_status == 'served':
            order.served_at = timezone.now()
        order.save()

        return JsonResponse({'ok': True, 'status': new_status})
    except TableOrder.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Narudzba ne postoji'}, status=404)
    except ObjectDoesNotExist as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# ── Admin Panel ───────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    """Gastro admin dashboard."""
    company = get_user_company(request)
    menus = DigitalMenu.objects.filter(company=company)
    menu = menus.first()

    if not menu:
        return render(request, 'gastro_menu/admin_dashboard.html', {
            'menu': None, 'categories': [], 'stats': {},
        })

    categories = MenuCategory.objects.filter(
        menu=menu
    ).prefetch_related('items').order_by('sort_order')

    total_items = MenuItem.objects.filter(category__menu=menu).count()
    available = MenuItem.objects.filter(category__menu=menu, is_available=True).count()
    tables = TableQR.objects.filter(company=company, menu=menu).count()

    low_stock = []
    try:
        from inventory.models import InventoryItem
        low = InventoryItem.objects.filter(
            company=company, category__in=['food', 'drink'], is_active=True,
        ).extra(where=['quantity <= min_quantity AND min_quantity > 0'])
        low_stock = list(low.values('name', 'quantity', 'min_quantity', 'unit')[:10])
    except DatabaseError:
        pass

    return render(request, 'gastro_menu/admin_dashboard.html', {
        'menu': menu,
        'categories': categories,
        'stats': {
            'total_items': total_items,
            'available': available,
            'unavailable': total_items - available,
            'tables': tables,
        },
        'low_stock': low_stock,
    })


@login_required
@require_POST
def toggle_availability(request):
    """AJAX: toggle MenuItem.is_available."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        item = MenuItem.objects.select_related('category__menu').get(
            pk=data.get('item_id'), category__menu__company=company)
        item.is_available = not item.is_available
        item.save(update_fields=['is_available'])
        return JsonResponse({'ok': True, 'is_available': item.is_available})
    except MenuItem.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@login_required
@require_POST
def update_price(request):
    """AJAX: update MenuItem.price inline."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        price = Decimal(str(data.get('price', 0)))
        if price < 0:
            return JsonResponse({'ok': False, 'error': 'Negativna cijena'}, status=400)
        item = MenuItem.objects.select_related('category__menu').get(
            pk=data.get('item_id'), category__menu__company=company)
        item.price = price
        item.save(update_fields=['price'])
        try:
            from inventory.models import InventoryItem
            from django.utils.text import slugify
            InventoryItem.objects.filter(
                company=company, sku=slugify(item.name)[:40]
            ).update(unit_price=price)
        except DatabaseError:
            pass
        return JsonResponse({'ok': True, 'price': str(price)})
    except MenuItem.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


# ── Upute (javno) ─────────────────────────────────────────────────

def upute(request, slug):
    """Javna stranica s uputama."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    return render(request, 'gastro_menu/upute.html', {
        'menu': menu,
        'company_name': menu.company.name,
        'generated_date': timezone.now().strftime('%d.%m.%Y'),
    })
