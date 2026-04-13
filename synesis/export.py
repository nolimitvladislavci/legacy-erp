"""
synesis/export.py — Export API for reverse sync (ERP → Synesis MDB).

GET /api/synesis/export/{token}/ → returns JSON with items/partners to write back to Synesis.
Each record has an 'action' field: 'update' or 'insert'.
The sync script on Windows reads this and writes into Storage.mdb.
"""
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt


# CSRF exempt: token-authenticated API endpoint
@csrf_exempt
def synesis_export_api(request, token):
    """
    GET /api/synesis/export/{token}/
    Returns pending changes to push back to Synesis.

    Response:
    {
        "items": [
            {"action": "update", "synesis_id": "123", "fields": {"ITEM_PRICE": 5.50, "ITEM_NETPRICE": 4.40}},
            {"action": "insert", "fields": {"ITEM_NAME": "Novi artikl", "ITEM_PRICE": 10.00, ...}},
        ],
        "partners": [
            {"action": "update", "synesis_id": "456", "fields": {"PARTNER_DISCOUNTRATE": 15.0}},
        ],
        "timestamp": "2026-03-06T15:30:00Z"
    }
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    from synesis.models import SynesisConfig
    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=401)

    company = cfg.company

    # Collect pending exports
    items_export = _export_items(company)
    partners_export = _export_partners(company)
    calculations_export = _export_calculations(company)

    # Mark as exported
    from synesis.models import SynesisExportQueue
    SynesisExportQueue.objects.filter(
        company=company, is_exported=False
    ).update(is_exported=True, exported_at=timezone.now())

    pkv_export = _export_pkv(company)

    return JsonResponse({
        "items": items_export,
        "partners": partners_export,
        "calculations": calculations_export,
        "pkv": pkv_export,
        "timestamp": timezone.now().isoformat(),
        "total": len(items_export) + len(partners_export) + len(calculations_export) + len(pkv_export),
    })


@csrf_exempt
def synesis_export_confirm(request, token):
    """
    POST /api/synesis/export/{token}/confirm/
    Client confirms which records were successfully written to MDB.
    Body: {"confirmed_ids": [1, 2, 3]}
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    from synesis.models import SynesisConfig, SynesisExportQueue
    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=401)

    try:
        body = json.loads(request.body)
        confirmed = body.get("confirmed_ids", [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    count = SynesisExportQueue.objects.filter(
        company=cfg.company, pk__in=confirmed
    ).update(is_confirmed=True, confirmed_at=timezone.now())

    return JsonResponse({"confirmed": count})


def _export_items(company):
    """Get pending item changes to push to Synesis."""
    from synesis.models import SynesisExportQueue
    pending = SynesisExportQueue.objects.filter(
        company=company, export_type='item', is_exported=False
    ).order_by('created_at')

    results = []
    for q in pending:
        entry = {
            "queue_id": q.pk,
            "action": q.action,
            "fields": q.payload,
        }
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results


def _export_partners(company):
    """Get pending partner changes to push to Synesis."""
    from synesis.models import SynesisExportQueue
    pending = SynesisExportQueue.objects.filter(
        company=company, export_type='partner', is_exported=False
    ).order_by('created_at')

    results = []
    for q in pending:
        entry = {
            "queue_id": q.pk,
            "action": q.action,
            "fields": q.payload,
        }
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results

def _export_calculations(company):
    """Get pending calculation exports to push to Synesis."""
    from synesis.models import SynesisExportQueue
    pending = SynesisExportQueue.objects.filter(
        company=company, export_type='calculation', is_exported=False
    ).order_by('created_at')
    results = []
    for q in pending:
        entry = {
            "queue_id": q.pk,
            "action": q.action,
            "erp_object_id": q.erp_object_id,
            "description": q.description,
            "fields": q.payload,
        }
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results


def _export_pkv(company):
    """Get pending PKV exports to push to Synesis RETAIL table."""
    from synesis.models import SynesisExportQueue
    pending = SynesisExportQueue.objects.filter(
        company=company, export_type='pkv', is_exported=False
    ).order_by('created_at')
    results = []
    for q in pending:
        entry = {
            "queue_id": q.pk,
            "action":   q.action,
            "erp_object_id": q.erp_object_id,
            "description":   q.description,
            "fields":        q.payload,
        }
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results
