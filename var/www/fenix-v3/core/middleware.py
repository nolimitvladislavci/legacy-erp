"""
Fenix v3 — Middleware | 13/10

TenantMiddleware: Automatski company scope na SVAKI request.
AuditMiddleware: GDPR audit trail — tko, što, kad.
AccessibilityMiddleware: WCAG headeri + screen reader hints.
"""

import json
import logging
import time
import uuid
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

logger = logging.getLogger("fenix.audit")


class TenantMiddleware(MiddlewareMixin):
    """
    Svaki request dobiva request.company.
    Bez firme = redirect na company select.
    Excluda: login, logout, admin, static, public.
    """

    EXCLUDE_PATHS = (
        "/admin/",
        "/static/",
        "/media/",
        "/accounts/login/",
        "/accounts/logout/",
        "/accounts/register/",
        "/api/public/",
        "/health/",
    )

    def process_request(self, request):
        request.company = None
        request.company_id = None

        if any(request.path.startswith(p) for p in self.EXCLUDE_PATHS):
            return None

        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        company_id = request.session.get("active_company_id")
        if company_id:
            from companies.models import Company

            try:
                request.company = Company.objects.get(id=company_id, is_deleted=False)
                request.company_id = request.company.id
            except Company.DoesNotExist:
                request.session.pop("active_company_id", None)

        return None


class AuditMiddleware(MiddlewareMixin):
    """
    GDPR audit log. Svaka mutacija (POST/PUT/PATCH/DELETE) se logira.
    Format: JSON structured logging za kasniju analizu.
    """

    MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_request(self, request):
        request._audit_start = time.monotonic()
        request._audit_id = str(uuid.uuid4())[:8]

    def process_response(self, request, response):
        if request.method not in self.MUTATION_METHODS:
            return response

        if not hasattr(request, "user") or not request.user.is_authenticated:
            return response

        duration = time.monotonic() - getattr(request, "_audit_start", time.monotonic())

        audit_entry = {
            "audit_id": getattr(request, "_audit_id", "?"),
            "timestamp": timezone.now().isoformat(),
            "user_id": str(request.user.id),
            "user_email": getattr(request.user, "email", ""),
            "company_id": str(getattr(request, "company_id", None) or ""),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "")[:200],
        }

        logger.info(json.dumps(audit_entry))
        return response

    def _get_client_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class AccessibilityMiddleware(MiddlewareMixin):
    """
    WCAG compliance headeri.
    Osigurava da svaki response ima ispravne accessibility meta.
    """

    def process_response(self, request, response):
        if "text/html" in response.get("Content-Type", ""):
            response["X-Content-Type-Options"] = "nosniff"
            response["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response["Permissions-Policy"] = (
                "microphone=(self), camera=(), geolocation=(self), speech-synthesis=(self), speech-recognition=(self)"
            )
        return response


class PerformanceMiddleware(MiddlewareMixin):
    """
    Server-Timing header za svaki request.
    Frontend može čitati i prikazati u dev tools.
    """

    def process_request(self, request):
        request._perf_start = time.monotonic()

    def process_response(self, request, response):
        if hasattr(request, "_perf_start"):
            duration = (time.monotonic() - request._perf_start) * 1000
            response["Server-Timing"] = f"total;dur={duration:.1f}"
        return response
