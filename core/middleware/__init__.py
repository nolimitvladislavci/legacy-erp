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
    """Redis-based rate limiting per IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', 'unknown')

        if '/login/' in path or '/api/token/' in path or '/password/' in path:
            limit, window = 10, 60
        elif path.startswith('/api/') or path.startswith('/_dev/'):
            limit, window = 60, 60
        else:
            limit, window = 300, 60

        key = 'rl:%s:%s' % (ip, path.split('/')[1] if len(path) > 1 else 'root')

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
                return JsonResponse({'error': 'Previse zahtjeva. Pricekajte.', 'retry_after': window}, status=429)
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
