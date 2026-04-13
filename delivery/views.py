import logging
logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Q
from django.views.decorators.http import require_POST

def _post_or_json(request, key, default=''):
    """Read from POST data or JSON body (for offline queue replay)."""
    if request.content_type == 'application/json':
        import json
        try:
            body = json.loads(request.body)
            return body.get(key, default)
        except (json.JSONDecodeError, AttributeError):
            return default
    return request.POST.get(key, default)


from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext as _

from core.company_utils import get_user_company
from .models import (
    ConsolidatedDelivery, ColdChainZone, SensorReading,
    Vehicle, DeliveryRoute,
)


@login_required
def index(request):
    """Redirect to consolidated dashboard if company has deliveries, else coming soon."""
    company = get_user_company(request)
    if company and ConsolidatedDelivery.objects.filter(
        Q(hub_company=company) | Q(buyer_company=company)
    ).exists():
        return redirect('delivery:consolidated_list')
    return render(request, "coming_soon.html", {
        "module_name": "Dostava",
        "module_icon": "fas fa-truck",
        "module_description": "Upravljanje dostavama, rutiranje vozila, pracenje statusa i automatsko obavjestavanje kupaca.",
    })


@login_required
def consolidated_list(request):
    """Hub dashboard — lista konsolidiranih isporuka."""
    company = get_user_company(request)
    qs = ConsolidatedDelivery.objects.filter(
        Q(hub_company=company) | Q(buyer_company=company)
    ).select_related('hub_company', 'buyer_company', 'vehicle', 'cold_chain_zone')

    status_filter = request.GET.get('status', 'active')
    if status_filter == 'active':
        qs = qs.exclude(status__in=['delivered', 'cancelled'])
    elif status_filter == 'delivered':
        qs = qs.filter(status='delivered')

    # Annotate latest temp
    latest_reading_sq = SensorReading.objects.filter(
        consolidated_delivery=OuterRef('pk')
    ).order_by('-timestamp')

    deliveries = list(qs.order_by('-created_at')[:50])

    # Attach latest temp to each delivery
    for cd in deliveries:
        reading = SensorReading.objects.filter(
            consolidated_delivery=cd
        ).order_by('-timestamp').first()
        if reading:
            cd.latest_temp = reading.temperature
            if cd.cold_chain_zone:
                cd.temp_ok = (
                    cd.cold_chain_zone.target_min_temp <= reading.temperature <= cd.cold_chain_zone.target_max_temp
                )
            else:
                cd.temp_ok = True
        else:
            cd.latest_temp = None
            cd.temp_ok = True

        # Check if late
        cd.is_late = cd.eta and cd.eta < timezone.now() and cd.status not in ('delivered', 'cancelled')

    # Stats
    all_qs = ConsolidatedDelivery.objects.filter(
        Q(hub_company=company) | Q(buyer_company=company)
    )
    today = timezone.now().date()
    stats = {
        'collecting': all_qs.filter(status='collecting').count(),
        'consolidating': all_qs.filter(status='consolidating').count(),
        'in_transit': all_qs.filter(status__in=['dispatched', 'in_transit']).count(),
        'delivered_today': all_qs.filter(status='delivered', delivered_at__date=today).count(),
    }

    # Cold chain alerts
    cold_chain_alerts = ColdChainZone.objects.filter(
        company=company, is_active=True
    ).count()
    # Count zones out of range
    alert_count = 0
    for zone in ColdChainZone.objects.filter(buyer_company=company, is_active=True):
        if zone.is_in_range is False:
            alert_count += 1

    return render(request, 'delivery/consolidated_dashboard.html', {
        'deliveries': deliveries,
        'stats': stats,
        'cold_chain_alerts': alert_count,
        'current_status': status_filter,
    })


@login_required
def consolidated_detail(request, pk):
    """Detail view for a consolidated delivery."""
    company = get_user_company(request)
    cd = get_object_or_404(
        ConsolidatedDelivery.objects.select_related(
            'hub_company', 'buyer_company', 'vehicle', 'cold_chain_zone', 'tracked_item'
        ),
        pk=pk,
    )
    orders = cd.marketplace_orders.select_related('buyer_company').prefetch_related('items__product')
    readings = SensorReading.objects.filter(consolidated_delivery=cd).order_by('-timestamp')[:20]

    return render(request, 'delivery/consolidated_detail.html', {
        'cd': cd,
        'orders': orders,
        'readings': readings,
    })


