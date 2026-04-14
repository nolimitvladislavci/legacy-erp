"""
Umbrella Client Enrichment — EU #1 Innovation Layer

Computes urgency score, deadline radar, and AI priority queue
for each umbrella child company. Injected into umbrella_dashboard context.
"""

import logging
from datetime import timedelta

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)


def enrich_children_data(children_data, umbrella_company):
    """Add urgency_score, deadline_info, and priority sorting to children_data.

    Returns the same list, mutated with extra keys, sorted by urgency (most urgent first).
    """
    today = timezone.now().date()
    soon = today + timedelta(days=7)

    child_ids = [cd["company"].pk for cd in children_data]

    # ── 1. Upcoming tax deadlines per company ──
    deadline_map = {}  # company_id -> {next_deadline, overdue_count, upcoming_count, label}
    try:
        from konto.models import TaxDeadline

        deadlines = TaxDeadline.objects.filter(
            company_id__in=child_ids,
            is_completed=False,
        ).order_by("deadline_date")

        for dl in deadlines:
            cid = dl.company_id
            if cid not in deadline_map:
                deadline_map[cid] = {
                    "next_deadline": None,
                    "next_label": "",
                    "overdue_count": 0,
                    "upcoming_count": 0,
                }
            info = deadline_map[cid]
            if dl.deadline_date < today:
                info["overdue_count"] += 1
            elif dl.deadline_date <= soon:
                info["upcoming_count"] += 1
            if info["next_deadline"] is None or dl.deadline_date < info["next_deadline"]:
                info["next_deadline"] = dl.deadline_date
                info["next_label"] = dl.filing_type or "Rok"
    except (DatabaseError, ImportError):
        pass

    # Also check edik_taxcalendar
    try:
        from edik.models import TaxCalendar

        for tc in TaxCalendar.objects.filter(
            company_id__in=child_ids,
            is_completed=False,
        ).order_by("deadline"):
            cid = tc.company_id
            if cid not in deadline_map:
                deadline_map[cid] = {
                    "next_deadline": None,
                    "next_label": "",
                    "overdue_count": 0,
                    "upcoming_count": 0,
                }
            info = deadline_map[cid]
            if tc.deadline < today:
                info["overdue_count"] += 1
            elif tc.deadline <= soon:
                info["upcoming_count"] += 1
            if info["next_deadline"] is None or tc.deadline < info["next_deadline"]:
                info["next_deadline"] = tc.deadline
                info["next_label"] = getattr(tc, "form_type", None) or "Porez"
    except (DatabaseError, ImportError):
        pass

    # ── 2. Health scores (already computed) ──
    health_map = {}
    try:
        from companies.models import ClientHealthScore

        for hs in ClientHealthScore.objects.filter(umbrella_parent=umbrella_company):
            health_map[hs.company_id] = hs
    except (DatabaseError, ImportError):
        pass

    # ── 3. Overdue invoices per company ──
    overdue_map = {}
    try:
        from django.db.models import Count

        from invoicing.models import Invoice

        for row in (
            Invoice.objects.filter(company_id__in=child_ids, status="OVERDUE")
            .values("company_id")
            .annotate(cnt=Count("id"))
        ):
            overdue_map[row["company_id"]] = row["cnt"]
    except (DatabaseError, ImportError):
        pass

    # ── 4. Compute urgency score per child ──
    for cd in children_data:
        cid = cd["company"].pk
        urgency = 0
        badges = []

        # Deadline urgency
        dl_info = deadline_map.get(cid)
        if dl_info:
            cd["deadline_info"] = dl_info
            if dl_info["overdue_count"] > 0:
                urgency += 100 * dl_info["overdue_count"]
                days_over = (
                    (today - dl_info["next_deadline"]).days
                    if dl_info["next_deadline"] and dl_info["next_deadline"] < today
                    else 0
                )
                badges.append(
                    {
                        "type": "danger",
                        "icon": "exclamation-triangle",
                        "text": f"Rok prošao {days_over}d"
                        if days_over
                        else f"{dl_info['overdue_count']} prekoračena roka",
                    }
                )
            elif dl_info["upcoming_count"] > 0:
                days_until = (dl_info["next_deadline"] - today).days if dl_info["next_deadline"] else 7
                urgency += max(0, 50 - days_until * 5)
                badges.append(
                    {
                        "type": "warning",
                        "icon": "clock",
                        "text": f"{dl_info['next_label']} za {days_until}d",
                    }
                )
        else:
            cd["deadline_info"] = None

        # Overdue invoices
        overdue = overdue_map.get(cid, 0)
        if overdue:
            urgency += overdue * 15
            badges.append(
                {
                    "type": "danger",
                    "icon": "file-invoice",
                    "text": f"{overdue} dospjelih",
                }
            )

        # Health score
        hs = health_map.get(cid)
        if hs:
            if hs.status == "red":
                urgency += 30
            elif hs.status == "yellow":
                urgency += 10
            if hs.days_since_last_activity > 30:
                badges.append(
                    {
                        "type": "muted",
                        "icon": "hourglass-half",
                        "text": f"{hs.days_since_last_activity}d neaktivno",
                    }
                )

        # Revenue as tiebreaker (higher revenue = slightly higher priority)
        urgency += min(10, cd.get("total_revenue", 0) / 1000)

        cd["urgency"] = round(urgency, 1)
        cd["urgency_badges"] = badges

    # ── 5. Sort by urgency (highest first) ──
    children_data.sort(key=lambda cd: cd["urgency"], reverse=True)

    # ── 6. Find "Start My Day" candidate ──
    start_my_day = None
    for cd in children_data:
        if cd["urgency"] > 0:
            start_my_day = cd
            break

    return children_data, start_my_day
