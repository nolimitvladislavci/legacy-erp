import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

logger = logging.getLogger(__name__)


@login_required
def onboarding_wizard(request):
    """Step-by-step guided onboarding — replaces static checklist."""
    company = get_user_company(request)
    if not company:
        return redirect("dashboard")

    from companies.models import OnboardingProgress
    onboarding, _ = OnboardingProgress.objects.get_or_create(company=company)

    # If dismissed or 100%, go to dashboard
    if onboarding.dismissed and not request.GET.get("force"):
        return redirect("company_dashboard")

    # Determine current step based on completion
    if not onboarding.profile_completed:
        step = 1
    elif not onboarding.first_partner_added:
        step = 2
    elif not onboarding.first_item_added:
        step = 3
    elif not onboarding.first_invoice_created:
        step = 4
    elif not onboarding.pos_configured:
        step = 5
    else:
        step = 6  # Complete!

    # Allow manual navigation via GET param
    requested_step = request.GET.get("step")
    if requested_step:
        try:
            step = int(requested_step)
        except (ValueError, TypeError):
            pass

    return render(request, "core/onboarding_wizard.html", {
        "company": company,
        "onboarding": onboarding,
        "step": step,
        "total_steps": 6,
    })


@login_required
@require_POST
def onboarding_update_profile(request):
    """Step 1: Update company profile from onboarding wizard."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False, "error": "Nema tvrtke"}, status=400)

    # Update company fields
    name = request.POST.get("name", "").strip()
    oib = request.POST.get("oib", "").strip()
    address = request.POST.get("address", "").strip()
    city = request.POST.get("city", "").strip()
    zip_code = request.POST.get("zip_code", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()

    if name:
        company.name = name
    if oib:
        company.oib = oib
    if address:
        company.address = address
    if city:
        company.city = city
    if zip_code:
        company.zip_code = zip_code
    if email and hasattr(company, "email"):
        company.email = email
    if phone and hasattr(company, "phone"):
        company.phone = phone
    company.save()

    # Mark profile completed
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.profile_completed:
        ob.profile_completed = True
        ob.save(update_fields=["profile_completed", "updated_at"])

    return JsonResponse({"ok": True, "next_step": 2})


@login_required
@require_POST
def onboarding_add_partner(request):
    """Step 2: Quick-add a partner from onboarding wizard."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False, "error": "Nema tvrtke"}, status=400)

    from partners.models import Partner

    name = request.POST.get("name", "").strip()
    oib = request.POST.get("oib", "").strip()
    email = request.POST.get("email", "").strip()
    partner_type = request.POST.get("partner_type", "client")

    if not name:
        return JsonResponse({"ok": False, "error": "Naziv partnera je obavezan"}, status=400)

    partner = Partner.objects.create(
        company=company,
        name=name,
        oib=oib,
        email=email,
        partner_type=partner_type,
    )

    return JsonResponse({"ok": True, "partner_id": partner.pk, "next_step": 3})


@login_required
@require_POST
def onboarding_add_item(request):
    """Step 3: Quick-add an inventory item from onboarding wizard."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False, "error": "Nema tvrtke"}, status=400)

    from inventory.models import InventoryItem

    name = request.POST.get("name", "").strip()
    price = request.POST.get("price", "0").strip()
    category = request.POST.get("category", "product")
    sku = request.POST.get("sku", "").strip()

    if not name:
        return JsonResponse({"ok": False, "error": "Naziv artikla je obavezan"}, status=400)

    try:
        price_val = float(price)
    except (ValueError, TypeError):
        price_val = 0

    # Auto-generate SKU if not provided
    if not sku:
        count = InventoryItem.objects.filter(company=company).count()
        sku = f"ART-{count + 1:04d}"

    item = InventoryItem.objects.create(
        company=company,
        name=name,
        sku=sku,
        unit_price=price_val,
        category=category,
        quantity=0,
    )

    # Mark step
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.first_item_added:
        ob.first_item_added = True
        ob.save(update_fields=["first_item_added", "updated_at"])

    return JsonResponse({"ok": True, "item_id": item.pk, "next_step": 4})


@login_required
@require_POST
def onboarding_activate_pos(request):
    """Step 5: Quick-create a POS terminal from onboarding wizard."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False, "error": "Nema tvrtke"}, status=400)

    from pos.models import POSTerminal

    # Create default terminal if none exists
    if not POSTerminal.objects.filter(company=company).exists():
        POSTerminal.objects.create(
            company=company,
            name="Blagajna 1",
            terminal_type="quick",
            is_active=True,
        )

    # Mark step
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.pos_configured:
        ob.pos_configured = True
        ob.save(update_fields=["pos_configured", "updated_at"])

    return JsonResponse({"ok": True, "next_step": 6})


@login_required
@require_POST
def onboarding_skip_step(request):
    """Skip a step and mark it done."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False}, status=400)

    step = request.POST.get("step", "")
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)

    field_map = {
        "1": "profile_completed",
        "2": "first_partner_added",
        "3": "first_item_added",
        "4": "first_invoice_created",
        "5": "pos_configured",
    }

    field = field_map.get(step)
    if field and not getattr(ob, field):
        setattr(ob, field, True)
        ob.save(update_fields=[field, "updated_at"])

    try:
        next_step = int(step) + 1
    except (ValueError, TypeError):
        next_step = 6

    return JsonResponse({"ok": True, "next_step": next_step})


@login_required
@require_POST
def onboarding_complete(request):
    """Mark onboarding as dismissed/complete."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False}, status=400)

    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    ob.dismissed = True
    ob.save(update_fields=["dismissed", "updated_at"])

    return JsonResponse({"ok": True})
