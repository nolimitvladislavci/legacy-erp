"""
Company Command Center — Tab views for HTMX partial loading.
Each tab has its own view that returns a fragment template.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.db import DatabaseError

from accounts.models import UserProfile
from .models import Company, CompanyBranch, CompanyModuleConfig

logger = logging.getLogger(__name__)


def _get_company_context(request):
    """Build common context for all settings tabs."""
    try:
        profile = request.user.profile
        company = profile.company
    except (AttributeError, UserProfile.DoesNotExist):
        return None, None, {}

    if not company:
        return profile, None, {}

    employees = UserProfile.objects.filter(company=company).select_related("user")
    branches = company.branches.all()
    sub = company.subscriptions.filter(is_active=True).select_related("pricing_plan").first()

    usage = {
        "users": employees.count(),
        "locations": branches.filter(is_active=True).count(),
        "invoices": 0,
    }
    try:
        from invoicing.models import Invoice
        usage["invoices"] = Invoice.objects.filter(company=company).count()
    except (DatabaseError, Exception):
        pass

    # Module info
    try:
        module_config = CompanyModuleConfig.objects.get(company=company)
        enabled_modules = module_config.enabled_modules or []
    except CompanyModuleConfig.DoesNotExist:
        enabled_modules = []

    from companies.module_registry import MODULES, CATEGORIES, TIER_META
    module_count = len(enabled_modules)

    ctx = {
        "company": company,
        "profile": profile,
        "employees": employees,
        "branches": branches,
        "subscription": sub,
        "usage": usage,
        "module_count": module_count,
        "settings_data": company.settings or {},
        "country_choices": Company.Country.choices,
        "branch_types": CompanyBranch.BRANCH_TYPES,
        "role_choices": [r for r in UserProfile.ROLE_CHOICES if r[0] != "superadmin"],
    }
    return profile, company, ctx


def _modules_context(company, ctx):
    """Build modules grid context with tier/lock info."""
    from companies.module_registry import MODULES, CATEGORIES, TIER_META

    sub = ctx.get("subscription")
    current_tier = "free"
    if sub and sub.pricing_plan:
        slug = sub.pricing_plan.slug
        if "enterprise" in slug:
            current_tier = "enterprise"
        elif "pro" in slug:
            current_tier = "pro"
        elif "starter" in slug:
            current_tier = "starter"

    tier_order = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3, "vertical": 2}

    try:
        module_config = CompanyModuleConfig.objects.get(company=company)
        enabled_ids = set(module_config.enabled_modules or [])
        ai_recommended_ids = set(module_config.ai_recommended or [])
    except CompanyModuleConfig.DoesNotExist:
        enabled_ids = set()
        ai_recommended_ids = set()

    all_modules = []
    for mod in MODULES:
        tier = mod.get("tier", "free")
        tier_meta = TIER_META.get(tier, {})
        is_locked = tier_order.get(tier, 0) > tier_order.get(current_tier, 0)

        all_modules.append({
            "id": mod["id"],
            "name": mod["name"],
            "icon": mod.get("icon", "fa-puzzle-piece"),
            "category": mod.get("category", "core"),
            "category_name": CATEGORIES.get(mod.get("category", ""), {}).get("name", ""),
            "description": mod.get("description", ""),
            "url_prefix": mod.get("url_prefix", ""),
            "tier": tier,
            "tier_name": tier_meta.get("name", tier),
            "tier_color": tier_meta.get("color", "#666"),
            "is_enabled": mod["id"] in enabled_ids,
            "is_locked": is_locked,
            "always_on": mod.get("always_on", False),
        })

    ai_recommended = [m for m in all_modules if m["id"] in ai_recommended_ids and not m["is_enabled"]]

    ctx.update({
        "all_modules": all_modules,
        "categories": CATEGORIES,
        "enabled_count": len(enabled_ids),
        "free_count": sum(1 for m in all_modules if m["tier"] == "free"),
        "available_count": sum(1 for m in all_modules if not m["is_locked"]),
        "locked_count": sum(1 for m in all_modules if m["is_locked"]),
        "ai_recommended": ai_recommended[:5],
    })
    return ctx


def _subscription_context(company, ctx):
    """Build subscription/plan comparison context."""
    from registration.models import PricingPlan
    all_plans = PricingPlan.objects.filter(is_active=True).order_by("sort_order")

    sub = ctx.get("subscription")
    current_plan_slug = ""
    current_plan_price = 0
    plan_limits = {}
    if sub and sub.pricing_plan:
        current_plan_slug = sub.pricing_plan.slug
        current_plan_price = sub.pricing_plan.price_monthly
        plan_limits = {
            "max_users": sub.pricing_plan.max_users,
            "max_invoices": sub.pricing_plan.max_invoices_per_month,
            "storage_mb": sub.pricing_plan.storage_mb,
        }

    ctx.update({
        "all_plans": all_plans,
        "current_plan_slug": current_plan_slug,
        "current_plan_price": current_plan_price,
        "plan_limits": plan_limits,
    })
    return ctx


@login_required
def settings_tab(request, tab_name):
    """HTMX endpoint: returns partial template for a single tab."""
    profile, company, ctx = _get_company_context(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=403)

    ctx["tab"] = tab_name

    # Tab-specific context
    if tab_name == "modules":
        ctx = _modules_context(company, ctx)
    elif tab_name == "subscription":
        ctx = _subscription_context(company, ctx)
    elif tab_name == "fiscal":
        try:
            from invoicing.fiscal_models import FiscalCertificate
            from django.utils import timezone as _tz
            certs = list(FiscalCertificate.objects.filter(company=company).select_related('location').order_by('-uploaded_at'))
            for c in certs:
                c.is_expired = c.valid_until and c.valid_until < _tz.now()
            ctx["fiscal_certs"] = certs
        except Exception:
            ctx["fiscal_certs"] = []

    template_map = {
        "profile": "companies/settings/_profile.html",
        "config": "companies/settings/_config.html",
        "employees": "companies/settings/_employees.html",
        "branches": "companies/settings/_branches.html",
        "fiscal": "companies/settings/_fiscal.html",
        "subscription": "companies/settings/_subscription.html",
        "modules": "companies/settings/_modules.html",
        "website": "companies/settings/_website.html",
        "webshop": "companies/settings/_webshop.html",
        "booking": "companies/settings/_booking.html",
        "integrations": "companies/settings/_integrations.html",
        "ai": "companies/settings/_ai.html",
    }

    template = template_map.get(tab_name, "companies/settings/_profile.html")
    return render(request, template, ctx)


@login_required
def toggle_module(request):
    """HTMX endpoint: toggle a module on/off."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        profile = request.user.profile
        company = profile.company
    except (AttributeError, UserProfile.DoesNotExist):
        return JsonResponse({"error": "No company"}, status=403)

    module_id = request.POST.get("module_id", "")
    if not module_id:
        return JsonResponse({"error": "No module_id"}, status=400)

    config, created = CompanyModuleConfig.objects.get_or_create(
        company=company,
        defaults={"enabled_modules": [], "sidebar_order": []}
    )

    modules = list(config.enabled_modules or [])
    if module_id in modules:
        modules.remove(module_id)
        action = "disabled"
    else:
        modules.append(module_id)
        action = "enabled"

    config.enabled_modules = modules
    config.save(update_fields=["enabled_modules", "updated_at"])

    return JsonResponse({"status": "ok", "action": action, "module_id": module_id})
