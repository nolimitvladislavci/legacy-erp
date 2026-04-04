"""
memio_pet/security.py — Obrambeni sloj memio.pet API-ja

Doktrina: "Blockchain razina zaštite"
Svaki zahtjev prolazi kroz:
  1. Rate limiting (Django cache)
  2. Input validaciju (validators.py)
  3. HMAC potpis za privilegirane operacije
  4. Security headere na svim odgovorima
  5. Audit log svakog sumnjivog zahtjeva
"""
import hashlib
import hmac
import logging
import time
from functools import wraps
from django.contrib.auth.decorators import login_required  # BUG-1 fix
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger('memio_pet.security')

# ─── Security Headers ───────────────────────────────────────────���────────────

def add_security_headers(response):
    """Dodaj sigurnosne headere na svaki odgovor memio API-ja."""
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['X-XSS-Protection'] = '1; mode=block'
    response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response['Cache-Control'] = 'no-store'
    # Nema Authorization headera u odgovoru
    response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


# ─── Rate Limiting ───────────────────────────────────────────────────────────

def rate_limit(key_prefix: str, max_requests: int, window_seconds: int):
    """
    Dekorator za rate limiting.
    key_prefix: identifikator endpointa
    max_requests: maks zahtjeva u prozoru
    window_seconds: veličina vremenskog prozora
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # Ključ: IP adresa + endpoint
            ip = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR', 'unknown')
            )
            cache_key = f"rl:{key_prefix}:{ip}"
            count = cache.get(cache_key, 0)

            if count >= max_requests:
                logger.warning(
                    "RATE LIMIT prekoračen: %s IP=%s count=%d",
                    key_prefix, ip, count
                )
                resp = JsonResponse(
                    {'error': 'Previše zahtjeva. Pokušajte za nekoliko minuta.'},
                    status=429
                )
                resp['Retry-After'] = str(window_seconds)
                return add_security_headers(resp)

            cache.set(cache_key, count + 1, timeout=window_seconds)
            response = view_func(request, *args, **kwargs)
            return add_security_headers(response)
        return wrapped
    return decorator


# ─── HMAC API Key (za push endpoint) ─────────────────────────────────────────

def generate_api_key(company_id: str, secret: str) -> str:
    """
    Generira HMAC-SHA256 API ključ za kompaniju.
    Format: memio_{hex(hmac)}
    """
    msg = f"memio:{company_id}:{int(time.time() // 86400)}"  # mijenja se dnevno
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"memio_{sig[:32]}"


def verify_memio_api_key(request, company) -> bool:
    """
    Verificira API ključ iz X-Memio-Key headera.
    Kompanija mora imati validan ključ u BreederProfile.
    """
    from django.conf import settings
    provided_key = request.META.get('HTTP_X_MEMIO_KEY', '')

    if not provided_key:
        return False

    try:
        from memio_pet.models import BreederProfile
        profile = BreederProfile.objects.using('memio_pets').get(
            limit_company_id=str(company.pk)
        )
        # Provjeri da ključ odgovara UUID api_key
        return str(profile.api_key) == provided_key
    except Exception:
        return False


def require_memio_key(view_func):
    """
    Dekorator: zahtijeva X-Memio-Key header za pristup.
    Koristi se uz login_required za dvostruku zaštitu.
    """
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        from core.company_utils import get_user_company
        company = get_user_company(request)

        if not company:
            resp = JsonResponse({'error': 'Nema aktivne firme.'}, status=403)
            return add_security_headers(resp)

        if not verify_memio_api_key(request, company):
            logger.warning(
                "SECURITY: Nevalidan Memio API ključ. company=%s IP=%s",
                company.pk,
                request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            )
            resp = JsonResponse(
                {'error': 'Nevalidan API ključ. Pristup odbijen.'},
                status=401
            )
            return add_security_headers(resp)

        return view_func(request, *args, **kwargs)
    return wrapped


# ─── Audit Log ───────────────────────────────────────────────────────────────

def audit_log(event: str, request, extra: dict = None):
    """Bilježi sigurnosne događaje u log."""
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', 'unknown')
    )
    ua = request.META.get('HTTP_USER_AGENT', '')[:100]
    origin = request.META.get('HTTP_ORIGIN', '')

    logger.info(
        "AUDIT [memio] event=%s ip=%s origin=%s ua=%s extra=%s",
        event, ip, origin, ua, extra or {}
    )
