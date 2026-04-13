"""
T&C Consent Middleware
Ako firma nije potpisala uvjete korištenja → redirect na /legal/tc-accept/
Exempt: superadmin, API, ajax, login, static, media, legal pages
"""
from django.shortcuts import redirect

EXEMPT_PREFIXES = (
    '/admin/', '/api/', '/hr/login', '/hr/logout', '/legal/',
    '/static/', '/media/', '/_dev/', '/mcp/', '/health',
    '/invoicing/portal/', '/invoicing/client/', '/invoicing/public/',
    '/eracun/', '/einvoice/',
)
EXEMPT_AJAX = True


class TCConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Preskoci exempt putanje
        path = request.path
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return self.get_response(request)

        # Preskoci AJAX i API pozive
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_response(request)
        if 'application/json' in request.headers.get('Accept', ''):
            return self.get_response(request)

        # Preskoci ne-autenticirane
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Preskoci superadmin
        if request.user.is_superuser:
            return self.get_response(request)

        # Provjeri T&C za aktivnu kompaniju
        try:
            company = getattr(request, 'company', None)
            if company and not company.has_signed_tc_consent:
                tc_url = '/legal/tc-accept/'
                if path != tc_url:
                    return redirect(tc_url)
        except (AttributeError, TypeError):
            pass

        return self.get_response(request)