@login_required
def consolidated_create(request):
    """Create a new consolidated delivery."""
    company = get_user_company(request)
    if request.method == 'POST':
        from marketplace.models import MarketplaceOrder
        buyer_id = request.POST.get('buyer_company')
        method = request.POST.get('delivery_method', 'internal')
        order_ids = request.POST.getlist('orders')
        cold_zone_id = request.POST.get('cold_chain_zone')

        cd = ConsolidatedDelivery.objects.create(
            hub_company=company,
            buyer_company_id=buyer_id,
            delivery_method=method,
            requires_cold_chain=bool(cold_zone_id),
            cold_chain_zone_id=cold_zone_id or None,
            external_carrier_name=request.POST.get('carrier_name', ''),
            external_carrier_contact=request.POST.get('carrier_contact', ''),
            external_carrier_ref=request.POST.get('carrier_ref', ''),
            delivery_address=request.POST.get('delivery_address', ''),
            hub_cutoff_time=request.POST.get('hub_cutoff_time') or None,
            total_weight_kg=request.POST.get('total_weight_kg') or None,
            package_count=request.POST.get('package_count', 1),
            delivery_notes=request.POST.get('notes', ''),
            created_by=request.user,
        )

        if order_ids:
            cd.marketplace_orders.set(order_ids)

        # Auto-create TrackedItem
        from tracking.models import TrackedItem
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(ConsolidatedDelivery)
        tracked = TrackedItem.objects.create(
            content_type=ct,
            object_id=str(cd.pk),
            tracking_type='shipment',
            delivery_method=method,
        )
        cd.tracked_item = tracked
        cd.save(update_fields=['tracked_item'])

        messages.success(request, f'Isporuka {cd.delivery_number} kreirana. Tracking: /tracking/t/{tracked.public_token}/')
        return redirect('delivery:consolidated_detail', pk=cd.pk)

    # GET — form data
    from companies.models import Company
    from marketplace.models import MarketplaceOrder
    buyers = Company.objects.filter(
        marketplace_orders__isnull=False
    ).distinct().order_by('name')
    pending_orders = MarketplaceOrder.objects.filter(
        status__in=['confirmed', 'collecting']
    ).exclude(
        consolidated_deliveries__isnull=False
    ).select_related('buyer_company').order_by('-created_at')[:50]
    zones = ColdChainZone.objects.filter(buyer_company=company, is_active=True)
    vehicles = Vehicle.objects.filter(company=company, is_active=True)

    return render(request, 'delivery/consolidated_form.html', {
        'buyers': buyers,
        'pending_orders': pending_orders,
        'zones': zones,
        'vehicles': vehicles,
        'method_choices': ConsolidatedDelivery.DELIVERY_METHOD_CHOICES,
    })


@login_required
def consolidated_status_update(request, pk):
    """Quick status update for a consolidated delivery."""
    cd = get_object_or_404(ConsolidatedDelivery, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(ConsolidatedDelivery.STATUS_CHOICES):
            cd.status = new_status
            update_fields = ['status', 'updated_at']

            if new_status == 'dispatched':
                cd.dispatched_at = timezone.now()
                update_fields.append('dispatched_at')
            elif new_status == 'delivered':
                cd.delivered_at = timezone.now()
                update_fields.append('delivered_at')

            cd.save(update_fields=update_fields)

            # Update tracking status too
            if cd.tracked_item:
                from tracking.models import TrackingStatus
                status_map = {
                    'collecting': 'prikupljanje',
                    'consolidating': 'konsolidacija',
                    'dispatched': 'otpremljeno',
                    'in_transit': 'u-transportu',
                    'delivered': 'dostavljeno',
                }
                slug = status_map.get(new_status)
                if slug:
                    ts = TrackingStatus.objects.filter(
                        tracking_type='shipment', slug=slug
                    ).first()
                    if ts:
                        cd.tracked_item.update_status(ts, user=request.user)

            messages.success(request, f'Status promjenjen na: {cd.get_status_display()}')

    return redirect('delivery:consolidated_detail', pk=cd.pk)




# ═══════════════════════════════════════════════════════════════
# DRIVER MOBILE VIEWS
# ═══════════════════════════════════════════════════════════════
@login_required
def driver_stop(request, pk):
    """Mobile-first view za vozaca na stanici dostave."""
    stop = get_object_or_404(DeliveryStop, pk=pk)
    rollwagens = stop.rollwagens.all().order_by('load_order')
    exchanges = stop.packaging_exchanges.all()
    return render(request, 'delivery/driver_stop.html', {
        'stop': stop,
        'rollwagens': rollwagens,
        'exchanges': exchanges,
    })


@login_required
@require_POST
def driver_packaging_save(request, stop_pk):
    """Sprema razmjenu ambalaze za stanicu dostave."""
    stop = get_object_or_404(DeliveryStop, pk=stop_pk)
    pkg_type = _post_or_json(request, 'packaging_type', 'ifco')
    delivered = int(_post_or_json(request, 'delivered_qty', 0))
    returned = int(_post_or_json(request, 'returned_qty', 0))

    from .models import PackagingExchange
    exchange = PackagingExchange.objects.create(
        delivery_stop=stop,
        packaging_type=pkg_type,
        delivered_qty=delivered,
        returned_qty=returned,
    )

    photo = request.FILES.get('photo')
    if photo:
        exchange.photo = photo
        exchange.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'balance': exchange.balance})
    return redirect('delivery:driver_stop', pk=stop_pk)


