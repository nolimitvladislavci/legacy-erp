"""GovExport Views — dashboard + run pipeline."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import GovDocumentType, GovExport, GovInstitution


@login_required
def dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    exports = GovExport.objects.filter(company=company)[:20]
    institutions = GovInstitution.objects.filter(is_active=True)
    doc_types = GovDocumentType.objects.filter(is_active=True).select_related('institution')

    stats = {
        'total': exports.count(),
        'accepted': exports.filter(status='accepted').count(),
        'pending': exports.filter(status__in=['draft', 'validated', 'signed', 'sent']).count(),
        'rejected': exports.filter(status='rejected').count(),
    }

    return render(request, 'gov_export/dashboard.html', {
        'exports': exports, 'institutions': institutions,
        'doc_types': doc_types, 'stats': stats,
    })


@login_required
@require_POST
def run_export(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)

    from .pipeline import run_pipeline
    results = run_pipeline(export, user=request.user)

    passed = sum(1 for v in results.values() if 'ok' in str(v))
    total = len(results)
    messages.success(request, f'Pipeline: {passed}/{total} koraka uspješno. Status: {export.status}')
    return redirect('gov_export:dashboard')


@login_required
def download_xml(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)

    if not export.xml_content:
        messages.error(request, _('XML još nije generiran.'))
        return redirect('gov_export:dashboard')

    response = HttpResponse(export.xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{export.reference_number}.xml"'
    return response


@login_required
def export_log(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)
    logs = export.logs.all()

    return JsonResponse({
        'reference': export.reference_number,
        'status': export.status,
        'progress': export.pipeline_progress,
        'logs': [
            {'step': l.step, 'status': l.status, 'message': l.message,
             'duration_ms': l.duration_ms, 'timestamp': l.timestamp.isoformat()}
            for l in logs
        ]
    })
