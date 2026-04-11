"""
memio_pet/views.py -- Public-facing views za memio.pet domenu

Endpointi:
  GET /pas/<chip_or_tag>/         -- Javni profil ljubimca (HTML stranica za QR)
  GET /pas/<chip_or_tag>/qr/      -- QR kod slika (PNG)
  GET /uzgajivac/<uuid>/          -- Javni profil uzgajivaca
  GET/POST /ljubimac/novi/        -- Dodaj ljubimca (session auth)
  GET/POST /ljubimac/zatrazi/     -- Zatrazi magic link (email + token)
  GET/POST /ljubimac/token/<tok>/ -- Dodaj ljubimca putem magic tokena
"""
import io
import qrcode
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_page, never_cache
from memio_pet.models import AnimalProfile, BreederProfile, PetHealthRecord, PetOwnership, BreederReview


def _find_animal(chip_or_tag):
    db = "memio_pets"
    chip_or_tag = chip_or_tag.strip()
    animal = AnimalProfile.objects.using(db).filter(chip_number=chip_or_tag).first()
    if not animal:
        animal = AnimalProfile.objects.using(db).filter(ear_tag=chip_or_tag).first()
    return animal


@require_GET
def pet_profile_page(request, chip_or_tag):
    animal = _find_animal(chip_or_tag)
    if not animal:
        return render(request, "memio_pet/not_found.html", {"chip_or_tag": chip_or_tag}, status=404)

    db = "memio_pets"
    breeder = animal.breeder
    health_records = list(PetHealthRecord.objects.using(db).filter(animal=animal).order_by("datum").select_related("vet_profile"))
    ownership_chain = list(PetOwnership.objects.using(db).filter(animal=animal).order_by("acquired_at"))

    trust_score = breeder.trust_score if breeder else 0
    if trust_score >= 80:
        trust_color, trust_label = "#28a745", "Visoko povjerenje"
    elif trust_score >= 50:
        trust_color, trust_label = "#ffc107", "Umjereno povjerenje"
    else:
        trust_color, trust_label = "#dc3545", "Nedovoljno podataka"

    identifier = animal.chip_number or animal.ear_tag
    reviews = []
    if breeder:
        reviews = list(BreederReview.objects.using(db).filter(breeder=breeder, is_published=True).order_by("-created_at")[:10])

    # Memorial context
    from memio_pet.models import MemorialProfile, LifeMilestone
    is_memorial = (animal.status == 'uginulo')
    memorial = None
    if is_memorial:
        try:
            memorial = MemorialProfile.objects.using(db).get(animal=animal)
        except MemorialProfile.DoesNotExist:
            pass

    # Zivotni trak (timeline)
    timeline = []
    if animal.date_of_birth:
        timeline.append({'date': animal.date_of_birth, 'type': 'rodenje', 'icon': '🐾',
                         'title': f'Rođen/a {animal.name}', 'note': '', 'photo': None})
    for own in ownership_chain:
        timeline.append({'date': own.acquired_at, 'type': 'vlasnistvo', 'icon': '🏠',
                         'title': f'Novi dom — {own.owner_name}', 'note': '', 'photo': None})
    for hr in health_records:
        timeline.append({'date': hr.datum, 'type': 'zdravlje', 'icon': '💉',
                         'title': hr.get_tip_display(), 'note': hr.opis or '', 'photo': None})
    milestones = list(LifeMilestone.objects.using(db).filter(animal=animal).order_by('date'))
    for m in milestones:
        icon = m.get_type_display().split(' ')[0] if m.get_type_display() else '⭐'
        timeline.append({'date': m.date, 'type': m.type, 'icon': icon,
                         'title': m.title, 'note': m.note,
                         'photo': m.photo.url if m.photo else None})
    if is_memorial and memorial and memorial.date_of_death:
        timeline.append({'date': memorial.date_of_death, 'type': 'memorial', 'icon': '🌈',
                         'title': 'Dugini Most', 'note': memorial.epitaph or '', 'photo': None})
    timeline.sort(key=lambda x: x['date'])

    return render(request, "memio_pet/profile.html", {
        "animal": animal, "breeder": breeder,
        "health_records": health_records, "ownership_chain": ownership_chain,
        "reviews": reviews, "trust_score": trust_score,
        "trust_color": trust_color, "trust_label": trust_label,
        "qr_url": f"https://memio.pet/pas/{identifier}/qr/",
        "profile_url": f"https://memio.pet/pas/{identifier}/",
        "identifier": identifier, "verified": animal.is_verified,
        "is_memorial": is_memorial, "memorial": memorial,
        "timeline": timeline, "milestones": milestones,
        "needs_parental_consent": breeder.needs_parental_consent if breeder else False,
    })


@require_GET
@cache_page(3600)
def pet_qr_code(request, chip_or_tag):
    animal = _find_animal(chip_or_tag)
    if not animal:
        return HttpResponse("Ljubimac nije pronadjen.", status=404, content_type="text/plain")
    identifier = animal.chip_number or animal.ear_tag
    url = f"https://memio.pet/pas/{identifier}/"
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    response["Content-Disposition"] = f'inline; filename="memio-{identifier}.png"'
    return response


@require_GET
def breeder_profile_page(request, breeder_id):
    db = "memio_pets"
    try:
        breeder = BreederProfile.objects.using(db).get(pk=breeder_id)
    except BreederProfile.DoesNotExist:
        return render(request, "memio_pet/not_found.html", {"chip_or_tag": "uzgajivac"}, status=404)

    animals = list(AnimalProfile.objects.using(db).filter(breeder=breeder).order_by("-created_at"))
    reviews = list(BreederReview.objects.using(db).filter(breeder=breeder, is_published=True).order_by("-created_at")[:20])

    trust_score = breeder.trust_score
    if trust_score >= 80:
        trust_color, trust_label = "#28a745", "Visoko povjerenje"
    elif trust_score >= 50:
        trust_color, trust_label = "#ffc107", "Umjereno povjerenje"
    else:
        trust_color, trust_label = "#dc3545", "Nedovoljno podataka"

    return render(request, "memio_pet/breeder.html", {
        "breeder": breeder, "animals": animals, "reviews": reviews,
        "trust_score": trust_score, "trust_color": trust_color, "trust_label": trust_label,
    })


