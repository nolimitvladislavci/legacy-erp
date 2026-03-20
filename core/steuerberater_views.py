import logging
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@login_required
def steuerberater_portal(request):
    """Steuerberater upload portal — limited view for tax advisor."""
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from documents.models import ArhivaEntry
    recent = ArhivaEntry.objects.filter(
        company=company, source_type='steuerberater_upload'
    ).order_by('-archived_at')[:20]

    return render(request, 'core/steuerberater_portal.html', {
        'company': company, 'recent': recent,
    })


@login_required
@require_POST
def steuerberater_upload(request):
    """Handle file upload from Steuerberater."""
    from core.company_utils import get_user_company
    company = get_user_company(request)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'Keine Datei'}, status=400)

    doc_type = request.POST.get('doc_type', 'lohnabrechnung')
    notes = request.POST.get('notes', '')

    # Save file
    upload_dir = os.path.join('/var/www/fina-connect/media/steuerberater', str(company.pk))
    os.makedirs(upload_dir, exist_ok=True)

    filename = f'{timezone.now().strftime("%Y%m%d_%H%M")}_{f.name}'
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, 'wb') as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    # Create archive entry
    from documents.models import ArhivaEntry
    entry = ArhivaEntry.objects.create(
        company=company,
        source_type='steuerberater_upload',
        source_id=f'stb_{timezone.now().strftime("%Y%m%d%H%M%S")}',
        doc_number=f'STB-{doc_type.upper()[:4]}-{timezone.now().strftime("%Y%m")}',
        partner_name=f'Steuerberater Upload ({request.user.get_full_name()})',
        amount=0,
        currency='EUR',
        doc_date=timezone.now().date(),
        file_path=f'steuerberater/{company.pk}/{filename}',
    )

    # Notify owner via WhatsApp
    try:
        from core.whatsapp import send_text
        send_text('+385976091655',
            f'\U0001f4c4 Steuerberater Upload: {f.name}\nTyp: {doc_type}\nFirma: {company.name}\nVon: {request.user.get_full_name()}')
    except Exception:
        pass

    logger.info('Steuerberater upload: %s by %s for %s', f.name, request.user, company)

    return JsonResponse({
        'ok': True,
        'message': 'Datei erfolgreich hochgeladen.',
        'entry_id': entry.pk,
    })
