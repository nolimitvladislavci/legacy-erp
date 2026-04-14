from celery import shared_task
from django.utils import timezone


@shared_task
def monthly_depreciation_task():
    from companies.models import Company

    from .services import run_monthly_depreciation

    today = timezone.now().date()
    results = []
    for company in Company.objects.all():
        entries = run_monthly_depreciation(company, today.year, today.month)
        if entries:
            results.append(f"{company.name}: {len(entries)}")
    return results or ["Nothing to depreciate"]
