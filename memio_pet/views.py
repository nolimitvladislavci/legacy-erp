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
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page, never_cache
from memio_pet.models import AnimalProfile, BreederProfile, PetHealthRecord, PetOwnership, BreederReview


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

    # Reviews
    reviews = []
    if breeder:
        reviews = list(
            BreederReview.objects.using(db)
            .filter(breeder=breeder, is_published=True)
            .order_by("-created_at")[:10]
        )

    context = {
        "animal": animal,
        "breeder": breeder,
        "health_records": health_records,
        "ownership_chain": ownership_chain,
        "reviews": reviews,
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
        return HttpResponse("Ljubimac nije pronadjen.", status=404, content_type="text/plain")

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
    reviews = list(
        BreederReview.objects.using(db)
        .filter(breeder=breeder, is_published=True)
        .order_by("-created_at")[:20]
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
        "reviews": reviews,
        "trust_score": trust_score,
        "trust_color": trust_color,
        "trust_label": trust_label,
    }
    return render(request, "memio_pet/breeder.html", context)


# ════════════════════════════════════════════════════════════
# BARF Marketplace + Njuškalo Badge (Sprint BARF)
# ════════════════════════════════════════════════════════════

def njuskalo_badge(request, breeder_id):
    """Trust Badge SVG — javno, za embed u Njuškalo oglase."""
    from memio_pet.models import BreederProfile
    from django.http import HttpResponse

    try:
        breeder = BreederProfile.objects.get(pk=breeder_id)
    except BreederProfile.DoesNotExist:
        return HttpResponse('Not Found', status=404)

    trust = breeder.trust_score or 0
    name = (breeder.name or 'Uzgajivač')[:20]
    verified = breeder.is_cro_validated
    colour = '#4caf7d' if trust >= 80 else '#c9a84c' if trust >= 50 else '#888'
    check = '&#10003;' if verified else '?'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="340" height="90" viewBox="0 0 340 90">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#1a1a2e"/><stop offset="100%" stop-color="#2d2d4a"/>
  </linearGradient></defs>
  <rect width="340" height="90" rx="10" fill="url(#bg)"/>
  <rect x="0" y="0" width="6" height="90" rx="3" fill="{colour}"/>
  <text x="24" y="28" font-family="Arial,sans-serif" font-size="11" fill="#888" letter-spacing="2">MEMIO.PET VERIFICIRANO</text>
  <text x="24" y="54" font-family="Arial,sans-serif" font-size="18" font-weight="bold" fill="#e8e8e8">{check} {name}</text>
  <text x="24" y="75" font-family="Arial,sans-serif" font-size="12" fill="{colour}" font-weight="600">TRUST SCORE {trust}/100</text>
  <text x="320" y="75" font-family="Arial,sans-serif" font-size="9" fill="#555" text-anchor="end">memio.pet</text>
</svg>"""

    response = HttpResponse(svg, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def barf_listings(request):
    """Javni popis BARF ponuda — bez prijave."""
    from memio_pet.models import RawFoodListing
    from django.utils import timezone

    today = timezone.now().date()
    listings = (RawFoodListing.objects.filter(status='available', expires_at__gte=today)
                .select_related('company')
                .order_by('-created_at')[:50])

    return render(request, 'memio_pet/barf_listings.html', {
        'listings': listings,
        'page_title': 'BARF Marketplace',
    })
