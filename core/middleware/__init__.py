import logging
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from core.tenant import set_current_company
from core.company_utils import get_user_company

logger = logging.getLogger(__name__)


class CompanyMiddleware(MiddlewareMixin):
    """Inject current company into thread-local storage.
    Supports multi-company switching via session."""
    def process_request(self, request):
        if not request.user.is_authenticated:
            set_current_company(None)
            request.company = None
            return None

        # Multi-company switching for regular users
        membership_id = request.session.get('active_membership_id')
        if membership_id:
            try:
                from accounts.models import CompanyMembership
                mem = CompanyMembership.objects.select_related('company').get(
                    pk=membership_id, user=request.user, is_active=True
                )
                # In-memory override (NOT saved to DB)
                try:
                    request.user.profile.company = mem.company
                    request.user.profile.role = mem.role
                except Exception:
                    pass
            except Exception:
                request.session.pop('active_membership_id', None)

        company = get_user_company(request)
        set_current_company(company)
        request.company = company
        return None

    def process_response(self, request, response):
        set_current_company(None)
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Log all requests with timing. Warn on slow requests."""
    def process_request(self, request):
        import time
        request._start_time = time.monotonic()
        return None

    def process_response(self, request, response):
        import time
        if hasattr(request, '_start_time'):
            duration = time.monotonic() - request._start_time
            if duration > 2.0:
                logger.warning(f"SLOW {request.method} {request.path} {duration:.2f}s")
            elif settings.DEBUG:
                logger.debug(f"{request.method} {request.path} {response.status_code} {duration:.3f}s")
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses."""
    def process_response(self, request, response):
        # Skip security headers for MCP endpoint (handled by nginx CORS)
        if request.path.startswith('/mcp/'):
            return response
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=(self)'
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        return response


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    """Redirect users who need to change their password."""
    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        if request.user.is_superuser:
            return None
        if request.path.startswith('/accounts/password/') or request.path.startswith('/accounts/logout'):
            return None
        try:
            profile = request.user.profile
            if getattr(profile, 'must_change_password', False):
                from django.shortcuts import redirect
                return redirect('/accounts/password/change/')
        except Exception:
            pass
        return None


class Force2FAMiddleware:
    """
    Blokira superadmin, company_admin i tenant_admin korisnike
    koji nemaju aktiviran TOTP 2FA.
    Preusmjerava ih na /2fa/setup/ dok god totp_enabled != True.

    Anti-loop: poruka se dodaje samo jednom (nema message spama).
    """

    WHITELISTED_PREFIXES = (
        '/2fa/',
        '/accounts/logout',
        '/logout',
        '/static/',
        '/media/',
        '/health/',
        '/api/',
        '/admin/',
        '/__debug__/',
        '/i18n/',
    )

    ENFORCED_ROLES = ('superadmin', 'company_admin', 'tenant_admin')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        # Whitelist — propusti bez provjere
        path = request.path
        for prefix in self.WHITELISTED_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        # Provjeri samo kriticne uloge
        try:
            profile = request.user.userprofile
        except Exception:
            return self.get_response(request)

        if profile.role not in self.ENFORCED_ROLES and not request.user.is_superuser:
            return self.get_response(request)

        # Ako 2FA vec aktiviran — propusti
        if profile.totp_enabled:
            return self.get_response(request)

        # Blokada — preusmjeri na setup (bez message spama)
        from django.contrib import messages
        from django.shortcuts import redirect

        system_message = 'Sustav zahtijeva obaveznu aktivaciju 2FA zaštite za administratore.'
        has_message = False
        storage = messages.get_messages(request)
        for msg in storage:
            if msg.message == system_message:
                has_message = True
                break
        storage.used = False  # Vrati poruke u storage da se prikazu na iducem ekranu

        if not has_message:
            messages.warning(request, system_message)

        return redirect('setup_2fa')




class ForceTCMiddleware:
    """
    Blokira korisnike cija firma NEMA potpisan T&C consent (GDPR cl.6b).
    Bez has_signed_tc_consent=True sustav NE SMIJE agregirati podatke firme.
    Preusmjerava na /legal/tc-consent/ dok admin ne potpise.
    Superadmini su izuzeti.
    """

    WHITELISTED_PREFIXES = (
        '/legal/', '/accounts/logout', '/logout', '/static/', '/media/',
        '/digitalni-posrednik/', '/partners/wizard/',
        '/health/', '/api/', '/admin/', '/__debug__/', '/i18n/', '/2fa/', '/login',
    )

    TC_CURRENT_VERSION = 'v1.0-2026'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        for prefix in self.WHITELISTED_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        company = getattr(request, 'current_company', None)
        if not company:
            try:
                company = request.user.userprofile.company
            except Exception:
                return self.get_response(request)

        if not company:
            return self.get_response(request)

        if company.has_signed_tc_consent and company.tc_consent_version == self.TC_CURRENT_VERSION:
            return self.get_response(request)

        from django.contrib import messages
        from django.shortcuts import redirect

        msg = 'Potrebno je prihvatiti uvjete koristenja LIMIT Connect sustava prije nastavka.'
        storage = messages.get_messages(request)
        has_msg = any(m.message == msg for m in storage)
        storage.used = False
        if not has_msg:
            messages.warning(request, msg)

        return redirect('tc_consent')


