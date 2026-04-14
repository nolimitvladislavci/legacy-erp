"""
Umbrella Innovation Views: Smart Desk + Client Pulse
EU #1 Bookkeeper Workspace Management
"""

import logging

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.company_utils import get_umbrella_home, get_user_company

logger = logging.getLogger(__name__)


@login_required
def smart_desk_dashboard(request):
    """Smart Desk: AI-driven workload analysis across bookkeeper desks."""
    from companies.models import Workspace

    home = get_umbrella_home(request)
    company = home or get_user_company(request)
    if not company or not company.is_umbrella:
        return redirect("dashboard")

    today = timezone.now().date()

    desks = Workspace.objects.filter(company=company, type="desk", is_active=True).order_by("position")

    desk_data = []
    for desk in desks:
        client_ids = list(desk.clients.values_list("pk", flat=True))
        client_count = len(client_ids)

        # Invoice count this month
        inv_count = 0
        try:
            from invoicing.models import Invoice

            inv_count = Invoice.objects.filter(company__in=client_ids, date_issued__date__gte=month_start).count()
        except (DatabaseError, ImportError):
            pass

        # Document count this month
        doc_count = 0
        try:
            from documents.models import ArhivaEntry

            doc_count = ArhivaEntry.objects.filter(company__in=client_ids, captured_at__date__gte=month_start).count()
        except (DatabaseError, ImportError):
            pass

        # Booking entries this month
        book_count = 0
        try:
            from konto.models import BookingEntry

            book_count = BookingEntry.objects.filter(company__in=client_ids, date__gte=month_start).count()
        except (DatabaseError, ImportError):
            pass

        # Weighted score: invoices*3 + documents*1 + bookings*2
        score = inv_count * 3 + doc_count * 1 + book_count * 2

        # Workers assigned
        workers = list(desk.workers.values_list("first_name", "last_name"))
        worker_names = [f"{fn} {ln}".strip() or "?" for fn, ln in workers]

        desk_data.append(
            {
                "desk": desk,
                "client_count": client_count,
                "inv_count": inv_count,
                "doc_count": doc_count,
                "book_count": book_count,
                "score": score,
                "workers": worker_names,
            }
        )

    # Calculate balance stats
    scores = [d["score"] for d in desk_data if d["score"] > 0]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0
    imbalance = max_score - min_score if scores else 0

    # AI recommendation
    recommendations = []
    if imbalance > avg_score * 0.5 and len(desk_data) > 1:
        heaviest = max(desk_data, key=lambda d: d["score"])
        lightest = min(desk_data, key=lambda d: d["score"])
        diff = heaviest["score"] - lightest["score"]
        # Find clients in heaviest desk that could be moved
        move_count = min(3, heaviest["client_count"] // 4)
        if move_count > 0:
            recommendations.append(
                {
                    "type": "rebalance",
                    "message": _(
                        "%(heavy)s ima %(diff)d bodova više od %(light)s. "
                        "Predlažemo premještaj %(n)d klijenata za ujednačenije opterećenje."
                    )
                    % {
                        "heavy": heaviest["desk"].name,
                        "diff": diff,
                        "light": lightest["desk"].name,
                        "n": move_count,
                    },
                    "from_desk": heaviest["desk"].id,
                    "to_desk": lightest["desk"].id,
                    "count": move_count,
                }
            )

    return render(
        request,
        "companies/smart_desk.html",
        {
            "company": company,
            "desk_data": desk_data,
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "imbalance": imbalance,
            "recommendations": recommendations,
            "month_label": today.strftime("%m/%Y"),
        },
    )


@login_required
def client_pulse_dashboard(request):
    """Client Pulse: real-time health overview of all umbrella children."""
    from companies.models import ClientHealthScore, Company

    home = get_umbrella_home(request)
    company = home or get_user_company(request)
    if not company or not company.is_umbrella:
        return redirect("dashboard")

    children = Company.objects.filter(umbrella_parent=company).order_by("name")

    # Ensure all children have health scores
    existing_ids = set(ClientHealthScore.objects.filter(umbrella_parent=company).values_list("company_id", flat=True))
    for child in children:
        if child.pk not in existing_ids:
            ClientHealthScore.objects.create(
                company=child,
                umbrella_parent=company,
            )

    # Get all health scores with related company
    scores = (
        ClientHealthScore.objects.filter(umbrella_parent=company).select_related("company").order_by("status", "score")
    )

    # Summary stats
    total = scores.count()
    green = scores.filter(status="green").count()
    yellow = scores.filter(status="yellow").count()
    red = scores.filter(status="red").count()

    # Group by workspace
    from companies.models import Workspace

    desks = Workspace.objects.filter(company=company, type="desk").prefetch_related("clients")
    workspace_pulse = []
    for desk in desks:
        desk_client_ids = set(desk.clients.values_list("pk", flat=True))
        desk_scores = [s for s in scores if s.company_id in desk_client_ids]
        desk_red = sum(1 for s in desk_scores if s.status == "red")
        desk_yellow = sum(1 for s in desk_scores if s.status == "yellow")
        workspace_pulse.append(
            {
                "desk": desk,
                "scores": desk_scores,
                "red_count": desk_red,
                "yellow_count": desk_yellow,
                "total": len(desk_scores),
            }
        )

    return render(
        request,
        "companies/client_pulse.html",
        {
            "company": company,
            "scores": scores,
            "total": total,
            "green": green,
            "yellow": yellow,
            "red": red,
            "workspace_pulse": workspace_pulse,
        },
    )


@login_required
def client_pulse_recalculate(request):
    """Recalculate health scores for all children (AJAX)."""

    home = get_umbrella_home(request)
    company = home or get_user_company(request)
    if not company or not company.is_umbrella:
        return JsonResponse({"error": "Not umbrella"}, status=403)

    updated = _recalculate_health_scores(company)
    return JsonResponse({"updated": updated, "status": "ok"})


def _recalculate_health_scores(umbrella):
    """Core recalculation logic — used by view and celery task."""
    from companies.models import ClientHealthScore, Company

    today = timezone.now().date()

    children = Company.objects.filter(umbrella_parent=umbrella)
    updated = 0

    for child in children:
        score, _ = ClientHealthScore.objects.get_or_create(
            company=child,
            defaults={"umbrella_parent": umbrella},
        )
        if not score.umbrella_parent_id:
            score.umbrella_parent = umbrella
            score.save(update_fields=["umbrella_parent"])

        # Overdue invoices
        try:
            from invoicing.models import Invoice

            score.overdue_invoices = Invoice.objects.filter(company=child, status="OVERDUE").count()
        except (DatabaseError, ImportError):
            score.overdue_invoices = 0

        # Days since last activity (any invoice, document, or booking)
        last_activity = None
        try:
            from invoicing.models import Invoice

            last_inv = Invoice.objects.filter(company=child).order_by("-date_issued").first()
            if last_inv and last_inv.date_issued:
                last_d = last_inv.date_issued.date() if hasattr(last_inv.date_issued, "date") else last_inv.date_issued
                if not last_activity or last_d > last_activity:
                    last_activity = last_d
        except (DatabaseError, ImportError):
            pass
        try:
            from documents.models import ArhivaEntry

            last_doc = ArhivaEntry.objects.filter(company=child).order_by("-captured_at").first()
            if last_doc and last_doc.captured_at:
                last_d = last_doc.captured_at.date()
                if not last_activity or last_d > last_activity:
                    last_activity = last_d
        except (DatabaseError, ImportError):
            pass

        if last_activity:
            score.days_since_last_activity = (today - last_activity).days
            score.last_bookkeeper_activity = timezone.make_aware(
                timezone.datetime.combine(last_activity, timezone.datetime.min.time())
            )
        else:
            score.days_since_last_activity = 999

        score.save(
            update_fields=[
                "overdue_invoices",
                "days_since_last_activity",
                "last_bookkeeper_activity",
            ]
        )
        score.recalculate()
        updated += 1

    return updated
