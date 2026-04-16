"""
Identity Middleware — Ghost State Interceptor
=============================================
Bankarski model: uđi slobodno, ali dok se ne verificiraš —
ostaneš na čekaonici (/pristup/).

IMPORTANT: Ne blokira agresivno. Preusmjerava na /pristup/
gdje korisnik bira: kreiraj firmu, pridruži se, ili kontaktiraj.
"""
import logging

from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger("identity.middleware")

GHOST_ALLOWED_PATHS = (
    "/accounts/",
    "/pristup/",
    "/identity/",
    "/static/",
    "/media/",
    "/admin/",
    "/superadmin/",
    "/hr/logout/",
    "/logout/",
    "/api/security/",
    "/health/",
    "/qr/",
    "/api/oib/",
)


class GhostStateMiddleware:
    """
    Presreće korisnike u Ghost stanju (autentificiran, company=NULL).
    Preusmjerava na /pristup/ gdje se nudi put verifikacije.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_intercept(request):
            logger.info(
                "GHOST_INTERCEPT: user=%s path=%s",
                request.user.username, request.path
            )
            # Logiraj ghost state event (ne prečesto — throttle)
            self._log_ghost_once(request)
            return redirect("/pristup/")
        return self.get_response(request)

    def _should_intercept(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return False

        # Ne presreći dopuštene putanje
        path = request.path
        for allowed in GHOST_ALLOWED_PATHS:
            if path.startswith(allowed):
                return False

        # Ghost state detekcija
        from .engine import detect_ghost_state
        return detect_ghost_state(request.user)

    def _log_ghost_once(self, request):
        """Log samo jednom po sesiji da ne spamamo audit log."""
        key = f"ghost_logged_{request.user.id}"
        if not request.session.get(key):
            request.session[key] = True
            from .models import IdentityAuditLog
            try:
                IdentityAuditLog.log(
                    "login_no_company",
                    user=request.user,
                    ip=request.META.get("REMOTE_ADDR"),
                    ua=request.META.get("HTTP_USER_AGENT", "")[:200],
                    detail={"path": request.path}
                )
            except Exception:
                pass