# BARF Marketplace + Njuskalo Badge

def njuskalo_badge(request, breeder_id):
    try:
        breeder = BreederProfile.objects.using('memio_pets').get(pk=breeder_id)
    except BreederProfile.DoesNotExist:
        return HttpResponse('Not Found', status=404)
    trust = breeder.trust_score or 0
    name = (breeder.name or 'Uzgajivac')[:20]
    colour = '#4caf7d' if trust >= 80 else '#c9a84c' if trust >= 50 else '#888'
    check = '&#10003;' if breeder.is_cro_validated else '?'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="90" viewBox="0 0 340 90"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#1a1a2e"/><stop offset="100%" stop-color="#2d2d4a"/></linearGradient></defs><rect width="340" height="90" rx="10" fill="url(#bg)"/><rect x="0" y="0" width="6" height="90" rx="3" fill="{colour}"/><text x="24" y="28" font-family="Arial,sans-serif" font-size="11" fill="#888" letter-spacing="2">MEMIO.PET VERIFICIRANO</text><text x="24" y="54" font-family="Arial,sans-serif" font-size="18" font-weight="bold" fill="#e8e8e8">{check} {name}</text><text x="24" y="75" font-family="Arial,sans-serif" font-size="12" fill="{colour}" font-weight="600">TRUST SCORE {trust}/100</text><text x="320" y="75" font-family="Arial,sans-serif" font-size="9" fill="#555" text-anchor="end">memio.pet</text></svg>'
    response = HttpResponse(svg, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def barf_listings(request):
    from memio_pet.models import RawFoodListing
    from django.utils import timezone
    today = timezone.now().date()
    listings = RawFoodListing.objects.using('memio_pets').filter(status='available', expires_at__gte=today).order_by('-created_at')[:50]
    return render(request, 'memio_pet/barf_listings.html', {'listings': listings, 'page_title': 'BARF Marketplace'})


@login_required
def barf_create(request):
    from memio_pet.models import RawFoodListing
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return redirect('/')
    if request.method == 'POST':
        try:
            listing = RawFoodListing.objects.using('memio_pets').create(
                company=company, product_type=request.POST.get('product_type', 'ostalo'),
                quantity_kg=request.POST.get('quantity_kg', 0), price_eur_kg=request.POST.get('price_eur_kg', 0),
                available_from=request.POST.get('available_from'), expires_at=request.POST.get('expires_at'),
                k3_cert_number=request.POST.get('k3_cert_number', ''),
                is_antibiotic_free='is_antibiotic_free' in request.POST,
                is_free_range='is_free_range' in request.POST, description=request.POST.get('description', ''),
            )
            messages.success(request, f'BARF ponuda kreirana: {listing}')
            return redirect('memio_pet:barf_listings')
        except Exception as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    return render(request, 'memio_pet/barf_create.html', {
        'company': company, 'product_types': RawFoodListing.PRODUCT_CHOICES, 'page_title': 'Nova BARF ponuda',
    })


def pet_hotel_booking(request):
    from memio_pet.models import PetBoardingReservation
    db = 'memio_pets'
    hotels = BreederProfile.objects.using(db).filter(account_type='hotel').order_by('name')
    if request.method == 'POST':
        try:
            hotel = BreederProfile.objects.using(db).get(pk=request.POST.get('hotel_id'))
            reservation = PetBoardingReservation(
                hotel=hotel, owner_name=request.POST.get('owner_name', ''),
                owner_phone=request.POST.get('owner_phone', ''), owner_email=request.POST.get('owner_email', ''),
                check_in=request.POST.get('check_in'), check_out=request.POST.get('check_out'),
                room_type=request.POST.get('room_type', 'standard'),
                special_diet=request.POST.get('special_diet', ''),
                medical_notes=request.POST.get('medical_notes', ''),
                emergency_contact=request.POST.get('emergency_contact', ''),
            )
            chip = request.POST.get('chip_number', '').strip()
            pet_name = request.POST.get('pet_name', '').strip()
            animal = None
            if chip:
                animal = AnimalProfile.objects.using(db).filter(chip_number=chip).first()
            if not animal and pet_name:
                animal = AnimalProfile.objects.using(db).create(
                    name=pet_name, vrsta=request.POST.get('vrsta', 'pas'),
                    chip_number=chip, breeder_name_snapshot=request.POST.get('owner_name', ''),
                )
            if animal:
                reservation.animal = animal
                reservation.save()
                messages.success(request, f'Rezervacija potvrdjena za {animal.name}!')
                return redirect('memio_pet:pet_hotel_booking')
            else:
                messages.error(request, 'Unesite ime ljubimca ili broj mikrocipa.')
        except Exception as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    return render(request, 'memio_pet/pet_hotel_booking.html', {
        'hotels': hotels, 'room_types': PetBoardingReservation.ROOM_TYPES, 'page_title': 'Pet Hotel — Rezervacija',
    })


def training_list(request):
    from memio_pet.models import DogTrainingSession
    trainers = BreederProfile.objects.using('memio_pets').filter(account_type='trainer').order_by('name')
    return render(request, 'memio_pet/training_list.html', {
        'trainers': trainers, 'training_types': DogTrainingSession.TRAINING_TYPES, 'page_title': 'Dresura pasa',
    })


# REGISTRACIJA

def registracija(request):
    db = 'memio_pets'
    error = None
    if request.method == 'POST':
        ime = request.POST.get('ime', '').strip()
        email = request.POST.get('email', '').strip().lower()
        grad = request.POST.get('grad', '').strip()
        account_type = request.POST.get('account_type', 'owner')
        telefon = request.POST.get('telefon', '').strip()
        dob_str = request.POST.get('date_of_birth', '').strip()
        parent_email = request.POST.get('parent_email', '').strip().lower()

        if not ime or not email:
            error = 'Ime i email su obavezni.'
        elif (bp := BreederProfile.find_by_email(email)):
            request.session['memio_breeder_pk'] = str(bp.pk)
            request.session['memio_breeder_email'] = bp.email
            request.session.set_expiry(86400 * 7)
            return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)
        else:
            # GDPR dob provjera (HR: 16 godina, čl. 19 ZoPOUOZP)
            dob = None
            is_minor = False
            if dob_str:
                try:
                    from datetime import date, datetime
                    dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    today = date.today()
                    age = today.year - dob.year - (
                        (today.month, today.day) < (dob.month, dob.day)
                    )
                    is_minor = age < 16
                    if age < 13:
                        error = 'Moraš imati najmanje 13 godina. Zamoli roditelja da kreira profil za tebe.'
                    elif is_minor and not parent_email:
                        error = 'Imaš manje od 16 godina — upiši email roditelja ili skrbnika za pristanak (GDPR).'
                    elif is_minor and '@' not in parent_email:
                        error = 'Email roditelja nije ispravan.'
                except ValueError:
                    pass  # nevaljan datum, preskočimo

            if not error:
                oib = request.POST.get('oib', '').strip()
                website = request.POST.get('website', '').strip()
                initial_trust = 40
                if oib and len(oib) == 11 and oib.isdigit():
                    initial_trust += 20
                try:
                    import secrets as _s
                    consent_token = _s.token_urlsafe(32) if is_minor else ''
                    bp = BreederProfile.objects.using(db).create(
                        name=ime, email=email, phone=telefon, city=grad,
                        account_type=account_type, country='HR',
                        trust_score=initial_trust, is_no_limit_partner=False,
                        oib=oib, website=website,
                        date_of_birth=dob,
                        parent_email=parent_email if is_minor else '',
                        parental_consent=not is_minor,  # punoljetni = automatski OK
                        consent_token=consent_token,
                    )
                    # Pošalji consent email roditelju (async, ne blokira)
                    if is_minor and parent_email:
                        from django.utils import timezone
                        bp.consent_sent_at = timezone.now()
                        bp.save(using=db, update_fields=['consent_sent_at'])
                        _send_parental_consent_email(bp, parent_email)

                    request.session['memio_breeder_pk'] = str(bp.pk)
                    request.session['memio_breeder_email'] = bp.email
                    request.session.set_expiry(86400 * 7)

                    # Welcome email
                    try:
                        from django.core.mail import send_mail
                        send_mail(
                            subject=f'Dobrodošli na Memio.pet, {ime}!',
                            message=(
                                f'Pozdrav {ime},\n\n'
                                f'Vaš profil na Memio.pet je kreiran!\n\n'
                                f'Što možete napraviti:\n'
                                f'  - Dodajte ljubimca: https://memio.pet/ljubimac/novi/\n'
                                f'  - Vaš profil: https://memio.pet/uzgajivac/{bp.pk}/\n'
                                f'  - Prijava: https://memio.pet/prijava/\n\n'
                                f'Za prijavu koristite ovaj email — bez lozinke.\n\n'
                                f'Lijep pozdrav,\n'
                                f'Memio.pet tim'
                            ),
                            from_email='noreply@memio.pet',
                            recipient_list=[email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass

                    return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)
                except Exception as e:
                    error = f'Greska: {e}'
    return render(request, 'memio_pet/registracija.html', {
        'error': error, 'chip': request.GET.get('chip', ''), 'source': request.GET.get('source', ''),
        'pet_name': request.GET.get('pet', ''),
        'page_title': 'Kreiraj profil', 'account_types': [
            ('owner', '🐾 Vlasnik ljubimca'), ('breeder', '🏆 Uzgajivac'),
            ('opg', '🌿 OPG / Pcelar'), ('vet', '💉 Veterinar'),
            ('hotel', '🏨 Pet Hotel'), ('trainer', '🎯 Kinolog / Trener'), ('shelter', '🏠 Azil'),
        ],
    })


def _send_parental_consent_email(bp, parent_email):
    """Šalje email roditelju s linkom za pristanak. Ne blokira registraciju."""
    try:
        from django.core.mail import send_mail
        consent_url = f"https://memio.pet/pristanak/{bp.consent_token}/"
        dob_str = bp.date_of_birth.strftime('%d.%m.%Y.') if bp.date_of_birth else 'nije upisano'
        send_mail(
            subject=f'Memio.pet — Vaše dijete ({bp.name}) traži pristanak',
            message=(
                f'Poštovani,\n\n'
                f'Vaše dijete {bp.name} (rođ. {dob_str}) želi koristiti Memio.pet — '
                f'besplatnu platformu za digitalne profile kućnih ljubimaca.\n\n'
                f'ŠTO JE MEMIO.PET?\n'
                f'Platforma gdje vlasnici kreiraju digitalne profile za svoje ljubimce '
                f'(pas, mačka, konj...). Sadrži zdravstveni karton, fotografije i '
                f'QR kod za identifikaciju. Besplatno, bez oglasa.\n\n'
                f'KOJI PODACI SE PRIKUPLJAJU?\n'
                f'- Ime djeteta, email, grad\n'
                f'- Podaci o ljubimcu (ime, pasmina, čip broj)\n'
                f'- Svi osobni podaci su enkriptirani (AES-256)\n'
                f'- Nema plaćanja, nema oglasa, nema prodaje podataka\n\n'
                f'ZAŠTO TREBAMO VAŠ PRISTANAK?\n'
                f'EU GDPR (čl. 8) i hrvatski zakon (čl. 19 ZoPOUOZP) zahtijevaju '
                f'pristanak roditelja za obradu osobnih podataka djece mlađe od 16 godina.\n\n'
                f'ODOBRI ILI ODBIJ:\n'
                f'{consent_url}\n\n'
                f'Na ovom linku možete:\n'
                f'  ✅ Odobriti — dijete koristi Memio.pet normalno\n'
                f'  ❌ Odbiti — profil i svi podaci se brišu\n\n'
                f'Ako niste upoznati s ovim zahtjevom ili vaše dijete nije '
                f'zatražilo ovo, slobodno ignorirajte ovaj email.\n\n'
                f'S poštovanjem,\n'
                f'Memio.pet tim\n'
                f'Projekt NO LIMIT udruge · memio.pet · Konjik d.o.o.'
            ),
            from_email=None,
            recipient_list=[parent_email],
            fail_silently=True,
        )
    except Exception:
        pass  # ne prekidaj registraciju ako email ne prođe


def parental_consent(request, token):
    """Roditelj klikne link iz emaila → odobri ili odbij profil djeteta."""
    db = 'memio_pets'
    bp = BreederProfile.objects.using(db).filter(consent_token=token).first()
    if not bp:
        return render(request, 'memio_pet/consent_result.html', {
            'success': False, 'message': 'Link nije valjan ili je istekao.',
        })
    if bp.parental_consent:
        return render(request, 'memio_pet/consent_result.html', {
            'success': True, 'message': f'Pristanak za {bp.name} je već potvrđen.',
            'breeder': bp,
        })

    # Dohvati ljubimce djeteta za prikaz roditelju
    animals = list(AnimalProfile.objects.using(db).filter(breeder=bp).values_list('name', flat=True))

    if request.method == 'POST':
        from django.utils import timezone
        action = request.POST.get('action', 'approve')

        if action == 'reject':
            # Roditelj odbija → briši profil i sve životinje
            AnimalProfile.objects.using(db).filter(breeder=bp).delete()
            bp.delete(using=db)
            return render(request, 'memio_pet/consent_result.html', {
                'success': True,
                'message': 'Profil je obrisan. Dijete će morati zatražiti vaš pristanak ponovo.',
                'rejected': True,
            })

        # Odobri
        bp.parental_consent = True
        bp.consent_given_at = timezone.now()
        bp.consent_token = ''  # jednokratni
        bp.save(using=db, update_fields=['parental_consent', 'consent_given_at', 'consent_token'])
        return render(request, 'memio_pet/consent_result.html', {
            'success': True,
            'message': f'Pristanak za {bp.name} je odobren. Profil je sada potpuno aktivan.',
            'breeder': bp,
        })

    return render(request, 'memio_pet/consent_form.html', {
        'breeder': bp, 'token': token, 'animals': animals,
    })


def resend_consent(request):
    """Dijete traži ponovo slanje consent emaila roditelju."""
    db = 'memio_pets'
    breeder_pk = request.session.get('memio_breeder_pk')
    if not breeder_pk:
        return redirect('memio_pet:registracija')
    try:
        import uuid as _u
        bp = BreederProfile.objects.using(db).get(pk=_u.UUID(str(breeder_pk)))
    except Exception:
        return redirect('memio_pet:registracija')

    if bp.parental_consent:
        messages.info(request, 'Pristanak roditelja je već potvrđen.')
        return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)

    if not bp.parent_email:
        messages.error(request, 'Nema upisanog emaila roditelja.')
        return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)

    # Generiraj novi token ako je stari prazan
    if not bp.consent_token:
        import secrets as _s
        bp.consent_token = _s.token_urlsafe(32)

    from django.utils import timezone
    bp.consent_sent_at = timezone.now()
    bp.save(using=db, update_fields=['consent_token', 'consent_sent_at'])
    _send_parental_consent_email(bp, bp.parent_email)
    messages.success(request, f'Email ponovo poslan roditelju. Provjeri s njim/njom.')
    return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)