class ImpersonationMiddleware(MiddlewareMixin):
    """Allow superadmin to impersonate another company."""
    def process_request(self, request):
        if request.user.is_authenticated and request.user.is_superuser:
            company_id = request.session.get('superadmin_as_company')
            if company_id:
                request._impersonating_company_id = company_id
        return None


class CompanyBranchMiddleware(MiddlewareMixin):
    """Attach current branch to request if set in session."""
    def process_request(self, request):
        if request.user.is_authenticated:
            branch_id = request.session.get('active_branch_id')
            if branch_id:
                try:
                    from companies.models import CompanyBranch
                    request.active_branch = CompanyBranch.objects.get(pk=branch_id)
                except Exception:
                    request.active_branch = None
            else:
                request.active_branch = None
        return None


class UserLanguageMiddleware(MiddlewareMixin):
    """Set UI language from UserProfile.preferred_language.

    Runs BEFORE Django's LocaleMiddleware:
    1. Sets language cookie from profile if mismatch
    2. Redirects unprefixed URLs to language-prefixed URLs
       (e.g. /worktime/ -> /hr/worktime/ for Croatian users)
    """
    SKIP_PREFIXES = (
        '/api/', '/static/', '/media/', '/admin/', '/i18n/',
        '/push/', '/sw.js', '/manifest.json', '/offline.html',
        '/burza/', '/marketplace/', '/delivery/', '/traceability/',
        '/gastro-menu/', '/sos/', '/track/', '/rosetta/',
        '/accounts/login/', '/notifications/',
    )
    LANG_PREFIXES = ('hr', 'en', 'de', 'tr', 'el')

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        try:
            lang = request.user.profile.preferred_language
        except Exception:
            lang = None

        # Fallback: Company.ui_language ako user nema explicit preference
        if not lang:
            try:
                from core.company_utils import get_user_company
                company = get_user_company(request)
                if company:
                    lang = company.ui_language or 'hr'
            except Exception:
                pass

        if not lang:
            return None

        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang != lang:
            request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
            request._set_language_cookie = lang

        # Redirect unprefixed URLs for non-default languages
        if lang in self.LANG_PREFIXES and request.method == 'GET':
            path = request.path
            # Already has correct prefix
            if path.startswith('/' + lang + '/'):
                return None
            # Skip non-i18n paths
            for prefix in self.SKIP_PREFIXES:
                if path.startswith(prefix):
                    return None
            # Skip if path has another language prefix
            for lp in self.LANG_PREFIXES:
                if path.startswith('/' + lp + '/'):
                    return None
            # Redirect to prefixed URL
            from django.shortcuts import redirect as _redir
            new_url = '/' + lang + path
            qs = request.META.get('QUERY_STRING', '')
            if qs:
                new_url += '?' + qs
            return _redir(new_url)

        return None

    def process_response(self, request, response):
        lang = getattr(request, '_set_language_cookie', None)
        if lang:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME, lang,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path='/', samesite='Lax',
            )
        return response




class RateLimitMiddleware:
    """Redis-based rate limiting per IP — pametno po kontekstu."""

    SKIP_PREFIXES = ('/static/', '/media/', '/favicon', '/manifest', '/sw.js', '/health/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Preskoči static/media — nginx ih ionako servira, ovo je fallback
        for prefix in self.SKIP_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', 'unknown')
        is_authenticated = getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False)

        # Autenticirani korisnici — praktično bez limita
        if is_authenticated:
            return self.get_response(request)

        # Login brute-force zaštita — striktno po IP+path
        if ('/login/' in path or '/api/token/' in path or '/password/' in path) and request.method == 'POST':
            limit, window = 20, 60
            key = 'rl:%s:login' % ip
        elif path.startswith('/api/'):
            limit, window = 120, 60
            key = 'rl:%s:api' % ip
        else:
            limit, window = 300, 60
            key = 'rl:%s:page' % ip

        try:
            import redis
            broker = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
            r = redis.Redis.from_url(broker)
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = pipe.execute()
            if count > limit:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Previse zahtjeva. Pricekajte minutu.', 'retry_after': window}, status=429)
        except Exception:
            pass

        return self.get_response(request)



