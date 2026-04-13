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
from django.db import DatabaseError, models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET, require_POST

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
    """Unified operations dashboard — SLA alerts + mini kanbans + AI digest.
    
    Performance: Redis cache 45s TTL (HTMX refreshes every 60s).
    SLA alerts: bulk query eliminira N+1.
    """
    from django.core.cache import cache

    from burza.models import ProjectLead
    from interventions.models import HitnaIntervencija
    from work_orders.models import WorkOrder

    now = timezone.now()
    CACHE_TTL = 45  # Sekundi — HTMX refresh je 60s, cache istekne prije

    # ── SLA breaches — OPTIMIZIRANO (bulk, ne N+1) ──
    sla_alerts = cache.get('borg_hub_sla_alerts')
    if sla_alerts is None:
        sla_alerts = []
        from .tasks import SLA_RULES
        for model_path, rules in SLA_RULES.items():
            app_label, model_name = model_path.split('.')
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            ct = ContentType.objects.get_for_model(Model)
            for status, max_minutes in rules.items():
                cutoff = now - timezone.timedelta(minutes=max_minutes)
                # BULK: dohvati sve overdue timestamps odjednom s entered_at
                overdue_ts = StatusTimestamp.objects.filter(
                    content_type=ct, status=status,
                    exited_at__isnull=True, entered_at__lt=cutoff,
                ).values('object_id', 'entered_at')[:10]

                if not overdue_ts:
                    continue

                # BULK: dohvati sve objekte odjednom
                obj_ids = [t['object_id'] for t in overdue_ts]
                objects = {o.pk: o for o in Model.objects.filter(pk__in=obj_ids)}

                for ts in overdue_ts:
                    obj = objects.get(ts['object_id'])
                    if not obj:
                        continue
                    minutes = int((now - ts['entered_at']).total_seconds() / 60)
                    sla_alerts.append({
                        'model': model_name,
                        'obj': str(obj),
                        'status': status,
                        'minutes': minutes,
                        'max': max_minutes,
                        'severity': 'critical' if minutes > max_minutes * 2 else 'warning',
                    })
        sla_alerts.sort(key=lambda x: -x['minutes'])
        cache.set('borg_hub_sla_alerts', sla_alerts, CACHE_TTL)

    # Mini kanbans — top 5 per system (cached)
    interventions_active = cache.get('borg_hub_interventions')
    if interventions_active is None:
        interventions_active = list(HitnaIntervencija.objects.exclude(
            status__in=['RIJESENO', 'FAKTURIRANO']
        ).select_related('assigned_to').order_by('created_at')[:5])
        cache.set('borg_hub_interventions', interventions_active, CACHE_TTL)

    wo_active = cache.get('borg_hub_work_orders')
    if wo_active is None:
        wo_active = list(WorkOrder.objects.filter(
            status__in=['draft', 'in_progress']
        ).select_related('client', 'assigned_to').order_by('created_at')[:5])
        cache.set('borg_hub_work_orders', wo_active, CACHE_TTL)

    leads_open = cache.get('borg_hub_leads')
    if leads_open is None:
        leads_open = list(ProjectLead.objects.filter(
            status__in=['NOVI_UPIT', 'INTERNA_PROCJENA', 'NA_BURZI']
        ).select_related('company').order_by('created_at')[:5])
        cache.set('borg_hub_leads', leads_open, CACHE_TTL)

    # AI Digest — FenixSignal last 24h (cached)
    signal_stats = cache.get('borg_hub_signals')
    if signal_stats is None:
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
        except DatabaseError:
            pass
        cache.set('borg_hub_signals', signal_stats, CACHE_TTL)

    # ── Experiences — danas (cached) ──
    exp_today = cache.get('borg_hub_exp_today')
    if exp_today is None:
        exp_today = {'schedules': 0, 'bookings': 0, 'no_shows': 0, 'revenue': 0}
        try:
            from experiences.models import ExperienceBooking, ExperienceSchedule
            today = now.date()
            today_scheds = ExperienceSchedule.objects.filter(date=today)
            exp_today['schedules'] = today_scheds.count()
            today_bookings = ExperienceBooking.objects.filter(schedule__date=today)
            # Jedna agregacija umjesto 3 upita
            from django.db.models import Count, Q, Sum
            agg = today_bookings.aggregate(
                total=Count('id'),
                no_shows=Count('id', filter=Q(status='no_show')),
                revenue=Sum('price_total', filter=Q(status__in=['completed', 'checked_in'])),
            )
            exp_today['bookings'] = agg['total'] or 0
            exp_today['no_shows'] = agg['no_shows'] or 0
            exp_today['revenue'] = agg['revenue'] or 0
        except DatabaseError:
            pass
        cache.set('borg_hub_exp_today', exp_today, CACHE_TTL)

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
    except DatabaseError:
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
    except DatabaseError:
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

    from .dispatch import estimate_budget, suggest_workers

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
    except AttributeError as e:
        logger.error('GPS update failed: %s', e)
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@cache_page(60 * 5)
def public_trace_api(request, qr_token):
    """
    Javni API za QR traceability.
    ČITA SAMO: is_public_facing=True AND is_system_generated=True
    """
    from .models import CardActivity

    # TODO H2.2: implementirati QR token lookup
    # Trenutno: samo potvrdi da filtar radi
    public_activities = CardActivity.objects.filter(
        is_public_facing=True,
        is_system_generated=True,
    ).count()

    return JsonResponse({
        'status': 'stub',
        'public_records': public_activities,
        'note': 'Full QR traceability implementira se u H2.2',
    })


