"""
Mandate (Punomoć) views — upravljanje e-Račun mandatima.
Marija vidi sve punomoći, kreira nove, bulk umbrella.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger("eracun.mandate")


@login_required
def mandate_list(request):
    """GET /eracun/mandati/ — lista svih punomoći za kompaniju."""
    from einvoice.models.mandate import Mandate

    user_co = request.user.profile.company

    if request.user.is_superuser:
        mandates = Mandate.objects.all()
    else:
        mandates = Mandate.objects.filter(agent_company=user_co)

    mandates = mandates.select_related("principal_company", "agent_company").order_by("-created_at")

    stats = {
        "draft": mandates.filter(status="draft").count(),
        "signed": mandates.filter(status="signed").count(),
        "active": mandates.filter(status="active").count(),
        "total": mandates.count(),
    }

    return render(
        request,
        "eracun/mandate_list.html",
        {
            "mandates": mandates,
            "stats": stats,
        },
    )


@login_required
def mandate_create(request):
    """POST /eracun/mandati/novi/ — kreira novi mandat."""
    from companies.models import Company
    from einvoice.models.mandate import Mandate, MandateStatus, MandateType

    if request.method != "POST":
        # GET — prikaži formu s listom umbrella firmi
        user_co = request.user.profile.company
        children = Company.objects.filter(umbrella_parent=user_co).order_by("name")
        return render(request, "eracun/mandate_create.html", {"children": children})

    principal_id = request.POST.get("principal_id")
    principal = get_object_or_404(Company, id=principal_id)
    agent = request.user.profile.company

    # Check duplicate
    if Mandate.objects.filter(principal_company=principal, agent_company=agent).exists():
        messages.warning(request, f"Punomoć za {principal.name} već postoji.")
        return redirect("eracun:mandate_list")

    Mandate.objects.create(
        principal_company=principal,
        principal_oib=principal.oib or "",
        agent_company=agent,
        agent_oib=agent.oib or "",
        mandate_type=MandateType.FULL,
        status=MandateStatus.DRAFT,
        valid_from=timezone.now().date(),
        created_by=request.user,
    )

    messages.success(request, f"Punomoć kreirana za {principal.name}. Status: nacrt.")
    return redirect("eracun:mandate_list")


@login_required
def mandate_activate(request, pk):
    """POST /eracun/mandati/<uuid>/aktiviraj/ — aktiviraj mandat."""
    from einvoice.models.mandate import Mandate, MandateStatus

    mandate = get_object_or_404(Mandate, pk=pk)
    if mandate.status not in ("draft", "signed"):
        messages.error(request, _("Mandat nije u statusu za aktivaciju."))
        return redirect("eracun:mandate_list")

    mandate.status = MandateStatus.ACTIVE
    mandate.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Punomoć za {mandate.principal_company.name} aktivirana.")
    return redirect("eracun:mandate_list")


@login_required
def mandate_revoke(request, pk):
    """POST /eracun/mandati/<uuid>/opozovi/ — opozovi mandat."""
    from einvoice.models.mandate import Mandate

    mandate = get_object_or_404(Mandate, pk=pk)
    mandate.revoke()
    messages.warning(request, f"Punomoć za {mandate.principal_company.name} opozvana.")
    return redirect("eracun:mandate_list")


@login_required
def mandate_bulk_umbrella(request):
    """POST /eracun/mandati/bulk-umbrella/ — bulk kreiranje za sve umbrella firme."""
    from companies.models import Company
    from einvoice.models.mandate import Mandate, MandateStatus, MandateType

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    agent = request.user.profile.company
    children = Company.objects.filter(umbrella_parent=agent)

    created = 0
    already = 0

    for firm in children:
        if Mandate.objects.filter(principal_company=firm, agent_company=agent).exists():
            already += 1
            continue

        Mandate.objects.create(
            principal_company=firm,
            principal_oib=firm.oib or "",
            agent_company=agent,
            agent_oib=agent.oib or "",
            mandate_type=MandateType.FULL,
            status=MandateStatus.DRAFT,
            valid_from=timezone.now().date(),
            created_by=request.user,
        )
        created += 1

    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "already_exists": already,
            "total": children.count(),
            "message": f"Kreirano {created} punomoći. Vlasnici moraju potpisati.",
        }
    )