class AdminLangRedirectMiddleware(MiddlewareMixin):
    """
    Redirect /admin/ requests to use the company's preferred language.
    Prevents German users seeing Croatian admin, and vice versa.
    Also handles /rosetta/ and other admin-like paths.
    """

    ADMIN_PREFIXES = ('/admin/', '/rosetta/')

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        if not request.user.is_staff:
            return None

        path = request.path
        is_admin = any(path.startswith(p) for p in self.ADMIN_PREFIXES)
        if not is_admin:
            return None

        # Get user's preferred language
        try:
            lang = request.user.profile.preferred_language
        except Exception:
            lang = None

        if not lang:
            try:
                from core.company_utils import get_user_company
                company = get_user_company(request)
                if company:
                    lang = company.ui_language
            except Exception:
                pass

        if lang:
            from django.utils.translation import activate
            activate(lang)
            request.LANGUAGE_CODE = lang

        return None


# ═══════════════════════════════════════════════════════════════
#  GRACEFUL ERROR HANDLER — Zero Friction Error Experience
# ═══════════════════════════════════════════════════════════════

class GracefulErrorMiddleware:
    """
    Hvata unhandled exceptions i pretvara ih u user-friendly toast redirect.

    Umjesto: 500 page → korisnik klikne "Početna" → izgubljen kontekst
    Sada:    Exception → redirect na referrer/home → zlatni toast
             "Dogodila se greška. Tim je obaviješten."
    """

    ERROR_MESSAGES = {
        'default': 'Dogodila se neočekivana greška. Tim je obaviješten i radi na rješenju.',
        'database': 'Privremeni problem s bazom podataka. Pokušajte ponovo za minutu.',
        'permission': 'Nemate pristup ovom resursu. Kontaktirajte administratora.',
        'timeout': 'Zahtjev je trajao predugo. Pokušajte ponovo.',
        'validation': 'Podaci nisu ispravni. Provjerite unos i pokušajte ponovo.',
    }

    EXCEPTION_MAP = {
        'OperationalError': 'database',
        'InterfaceError': 'database',
        'DatabaseError': 'database',
        'PermissionDenied': 'permission',
        'Forbidden': 'permission',
        'TimeoutError': 'timeout',
        'ConnectionTimeout': 'timeout',
        'ValidationError': 'validation',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Hvata SVE unhandled exceptions prije nego Django renderira 500."""
        import traceback as tb_module
        from django.core.exceptions import (
            DisallowedHost, SuspiciousOperation, PermissionDenied,
        )
        from django.http import Http404

        # Django internal exceptions — pustimo ih, Django ih sam obrađuje
        if isinstance(exception, (DisallowedHost, SuspiciousOperation, Http404)):
            return None

        # PermissionDenied — Django sam radi 403
        if isinstance(exception, PermissionDenied):
            return None

        # API/AJAX — ostavi, vraćaju JSON
        if self._is_api(request):
            return None
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return None
        if 'application/json' in request.headers.get('Accept', ''):
            return None

        exc_name = type(exception).__name__
        category = self.EXCEPTION_MAP.get(exc_name, 'default')
        traceback_str = tb_module.format_exc()

        logger.error(
            'GracefulError [%s] %s %s: %s\n%s',
            category, request.method, request.path, exception, traceback_str,
        )

        # Async alert trojci
        self._notify_team(request, exception, category, traceback_str)

        # Audit log
        self._audit_log(request, exception, category)

        # Redirect s toast porukom
        return self._graceful_redirect(request, category)

    def _graceful_redirect(self, request, category):
        from django.contrib import messages
        from django.shortcuts import redirect

        msg = self.ERROR_MESSAGES.get(category, self.ERROR_MESSAGES['default'])
        messages.error(request, msg)

        referrer = request.META.get('HTTP_REFERER', '')
        if referrer and request.build_absolute_uri() != referrer:
            from urllib.parse import urlparse
            parsed = urlparse(referrer)
            if parsed.netloc == '' or parsed.netloc == request.get_host():
                return redirect(referrer)

        return redirect('/')

    def _notify_team(self, request, exception, category, traceback_str):
        try:
            from core.tasks import notify_error_to_team
            notify_error_to_team.delay(
                user=request.user.username if request.user.is_authenticated else 'anonymous',
                path=request.path,
                method=request.method,
                exc_class=type(exception).__name__,
                exc_message=str(exception)[:500],
                category=category,
                traceback=traceback_str[-2000:],
                ip=request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip(),
            )
        except Exception as e:
            logger.warning('Failed to dispatch error notification: %s', e)

    def _audit_log(self, request, exception, category):
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                company_id=getattr(request, 'company_id', None),
                model_name='_system_error',
                object_id='0',
                action='error',
                changes={
                    'category': category,
                    'exception': type(exception).__name__,
                    'message': str(exception)[:500],
                    'path': request.path,
                    'method': request.method,
                },
                ip_address=request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip(),
            )
        except Exception:
            pass

    @staticmethod
    def _is_api(request):
        return '/api/' in request.path or request.path.startswith('/_dev/')
