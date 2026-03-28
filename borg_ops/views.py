"""
BORG Ops views — universal card move API + operations dashboard.

v3: Race condition aware (select_for_update u FSMMixin),
    stale card detection (expected_status), refresh endpoint.
"""
import json
import logging

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.db import models
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from .models import CardActivity, StatusTimestamp

logger = logging.getLogger('borg.ops')

# Allowed models for the universal move API
CARD_MODELS = {
    'ProjectLead': ('burza', 'ProjectLead'),
    'WorkOrder': ('work_orders', 'WorkOrder'),
    'HitnaIntervencija': ('interventions', 'HitnaIntervencija'),
}


@login_required
@require_POST
def card_move(request):
    """
    Universal card move API.
    POST /api/card/move/
    Body: {
        "model": "WorkOrder",
        "pk": 1,
        "new_status": "in_progress",
        "expected_status": "draft"  ← opcijalno, stale card detection
    }

    Stale card detection: ako frontend pošalje expected_status koji se
    ne poklapa s trenutnim statusom u bazi, vraća grešku UMJESTO da
    pokuša tranziciju. Ovo sprečava "iluziju" stale Kanban ploče.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    model_name = data.get('model', '')
    pk = data.get('pk')
    new_status = data.get('new_status', '')
    expected_status = data.get('expected_status')  # Dron #3: stale detection

    if model_name not in CARD_MODELS:
        return JsonResponse({'ok': False, 'error': f'Nepoznat model: {model_name}'}, status=400)

    if not pk or not new_status:
        return JsonResponse({'ok': False, 'error': 'pk i new_status su obavezni'}, status=400)

    app_label, cls_name = CARD_MODELS[model_name]
    try:
        Model = apps.get_model(app_label, cls_name)
    except LookupError:
        return JsonResponse({'ok': False, 'error': f'Model {model_name} ne postoji'}, status=400)

    try:
        obj = Model.objects.get(pk=pk)
    except Model.DoesNotExist:
        return JsonResponse({'ok': False, 'error': f'{model_name} #{pk} ne postoji'}, status=404)

    # Stale card detection — Dron #3 fix
    if expected_status:
        actual = getattr(obj, obj.STATUS_FIELD if hasattr(obj, 'STATUS_FIELD') else 'status')
        if actual != expected_status:
            err_msg = (
                f'Kartica je već promijenjena: očekivano "{expected_status}", '
                f'stvarno "{actual}". Osvježite ploču.'
            )
            is_htmx = request.headers.get('HX-Request') == 'true'
            if is_htmx:
                response = HttpResponse('', status=200)
                response['HX-Trigger'] = json.dumps({
                    'showFsmError': err_msg,
                    'refreshBoard': True,  # Signal frontendu da refresha
                })
                response['HX-Reswap'] = 'none'
                return response
            return JsonResponse({
                'ok': False,
                'error': err_msg,
                'actual_status': actual,
                'stale': True,
            }, status=409)  # 409 Conflict

    try:
        obj.transition_to(new_status, user=request.user)
    except ValueError as e:
        err_msg = str(e)
        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            response = HttpResponse(
                f'<div class="fsm-error-toast" style="display:none">{err_msg}</div>',
                status=200
            )
            response['HX-Trigger'] = json.dumps({'showFsmError': err_msg})
            response['HX-Reswap'] = 'none'
            return response
        return JsonResponse({'ok': False, 'error': err_msg}, status=400)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        response = HttpResponse('', status=200)
        response['HX-Trigger'] = json.dumps({
            'cardMoved': {
                'model': model_name,
                'pk': str(pk),
                'status': new_status,
            }
        })
        return response

    return JsonResponse({
        'ok': True,
        'model': model_name,
        'pk': str(pk),
        'new_status': new_status,
        'message': f'{model_name} premješten u {new_status}',
    })


@login_required
@require_GET
def board_version(request):
    """
    Lagani endpoint za Dron #3 — umjesto pollinga cijele ploče,
    frontend pita samo "ima li promjena od mog zadnjeg viđenja?"

    GET /api/card/version/?since=2026-03-28T17:00:00Z
    Returns: {"has_changes": true/false, "latest": "2026-03-28T17:05:12Z", "count": 3}

    Frontend poziva ovo svakih 30s — jedan COUNT query, ne JOIN.
    Ako has_changes=true, frontend radi puni refresh ploče.
    """
    since_str = request.GET.get('since', '')
    try:
        since = timezone.datetime.fromisoformat(since_str)
        if timezone.is_naive(since):
            since = timezone.make_aware(since)
    except (ValueError, TypeError):
        since = timezone.now() - timezone.timedelta(minutes=5)

    # Samo COUNT — najlakši mogući query
    recent = CardActivity.objects.filter(
        action='status_change',
        created_at__gt=since,
    )
    count = recent.count()
    latest = recent.order_by('-created_at').values_list('created_at', flat=True).first()

    return JsonResponse({
        'has_changes': count > 0,
        'latest': latest.isoformat() if latest else since.isoformat(),
        'count': count,
    })


@login_required
def operations_dashboard(request):
    """Unified operations dashboard — SLA alerts + mini kanbans + AI digest."""
    from interventions.models import HitnaIntervencija
    from work_orders.models import WorkOrder
    from burza.models import ProjectLead

    now = timezone.now()

    # SLA breaches — open timestamps exceeding limits
    from .tasks import SLA_RULES
    sla_alerts = []
    for model_path, rules in SLA_RULES.items():
        app_label, model_name = model_path.split('.')
        try:
            Model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        ct = ContentType.objects.get_for_model(Model)
        for status, max_minutes in rules.items():
            cutoff = now - timezone.timedelta(minutes=max_minutes)
            overdue = StatusTimestamp.objects.filter(
                content_type=ct, status=status,
                exited_at__isnull=True, entered_at__lt=cutoff,
            ).values_list('object_id', flat=True)[:10]
            for obj_id in overdue:
                try:
                    obj = Model.objects.get(pk=obj_id)
                    ts_entry = StatusTimestamp.objects.filter(
                        content_type=ct, object_id=obj_id,
                        status=status, exited_at__isnull=True,
                    ).first()
                    minutes = int((now - ts_entry.entered_at).total_seconds() / 60) if ts_entry else 0
                    sla_alerts.append({
                        'model': model_name,
                        'obj': obj,
                        'status': status,
                        'minutes': minutes,
                        'max': max_minutes,
                        'severity': 'critical' if minutes > max_minutes * 2 else 'warning',
                    })
                except Model.DoesNotExist:
                    pass

    # Mini kanbans — top 5 per system
    interventions_active = HitnaIntervencija.objects.exclude(
        status__in=['RIJESENO', 'FAKTURIRANO']
    ).select_related('assigned_to').order_by('created_at')[:5]

    wo_active = WorkOrder.objects.filter(
        status__in=['draft', 'in_progress']
    ).select_related('client', 'assigned_to').order_by('created_at')[:5]

    leads_open = ProjectLead.objects.filter(
        status__in=['NOVI_UPIT', 'INTERNA_PROCJENA', 'NA_BURZI']
    ).select_related('company').order_by('created_at')[:5]

    # AI Digest — FenixSignal last 24h
    signal_stats = {'total': 0, 'new': 0, 'critical': 0}
    try:
        from limit_connect_ai.models_signal import FenixSignal
        since = now - timezone.timedelta(hours=24)
        signals_24h = FenixSignal.objects.filter(created_at__gte=since)
        signal_stats = {
            'total': signals_24h.count(),
            'new': signals_24h.filter(status='new').count(),
            'critical': signals_24h.filter(priority__lte=2).count(),
        }
    except Exception:
        pass

    # ── Experiences — danas ──
    exp_today = {'schedules': 0, 'bookings': 0, 'no_shows': 0, 'revenue': 0}
    try:
        from experiences.models import ExperienceSchedule, ExperienceBooking
        today = now.date()
        today_scheds = ExperienceSchedule.objects.filter(date=today)
        exp_today['schedules'] = today_scheds.count()
        today_bookings = ExperienceBooking.objects.filter(
            schedule__date=today
        )
        exp_today['bookings'] = today_bookings.count()
        exp_today['no_shows'] = today_bookings.filter(status='no_show').count()
        from django.db.models import Sum
        exp_today['revenue'] = today_bookings.filter(
            status__in=['completed', 'checked_in']
        ).aggregate(s=Sum('price_total'))['s'] or 0
    except Exception:
        pass

    # ── Inventory alerts ──
    inv_alerts = {'low_stock': 0, 'karenca': 0, 'expiring': 0, 'items': []}
    try:
        from inventory.models import InventoryItem, StockBatch
        low = InventoryItem.objects.filter(
            is_active=True, quantity__lte=models.F('min_quantity'),
            min_quantity__gt=0,
        )[:5]
        inv_alerts['low_stock'] = low.count()
        inv_alerts['items'] = list(low.values_list('name', flat=True))

        # Karenca
        karenca_items = InventoryItem.objects.filter(
            source_flock__isnull=False, is_active=True,
        )
        karenca_count = 0
        for item in karenca_items:
            if item.source_flock and item.source_flock.has_active_karenca:
                karenca_count += 1
        inv_alerts['karenca'] = karenca_count

        # Expiring batches (7 days)
        from datetime import timedelta
        week = today + timedelta(days=7)
        inv_alerts['expiring'] = StockBatch.objects.filter(
            expiry_date__lte=week, expiry_date__gte=today,
            quarantine_status='active',
        ).count()
    except Exception:
        pass

    # ── Financijski pulse ──
    fin_pulse = {'today_revenue': 0, 'unpaid': 0, 'overdue': 0}
    try:
        from invoicing.models import Invoice
        today_invoices = Invoice.objects.filter(
            date_issued=today, status__in=['CONFIRMED', 'FISCALIZED', 'SENT'],
        )
        fin_pulse['today_revenue'] = today_invoices.aggregate(
            s=Sum('total'))['s'] or 0
        fin_pulse['unpaid'] = Invoice.objects.filter(
            status__in=['CONFIRMED', 'FISCALIZED', 'SENT'],
        ).exclude(total=0).count()
    except Exception:
        pass

    return render(request, 'borg_ops/operations_dashboard.html', {
        'sla_alerts': sorted(sla_alerts, key=lambda x: -x['minutes']),
        'interventions': interventions_active,
        'work_orders': wo_active,
        'leads': leads_open,
        'signal_stats': signal_stats,
        'exp_today': exp_today,
        'inv_alerts': inv_alerts,
        'fin_pulse': fin_pulse,
        'now': now,
    })


@login_required
@require_GET
def activity_fragment(request):
    """
    HTMX lazy-load fragment za _activity_log.html.
    GET /api/card/activity/?ct=work_orders.workorder&pk=123
    Returns: rendered _activity_log.html partial.
    """
    ct_str = request.GET.get('ct', '')
    pk = request.GET.get('pk', '')

    if not ct_str or not pk:
        return HttpResponse('<div class="al-empty">Nedostaju parametri.</div>')

    try:
        app_label, model_name = ct_str.split('.')
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
    except (ValueError, ContentType.DoesNotExist):
        return HttpResponse('<div class="al-empty">Nepoznat model.</div>')

    activities = CardActivity.objects.filter(
        content_type=ct,
        object_id=str(pk),
    ).select_related('user').order_by('-created_at')[:20]

    return render(request, 'borg_ops/_activity_log.html', {
        'activities': activities,
    })


@login_required
@require_GET
def dispatch_suggest(request, pk):
    """
    Smart Dispatch API — predlaže radnike za intervenciju.
    GET /api/dispatch/suggest/<pk>/
    Returns: JSON s rangiranim kandidatima.
    """
    from interventions.models import HitnaIntervencija
    from .dispatch import suggest_workers, estimate_budget

    try:
        interv = HitnaIntervencija.objects.select_related('company').get(pk=pk)
    except HitnaIntervencija.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Intervencija ne postoji'}, status=404)

    candidates = suggest_workers(interv, limit=5)
    budget = estimate_budget(interv.category, interv.company)

    return JsonResponse({
        'ok': True,
        'intervention': {
            'pk': interv.pk,
            'title': interv.title,
            'category': interv.category,
            'address': interv.address,
            'has_gps': bool(interv.last_lat),
        },
        'candidates': [
            {
                'user_id': c['user'].pk,
                'username': c['user'].username,
                'full_name': c['user'].get_full_name() or c['user'].username,
                'score': c['score'],
                'distance_km': c['distance_km'],
                'workload': c['workload'],
                'has_category': c['has_category'],
                'breakdown': c['breakdown'],
            }
            for c in candidates
        ],
        'budget_estimate': {
            'estimate': str(budget['estimate']),
            'median': str(budget['median']),
            'min': str(budget['min']),
            'max': str(budget['max']),
            'sample_size': budget['sample_size'],
            'source': budget['source'],
        },
    })


@login_required
@require_POST
def update_worker_gps(request):
    """
    POST /api/worker/gps/
    Body: {"lat": 45.55, "lng": 18.69}

    Dron #1 fix: ažurira UserProfile.last_lat/lng/gps_update.
    Poziva se iz JS Geolocation API pri svakom FSM tranziciji na mobitelu.
    """
    try:
        data = json.loads(request.body)
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Neispravan GPS'}, status=400)

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({'ok': False, 'error': 'GPS izvan granica'}, status=400)

    try:
        profile = request.user.profile
        profile.last_lat = lat
        profile.last_lng = lng
        profile.last_gps_update = timezone.now()
        profile.save(update_fields=['last_lat', 'last_lng', 'last_gps_update'])
        logger.info('GPS update: user=%s lat=%.4f lng=%.4f', request.user.username, lat, lng)
        return JsonResponse({'ok': True, 'lat': lat, 'lng': lng})
    except Exception as e:
        logger.error('GPS update failed: %s', e)
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
