"""VAPID push subscription management views."""

import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST


def vapid_public_key(request):
    """Vrati VAPID public key za browser."""
    return JsonResponse({"public_key": settings.VAPID_PUBLIC_KEY})


@login_required
@require_POST
def subscribe(request):
    """Browser šalje subscription object nakon pushManager.subscribe()."""
    try:
        data = json.loads(request.body)
        sub_json = json.dumps(data)  # Normalize
        request.user.profile.push_subscription = sub_json
        request.user.profile.save(update_fields=["push_subscription"])
        return JsonResponse({"ok": True})
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
@require_POST
def unsubscribe(request):
    """Obrisi pretplatu (kad user odabere opt-out)."""
    request.user.profile.push_subscription = ""
    request.user.profile.save(update_fields=["push_subscription"])
    return JsonResponse({"ok": True})
