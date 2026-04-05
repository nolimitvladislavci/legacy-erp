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
from django.shortcuts import render, redirect
from django.contrib import messages
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
        breeder = BreederProfile.objects.using('memio_pets').get(pk=breeder_id)
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
    listings = (RawFoodListing.objects.using('memio_pets').filter(status='available', expires_at__gte=today)
                .order_by('-created_at')[:50])

    return render(request, 'memio_pet/barf_listings.html', {
        'listings': listings,
        'page_title': 'BARF Marketplace',
    })


@login_required
def barf_create(request):
    """OPG vlasnik kreira BARF ponudu."""
    from memio_pet.models import RawFoodListing
    from core.company_utils import get_user_company

    company = get_user_company(request)
    if not company:
        return redirect('/')

    if request.method == 'POST':
        try:
            listing = RawFoodListing.objects.using('memio_pets').create(
                company=company,
                product_type=request.POST.get('product_type', 'ostalo'),
                quantity_kg=request.POST.get('quantity_kg', 0),
                price_eur_kg=request.POST.get('price_eur_kg', 0),
                available_from=request.POST.get('available_from'),
                expires_at=request.POST.get('expires_at'),
                k3_cert_number=request.POST.get('k3_cert_number', ''),
                is_antibiotic_free='is_antibiotic_free' in request.POST,
                is_free_range='is_free_range' in request.POST,
                description=request.POST.get('description', ''),
            )
            messages.success(request, f'BARF ponuda kreirana: {listing}')
            return redirect('memio_pet:barf_listings')
        except Exception as e:
            messages.error(request, f'Greška: {e}')

    return render(request, 'memio_pet/barf_create.html', {
        'company': company,
        'product_types': RawFoodListing.PRODUCT_CHOICES,
        'page_title': 'Nova BARF ponuda',
    })


def pet_hotel_booking(request):
    """Javna stranica za rezervaciju pet hotela."""
    from memio_pet.models import BreederProfile, PetBoardingReservation

    db = 'memio_pets'
    hotels = BreederProfile.objects.using(db).filter(account_type='hotel').order_by('name')

    if request.method == 'POST':
        try:
            hotel = BreederProfile.objects.using(db).get(pk=request.POST.get('hotel_id'))
            reservation = PetBoardingReservation(
                hotel=hotel,
                owner_name=request.POST.get('owner_name', ''),
                owner_phone=request.POST.get('owner_phone', ''),
                owner_email=request.POST.get('owner_email', ''),
                check_in=request.POST.get('check_in'),
                check_out=request.POST.get('check_out'),
                room_type=request.POST.get('room_type', 'standard'),
                special_diet=request.POST.get('special_diet', ''),
                medical_notes=request.POST.get('medical_notes', ''),
                emergency_contact=request.POST.get('emergency_contact', ''),
            )
            # Find or create animal
            chip = request.POST.get('chip_number', '').strip()
            pet_name = request.POST.get('pet_name', '').strip()
            from memio_pet.models import AnimalProfile
            animal = None
            if chip:
                animal = AnimalProfile.objects.using(db).filter(chip_number=chip).first()
            if not animal and pet_name:
                animal = AnimalProfile.objects.using(db).create(
                    name=pet_name,
                    vrsta=request.POST.get('vrsta', 'pas'),
                    chip_number=chip,
                    breeder_name_snapshot=request.POST.get('owner_name', ''),
                )
            if animal:
                reservation.animal = animal
                reservation.save()
                messages.success(request, f'Rezervacija potvrđena za {animal.name}! Kontaktirat ćemo vas uskoro.')
                return redirect('memio_pet:pet_hotel_booking')
            else:
                messages.error(request, 'Unesite ime ljubimca ili broj mikročipa.')
        except Exception as e:
            messages.error(request, f'Greška: {e}')

    return render(request, 'memio_pet/pet_hotel_booking.html', {
        'hotels': hotels,
        'room_types': PetBoardingReservation.ROOM_TYPES,
        'page_title': 'Pet Hotel — Rezervacija',
    })


def training_list(request):
    """Javni popis kinologa / trenera."""
    from memio_pet.models import BreederProfile, DogTrainingSession

    trainers = BreederProfile.objects.using('memio_pets').filter(account_type='trainer').order_by('name')

    return render(request, 'memio_pet/training_list.html', {
        'trainers': trainers,
        'training_types': DogTrainingSession.TRAINING_TYPES,
        'page_title': 'Dresura pasa — Kinolozi',
    })


# ════════════════════════════════════════════════════════════════
# REGISTRACIJA uzgajivača/vlasnika — memio.pet/registracija/
# Nema veze s LIMIT Connect ERP. Besplatno. Uvijek.
# ════════════════════════════════════════════════════════════════