@cache_page(300)
def landing_page(request):
    return render(request, 'memio_pet/landing.html')


@login_required
def breeder_dashboard(request):
    db = 'memio_pets'
    breeder = BreederProfile.objects.using(db).filter(user_id=request.user.pk).first()
    if not breeder:
        breeder = BreederProfile.objects.using(db).filter(email=request.user.email).first()
        if breeder:
            breeder.user_id = request.user.pk
            breeder.save(using=db, update_fields=['user_id'])
    if not breeder:
        messages.info(request, 'Nemate profil. Kreirajte ga.')
        return redirect('memio_pet:registracija')
    animals = list(AnimalProfile.objects.using(db).filter(breeder=breeder).order_by('-created_at'))
    reviews = list(BreederReview.objects.using(db).filter(breeder=breeder, is_published=True).order_by('-created_at')[:10])
    trust_score = breeder.trust_score
    trust_color = '#28a745' if trust_score >= 80 else '#ffc107' if trust_score >= 50 else '#dc3545'
    return render(request, 'memio_pet/dashboard.html', {
        'breeder': breeder, 'animals': animals, 'reviews': reviews,
        'trust_score': trust_score, 'trust_color': trust_color,
    })


# ADD ANIMAL — session auth

def add_animal(request):
    db = 'memio_pets'
    breeder_pk = (request.session.get('memio_breeder_pk') or
                  request.GET.get('breeder') or request.POST.get('breeder_id'))
    if not breeder_pk:
        return render(request, 'memio_pet/add_animal_auth.html', {'page_title': 'Tko si ti?'})
    try:
        import uuid as _u
        breeder = BreederProfile.objects.using(db).get(pk=_u.UUID(str(breeder_pk)))
    except Exception:
        return redirect('memio_pet:registracija')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        vrsta = request.POST.get('vrsta', 'pas')
        breed = request.POST.get('breed', '').strip()
        chip = request.POST.get('chip_number', '').strip()
        ear_tag = request.POST.get('ear_tag', '').strip()
        spol = request.POST.get('spol', 'N')
        dob = request.POST.get('date_of_birth') or None
        notes = request.POST.get('notes', '').strip()
        status = request.POST.get('status', 'aktivno')
        _ctx = {
            'breeder': breeder, 'breeder_id': str(breeder.pk),
            'vrsta_choices': AnimalProfile.VRSTA_CHOICES, 'spol_choices': AnimalProfile.SPOL_CHOICES,
        }
        if not name:
            return render(request, 'memio_pet/add_animal.html', {**_ctx, 'error': 'Ime ljubimca je obavezno.'})
        import re
        if chip and not re.match(r'^\d{9,15}$', chip):
            return render(request, 'memio_pet/add_animal.html', {
                **_ctx, 'error': 'Broj mikročipa mora sadržavati samo znamenke (9-15 znamenki). Ako nemaš čip, ostavi prazno.'})
        if status not in dict(AnimalProfile.STATUS_CHOICES):
            status = 'aktivno'
        import uuid as _u2
        if not chip and not ear_tag:
            ear_tag = f"{vrsta}-{_u2.uuid4().hex[:8]}"
        animal = AnimalProfile(
            name=name, vrsta=vrsta, breed=breed, chip_number=chip,
            ear_tag=ear_tag or f"{vrsta}-{_u2.uuid4().hex[:8]}",
            spol=spol, date_of_birth=dob, notes=notes,
            breeder=breeder, breeder_name_snapshot=breeder.name, status=status,
        )
        if 'photo' in request.FILES:
            animal.photo = request.FILES['photo']
        animal.save(using=db)
        # Ako je status uginulo, kreiraj memorial automatski
        if status == 'uginulo':
            from memio_pet.models import MemorialProfile
            MemorialProfile.objects.using(db).get_or_create(animal=animal)
        request.session['memio_breeder_pk'] = str(breeder.pk)
        identifier = animal.chip_number or animal.ear_tag
        messages.success(request, f'{name} je dodan!')
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    return render(request, 'memio_pet/add_animal.html', {
        'breeder': breeder, 'breeder_id': str(breeder.pk),
        'page_title': f'Dodaj ljubimca — {breeder.name}',
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES, 'spol_choices': AnimalProfile.SPOL_CHOICES,
    })


