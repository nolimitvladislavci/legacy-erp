"""
Identity Views — /pristup/ router
===================================
Čekaonica za Ghost korisnike.
Jedina stranica kojoj Ghost ima pristup (osim logout/static).
"""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .engine import calculate_trust_score, process_join_request, suggest_companies_for_user
from .models import CompanyDomainWhitelist, IdentityInviteToken, IdentityJoinRequest

logger = logging.getLogger("identity.views")


@login_required
def pristup_router(request):
    """
    Glavna /pristup/ stranica za Ghost korisnike.
    Prikazuje opcije + AI sugestije firmi.
    """
    user = request.user
    suggestions = suggest_companies_for_user(user)
    pending = IdentityJoinRequest.objects.filter(user=user, status="pending").select_related("company")

    return render(request, "identity/pristup.html", {
        "suggestions": suggestions,
        "pending_requests": pending,
        "page_title": "Pristup platformi",
        "user": user,
    })


@login_required
@require_POST
def request_join(request):
    """
    Korisnik zahtijeva pristup firmi (upiše OIB ili company_id).
    """
    from companies.models import Company

    oib = request.POST.get("oib", "").strip()
    company_id = request.POST.get("company_id", "").strip()
    user_note = request.POST.get("note", "").strip()[:500]
    requested_role = request.POST.get("role", "worker")
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or \
         request.META.get("REMOTE_ADDR")

    company = None
    if company_id:
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Firma ne postoji"}, status=404)
    elif oib:
        # Traži po OIB-u
        company = Company.objects.filter(oib=oib).first()
        if not company:
            return JsonResponse({"ok": False, "error": "Nije pronađena firma s tim OIB-om"}, status=404)

    if not company:
        return JsonResponse({"ok": False, "error": "Navedite OIB firme ili pozivni kod"}, status=400)

    # Provjeri nije li već u toj firmi
    try:
        if request.user.profile.company_id == company.pk:
            return JsonResponse({"ok": False, "error": "Već ste član ove firme"}, status=400)
    except Exception:
        pass

    # Provjeri nema li već pending zahtjev
    existing = IdentityJoinRequest.objects.filter(
        user=request.user, company=company, status="pending"
    ).first()
    if existing:
        return JsonResponse({
            "ok": True, "status": "already_pending",
            "message": "Zahtjev je već poslan, čekate odobrenje"
        })

    # Kreiraj zahtjev
    jr = IdentityJoinRequest.objects.create(
        user=request.user,
        company=company,
        requested_role=requested_role,
        user_note=user_note,
        oib_provided=oib,
        ip_address=ip,
    )

    # Async: izračunaj trust score i obradi
    result = process_join_request(jr, ip=ip)

    messages = {
        "auto_approved": f"✅ Pristup odobren! Dobrodošli u {company.name}",
        "pending": f"📨 Zahtjev poslan. Administrator {company.name} će vas odobriti.",
        "blocked": "⛔ Zahtjev nije moguće obraditi. Kontaktirajte podršku.",
    }

    if result == "auto_approved":
        return JsonResponse({"ok": True, "status": result,
                            "message": messages[result], "redirect": "/hr/pos/"})
    return JsonResponse({"ok": True, "status": result, "message": messages.get(result, "")})


@login_required
def use_invite(request, token):
    """
    Korisnik klikne /pristup/pozivnica/{token}/ → automatski se veže za firmu.
    """
    invite = get_object_or_404(IdentityInviteToken, token=token)
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or \
         request.META.get("REMOTE_ADDR")

    if not invite.is_valid():
        return render(request, "identity/invite_invalid.html", {
            "reason": "Pozivnica je iskorištena ili je istekla"
        })

    # Email hint provjera (opcionalno)
    if invite.email_hint and invite.email_hint.lower() != request.user.email.lower():
        return render(request, "identity/invite_invalid.html", {
            "reason": "Ova pozivnica nije namijenjena vašem email računu"
        })

    # Aktivacija
    invite.consume(request.user, ip=ip)

    # Poveži korisnika s firmom
    from accounts.models import UserProfile
    from .models import IdentityAuditLog
    from django.db import transaction

    with transaction.atomic():
        p = UserProfile.objects.select_for_update().get(user=request.user)
        p.company = invite.company
        p.role = invite.scope
        p.save(update_fields=["company", "role"])

    IdentityAuditLog.log(
        "invite_used",
        user=request.user, company=invite.company, ip=ip,
        detail={"token_id": str(invite.id), "scope": invite.scope}
    )

    from django.contrib import messages as django_messages
    django_messages.success(
        request,
        f"✅ Dobrodošli u {invite.company.name}! Pristup aktiviran."
    )
    return redirect("/hr/pos/")


@login_required
def admin_pending_requests(request):
    """
    Admin pregled zahtjeva za pridruživanje.
    """
    company = getattr(request, "company", None)
    if not company:
        return redirect("/pristup/")

    pending = IdentityJoinRequest.objects.filter(
        company=company, status="pending"
    ).select_related("user", "user__profile").order_by("-created_at")

    return render(request, "identity/admin_requests.html", {
        "pending": pending,
        "page_title": "Zahtjevi za pristup",
    })


@login_required
@require_POST
def resolve_request(request, request_id):
    """Admin odobrava ili odbija zahtjev."""
    company = getattr(request, "company", None)
    jr = get_object_or_404(IdentityJoinRequest, id=request_id, company=company)

    action = request.POST.get("action")
    note   = request.POST.get("note", "")[:500]

    from .models import IdentityAuditLog

    if action == "approve":
        jr.approve(by_user=request.user, note=note)
        IdentityAuditLog.log("join_approved", user=jr.user, company=company,
                              detail={"approved_by": request.user.username})
        return JsonResponse({"ok": True, "message": f"{jr.user.username} odobren"})
    elif action == "reject":
        jr.status = "rejected"
        jr.admin_note = note
        from django.utils import timezone
        jr.resolved_at = timezone.now()
        jr.resolved_by = request.user
        jr.save(update_fields=["status", "admin_note", "resolved_at", "resolved_by"])
        IdentityAuditLog.log("join_rejected", user=jr.user, company=company,
                              detail={"rejected_by": request.user.username, "note": note})
        return JsonResponse({"ok": True, "message": f"{jr.user.username} odbijen"})

    return JsonResponse({"ok": False, "error": "Nepoznata akcija"}, status=400)
