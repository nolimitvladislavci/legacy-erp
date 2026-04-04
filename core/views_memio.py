"""
core/views_memio.py — Javni API za memio.pet domenu

Endpointi (bez autentifikacije, javni):
  POST /api/memio/waitlist/        — Waiting lista
  GET  /api/memio/pet/<chip_id>/   — Javni profil ljubimca (QR kod)
  GET  /api/memio/stats/           — Statistike za landing page (live brojevi)
"""
import json
import logging
from django.contrib.auth.decorators import login_required
from memio_pet.security import rate_limit, add_security_headers, require_memio_key, audit_log
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

# ─── CORS helper ────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    'https://memio.pet',
    'https://www.memio.pet',
    'https://memio.world',
    'https://www.memio.world',
    'https://no-limit.world',
]


def _cors(response, origin=None):
    """Dodaj CORS headere za memio.* domene."""
    if origin in ALLOWED_ORIGINS:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = 'https://memio.pet'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Max-Age'] = '86400'
    return response


# ─── Waiting lista ───────────────────────────────────────────────────────────

@csrf_exempt
@rate_limit("memio_wl", max_requests=5, window_seconds=900)
@require_http_methods(['POST', 'OPTIONS'])
def memio_waitlist(request):
    """
    POST /api/memio/waitlist/
    Body: {name, email, pet_type, user_type, source}
    """
    origin = request.META.get('HTTP_ORIGIN', '')

    # Preflight
    if request.method == 'OPTIONS':
        return _cors(JsonResponse({'ok': True}), origin)

    try:
        raw = json.loads(request.body)
    except Exception:
        return _cors(JsonResponse({'error': 'Invalid JSON'}, status=400), origin)

    from memio_pet.validators import clean_api_input, validate_no_scripts, validate_no_sql
    data = clean_api_input(raw)

    # Provjera XSS/SQL injection na svim string poljima
    for field_val in [data.get('name',''), data.get('email',''), data.get('source','')]:
        try:
            validate_no_scripts(field_val)
            validate_no_sql(field_val)
        except Exception:
            logger.warning("SECURITY memio_waitlist injection: origin=%s", origin)
            return _cors(JsonResponse({'error': 'Nedozvoljeni sadržaj.'}, status=400), origin)

    email = (data.get('email') or '').strip().lower()
    name  = (data.get('name') or '').strip()

    if not email or '@' not in email:
        return _cors(JsonResponse({'error': 'Email obavezan.'}, status=400), origin)
    if not name:
        return _cors(JsonResponse({'error': 'Ime obavezno.'}, status=400), origin)

    # IP (iza nginx proxija)
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )

    from memio_pet.models import WaitlistEntry
    obj, created = WaitlistEntry.objects.using('memio_pets').get_or_create(
        email=email,
        defaults={
            'name': name,
            'pet_type': data.get('pet_type', ''),
            'user_type': data.get('user_type', ''),
            'source': data.get('source', 'memio.pet'),
            'ip': ip,
        }
    )

    if not created:
        logger.info("memio waitlist duplicate: %s", email)

    total = WaitlistEntry.objects.using('memio_pets').count()
    logger.info("memio waitlist signup: %s (%s), total=%d", email, 'new' if created else 'dup', total)

    return _cors(JsonResponse({
        'ok': True,
        'position': total,
        'message': 'Prijava uspješna! Javit ćemo se čim otvorimo.',
    }), origin)


# ─── Javni profil ljubimca (QR) ─────────────────────────────────────────────