# MAGIC TOKEN — sigurna autorizacija

def add_animal_request(request):
    """Zatrazi magic link za dodavanje ljubimca."""
    db = 'memio_pets'
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            return render(request, 'memio_pet/add_animal_auth.html', {
                'error': 'Upisi email adresu.', 'page_title': 'Tko si ti?',
            })
        bp = BreederProfile.find_by_email(email)
        if bp:
            from memio_pet.models import AddAnimalToken
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            token_obj = AddAnimalToken.create(breeder=bp, email=email, ip=ip)
            from django.core.mail import send_mail
            magic_url = f"https://memio.pet/ljubimac/token/{token_obj.token}/"
            try:
                send_mail(
                    subject='Memio.pet — Dodaj ljubimca',
                    message=(
                        f'Bok {bp.name}!\n\n'
                        f'Klikni na link da dodas ljubimca:\n{magic_url}\n\n'
                        f'Link vrijedi 30 minuta i moze se koristiti samo jednom.\n\n'
                        f'Ako nisi ti zatrazio/la ovaj link, slobodno ga ignoriraj.\n\n'
                        f'— Memio.pet tim'
                    ),
                    from_email=None, recipient_list=[email], fail_silently=True,
                )
            except Exception:
                pass
            request.session['memio_breeder_pk'] = str(bp.pk)
            request.session['memio_breeder_email'] = bp.email
            request.session.set_expiry(86400 * 7)
            return render(request, 'memio_pet/add_animal_auth.html', {
                'success': True, 'email_sent': email, 'page_title': 'Provjeri email!', 'breeder': bp,
            })
        else:
            return render(request, 'memio_pet/add_animal_auth.html', {
                'error': 'Nismo pronasli profil s tim emailom. Kreiraj novi profil.',
                'show_register': True, 'page_title': 'Tko si ti?',
            })
    return render(request, 'memio_pet/add_animal_auth.html', {'page_title': 'Tko si ti?'})


