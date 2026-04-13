"""
companies/views_modules.py
Module picker — visual grid for enabling/disabling ERP modules.
Also: specialized module config (udruge, DVD, KUD, etc.)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from core.company_utils import get_user_company


@login_required
def module_picker(request):
    """Module picker — visual grid with toggles."""
    company = get_user_company(request)
    if not company:
        messages.error(request, _("Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika."))
        return redirect("dashboard")

    from .models import CompanyModuleConfig
    from .module_registry import MODULES, get_modules_by_category

    config, created = CompanyModuleConfig.objects.get_or_create(
        company=company, defaults={"enabled_modules": [m["id"] for m in MODULES if m.get("always_visible")]}
    )

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "save":
            enabled = request.POST.getlist("modules")
            # Always include core modules
            for m in MODULES:
                if m.get("always_visible") and m["id"] not in enabled:
                    enabled.append(m["id"])
            config.enabled_modules = enabled
            config.sidebar_order = enabled  # order = selection order
            config.save()
            messages.success(request, f"Spremljeno! {len(enabled)} modula aktivno.")
            return redirect("dashboard")

        elif action == "ai_recommend":
            recommendations = _ai_recommend(company)
            config.ai_recommended = recommendations
            config.save(update_fields=["ai_recommended"])
            return render(
                request,
                "companies/module_picker.html",
                {
                    "categories": get_modules_by_category(),
                    "config": config,
                    "ai_recommendations": recommendations,
                },
            )

    # Get counters for each module
    counters = _get_module_counters(company)

    # Inject counters into module dicts for template
    categories = get_modules_by_category()
    for cat_id, cat_data in categories.items():
        for mod in cat_data["modules"]:
            mod["counter"] = counters.get(mod["id"], 0)

    return render(
        request,
        "companies/module_picker.html",
        {
            "categories": categories,
            "config": config,
            "counters": counters,
        },
    )


@login_required
def module_toggle_api(request):
    """AJAX toggle single module on/off."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    import json

    body = json.loads(request.body)
    module_id = body.get("module_id", "")
    enabled = body.get("enabled", True)

    company = get_user_company(request)
    from .models import CompanyModuleConfig

    config, _ = CompanyModuleConfig.objects.get_or_create(company=company, defaults={"enabled_modules": []})

    if enabled and module_id not in config.enabled_modules:
        config.enabled_modules.append(module_id)
    elif not enabled and module_id in config.enabled_modules:
        config.enabled_modules.remove(module_id)

    config.sidebar_order = config.enabled_modules
    config.save()

    return JsonResponse({"ok": True, "enabled": config.enabled_modules})


# ═══════════════════════════════════════════════════════════════════════════
#  Specialized Module Config (udruge, DVD, KUD, ribolov, etc.)
# ═══════════════════════════════════════════════════════════════════════════


@login_required
def company_modules(request):
    """
    Admin panel for specialized modules — toggle switches per business type.
    URL: /companies/modules/config/
    Template: templates/companies/module_config.html
    """
    company = get_user_company(request)
    if not company:
        messages.error(request, _("Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika."))
        return redirect("dashboard")

    from core.module_registry import (
        MODULE_REGISTRY,
        activate_module,
        auto_detect_modules,
        get_active_modules,
        get_all_modules_grouped,
    )

    from .models import CompanyModuleConfig

    config, _ = CompanyModuleConfig.objects.get_or_create(company=company, defaults={"enabled_modules": []})

    ai_detected = None

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "save":
            # Get selected modules from form
            selected = set(request.POST.getlist("modules"))

            # Ensure always-on modules stay active
            for key, mod in MODULE_REGISTRY.items():
                if mod.get("always_on") and company.business_type in mod.get("auto_activate_for", []):
                    selected.add(key)

            # Separate spec modules from general ERP modules
            spec_keys = set(MODULE_REGISTRY.keys())
            non_spec = [m for m in config.enabled_modules if m not in spec_keys]
            config.enabled_modules = non_spec + sorted(selected)
            config.save(update_fields=["enabled_modules", "updated_at"])

            messages.success(request, f"Konfiguracija spremljena! {len(selected)} specijaliziranih modula aktivno.")
            return redirect("companies:company_modules")

        elif action == "auto_detect":
            ai_detected = auto_detect_modules(company)
            if not ai_detected:
                messages.info(
                    request,
                    "Auto-detekcija nije pronašla dodatne module za vašu firmu. Provjerite NKD kod i tip djelatnosti.",
                )

        elif action == "apply_detected":
            detected_keys = request.POST.getlist("detected_modules")
            count = 0
            for key in detected_keys:
                try:
                    if activate_module(company, key):
                        count += 1
                except (ValueError, Exception):
                    pass
            if count:
                messages.success(request, f"Aktivirano {count} preporučenih modula!")
            else:
                messages.info(request, _("Svi preporučeni moduli su već aktivni."))
            return redirect("companies:company_modules")

    active_keys = get_active_modules(company)
    categories = get_all_modules_grouped()

    return render(
        request,
        "companies/module_config.html",
        {
            "company": company,
            "config": config,
            "active_keys": active_keys,
            "categories": categories,
            "ai_detected": ai_detected,
        },
    )


@login_required
def spec_module_toggle_api(request):
    """AJAX toggle for specialized modules."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    import json

    body = json.loads(request.body)
    module_key = body.get("module_key", "")
    enabled = body.get("enabled", True)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=400)

    from core.module_registry import activate_module, deactivate_module

    try:
        if enabled:
            activate_module(company, module_key)
        else:
            deactivate_module(company, module_key)
        return JsonResponse({"ok": True, "module": module_key, "enabled": enabled})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers (unchanged)
# ═══════════════════════════════════════════════════════════════════════════


def _get_module_counters(company):
    """Get record counts for modules that have counter_model."""
    from django.apps import apps

    from .module_registry import MODULES

    counters = {}
    for m in MODULES:
        cm = m.get("counter_model")
        if cm:
            try:
                app_label, model_name = cm.split(".")
                Model = apps.get_model(app_label, model_name)
                counters[m["id"]] = Model.objects.filter(company=company).count()
            except DatabaseError:
                counters[m["id"]] = 0
    return counters


def _ai_recommend(company):
    """AI-based module recommendation based on company data."""
    from django.apps import apps

    # Gather signals
    signals = {}
    try:
        signals["has_invoices"] = apps.get_model("invoicing", "Invoice").objects.filter(company=company).exists()
        signals["has_partners"] = apps.get_model("partners", "Partner").objects.filter(company=company).count() > 10
        signals["has_items"] = apps.get_model("inventory", "InventoryItem").objects.filter(company=company).exists()
        signals["has_employees"] = (
            apps.get_model("worktime", "EmployeeProfile").objects.filter(company=company).exists()
        )
        signals["has_konto"] = apps.get_model("konto", "JournalEntry").objects.filter(company=company).exists()
        signals["country"] = getattr(company, "country", "HR")
    except DatabaseError:
        pass

    recommendations = ["dashboard", "invoicing", "partners"]  # always

    if signals.get("has_items"):
        recommendations.extend(["inventory", "smart_import"])
    if signals.get("has_employees"):
        recommendations.extend(["worktime", "payroll"])
    if signals.get("has_invoices"):
        recommendations.extend(["eracun", "konto", "pdv_s", "bank"])
    if signals.get("has_konto"):
        recommendations.append("documents")
    if signals.get("country") == "HR":
        recommendations.append("eracun_inbox")

    return list(dict.fromkeys(recommendations))  # dedupe preserving order