@login_required
@require_POST
def driver_rollwagen_scan(request, stop_pk):
    """Vozac skenira QR kod rollwagena."""
    from django.utils import timezone as tz
    from .models import Rollwagen

    qr = _post_or_json(request, 'qr_code', '').strip()
    try:
        rw = Rollwagen.objects.get(qr_code=qr, delivery_stop__pk=stop_pk)
        rw.is_loaded = not rw.is_loaded
        rw.loaded_at = tz.now() if rw.is_loaded else None
        rw.save()
        return JsonResponse({'ok': True, 'qr': qr, 'loaded': rw.is_loaded})
    except Rollwagen.DoesNotExist:
        return JsonResponse({'ok': False, 'error': f'Rollwagen {qr} nicht gefunden'}, status=404)


# ═══════════════════════════════════════════════════════════════
# DISPATCHER — Ponude za taksiste/gepek vozače
# ═══════════════════════════════════════════════════════════════
@login_required
def dispatcher_board(request):
    """Control Tower — exception-based dispatcher dashboard."""
    from .models import (
        DispatchOffer, ConsolidatedDelivery, HACCPIncident,
        SmartBox, PackagingExchange,
    )
    from django.db.models import Sum

    company = request.user.profile.company

    # Core data
    pending_deliveries = ConsolidatedDelivery.objects.filter(
        hub_company=company, status__in=['collecting', 'consolidating'],
        driver__isnull=True,
    )
    active_offers = DispatchOffer.objects.filter(
        consolidated_delivery__hub_company=company,
        status__in=['pending', 'accepted'],
    ).select_related('consolidated_delivery', 'driver')
    in_transit = ConsolidatedDelivery.objects.filter(
        hub_company=company, status='in_transit',
    ).select_related('driver', 'buyer_company')
    completed_today = DispatchOffer.objects.filter(
        consolidated_delivery__hub_company=company,
        status='completed',
        completed_at__date=timezone.now().date(),
    )

    # HACCP Panic Room
    haccp_open = HACCPIncident.objects.filter(
        is_resolved=False,
        smart_box__owner_company=company,
    ).select_related('smart_box').order_by('-breach_start')
    blocked_boxes = SmartBox.objects.filter(
        owner_company=company,
        haccp_status__in=['blocked', 'critical'],
    )

    # Packaging Radar — aggregate balance by type
    packaging_balance = PackagingExchange.objects.filter(
        delivery_stop__company=company,
    ).values('packaging_type').annotate(
        total_delivered=Sum('delivered_qty'),
        total_returned=Sum('returned_qty'),
        total_balance=Sum('balance'),
    ).order_by('-total_balance')

    # Metrics
    today = timezone.now().date()
    deliveries_today = ConsolidatedDelivery.objects.filter(
        hub_company=company, created_at__date=today,
    ).count()

    return render(request, 'delivery/dispatcher_board.html', {
        'pending_deliveries': pending_deliveries,
        'active_offers': active_offers,
        'in_transit': in_transit,
        'completed_today': completed_today,
        'haccp_open': haccp_open,
        'blocked_boxes': blocked_boxes,
        'packaging_balance': packaging_balance,
        'deliveries_today': deliveries_today,
        'completed_count': completed_today.count(),
    })