def registracija(request):
    """
    Korak 1: tip profila + email → kreira BreederProfile
    Redirect na /uzgajivac/UUID/ nakon uspjeha
    """
    db = 'memio_pets'
    success = None
    error = None

    if request.method == 'POST':
        ime = request.POST.get('ime', '').strip()
        email = request.POST.get('email', '').strip().lower()
        grad = request.POST.get('grad', '').strip()
        account_type = request.POST.get('account_type', 'owner')
        telefon = request.POST.get('telefon', '').strip()

        if not ime or not email:
            error = 'Ime i email su obavezni.'
        elif BreederProfile.objects.using(db).filter(email=email).exists():
            # Već postoji — pošalji ih na profil
            bp = BreederProfile.objects.using(db).get(email=email)
            return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)
        else:
            try:
                bp = BreederProfile.objects.using(db).create(
                    name=ime,
                    email=email,
                    phone=telefon,
                    city=grad,
                    account_type=account_type,
                    country='HR',
                    trust_score=40,
                    is_no_limit_partner=False,
                )
                return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)
            except Exception as e:
                error = f'Greška: {e}'

    chip = request.GET.get('chip', '')
    source = request.GET.get('source', '')

    return render(request, 'memio_pet/registracija.html', {
        'error': error,
        'chip': chip,
        'source': source,
        'page_title': 'Kreiraj profil — Memio.pet',
        'account_types': [
            ('owner', '🐾 Vlasnik ljubimca'),
            ('breeder', '🏆 Uzgajivač'),
            ('opg', '🌿 OPG / Pčelar'),
            ('vet', '💉 Veterinar'),
            ('hotel', '🏨 Pet Hotel'),
            ('trainer', '🎯 Kinolog / Trener'),
            ('shelter', '🏠 Azil'),
        ],
    })


# ════════════════════════════════════════════════════════════════
# LANDING PAGE
# ════════════════════════════════════════════════════════════════

def landing_page(request):
    """memio.pet landing page."""
    return render(request, 'memio_pet/landing.html')


# ════════════════════════════════════════════════════════════════
# BREEDER DASHBOARD (login required)
# ════════════════════════════════════════════════════════════════

@login_required
def breeder_dashboard(request):
    """Dashboard za uzgajivača — moji ljubimci, trust score, recenzije."""
    db = 'memio_pets'

    # Nađi breeder profil za ulogiranog usera
    breeder = BreederProfile.objects.using(db).filter(user_id=request.user.pk).first()
    if not breeder:
        # Pokušaj po emailu
        breeder = BreederProfile.objects.using(db).filter(email=request.user.email).first()
        if breeder:
            # Poveži usera
            breeder.user_id = request.user.pk
            breeder.save(using=db, update_fields=['user_id'])

    if not breeder:
        messages.info(request, 'Nemate uzgajivački profil. Kreirajte ga.')
        return redirect('memio_pet:registracija')

    animals = list(
        AnimalProfile.objects.using(db)
        .filter(breeder=breeder)
        .order_by('-created_at')
    )
    reviews = list(
        BreederReview.objects.using(db)
        .filter(breeder=breeder, is_published=True)
        .order_by('-created_at')[:10]
    )

    trust_score = breeder.trust_score
    if trust_score >= 80:
        trust_color = '#28a745'
    elif trust_score >= 50:
        trust_color = '#ffc107'
    else:
        trust_color = '#dc3545'

    return render(request, 'memio_pet/dashboard.html', {
        'breeder': breeder,
        'animals': animals,
        'reviews': reviews,
        'trust_score': trust_score,
        'trust_color': trust_color,
    })


# ════════════════════════════════════════════════════════════════
# ADD ANIMAL (login required)
# ════════════════════════════════════════════════════════════════

@login_required
def add_animal(request):
    """Dodaj novog ljubimca."""
    db = 'memio_pets'

    breeder = BreederProfile.objects.using(db).filter(user_id=request.user.pk).first()
    if not breeder:
        breeder = BreederProfile.objects.using(db).filter(email=request.user.email).first()
    if not breeder:
        messages.error(request, 'Nemate uzgajivački profil.')
        return redirect('memio_pet:registracija')

    if request.method == 'POST':
        try:
            animal = AnimalProfile(
                name=request.POST.get('name', '').strip(),
                vrsta=request.POST.get('vrsta', 'pas'),
                breed=request.POST.get('breed', '').strip(),
                spol=request.POST.get('spol', 'N'),
                chip_number=request.POST.get('chip_number', '').strip(),
                date_of_birth=request.POST.get('date_of_birth') or None,
                weight_kg=request.POST.get('weight_kg') or None,
                color_description=request.POST.get('color_description', '').strip(),
                breeder=breeder,
                breeder_name_snapshot=breeder.name,
                status='aktivno',
            )

            # Generiraj ear_tag ako nije unesen
            ear_tag = request.POST.get('ear_tag', '').strip()
            if not ear_tag:
                import uuid as _uuid
                ear_tag = f"{animal.name or 'pet'}-{animal.vrsta}-{_uuid.uuid4().hex[:8]}"
            animal.ear_tag = ear_tag

            # Foto
            if 'photo' in request.FILES:
                animal.photo = request.FILES['photo']

            animal.save(using=db)
            identifier = animal.chip_number or animal.ear_tag
            messages.success(request, f'Ljubimac {animal.name} dodan!')
            return redirect('memio_pet:pet_profile', chip_or_tag=identifier)
        except Exception as e:
            messages.error(request, f'Greška: {e}')

    return render(request, 'memio_pet/add_animal.html', {
        'breeder': breeder,
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES,
        'spol_choices': AnimalProfile.SPOL_CHOICES,
    })
