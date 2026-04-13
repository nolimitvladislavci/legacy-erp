"""
pos/field_sales_views.py — Terenska prodaja za pekaru
Utovar → Ruta → Prodaja (POS) → Povratnica → Z-report
"""
import json
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from inventory.models import InventoryItem, StockMovement
from pos.models import POSTerminal, POSSession
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('pos.field_sales')


@login_required
def field_start(request, terminal_id):
    """Otvori terensku smjenu - utovar artikala u vozilo."""
    terminal = get_object_or_404(POSTerminal, pk=terminal_id, pos_type='field')
    company = get_user_company(request)

    # Check if already open
    open_session = POSSession.objects.filter(terminal=terminal, status='open').first()
    if open_session:
        return redirect('pos:field_dashboard', session_id=open_session.pk)

    items = InventoryItem.objects.filter(
        company=company, is_active=True, quantity__gt=0
    ).order_by('category', 'name')

    if request.method == 'POST':
        vehicle = request.POST.get('vehicle_plate', '').strip()
        route = request.POST.get('route_name', '').strip()
        opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')

        # Parse loaded items
        loaded = []
        for item in items:
            qty_key = 'load_' + str(item.pk)
            qty = request.POST.get(qty_key, '0')
            try:
                qty = int(qty)
            except (ValueError, TypeError):
                qty = 0
            if qty > 0:
                loaded.append({
                    'id': item.pk,
                    'name': item.name,
                    'sku': item.sku or '',
                    'qty': qty,
                    'price': str(item.unit_price),
                })
                # Oduzmi sa skladista (izlaz na teren)
                StockMovement.objects.create(
                    item=item,
                    movement_type='out',
                    quantity=qty,
                    unit_price=item.unit_price,
                    reason='Utovar teren: ' + route + ' (' + vehicle + ')',
                    performed_by=request.user,
                )
                item.quantity -= qty
                item.save(update_fields=['quantity'])

        if not loaded:
            messages.error(request, _('Morate utovariti barem jedan artikl.'))
            return redirect('pos:field_start', terminal_id=terminal_id)

        # Create session
        last = POSSession.objects.filter(terminal=terminal).order_by('-session_number').first()
        next_num = (last.session_number + 1) if last else 1

        session = POSSession.objects.create(
            terminal=terminal,
            operator=request.user,
            session_number=next_num,
            opening_cash=opening_cash,
            is_field_session=True,
            vehicle_plate=vehicle,
            route_name=route,
            loaded_items_json=loaded,
        )

        # Auto clock-in cashier
        try:
            from pos.worktime_bridge import cashier_clock_in
            from pos.models import POSCashier
            cashier = POSCashier.objects.filter(user=request.user, company=company).first()
            if cashier:
                cashier_clock_in(cashier)
                session.active_cashiers.add(cashier)
        except DatabaseError:
            pass

        # Auto-generate otpremnica
        try:
            from documents.models import Otpremnica, OtpremnicaItem
            otp = Otpremnica.objects.create(
                company=company,
                doc_number='TER-' + str(next_num),
                date_issued=timezone.now().date(),
                vehicle_plate=vehicle,
                driver_name=request.user.get_full_name() or request.user.username,
                notes='Terenska ruta: ' + route,
                status='confirmed',
                created_by=request.user,
            )
            for li in loaded:
                OtpremnicaItem.objects.create(
                    document=otp,
                    product_name=li['name'],
                    quantity=Decimal(str(li['qty'])),
                    unit='kom',
                    unit_price=Decimal(li['price']),
                )
            logger.info('Otpremnica %s created for field session %s', otp.doc_number, session.pk)
        except (ValueError, TypeError) as e:
            logger.warning('Otpremnica creation failed: %s', e)

        messages.success(request, _('Terenska smjena otvorena! Ruta: ') + route)
        return redirect('pos:field_dashboard', session_id=session.pk)

    return render(request, 'pos/field_start.html', {
        'terminal': terminal,
        'items': items,
    })


