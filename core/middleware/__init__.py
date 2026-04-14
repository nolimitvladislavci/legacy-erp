import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.utils.deprecation import MiddlewareMixin

from core.company_utils import get_user_company
from core.tenant import set_current_company

logger = logging.getLogger(__name__)


class CompanyMiddleware(MiddlewareMixin):
    """Inject current company into thread-local storage.
    Supports multi-company switching via session."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            set_current_company(None)
            request.company = None
            return None

        # Multi-company switching — session membership ima prioritet
        membership_id = request.session.get("active_membership_id")
        if membership_id:
            try:
                from accounts.models import CompanyMembership

                mem = CompanyMembership.objects.select_related("company").get(
                    pk=membership_id, user=request.user, is_active=True
                )
                # Postavi direktno — zaobiđi get_user_company koji gleda profile
                try:
                    request.user.profile.company = mem.company
                    request.user.profile.role = mem.role
                except AttributeError:
                    pass
                set_current_company(mem.company)
                request.company = mem.company
                return None
            except AttributeError:
                request.session.pop("active_membership_id", None)

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

        if hasattr(request, "_start_time"):
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
        if request.path.startswith("/mcp/"):
            return response
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(self)"
        if not settings.DEBUG:
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
            response["Content-Security-Policy"] = (
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
        if (
            request.path.startswith("/accounts/password/")
            or request.path.startswith("/accounts/logout")
            or request.path.startswith("/onboarding/")
        ):
            return None
        try:
            profile = request.user.profile
            if getattr(profile, "must_change_password", False):
                from django.shortcuts import redirect

                return redirect("/accounts/password/change/")
        except ImportError:
            pass
        return None


class Force2FAMiddleware:
    """
    Blokira admin korisnike bez aktiviranog TOTP 2FA.
    FAL Faza 1: koristi RouteRegistry.is_public() umjesto path string matchinga.
    Rješava i18n bug: /hr/2fa/setup/ i /en/2fa/setup/ obje su PUBLIC.
    """

    ENFORCED_ROLES = ("superadmin", "company_admin", "tenant_admin")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from permissions.route_registry import RouteRegistry

        # Nelogirani → propusti
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return self.get_response(request)

        # Javne rute (PUBLIC + AUTHENTICATED) → propusti bez provjere 2FA
        if RouteRegistry.is_public(request) or RouteRegistry.requires_auth_only(request):
            return self.get_response(request)

        # 2FA setup/verify view — uvijek propusti (view_name check kao sigurnosna mreža)
        view_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
        if view_name in ("setup_2fa", "verify_2fa"):
            return self.get_response(request)

        # Superuseri izuzeti od 2FA enforcement-a
        if request.user.is_superuser:
            return self.get_response(request)

        # Provjeri samo kriticne uloge
        try:
            profile = request.user.profile
        except AttributeError:
            return self.get_response(request)

        if profile.role not in self.ENFORCED_ROLES:
            return self.get_response(request)

        # Ako 2FA vec aktiviran — propusti
        if profile.totp_enabled:
            return self.get_response(request)

        # Blokada — preusmjeri na setup (bez message spama)
        from django.contrib import messages
        from django.shortcuts import redirect

        system_message = "Sustav zahtijeva obaveznu aktivaciju 2FA zaštite za administratore."
        has_message = False
        storage = messages.get_messages(request)
        for msg in storage:
            if msg.message == system_message:
                has_message = True
                break
        if hasattr(storage, "used"):
            storage.used = False  # Vrati poruke u storage da se prikazu na iducem ekranu

        if not has_message:
            messages.warning(request, system_message, fail_silently=True)

        return redirect("setup_2fa")


class ForceTCMiddleware:
    """
    Blokira korisnike cija firma NEMA potpisan T&C consent (GDPR cl.6b).
    Bez has_signed_tc_consent=True sustav NE SMIJE agregirati podatke firme.
    Preusmjerava na /legal/tc-consent/ dok admin ne potpise.
    Superadmini su izuzeti.
    """

    TC_CURRENT_VERSION = "v1.0-2026"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from permissions.route_registry import AccessLevel, RouteRegistry

        # Nelogirani → propusti
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return self.get_response(request)

        # Javne i samo-authenticated rute ne trebaju TC consent
        level = RouteRegistry.get_access_level(request)
        if level in (AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED):
            return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        company = getattr(request, "current_company", None)
        if not company:
            try:
                company = request.user.profile.company
            except AttributeError:
                return self.get_response(request)

        if not company:
            return self.get_response(request)

        if company.has_signed_tc_consent and company.tc_consent_version == self.TC_CURRENT_VERSION:
            return self.get_response(request)

        from django.contrib import messages
        from django.shortcuts import redirect

        msg = "Potrebno je prihvatiti uvjete koristenja LIMIT Connect sustava prije nastavka."
        storage = messages.get_messages(request)
        has_msg = any(m.message == msg for m in storage)
        storage.used = False
        if not has_msg:
            messages.warning(request, msg, fail_silently=True)

        return redirect("tc_consent")


class ImpersonationMiddleware(MiddlewareMixin):
    """Allow superadmin to impersonate another company."""

    def process_request(self, request):
        if request.user.is_authenticated and request.user.is_superuser:
            company_id = request.session.get("superadmin_as_company")
            if company_id:
                request._impersonating_company_id = company_id
        return None


class CompanyBranchMiddleware(MiddlewareMixin):
    """Attach current branch to request if set in session."""

    def process_request(self, request):
        if request.user.is_authenticated:
            branch_id = request.session.get("active_branch_id")
            if branch_id:
                try:
                    from companies.models import CompanyBranch

                    request.active_branch = CompanyBranch.objects.get(pk=branch_id)
                except ObjectDoesNotExist:
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
        "/api/",
        "/static/",
        "/media/",
        "/admin/",
        "/i18n/",
        "/push/",
        "/sw.js",
        "/manifest.json",
        "/offline.html",
        "/burza/",
        "/marketplace/",
        "/delivery/",
        "/traceability/",
        "/gastro-menu/",
        "/sos/",
        "/track/",
        "/rosetta/",
        "/accounts/login/",
        "/notifications/",
        "/firma/",
        "/pocni/",
        "/informacijski-posrednik/",
        "/inspektor/",
        "/panic/",
        "/inspektor",
        "/gov_export/",
        "/no-limit/",
        "/legal/",
    )
    LANG_PREFIXES = ("hr", "en", "de", "tr", "el")

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        try:
            lang = request.user.profile.preferred_language
        except AttributeError:
            lang = None

        # Fallback: Company.ui_language ako user nema explicit preference
        if not lang:
            try:
                from core.company_utils import get_user_company

                company = get_user_company(request)
                if company:
                    lang = company.ui_language or "hr"
            except ImportError:
                pass

        if not lang:
            return None

        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang != lang:
            request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
            request._set_language_cookie = lang

        # Redirect unprefixed URLs for non-default languages
        if lang in self.LANG_PREFIXES and request.method == "GET":
            path = request.path
            # Already has correct prefix
            if path.startswith("/" + lang + "/"):
                return None
            # Skip non-i18n paths
            for prefix in self.SKIP_PREFIXES:
                if path.startswith(prefix):
                    return None
            # Skip if path has another language prefix
            for lp in self.LANG_PREFIXES:
                if path.startswith("/" + lp + "/"):
                    return None
            # Redirect to prefixed URL
            from django.shortcuts import redirect as _redir

            new_url = "/" + lang + path
            qs = request.META.get("QUERY_STRING", "")
            if qs:
                new_url += "?" + qs
            return _redir(new_url)

        return None

    def process_response(self, request, response):
        lang = getattr(request, "_set_language_cookie", None)
        if lang:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                lang,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path="/",
                samesite="Lax",
            )
        return response


class RateLimitMiddleware:
    """Redis-based rate limiting per IP — pametno po kontekstu."""

    SKIP_PREFIXES = ("/static/", "/media/", "/favicon", "/manifest", "/sw.js", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Preskoči static/media — nginx ih ionako servira, ovo je fallback
        for prefix in self.SKIP_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "unknown")
        is_authenticated = getattr(request, "user", None) and getattr(request.user, "is_authenticated", False)

        # Autenticirani korisnici — bez limita
        if is_authenticated:
            return self.get_response(request)

        # Whitelist IP-ova (admin, office) — bez limita
        WHITELIST_IPS = getattr(
            settings,
            "RATE_LIMIT_WHITELIST",
            [
                "37.27.248.86",  # Server
                "127.0.0.1",  # Localhost
            ],
        )
        if ip in WHITELIST_IPS:
            return self.get_response(request)

        # Login brute-force zaštita — striktno po IP+path
        if ("/login/" in path or "/api/token/" in path or "/password/" in path) and request.method == "POST":
            limit, window = 20, 300  # 20 login pokusaja u 5 min (brute-force)
            key = "rl:%s:login" % ip
        elif path.startswith("/api/"):
            limit, window = 600, 60  # 600/min za API
            key = "rl:%s:api" % ip
        else:
            limit, window = 1000, 60  # 1000/min za stranice (normalna navigacija)
            key = "rl:%s:page" % ip

        try:
            import redis

            broker = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
            r = redis.Redis.from_url(broker)
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = pipe.execute()
            if count > limit:
                # API poziv → JSON
                if (
                    request.headers.get("Accept", "") == "application/json"
                    or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.path.startswith("/api/")
                ):
                    from django.http import JsonResponse

                    return JsonResponse(
                        {"error": "Previše zahtjeva. Pričekajte minutu.", "retry_after": window}, status=429
                    )
                # Preglednik → lijepa HTML stranica s odbrojačem
                from django.http import HttpResponse

                html = """<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sigurnosna provjera — LIMIT Connect</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
      display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.box{{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:48px 40px;
      max-width:480px;width:100%;text-align:center}}
