"""
Global Photo Gallery / Baustela Dashboard.

3 views: gallery_dashboard (grid), gallery_map (Leaflet), gallery_timeline (chrono).
Plus API for HTMX partials and camera widget uploads.
"""

import json
import os
import uuid

from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import ArhivaEntry

APP_LABELS = {
    "stolarija": "Stolarija",
    "delivery": "Dostava",
    "worktime": "Gradiliste",
    "production": "Proizvodnja",
    "assessment": "Inspekcija",
    "livestock": "Stocarstvo",
    "invoicing": "Fakturiranje",
    "projects": "Projekti",
    "komunalno": "Komunalno",
    "documents": "Dokumenti",
    "manual": "Rucni upload",
}

SOURCE_TYPE_ICONS = {
    "site_photo": "fa-camera",
    "before_photo": "fa-arrow-left",
    "after_photo": "fa-arrow-right",
    "delivery_proof": "fa-truck",
    "transport_photo": "fa-shipping-fast",
    "qc_photo": "fa-check-circle",
    "receipt_scan": "fa-receipt",
    "complaint_photo": "fa-exclamation-triangle",
    "animal_photo": "fa-paw",
}


def _company(request):
    try:
        return request.user.profile.company
    except AttributeError:
        return None


def _base_qs(request):
    """Filtered queryset for photo entries."""
    company = _company(request)
    if not company:
        return ArhivaEntry.objects.none()

    qs = (
        ArhivaEntry.objects.filter(
            company=company,
            content_category="photo",
        )
        .select_related("captured_by")
        .order_by("-archived_at")
    )

    # Apply filters
    app = request.GET.get("app", "")
    stype = request.GET.get("type", "")
    tag = request.GET.get("tag", "")
    addr = request.GET.get("address", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    if app:
        qs = qs.filter(source_app=app)
    if stype:
        qs = qs.filter(source_type=stype)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    if addr:
        qs = qs.filter(address__icontains=addr)
    if date_from:
        qs = qs.filter(archived_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(archived_at__date__lte=date_to)

    partner = request.GET.get("partner", "")
    if partner:
        qs = qs.filter(partner_name__icontains=partner)

    return qs


def _filter_context(request, qs):
    """Common filter context for all gallery views."""
    active_apps = list(qs.values_list("source_app", flat=True).distinct().order_by("source_app"))
    active_types = list(qs.values_list("source_type", flat=True).distinct().order_by("source_type"))

    return {
        "active_apps": [(a, APP_LABELS.get(a, a)) for a in active_apps if a],
        "active_types": active_types,
        "filters": {
            "app": request.GET.get("app", ""),
            "type": request.GET.get("type", ""),
            "tag": request.GET.get("tag", ""),
            "address": request.GET.get("address", ""),
            "from": request.GET.get("from", ""),
            "to": request.GET.get("to", ""),
        },
        "APP_LABELS": APP_LABELS,
        "SOURCE_TYPE_ICONS": SOURCE_TYPE_ICONS,
    }


# ═══════════════════════════════════════════════════════════════
# VIEW 1: Gallery Dashboard — Grid + Filters + Stats
# ═══════════════════════════════════════════════════════════════


@login_required
def gallery_dashboard(request):
    qs = _base_qs(request)
    total = qs.count()
    with_gps = qs.filter(latitude__isnull=False).count()

    # Stats by app
    from django.db.models import Count

    app_stats = dict(qs.values_list("source_app").annotate(c=Count("pk")).values_list("source_app", "c"))

    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get("page", 1))

    ctx = _filter_context(request, qs)
    ctx.update(
        {
            "page": page,
            "total": total,
            "with_gps": with_gps,
            "app_stats": app_stats,
            "tab": "dashboard",
            "page_title": "Galerija",
        }
    )
    return render(request, "documents/gallery_dashboard.html", ctx)


# ═══════════════════════════════════════════════════════════════
# VIEW 2: Gallery Map — Leaflet + GPS pins
# ═══════════════════════════════════════════════════════════════


@login_required
def gallery_map(request):
    qs = _base_qs(request)
    total = qs.count()

    # GPS points (max 500)
    points = list(
        qs.filter(latitude__isnull=False, longitude__isnull=False).values(
            "pk",
            "latitude",
            "longitude",
            "address",
            "source_app",
            "source_type",
            "archived_at",
            "thumbnail_path",
            "file_path",
        )[:500]
    )
    for p in points:
        p["archived_at"] = p["archived_at"].isoformat() if p["archived_at"] else ""

    ctx = _filter_context(request, qs)
    ctx.update(
        {
            "total": total,
            "with_gps": len(points),
            "map_points_json": json.dumps(points),
            "tab": "map",
            "page_title": "Mapa",
        }
    )
    return render(request, "documents/gallery_map.html", ctx)


# ═══════════════════════════════════════════════════════════════
# VIEW 3: Gallery Timeline — Chronological grouped by day
# ═══════════════════════════════════════════════════════════════


@login_required
def gallery_timeline(request):
    qs = _base_qs(request)
    total = qs.count()

    # Group by day (last 30 days max)
    from collections import OrderedDict
    from django.db.models.functions import TruncDate

    daily = qs.annotate(day=TruncDate("archived_at")).values("day").annotate(count=Count("pk")).order_by("-day")[:30]

    # Fetch entries per day
    days_data = OrderedDict()
    for d in daily:
        day = d["day"]
        entries = list(qs.filter(archived_at__date=day)[:12])
        days_data[day] = entries

    ctx = _filter_context(request, qs)
    ctx.update(
        {
            "total": total,
            "days_data": days_data,
            "tab": "timeline",
            "page_title": "Timeline",
        }
    )
    return render(request, "documents/gallery_timeline.html", ctx)


# ═══════════════════════════════════════════════════════════════
# API: JSON for HTMX/Leaflet + Camera Upload
# ═══════════════════════════════════════════════════════════════


@login_required
def gallery_api(request):
    """JSON API for lazy-loading gallery cards."""
    qs = _base_qs(request)
    page_num = int(request.GET.get("page", 1))
    paginator = Paginator(qs, 24)
    page = paginator.get_page(page_num)

    items = []
    for entry in page:
        items.append(
            {
                "pk": entry.pk,
                "file_path": entry.file_path,
                "thumbnail_path": entry.thumbnail_path,
                "source_app": entry.source_app,
                "source_type": entry.source_type,
                "tags": entry.tags or [],
                "address": entry.address,
                "archived_at": entry.archived_at.isoformat(),
                "captured_by": str(entry.captured_by) if entry.captured_by else "",
                "latitude": entry.latitude,
                "longitude": entry.longitude,
            }
        )
    return JsonResponse(
        {
            "items": items,
            "has_next": page.has_next(),
            "total": paginator.count,
        }
    )


@login_required
def gallery_upload(request):
    """Camera widget upload endpoint."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    company = _company(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=403)

    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "No photo"}, status=400)

    # Save file
    now = timezone.now()
    upload_dir = f"arhiva/uploads/{now.year}/{now.month:02d}"
    abs_dir = os.path.join(django_settings.MEDIA_ROOT, upload_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex[:12]}_{photo.name}"
    filepath = os.path.join(upload_dir, filename)
    abs_path = os.path.join(django_settings.MEDIA_ROOT, filepath)

    with open(abs_path, "wb") as f:
        for chunk in photo.chunks():
            f.write(chunk)

    from documents.photo_registry import archive_photo

    lat = request.POST.get("latitude", "")
    lng = request.POST.get("longitude", "")
    tags_raw = request.POST.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else ["rucni-upload"]

    entry = archive_photo(
        company=company,
        file_path=filepath,
        source_type=request.POST.get("source_type", "site_photo"),
        source_app=request.POST.get("source_app", "manual"),
        source_model="ManualUpload",
        captured_by=request.user,
        tags=tags,
        latitude=float(lat) if lat else None,
        longitude=float(lng) if lng else None,
        address=request.POST.get("address", ""),
    )

    if entry:
        return JsonResponse(
            {
                "ok": True,
                "archive_number": entry.archive_number,
                "thumbnail": entry.thumbnail_path,
            }
        )
    return JsonResponse({"ok": False, "error": "Archive failed"}, status=500)
