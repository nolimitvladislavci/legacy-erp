"""
memio_world/views_kum.py — Kum sustav views
"""

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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

    # B-13: child selector — puna lista djece roditelja za JS
    from memio_world.models import ChildProfile

    my_children = ChildProfile.objects.using("memio_world").filter(guardian_emails_encrypted__icontains=parent.email)

    return render(
        request,
        "memio_world/kum_dashboard.html",
        {
            "nav": "family",
            "as_kum": as_kum,
            "kums_for_my_children": kums_for_my_children,
            "pending_gifts": pending_gifts,
            "sent_invitations": sent_invitations,
            "my_children": my_children,  # B-13: za JS child selector
            "my_children_json": [{"id": str(c.id), "name": c.name, "age": c.age or ""} for c in my_children],
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


# ════════════════════════════════════════════════════════════
# B-11 — KumGift Stripe Checkout
# ════════════════════════════════════════════════════════════


@login_required_play
def kum_gift_checkout(request, gift_id):
    """
    Kum inicira Stripe Checkout za KumGift koji je roditelj odobrio.
    GET  → redirect na Stripe Checkout URL
    POST → isto (za kompatibilnost)
    """
    parent = request.play_parent  # ovdje parent == kum (logged-in korisnik)
    gift = get_object_or_404(KumGift.objects.using("memio_world"), pk=gift_id)

    # Samo kum koji je poslao poklon može platiti
    if gift.relationship.kum_id != parent.id:
        return JsonResponse({"error": "Nemate dozvolu."}, status=403)

    # Mora biti odobreno od roditelja
    if gift.status != "pending_payment":
        return JsonResponse(
            {"error": f"Poklon nije u stanju 'pending_payment'. Status: {gift.status}"},
            status=400,
        )

    try:
        import stripe
        from django.conf import settings as dj_settings

        stripe.api_key = getattr(dj_settings, "STRIPE_SECRET_KEY", "")
        if not stripe.api_key:
            raise RuntimeError("STRIPE_SECRET_KEY nije konfiguriran u settings.")

        base = request.build_absolute_uri("/")
        success_url = f"{base}api/memio-world/play/kum/poklon/{gift_id}/success/?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}api/memio-world/play/kum/"

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": int(gift.amount_eur * 100),
                        "product_data": {
                            "name": f"Memio poklon pretplate — {gift.get_plan_display()}",
                            "description": (
                                f"Poklon za {gift.relationship.child.name} od {gift.relationship.kum.name or 'Kum'}"
                            ),
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=parent.email or None,
            metadata={
                "gift_id": str(gift.id),
                "kum_id": str(parent.id),
                "child_id": str(gift.relationship.child_id),
                "plan": gift.plan,
            },
        )

        # Spremi Stripe session ID
        gift.stripe_payment_intent = session.id
        gift.save(update_fields=["stripe_payment_intent"])

        return redirect(session.url)

    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required_play
def kum_gift_success(request, gift_id):
    """Stripe redirect nakon uspješnog plaćanja. Aktivira poklon."""
    parent = request.play_parent
    gift = get_object_or_404(KumGift.objects.using("memio_world"), pk=gift_id)

    if gift.relationship.kum_id != parent.id:
        return JsonResponse({"error": "Nemate dozvolu."}, status=403)

    session_id = request.GET.get("session_id", "")

    # Verifikacija s Stripeom
    try:
        import stripe
        from django.conf import settings as dj_settings

        stripe.api_key = getattr(dj_settings, "STRIPE_SECRET_KEY", "")
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == "paid":
            if gift.status != "active":
                gift.activate()
    except Exception:
        pass  # Aktivan čak i bez Stripe verifikacije ako session_id odgovara

    return render(
        request,
        "memio_world/kum_gift_success.html",
        {
            "gift": gift,
            "child": gift.relationship.child,
        },
    )


@require_POST
def kum_gift_stripe_webhook(request):
    """
    Stripe webhook za pouzdanu aktivaciju poklona.
    Registriraj na: https://dashboard.stripe.com/webhooks
    URL: /api/memio-world/play/kum/webhook/stripe/
    Event: checkout.session.completed
    """
    import json

    import stripe
    from django.conf import settings as dj_settings

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    wh_secret = getattr(dj_settings, "STRIPE_WEBHOOK_SECRET_KUM", "")

    try:
        if wh_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, wh_secret)
        else:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        gift_id = session.get("metadata", {}).get("gift_id")
        if gift_id:
            try:
                gift = KumGift.objects.using("memio_world").get(pk=gift_id)
                if gift.status != "active":
                    gift.activate()
            except KumGift.DoesNotExist:
                pass

    return HttpResponse(status=200)
