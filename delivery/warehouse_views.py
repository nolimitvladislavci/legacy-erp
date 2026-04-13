"""
delivery/warehouse_views.py — Warehouse Pick & Pack Terminal
Tablet-optimized views for warehouse staff.
Safety checks: weight tolerance (6.2), anti-crush (6.3), packaging lock (6.4).
"""
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    PackagingExchange,
    PickTask,
    PickWave,
    Rollwagen,
)

logger = logging.getLogger(__name__)

# ── Safety constants ──────────────────────────────────────────
WEIGHT_TOLERANCE = Decimal('0.20')  # ±20% deviation allowed


@login_required
def warehouse_terminal(request):
    """Main warehouse dashboard — list open waves + quick stats."""
    company = request.user.profile.company

    open_waves = PickWave.objects.filter(
        company=company,
        status__in=['open', 'picking', 'picked', 'packing'],
    ).order_by('created_at')

    # Orders waiting to be packed (no pick wave yet)
    from marketplace.models import MarketplaceOrder
    pending_orders = MarketplaceOrder.objects.filter(
        buyer_company__hub_consolidated_deliveries__hub_company=company,
        status='confirmed',
    ).distinct()[:20]

    # Stats
    today = timezone.now().date()
    packed_today = PickWave.objects.filter(
        company=company, status__in=['packed', 'loaded'],
        completed_at__date=today,
    ).count()

    return render(request, 'delivery/warehouse_terminal.html', {
        'open_waves': open_waves,
        'pending_orders': pending_orders,
        'packed_today': packed_today,
    })


@login_required
def wave_pick(request, wave_pk):
    """Wave picking view — aggregated list, picker marks items as picked."""
    wave = get_object_or_404(PickWave, pk=wave_pk)
    tasks = wave.tasks.all().select_related('product')

    if request.method == 'POST':
        task_pk = request.POST.get('task_pk')
        picked_qty = request.POST.get('picked_quantity', '')

        if task_pk:
            task = get_object_or_404(PickTask, pk=task_pk, wave=wave)
            if picked_qty:
                task.picked_quantity = Decimal(picked_qty)
            else:
                task.picked_quantity = task.total_quantity
            task.status = 'picked'
            task.save(update_fields=['picked_quantity', 'status'])

            # Check if all tasks picked
            if not wave.tasks.filter(status='pending').exists():
                wave.status = 'picked'
                wave.save(update_fields=['status'])

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'task_id': task.pk})

        return redirect('delivery:wave_pick', wave_pk=wave.pk)

    return render(request, 'delivery/wave_pick.html', {
        'wave': wave,
        'tasks': tasks,
    })


def _check_weight_tolerance(actual_qty, ordered_qty):
    """
    6.2 Scale Tolerance — block if actual weight deviates more than +/-20%.
    Returns (ok, error_message).
    """
    if ordered_qty <= 0:
        return True, ''
    deviation = abs(actual_qty - ordered_qty) / ordered_qty
    if deviation > WEIGHT_TOLERANCE:
        pct = int(deviation * 100)
        return False, (
            f'Tolerancija premasena: {actual_qty} vs naruceno {ordered_qty} '
            f'({pct}% odstupanje, max {int(WEIGHT_TOLERANCE * 100)}%). '
            f'Koristite "force=1" za override.'
        )
    return True, ''


def _check_anti_crush(rollwagen, new_product):
    """
    6.3 Anti-Crush — heavy items cannot go into a rollwagen
    that already has fragile items.
    Returns (ok, error_message).
    """
    if not new_product.is_heavy:
        return True, ''

    # Check if any item already in this rollwagen (via bound_order) is fragile
    if not rollwagen.bound_order:
        return True, ''

    fragile_in_rw = rollwagen.bound_order.items.filter(
        product__is_fragile=True,
        packed_at__isnull=False,
    ).exists()

    if fragile_in_rw:
        return False, (
            f'ANTI-CRUSH BLOKADA: Rollwagen {rollwagen.qr_code} vec sadrzi krhke proizvode. '
            f'Teske stavke ({new_product.name}) ne mogu ici u isti rollwagen.'
        )
    return True, ''


