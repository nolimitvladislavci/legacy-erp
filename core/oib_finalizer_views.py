"""
OIB Finalizer Views — Marija jednim klikom "ozakonjuje" DRAFT firmu.

Routes:
  /umbrella/drafts/           → lista DRAFT tvrtki
  /umbrella/drafts/finalize/  → POST: finalizacija OIB-a
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.services_oib_finalizer import (
    OIBFinalizerError,
    finalize_oib,
    get_draft_companies,
)

logger = logging.getLogger(__name__)


@login_required
def draft_companies_view(request):
    """Lista DRAFT tvrtki čekaju pravi OIB."""
    from core.company_utils import get_user_company

    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if not company.is_umbrella and not request.user.is_superuser:
        messages.warning(request, _('Samo umbrella korisnici mogu pristupiti ovoj stranici.'))
        return redirect('dashboard')

    drafts = get_draft_companies()

    return render(request, 'dashboards/draft_companies.html', {
        'company': company,
        'drafts': drafts,
        'draft_count': len(drafts),
    })


@login_required
@require_POST
def finalize_oib_view(request):
    """POST endpoint: finalizacija OIB-a za DRAFT tvrtku."""
    company_id = request.POST.get('company_id')
    new_oib = request.POST.get('new_oib', '').strip()

    if not company_id or not new_oib:
        messages.error(request, _('Nedostaje ID tvrtke ili OIB.'))
        return redirect('draft_companies')

    try:
        result = finalize_oib(company_id, new_oib, user=request.user)

        if result['success']:
            action_summary = ' | '.join(result['actions'])
            messages.success(
                request,
                f'OIB finaliziran: {result["company_name"]} → {new_oib}. '
                f'Akcije: {action_summary}'
            )
        else:
            messages.warning(request, _('Finalizacija završena s upozorenjima.'))

    except OIBFinalizerError:
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    except Exception as exc:
        logger.exception('OIB Finalizer unexpected error')
        messages.error(request, f'Neočekivana greška: {exc}')

    return redirect('draft_companies')


@login_required
def finalize_oib_api(request):
    """AJAX endpoint za real-time preview prije finalizacije."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST

    company_id = data.get('company_id')
    new_oib = data.get('new_oib', '').strip()

    if not company_id or not new_oib:
        return JsonResponse({'error': 'Nedostaje company_id ili new_oib'}, status=400)

    try:
        result = finalize_oib(company_id, new_oib, user=request.user)
        return JsonResponse(result)
    except OIBFinalizerError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except (ValueError, TypeError) as exc:
        logger.exception('OIB Finalizer API error')
        return JsonResponse({'error': str(exc)}, status=500)
