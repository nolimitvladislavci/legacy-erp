"""
PLAY.EU Auth — Registracija, Login, Child Profile Setup
=========================================================
Cookie-based auth na memio_world bazi (odvojeno od Django auth).
"""

import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

DB = "memio_world"


def _get_parent(request):
    """Get parent from session cookie."""
    token = request.COOKIES.get("playeu_session")
    if not token:
        return None
    try:
        from memio_world.parent_models import SessionToken

        session = (
            SessionToken.objects.using(DB)
            .select_related("parent")
            .get(token=token, is_active=True, expires_at__gt=timezone.now())
        )
        return session.parent
    except Exception:
        return None


def _lang(request):
    return request.GET.get("lang", "hr")


def register_page(request):
    """Registracija roditelja."""
    lang = _lang(request)
    parent = _get_parent(request)
    if parent:
        return redirect("memio_world:account_page")
    return render(request, "memio_world/auth_register.html", {"nav": "home", "lang": lang})


@csrf_exempt
@require_POST
def register_action(request):
    """API: kreiraj ParentAccount."""
    from memio_world.parent_models import ParentAccount, SessionToken

    data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    lang = data.get("lang") or "hr"
    ref_code = (data.get("ref_code") or "").strip().upper()

    if not email or "@" not in email:
        return JsonResponse({"ok": False, "error": "Email je obavezan."}, status=400)
    if len(password) < 6:
        return JsonResponse({"ok": False, "error": "Lozinka mora imati barem 6 znakova."}, status=400)

    if ParentAccount.objects.using(DB).filter(email=email).exists():
        return JsonResponse({"ok": False, "error": "Email je već registriran."}, status=400)

    parent = ParentAccount(email=email, name=name, preferred_language=lang)
    parent.set_password(password)
    parent.plan = "trial"
    parent.plan_started = timezone.now()

    # Referral
    if ref_code:
        referrer = ParentAccount.objects.using(DB).filter(referral_code=ref_code).first()
        if referrer:
            parent.referred_by = ref_code
            referrer.referral_count += 1
            referrer.save(using=DB)

    parent.save(using=DB)

    # Create session
    session = SessionToken.create_for(parent)
    response = JsonResponse({"ok": True, "redirect": "/api/memio-world/play/setup/"})
    response.set_cookie("playeu_session", session.token, max_age=30 * 86400, httponly=True, samesite="Lax", secure=True)
    return response


def login_page(request):
    """Login stranica."""
    lang = _lang(request)
    parent = _get_parent(request)
    if parent:
        return redirect("memio_world:account_page")
    return render(request, "memio_world/auth_login.html", {"nav": "home", "lang": lang})


@csrf_exempt
@require_POST
def login_action(request):
    """API: login."""
    from memio_world.parent_models import ParentAccount, SessionToken

    data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    try:
        parent = ParentAccount.objects.using(DB).get(email=email)
    except ParentAccount.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Neispravan email ili lozinka."}, status=400)

    if not parent.check_password(password):
        return JsonResponse({"ok": False, "error": "Neispravan email ili lozinka."}, status=400)

    parent.last_login = timezone.now()
    parent.save(using=DB)

    session = SessionToken.create_for(parent)
    response = JsonResponse({"ok": True, "redirect": "/api/memio-world/play/account/"})
    response.set_cookie("playeu_session", session.token, max_age=30 * 86400, httponly=True, samesite="Lax", secure=True)
    return response


def logout_action(request):
    """Logout — brisanje session cookija."""
    token = request.COOKIES.get("playeu_session")
    if token:
        from memio_world.parent_models import SessionToken

        SessionToken.objects.using(DB).filter(token=token).update(is_active=False)
    response = redirect("memio_world:play_home")
    response.delete_cookie("playeu_session")
    return response


def setup_page(request):
    """Child profile setup — prvi korak nakon registracije."""
    lang = _lang(request)
    parent = _get_parent(request)
    if not parent:
        return redirect("memio_world:login_page")
    return render(request, "memio_world/auth_setup.html", {"nav": "home", "lang": lang, "parent": parent})


@csrf_exempt
@require_POST
def setup_child_action(request):
    """API: kreiraj ChildProfile + ChildProgress."""
    from memio_world.models import ChildProfile
    from memio_world.parent_models import ChildProgress

    parent = _get_parent(request)
    if not parent:
        return JsonResponse({"ok": False, "error": "Niste prijavljeni."}, status=401)

    data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    name = (data.get("name") or "").strip()
    birth_date = data.get("birth_date") or ""
    if not name:
        return JsonResponse({"ok": False, "error": "Ime djeteta je obavezno."}, status=400)

    try:
        dob = date.fromisoformat(birth_date)
    except (ValueError, TypeError):
        dob = date(2018, 1, 1)  # default

    child = ChildProfile.objects.using(DB).create(
        name=name,
        date_of_birth=dob,
        guardian_emails_encrypted=parent.email,
        visibility="private",
    )

    ChildProgress.objects.using(DB).create(
        child=child,
        parent=parent,
    )

    return JsonResponse({"ok": True, "child_id": str(child.id), "redirect": "/api/memio-world/play/school/"})


def account_page(request):
    """Pregled računa — djeca, pretplata, postavke."""
    lang = _lang(request)
    parent = _get_parent(request)
    if not parent:
        return redirect("memio_world:login_page")

    from memio_world.parent_models import ChildProgress

    children = ChildProgress.objects.using(DB).filter(parent=parent).select_related("child")

    return render(
        request,
        "memio_world/auth_account.html",
        {"nav": "home", "lang": lang, "parent": parent, "children": children},
    )


def login_required_play(view_func):
    """Decorator: zahtjeva prijavljenog roditelja (memio_world session)."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        parent = _get_parent(request)
        if not parent:
            from django.shortcuts import redirect

            return redirect("memio_world:login_page")
        request.play_parent = parent
        return view_func(request, *args, **kwargs)

    return wrapper