@rate_limit("memio_prof", max_requests=30, window_seconds=60)
@require_http_methods(['GET', 'OPTIONS'])
def memio_pet_profile(request, chip_id):
    """
    GET /api/memio/pet/<chip_id>/
    Vraća javne podatke o ljubimcu po broju mikročipa ili ear_tag.
    Koristi se za QR kod na rodovnici.
    """
    origin = request.META.get('HTTP_ORIGIN', '')

    if request.method == 'OPTIONS':
        return _cors(JsonResponse({'ok': True}), origin)

    chip_id = chip_id.strip()
    if not chip_id:
        return _cors(JsonResponse({'error': 'Chip ID obavezan.'}, status=400), origin)

    from memio_pet.models import AnimalProfile

    pet = (
        AnimalProfile.objects.using('memio_pets')
        .filter(chip_number=chip_id)
        .first()
    )
    if not pet:
        pet = (
            AnimalProfile.objects.using('memio_pets')
            .filter(ear_tag=chip_id)
            .first()
        )

    if not pet:
        return _cors(JsonResponse({
            'found': False,
            'message': 'Ljubimac nije pronađen u sustavu.',
        }, status=404), origin)

    # Javni zdravstveni zapisi
    records = list(
        pet.health_records
        .using('memio_pets')
        .filter(tip='cijepljenje')
        .order_by('datum')
        .values('datum', 'opis', 'veterinar', 'lijek')
    )

    breeder = pet.breeder
    profile = {
        'found': True,
        'public_id': str(pet.public_id),
        'name': pet.name or '',
        'vrsta': pet.get_vrsta_display(),
        'breed': pet.breed or '',
        'spol': pet.get_spol_display(),
        'color': pet.color_description or '',
        'chip_number': pet.chip_number or '',
        'pedigree_number': pet.pedigree_number or '',
        'date_of_birth': pet.date_of_birth.isoformat() if pet.date_of_birth else None,
        'father': pet.father_name or '',
        'mother': pet.mother_name or '',
        'breeder': breeder.name if breeder else pet.breeder_name_snapshot,
        'breeder_city': breeder.city if breeder else '',
        'breeder_verified': bool(breeder and breeder.verified_badge) if breeder else False,
        'is_shelter': bool(breeder and breeder.account_type == 'shelter') if breeder else False,
        'shelter_sponsor': (breeder.shelter_sponsor if breeder else '') or '',
        'photo_url': (
            request.build_absolute_uri(pet.photo.url)
            if pet.photo else None
        ),
        'vaccinations': records,
        'verified': pet.is_verified,
    }

    return _cors(JsonResponse(profile), origin)


# ─── Live statistike za landing page ────────────────────────────────────────

@rate_limit("memio_stats", max_requests=60, window_seconds=60)
@require_http_methods(['GET', 'OPTIONS'])
def memio_stats(request):
    """
    GET /api/memio/stats/
    Živi brojevi za hero section na landing pageu.
    Cache 5 minuta.
    """
    origin = request.META.get('HTTP_ORIGIN', '')

    if request.method == 'OPTIONS':
        return _cors(JsonResponse({'ok': True}), origin)

    from django.core.cache import cache
    cached = cache.get('memio_stats')
    if cached:
        return _cors(JsonResponse(cached), origin)

    from memio_pet.models import AnimalProfile, WaitlistEntry

    total_pets     = AnimalProfile.objects.using('memio_pets').count()
    total_waitlist = WaitlistEntry.objects.using('memio_pets').count()
    # Fallback: dodaj i stari waitlist iz core baze dok traje migracija
    try:
        from core.models import MemioPetWaitlist
        total_waitlist += MemioPetWaitlist.objects.count()
    except Exception:
        pass

    data = {
        'ljubimaca': total_pets,
        'uzgajivaca': AnimalProfile.objects.using('memio_pets').values('breeder').distinct().count(),
        'waitlist': total_waitlist,
        'drzava': 1,  # Hrvatska (za sada)
    }
    cache.set('memio_stats', data, 300)
    return _cors(JsonResponse(data), origin)


# ─── Push: LIMIT Connect → memio_pets baza ──────────────────────────────────

@login_required
@require_memio_key
@rate_limit("memio_push", max_requests=100, window_seconds=3600)
@require_http_methods(['POST'])
def memio_push(request):
    """
    POST /api/memio/push/
    LIMIT Connect šalje ljubimca u memio.pet bazu.
    Autoriziran sesijom (login_required) — interno.
    """
    try:
        data = json.loads(request.body)
        livestock_id = data.get('livestock_id')
        if not livestock_id:
            return JsonResponse({'error': 'livestock_id obavezan.'}, status=400)

        from livestock.models import Livestock
        from core.company_utils import get_user_company
        from memio_pet.bridge import push_animal_profile, push_health_record

        company = get_user_company(request)
        pet = Livestock.objects.filter(pk=livestock_id, company=company).first()
        if not pet:
            return JsonResponse({'error': 'Ljubimac nije pronađen.'}, status=404)

        if pet.vrsta not in Livestock.PET_VRSTE:
            return JsonResponse({'error': 'Nije ljubimac (vrsta).'}, status=400)

        profile = push_animal_profile(pet)

        # Pushaj i zdravstvene zapise
        for rec in pet.health_records.all():
            push_health_record(rec, animal_profile=profile)

        return JsonResponse({
            'ok': True,
            'public_id': str(profile.public_id),
            'public_url': profile.public_url,
            'message': f'{pet.name or pet.ear_tag} sinkroniziran na Memio.pet.',
        })

    except Exception as e:
        logger.error("memio_push: %s", e)
        return JsonResponse({'error': str(e)[:200]}, status=500)
