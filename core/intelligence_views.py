"""
Intelligence Dashboard — cross-company partner BI for umbrella admins.

Accessible at /umbrella/intelligence/ for umbrella admins and superadmins.
Read-only aggregation — never mutates data across tenants.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.services_intelligence import get_intelligence_stats, search_partner_global

logger = logging.getLogger(__name__)


def _get_company_ids(company, user):
    """Get list of company IDs for intelligence queries."""
    from companies.models import Company

    if user.is_superuser:
        umbrella_id = None
        # Superadmin can specify umbrella via GET param (handled in view)
        if company and company.is_umbrella:
            children = Company.objects.filter(umbrella_parent=company).values_list('id', flat=True)
            return [company.id] + list(children)
        # Superadmin without umbrella: all companies
        return list(Company.objects.values_list('id', flat=True))

    if not company or not company.is_umbrella:
        return [company.id] if company else []

    children = Company.objects.filter(umbrella_parent=company).values_list('id', flat=True)
    return [company.id] + list(children)


@login_required
def intelligence_dashboard(request):
    """Main intelligence dashboard view."""
    from companies.models import Company
    from core.company_utils import get_user_company

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nemate dodijeljenu tvrtku.')
        return redirect('dashboard')

    # Superadmin umbrella override
    umbrella_id = request.GET.get('umbrella')
    if request.user.is_superuser and umbrella_id:
        try:
            company = Company.objects.get(pk=umbrella_id)
        except Company.DoesNotExist:
            pass

    if not company.is_umbrella and not request.user.is_superuser:
        messages.warning(request, 'Intelligence Dashboard je dostupan samo za umbrella korisnike.')
        return redirect('dashboard')

    company_ids = _get_company_ids(company, request.user)
    stats = get_intelligence_stats(company_ids)

    # Umbrella selector for superadmins
    all_umbrellas = None
    if request.user.is_superuser:
        all_umbrellas = Company.objects.filter(is_umbrella=True).order_by('name')

    children_count = len(company_ids) - 1  # exclude parent

    return render(request, 'dashboards/intelligence.html', {
        'company': company,
        'children_count': children_count,
        'all_umbrellas': all_umbrellas,
        **stats,
    })


@login_required
def intelligence_search(request):
    """AJAX endpoint: search partner by OIB across companies."""
    from core.company_utils import get_user_company

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=403)

    oib = request.GET.get('oib', '').strip()
    if not oib:
        return JsonResponse({'results': []})

    company_ids = _get_company_ids(company, request.user)
    results = search_partner_global(oib, company_ids)

    # Convert Decimal to float for JSON
    for r in results:
        for k in ('cached_balance', 'unpaid_total'):
            if k in r and r[k] is not None:
                r[k] = float(r[k])
        if 'company_id' in r:
            r['company_id'] = str(r['company_id'])

    return JsonResponse({'results': results, 'oib': oib})
