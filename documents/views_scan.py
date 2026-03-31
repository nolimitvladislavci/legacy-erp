"""Scan Views — QR scan + Scan Batch (BORG FENIX)."""
import json
import logging
import uuid as _uuid

import base64 as _b64
import io as _io
import redis as _redis
import qrcode as _qrcode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt as _csrf_exempt_scan
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import ArhivaEntry, ScanBatch, ScanBatchImage

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# QR SCAN — Remote skeniranje s mobitela
# ════════════════════════════════════════════════════════════

def _get_redis():
    return _redis.Redis(host='127.0.0.1', port=6379, db=2, decode_responses=False)

@login_required
def scan_create_token(request):
    """Desktop: kreira token za remote scan i vraca QR kod."""
    token = str(_uuid.uuid4())
    r = _get_redis()
    # Spremi token s company_id i user_id, 10 min TTL
    company = get_user_company(request)
    data = '%d:%d' % (company.id if company else 0, request.user.id)
    r.setex('scan:%s' % token, 600, data.encode('utf-8'))

    # Generiraj QR kod kao base64
    from django.urls import reverse as _rev; url = request.build_absolute_uri(_rev('documents:scan_mobile_page', args=[token]))
    qr = _qrcode.QRCode(version=1, error_correction=_qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#c9a84c', back_color='#0a0a0a')
    buf = _io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = _b64.b64encode(buf.getvalue()).decode('ascii')

    return JsonResponse({
        'token': token,
        'qr_data': 'data:image/png;base64,' + qr_b64,
        'url': url,
        'expires_in': 600,
    })


def scan_mobile_page(request, token):
    """Mobitel: stranica s kamerom — bez login-a, samo token provjera."""
    r = _get_redis()
    data = r.get('scan:%s' % token)
    if not data:
        return render(request, 'documents/scan_expired.html', {})
    return render(request, 'documents/scan_mobile.html', {'token': token})


@_csrf_exempt_scan
def scan_upload(request, token):
    """Mobitel: prima sliku i sprema u Redis pod tokenom."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    r = _get_redis()
    data = r.get('scan:%s' % token)
    if not data:
        return JsonResponse({'error': 'Token istekao'}, status=410)

    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'Nema datoteke'}, status=400)

    # Samo slike — sprijecava upload proizvoljnih fajlova
    if not uploaded.content_type.startswith('image/'):
        return JsonResponse({'error': 'Samo slike (JPG, PNG, WebP)'}, status=400)

    file_bytes = uploaded.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Prevelika datoteka (max 10MB)'}, status=400)

    # Spremi sliku u Redis (5 min TTL)
    meta = json.dumps({'filename': uploaded.name, 'size': len(file_bytes), 'content_type': uploaded.content_type})
    r.setex('scan_img:%s' % token, 300, file_bytes)
    r.setex('scan_meta:%s' % token, 300, meta.encode('utf-8'))

    # Oznaci da je slika stigla
    r.setex('scan_ready:%s' % token, 300, b'1')
    # Single-use: obrisi token nakon uploada
    r.delete("scan:%s" % token)

    return JsonResponse({'ok': True, 'message': 'Slika primljena! Mozete zatvoriti ovu stranicu.'})


@login_required
def scan_poll(request, token):
    """Desktop: polling — provjerava je li slika stigla."""
    r = _get_redis()
    ready = r.get('scan_ready:%s' % token)
    if not ready:
        return JsonResponse({'ready': False})

    # Slika je tu — dohvati i pokreni konverziju
    meta_raw = r.get('scan_meta:%s' % token)
    file_bytes = r.get('scan_img:%s' % token)

    if not file_bytes or not meta_raw:
        return JsonResponse({'ready': False})

    meta = json.loads(meta_raw.decode('utf-8'))

    # Pokreni konverziju
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne tvrtke'}, status=400)

    try:
        from documents.conversion_service import convert_image_to_xml
        record = convert_image_to_xml(
            file_bytes=file_bytes,
            filename=meta.get('filename', 'scan.jpg'),
            company=company,
            user=request.user,
        )

        # Ocisti Redis
        for key in ['scan:%s', 'scan_img:%s', 'scan_meta:%s', 'scan_ready:%s']:
            r.delete(key % token)

        return JsonResponse({
            'ready': True,
            'converted': True,
            'record_id': str(record.id),
            'status': record.status,
            'confidence_score': record.ai_confidence_score,
            'fields_extracted': record.fields_extracted,
            'items_extracted': record.items_extracted,
            'is_valid': record.is_valid,
            'validation_errors': record.validation_errors,
            'extracted_data': record.extracted_data,
            'savings': record.savings_display,
            'size_reduction_pct': round(record.size_reduction_pct, 1),
            'message': 'Konverzija zavrsena: %s' % meta.get('filename', 'scan'),
        })
    except Exception as e:
        return JsonResponse({'ready': True, 'converted': False, 'error': str(e)})


# ════════════════════════════════════════════════════════════
# SCAN BATCH — BORG FENIX
# ════════════════════════════════════════════════════════════

@login_required
def scan_batch_new(request):
    """Kreiraj novu batch sesiju za skeniranje."""
    company = get_user_company(request)
    if not company:
        return redirect('documents:list')

    batch = ScanBatch.objects.create(company=company, created_by=request.user)
    return redirect('documents:scan_batch_detail', pk=batch.pk)


@login_required
def scan_batch_detail(request, pk):
    """Pregled batch sesije s 2-tipke UI."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    images = batch.images.all().order_by('order')
    return render(request, 'documents/scan_batch.html', {
        'batch': batch,
        'images': images,
    })


@login_required
@require_POST
def scan_batch_upload(request, pk):
    """Upload slika u batch (multipart, do 100)."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.status not in ('collecting',):
        return JsonResponse({'ok': False, 'error': 'Batch nije u collecting statusu'}, status=400)

    files = request.FILES.getlist('images')
    if not files:
        return JsonResponse({'ok': False, 'error': 'Nema slika'}, status=400)

    current_count = batch.images.count()
    if current_count + len(files) > 100:
        return JsonResponse({'ok': False, 'error': f'Max 100 slika (trenutno {current_count})'}, status=400)

    added = 0
    for i, f in enumerate(files):
        ScanBatchImage.objects.create(
            batch=batch,
            image=f,
            order=current_count + i + 1,
            original_filename=f.name,
            file_size_kb=f.size // 1024,
        )
        added += 1

    batch.total_images = batch.images.count()
    batch.total_size_kb = sum(img.file_size_kb for img in batch.images.all())
    batch.save(update_fields=['total_images', 'total_size_kb', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'added': added,
        'total_images': batch.total_images,
        'total_size_kb': batch.total_size_kb,
    })


@login_required
@require_POST
def scan_batch_process(request, pk):
    """Pokreni OCR + AI grupiranje za batch."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.total_images == 0:
        return JsonResponse({'ok': False, 'error': 'Nema slika za obradu'}, status=400)

    batch.status = 'processing'
    batch.save(update_fields=['status'])

    from documents.tasks import process_scan_batch
    process_scan_batch.delay(batch.pk)

    return JsonResponse({'ok': True, 'status': 'processing'})


@login_required
def scan_batch_status(request, pk):
    """JSON status za polling."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    images = batch.images.all().order_by('order')
    return JsonResponse({
        'status': batch.status,
        'total_images': batch.total_images,
        'total_documents': batch.total_documents,
        'images': [
            {
                'id': img.pk,
                'order': img.order,
                'document_group': img.document_group,
                'page_in_group': img.page_in_group,
                'confidence': img.ai_confidence,
                'has_text': bool(img.extracted_text),
            }
            for img in images
        ],
    })


@login_required
@require_POST
def scan_batch_archive(request, pk):
    """Spremi batch u arhivu — kreira ArhivaEntry za svaki dokument."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)

    if batch.status != 'ready':
        return JsonResponse({'ok': False, 'error': 'Batch nije spreman'}, status=400)

    groups = {}
    for img in batch.images.filter(document_group__isnull=False).order_by('document_group', 'page_in_group'):
        groups.setdefault(img.document_group, []).append(img)

    created = 0
    for group_num, imgs in groups.items():
        first = imgs[0]
        data = first.extracted_data or {}
        ArhivaEntry.objects.create(
            company=company,
            uploaded_by=request.user,
            file=first.image,
            original_filename=first.original_filename or f'batch_{batch.pk}_doc_{group_num}',
            doc_type=data.get('doc_type', 'unknown'),
            extracted_data=data,
            status='ai_processed',
        )
        created += 1

    batch.status = 'done'
    batch.total_documents = created
    batch.save(update_fields=['status', 'total_documents'])

    return JsonResponse({'ok': True, 'archived': created})
