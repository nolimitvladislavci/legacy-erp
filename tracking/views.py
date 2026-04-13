import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from delivery.models import ConsolidatedDelivery, SensorReading

from .models import TrackedItem, TrackingStatus


def tracking_status_api(request, token):
    """GET public status by token - no auth required."""
    item = get_object_or_404(TrackedItem, public_token=token)
    status = item.current_status
    return JsonResponse(
        {
            "ok": True,
            "tracking_type": item.tracking_type,
            "status": status.name if status else None,
            "status_color": status.color if status else None,
            "status_icon": status.icon if status else None,
            "latitude": float(item.latitude) if item.latitude else None,
            "longitude": float(item.longitude) if item.longitude else None,
            "updated_at": item.updated_at.isoformat(),
        }
    )


def tracking_events_api(request, token):
    """GET event history by token - no auth required."""
    item = get_object_or_404(TrackedItem, public_token=token)
    events = item.events.select_related("status").order_by("created_at")
    return JsonResponse(
        {
            "ok": True,
            "events": [
                {
                    "status": e.status.name,
                    "color": e.status.color,
                    "icon": e.status.icon,
                    "note": e.note,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
        }
    )


@login_required
@require_POST
def tracking_update(request, pk):
    """Staff status update for a tracked item."""
    item = get_object_or_404(TrackedItem, pk=pk)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    status_id = data.get("status_id")
    note = data.get("note", "")
    if not status_id:
        return JsonResponse({"ok": False, "error": "status_id required"}, status=400)
    new_status = get_object_or_404(TrackingStatus, pk=status_id)
    item.update_status(new_status, user=request.user, note=note)
    return JsonResponse({"ok": True, "status": new_status.name})


@login_required
def tracking_dashboard(request):
    """Dashboard listing all tracked items."""
    items = TrackedItem.objects.select_related("current_status", "content_type").order_by("-updated_at")
    statuses = TrackingStatus.objects.all().order_by("tracking_type", "order")
    return render(
        request,
        "tracking/dashboard.html",
        {
            "items": items,
            "statuses": statuses,
        },
    )


@login_required
def shipment_update(request, pk):
    """Update logistics fields + status for a shipment TrackedItem."""
    item = get_object_or_404(TrackedItem, pk=pk, tracking_type="shipment")
    if request.method == "POST":
        item.driver_name = request.POST.get("driver_name", "").strip()
        item.vehicle_plate = request.POST.get("vehicle_plate", "").strip()
        item.tracking_url = request.POST.get("tracking_url", "").strip()
        dispatched = request.POST.get("dispatched_at", "").strip()
        delivered = request.POST.get("delivered_at", "").strip()
        from django.utils.dateparse import parse_datetime

        if dispatched:
            item.dispatched_at = parse_datetime(dispatched)
        if delivered:
            item.delivered_at = parse_datetime(delivered)
        new_status_slug = request.POST.get("status_slug", "").strip()
        if new_status_slug:
            st = TrackingStatus.objects.filter(tracking_type="shipment", slug=new_status_slug).first()
            if st:
                item.update_status(st, user=request.user, note=request.POST.get("note", ""))
        item.save()
        from django.contrib import messages
        from django.utils.translation import gettext as _

        messages.success(request, _("Tracking ažuriran."))
    return redirect(request.META.get("HTTP_REFERER", "/tracking/"))


def tracking_public(request, token):
    """Public shipment tracking page - no auth required."""
    item = get_object_or_404(TrackedItem, public_token=token, tracking_type="shipment")
    events = item.events.select_related("status").order_by("created_at")
    # Try to resolve the linked document name
    doc_label = None
    try:
        doc = item.content_object
        doc_label = str(doc) if doc else None
    except (ValueError, TypeError):
        pass

    # Cold chain data
    cold_chain = None
    try:
        cd = ConsolidatedDelivery.objects.get(tracked_item=item)
        if cd.requires_cold_chain:
            readings = SensorReading.objects.filter(consolidated_delivery=cd).order_by("-timestamp")[:10]
            if not readings.exists() and cd.cold_chain_zone:
                readings = cd.cold_chain_zone.sensor_readings.order_by("-timestamp")[:10]
            if readings.exists():
                from django.db.models import Max, Min

                latest = readings.first()
                agg = readings.aggregate(
                    min_temp=Min("temperature"),
                    max_temp=Max("temperature"),
                )
                zone = cd.cold_chain_zone
                in_range = True
                if zone:
                    in_range = zone.target_min_temp <= latest.temperature <= zone.target_max_temp
                cold_chain = {
                    "current_temp": latest.temperature,
                    "last_reading": latest.timestamp,
                    "min_temp": agg["min_temp"],
                    "max_temp": agg["max_temp"],
                    "target_min": zone.target_min_temp if zone else None,
                    "target_max": zone.target_max_temp if zone else None,
                    "status": "ok" if in_range else "alert",
                    "zone_name": zone.name if zone else None,
                }
    except ConsolidatedDelivery.DoesNotExist:
        pass

    # Consolidated delivery info
    consolidated = None
    try:
        cd = ConsolidatedDelivery.objects.get(tracked_item=item)
        consolidated = cd
    except ConsolidatedDelivery.DoesNotExist:
        pass

    return render(
        request,
        "tracking/public_shipment.html",
        {
            "item": item,
            "events": events,
            "doc_label": doc_label,
            "cold_chain": cold_chain,
            "consolidated": consolidated,
        },
    )
