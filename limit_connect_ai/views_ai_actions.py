"""
limit_connect_ai/views_ai_actions.py — AI akcije review views
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models_ai_action import AIAction


@login_required
@require_POST
def review_action(request, action_id):
    """
    Korisnik označuje AI akciju kao pregledanu.
    Vraća ažurirani HTML fragment za HTMX swap.
    """
    action = get_object_or_404(
        AIAction,
        id=action_id,
        company=request.user.core_userprofile.company,
    )
    action.is_reviewed = True
    action.reviewed_by = request.user
    action.reviewed_at = timezone.now()
    note = request.POST.get("note", "")
    if note:
        action.review_note = note
    action.save(update_fields=["is_reviewed", "reviewed_by", "reviewed_at", "review_note"])

    # HTMX fragment — vrati samo ovaj redak označen kao pregledano
    return render(
        request,
        "ai_assistant/partials/ai_action_row_reviewed.html",
        {
            "action": action,
            "request": request,
        },
    )


@login_required
def ai_actions_list(request):
    """
    Lista svih AI akcija za kompaniju — za admin/cockpit.
    """
    company = request.user.core_userprofile.company
    actions = AIAction.objects.filter(company=company).order_by("-created_at")[:100]
    unreviewed = AIAction.objects.filter(company=company, is_reviewed=False).count()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "ai_assistant/partials/ai_activity_widget.html",
            {
                "actions": actions[:10],
                "unreviewed": unreviewed,
                "request": request,
            },
        )

    return render(
        request,
        "limit_connect_ai/ai_actions_list.html",
        {
            "actions": actions,
            "unreviewed": unreviewed,
        },
    )
