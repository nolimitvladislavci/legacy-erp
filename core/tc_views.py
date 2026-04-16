import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def tc_accept_view(request):
    if request.method == "POST" and request.POST.get("tc_accept"):
        company = None
        try:
            company = request.user.profile.company
        except AttributeError:
            logger.exception("Profile access failed")
        if company:
            company.has_signed_tc_consent = True
            company.tc_consent_signed_at = timezone.now()
            company.tc_consent_version = "v1.0-2026"
            company.save(update_fields=["has_signed_tc_consent", "tc_consent_signed_at", "tc_consent_version"])
        return redirect(request.GET.get("next", "/"))
    return render(request, "legal/tc_accept.html")
