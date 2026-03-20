import logging
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from core.tenant import set_current_company
from core.company_utils import get_user_company

logger = logging.getLogger(__name__)


class CompanyMiddleware(MiddlewareMixin):
    """Inject current company into thread-local storage."""
    def process_request(self, request):
        if request.user.is_authenticated:
            company = get_user_company(request)
            set_current_company(company)
        else:
            set_current_company(None)
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
    """Add security headers + CSP to all responses."""
    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com fonts.googleapis.com; "
            "img-src 'self' data: blob:; "
            "font-src 'self' fonts.gstatic.com cdnjs.cloudflare.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
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



class RateLimitMiddleware:
    """
    Redis-based rate limiting.
    - Auth: 10 req/min
    - API: 60 req/min
    - Dev API: 30 req/min
    - General: 300 req/min
    """

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

        key = 'rl:%s:%s' % (ip, path.split('/')[1] if '/' in path[1:] else 'root')

        try:
            import redis
            from django.conf import settings as _s
            broker = getattr(_s, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
            r = redis.Redis.from_url(broker)
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = pipe.execute()

            if count > limit:
                from django.http import JsonResponse
                return JsonResponse({
                    'error': 'Previse zahtjeva. Pricekajte.',
                    'retry_after': window
                }, status=429)
        except Exception:
            pass

        return self.get_response(request)