@login_required
def dispatcher_board_data(request):
    """AJAX endpoint for 15s auto-refresh."""
    from .models import (
        DispatchOffer, ConsolidatedDelivery, HACCPIncident, SmartBox,
    )

    company = request.user.profile.company

    pending_count = ConsolidatedDelivery.objects.filter(
        hub_company=company, status__in=['collecting', 'consolidating'],
        driver__isnull=True,
    ).count()

    haccp_list = []
    for inc in HACCPIncident.objects.filter(
        is_resolved=False, smart_box__owner_company=company,
    ).select_related('smart_box'):
        haccp_list.append({
            'id': inc.id,
            'type': inc.get_incident_type_display(),
            'severity': inc.severity,
            'max_temp': str(inc.max_temperature),
            'box_id': inc.smart_box.box_id if inc.smart_box else '?',
            'start': inc.breach_start.isoformat() if inc.breach_start else '',
        })

    blocked_count = SmartBox.objects.filter(
        owner_company=company,
        haccp_status__in=['blocked', 'critical'],
    ).count()

    in_transit_list = []
    for cd in ConsolidatedDelivery.objects.filter(
        hub_company=company, status='in_transit',
    ).select_related('driver', 'buyer_company'):
        in_transit_list.append({
            'number': cd.delivery_number,
            'buyer': cd.buyer_company.name if cd.buyer_company else '',
            'driver': cd.driver.get_full_name() if cd.driver else '',
            'dispatched': cd.dispatched_at.isoformat() if cd.dispatched_at else '',
        })

    offers_list = []
    for o in DispatchOffer.objects.filter(
        consolidated_delivery__hub_company=company,
        status__in=['pending', 'accepted'],
    ).select_related('consolidated_delivery', 'driver'):
        offers_list.append({
            'id': o.id,
            'status': o.status,
            'price': str(o.offered_price),
            'number': o.consolidated_delivery.delivery_number,
            'driver': o.driver.get_full_name() if o.driver else '',
        })

    completed_count = DispatchOffer.objects.filter(
        consolidated_delivery__hub_company=company,
        status='completed',
        completed_at__date=timezone.now().date(),
    ).count()

    return JsonResponse({
        'pending_count': pending_count,
        'haccp': haccp_list,
        'blocked_count': blocked_count,
        'in_transit': in_transit_list,
        'active_offers': offers_list,
        'completed_count': completed_count,
    })


@login_required
def driver_offers(request):
    """Vozač (taxi/gepek) vidi dostupne ponude i prihvaća."""
    from .models import DispatchOffer
    available = DispatchOffer.objects.filter(
        status='pending',
        driver__isnull=True,
    ).select_related('consolidated_delivery', 'consolidated_delivery__hub_company')

    my_active = DispatchOffer.objects.filter(
        driver=request.user,
        status='accepted',
    ).select_related('consolidated_delivery')

    return render(request, 'delivery/driver_offers.html', {
        'available': available,
        'my_active': my_active,
    })


@login_required
@require_POST
def driver_accept_offer(request, pk):
    """Vozač prihvaća ponudu."""
    from .models import DispatchOffer
    offer = get_object_or_404(DispatchOffer, pk=pk, status='pending')
    offer.accept(request.user)
    return redirect('delivery:driver_offers')


