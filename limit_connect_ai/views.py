"""
Views for LIMIT Connect AI cockpit and missions management.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.db.models import Count, F, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company

from .models import (
    AIAgentMission,
    AIReportLog,
    ComplianceWatchItem,
    FundApplicationDraft,
)


@login_required
def ai_cockpit(request):
    """Per-company AI dashboard with POS, inventory, invoices, compliance, funds."""
    company = get_user_company(request)
    if not company:
        return render(request, "limit_connect_ai/ai_cockpit.html", {"no_company": True})

    today = timezone.now().date()
    ctx = {"company": company, "today": today}

    # POS today
    try:
        from pos.models import POSReceipt

        agg = POSReceipt.objects.filter(
            session__terminal__company=company,
            status="paid",
            paid_at__date=today,
        ).aggregate(total=Sum("total"), count=Count("id"))
        ctx["pos_revenue"] = agg["total"] or 0
        ctx["pos_count"] = agg["count"] or 0
    except DatabaseError:
        ctx["pos_revenue"] = 0
        ctx["pos_count"] = 0

    # Open invoices
    try:
        from invoicing.models import Invoice

        agg = Invoice.objects.filter(
            company=company,
            status__in=["SENT", "OVERDUE", "UNPAID"],
        ).aggregate(total=Sum("total"), count=Count("id"))
        ctx["inv_count"] = agg["count"] or 0
        ctx["inv_total"] = agg["total"] or 0
    except DatabaseError:
        ctx["inv_count"] = 0
        ctx["inv_total"] = 0

    # Low stock
    try:
        from inventory.models import InventoryItem

        ctx["low_stock"] = (
            InventoryItem.objects.filter(
                company=company,
                is_active=True,
                quantity__lte=F("min_quantity"),
            )
            .exclude(min_quantity=0)
            .count()
        )
    except DatabaseError:
        ctx["low_stock"] = 0

    # Active funds
    try:
        from intelligence.models import FundOpportunity

        ctx["active_funds"] = FundOpportunity.objects.filter(status="aktivan").count()
    except DatabaseError:
        ctx["active_funds"] = 0

    # Fund drafts for this company
    ctx["fund_drafts"] = FundApplicationDraft.objects.filter(company=company)[:5]

    # Recent reports
    ctx["recent_reports"] = AIReportLog.objects.filter(company=company)[:5]

    # Active missions count
    ctx["missions_count"] = AIAgentMission.objects.filter(company=company, is_active=True).count()

    # Compliance
    ctx["compliance_items"] = ComplianceWatchItem.objects.filter(company=company).exclude(status="compliant")[:5]
    ctx["compliance_ok"] = not ctx["compliance_items"].exists()

    return render(request, "limit_connect_ai/ai_cockpit.html", ctx)


@login_required
def ai_missions(request):
    """List, create, and toggle AI missions for the company."""
    company = get_user_company(request)
    if not company:
        return render(request, "limit_connect_ai/ai_missions.html", {"no_company": True})

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            mission_type = request.POST.get("mission_type", "daily_report")
            title = request.POST.get("title", "").strip()
            notify_channel = request.POST.get("notify_channel", "whatsapp")
            notify_target = request.POST.get("notify_target", "").strip()
            frequency = request.POST.get("frequency", "daily")

            if title:
                AIAgentMission.objects.create(
                    company=company,
                    mission_type=mission_type,
                    title=title,
                    frequency=frequency,
                    notify_channel=notify_channel,
                    notify_target=notify_target,
                    next_run=timezone.now(),
                    created_by=request.user,
                )
                messages.success(request, _("Misija kreirana."))

        elif action == "toggle":
            mission_id = request.POST.get("mission_id")
            try:
                mission = AIAgentMission.objects.get(id=mission_id, company=company)
                mission.is_active = not mission.is_active
                mission.save(update_fields=["is_active"])
                state = "aktivirana" if mission.is_active else "deaktivirana"
                messages.success(request, _("Misija {}.").format(state))
            except AIAgentMission.DoesNotExist:
                messages.error(request, _("Misija nije pronadjena."))

        return redirect("limit_connect_ai:ai_missions")

    missions = AIAgentMission.objects.filter(company=company).order_by("-created_at")
    return render(
        request,
        "limit_connect_ai/ai_missions.html",
        {
            "company": company,
            "missions": missions,
            "mission_types": AIAgentMission.MISSION_TYPES,
            "frequency_choices": AIAgentMission.FREQUENCY_CHOICES,
            "channel_choices": AIAgentMission.NOTIFY_CHANNEL_CHOICES,
        },
    )


@login_required
def ai_reports(request):
    """History of AI-generated reports for the company."""
    company = get_user_company(request)
    if not company:
        return render(request, "limit_connect_ai/ai_reports.html", {"no_company": True})

    reports = AIReportLog.objects.filter(company=company).select_related("mission")
    return render(
        request,
        "limit_connect_ai/ai_reports.html",
        {
            "company": company,
            "reports": reports,
        },
    )


@login_required
def ai_funds(request):
    """EU fund applications list for the company."""
    company = get_user_company(request)
    if not company:
        return render(request, "limit_connect_ai/ai_funds.html", {"no_company": True})

    drafts = FundApplicationDraft.objects.filter(
        company=company,
    ).select_related("fund_opportunity")

    return render(
        request,
        "limit_connect_ai/ai_funds.html",
        {
            "company": company,
            "drafts": drafts,
        },
    )
