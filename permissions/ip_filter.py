"""
IP-based access control middleware.

Restricts access to sensitive paths (admin, superadmin, API) to
whitelisted IP addresses. Regular users are not affected.

Configure in settings.py:
    IP_WHITELIST = ['85.9.201.204', '127.0.0.1', '::1']
    IP_RESTRICTED_PATHS = ['/admin/', '/superadmin/', '/api/synesis/']
    IP_FILTER_ENABLED = True
"""
import logging

from django.conf import settings
from django.http import HttpResponseForbidden
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract real client IP, respecting X-Forwarded-For from nginx."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class IPFilterMiddleware:
    """
    Middleware that blocks requests to restricted paths from non-whitelisted IPs.
    Superusers are always allowed (after login).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'IP_FILTER_ENABLED', False)
        self.whitelist = set(getattr(settings, 'IP_WHITELIST', [
            '127.0.0.1', '::1', 'localhost',
        ]))
        self.restricted_paths = getattr(settings, 'IP_RESTRICTED_PATHS', [
            '/admin/',
            '/superadmin/',
        ])

    def __call__(self, request):
        if self.enabled and self._is_restricted(request.path):
            ip = get_client_ip(request)
            if ip not in self.whitelist:
                # Allow authenticated superusers from any IP
                if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
                    pass
                else:
                    logger.warning(
                        f'IP Filter: blocked {ip} from {request.path}'
                    )
                    return HttpResponseForbidden(
                        '<h1>403 Forbidden</h1>'
                        '<p>Pristup s ove IP adrese nije dozvoljen.</p>'
                        '<p style="color:#64748b;font-size:.8rem">'
                        f'IP: {ip}</p>'
                    )

        return self.get_response(request)

    def _is_restricted(self, path):
        return any(path.startswith(p) for p in self.restricted_paths)
