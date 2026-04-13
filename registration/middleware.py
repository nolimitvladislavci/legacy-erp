from django.db import DatabaseError

from .constants import MODULE_URL_MAP


class SubscriptionMiddleware:
    ALWAYS_ALLOWED_PREFIXES = (
        '/admin/',
        '/accounts/',
        '/register/',
        '/superadmin/',
        '/static/',
        '/media/',
        '/dashboard/',
        '/companies/',
        '/permissions/',
        '/website/',
        '/grosmarkt/',
        '/api/grosmarkt/',
        '/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requires_check(request):
            result = self._check_subscription(request)
            if result is not None:
                return result
        return self.get_response(request)

    def _requires_check(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return False
        path = request.path
        for prefix in self.ALWAYS_ALLOWED_PREFIXES:
            if path == prefix or (prefix != '/' and path.startswith(prefix)):
                return False
        return self._get_required_module(request.path) is not None

    def _get_required_module(self, path):
        for prefix, module in MODULE_URL_MAP.items():
            if path.startswith(prefix):
                return module
        return None

    def _check_subscription(self, request):
        required_module = self._get_required_module(request.path)
        if not required_module:
            return None
        company = getattr(request, 'company', None)
        if not company:
            try:
                company = request.user.profile.company
            except AttributeError:
                return None
        if not company:
            return None
        # Platform owner bypass — all modules unlocked
        if getattr(company, 'is_platform_owner', False):
            return None
        # Superadmin impersonating — bypass subscription check
        if getattr(request, 'impersonation_active', False):
            return None
        try:
            subscription = company.subscriptions.filter(is_active=True).order_by('-valid_from').first()
        except DatabaseError:
            return None

        # ── SOFT GATE: nikad ne blokiraj, samo označi za banner ──
        # Svi moduli uvijek dostupni. Upgrade poruka se prikazuje u UI-ju.
        # Korisnik vidi vrijednost PRIJE nego što plati.
        request.upgrade_hint = None
        if not subscription:
            request.upgrade_hint = required_module
        elif not subscription.has_module(required_module):
            request.upgrade_hint = required_module
        # NIKAD redirect — korisnik prolazi, vidi banner
        return None
