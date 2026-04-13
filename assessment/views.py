import base64
import io
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AssessmentPhoto, FieldAssessment
from django.core.exceptions import ObjectDoesNotExist


def _get_company(request):
    try:
        return request.user.userprofile.company
    except AttributeError:
        pass
    try:
        from accounts.models import UserProfile
        return UserProfile.objects.get(user=request.user).company
    except ObjectDoesNotExist:
        return None


# ── LIST ─────────────────────────────────────────────────────────────────────

@login_required
def assessment_list(request):
    qs = FieldAssessment.objects.select_related('created_by').prefetch_related('photos')

    status  = request.GET.get('status', '')
    atype   = request.GET.get('type', '')
    q       = request.GET.get('q', '')

    if status:
        qs = qs.filter(status=status)
    if atype:
        qs = qs.filter(assessment_type=atype)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(client_name__icontains=q) | Q(client_phone__icontains=q) | Q(client_address__icontains=q))

    return render(request, 'assessment/list.html', {
        'assessments':      qs[:60],
        'status_choices':   FieldAssessment.STATUS_CHOICES,
        'type_choices':     FieldAssessment.ASSESSMENT_TYPES,
        'selected_status':  status,
        'selected_type':    atype,
        'q':                q,
        'counts': {
            'total':     FieldAssessment.objects.count(),
            'draft':     FieldAssessment.objects.filter(status='DRAFT').count(),
            'completed': FieldAssessment.objects.filter(status='COMPLETED').count(),
            'sent':      FieldAssessment.objects.filter(status='OFFER_SENT').count(),
        },
    })


# ── NEW WIZARD ───────────────────────────────────────────────────────────────

@login_required
def assessment_new(request):
    return render(request, 'assessment/new.html', {})


# ── AJAX SAVE ────────────────────────────────────────────────────────────────

@login_required
@require_POST
def assessment_save(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    assessment_id  = payload.get('assessment_id')
    final_submit   = payload.get('final_submit', False)
    assessment_type = payload.get('assessment_type', 'bathroom')

    company = _get_company(request)

    if assessment_id:
        try:
            assessment = FieldAssessment.objects.get(pk=assessment_id)
        except FieldAssessment.DoesNotExist:
            assessment = FieldAssessment(company=company, created_by=request.user)
    else:
        assessment = FieldAssessment(company=company, created_by=request.user)

    if not hasattr(assessment, 'pk') or not assessment.pk:
        assessment.client_name = 'Skica'

    assessment.assessment_type = assessment_type

    # Merge step data
    existing = dict(assessment.json_data or {})
    for i in range(1, 7):
        key = f'step{i}'
        if payload.get(key):
            existing[key] = payload[key]
    assessment.json_data = existing

    # Populate top-level fields from step1
    s1 = existing.get('step1', {})
    if s1.get('client_name'):
        assessment.client_name  = s1['client_name']
        assessment.client_phone = s1.get('client_phone', '')
        assessment.client_email = s1.get('client_email', '')
        assessment.client_address = s1.get('client_address', '')
    elif not assessment.client_name:
        assessment.client_name = 'Skica'

    # Expert notes + price from step5
    s5 = existing.get('step5', {})
    if s5.get('expert_opinion'):
        assessment.notes = s5['expert_opinion']
    try:
        if s5.get('price_from'):
            assessment.calculated_price_from = float(str(s5['price_from']).replace(',', '.'))
        if s5.get('price_to'):
            assessment.calculated_price_to   = float(str(s5['price_to']).replace(',', '.'))
    except (ValueError, TypeError):
        pass

    assessment.status = 'COMPLETED' if final_submit else 'DRAFT'
    assessment.save()

    return JsonResponse({
        'ok':                True,
        'assessment_id':     assessment.pk,
        'status':            assessment.status,
        'completion_percent': assessment.completion_percent,
        'redirect_url':      assessment.get_absolute_url() if final_submit else '',
    })


# ── PHOTO UPLOAD ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def assessment_upload_photo(request, pk):
    assessment = get_object_or_404(FieldAssessment, pk=pk)
    photo_file = request.FILES.get('photo')
    if not photo_file:
        return JsonResponse({'ok': False, 'error': 'No file provided'}, status=400)

    ap = AssessmentPhoto.objects.create(
        assessment = assessment,
        photo      = photo_file,
        caption    = request.POST.get('caption', ''),
        step       = int(request.POST.get('step', 3)),
    )
    return JsonResponse({'ok': True, 'photo_id': ap.pk, 'url': ap.photo.url})


@login_required
@require_POST
def assessment_delete_photo(request, pk, photo_pk):
    photo = get_object_or_404(AssessmentPhoto, pk=photo_pk, assessment__pk=pk)
    photo.photo.delete(save=False)
    photo.delete()
    return JsonResponse({'ok': True})


# ── DETAIL ────────────────────────────────────────────────────────────────────

@login_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(FieldAssessment, pk=pk)
    photos_by_step = {}
    for p in assessment.photos.all():
        photos_by_step.setdefault(p.step, []).append(p)

    return render(request, 'assessment/detail.html', {
        'assessment':    assessment,
        'photos_by_step': photos_by_step,
        'data':          assessment.step_data,
    })


# ── STATUS UPDATE ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def assessment_status_update(request, pk):
    assessment = get_object_or_404(FieldAssessment, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(FieldAssessment.STATUS_CHOICES):
        assessment.status = new_status
        assessment.save(update_fields=['status', 'updated_at'])
    return redirect('assessment:detail', pk=pk)


# ── PDF ───────────────────────────────────────────────────────────────────────

@login_required
def assessment_pdf(request, pk):
    assessment = get_object_or_404(FieldAssessment, pk=pk)
    company    = assessment.company

    # QR code
    qr_b64 = ''
    try:
        import qrcode
        qr_url = request.build_absolute_uri(assessment.get_absolute_url())
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=4, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass

    # Company logo
    logo_b64, logo_mime = '', 'image/png'
    try:
        if company.logo:
            ext = company.logo.name.split('.')[-1].lower()
            logo_mime = 'image/png' if ext == 'png' else 'image/jpeg'
            with open(company.logo.path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode()
    except (FileNotFoundError, PermissionError, IOError):
        pass

    # Embed photos as base64
    photos = []
    for p in assessment.photos.all():
        try:
            ext  = p.photo.name.split('.')[-1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            with open(p.photo.path, 'rb') as f:
                photos.append({'obj': p, 'b64': base64.b64encode(f.read()).decode(), 'mime': mime})
        except (FileNotFoundError, PermissionError, IOError):
            pass

    from django.template.loader import get_template
    html = get_template('assessment/pdf.html').render({
        'assessment':   assessment,
        'data':         assessment.step_data,
        'qr_b64':       qr_b64,
        'logo_b64':     logo_b64,
        'logo_mime':    logo_mime,
        'photos':       photos,
        'company':      company,
        'generated_at': timezone.now(),
    })

    result = io.BytesIO()
    try:
        from xhtml2pdf import pisa
        pdf = pisa.CreatePDF(html, dest=result, encoding='UTF-8')
        if not pdf.err:
            resp = HttpResponse(result.getvalue(), content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="nalaz-{assessment.pk}.pdf"'
            return resp
        messages.error(request, f'PDF greška: {pdf.err}')
    except Exception as e:
        messages.error(request, f'PDF greška: {e}')
    return redirect('assessment:detail', pk=pk)

@login_required
def bad_nalaz_new(request):
    return render(request, 'assessment/bad_nalaz.html', {})
