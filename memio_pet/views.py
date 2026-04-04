"""
memio_pet/views.py -- Public-facing views za memio.pet domenu

Endpointi:
  GET /pas/<chip_or_tag>/     -- Javni profil ljubimca (HTML stranica za QR)
  GET /pas/<chip_or_tag>/qr/  -- QR kod slika (PNG)
  GET /uzgajivac/<uuid>/      -- Javni profil uzgajivaca
"""
import io
import qrcode
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from memio_pet.models import AnimalProfile, BreederProfile, PetHealthRecord, PetOwnership


def _find_animal(chip_or_tag):
    """Nadje zivotinju po chip_number ili ear_tag."""
    db = "memio_pets"
    chip_or_tag = chip_or_tag.strip()
    animal = AnimalProfile.objects.using(db).filter(chip_number=chip_or_tag).first()
    if not animal:
        animal = AnimalProfile.objects.using(db).filter(ear_tag=chip_or_tag).first()
    return animal


@require_GET
def pet_profile_page(request, chip_or_tag):
    """
    Javna HTML stranica za profil ljubimca.
    Ovo je ono sto kupac vidi kad skenira QR kod.
    """
    animal = _find_animal(chip_or_tag)
    if not animal:
        return render(request, "memio_pet/not_found.html", {
            "chip_or_tag": chip_or_tag,
        }, status=404)

    db = "memio_pets"
    breeder = animal.breeder
    health_records = list(
        PetHealthRecord.objects.using(db)
        .filter(animal=animal)
        .order_by("datum")
        .select_related("vet_profile")
    )
    ownership_chain = list(
        PetOwnership.objects.using(db)
        .filter(animal=animal)
        .order_by("acquired_at")
    )

    # Trust score boja
    trust_score = breeder.trust_score if breeder else 0
    if trust_score >= 80:
        trust_color = "#28a745"
        trust_label = "Visoko povjerenje"
    elif trust_score >= 50:
        trust_color = "#ffc107"
        trust_label = "Umjereno povjerenje"
    else:
        trust_color = "#dc3545"
        trust_label = "Nedovoljno podataka"

    # QR URL
    identifier = animal.chip_number or animal.ear_tag
    qr_url = f"https://memio.pet/pas/{identifier}/qr/"
    profile_url = f"https://memio.pet/pas/{identifier}/"

    context = {
        "animal": animal,
        "breeder": breeder,
        "health_records": health_records,
        "ownership_chain": ownership_chain,
        "trust_score": trust_score,
        "trust_color": trust_color,
        "trust_label": trust_label,
        "qr_url": qr_url,
        "profile_url": profile_url,
        "identifier": identifier,
        "verified": animal.is_verified,
    }
    return render(request, "memio_pet/profile.html", context)


@require_GET
@cache_page(3600)
def pet_qr_code(request, chip_or_tag):
    """Generira QR kod PNG sliku za ljubimca."""
    animal = _find_animal(chip_or_tag)
    if not animal:
        raise Http404("Ljubimac nije pronadjen.")

    identifier = animal.chip_number or animal.ear_tag
    url = f"https://memio.pet/pas/{identifier}/"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="#f8f6f0")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    response["Content-Disposition"] = f'inline; filename="memio-{identifier}.png"'
    return response


@require_GET
def breeder_profile_page(request, breeder_id):
    """Javni profil uzgajivaca."""
    db = "memio_pets"
    try:
        breeder = BreederProfile.objects.using(db).get(pk=breeder_id)
    except BreederProfile.DoesNotExist:
        return render(request, "memio_pet/not_found.html", {
            "chip_or_tag": "uzgajivac",
        }, status=404)

    animals = list(
        AnimalProfile.objects.using(db)
        .filter(breeder=breeder)
        .order_by("-created_at")
    )

    trust_score = breeder.trust_score
    if trust_score >= 80:
        trust_color = "#28a745"
        trust_label = "Visoko povjerenje"
    elif trust_score >= 50:
        trust_color = "#ffc107"
        trust_label = "Umjereno povjerenje"
    else:
        trust_color = "#dc3545"
        trust_label = "Nedovoljno podataka"

    context = {
        "breeder": breeder,
        "animals": animals,
        "trust_score": trust_score,
        "trust_color": trust_color,
        "trust_label": trust_label,
    }
    return render(request, "memio_pet/breeder.html", context)