def add_animal_with_token(request, token):
    """Dodaj ljubimca putem magic tokena."""
    db = 'memio_pets'
    from memio_pet.models import AddAnimalToken
    try:
        token_obj = AddAnimalToken.objects.using(db).select_related('breeder').get(token=token)
    except AddAnimalToken.DoesNotExist:
        return render(request, 'memio_pet/add_animal_auth.html', {
            'error': 'Link nije valjan. Zatrazi novi.', 'page_title': 'Nevaljan link',
        })
    if not token_obj.is_valid:
        return render(request, 'memio_pet/add_animal_auth.html', {
            'error': 'Link je istekao ili je vec koristen. Zatrazi novi.', 'page_title': 'Link istekao',
        })
    breeder = token_obj.breeder

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        vrsta = request.POST.get('vrsta', 'pas')
        breed = request.POST.get('breed', '').strip()
        chip = request.POST.get('chip_number', '').strip()
        ear_tag = request.POST.get('ear_tag', '').strip()
        spol = request.POST.get('spol', 'N')
        dob = request.POST.get('date_of_birth') or None
        notes = request.POST.get('notes', '').strip()
        status = request.POST.get('status', 'aktivno')
        _ctx = {
            'breeder': breeder, 'breeder_id': str(breeder.pk),
            'vrsta_choices': AnimalProfile.VRSTA_CHOICES, 'spol_choices': AnimalProfile.SPOL_CHOICES,
            'token': token,
        }
        if not name:
            return render(request, 'memio_pet/add_animal.html', {**_ctx, 'error': 'Ime ljubimca je obavezno.'})
        import re
        if chip and not re.match(r'^\d{9,15}$', chip):
            return render(request, 'memio_pet/add_animal.html', {
                **_ctx, 'error': 'Broj mikročipa mora sadržavati samo znamenke (9-15 znamenki). Ako nemaš čip, ostavi prazno.'})
        if status not in dict(AnimalProfile.STATUS_CHOICES):
            status = 'aktivno'
        import uuid as _u2
        if not chip and not ear_tag:
            ear_tag = f"{vrsta}-{_u2.uuid4().hex[:8]}"
        animal = AnimalProfile(
            name=name, vrsta=vrsta, breed=breed, chip_number=chip,
            ear_tag=ear_tag or f"{vrsta}-{_u2.uuid4().hex[:8]}",
            spol=spol, date_of_birth=dob, notes=notes,
            breeder=breeder, breeder_name_snapshot=breeder.name, status=status,
        )
        if 'photo' in request.FILES:
            animal.photo = request.FILES['photo']
        animal.save(using=db)
        token_obj.consume()
        request.session['memio_breeder_pk'] = str(breeder.pk)
        identifier = animal.chip_number or animal.ear_tag
        messages.success(request, f'{name} je dodan!')
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    return render(request, 'memio_pet/add_animal.html', {
        'breeder': breeder, 'breeder_id': str(breeder.pk),
        'page_title': f'Dodaj ljubimca — {breeder.name}',
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES, 'spol_choices': AnimalProfile.SPOL_CHOICES,
        'token': token,
    })


