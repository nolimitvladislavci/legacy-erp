"""Claude Doktor -- Views."""
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from companies.models import Company
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models_doktor import DiagnosisReport
from .tasks_doktor import run_clinic_diagnostics_single


@login_required
def doktor_dashboard(request, company_id=None):
    if company_id:
        company = get_object_or_404(Company, id=company_id)
    else:
        # Pronađi company via UserProfile (pravi related_name)
        from accounts.models import UserProfile
        try:
            company = UserProfile.objects.get(user=request.user).company
        except UserProfile.DoesNotExist:
            company = None
        if not company:
            return render(request, "limit_connect_ai/doktor_no_company.html")
    today = date.today()
    report = DiagnosisReport.objects.filter(company=company, report_date=today).first()
    history = list(DiagnosisReport.objects.filter(
        company=company, report_date__gte=today - timedelta(days=7), status="done"
    ).order_by("report_date").values("report_date", "overall_score", "score_delta"))
    return render(request, "limit_connect_ai/doktor_dashboard.html", {
        "company": company, "report": report, "history": history, "today": today})


@login_required
def doktor_superadmin(request):
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    today = date.today()
    reports = (DiagnosisReport.objects.filter(report_date=today, status="done")
               .select_related("company").order_by("overall_score"))
    done_ids = reports.values_list("company_id", flat=True)
    missing = Company.objects.exclude(id__in=done_ids)
    summary = {
        "total": reports.count(),
        "critical": reports.filter(overall_score__lt=50).count(),
        "moderate": reports.filter(overall_score__gte=50, overall_score__lt=80).count(),
        "good": reports.filter(overall_score__gte=80).count(),
        "missing": missing.count(),
    }
    return render(request, "limit_connect_ai/doktor_superadmin.html", {
        "reports": reports, "missing": missing, "summary": summary, "today": today})


@login_required
@require_GET
def doktor_trigger(request, company_id):
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    run_clinic_diagnostics_single.delay(str(company_id))
    return JsonResponse({"status": "dispatched", "company_id": str(company_id)})
