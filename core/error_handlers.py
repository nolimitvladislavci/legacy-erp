"""
core/error_handlers.py — Custom error handlers (404, 500)
Izdvojeno iz urls.py da se izbjegne circular import pri test DB kreaciji.
"""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.shortcuts import render

logger = logging.getLogger(__name__)


def custom_403_handler(request, exception=None):
    """403 → tenant izolacija ili permission denied."""
    return render(request, "403.html", status=403)


def custom_404_handler(request, exception=None):
    """404 → renders 404 stranica s FenixSignal gumbom."""
    # Auto-report za ulogirane korisnike
    try:
        if hasattr(request, "user") and request.user.is_authenticated:
            from limit_connect_ai.models_signal import FenixSignal

            FenixSignal.objects.create(
                user=request.user,
                company=getattr(request, "current_company", None),
                signal_type="bug",
                source="in_app",
                message=f"404 na {request.path}",
                page_url=request.build_absolute_uri(),
                context={"referrer": request.META.get("HTTP_REFERER", ""), "auto": True},
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
    except (IntegrityError, DatabaseError):
        pass
    return render(request, "404.html", status=404)


def custom_500_handler(request):
    """500 → BORG ingestion + redirect na početnu s porukom."""
    # Fire-and-forget: BORG hvata kontekst
    try:
        capture_error_for_borg(request)
    except Exception:
        logger.exception("Unexpected error in: capture_error_for_borg(request)")

    # Redirect na početnu s error porukom
    from django.contrib import messages
    from django.shortcuts import redirect

    try:
        messages.error(
            request,
            "Došlo je do greške. Tim je obaviješten i radi na rješenju. Pokušajte ponovo ili kontaktirajte podršku.",
        )
        return redirect("/")
    except Exception:
        # Ako ni redirect ne radi (session corruption), vrati static 500
        return render(request, "500.html", status=500)


# ═══════════════════════════════════════════════════
#  BORG AUTO-REMEDIATION — Error Ingestion Pipeline
# ═══════════════════════════════════════════════════

import logging
import traceback

from django.utils import timezone

logger = logging.getLogger("borg.remediation")


def capture_error_for_borg(request, exc_info=None):
    """
    Hvata 500 error kontekst i kreira PendingAIAction za BORG analizu.

    Poziva se iz custom_500_handler ili middleware.
    Ne blokira user experience — fire-and-forget.

    Kontekst koji se hvata:
      - Stack trace (zadnjih 50 linija)
      - URL + HTTP method
      - User ID + company
      - Request body (sanitizirano — bez passworda)
      - Zadnjih 20 linija gunicorn error loga
    """
    try:
        import sys

        exc_info = exc_info or sys.exc_info()

        # Stack trace
        tb_lines = traceback.format_exception(*exc_info) if exc_info[0] else []
        stack_trace = "".join(tb_lines)[-3000:]  # max 3K chars

        # Request context
        url = getattr(request, "path", "?")
        method = getattr(request, "method", "?")
        user_id = getattr(request.user, "id", None) if hasattr(request, "user") else None
        user_name = str(getattr(request.user, "username", "?")) if hasattr(request, "user") else "?"

        # Company context
        company_id = None
        company_name = None
        try:
            company = getattr(request, "current_company", None)
            if not company and hasattr(request, "user") and hasattr(request.user, "userprofile"):
                company = request.user.profile.company
            if company:
                company_id = str(company.pk)
                company_name = company.name
        except (ValueError, TypeError):
            logger.exception("HTTP request failed")

        # Sanitize POST data (remove passwords, tokens)
        post_data = {}
        if hasattr(request, "POST") and request.POST:
            sensitive_keys = {"password", "token", "secret", "key", "csrf", "otp", "pin"}
            post_data = {
                k: "***" if any(s in k.lower() for s in sensitive_keys) else str(v)[:200]
                for k, v in request.POST.items()
            }

        # Error log tail (zadnjih 20 linija)
        error_log_tail = ""
        try:
            import subprocess

            result = subprocess.run(
                ["tail", "-20", "/var/log/gunicorn/error.log"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            error_log_tail = result.stdout[-2000:] if result.stdout else ""
        except Exception:
            logger.exception("Failed to import subprocess")

        # Error type extraction
        error_type = exc_info[0].__name__ if exc_info[0] else "Unknown"
        error_msg = str(exc_info[1])[:500] if exc_info[1] else ""

        # Extract file + line from traceback
        source_file = ""
        source_line = 0
        if exc_info[2]:
            import os

            tb = exc_info[2]
            while tb.tb_next:
                tb = tb.tb_next
            source_file = os.path.basename(tb.tb_frame.f_code.co_filename)
            source_line = tb.tb_lineno

        # Kreira PendingAIAction
        from companies.models import Company
        from superadmin_ai.models import PendingAIAction

        company_obj = None
        if company_id:
            try:
                company_obj = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                pass

        action = PendingAIAction.objects.create(
            company=company_obj,
            module="error_remediation",
            action_type="auto_fix",
            description=(
                f"500 Error: {error_type} u {source_file}:{source_line}\n"
                f"URL: {method} {url}\n"
                f"User: {user_name} (ID: {user_id})\n"
                f"Firma: {company_name or '?'}\n"
                f"Poruka: {error_msg}"
            ),
            payload={
                "error_type": error_type,
                "error_message": error_msg,
                "stack_trace": stack_trace,
                "url": url,
                "method": method,
                "user_id": user_id,
                "user_name": user_name,
                "company_id": company_id,
                "company_name": company_name,
                "post_data": post_data,
                "error_log_tail": error_log_tail,
                "source_file": source_file,
                "source_line": source_line,
                "timestamp": timezone.now().isoformat(),
                "server": "37.27.248.86",
            },
            status="pending",
        )

        logger.info(
            "BORG ingestion: Error #%s — %s in %s:%d (user=%s, company=%s)",
            action.pk,
            error_type,
            source_file,
            source_line,
            user_name,
            company_name,
        )

        return action

    except ObjectDoesNotExist as e:
        # NIKADA ne crashaj error handler
        logger.error("BORG ingestion failed: %s", e)
        return None
