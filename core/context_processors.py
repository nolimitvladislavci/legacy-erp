"""Fenix v3 — Context Processors | PLAN_003"""

from __future__ import annotations

from django.conf import settings


def company_context(request):
    """Aktivna company dostupna u svakom templateu."""
    company = getattr(request, "company", None)
    subscription = None

    if request.user.is_authenticated:
        company_id = request.session.get("active_company_id")
        if company_id:
            try:
                from companies.billing import CompanySubscription

                subscription = CompanySubscription.objects.select_related("plan").get(company_id=company_id)
            except Exception:
                pass

    return {
        "company": company,
        "active_company_id": request.session.get("active_company_id"),
        "subscription": subscription,
        "trial_banner_dismissed": request.session.get("trial_banner_dismissed", False),
    }


def ui_context(request):
    """UI konstante dostupne u svakom templateu."""
    return {
        "DEBUG": settings.DEBUG,
        "LANGUAGE_CODE": getattr(settings, "LANGUAGE_CODE", "hr"),
        "AI_ENABLED": bool(getattr(settings, "ANTHROPIC_API_KEY", "")),
    }


def failed_imports_badge(request):
    """Badge count za failed smart imports — koristi se u nav baru."""
    from django.core.cache import cache

    try:
        key = f"failed_imports:{getattr(request, 'company_id', 0)}"
        count = cache.get(key)
        if count is None:
            from documents.models import SmartImportBatch

            company = getattr(request, "company", None)
            if company:
                count = SmartImportBatch.objects.filter(company=company, status="error").count()
            else:
                count = 0
            cache.set(key, count, 300)
        return {"failed_imports_count": count}
    except Exception:
        return {"failed_imports_count": 0}