@login_required
def pack_station(request, order_pk):
    """
    Pack station — per-order view for weighing + rollwagen binding.
    Dynamic pricing: actual_quantity updates draft invoice.
    Safety: weight tolerance (6.2), anti-crush (6.3).
    """
    from marketplace.models import MarketplaceOrder

    order = get_object_or_404(MarketplaceOrder, pk=order_pk)
    items = order.items.all().select_related('product')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        force = request.POST.get('force') == '1'

        if action == 'weigh':
            # Dynamic weighing — update actual quantities
            errors = []
            with transaction.atomic():
                for item in items:
                    actual_qty_str = request.POST.get(f'actual_qty_{item.pk}', '')
                    if not actual_qty_str:
                        continue

                    actual_qty = Decimal(actual_qty_str)

                    # 6.2 Weight tolerance check
                    if not force:
                        ok, err = _check_weight_tolerance(actual_qty, item.quantity)
                        if not ok:
                            errors.append(err)
                            continue

                    item.actual_quantity = actual_qty
                    item.actual_total = actual_qty * item.unit_price
                    item.packed_by = request.user
                    item.packed_at = timezone.now()
                    item.seller_status = 'ready'
                    item.save(update_fields=[
                        'actual_quantity', 'actual_total',
                        'packed_by', 'packed_at', 'seller_status',
                    ])

                if errors:
                    if is_ajax:
                        return JsonResponse({'ok': False, 'errors': errors}, status=400)
                    for e in errors:
                        messages.error(request, e)
                    return redirect('delivery:pack_station', order_pk=order.pk)

                # Recalculate order total with actual amounts
                new_subtotal = sum(
                    i.actual_total if i.actual_total else i.total
                    for i in order.items.all()
                )
                order.subtotal = new_subtotal
                order.total = new_subtotal + order.delivery_fee
                order.save(update_fields=['subtotal', 'total'])

                # Update draft invoice amount
                if order.invoice and order.invoice.status == 'DRAFT':
                    order.invoice.notes = (
                        f'Azurirano nakon vaganja. '
                        f'Novi iznos: {order.total} EUR. '
                        f'Pakirao: {request.user.get_full_name()}'
                    )
                    order.invoice.save(update_fields=['notes'])

            if is_ajax:
                return JsonResponse({
                    'ok': True,
                    'new_total': str(order.total),
                })
            return redirect('delivery:pack_station', order_pk=order.pk)

        elif action == 'genesis_scan':
            # Bind rollwagen to this order
            qr_code = request.POST.get('qr_code', '').strip()
            if qr_code:
                try:
                    rw = Rollwagen.objects.get(qr_code=qr_code)

                    # 6.3 Anti-crush check — heavy on fragile
                    if not force:
                        for item in items.filter(packed_at__isnull=False):
                            ok, err = _check_anti_crush(rw, item.product)
                            if not ok:
                                if is_ajax:
                                    return JsonResponse({'ok': False, 'error': err}, status=400)
                                messages.error(request, err)
                                return redirect('delivery:pack_station', order_pk=order.pk)

                    rw.bound_order = order
                    rw.packed_by = request.user
                    rw.packed_at = timezone.now()

                    # Parse packaging count from form
                    pkg = {}
                    for key in ['ifco', 'euro_pallet', 'chep', 'smartbox']:
                        val = request.POST.get(f'pkg_{key}', '0')
                        if val and int(val) > 0:
                            pkg[key] = int(val)
                    rw.packaging_count = pkg
                    rw.save(update_fields=[
                        'bound_order', 'packed_by', 'packed_at', 'packaging_count',
                    ])

                    # Auto-create PackagingExchange for Pfand tracking
                    if rw.delivery_stop and pkg:
                        for pkg_type, qty in pkg.items():
                            PackagingExchange.objects.create(
                                delivery_stop=rw.delivery_stop,
                                packaging_type=pkg_type,
                                delivered_qty=qty,
                            )

                    if is_ajax:
                        return JsonResponse({
                            'ok': True, 'qr': qr_code,
                            'rollwagen': str(rw),
                        })
                except Rollwagen.DoesNotExist:
                    if is_ajax:
                        return JsonResponse(
                            {'ok': False, 'error': f'Rollwagen {qr_code} ne postoji'},
                            status=404,
                        )

            return redirect('delivery:pack_station', order_pk=order.pk)

    # GET — show pack station
    bound_rollwagens = Rollwagen.objects.filter(bound_order=order)

    return render(request, 'delivery/pack_station.html', {
        'order': order,
        'items': items,
        'bound_rollwagens': bound_rollwagens,
    })


@login_required
@require_POST
def create_wave(request):
    """Create a pick wave from selected orders or a route."""
    from django.db.models import Sum

    from marketplace.models import MarketplaceOrder, MarketplaceOrderItem

    company = request.user.profile.company
    order_pks = request.POST.getlist('order_pks')

    if not order_pks:
        return JsonResponse({'error': 'Odaberite narudzbe'}, status=400)

    orders = MarketplaceOrder.objects.filter(pk__in=order_pks)

    wave = PickWave.objects.create(
        company=company,
        picker=request.user,
        status='open',
    )

    # Aggregate items by product across all orders
    aggregated = (
        MarketplaceOrderItem.objects
        .filter(order__in=orders)
        .values('product_id', 'product__name')
        .annotate(total_qty=Sum('quantity'))
    )

    for agg in aggregated:
        PickTask.objects.create(
            wave=wave,
            product_id=agg['product_id'],
            total_quantity=agg['total_qty'],
            location_hint='',
        )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'wave_number': wave.wave_number,
            'task_count': wave.tasks.count(),
        })

    return redirect('delivery:wave_pick', wave_pk=wave.pk)
