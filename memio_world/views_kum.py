"""
memio_world/views_kum.py — Kum sustav views
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from memio_world.kum_models import KumGift, KumInvitation, KumRelationship
from memio_world.views_auth import login_required_play

logger = logging.getLogger("memio_world.kum")


@login_required_play
def kum_dashboard(request):
    """Prikaz svih Kum veza — kao Kum i kao Roditelj."""
    parent = request.play_parent

    # Veze gdje sam JA Kum
    as_kum = (
        KumRelationship.objects.using("memio_world")
        .filter(kum=parent, status="active")
        .select_related("child", "child__parent")
    )

    # Veze gdje netko drugi kumuje MOJOJ djeci
    from memio_world.models import ChildProfile

    my_children_ids = (
        ChildProfile.objects.using("memio_world")
        .filter(guardian_emails_encrypted__icontains=parent.email)
        .values_list("id", flat=True)
    )

    kums_for_my_children = (
        KumRelationship.objects.using("memio_world")
        .filter(child__in=my_children_ids, status="active")
        .select_related("kum", "child")
    )

    # Moji pokloni na čekanju
    pending_gifts = (
        KumGift.objects.using("memio_world")
        .filter(
            relationship__child__in=my_children_ids,
            status="pending_parent",
        )
        .select_related("relationship__kum", "relationship__child")
    )

    # Pozivnice koje sam poslao/la
    sent_invitations = KumInvitation.objects.using("memio_world").filter(parent=parent).order_by("-created_at")[:10]

    return render(
        request,
        "memio_world/kum_dashboard.html",
        {
            "nav": "family",
            "as_kum": as_kum,
            "kums_for_my_children": kums_for_my_children,
            "pending_gifts": pending_gifts,
            "sent_invitations": sent_invitations,
        },
    )


@login_required_play
@require_POST
def kum_invite_send(request):
    """Roditelj šalje pozivnicu Kumu."""
    parent = request.play_parent
    data = json.loads(request.body) if request.content_type == "application/json" else request.POST

    child_id = data.get("child_id")
    kum_email = (data.get("kum_email") or "").strip().lower()
    kum_name = (data.get("kum_name") or "").strip()
    note = (data.get("personal_note") or "")[:500]
    can_pay = data.get("can_pay_subscription", True) in (True, "true", "1", "on")
    can_see = data.get("can_see_progress", True) in (True, "true", "1", "on")

    if not kum_email or "@" not in kum_email:
        return JsonResponse({"error": "Email obavezan"}, status=400)

    from memio_world.models import ChildProfile

    try:
        child = ChildProfile.objects.using("memio_world").get(pk=child_id)
    except ChildProfile.DoesNotExist:
        return JsonResponse({"error": "Dijete nije pronađeno"}, status=404)

    # Ne smije biti već aktivan Kum
    if KumRelationship.objects.using("memio_world").filter(kum__email=kum_email, child=child, status="active").exists():
        return JsonResponse({"error": "Ta osoba je već Kum ovom djetetu."}, status=400)

    inv = KumInvitation.objects.using("memio_world").create(
        parent=parent,
        child=child,
        kum_email=kum_email,
        kum_name=kum_name,
        personal_note=note,
        can_pay_subscription=can_pay,
        can_see_progress=can_see,
    )

    # TODO: Slanje email pozivnice (Celery task)
    logger.info("Kum pozivnica poslana: %s → %s (dijete: %s)", parent.email, kum_email, child.name)

    return JsonResponse({"ok": True, "token": inv.token, "message": f"Pozivnica poslana na {kum_email}"})


def kum_invite_accept(request, token):
    """Kum prihvati pozivnicu — javna stranica, bez logina, ali treba account."""
    inv = get_object_or_404(KumInvitation.objects.using("memio_world"), token=token)

    if not inv.is_valid:
        return render(request, "memio_world/kum_invite_invalid.html", {"nav": "family", "reason": inv.status})

    # Ako je Kum već logiran
    parent = getattr(request, "play_parent", None)

    if request.method == "POST" and parent:
        rel = inv.accept(parent)
        return render(
            request,
            "memio_world/kum_invite_accepted.html",
            {
                "nav": "family",
                "child": inv.child,
                "relationship": rel,
            },
        )

    return render(
        request,
        "memio_world/kum_invite_landing.html",
        {
            "nav": "family",
            "invitation": inv,
            "already_logged_in": parent is not None,
        },
    )


@login_required_play
@require_POST
def kum_gift_create(request):
    """Kum šalje poklon pretplate kumčetu."""
    parent = request.play_parent
    data = json.loads(request.body) if request.content_type == "application/json" else request.POST

    rel_id = data.get("relationship_id")
    plan = data.get("plan", "monthly")
    message = (data.get("gift_message") or "")[:500]

    try:
        rel = KumRelationship.objects.using("memio_world").get(pk=rel_id, kum=parent, status="active")
    except KumRelationship.DoesNotExist:
        return JsonResponse({"error": "Kum veza nije pronađena"}, status=404)

    if not rel.can_pay_subscription:
        return JsonResponse({"error": "Nemate dozvolu za plaćanje pretplate"}, status=403)

    if plan not in KumGift.PLAN_PRICES:
        return JsonResponse({"error": "Nepoznati plan"}, status=400)

    gift = KumGift.objects.using("memio_world").create(
        relationship=rel,
        plan=plan,
        amount_eur=KumGift.PLAN_PRICES[plan],
        gift_message=message,
    )

    logger.info("KumGift kreiran: %s → %s (%s)", parent.email, rel.child.name, plan)
    return JsonResponse(
        {
            "ok": True,
            "gift_id": str(gift.id),
            "message": f"Roditelj mora odobriti poklon. Čeka potvrdu...",
        }
    )


@login_required_play
@require_POST
def kum_gift_approve(request, gift_id):
    """Roditelj odobri ili odbije KumGift."""
    parent = request.play_parent
    data = json.loads(request.body) if request.content_type == "application/json" else request.POST

    gift = get_object_or_404(KumGift.objects.using("memio_world"), pk=gift_id)
    action = data.get("action")  # "approve" ili "decline"

    if action == "approve":
        gift.approve(parent)
        return JsonResponse({"ok": True, "message": "Poklon odobren! Kum može platiti."})
    elif action == "decline":
        reason = (data.get("reason") or "")[:300]
        gift.decline(parent, reason)
        return JsonResponse({"ok": True, "message": "Poklon odbijen."})
    else:
        return JsonResponse({"error": "Nepoznata akcija"}, status=400)