@csrf_exempt
@require_POST
def memorial_candle_api(request, chip_or_tag):
    """API: upali svjećicu na memorijalu (javna anonimna akcija)."""
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)
    if not animal or animal.status != 'uginulo':
        return JsonResponse({'error': 'not found'}, status=404)
    try:
        from memio_pet.models import MemorialProfile
        memorial = MemorialProfile.objects.using(db).get(animal=animal)
        memorial.candle_count += 1
        memorial.save(using=db, update_fields=['candle_count'])
        return JsonResponse({'total': memorial.candle_count})
    except MemorialProfile.DoesNotExist:
        return JsonResponse({'error': 'no memorial'}, status=404)


def prijava(request):
    """Prijava postojećeg korisnika — email lookup → session."""
    db = 'memio_pets'
    error = None
    email_value = ''

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        email_value = email
        if not email or '@' not in email:
            error = 'Upiši ispravnu email adresu.'
        else:
            bp = BreederProfile.find_by_email(email)
            if bp:
                request.session['memio_breeder_pk'] = str(bp.pk)
                request.session['memio_breeder_email'] = bp.email
                request.session.set_expiry(86400 * 7)
                return redirect('memio_pet:breeder_profile', breeder_id=bp.pk)
            else:
                error = 'Email nije pronađen. Želiš li kreirati novi profil?'

    return render(request, 'memio_pet/prijava.html', {
        'error': error,
        'email_value': email_value,
    })


def udomljavanje_lista(request):
    """Javna stranica — životinje iz azila koje čekaju dom."""
    db = 'memio_pets'
    vrsta_filter = request.GET.get('vrsta', '')
    grad_filter = request.GET.get('grad', '')

    qs = AnimalProfile.objects.using(db).filter(
        status='u_azilu'
    ).select_related('breeder').order_by('-created_at')

    if vrsta_filter:
        qs = qs.filter(vrsta=vrsta_filter)
    if grad_filter:
        qs = qs.filter(breeder__city__icontains=grad_filter)

    return render(request, 'memio_pet/udomljavanje.html', {
        'animals': list(qs[:50]),
        'vrsta_filter': vrsta_filter,
        'grad_filter': grad_filter,
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES,
        'total': qs.count(),
    })


def add_milestone(request):
    """Dodaj životnu prekretnicu na profil ljubimca."""
    db = 'memio_pets'
    chip = request.GET.get('animal') or request.POST.get('chip')
    animal = _find_animal(chip) if chip else None
    if not animal:
        return redirect('memio_pet:landing')

    if request.method == 'POST':
        from memio_pet.models import LifeMilestone
        m = LifeMilestone(
            animal=animal,
            type=request.POST.get('type', 'custom'),
            title=request.POST.get('title', '').strip(),
            date=request.POST.get('date'),
            note=request.POST.get('note', '').strip(),
        )
        if 'photo' in request.FILES:
            m.photo = request.FILES['photo']
        m.save(using=db)
        identifier = animal.chip_number or animal.ear_tag
        messages.success(request, f'Prekretnica dodana!')
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    from memio_pet.models import LifeMilestone as LM
    return render(request, 'memio_pet/add_milestone.html', {
        'animal': animal, 'chip': chip,
        'milestone_types': LM.TYPES,
    })



def dugini_most(request, chip_or_tag):
    """Označi ljubimca kao uginulog — Dugini Most flow."""
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)
    if not animal:
        return redirect('memio_pet:landing')

    # Session auth
    breeder_pk = request.session.get('memio_breeder_pk')
    if not breeder_pk or (animal.breeder and str(animal.breeder.pk) != breeder_pk):
        if not (request.user.is_authenticated and request.user.is_staff):
            messages.error(request, 'Nemate pristup za ovu akciju.')
            identifier = animal.chip_number or animal.ear_tag
            return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    if animal.status == 'uginulo':
        identifier = animal.chip_number or animal.ear_tag
        return redirect('memio_pet:memorial_edit', chip_or_tag=identifier)

    if request.method == 'POST':
        animal.status = 'uginulo'
        animal.save(using=db, update_fields=['status', 'updated_at'])
        from memio_pet.models import MemorialProfile
        memorial, _ = MemorialProfile.objects.using(db).get_or_create(animal=animal)
        date_of_death = request.POST.get('date_of_death', '')
        epitaph = request.POST.get('epitaph', '').strip()
        if date_of_death:
            memorial.date_of_death = date_of_death
        if epitaph:
            memorial.epitaph = epitaph[:500]
        memorial.save(using=db)
        identifier = animal.chip_number or animal.ear_tag
        messages.success(request, f'{animal.name} je sada na Duginom Mostu. Uspomene ostaju zauvijek.')
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    return render(request, 'memio_pet/dugini_most.html', {
        'animal': animal,
        'identifier': animal.chip_number or animal.ear_tag,
    })


