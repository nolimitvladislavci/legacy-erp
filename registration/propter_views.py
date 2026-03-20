"""
Propter operator dashboard & tenant management views.
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone

from .models import PropterTenant, CompanySubscription


def is_superadmin(user):
    return user.is_active and user.is_staff


@login_required
@user_passes_test(is_superadmin)
def propter_dashboard(request):
    """Main Propter operator dashboard — overview of all tenants."""
    tenants = PropterTenant.objects.select_related('company', 'managed_by').all()

    # Stats
    total_tenants = tenants.count()
    active_tenants = tenants.filter(is_active=True).count()
    bookkeepers = tenants.filter(tier='bookkeeper', is_active=True).count()
    clients = tenants.filter(tier='client', is_active=True).count()

    mrr = tenants.filter(is_active=True).aggregate(
        total=Sum('monthly_fee')
    )['total'] or Decimal('0')

    # Cert status breakdown
    cert_active = tenants.filter(fina_cert_status='active').count()
    cert_pending = tenants.filter(fina_cert_status='pending').count()
    cert_expired = tenants.filter(fina_cert_status__in=['expired', 'expiring']).count()
    cert_none = tenants.filter(fina_cert_status='none').count()

    # e-Racun stats
    total_eracuni = tenants.aggregate(t=Sum('eracuni_sent_total'))['t'] or 0
    month_eracuni = tenants.aggregate(t=Sum('eracuni_sent_month'))['t'] or 0

    # Per-bookkeeper breakdown
    bookkeeper_list = tenants.filter(tier='bookkeeper', is_active=True).annotate(
        client_count=Count('managed_tenants')
    )

    # Filter
    tier_filter = request.GET.get('tier', '')
    cert_filter = request.GET.get('cert', '')
    search = request.GET.get('q', '')

    filtered = tenants
    if tier_filter:
        filtered = filtered.filter(tier=tier_filter)
    if cert_filter:
        filtered = filtered.filter(fina_cert_status=cert_filter)
    if search:
        filtered = filtered.filter(
            Q(company__name__icontains=search) |
            Q(operator_name__icontains=search) |
            Q(company__oib__icontains=search)
        )

    context = {
        'tenants': filtered,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'bookkeepers': bookkeepers,
        'clients': clients,
        'mrr': mrr,
        'cert_active': cert_active,
        'cert_pending': cert_pending,
        'cert_expired': cert_expired,
        'cert_none': cert_none,
        'total_eracuni': total_eracuni,
        'month_eracuni': month_eracuni,
        'bookkeeper_list': bookkeeper_list,
        'tier_filter': tier_filter,
        'cert_filter': cert_filter,
        'search': search,
    }
    return render(request, 'registration/propter_dashboard.html', context)


@login_required
@user_passes_test(is_superadmin)
def propter_tenant_detail(request, pk):
    """Detail/edit view for a single tenant."""
    tenant = get_object_or_404(PropterTenant.objects.select_related('company', 'managed_by'), pk=pk)

    # Get or create ERacunConfig (API key management)
    eracun_cfg = None
    try:
        from eracun.models import ERacunConfig
        eracun_cfg, _ = ERacunConfig.objects.get_or_create(
            company=tenant.company,
            defaults={'is_active': False}
        )
    except Exception:
        pass

    # Get e-racun stats from eracun app
    eracun_stats = {}
    try:
        from eracun.models import ERacun
        qs = ERacun.objects.filter(company=tenant.company)
        eracun_stats = {
            'total': qs.count(),
            'accepted': qs.filter(status='accepted').count(),
            'rejected': qs.filter(status='rejected').count(),
            'errors': qs.filter(status='error').count(),
            'draft': qs.filter(status='draft').count(),
        }
    except Exception:
        pass

    # Managed clients (for bookkeepers)
    managed_clients = []
    if tenant.tier == 'bookkeeper':
        managed_clients = PropterTenant.objects.filter(
            managed_by=tenant, is_active=True
        ).select_related('company')

    # Available bookkeepers for assignment
    bookkeepers = PropterTenant.objects.filter(
        tier='bookkeeper', is_active=True
    ).exclude(pk=tenant.pk).select_related('company')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update':
            tenant.tier = request.POST.get('tier', tenant.tier)
            tenant.operator_name = request.POST.get('operator_name', '')
            tenant.monthly_fee = Decimal(request.POST.get('monthly_fee', '0') or '0')
            tenant.max_companies = int(request.POST.get('max_companies', '1') or '1')
            tenant.billing_day = int(request.POST.get('billing_day', '1') or '1')
            tenant.fina_cert_status = request.POST.get('fina_cert_status', tenant.fina_cert_status)
            tenant.notes = request.POST.get('notes', '')
            tenant.is_active = 'is_active' in request.POST

            # Managed by (bookkeeper assignment)
            managed_by_id = request.POST.get('managed_by', '')
            if managed_by_id:
                try:
                    tenant.managed_by = PropterTenant.objects.get(pk=managed_by_id)
                except PropterTenant.DoesNotExist:
                    tenant.managed_by = None
            else:
                tenant.managed_by = None

            tenant.save()
            messages.success(request, f'Tenant {tenant.company.name} azuriran.')
            return redirect('registration:propter_tenant_detail', pk=tenant.pk)

        elif action == 'toggle_active':
            tenant.is_active = not tenant.is_active
            tenant.save(update_fields=['is_active'])
            status = 'aktiviran' if tenant.is_active else 'deaktiviran'
            messages.success(request, f'{tenant.company.name} {status}.')
            return redirect('registration:propter_dashboard')

    context = {
        'tenant': tenant,
        'eracun_stats': eracun_stats,
        'managed_clients': managed_clients,
        'bookkeepers': bookkeepers,
        'eracun_cfg': eracun_cfg,
    }
    return render(request, 'registration/propter_tenant_detail.html', context)


@login_required
@user_passes_test(is_superadmin)
def propter_create_tenant(request):
    """Create PropterTenant for an existing company that doesn't have one."""
    from companies.models import Company

    # Companies without tenant
    existing_ids = PropterTenant.objects.values_list('company_id', flat=True)
    available = Company.objects.exclude(id__in=existing_ids).order_by('name')

    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        if not company_id:
            messages.error(request, 'Odaberite tvrtku.')
            return redirect('registration:propter_create_tenant')

        company = get_object_or_404(Company, pk=company_id)

        # Check if already exists
        if PropterTenant.objects.filter(company=company).exists():
            messages.warning(request, f'{company.name} vec ima Propter pretplatu.')
            return redirect('registration:propter_dashboard')

        tier = request.POST.get('tier', 'client')
        fees = {'client': Decimal('50.00'), 'bookkeeper': Decimal('175.00')}

        tenant = PropterTenant.objects.create(
            company=company,
            tier=tier,
            operator_name=request.POST.get('operator_name', ''),
            monthly_fee=Decimal(request.POST.get('monthly_fee', '0') or str(fees.get(tier, '50'))),
            max_companies=int(request.POST.get('max_companies', '1') or '1'),
            billing_day=1,
            is_active=True,
        )
        messages.success(request, f'Propter tenant kreiran za {company.name}.')
        return redirect('registration:propter_tenant_detail', pk=tenant.pk)

    return render(request, 'registration/propter_create_tenant.html', {
        'available_companies': available,
    })


