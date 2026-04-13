"""
Company Command Center — Full-stack tab views.
HTMX partial loading + POST handlers + AI integration.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import UserProfile

from .models import Company, CompanyBranch, CompanyModuleConfig

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  CONTEXT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════


def _get_company_context(request, profile=None, company=None):
    """Build common context for all settings tabs."""
    if not profile:
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

    try:
        module_config = CompanyModuleConfig.objects.get(company=company)
        enabled_modules = module_config.enabled_modules or []
    except CompanyModuleConfig.DoesNotExist:
        enabled_modules = []

    module_count = len(enabled_modules)

    # FINA token for integrations
    fina_token = (company.settings or {}).get("fina_infobiz_token", "")
    try:
        from partners.fina_infobiz import mask_token

        fina_masked = mask_token(fina_token) if fina_token else ""
    except ImportError:
        fina_masked = "***" if fina_token else ""

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
        "fina_token_masked": fina_masked,
        "has_fina_token": bool(fina_token),
    }
    return profile, company, ctx


def _modules_context(company, ctx):
    """Build modules grid context with tier/lock info."""
    from companies.module_registry import CATEGORIES, MODULES, TIER_META

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

        all_modules.append(
            {
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
            }
        )

    ai_recommended = [m for m in all_modules if m["id"] in ai_recommended_ids and not m["is_enabled"]]

    ctx.update(
        {
            "all_modules": all_modules,
            "categories": CATEGORIES,
            "enabled_count": len(enabled_ids),
            "free_count": sum(1 for m in all_modules if m["tier"] == "free"),
            "available_count": sum(1 for m in all_modules if not m["is_locked"]),
            "locked_count": sum(1 for m in all_modules if m["is_locked"]),
            "ai_recommended": ai_recommended[:5],
        }
    )
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

    ctx.update(
        {
            "all_plans": all_plans,
            "current_plan_slug": current_plan_slug,
            "current_plan_price": current_plan_price,
            "plan_limits": plan_limits,
        }
    )
    return ctx


def _fiscal_context(company, ctx):
    """Build fiscal tab context."""
    try:
        from invoicing.fiscal_models import FiscalCertificate

        certs = list(
            FiscalCertificate.objects.filter(company=company).select_related("location").order_by("-uploaded_at")
        )
        now = timezone.now()
        for c in certs:
            c.is_expired = c.valid_until and c.valid_until < now
        ctx["fiscal_certs"] = certs
    except Exception:
        ctx["fiscal_certs"] = []
    return ctx


def _website_context(company, ctx):
    """Build website builder context."""
    try:
        from website.models import CompanyInfo, CompanyWebsite

        ws, _ = CompanyWebsite.objects.get_or_create(company=company)
        info, _ = CompanyInfo.objects.get_or_create(company=company)
        ctx["website_obj"] = ws
        ctx["website_info"] = info
    except Exception:
        ctx["website_obj"] = None
        ctx["website_info"] = None
    return ctx


def _booking_context(company, ctx):
    """Build booking tab context."""
    try:
        from appointments.models import BookingResource, BookingService

        ctx["booking_services"] = BookingService.objects.filter(company=company).order_by("name")
        ctx["booking_resources"] = BookingResource.objects.filter(company=company).order_by("name")
    except Exception:
        ctx["booking_services"] = []
        ctx["booking_resources"] = []
    return ctx


def _ai_context(company, ctx):
    """Build AI tab context with real data."""
    try:
        from ai_assistant.models import Conversation, PatrolReport

        last_patrol = PatrolReport.objects.filter(company=company).order_by("-created_at").first()
        ctx["last_patrol"] = last_patrol
        ctx["patrol_findings"] = (
            last_patrol.findings_count if last_patrol and hasattr(last_patrol, "findings_count") else 0
        )
        ctx["ai_conversations"] = Conversation.objects.filter(company=company).count()
    except Exception:
        ctx["last_patrol"] = None
        ctx["patrol_findings"] = 0
        ctx["ai_conversations"] = 0

    try:
        from pos.models import ImprovementSuggestion

        ctx["ai_suggestions"] = list(
            ImprovementSuggestion.objects.filter(company=company, is_resolved=False).order_by("-created_at")[:5]
        )
    except Exception:
        ctx["ai_suggestions"] = []
    return ctx


def _webshop_context(company, ctx):
    """Build webshop stats context."""
    try:
        from webshop.models import Order, Product

        ctx["webshop_stats"] = {
            "products": Product.objects.filter(company=company).count(),
            "orders": Order.objects.filter(company=company).count(),
            "revenue": 0,
        }
    except Exception:
        ctx["webshop_stats"] = {"products": 0, "orders": 0, "revenue": 0}
    return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  FULL PAGE VIEW (delegated from company_settings for new tabs)
# ═══════════════════════════════════════════════════════════════════════════


def settings_full_page(request, tab, profile, company):
    """Render full settings page with tab-specific context and POST handling."""
    _, _, ctx = _get_company_context(request, profile, company)
    ctx["tab"] = tab

    # ── POST Handlers ─────────────────────────────────────────────────────
    if request.method == "POST":
        return _handle_post(request, tab, company, ctx)

    # ── GET: Build tab-specific context ───────────────────────────────────
    context_builders = {
        "modules": _modules_context,
        "subscription": _subscription_context,
        "fiscal": _fiscal_context,
        "website": _website_context,
        "booking": _booking_context,
        "ai": _ai_context,
        "webshop": _webshop_context,
    }

    builder = context_builders.get(tab)
    if builder:
        ctx = builder(company, ctx)

    return render(request, "companies/settings.html", ctx)


def _handle_post(request, tab, company, ctx):
    """Route POST requests to tab-specific handlers."""
    handlers = {
        "fiscal": _post_fiscal,
        "website": _post_website,
        "booking": _post_booking,
        "webshop": _post_webshop,
        "integrations": _post_integrations,
        "ai": _post_ai,
    }

    handler = handlers.get(tab)
    if handler:
        return handler(request, company)

    return redirect(f"/companies/settings/?tab={tab}")


# ═══════════════════════════════════════════════════════════════════════════
#  POST HANDLERS
# ═══════════════════════════════════════════════════════════════════════════


def _post_fiscal(request, company):
    """Save fiscal settings + handle certificate upload."""
    action = request.POST.get("action", "")

    if action == "upload_cert":
        cert_file = request.FILES.get("cert_file")
        cert_password = request.POST.get("cert_password", "")
        if cert_file:
            try:
                from invoicing.fiscal_models import FiscalCertificate

                FiscalCertificate.objects.create(
                    company=company,
                    certificate_file=cert_file,
                    password_hint=cert_password[:3] + "***" if cert_password else "",
                    uploaded_at=timezone.now(),
                )
                messages.success(request, _("Certifikat uspješno učitan."))
            except Exception:
                logger.exception("Certificate upload failed")
                messages.error(request, _("Greška pri učitavanju certifikata."))
        return redirect("/companies/settings/?tab=fiscal")

    # Save fiscal fields
    company.fiscal_system = request.POST.get("fiscal_system", company.fiscal_system)
    company.pdv_status = request.POST.get("pdv_status", company.pdv_status)
    company.is_vat_registered = request.POST.get("is_vat_registered") == "on"
    company.is_kleinunternehmer = request.POST.get("is_kleinunternehmer") == "on"
    company.vat_id = request.POST.get("vat_id", company.vat_id)
    company.save(
        update_fields=[
            "fiscal_system",
            "pdv_status",
            "is_vat_registered",
            "is_kleinunternehmer",
            "vat_id",
        ]
    )
    messages.success(request, _("Fiskalne postavke spremljene."))
    return redirect("/companies/settings/?tab=fiscal")


def _post_website(request, company):
    """Save website builder settings."""
    try:
        from website.models import CompanyInfo, CompanyWebsite

        ws, _ = CompanyWebsite.objects.get_or_create(company=company)
        info, _ = CompanyInfo.objects.get_or_create(company=company)

        # Website config
        ws.theme = request.POST.get("theme", ws.theme)
        ws.primary_color = request.POST.get("primary_color", ws.primary_color)
        ws.hero_text = request.POST.get("hero_text", ws.hero_text)
        ws.about_text = request.POST.get("about_text", ws.about_text)
        ws.is_published = request.POST.get("is_published") == "on"
        ws.facebook_url = request.POST.get("facebook_url", "")
        ws.instagram_url = request.POST.get("instagram_url", "")
        ws.linkedin_url = request.POST.get("linkedin_url", "")

        if "logo" in request.FILES:
            ws.logo = request.FILES["logo"]

        ws.save()

        # SEO
        info.seo_title = request.POST.get("seo_title", "")
        info.seo_description = request.POST.get("seo_description", "")
        info.seo_keywords = request.POST.get("seo_keywords", "")
        info.save()

        messages.success(request, _("Website postavke spremljene."))
    except Exception:
        logger.exception("Website save failed")
        messages.error(request, _("Greška pri spremanju website postavki."))

    return redirect("/companies/settings/?tab=website")


def _post_booking(request, company):
    """Handle booking service/resource CRUD."""
    action = request.POST.get("action", "")

    if action == "add_service":
        try:
            from appointments.models import BookingService

            BookingService.objects.create(
                company=company,
                name=request.POST.get("service_name", ""),
                duration_minutes=int(request.POST.get("duration", 30)),
                price=request.POST.get("price", 0),
                slot_duration=int(request.POST.get("slot_duration", 30)),
                is_active=True,
            )
            messages.success(request, _("Usluga dodana."))
        except (ValueError, TypeError):
            messages.error(request, _("Neispravan unos."))

    elif action == "add_resource":
        try:
            from appointments.models import BookingResource

            BookingResource.objects.create(
                company=company,
                name=request.POST.get("resource_name", ""),
                resource_type=request.POST.get("resource_type", "worker"),
                is_active=True,
            )
            messages.success(request, _("Resurs dodan."))
        except (ValueError, TypeError):
            messages.error(request, _("Neispravan unos."))

    elif action == "toggle_service":
        try:
            from appointments.models import BookingService

            svc = BookingService.objects.get(pk=request.POST.get("service_id"), company=company)
            svc.is_active = not svc.is_active
            svc.save(update_fields=["is_active"])
        except Exception:
            pass

    elif action == "toggle_resource":
        try:
            from appointments.models import BookingResource

            res = BookingResource.objects.get(pk=request.POST.get("resource_id"), company=company)
            res.is_active = not res.is_active
            res.save(update_fields=["is_active"])
        except Exception:
            pass

    elif action == "save_booking_theme":
        company.booking_theme = request.POST.get("booking_theme", "standard")
        company.save(update_fields=["booking_theme"])
        messages.success(request, _("Tema spremljena."))

    return redirect("/companies/settings/?tab=booking")


def _post_webshop(request, company):
    """Save webshop configuration."""
    s = company.settings or {}
    s["min_order"] = request.POST.get("min_order", "0")
    s["delivery_dpd"] = request.POST.get("delivery_dpd") == "on"
    s["delivery_hp"] = request.POST.get("delivery_hp") == "on"
    company.settings = s
    company.save(update_fields=["settings"])
    messages.success(request, _("Webshop postavke spremljene."))
    return redirect("/companies/settings/?tab=webshop")


def _post_integrations(request, company):
    """Save integration tokens."""
    s = company.settings or {}
    fina_token = request.POST.get("fina_infobiz_token", "").strip()
    if fina_token:
        s["fina_infobiz_token"] = fina_token
    elif "fina_infobiz_token_clear" in request.POST:
        s.pop("fina_infobiz_token", None)
    company.settings = s
    company.save(update_fields=["settings"])
    messages.success(request, _("Integracije spremljene."))
    return redirect("/companies/settings/?tab=integrations")


def _post_ai(request, company):
    """Handle AI actions."""
    action = request.POST.get("action", "")

    if action == "run_patrol":
        try:
            from ai_assistant.patrol_tasks import run_company_patrol

            run_company_patrol.delay(str(company.pk))
            messages.success(request, _("AI patrol pokrenut. Rezultati za par minuta."))
        except Exception:
            messages.info(request, _("AI patrol zadatak poslan."))

    elif action == "accept_suggestion":
        try:
            from pos.models import ImprovementSuggestion

            suggestion_id = request.POST.get("suggestion_id")
            ImprovementSuggestion.objects.filter(pk=suggestion_id, company=company).update(is_resolved=True)
        except Exception:
            pass

    elif action == "dismiss_suggestion":
        try:
            from pos.models import ImprovementSuggestion

            suggestion_id = request.POST.get("suggestion_id")
            ImprovementSuggestion.objects.filter(pk=suggestion_id, company=company).update(is_resolved=True)
        except Exception:
            pass

    return redirect("/companies/settings/?tab=ai")


# ═══════════════════════════════════════════════════════════════════════════
#  HTMX TAB ENDPOINT (partial rendering)
# ═══════════════════════════════════════════════════════════════════════════

TEMPLATE_MAP = {
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

CONTEXT_BUILDERS = {
    "modules": _modules_context,
    "subscription": _subscription_context,
    "fiscal": _fiscal_context,
    "website": _website_context,
    "booking": _booking_context,
    "ai": _ai_context,
    "webshop": _webshop_context,
}


@login_required
def settings_tab(request, tab_name):
    """HTMX endpoint: returns partial template for a single tab."""
    profile, company, ctx = _get_company_context(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=403)

    ctx["tab"] = tab_name

    builder = CONTEXT_BUILDERS.get(tab_name)
    if builder:
        ctx = builder(company, ctx)

    template = TEMPLATE_MAP.get(tab_name, "companies/settings/_profile.html")
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
        company=company, defaults={"enabled_modules": [], "sidebar_order": []}
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