# DUGINI MOST — memorial views

def memorial_edit(request, chip_or_tag):
    """Uredi memorijalni profil — session auth (vlasnik)."""
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)
    if not animal or animal.status != 'uginulo':
        return redirect('memio_pet:landing')

    from memio_pet.models import MemorialProfile
    try:
        memorial = MemorialProfile.objects.using(db).get(animal=animal)
    except MemorialProfile.DoesNotExist:
        memorial = MemorialProfile.objects.using(db).create(animal=animal)

    # Session auth — provjeri da je vlasnik
    breeder_pk = request.session.get('memio_breeder_pk')
    if not breeder_pk or (animal.breeder and str(animal.breeder.pk) != breeder_pk):
        if not (request.user.is_authenticated and request.user.is_staff):
            messages.error(request, 'Nemate pristup za uredjivanje ovog memorijala.')
            identifier = animal.chip_number or animal.ear_tag
            return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    if request.method == 'POST':
        memorial.epitaph = request.POST.get('epitaph', '').strip()[:500]
        memorial.date_of_death = request.POST.get('date_of_death') or memorial.date_of_death
        memorial.cause_note = request.POST.get('cause_note', '').strip()[:200]
        memorial.cremated = 'cremated' in request.POST
        memorial.urn_description = request.POST.get('urn_description', '').strip()[:200]
        # Donacije azilu
        shelter_pk = request.POST.get('donation_target')
        if shelter_pk:
            try:
                import uuid as _u
                shelter = BreederProfile.objects.using(db).get(
                    pk=_u.UUID(str(shelter_pk)), account_type='shelter')
                memorial.donation_target = shelter
            except Exception:
                pass
        memorial.save(using=db)
        messages.success(request, 'Memorijal azuriran.')
        identifier = animal.chip_number or animal.ear_tag
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    shelters = list(BreederProfile.objects.using(db).filter(account_type='shelter').order_by('name'))
    return render(request, 'memio_pet/memorial_edit.html', {
        'animal': animal, 'memorial': memorial, 'shelters': shelters,
        'identifier': animal.chip_number or animal.ear_tag,
    })


# ════════════════════════════════════════════════════════════════
# KNJIGA SJEĆANJA — PDF generiranje (WeasyPrint)
# URL: /pas/<chip>/knjiga/
# ════════════════════════════════════════════════════════════════

@require_GET
def knjiga_sjecanja_pdf(request, chip_or_tag):
    """Generira PDF 'Knjiga sjećanja' za ljubimca."""
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)

    if not animal:
        return HttpResponse('Ljubimac nije pronađen.', status=404, content_type='text/plain')

    # Dohvati sve podatke
    health_records = list(
        PetHealthRecord.objects.using(db)
        .filter(animal=animal)
        .order_by('datum')
    )
    ownership_chain = list(
        PetOwnership.objects.using(db)
        .filter(animal=animal)
        .order_by('acquired_at')
    )
    try:
        from memio_pet.models import LifeMilestone, MemorialProfile
        milestones = list(
            LifeMilestone.objects.using(db)
            .filter(animal=animal)
            .order_by('date')
        )
        memorial = MemorialProfile.objects.using(db).filter(animal=animal).first()
    except Exception:
        milestones = []
        memorial = None

    # Agregacija životnog traka
    from datetime import date as _date
    timeline = []

    if animal.date_of_birth:
        timeline.append({
            'date': animal.date_of_birth,
            'icon': '🐾',
            'title': f'Rodio/la se {animal.name}',
            'note': animal.breed or '',
            'photo': None,
            'type': 'rodenje',
        })

    for own in ownership_chain:
        timeline.append({
            'date': own.acquired_at,
            'icon': '🏠',
            'title': f'Novi dom — {own.owner_name}',
            'note': own.owner_city or '',
            'photo': None,
            'type': 'vlasnistvo',
        })

    for hr in health_records:
        timeline.append({
            'date': hr.datum,
            'icon': '💊',
            'title': f'{hr.get_tip_display()} — {hr.veterinar or ""}',
            'note': hr.opis or '',
            'photo': None,
            'type': 'zdravlje',
        })

    for m in milestones:
        timeline.append({
            'date': m.date,
            'icon': m.get_type_display().split(' ')[0],
            'title': m.title,
            'note': m.note,
            'photo': m.photo.url if m.photo else None,
            'type': m.type,
        })

    timeline.sort(key=lambda x: x['date'])

    from django.utils import timezone as _tz
    context = {
        'animal': animal,
        'health_records': health_records,
        'ownership_chain': ownership_chain,
        'milestones': milestones,
        'memorial': memorial,
        'timeline': timeline,
        'generated_at': _tz.now(),
        'request': request,
    }

    # WeasyPrint HTML→PDF
    try:
        import weasyprint
        from django.template.loader import render_to_string
        html_string = render_to_string('memio_pet/knjiga_pdf.html', context, request=request)
        base_url = request.build_absolute_uri('/')
        pdf_bytes = weasyprint.HTML(
            string=html_string,
            base_url=base_url
        ).write_pdf()

        ime = (animal.name or 'ljubimac').replace(' ', '_')
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="memio-knjiga-{ime}.pdf"'
        response['Cache-Control'] = 'no-cache'
        return response

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'knjiga_sjecanja_pdf error: {e}')
        return HttpResponse(f'Greška pri generiranju PDF-a: {e}', status=500, content_type='text/plain')


# ════════════════════════════════════════════════════════════════
# MEMORIAL CANDLE API
# URL: /api/memorial/<chip>/candle/  (POST)
# ════════════════════════════════════════════════════════════════