@login_required
def borg_hub(request):
    """
    BORG Hub — Cross-module command center.
    Jedan prikaz za sve module u real-time.
    """
    from datetime import timedelta

    from django.core.cache import cache
    from django.db.models import Sum

    from core.company_utils import get_user_company

    company = get_user_company(request)
    now = timezone.now()
    today = now.date()
    CACHE_TTL = 45

    # ── WORK ORDERS ──
    work_orders = cache.get(f'borg_hub_wo_{company.pk}')
    wo_stats = cache.get(f'borg_hub_wo_stats_{company.pk}')
    if work_orders is None:
        try:
            from work_orders.models import WorkOrder
            wo_qs = WorkOrder.objects.filter(company=company)
            work_orders = {
                'draft':       list(wo_qs.filter(status='draft').select_related('client').order_by('-created_at')[:10]),
                'in_progress': list(wo_qs.filter(status='in_progress').select_related('client').order_by('-created_at')[:10]),
                'completed':   list(wo_qs.filter(status='completed', date=today).select_related('client')[:5]),
            }
            wo_stats = {
                'open': wo_qs.filter(status__in=['draft', 'in_progress']).count(),
                'completed_today': wo_qs.filter(status='completed', date=today).count(),
            }
        except DatabaseError:
            work_orders = {}
            wo_stats = {}
        cache.set(f'borg_hub_wo_{company.pk}', work_orders, CACHE_TTL)
        cache.set(f'borg_hub_wo_stats_{company.pk}', wo_stats, CACHE_TTL)

    # ── RECENT ACTIVITY ──
    try:
        recent_activity = list(CardActivity.objects.select_related('user').order_by('-created_at')[:20])
    except DatabaseError:
        recent_activity = []

    # ── EXPERIENCES ──
    upcoming_schedules = []
    pending_bookings = []
    exp_stats = {}
    try:
        from experiences.models import ExperienceBooking, ExperienceSchedule
        upcoming_schedules = list(ExperienceSchedule.objects.filter(
            experience__company=company,
            date__gte=today,
            date__lte=today + timedelta(days=7),
            status='open',
        ).select_related('experience').order_by('date', 'time_from')[:10])
        pending_bookings = list(ExperienceBooking.objects.filter(
            schedule__experience__company=company,
            status='pending',
        ).select_related('schedule__experience')[:10])
        exp_stats = {
            'upcoming': len(upcoming_schedules),
            'pending_payment': len(pending_bookings),
        }
    except DatabaseError:
        pass

    # ── BURZA ──
    burza_active = []
    try:
        from burza.models import ProjectLead
        burza_active = list(ProjectLead.objects.filter(
            company=company,
            status__in=['NOVI_UPIT', 'INTERNA_PROCJENA', 'NA_BURZI'],
        ).order_by('-created_at')[:5])
    except DatabaseError:
        pass

    # ── FENIX SIGNALS ──
    alerts = []
    try:
        from limit_connect_ai.models_signal import FenixSignal
        alerts = list(FenixSignal.objects.filter(
            status__in=['new', 'acknowledged'],
        ).order_by('priority', '-created_at')[:5])
    except DatabaseError:
        pass

    # ── INVOICING ──
    unpaid_invoices = []
    overdue_count = 0
    try:
        from invoicing.models import Invoice
        unpaid_invoices = list(Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'OVERDUE'],
        ).order_by('due_date')[:8])
        overdue_count = Invoice.objects.filter(
            company=company, status='OVERDUE',
        ).count()
    except DatabaseError:
        pass

    # ── POS DANAS ──
    pos_today_count = 0
    pos_today_revenue = 0
    try:
        from pos.models import POSReceipt
        pos_qs = POSReceipt.objects.filter(
            company=company, created_at__date=today,
        )
        pos_today_count = pos_qs.count()
        pos_today_revenue = pos_qs.aggregate(s=Sum('total'))['s'] or 0
    except DatabaseError:
        pass

    # ── INTERVENTIONS ──
    interventions_active = []
    try:
        from interventions.models import HitnaIntervencija
        interventions_active = list(HitnaIntervencija.objects.filter(
            company=company,
        ).exclude(
            status__in=['RIJESENO', 'FAKTURIRANO'],
        ).select_related('assigned_to').order_by('created_at')[:5])
    except DatabaseError:
        pass

    return render(request, 'borg_ops/hub.html', {
        'work_orders': work_orders,
        'wo_stats': wo_stats,
        'recent_activity': recent_activity,
        'upcoming_schedules': upcoming_schedules,
        'pending_bookings': pending_bookings,
        'exp_stats': exp_stats,
        'burza_active': burza_active,
        'alerts': alerts,
        'unpaid_invoices': unpaid_invoices,
        'overdue_count': overdue_count,
        'pos_today_count': pos_today_count,
        'pos_today_revenue': pos_today_revenue,
        'interventions': interventions_active,
        'now': now,
        'today': today,
    })