@login_required
def field_dashboard(request, session_id):
    """Terenski dashboard - pregled utovarenog, prodanog, preostalog."""
    session = get_object_or_404(POSSession, pk=session_id, is_field_session=True)
    loaded = session.loaded_items_json or []
    returned = session.returned_items_json or []

    # Calculate sold quantities from receipts
    sold_map = {}
    for receipt in session.receipts.filter(status='paid'):
        for ri in receipt.items.all():
            iid = ri.inventory_item_id
            if iid:
                sold_map[iid] = sold_map.get(iid, 0) + int(ri.quantity)

    # Build summary
    summary = []
    total_loaded = 0
    total_sold = 0
    total_revenue = Decimal('0')

    for li in loaded:
        item_id = li['id']
        qty_loaded = li['qty']
        qty_sold = sold_map.get(item_id, 0)
        qty_remaining = qty_loaded - qty_sold
        price = Decimal(li.get('price', '0'))
        revenue = price * qty_sold

        summary.append({
            'id': item_id,
            'name': li['name'],
            'sku': li.get('sku', ''),
            'loaded': qty_loaded,
            'sold': qty_sold,
            'remaining': qty_remaining,
            'price': price,
            'revenue': revenue,
        })
        total_loaded += qty_loaded
        total_sold += qty_sold
        total_revenue += revenue

    return render(request, 'pos/field_dashboard.html', {
        'session': session,
        'summary': summary,
        'total_loaded': total_loaded,
        'total_sold': total_sold,
        'total_remaining': total_loaded - total_sold,
        'total_revenue': total_revenue,
        'is_open': session.status == 'open',
    })


@login_required
@require_POST
def field_return(request, session_id):
    """Povratnica - vrati neprodano na skladiste i zatvori smjenu."""
    session = get_object_or_404(POSSession, pk=session_id, is_field_session=True, status='open')
    company = get_user_company(request)
    loaded = session.loaded_items_json or []

    # Calculate sold
    sold_map = {}
    for receipt in session.receipts.filter(status='paid'):
        for ri in receipt.items.all():
            if ri.inventory_item_id:
                sold_map[ri.inventory_item_id] = sold_map.get(ri.inventory_item_id, 0) + int(ri.quantity)

    # Return unsold to stock
    returned = []
    for li in loaded:
        item_id = li['id']
        qty_loaded = li['qty']
        qty_sold = sold_map.get(item_id, 0)
        qty_return = qty_loaded - qty_sold

        # Manual override if provided
        manual_key = 'return_' + str(item_id)
        manual_qty = request.POST.get(manual_key)
        if manual_qty is not None:
            try:
                qty_return = int(manual_qty)
            except (ValueError, TypeError):
                pass

        if qty_return > 0:
            item = InventoryItem.objects.filter(pk=item_id).first()
            if not item:
                continue

            action = request.POST.get('action_' + str(item_id), 'return')

            if action == 'return':
                # Vrati na zalihu kao svjeze
                StockMovement.objects.create(
                    item=item, movement_type='in', quantity=qty_return,
                    unit_price=item.unit_price,
                    reason='Povrat s terena: ' + session.route_name,
                    performed_by=request.user,
                )
                item.quantity += qty_return
                item.save(update_fields=['quantity'])

            elif action == 'discount':
                # Vrati na zalihu ali oznaci kao jucerasnje (-50% cijena)
                discounted_price = item.unit_price * Decimal('0.5')
                StockMovement.objects.create(
                    item=item, movement_type='in', quantity=qty_return,
                    unit_price=discounted_price,
                    reason='JUCERASNJE (-50%) povrat: ' + session.route_name,
                    performed_by=request.user,
                )
                item.quantity += qty_return
                item.save(update_fields=['quantity'])
                # TODO: oznaci artikle kao "jucerasnji" za POS prikaz

            elif action == 'writeoff':
                # Otpisi — ne vraca na zalihu, samo log
                StockMovement.objects.create(
                    item=item, movement_type='out', quantity=qty_return,
                    unit_price=item.unit_price,
                    reason='OTPIS (kalo/rastur) teren: ' + session.route_name,
                    performed_by=request.user,
                )
                # NE dodajemo na zalihu — roba je otpisana

            returned.append({
                'id': item_id,
                'name': li['name'],
                'qty': qty_return,
                'action': action,
            })

    session.returned_items_json = returned

    # Close session
    closing_cash = Decimal(request.POST.get('closing_cash', '0') or '0')
    session.closing_cash = closing_cash
    session.closed_at = timezone.now()
    session.status = 'closed'
    session.save()

    # Auto clock-out
    try:
        from pos.worktime_bridge import session_close_all_cashiers
        session_close_all_cashiers(session)
    except Exception:
        pass

    messages.success(request, _('Terenska smjena zatvorena. Povrat: ') + str(len(returned)) + ' artikala.')
    return redirect('pos:field_dashboard', session_id=session.pk)
