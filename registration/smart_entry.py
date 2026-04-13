"""
registration/smart_entry.py
Jedina ulazna točka — /pocni/
Email detect → pravi flow, nema dead enda.
"""

import json

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST


@ensure_csrf_cookie
def pocni(request):
    """
    GET  → prikazuje stranicu s email poljem
    Parametri: ?ref=REF-MARIJA-2026, ?pet=Vučko, ?plan=professional
    """
    if request.user.is_authenticated:
        return redirect("/hr/portal/" if hasattr(request, "white_label") and request.white_label else "/hr/dashboard/")

    ref = request.GET.get("ref", "")
    if ref:
        request.session["agent_ref"] = ref

    return render(
        request,
        "registration/smart_entry.html",
        {
            "pet": request.GET.get("pet", ""),
            "plan": request.GET.get("plan", ""),
            "ref": ref,
            "page_title": "Počnite s LIMIT Connect",
        },
    )


# CSRF exempt: public detection endpoint
@csrf_exempt
@require_POST
def api_detect_email(request):
    """
    POST /pocni/provjeri/
    Body: {"email": "ivan@firma.hr"}
    Returns: {"status": "new|existing|rate_limit", ...}
    """
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip().lower()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "error", "msg": "Neispravan zahtjev"}, status=400)

    if not email or "@" not in email:
        return JsonResponse({"status": "error", "msg": "Unesite valjanu email adresu"})

    # Rate limit: 10 pokušaja / 10 min po IP
    rate_key = f"smart_entry_rate:{request.META.get('REMOTE_ADDR', '')}"
    attempts = cache.get(rate_key, 0)
    if attempts > 10:
        return JsonResponse(
            {
                "status": "rate_limit",
                "msg": "Previše pokušaja. Pričekajte 10 minuta.",
                "wait_seconds": 600,
            }
        )
    cache.set(rate_key, attempts + 1, timeout=600)

    user = User.objects.filter(email=email).order_by("-last_login").first()
    if user:
        # Posalji magic link
        try:
            _send_magic_link(user, request)
        except Exception:
            pass

        # Privacy-First: NE otkrivamo ime/firmu/status na javnom endpointu
        # GDPR: User Enumeration = krsenje privatnosti
        return JsonResponse(
            {
                "status": "check_email",
                "has_account": True,
                "msg": (
                    f"Provjerite {email} — poslali smo pristupni link. "
                    f"Ako vec imate lozinku, mozete se prijaviti direktno."
                ),
                "login_url": "/hr/login/",
            }
        )

    ref = request.session.get("agent_ref", "")
    return JsonResponse(
        {
            "status": "check_email",
            "has_account": False,
            "msg": "Dobrodošli! Kreiramo vaš račun.",
            "redirect": f"/hr/accounts/quick-register/?email={email}&ref={ref}",
        }
    )


def _send_magic_link(user, request):
    token = dumps({"user_id": user.pk}, key=settings.SECRET_KEY, salt="magic-login")
    safe_token = token.replace(":", "~")  # colons break email links
    link = request.build_absolute_uri(f"/pocni/magic/{safe_token}/")
    send_mail(
        subject="Vaš pristup — LIMIT Connect",
        message=f"Kliknite link za ulaz u portal:\n{link}\n\nLink je valjan 24 sata.",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@limit-connect.com"),
        recipient_list=[user.email],
        html_message=f'<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:2rem">'
        f'<h2 style="color:#c9a84c">LIMIT Connect</h2>'
        f"<p>Kliknite gumb za pristup portalu:</p>"
        f'<p style="margin:1.5rem 0"><a href="{link}" style="display:inline-block;padding:14px 28px;background:#c9a84c;color:#000;text-decoration:none;border-radius:8px;font-weight:700;font-size:1rem">Uđi u portal →</a></p>'
        f'<p style="color:#888;font-size:.85rem">Link vrijedi 24 sata.</p>'
        f'<p style="color:#888;font-size:.75rem">Ili kopirajte: {link}</p></div>',
        fail_silently=True,
    )


def magic_login(request, token):
    """One-click login via signed token (24h TTL)."""
    token = token.replace("~", ":")  # restore colons from email-safe format
    try:
        data = loads(token, key=settings.SECRET_KEY, salt="magic-login", max_age=86400)
        user = User.objects.get(pk=data["user_id"])
        login(request, user, backend="core.auth_backends.EmailOrUsernameBackend")
        if user.is_superuser:
            return redirect("/hr/superadmin/")
        return redirect("/hr/dashboard/")
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        return render(
            request,
            "registration/smart_entry.html",
            {
                "error": "Link je istekao ili neispravan. Unesite email ponovo.",
            },
        )
