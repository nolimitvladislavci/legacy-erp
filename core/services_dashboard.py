"""
Core business logic — dashboard statistics, impersonation, health checks.

Pure functions that aggregate data across modules.
No request/response dependency (except impersonation which needs session).
"""

import logging
from datetime import timedelta

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Company Dashboard Stats ─────────────────────────────────


def get_company_dashboard_stats(company, user) -> dict:
    """
    Aggregate all dashboard statistics for a company.
    Returns dict with all widget data.
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    stats = {
        "company": company,
        "today": today,
    }

    stats.update(_invoice_stats(company, month_start))
    stats.update(_worktime_stats(user, week_start, month_start))
    stats.update(_project_stats(company))
    stats.update(_partner_stats(company))
    stats.update(_finance_stats(company, month_start))
    stats.update(_appointment_stats(company, today, month_start))
    stats.update(_pos_stats(today))

    return stats


def _invoice_stats(company, month_start) -> dict:
    """Invoice aggregation for dashboard."""
    try:
        from invoicing.models import Invoice

        qs = Invoice.objects.all()
        if company:
            qs = qs.filter(company=company)

        return {
            "total_invoiced": qs.filter(doctype="R", status__in=("SENT", "PAID", "UNPAID", "OVERDUE")).aggregate(
                s=__import__("django.db.models", fromlist=["Sum"]).Sum("total")
            )["s"]
            or 0,
            "unpaid": qs.filter(doctype="R", status__in=("UNPAID", "OVERDUE")).aggregate(
                s=__import__("django.db.models", fromlist=["Sum"]).Sum("total")
            )["s"]
            or 0,
            "paid_month": qs.filter(doctype="R", status="PAID", date_issued__date__gte=month_start).aggregate(
                s=__import__("django.db.models", fromlist=["Sum"]).Sum("total")
            )["s"]
            or 0,
            "recent_invoices": list(qs.filter(doctype="R").select_related("company").order_by("-date_issued")[:8]),
            "pending_offers": qs.filter(doctype="PO", status__in=("DRAFT", "SENT")).count(),
        }
    except DatabaseError as e:
        logger.warning("Invoice stats failed: %s", e)
        return {"total_invoiced": 0, "unpaid": 0, "paid_month": 0, "recent_invoices": [], "pending_offers": 0}


def _worktime_stats(user, week_start, month_start) -> dict:
    """Worktime aggregation."""
    try:
        from django.db.models import Sum

        from worktime.models import TimeEntry

        qs = TimeEntry.objects.filter(user=user)
        return {
            "hours_week": qs.filter(date__gte=week_start).aggregate(s=Sum("duration"))["s"] or 0,
            "hours_month": qs.filter(date__gte=month_start).aggregate(s=Sum("duration"))["s"] or 0,
            "recent_entries": list(qs.select_related("project", "user").order_by("-date")[:5]),
        }
    except DatabaseError as e:
        logger.warning("Worktime stats failed: %s", e)
        return {"hours_week": 0, "hours_month": 0, "recent_entries": []}


def _project_stats(company) -> dict:
    """Project aggregation."""
    try:
        from projects.models import Project

        qs = Project.objects.all()
        if company:
            qs = qs.filter(company=company)
        return {
            "projects": list(
                qs.filter(status__in=("active", "in_progress", "open")).select_related("company").order_by("-id")[:5]
            ),
            "total_projects": qs.exclude(status__in=("completed", "cancelled")).count(),
        }
    except DatabaseError as e:
        logger.warning("Project stats failed: %s", e)
        return {"projects": [], "total_projects": 0}


def _partner_stats(company) -> dict:
    """Partner count."""
    try:
        from partners.models import Partner

        qs = Partner.objects.all()
        if company:
            qs = qs.filter(company=company)
        return {"total_partners": qs.count()}
    except DatabaseError as e:
        logger.warning("Partner stats failed: %s", e)
        return {"total_partners": 0}


def _finance_stats(company, month_start) -> dict:
    """Finance aggregation."""
    try:
        from django.db.models import Sum

        from finance.models import Transaction

        qs = Transaction.objects.all()
        if company:
            qs = qs.filter(company=company)

        income = qs.filter(direction="income", date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0
        expense = qs.filter(direction="expense", date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0
        return {
            "income_month": income,
            "expense_month": expense,
            "cashflow_month": income - expense,
        }
    except DatabaseError as e:
        logger.warning("Finance stats failed: %s", e)
        return {"income_month": 0, "expense_month": 0, "cashflow_month": 0}


def _appointment_stats(company, today, month_start) -> dict:
    """Appointment aggregation."""
    try:
        from appointments.models import Appointment

        qs = Appointment.objects.filter(start_time__date=today)
        if company:
            qs = qs.filter(company=company)
        month_count = Appointment.objects.filter(start_time__date__gte=month_start)
        if company:
            month_count = month_count.filter(company=company)

        return {
            "today_appointments": list(qs.select_related("client", "service", "resource").order_by("start_time")[:8]),
            "total_appointments_month": month_count.count(),
        }
    except DatabaseError as e:
        logger.warning("Appointment stats failed: %s", e)
        return {"today_appointments": [], "total_appointments_month": 0}


def _pos_stats(today) -> dict:
    """POS revenue today."""
    try:
        from django.db.models import Sum

        from pos.models import POSReceipt

        qs = POSReceipt.objects.filter(created_at__date=today, status="paid")
        return {
            "pos_revenue_today": qs.aggregate(s=Sum("total"))["s"] or 0,
            "pos_count_today": qs.count(),
        }
    except DatabaseError as e:
        logger.warning("POS stats failed: %s", e)
        return {"pos_revenue_today": 0, "pos_count_today": 0}


# ── Superadmin Stats ────────────────────────────────────────


def get_superadmin_stats() -> dict:
    """Aggregate platform-wide statistics for superadmin."""
    from django.contrib.auth.models import User

    from companies.models import Company

    try:
        return {
            "total_users": User.objects.filter(is_active=True).count(),
            "total_companies": Company.objects.count(),
            "active_companies": Company.objects.count(),
            "companies_list": list(
                Company.objects.all().order_by("name").values("id", "name", "oib", "created_at")[:50]
            ),
        }
    except DatabaseError as e:
        logger.exception("Superadmin stats failed: %s", e)
        return {"total_users": 0, "total_companies": 0, "active_companies": 0, "companies_list": []}


# ── Impersonation ───────────────────────────────────────────


def start_impersonation(admin_user, target_company_id: int) -> dict:
    """
    Start impersonating a company. Returns session data to set.
    Raises PermissionError if user is not superadmin.
    """
    if not admin_user.is_staff:
        raise PermissionError("Samo administratori mogu koristiti impersonaciju.")

    from companies.models import Company

    target = Company.objects.get(pk=target_company_id)

    logger.info("Impersonation started: admin=%s → company=%s", admin_user.pk, target.name)

    return {
        "impersonate_company_id": target.pk,
        "impersonate_company_name": target.name,
        "original_company_id": getattr(admin_user, "profile", None) and admin_user.profile.company_id,
    }


def stop_impersonation(admin_user) -> None:
    """Stop impersonating. Logs the action."""
    logger.info("Impersonation stopped by admin=%s", admin_user.pk)
