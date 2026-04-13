"""Scan Views — QR scan + Scan Batch (Enterprise Architecture)."""
import base64 as _b64
import io as _io
import json
import logging
import uuid as _uuid

import qrcode as _qrcode
import redis as _redis
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt as _csrf_exempt
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import ScanBatch, ScanBatchImage

logger = logging.getLogger(__name__)


# ================================================================
# QR SCAN — Remote skeniranje s mobitela
# ================================================================

def _get_redis():
    return _redis.Redis(host='127.0.0.1', port=6379, db=2, decode_responses=False)


@login_required
def scan_create_token(request):
    token = str(_uuid.uuid4())
    r = _get_redis()
    company = get_user_company(request)
    r.setex('scan:%s' % token, 600,
            ('%d:%d' % (company.id if company else 0, request.user.id)).encode())
    from django.urls import reverse
    url = request.build_absolute_uri(reverse('documents:scan_mobile_page', args=[token]))
    qr = _qrcode.QRCode(version=1, error_correction=_qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#c9a84c', back_color='#0a0a0a')
    buf = _io.BytesIO()
    img.save(buf, format='PNG')
    return JsonResponse({
        'token': token,
        'qr_data': 'data:image/png;base64,' + _b64.b64encode(buf.getvalue()).decode(),
        'url': url, 'expires_in': 600,
    })


def scan_mobile_page(request, token):
    r = _get_redis()
    if not r.get('scan:%s' % token):
        return render(request, 'documents/scan_expired.html', {})
    return render(request, 'documents/scan_mobile.html', {'token': token})


@_csrf_exempt
def scan_upload(request, token):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    r = _get_redis()
    if not r.get('scan:%s' % token):
        return JsonResponse({'error': 'Token istekao'}, status=410)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'Nema datoteke'}, status=400)
    if not uploaded.content_type.startswith('image/'):
        return JsonResponse({'error': 'Samo slike'}, status=400)
    file_bytes = uploaded.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Max 10MB'}, status=400)
    meta = json.dumps({'filename': uploaded.name, 'size': len(file_bytes),
                       'content_type': uploaded.content_type})
    r.setex('scan_img:%s' % token, 300, file_bytes)
    r.setex('scan_meta:%s' % token, 300, meta.encode())
    r.setex('scan_ready:%s' % token, 300, b'1')
    r.delete('scan:%s' % token)
    return JsonResponse({'ok': True, 'message': 'Slika primljena!'})


@login_required
def scan_poll(request, token):
    r = _get_redis()
    if not r.get('scan_ready:%s' % token):
        return JsonResponse({'ready': False})
    meta_raw = r.get('scan_meta:%s' % token)
    file_bytes = r.get('scan_img:%s' % token)
    if not file_bytes or not meta_raw:
        return JsonResponse({'ready': False})
    meta = json.loads(meta_raw.decode())
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema tvrtke'}, status=400)
    try:
        from documents.conversion_service import convert_image_to_xml
        record = convert_image_to_xml(
            file_bytes=file_bytes, filename=meta.get('filename', 'scan.jpg'),
            company=company, user=request.user)
        for k in ['scan:%s', 'scan_img:%s', 'scan_meta:%s', 'scan_ready:%s']:
            r.delete(k % token)
        return JsonResponse({
            'ready': True, 'converted': True,
            'record_id': str(record.id), 'status': record.status,
            'confidence_score': record.ai_confidence_score,
            'fields_extracted': record.fields_extracted,
            'items_extracted': record.items_extracted,
            'is_valid': record.is_valid,
            'validation_errors': record.validation_errors,
            'extracted_data': record.extracted_data,
            'savings': record.savings_display,
            'size_reduction_pct': round(record.size_reduction_pct, 1),
        })
    except ImportError as e:
        return JsonResponse({'ready': True, 'converted': False, 'error': str(e)})


# ================================================================
# SCAN BATCH — Enterprise Pipeline (3 klika)
# Views su TANKI — sva logika u DocumentProcessor
# ================================================================

@login_required
def scan_batch_new(request):
    company = get_user_company(request)
    # Radnica moze kreirati batch za komitenta iz svog stola
    override_id = request.GET.get('company', '')
    if override_id:
        from accounts.models import CompanyMembership
        has_access = CompanyMembership.objects.filter(
            user=request.user, company_id=override_id, is_active=True
        ).exists()
        if has_access:
            from companies.models import Company
            company = Company.objects.filter(pk=override_id).first() or company
    if not company:
        return redirect('documents:list')
    batch = ScanBatch.objects.create(company=company, created_by=request.user)
    return redirect('documents:scan_batch_detail', pk=batch.pk)


@login_required
def scan_batch_detail(request, pk):
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    return render(request, 'documents/scan_batch.html', {
        'batch': batch,
        'images': batch.images.order_by('order'),
    })


@login_required
@require_POST
def scan_batch_upload(request, pk):
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.status != 'collecting':
        return JsonResponse({'ok': False, 'error': 'Batch nije u collecting statusu'}, status=400)

    files = request.FILES.getlist('images')
    if not files:
        return JsonResponse({'ok': False, 'error': 'Nema slika'}, status=400)

    current = batch.images.count()
    if current + len(files) > 100:
        return JsonResponse({'ok': False, 'error': 'Max 100 slika (trenutno %d)' % current}, status=400)

    for i, f in enumerate(files):
        ScanBatchImage.objects.create(
            batch=batch, image=f, order=current + i + 1,
            original_filename=f.name, file_size_kb=f.size // 1024)

    batch.total_images = batch.images.count()
    batch.total_size_kb = sum(img.file_size_kb for img in batch.images.all())
    batch.save(update_fields=['total_images', 'total_size_kb', 'updated_at'])

    return JsonResponse({
        'ok': True, 'added': len(files),
        'total_images': batch.total_images,
        'total_size_kb': batch.total_size_kb,
    })


@login_required
@require_POST
def scan_batch_process(request, pk):
    """Klik 2: Pokreni AI analizu. Self-rescheduling, zero blocking."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.total_images == 0:
        return JsonResponse({'ok': False, 'error': 'Nema slika'}, status=400)

    batch.status = 'processing'
    batch.error_message = 'Pokrecem AI analizu...'
    batch.save(update_fields=['status', 'error_message'])

    # Self-rescheduling task — NEMA time.sleep
    from documents.tasks_scan_gemini import process_scan_chunk
    process_scan_chunk.delay(batch.pk, 0, 0, 0)

    total = batch.total_images
    chunks = (total + 9) // 10
    est = max(1, chunks + (chunks - 1))  # obrada + pauze

    return JsonResponse({
        'ok': True, 'status': 'processing',
        'total_images': total,
        'estimated_minutes': est,
    })


@login_required
def scan_batch_status(request, pk):
    """Polling endpoint — delegira na DocumentProcessor."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    from documents.services.document_processor import DocumentProcessor
    return JsonResponse(DocumentProcessor.get_summary(batch.pk))


@login_required
@require_POST
def scan_batch_archive(request, pk):
    """Klik 3: Async arhiviranje s atomic transactions."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.status != 'ready':
        return JsonResponse({'ok': False, 'error': 'Batch nije spreman'}, status=400)

    from documents.tasks_scan_gemini import archive_scan_batch
    archive_scan_batch.delay(batch.pk, request.user.pk)

    return JsonResponse({
        'ok': True,
        'message': 'Arhiviranje pokrenuto. Dokumenti se pojavljuju u arhivi.',
    })
