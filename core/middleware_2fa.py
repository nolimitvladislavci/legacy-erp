"""
Force2FAMiddleware — tjera superadmine i company admine na 2FA setup.

Pravila:
- Ako je user.profile.role in (superadmin, company_admin) I totp_enabled=False
  → redirect na /2fa/setup/ (osim whitelist URL-ova)
- Poruka se prikazuje JEDNOM po sesiji (nema spama)
- API endpointi, statički fajlovi i login/logout se NE diraju
"""
import logging

from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger(__name__)

# URL-ovi koji se NE blokiraju (korisnik ih mora moći otvoriti bez 2FA)
EXEMPT_PATHS = (
    '/2fa/',
    '/login/',
    '/logout/',
    '/admin/login/',
    '/static/',
    '/media/',
    '/api/',
    '/pos/sw.js',
    '/pos/api/',
    '/password-reset/',
    '/_dev/',
)

FORCED_ROLES = ('superadmin', 'company_admin')


class Force2FAMiddleware:
    """
    Middleware koji tjera privilegirane korisnike na aktivaciju 2FA.
    Bez 2FA = nema pristupa sustavu (osim /2fa/setup/).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Propusti ako nije autentificiran
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Propusti exempt pathove
        path = request.path
        if any(path.startswith(p) for p in EXEMPT_PATHS):
            return self.get_response(request)

        # Provjeri profil
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return self.get_response(request)

        role = getattr(profile, 'role', '')
        totp_enabled = getattr(profile, 'totp_enabled', False)

        # Ako nije privilegirani role ili već ima 2FA → propusti
        if role not in FORCED_ROLES or totp_enabled:
            return self.get_response(request)

        # ── Force redirect na 2FA setup ──────────────────────────────
        # Poruka samo jednom po sesiji (anti-spam)
        session_key = '_2fa_warning_shown'
        if not request.session.get(session_key):
            messages.warning(
                request,
                'Vaš račun zahtijeva dvofaktorsku autentifikaciju (2FA). '
                'Molimo aktivirajte je prije nastavka rada.',
            )
            request.session[session_key] = True

        return redirect('setup_2fa')
