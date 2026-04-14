from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)[:100]
    return render(
        request,
        "notifications/list.html",
        {
            "title": "Obavijesti",
            "notifications": notifications,
        },
    )


def notification_api(request):
    """GET -> {unread_count, recent: [...]} — optimizirano za polling svakih 60s."""
    from django.http import JsonResponse

    if not request.user.is_authenticated:
        return JsonResponse({"unread_count": 0, "recent": []}, status=401)

    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    display_count = min(unread, 99)

    recent_qs = (
        Notification.objects.filter(recipient=request.user)
        .order_by("-created_at")[:5]
        .values("id", "title", "message", "url", "is_read", "notification_type", "created_at")
    )
    # created_at je datetime — eksplicitno na ISO string da JsonResponse ne puca
    recent = [{**n, "created_at": n["created_at"].isoformat() if n["created_at"] else None} for n in recent_qs]
    return JsonResponse({"unread_count": display_count, "recent": recent})


@login_required
@require_POST
def notification_mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})
