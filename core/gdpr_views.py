"""
core/gdpr_views.py — GDPR compliance dashboard and API endpoints.

Provides:
- /gdpr/dashboard/  — Admin view of audit log, GDPR requests, data access
- /api/gdpr/export/ — REST API for data export (JSON download)
- /api/gdpr/erase/  — REST API for erasure request
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from core.audit_access import audit_sensitive_access

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  GDPR AUDIT DASHBOARD (admin only)
# ═══════════════════════════════════════════════════════════════════════

@login_required
@audit_sensitive_access('core.SystemAuditLog', description='GDPR Audit Dashboard pristup')
def gdpr_dashboard(request):
    """GDPR compliance dashboard — audit log, access tracking, GDPR requests."""
    from core.models import SystemAuditLog

    company = get_user_company(request)
    if not company:
        return render(request, 'core/gdpr_dashboard.html', {'error': 'Nema aktivne tvrtke.'})

    # Check permission — only tenant_admin or superadmin
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in ('superadmin', 'tenant_admin', 'company_admin'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Samo administratori mogu pristupiti GDPR dashboardu.")

    # Filters
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    user_filter = request.GET.get('user', '')
    days = int(request.GET.get('days', 30))

    cutoff = timezone.now() - timezone.timedelta(days=days)

    qs = SystemAuditLog.objects.filter(
        company=company,
        timestamp__gte=cutoff,
    ).select_related('user').order_by('-timestamp')

    if action_filter:
        qs = qs.filter(action=action_filter)
    if model_filter:
        qs = qs.filter(model_name__icontains=model_filter)
    if user_filter:
        qs = qs.filter(
            Q(user__username__icontains=user_filter) |
            Q(user__first_name__icontains=user_filter) |
            Q(user__last_name__icontains=user_filter)
        )

    # Stats
    stats = {
        'total_events': qs.count(),
        'reads': qs.filter(action='read').count(),
        'writes': qs.filter(action__in=['create', 'update']).count(),
        'deletes': qs.filter(action='delete').count(),
        'unique_users': qs.values('user').distinct().count(),
        'gdpr_exports': qs.filter(
            model_name='accounts.User',
            object_repr__icontains='GDPR'
        ).count(),
    }

    # Sensitive access breakdown by model
    sensitive_models = [
        'payroll.PayrollRun', 'payroll.Payslip',
        'konto.BankAccount', 'konto.JournalEntry',
        'accounts.User', 'worktime.EmployeeProfile',
    ]
    sensitive_access = qs.filter(
        action='read',
        model_name__in=sensitive_models,
    ).values('model_name').annotate(
        count=Count('id')
    ).order_by('-count')

    # Top accessors
    top_users = qs.values(
        'user__username', 'user__first_name', 'user__last_name'
    ).annotate(count=Count('id')).order_by('-count')[:10]

    ctx = {
        'logs': qs[:200],
        'stats': stats,
        'sensitive_access': sensitive_access,
        'top_users': top_users,
        'action_filter': action_filter,
        'model_filter': model_filter,
        'user_filter': user_filter,
        'days': days,
        'company': company,
    }
    return render(request, 'core/gdpr_dashboard.html', ctx)


# ═══════════════════════════════════════════════════════════════════════
#  REST API — GDPR EXPORT (čl. 20)
# ═══════════════════════════════════════════════════════════════════════

@login_required
@require_POST
@audit_sensitive_access('accounts.User', description='GDPR API Export (čl. 20)')
def api_gdpr_export(request):
    """
    POST /api/gdpr/export/
    Returns user's personal data as JSON (GDPR Article 20).
    Requires password confirmation in request body.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    password = data.get('password', '') or request.POST.get('password', '')

    if not request.user.check_password(password):
        return JsonResponse({
            'error': 'Pogrešna lozinka. GDPR export zahtijeva potvrdu identiteta.'
        }, status=403)

    from accounts.services.gdpr_export import GDPRExportService
    export_json = GDPRExportService.generate_export(request.user)

    response = HttpResponse(export_json, content_type='application/json; charset=utf-8')
    filename = f'gdpr_export_{request.user.username}_{timezone.now().strftime("%Y%m%d")}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ═══════════════════════════════════════════════════════════════════════
#  REST API — GDPR ERASURE (čl. 17)
# ═══════════════════════════════════════════════════════════════════════

@login_required
@require_POST
@audit_sensitive_access('accounts.User', description='GDPR API Erasure Request (čl. 17)')
def api_gdpr_erase(request):
    """
    POST /api/gdpr/erase/
    Anonymizes user's personal data (GDPR Article 17).
    Requires password confirmation.
    Financial records preserved per Croatian/German law (11 years).
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    password = data.get('password', '') or request.POST.get('password', '')

    if not request.user.check_password(password):
        return JsonResponse({
            'error': 'Pogrešna lozinka. GDPR brisanje zahtijeva potvrdu identiteta.'
        }, status=403)

    # Double confirmation
    confirm = data.get('confirm_erasure', False)
    if not confirm:
        return JsonResponse({
            'error': 'Morate potvrditi brisanje s confirm_erasure=true',
            'warning': (
                'Ova akcija je NEPOVRATNA. Vaš račun će biti deaktiviran '
                'i svi osobni podaci anonimizirani. Financijski zapisi '
                '(fakture, plaće, knjiženja) zadržavaju se po zakonu.'
            )
        }, status=400)

    from accounts.services.gdpr import GDPRAnonymizationService
    result = GDPRAnonymizationService.anonymize_user(request.user)

    return JsonResponse({
        'success': True,
        'message': 'Vaši osobni podaci su anonimizirani sukladno GDPR čl. 17.',
        'actions': result.get('actions', []),
        'note': 'Financijski zapisi zadržani po Zakonu o računovodstvu (čl. 10).',
    })
