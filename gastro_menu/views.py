"""
Gastro Menu views — digital menu display + admin panel.

Public: /gastro/menu/<slug>/ — QR jelovnik za goste
Admin:  /gastro/admin/ — upravljanje artiklima, cijenama, dostupnoscu
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from .models import DigitalMenu, MenuCategory, MenuItem, TableQR

logger = logging.getLogger('gastro_menu')


# ── Public Menu (QR) ──────────────────────────────────────────────

def public_menu(request, slug):
    """Public digital menu — gosti skeniraju QR kod."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    categories = MenuCategory.objects.filter(
        menu=menu, is_active=True
    ).prefetch_related('items').order_by('sort_order')

    # Filter only available items
    for cat in categories:
        cat.available_items = cat.items.filter(is_available=True).order_by('sort_order')

    return render(request, 'gastro_menu/public_menu.html', {
        'menu': menu,
        'categories': categories,
    })


# ── Admin Panel ───────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    """Gastro admin dashboard — pregled jelovnika, kategorija, artikala."""
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

    # Stats
    total_items = MenuItem.objects.filter(category__menu=menu).count()
    available = MenuItem.objects.filter(category__menu=menu, is_available=True).count()
    unavailable = total_items - available
    tables = TableQR.objects.filter(company=company, menu=menu).count()

    # Low stock warnings
    low_stock = []
    try:
        from inventory.models import InventoryItem
        low = InventoryItem.objects.filter(
            company=company,
            category__in=['food', 'drink'],
            is_active=True,
        ).extra(where=['quantity <= min_quantity AND min_quantity > 0'])
        low_stock = list(low.values('name', 'quantity', 'min_quantity', 'unit')[:10])
    except Exception:
        pass

    return render(request, 'gastro_menu/admin_dashboard.html', {
        'menu': menu,
        'categories': categories,
        'stats': {
            'total_items': total_items,
            'available': available,
            'unavailable': unavailable,
            'tables': tables,
        },
        'low_stock': low_stock,
    })


@login_required
@require_POST
def toggle_availability(request):
    """HTMX/AJAX: toggle MenuItem.is_available."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item = MenuItem.objects.select_related('category__menu').get(
            pk=item_id, category__menu__company=company
        )
        item.is_available = not item.is_available
        item.save(update_fields=['is_available'])
        return JsonResponse({
            'ok': True,
            'is_available': item.is_available,
            'item_id': item.pk,
        })
    except MenuItem.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def update_price(request):
    """HTMX/AJAX: update MenuItem.price inline."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        new_price = data.get('price')

        from decimal import Decimal, InvalidOperation
        try:
            price = Decimal(str(new_price))
            if price < 0:
                raise ValueError('Cijena ne moze biti negativna')
        except (InvalidOperation, TypeError, ValueError) as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)

        item = MenuItem.objects.select_related('category__menu').get(
            pk=item_id, category__menu__company=company
        )
        item.price = price
        item.save(update_fields=['price'])

        # Sync inventory unit_price
        try:
            from inventory.models import InventoryItem
            from django.utils.text import slugify
            sku = slugify(item.name)[:40]
            InventoryItem.objects.filter(
                company=company, sku=sku
            ).update(unit_price=price)
        except Exception:
            pass

        return JsonResponse({
            'ok': True,
            'item_id': item.pk,
            'price': str(price),
        })
    except MenuItem.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)



# ── Upute (javno dostupne) ────────────────────────────────────────

def upute(request, slug):
    """Javna stranica s uputama — od primke do knjizenja."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    from django.utils import timezone
    return render(request, 'gastro_menu/upute.html', {
        'menu': menu,
        'company_name': menu.company.name,
        'generated_date': timezone.now().strftime('%d.%m.%Y'),
    })