.icon{{font-size:3rem;margin-bottom:16px}}
h1{{font-size:1.4rem;font-weight:700;margin-bottom:10px;color:#f1f5f9}}
p{{font-size:.9rem;color:#94a3b8;line-height:1.6;margin-bottom:24px}}
.countdown{{font-size:2.5rem;font-weight:800;color:#c9a84c;margin:24px 0;
            font-variant-numeric:tabular-nums}}
.btn{{display:inline-block;padding:12px 28px;border-radius:10px;
      background:linear-gradient(135deg,#c9a84c,#a08030);color:#0a0a0c;
      font-weight:700;text-decoration:none;margin-top:8px;
      font-size:.9rem;transition:opacity .2s}}
.btn:hover{{opacity:.85}}
.note{{font-size:.75rem;color:#475569;margin-top:20px}}
</style>
</head>
<body>
<div class="box">
  <div class="icon">🔒</div>
  <h1>Sigurnosna provjera</h1>
  <p>Detektirali smo previše pokušaja u kratkom vremenu.<br>
     Ovo je automatska zaštita — nije greška s vaše strane.</p>
  <div class="countdown" id="cd">{seconds}s</div>
  <p style="font-size:.82rem;color:#64748b">Stranica se automatski osvježava kada istekne zaštita.</p>
  <a href="javascript:location.reload()" class="btn" id="retryBtn" style="display:none">
    → Pokušajte ponovo
  </a>
  <div class="note">
    Ako problem potraje, kontaktirajte podršku ili 
    <a href="/hr/login/" style="color:#c9a84c">prijavite se</a> ako već imate račun.
  </div>
</div>
<script>
var sec = {seconds};
var el = document.getElementById('cd');
var btn = document.getElementById('retryBtn');
var t = setInterval(function(){{
  sec--;
  if(sec <= 0){{
    clearInterval(t);
    el.textContent = '✓';
    el.style.color = '#22c55e';
    btn.style.display = 'inline-block';
    setTimeout(function(){{ location.reload(); }}, 800);
  }} else {{
    el.textContent = sec + 's';
  }}
}}, 1000);
</script>
</body>
</html>""".format(seconds=window)
                return HttpResponse(html, status=429, content_type="text/html; charset=utf-8")
        except Exception:
            pass

        return self.get_response(request)


class AdminLangRedirectMiddleware(MiddlewareMixin):
    """
    Redirect /admin/ requests to use the company's preferred language.
    Prevents German users seeing Croatian admin, and vice versa.
    Also handles /rosetta/ and other admin-like paths.
    """

    ADMIN_PREFIXES = ("/admin/", "/rosetta/")

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
        except AttributeError:
            lang = None

        if not lang:
            try:
                from core.company_utils import get_user_company

                company = get_user_company(request)
                if company:
                    lang = company.ui_language
            except ImportError:
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
        "default": "Dogodila se neočekivana greška. Tim je obaviješten i radi na rješenju.",
        "database": "Privremeni problem s bazom podataka. Pokušajte ponovo za minutu.",
        "permission": "Nemate pristup ovom resursu. Kontaktirajte administratora.",
        "timeout": "Zahtjev je trajao predugo. Pokušajte ponovo.",
        "validation": "Podaci nisu ispravni. Provjerite unos i pokušajte ponovo.",
    }

    EXCEPTION_MAP = {
        "OperationalError": "database",
        "InterfaceError": "database",
        "DatabaseError": "database",
        "PermissionDenied": "permission",
        "Forbidden": "permission",
        "TimeoutError": "timeout",
        "ConnectionTimeout": "timeout",
        "ValidationError": "validation",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Hvata SVE unhandled exceptions prije nego Django renderira 500."""
        import traceback as tb_module

        from django.core.exceptions import (
            DisallowedHost,
            PermissionDenied,
            SuspiciousOperation,
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
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return None
        if "application/json" in request.headers.get("Accept", ""):
            return None

        exc_name = type(exception).__name__
        category = self.EXCEPTION_MAP.get(exc_name, "default")
        traceback_str = tb_module.format_exc()

        logger.error(
            "GracefulError [%s] %s %s: %s\n%s",
            category,
            request.method,
            request.path,
            exception,
            traceback_str,
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

        msg = self.ERROR_MESSAGES.get(category, self.ERROR_MESSAGES["default"])
        messages.error(request, msg)

        referrer = request.META.get("HTTP_REFERER", "")
        if referrer and request.build_absolute_uri() != referrer:
            from urllib.parse import urlparse

            parsed = urlparse(referrer)
            if parsed.netloc == "" or parsed.netloc == request.get_host():
                return redirect(referrer)

        return redirect("/")

    def _notify_team(self, request, exception, category, traceback_str):
        try:
            user = request.user.username if request.user.is_authenticated else "anonymous"
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
            logger.error(
                "Error [%s] %s %s by %s from %s: %s",
                category,
                request.method,
                request.path,
                user,
                ip,
                str(exception)[:200],
            )
        except (ValueError, TypeError) as e:
            logger.warning("Failed to dispatch error notification: %s", e)

    def _audit_log(self, request, exception, category):
        try:
            from core.models import SystemAuditLog

            SystemAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                company_id=getattr(request, "company_id", None),
                model_name="_system_error",
                object_id="0",
                action="error",
                changes={
                    "category": category,
                    "exception": type(exception).__name__,
                    "message": str(exception)[:500],
                    "path": request.path,
                    "method": request.method,
                },
                ip_address=request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
                .split(",")[0]
                .strip(),
            )
        except (IntegrityError, DatabaseError):
            pass

    @staticmethod
    def _is_api(request):
        return "/api/" in request.path or request.path.startswith("/_dev/")


class WhiteLabelMiddleware:
    """
    Detektira WhiteLabel konfiguraciju iz HTTP_HOST.
    Sprema u request.white_label (None ako nije WL request).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.core.cache import cache

        from companies.models import WhiteLabelConfig

        host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
        cache_key = f"wl_config:{host}"

        wl = cache.get(cache_key, "__NOT_SET__")
        if wl == "__NOT_SET__":
            wl = WhiteLabelConfig.get_for_request(request)
            cache.set(cache_key, wl, timeout=3600)

        request.white_label = wl
        return self.get_response(request)


class LicenseCheckMiddleware:
    """Blokira pristup za suspendirane distributere. GDPR export uvijek dostupan."""

    BYPASS_PATHS = ("/admin/", "/static/", "/media/", "/pocni/", "/hr/gdpr/", "/hr/export/", "/mcp/", "/api/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        wl = getattr(request, "white_label", None)
        if wl:
            try:
                token = wl.license_token
                path = request.path
                if not any(path.startswith(p) for p in self.BYPASS_PATHS):
                    if not token.is_usable():
                        from django.shortcuts import render

                        return render(
                            request,
                            "license/suspended.html",
                            {
                                "wl": wl,
                                "token": token,
                                "status": token.status,
                            },
                            status=402,
                        )
                    elif token.days_until_expiry() < 7:
                        request.license_warning = True
                        request.license_days = token.days_until_expiry()
            except ImportError:
                pass
        return self.get_response(request)


# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN GATE — Restricts URL access per domain
# ═══════════════════════════════════════════════════════════════════════════════


class DomainGateMiddleware:
    """
    Svaka domena ima pristup samo relevantnim URL-ovima.
    limit-connect.com → sve (master domena)
    memio.farm → livestock, azili, dashboard, accounts, static/media
    memio.pet → memio_pet, boxgram, accounts, static/media
    no-limit.world → no_limit landing, static/media
    viskovic-group.de → stolarija, website, accounts, static/media

    Neovlašteni pristup → redirect na odgovarajući landing page domene.
    Superadmini prolaze uvijek (za debug/admin pristup).
    """

    # Putanje koje su UVIJEK dostupne (auth, static, API, admin)
    ALWAYS_ALLOWED = (
        "/static/",
        "/media/",
        "/favicon",
        "/robots.txt",
        "/api/",
        "/mcp/",
        "/admin/",
        "/j3wkuxuwuuc9/",
        "/hr/accounts/",
        "/de/accounts/",
        "/en/accounts/",
        "/hr/login",
        "/de/login",
        "/en/login",
        "/login",
        "/hr/dashboard/",
        "/de/dashboard/",
        "/en/dashboard/",
        "/logout",
        "/hr/logout",
        "/de/logout",
        "/en/logout",
        "/i18n/",
        "/__debug__/",
        "/hr/pocni/",
        "/de/pocni/",
        "/en/pocni/",
        "/pocni/",
        "/hr/gdpr/",
        "/hr/export/",
        "/privacy/",
        "/terms/",
    )

    # Per-domain URL whitelist (paths that start with these prefixes)
    DOMAIN_RULES = {
        "memio.farm": (
            "/hr/livestock/",
            "/de/livestock/",
            "/en/livestock/",
            "/hr/udruge/",
            "/de/udruge/",
            "/en/udruge/",
            "/hr/experiences/",
            "/hr/marketplace/",
            "/hr/invoicing/",
            "/de/invoicing/",
            "/en/invoicing/",
            "/hr/partners/",
            "/hr/inventory/",
            "/hr/companies/",
            "/de/companies/",
            "/hr/worktime/",
            "/hr/documents/",
            "/hr/pos/",
            "/de/pos/",
            "/site/",
            "/ponuda/",
        ),
        "www.memio.farm": "memio.farm",  # alias
        "memio.pet": (
            "/hr/memio/",
            "/de/memio/",
            "/en/memio/",
            "/hr/boxgram/",
            "/de/boxgram/",
            "/pet/",
            "/hr/pet/",
            "/ponuda/",
        ),
        "www.memio.pet": "memio.pet",
        "memio.world": (
            "/hr/memio/",
            "/de/memio/",
            "/en/memio/",
            "/hr/boxgram/",
            "/de/boxgram/",
            "/ponuda/",
        ),
        "www.memio.world": "memio.world",
        "no-limit.world": (
            "/no-limit/",
            "/hr/no-limit/",
            "/ponuda/",
        ),
        "www.no-limit.world": "no-limit.world",
        "viskovic-group.de": (
            "/hr/stolarija/",
            "/de/stolarija/",
            "/hr/invoicing/",
            "/de/invoicing/",
            "/hr/companies/",
            "/de/companies/",
            "/hr/partners/",
            "/de/partners/",
            "/hr/worktime/",
            "/de/worktime/",
            "/hr/documents/",
            "/de/documents/",
            "/hr/pos/",
            "/de/pos/",
            "/hr/inventory/",
            "/de/inventory/",
            "/site/",
            "/ponuda/",
        ),
        "www.viskovic-group.de": "viskovic-group.de",
        "fina-connect.online": (
            "/hr/invoicing/",
            "/de/invoicing/",
            "/hr/companies/",
            "/de/companies/",
            "/hr/partners/",
            "/de/partners/",
            "/site/",
            "/ponuda/",
        ),
        "www.fina-connect.online": "fina-connect.online",
    }

    # Landing pages per domain (where to redirect if blocked)
    DOMAIN_LANDING = {
        "memio.farm": "/hr/livestock/",
        "memio.pet": "/hr/memio/",
        "memio.world": "/hr/memio/",
        "no-limit.world": "/no-limit/",
        "viskovic-group.de": "/de/dashboard/",
        "fina-connect.online": "/hr/dashboard/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
        path = request.path

        # Master domain — no restrictions
        if "limit-connect.com" in host or host in ("localhost", "127.0.0.1", "37.27.248.86"):
            request.domain_name = "limit-connect.com"
            request.domain_restricted = False
            return self.get_response(request)

        # Always-allowed paths
        if any(path.startswith(p) for p in self.ALWAYS_ALLOWED):
            request.domain_name = host
            request.domain_restricted = True
            return self.get_response(request)

        # Root path → domain landing
        if path in ("/", "/hr/", "/de/", "/en/"):
            landing = self._get_landing(host)
            if landing:
                from django.shortcuts import redirect

                return redirect(landing)

        # Superadmin bypass
        if hasattr(request, "user") and request.user.is_authenticated:
            if request.user.is_superuser:
                request.domain_name = host
                request.domain_restricted = False
                return self.get_response(request)

        # Check domain rules
        rules = self._get_rules(host)
        if rules is None:
            # Unknown domain but in ALLOWED_HOSTS → allow (no restriction)
            request.domain_name = host
            request.domain_restricted = False
            return self.get_response(request)

        # Check if path is allowed for this domain
        if any(path.startswith(prefix) for prefix in rules):
            request.domain_name = host
            request.domain_restricted = True
            return self.get_response(request)

        # BLOCKED — redirect to domain landing
        landing = self._get_landing(host)
        if landing and path != landing:
            logger.warning(
                "DomainGate blocked: host=%s path=%s user=%s → redirect %s",
                host,
                path,
                getattr(request, "user", "anon"),
                landing,
            )
            from django.shortcuts import redirect

            return redirect(landing)

        # Fallback — let it through with a warning (don't break things)
        request.domain_name = host
        request.domain_restricted = True
        return self.get_response(request)

    def _get_rules(self, host):
        """Resolve rules, following aliases."""
        rules = self.DOMAIN_RULES.get(host)
        if isinstance(rules, str):
            rules = self.DOMAIN_RULES.get(rules)
        return rules

    def _get_landing(self, host):
        """Get landing page for domain."""
        # Strip www.
        bare = host.replace("www.", "")
        return self.DOMAIN_LANDING.get(bare, self.DOMAIN_LANDING.get(host, "/"))