@login_required
@user_passes_test(is_superadmin)
def propter_api_stats(request):
    """API endpoint for dashboard chart data."""
    from eracun.models import ERacun
    from django.db.models.functions import TruncMonth

    # Monthly e-racun volume (last 12 months)
    monthly = (
        ERacun.objects
        .filter(created_at__gte=timezone.now() - timezone.timedelta(days=365))
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Revenue by tier
    tenants = PropterTenant.objects.filter(is_active=True)
    revenue_by_tier = {
        'client': tenants.filter(tier='client').aggregate(s=Sum('monthly_fee'))['s'] or 0,
        'bookkeeper': tenants.filter(tier='bookkeeper').aggregate(s=Sum('monthly_fee'))['s'] or 0,
    }

    return JsonResponse({
        'monthly_volume': [{'month': m['month'].strftime('%Y-%m'), 'count': m['count']} for m in monthly],
        'revenue_by_tier': revenue_by_tier,
    })


@login_required
@user_passes_test(is_superadmin)
def propter_regenerate_api_key(request, pk):
    """Regenerate API key for a tenant."""
    import secrets
    from eracun.models import ERacunConfig
    tenant = get_object_or_404(PropterTenant, pk=pk)
    cfg, _ = ERacunConfig.objects.get_or_create(
        company=tenant.company, defaults={'is_active': False}
    )
    cfg.api_key = secrets.token_urlsafe(48)
    cfg.save(update_fields=['api_key'])
    messages.success(request, f'API kljuc regeneriran za {tenant.company.name}.')
    return redirect('registration:propter_tenant_detail', pk=pk)


@login_required
@user_passes_test(is_superadmin)
def propter_toggle_api(request, pk):
    """Toggle API access for a tenant."""
    from eracun.models import ERacunConfig
    tenant = get_object_or_404(PropterTenant, pk=pk)
    cfg, _ = ERacunConfig.objects.get_or_create(
        company=tenant.company, defaults={'is_active': False}
    )
    cfg.api_enabled = not cfg.api_enabled
    cfg.save(update_fields=['api_enabled'])
    status = 'aktiviran' if cfg.api_enabled else 'deaktiviran'
    messages.success(request, f'API pristup {status} za {tenant.company.name}.')
    return redirect('registration:propter_tenant_detail', pk=pk)