# ════════════════════════════════════════════════════════════════
# KREMATORIJ DIREKTORIJ
# URL: /krematoriji/
# ════════════════════════════════════════════════════════════════

@require_GET
def krematoriji_lista(request):
    """Javni direktorij krematorija za kućne ljubimce."""
    db = 'memio_pets'
    grad = request.GET.get('grad', '').strip()

    all_qs = BreederProfile.objects.using(db).filter(
        account_type='krematorij'
    ).order_by('city', 'name')

    # Krematoriji koji pokrivaju cijelu HR (poznati po preuzimanju na adresi)
    NATIONWIDE_NAMES = {'Pet 4ever', 'Pet Memo'}

    if grad:
        city_qs = all_qs.filter(city__icontains=grad)
        krematoriji = list(city_qs)
    else:
        krematoriji = list(all_qs)

    # Ako nema rezultata za grad — prikaži SVE s napomenom
    if grad and not krematoriji:
        display_list = list(all_qs)
    else:
        display_list = krematoriji

    # Označi koji pokrivaju cijelu HR
    for k in display_list:
        k.nationwide = k.name in NATIONWIDE_NAMES

    # Nationwide na vrh
    display_list.sort(key=lambda x: (not x.nationwide, x.city))

    return render(request, 'memio_pet/krematoriji.html', {
        'krematoriji': krematoriji,
        'display_list': display_list,
        'total': all_qs.count(),
        'grad_filter': grad,
        'page_title': 'Krematoriji za kućne ljubimce — Memio.pet',
    })


# ════════════════════════════════════════════════════════════════
# PET HOTELI DIREKTORIJ
# URL: /hoteli/
# ════════════════════════════════════════════════════════════════

@require_GET
def hoteli_lista(request):
    """Javni direktorij pet hotela."""
    db = 'memio_pets'
    grad = request.GET.get('grad', '').strip()

    qs = BreederProfile.objects.using(db).filter(
        account_type='hotel'
    ).order_by('city', 'name')

    if grad:
        qs = qs.filter(city__icontains=grad)

    return render(request, 'memio_pet/hoteli_lista.html', {
        'hoteli': list(qs),
        'grad_filter': grad,
        'page_title': 'Pet Hoteli — Memio.pet',
    })


def social_import_wizard(request):
    """Wizard za uvoz objava s društvenih mreža na profil ljubimca."""
    db = 'memio_pets'
    chip = request.GET.get('animal') or request.POST.get('animal')
    animal = _find_animal(chip) if chip else None
    if not animal:
        return redirect('memio_pet:landing')

    preview_data = None
    error = None

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')
        url = request.POST.get('url', '').strip()

        if not url:
            error = 'Upiši link na objavu.'
        elif action == 'preview':
            # Korak 1 → preview
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            from boxgram.services.social_import import fetch_oembed
            preview = fetch_oembed(url)
            if preview.success:
                preview_data = {
                    'platform': preview.platform,
                    'thumbnail': preview.thumbnail_url,
                    'caption': preview.caption or '',
                    'author': preview.author_name or '',
                    'url': url,
                }
            else:
                error = preview.error or 'Nije moguće učitati objavu. Provjeri link.'

        elif action == 'confirm':
            # Korak 2 → spremi kao LifeMilestone
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            title = request.POST.get('title', '').strip()
            if not title:
                title = f'Objava s društvene mreže'
            from memio_pet.models import LifeMilestone
            from django.utils import timezone
            LifeMilestone.objects.using(db).create(
                animal=animal,
                type='custom',
                title=title,
                date=timezone.now().date(),
                note=f'Uvezeno s: {url}',
            )
            identifier = animal.chip_number or animal.ear_tag
            messages.success(request, 'Objava dodana na životni trak!')
            return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    return render(request, 'memio_pet/social_import.html', {
        'animal': animal,
        'chip': chip,
        'preview': preview_data,
        'error': error,
    })


def sitemap_xml(request):
    """Dinamički sitemap.xml za memio.pet."""
    db = 'memio_pets'
    from django.http import HttpResponse
    from django.utils import timezone

    animals = AnimalProfile.objects.using(db).filter(
        status__in=['aktivno', 'u_azilu', 'udomljen', 'uginulo']
    ).order_by('-updated_at')[:5000]

    breeders = BreederProfile.objects.using(db).all().order_by('-updated_at')[:1000]

    urls = []
    # Static pages
    for path in ['/', '/feed/', '/udomljavanje/', '/registracija/', '/prijava/',
                 '/hoteli/', '/krematoriji/', '/barf/']:
        urls.append(f'  <url><loc>https://memio.pet{path}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')

    # Animal profiles
    for a in animals:
        identifier = a.chip_number or a.ear_tag
        urls.append(f'  <url><loc>https://memio.pet/pas/{identifier}/</loc><lastmod>{a.updated_at.strftime("%Y-%m-%d")}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')

    # Breeder profiles
    for b in breeders:
        urls.append(f'  <url><loc>https://memio.pet/uzgajivac/{b.pk}/</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '\n'.join(urls)
    xml += '\n</urlset>'

    return HttpResponse(xml, content_type='application/xml')


def privatnost(request):
    """Privacy policy stranica."""
    return render(request, 'memio_pet/privatnost.html')


@require_POST
def analytics_hit(request):
    """Minimalni analytics — broji pageviews bez cookieja. GDPR safe."""
    import json
    db = 'memio_pets'
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    path = (data.get('p') or request.META.get('HTTP_REFERER', ''))[:200]
    # Spremi u jednostavan log
    import logging
    logger = logging.getLogger('memio_pet.analytics')
    logger.info("HIT %s | %s | %s",
                path,
                request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', '')),
                request.META.get('HTTP_USER_AGENT', '')[:100])
    return JsonResponse({'ok': True})


def uvjeti(request):
    """Uvjeti korištenja stranica."""
    return render(request, 'memio_pet/uvjeti.html')
