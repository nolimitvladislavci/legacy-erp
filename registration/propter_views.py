"""
Propter operator dashboard & tenant management views.
Security hardened: input validation, audit logging, enum checks, bounds.
"""
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PropterTenant, CompanySubscription

logger = logging.getLogger('propter.security')

VALID_TIERS = {'client', 'bookkeeper'}
VALID_CERT_STATUSES = {'none', 'pending', 'active', 'expiring', 'expired'}
MAX_MONTHLY_FEE = Decimal('10000.00')
MAX_COMPANIES = 10000


def is_superadmin(user):
    return user.is_active and user.is_staff


def _audit_log(request, action, tenant, details=''):
    """Log sensitive propter operations."""
    logger.info(
        "PROPTER_AUDIT user=%s action=%s tenant=%s(pk=%s) company=%s %s",
        request.user.username, action, tenant.company.name, tenant.pk,
        tenant.company.oib, details,
    )
    try:
        from borg_ops.models import CardActivity
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(PropterTenant)
        CardActivity.objects.create(
            content_type=ct,
            object_id=str(tenant.pk),
            user=request.user,
            action=action,
            note=details[:200] if details else '',
            is_system_generated=False,
            is_public_facing=False,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    except Exception:
        pass


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
    if tier_filter and tier_filter in VALID_TIERS:
        filtered = filtered.filter(tier=tier_filter)
    if cert_filter and cert_filter in VALID_CERT_STATUSES:
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
            changes = []

            # Tier — validate enum
            new_tier = request.POST.get('tier', tenant.tier)
            if new_tier in VALID_TIERS and new_tier != tenant.tier:
                changes.append(f'tier: {tenant.tier}→{new_tier}')
                tenant.tier = new_tier

            tenant.operator_name = request.POST.get('operator_name', '')

            # Monthly fee — validate bounds
            try:
                new_fee = Decimal(request.POST.get('monthly_fee', '0') or '0')
                new_fee = max(Decimal('0'), min(new_fee, MAX_MONTHLY_FEE))
            except (InvalidOperation, ValueError):
                new_fee = tenant.monthly_fee
            if new_fee != tenant.monthly_fee:
                changes.append(f'fee: {tenant.monthly_fee}→{new_fee}')
            tenant.monthly_fee = new_fee

            # Max companies — validate bounds
            try:
                new_max = int(request.POST.get('max_companies', '1') or '1')
                new_max = max(1, min(new_max, MAX_COMPANIES))
            except (ValueError, TypeError):
                new_max = tenant.max_companies
            tenant.max_companies = new_max

            # Billing day — validate 1-28
            try:
                new_day = int(request.POST.get('billing_day', '1') or '1')
                new_day = max(1, min(new_day, 28))
            except (ValueError, TypeError):
                new_day = tenant.billing_day
            tenant.billing_day = new_day

            # Cert status — validate enum
            new_cert = request.POST.get('fina_cert_status', tenant.fina_cert_status)
            if new_cert in VALID_CERT_STATUSES:
                if new_cert != tenant.fina_cert_status:
                    changes.append(f'cert: {tenant.fina_cert_status}→{new_cert}')
                tenant.fina_cert_status = new_cert

            # Notes — truncate to prevent abuse
            tenant.notes = (request.POST.get('notes', '') or '')[:2000]

            tenant.is_active = 'is_active' in request.POST

            # Managed by — validate bookkeeper tier
            managed_by_id = request.POST.get('managed_by', '')
            if managed_by_id:
                try:
                    bookkeeper = PropterTenant.objects.get(pk=managed_by_id, tier='bookkeeper')
                    if bookkeeper != tenant.managed_by:
                        changes.append(f'managed_by: →{bookkeeper.company.name}')
                    tenant.managed_by = bookkeeper
                except PropterTenant.DoesNotExist:
                    tenant.managed_by = None
            else:
                if tenant.managed_by:
                    changes.append('managed_by: removed')
                tenant.managed_by = None

            tenant.save()

            # Audit log
            _audit_log(request, 'TENANT_UPDATE', tenant, '; '.join(changes) if changes else 'no field changes')

            messages.success(request, f'Tenant {tenant.company.name} ažuriran.')
            return redirect('registration:propter_tenant_detail', pk=tenant.pk)

        elif action == 'toggle_active':
            old = tenant.is_active
            tenant.is_active = not tenant.is_active
            tenant.save(update_fields=['is_active'])
            status = 'aktiviran' if tenant.is_active else 'deaktiviran'
            _audit_log(request, 'TENANT_TOGGLE', tenant, f'{old}→{tenant.is_active}')
            messages.success(request, f'{tenant.company.name} {status}.')
            return redirect('registration:propter_dashboard')

    # Mask API key for display (show only last 8 chars)
    api_key_masked = None
    if eracun_cfg and eracun_cfg.api_key:
        key = eracun_cfg.api_key
        api_key_masked = '•' * max(0, len(key) - 8) + key[-8:] if len(key) > 8 else key

    context = {
        'tenant': tenant,
        'eracun_stats': eracun_stats,
        'managed_clients': managed_clients,
        'bookkeepers': bookkeepers,
        'eracun_cfg': eracun_cfg,
        'api_key_masked': api_key_masked,
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
            messages.error(request, _('Odaberite tvrtku.'))
            return redirect('registration:propter_create_tenant')

        company = get_object_or_404(Company, pk=company_id)

        # Check if already exists
        if PropterTenant.objects.filter(company=company).exists():
            messages.warning(request, f'{company.name} vec ima Propter pretplatu.')
            return redirect('registration:propter_dashboard')

        tier = request.POST.get('tier', 'client')
        if tier not in VALID_TIERS:
            tier = 'client'

        fees = {'client': Decimal('50.00'), 'bookkeeper': Decimal('175.00')}

        try:
            monthly_fee = Decimal(request.POST.get('monthly_fee', '0') or str(fees.get(tier, '50')))
            monthly_fee = max(Decimal('0'), min(monthly_fee, MAX_MONTHLY_FEE))
        except (InvalidOperation, ValueError):
            monthly_fee = fees.get(tier, Decimal('50.00'))

        try:
            max_co = int(request.POST.get('max_companies', '1') or '1')
            max_co = max(1, min(max_co, MAX_COMPANIES))
        except (ValueError, TypeError):
            max_co = 1

        tenant = PropterTenant.objects.create(
            company=company,
            tier=tier,
            operator_name=request.POST.get('operator_name', '')[:200],
            monthly_fee=monthly_fee,
            max_companies=max_co,
            billing_day=1,
            is_active=True,
        )

        _audit_log(request, 'TENANT_CREATE', tenant, f'tier={tier} fee={monthly_fee}')
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
@require_POST
def propter_regenerate_api_key(request, pk):
    """Regenerate API key for a tenant. POST only."""
    import secrets
    from eracun.models import ERacunConfig
    tenant = get_object_or_404(PropterTenant, pk=pk)
    cfg, _ = ERacunConfig.objects.get_or_create(
        company=tenant.company, defaults={'is_active': False}
    )
    cfg.api_key = secrets.token_urlsafe(48)
    cfg.save(update_fields=['api_key'])
    _audit_log(request, 'API_KEY_REGEN', tenant, 'API key regenerated')
    messages.success(request, f'API ključ regeneriran za {tenant.company.name}.')
    return redirect('registration:propter_tenant_detail', pk=pk)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def propter_toggle_api(request, pk):
    """Toggle API access for a tenant. POST only."""
    from eracun.models import ERacunConfig
    tenant = get_object_or_404(PropterTenant, pk=pk)
    cfg, _ = ERacunConfig.objects.get_or_create(
        company=tenant.company, defaults={'is_active': False}
    )
    old = cfg.api_enabled
    cfg.api_enabled = not cfg.api_enabled
    cfg.save(update_fields=['api_enabled'])
    status = 'aktiviran' if cfg.api_enabled else 'deaktiviran'
    _audit_log(request, 'API_TOGGLE', tenant, f'{old}→{cfg.api_enabled}')
    messages.success(request, f'API pristup {status} za {tenant.company.name}.')
    return redirect('registration:propter_tenant_detail', pk=pk)
