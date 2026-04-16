"""
no_limit/views_admin.py
No-Limit Command Center — Admin panel za upravljanje portalom.
Pristup: samo superuser ili staff.
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from no_limit.models import AmbassadorApplication, CountryChapter, PartnershipLead

logger = logging.getLogger(__name__)


def _is_admin(user):
    return user.is_staff or user.is_superuser


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════


@login_required
@user_passes_test(_is_admin)
def admin_dashboard(request):
    """Glavni dashboard — pregled svega."""
    ambassadors = AmbassadorApplication.objects.all()
    chapters = CountryChapter.objects.all()
    leads = PartnershipLead.objects.all()

    stats = {
        "amb_total": ambassadors.count(),
        "amb_pending": ambassadors.filter(status="pending").count(),
        "amb_approved": ambassadors.filter(status__in=["approved", "active"]).count(),
        "amb_declined": ambassadors.filter(status="declined").count(),
        "chapters_active": chapters.filter(is_active=True).count(),
        "chapters_total": chapters.count(),
        "leads_total": leads.count(),
        "leads_new": leads.filter(status="new").count(),
        "leads_signed": leads.filter(status="signed").count(),
    }

    recent_ambassadors = ambassadors[:10]
    recent_leads = leads[:10]

    return render(
        request,
        "no_limit/admin/dashboard.html",
        {
            "stats": stats,
            "recent_ambassadors": recent_ambassadors,
            "recent_leads": recent_leads,
            "chapters": chapters,
        },
    )


# ═══════════════════════════════════════════════════════════════
#  AMBASADORI CRUD
# ═══════════════════════════════════════════════════════════════


@login_required
@user_passes_test(_is_admin)
def admin_ambassadors(request):
    """Lista svih ambasadorskih prijava."""
    status_filter = request.GET.get("status", "")
    country_filter = request.GET.get("country", "")

    qs = AmbassadorApplication.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)
    if country_filter:
        qs = qs.filter(country=country_filter)

    return render(
        request,
        "no_limit/admin/ambassadors.html",
        {
            "ambassadors": qs,
            "status_filter": status_filter,
            "country_filter": country_filter,
            "status_choices": AmbassadorApplication.STATUS_CHOICES,
            "country_choices": AmbassadorApplication.COUNTRY_CHOICES,
        },
    )


@login_required
@user_passes_test(_is_admin)
def admin_ambassador_detail(request, pk):
    """Detalji jedne prijave + akcije."""
    amb = get_object_or_404(AmbassadorApplication, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "approve":
            amb.status = "approved"
            amb.approved_at = timezone.now()
            amb.reviewed_by = request.user.get_full_name() or request.user.username
            amb.save(update_fields=["status", "approved_at", "reviewed_by", "updated_at"])
            _notify_ambassador_status(amb, "approved")
        elif action == "decline":
            amb.status = "declined"
            amb.reviewed_by = request.user.get_full_name() or request.user.username
            amb.review_notes = request.POST.get("review_notes", "")
            amb.save(update_fields=["status", "reviewed_by", "review_notes", "updated_at"])
        elif action == "activate":
            amb.status = "active"
            amb.save(update_fields=["status", "updated_at"])
        elif action == "save_notes":
            amb.review_notes = request.POST.get("review_notes", "")
            amb.save(update_fields=["review_notes", "updated_at"])

        return redirect("no_limit:admin_ambassador_detail", pk=pk)

    return render(request, "no_limit/admin/ambassador_detail.html", {"amb": amb})


def _notify_ambassador_status(amb, new_status):
    """WA notifikacija kad se status promijeni."""
    try:
        from core.whatsapp import send_whatsapp

        wa_number = getattr(settings, "IVAN_WHATSAPP_NUMBER", "")
        if wa_number:
            country = amb.get_country_display()
            send_whatsapp(
                wa_number,
                f"Ambasador {new_status}!\n{amb.full_name} ({country})\n{amb.email}",
            )
    except Exception:
        logger.exception("WA notification failed")


# ═══════════════════════════════════════════════════════════════
#  PARTNERI CRUD
# ═══════════════════════════════════════════════════════════════


@login_required
@user_passes_test(_is_admin)
def admin_leads(request):
    """Lista partnership leadova."""
    qs = PartnershipLead.objects.all()
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(
        request,
        "no_limit/admin/leads.html",
        {
            "leads": qs,
            "status_filter": status_filter,
            "status_choices": PartnershipLead.STATUS_CHOICES,
            "type_choices": PartnershipLead.TYPE_CHOICES,
        },
    )


@login_required
@user_passes_test(_is_admin)
@require_POST
def admin_lead_create(request):
    """Kreiraj novi lead."""
    PartnershipLead.objects.create(
        name=request.POST.get("name", "").strip(),
        organization=request.POST.get("organization", "").strip(),
        country=request.POST.get("country", "").strip(),
        email=request.POST.get("email", "").strip(),
        phone=request.POST.get("phone", "").strip(),
        partnership_type=request.POST.get("partnership_type", "partner"),
        notes=request.POST.get("notes", "").strip(),
        source=request.POST.get("source", "").strip(),
    )
    return redirect("no_limit:admin_leads")


@login_required
@user_passes_test(_is_admin)
@require_POST
def admin_lead_update_status(request, pk):
    """HTMX: update lead status."""
    lead = get_object_or_404(PartnershipLead, pk=pk)
    new_status = request.POST.get("status", "")
    if new_status in dict(PartnershipLead.STATUS_CHOICES):
        lead.status = new_status
        lead.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "status": lead.get_status_display()})


# ═══════════════════════════════════════════════════════════════
#  CHAPTERS
# ═══════════════════════════════════════════════════════════════


@login_required
@user_passes_test(_is_admin)
def admin_chapters(request):
    """Nacionalni ogranci."""
    chapters = CountryChapter.objects.all()

    if request.method == "POST":
        CountryChapter.objects.get_or_create(
            country=request.POST.get("country", "").strip(),
            defaults={
                "country_name": request.POST.get("country_name", "").strip(),
                "coordinator_name": request.POST.get("coordinator_name", "").strip(),
                "coordinator_email": request.POST.get("coordinator_email", "").strip(),
                "is_active": request.POST.get("is_active") == "on",
            },
        )
        return redirect("no_limit:admin_chapters")

    return render(request, "no_limit/admin/chapters.html", {"chapters": chapters})