@login_required
@require_POST
def driver_handoff(request, stop_pk):
    """HACCP primopredaja — vozač bilježi temperaturu, foto, checklist."""
    from .models import TransportHandoff, SmartBox

    stop = get_object_or_404(DeliveryStop, pk=stop_pk)

    # HACCP Block Check — ako je SmartBox blokiran, ne dopusti primopredaju
    blocked_boxes = stop.smart_boxes.filter(haccp_status='blocked')
    if blocked_boxes.exists():
        box = blocked_boxes.first()
        incident = box.haccp_incidents.filter(is_resolved=False).first()
        msg = {
            'blocked': True,
            'box_id': box.box_id,
            'reason': incident.description if incident else 'HACCP lanac prekinut',
            'incident_id': incident.id if incident else None,
            'message': f'SmartBox {box.box_id} je BLOKIRAN — zatrazite odobrenje dispatchera.',
        }
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(msg, status=403)
        from django.contrib import messages as django_messages
        django_messages.error(request, msg['message'])
        return redirect('delivery:driver_stop', pk=stop_pk)

    is_json = request.content_type == 'application/json'
    def _chk(name):
        val = _post_or_json(request, name, '')
        return val == 'on' or val is True

    checklist = {
        'packaging_intact': _chk('packaging_intact'),
        'temp_in_range': _chk('temp_in_range'),
        'vehicle_clean': _chk('vehicle_clean'),
        'no_cross_contamination': _chk('no_cross_contamination'),
        'delivery_time_ok': _chk('delivery_time_ok'),
    }

    handoff = TransportHandoff.objects.create(
        handoff_type='driver_to_customer',
        delivery_stop=stop,
        consolidated_delivery=stop.route.consolidated_deliveries.first() if stop.route else None,
        performed_by=request.user,
        temperature_at_handoff=_post_or_json(request, 'temperature', '') or None,
        recipient_name=_post_or_json(request, 'recipient_name', ''),
        haccp_checklist=checklist,
        notes=request.POST.get('notes', ''),
    )

    # SmartBox — ako je skenirana, označi kao vraća se
    box_qr = _post_or_json(request, 'box_qr', '').strip()
    if box_qr:
        try:
            box = SmartBox.objects.get(qr_code=box_qr)
            box.status = 'returning'
            box.current_stop = None
            box.save(update_fields=['status', 'current_stop'])
            handoff.smart_box = box
            handoff.save(update_fields=['smart_box'])
        except SmartBox.DoesNotExist:
            pass

    photo = request.FILES.get('photo')
    if photo:
        handoff.photo = photo
        handoff.save(update_fields=['photo'])

    # 6.4 Packaging Lock — block dispatch without rollwagen binding
    if stop.marketplace_order:
        has_rw = Rollwagen.objects.filter(bound_order=stop.marketplace_order).exists()
        if not has_rw:
            _msg = "AMBALAZA BLOKADA: Narudzba nema vezani rollwagen. Skenirajte rollwagen na Pack Station prije otpreme."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": _msg}, status=400)
            from django.contrib import messages as django_messages
            django_messages.error(request, _msg)
            return redirect("delivery:driver_stop", pk=stop_pk)

    # Mark stop as completed
    stop.status = 'completed'
    stop.completed_at = timezone.now()
    stop.save(update_fields=['status', 'completed_at'])

    # Deferred Fiscalization -- fiscalize draft invoice on handoff
    if stop.marketplace_order and hasattr(stop.marketplace_order, 'invoice'):
        invoice = stop.marketplace_order.invoice
        if invoice and invoice.status == 'DRAFT' and not invoice.is_fiscalized:
            try:
                invoice.status = 'CONFIRMED'
                invoice.save(update_fields=['status'])
                logger.info(f'Invoice {invoice.pk} confirmed on handoff for stop {stop_pk}')
            except Exception as e:
                logger.warning(f'Invoice confirmation failed on handoff: {e}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'compliant': handoff.is_compliant})
    return redirect('delivery:driver_stop', pk=stop_pk)


def delivery_cost_calc(request):
    """API: izračunaj cijenu dostave."""
    from .models import DeliveryCostRule
    region = request.GET.get('region', 'osijek_local')
    method = request.GET.get('method', 'taxi')
    distance = float(request.GET.get('distance', 10))
    cold_chain = request.GET.get('cold_chain', 'false') == 'true'

    try:
        rule = DeliveryCostRule.objects.get(
            region=region, delivery_method=method, is_active=True
        )
        cost = rule.calculate(distance, cold_chain)
        return JsonResponse({
            'cost': float(cost),
            'base_fee': float(rule.base_fee),
            'per_km': float(rule.per_km_fee),
            'distance': distance,
            'cold_surcharge': float(rule.cold_chain_surcharge) if cold_chain else 0,
            'min_order': float(rule.min_order_value),
        })
    except DeliveryCostRule.DoesNotExist:
        return JsonResponse({'error': 'No pricing rule found'}, status=404)


# ═══════════════════════════════════════════════════════════════
# DRIVER PWA — Mobile-first dashboard za vozace
# ═══════════════════════════════════════════════════════════════
@login_required
def driver_pwa(request):
    """PWA dashboard za vozaca — danas ruta, stopovi, navigacija."""
    from django.utils import timezone as tz
    today = tz.now().date()

    route = DeliveryRoute.objects.filter(
        driver=request.user,
        date=today,
    ).prefetch_related('stops__company').first()

    stops = []
    completed = 0
    total = 0
    if route:
        stops = route.stops.all().order_by('stop_order')
        total = stops.count()
        completed = stops.filter(status='completed').count()

    # Upcoming routes (next 3 days)
    upcoming = DeliveryRoute.objects.filter(
        driver=request.user,
        date__gt=today,
    ).order_by('date')[:3]

    return render(request, 'delivery/driver_pwa.html', {
        'route': route,
        'stops': stops,
        'completed': completed,
        'total': total,
        'upcoming': upcoming,
        'today': today,
    })


@login_required
@require_POST
def driver_update_stop(request, stop_pk):
    """AJAX: vozac updatea status stopa."""
    from django.utils import timezone as tz

    stop = get_object_or_404(DeliveryStop, pk=stop_pk)
    action = request.POST.get('action', '')

    if action == 'arrived':
        stop.status = 'arrived'
        stop.actual_arrival = tz.now()
        stop.save()
    elif action == 'completed':
        stop.status = 'completed'
        stop.completed_at = tz.now()
        stop.recipient_name = request.POST.get('recipient', '')
        stop.notes = request.POST.get('notes', '')
        # Handle photo
        if 'photo' in request.FILES:
            stop.delivery_photo = request.FILES['photo']
        # Handle temp
        temp = request.POST.get('temp')
        if temp:
            from decimal import Decimal
            stop.temp_at_handover = Decimal(temp)
        stop.save()

        # Check if all stops completed -> mark route as completed
        route = stop.route
        if not route.stops.exclude(status__in=['completed', 'skipped']).exists():
            route.status = 'completed'
            route.completed_at = tz.now()
            route.save()
    elif action == 'skipped':
        stop.status = 'skipped'
        stop.notes = request.POST.get('notes', 'Preskoceno')
        stop.save()

    return JsonResponse({
        'ok': True,
        'status': stop.status,
        'stop_id': stop.pk,
    })


@login_required
@require_POST
def driver_start_route(request, route_pk):
    """AJAX: vozac starta rutu."""
    from django.utils import timezone as tz
    route = get_object_or_404(DeliveryRoute, pk=route_pk, driver=request.user)
    if route.status == 'planned':
        route.status = 'in_progress'
        route.started_at = tz.now()
        route.save()
    return JsonResponse({'ok': True, 'status': route.status})


@login_required
def driver_gps_update(request):
    """AJAX: periodicni GPS update od vozaca."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    lat = request.POST.get('lat')
    lng = request.POST.get('lng')
    if lat and lng:
        DeliveryTracking.objects.create(
            route=DeliveryRoute.objects.filter(
                driver=request.user,
                status='in_progress',
            ).first(),
            latitude=lat,
            longitude=lng,
        )
    return JsonResponse({'ok': True})


# ── Public API: Delivery Zones ──────────────────────────────────
def api_delivery_zones(request, slug):
    """
    GET /delivery/api/zones/<slug>/
    Public endpoint — vraca zone dostave za firmu (po booking_slug).
    Koristi se u webshop checkout-u i landing stranicama.
    """
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)
    from .models import DeliveryZone
    zones = DeliveryZone.objects.filter(company=company, is_active=True)
    data = []
    for z in zones:
        data.append({
            'id': z.id,
            'name': z.name,
            'description': z.description,
            'price': float(z.price),
            'min_km': float(z.min_distance_km),
            'max_km': float(z.max_distance_km),
            'free_above': float(z.free_delivery_above) if z.free_delivery_above else None,
            'time_window': z.time_window,
            'days': z.days_display,
        })
    return JsonResponse({'zones': data, 'count': len(data)})


# ═══════════════════════════════════════════════════════════════
# TRANSPORT MODULE VIEWS
# ═══════════════════════════════════════════════════════════════
@login_required
def transport_order_list(request):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')
    from .models import TransportOrder
    status_f = request.GET.get('status', '')
    type_f = request.GET.get('type', '')
    qs = TransportOrder.objects.filter(company=company).select_related('vehicle', 'driver').order_by('-planned_departure')
    if status_f:
        qs = qs.filter(status=status_f)
    if type_f:
        qs = qs.filter(transport_type=type_f)
    return render(request, 'delivery/transport_order_list.html', {'orders': qs[:50], 'status_f': status_f, 'type_f': type_f})


@login_required
def transport_order_detail(request, pk):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    from .models import TransportOrder
    order = get_object_or_404(TransportOrder, pk=pk, company=company)
    issues = order.verify_documents() if hasattr(order, 'verify_documents') else []
    return render(request, 'delivery/transport_order_detail.html', {'order': order, 'issues': issues})


@login_required
def fleet_dashboard(request):
    from core.company_utils import get_user_company
    from .models import TransportOrder, Vehicle, VehicleDocument
    from django.utils import timezone
    from datetime import timedelta
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')
    today = timezone.now().date()
    warn_date = today + timedelta(days=30)

    vehicles = Vehicle.objects.filter(company=company, is_active=True) if hasattr(Vehicle, 'objects') else []
    active_orders = TransportOrder.objects.filter(company=company, status__in=['planned', 'in_transit', 'loading', 'border_crossing']).order_by('-planned_departure')[:20]

    expiring_vehicle_docs = VehicleDocument.objects.filter(vehicle__company=company, valid_until__lte=warn_date, valid_until__gte=today).order_by('valid_until')[:20]
    expired_vehicle_docs = VehicleDocument.objects.filter(vehicle__company=company, valid_until__lt=today).order_by('valid_until')[:10]

    return render(request, 'delivery/fleet_dashboard.html', {
        'vehicles': vehicles,
        'active_orders': active_orders,
        'expiring_docs': expiring_vehicle_docs,
        'expired_docs': expired_vehicle_docs,
        'today': today,
    })


@login_required
def transport_order_create(request):
    """Kreiranje novog transportnog naloga."""
    from core.company_utils import get_user_company
    from .models import TransportOrder, Vehicle
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if request.method == 'POST':
        order = TransportOrder(
            company=company,
            transport_type=request.POST.get('transport_type', 'freight_eu'),
            status='draft',
            origin_address=request.POST.get('origin_address', ''),
            origin_country=request.POST.get('origin_country', 'HR'),
            destination_address=request.POST.get('destination_address', ''),
            destination_country=request.POST.get('destination_country', 'HR'),
            planned_departure=request.POST.get('planned_departure') or None,
            planned_arrival=request.POST.get('planned_arrival') or None,
            cargo_description=request.POST.get('cargo_description', ''),
            total_weight_kg=request.POST.get('total_weight_kg') or None,
            total_volume_m3=request.POST.get('total_volume_m3') or None,
            package_count=request.POST.get('package_count') or 1,
            requires_cold_chain=request.POST.get('requires_cold_chain') == 'on',
            temp_min=request.POST.get('temp_min') or None,
            temp_max=request.POST.get('temp_max') or None,
            client_name=request.POST.get('client_name', ''),
            client_phone=request.POST.get('client_phone', ''),
            client_reference=request.POST.get('client_reference', ''),
            client_price=request.POST.get('client_price') or 0,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        vehicle_id = request.POST.get('vehicle')
        if vehicle_id:
            order.vehicle = Vehicle.objects.filter(pk=vehicle_id, company=company).first()
        driver_id = request.POST.get('driver')
        if driver_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            order.driver = User.objects.filter(pk=driver_id).first()
        order.save()

        issues = order.verify_documents()
        if issues:
            messages.warning(request, _('Nalog kreiran, ali postoje problemi s dokumentima: ') + '; '.join(issues))
        else:
            messages.success(request, f'Transportni nalog {order.order_number} kreiran.')
        return redirect('delivery:transport_detail', pk=order.pk)

    # GET — form
    vehicles = Vehicle.objects.filter(company=company, is_active=True)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    drivers = User.objects.filter(profile__company=company, is_active=True)
    return render(request, 'delivery/transport_order_create.html', {
        'vehicles': vehicles,
        'drivers': drivers,
        'transport_types': TransportOrder.TRANSPORT_TYPES,
        'country_choices': TransportOrder.COUNTRY_CHOICES,
    })
