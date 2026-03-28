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

    return render(request, 'borg_ops/operations_dashboard.html', {
        'sla_alerts': sorted(sla_alerts, key=lambda x: -x['minutes']),
        'interventions': interventions_active,
        'work_orders': wo_active,
        'leads': leads_open,
        'signal_stats': signal_stats,
        'now': now,
    })
