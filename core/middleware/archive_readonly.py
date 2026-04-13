"""
Archive Readonly Middleware

When a company's subscription plan is 'archive_readonly', block all
mutating requests (POST/PUT/PATCH/DELETE) except for logout and
language switching. This ensures 11-year legal archive access
(ZOR čl. 10, Zakon o računovodstvu) while preventing data modification.
"""
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

# URLs that are always allowed even in readonly mode
EXEMPT_PATHS = (
    '/accounts/logout/',
    '/i18n/setlang/',
    '/admin/',
    '/health/',
    '/mcp/',
)


class ArchiveReadonlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if self._is_archive_readonly(request):
                if not any(request.path.startswith(p) for p in EXEMPT_PATHS):
                    if request.headers.get('Accept', '').startswith('application/json'):
                        return JsonResponse({
                            'error': 'readonly',
                            'message': str(_('Vaša pretplata je istekla. Arhiva je dostupna samo za čitanje.')),
                        }, status=403)
                    messages.warning(request, _(
                        'Vaša pretplata je istekla. Arhiva je dostupna samo za čitanje. '
                        'Kontaktirajte nas za obnovu pretplate.'
                    ))
                    return redirect(request.META.get('HTTP_REFERER', '/'))
        return self.get_response(request)

    def _is_archive_readonly(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return False
        try:
            company = request.user.profile.company
            if not company:
                return False
            sub = company.subscriptions.filter(
                is_active=True
            ).order_by('-valid_from').first()
            if sub and sub.plan == 'archive_readonly':
                return True
        except Exception:
            pass
        return False
