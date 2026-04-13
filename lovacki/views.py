from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company


@login_required
def hunting_dashboard(request):
    """Lovački dashboard — kvote, odstrjeli, statistike."""
    from .models import HuntingGround, HuntingQuota, HuntRecord

    company = get_user_company(request)
    if not company:
        return redirect("/")

    year = timezone.now().year
    grounds = HuntingGround.objects.filter(company=company, is_active=True)
    records = HuntRecord.objects.filter(ground__company=company).order_by("-datum")[:20]
    quotas = HuntingQuota.objects.filter(ground__company=company, year=year).select_related("species", "ground")

    stats = {
        "total_records": HuntRecord.objects.filter(ground__company=company, datum__year=year).count(),
        "total_grounds": grounds.count(),
        "total_species": quotas.values("species").distinct().count(),
        "total_weight": sum(r.weight_kg or 0 for r in records),
    }

    return render(
        request,
        "lovacki/dashboard.html",
        {
            "grounds": grounds,
            "records": records,
            "quotas": quotas,
            "stats": stats,
            "year": year,
            "page_title": "Lovački modul",
        },
    )


@login_required
def hunt_record_create(request):
    """Novi odstrjel."""
    from .models import GameSpecies, HuntingGround, HuntRecord

    company = get_user_company(request)
    if not company:
        return redirect("/")

    grounds = HuntingGround.objects.filter(company=company, is_active=True)
    species = GameSpecies.objects.all()

    if request.method == "POST":
        try:
            record = HuntRecord.objects.create(
                ground_id=request.POST.get("ground"),
                species_id=request.POST.get("species"),
                hunter=request.user,
                datum=request.POST.get("datum"),
                lokacija=request.POST.get("lokacija", ""),
                spol=request.POST.get("spol", "N"),
                weight_kg=request.POST.get("weight_kg") or None,
                age_years=request.POST.get("age_years") or None,
                trophy_points=request.POST.get("trophy_points") or None,
                cites_number=request.POST.get("cites_number", ""),
                meat_available_kg=request.POST.get("meat_available_kg") or None,
                notes=request.POST.get("notes", ""),
                created_by=request.user,
            )
            messages.success(request, f"Odstrjel evidentiran: {record}")
            return redirect("lovacki:dashboard")
        except (IntegrityError, DatabaseError):
            messages.error(request, _("Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku."))

    return render(
        request,
        "lovacki/record_create.html",
        {
            "grounds": grounds,
            "species": species,
            "page_title": "Novi odstrjel",
        },
    )
