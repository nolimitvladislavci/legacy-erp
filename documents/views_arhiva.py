"""Arhiva Views — Centralizirana arhiva svih dokumenata."""
import csv
import io
import json
import logging
import mimetypes
import os
import zipfile
from datetime import date
from decimal import Decimal

import fitz  # PyMuPDF

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from partners.models import Partner

from .models import ArhivaBookmark, ArhivaEntry, ArhivaLabel, DocumentBlob
from .storage_backends import store_document

logger = logging.getLogger(__name__)


def _safe_err(e, default="Greska pri obradi. Kontaktirajte administratora."):
    """Sanitizira exception poruku — ne salje stack trace korisniku."""
    msg = str(e)
    if len(msg) > 80 or any(x in msg for x in ['File "', 'line ', 'Traceback', 'django.', 'psycopg']):
        return default
    return msg[:80]


def _fuzzy_match_partner(partner_name, company):
    """Fuzzy match partner_name against Partner model for the company.
    Returns (Partner instance, match_score) or (None, 0)."""
    if not partner_name or not partner_name.strip():
        return None, 0

    name_clean = partner_name.strip()

    # 1. Exact match (case-insensitive)
    exact = Partner.objects.filter(
        company=company, is_active=True, name__iexact=name_clean
    ).first()
    if exact:
        return exact, 1.0

    # 2. Starts-with match (first 10 chars)
    prefix = name_clean[:10]
    starts = Partner.objects.filter(
        company=company, is_active=True, name__istartswith=prefix
    ).first()
    if starts:
        return starts, 0.85

    # 3. Contains match (longest word from name)
    words = [w for w in name_clean.split() if len(w) > 3]
    if words:
        longest = max(words, key=len)
        contains = Partner.objects.filter(
            company=company, is_active=True, name__icontains=longest
        ).first()
        if contains:
            return contains, 0.65

    # 4. Trigram / token overlap
    tokens = set(name_clean.lower().split())
    if tokens:
        candidates = Partner.objects.filter(company=company, is_active=True)[:500]
        best = None
        best_score = 0
        for p in candidates:
            p_tokens = set(p.name.lower().split())
            if tokens and p_tokens:
                overlap = len(tokens & p_tokens) / max(len(tokens), len(p_tokens))
                if overlap > best_score:
                    best_score = overlap
                    best = p
        if best and best_score >= 0.5:
            return best, best_score

    return None, 0


def _get_thumbnail_path(entry):
    """
    Vrati putanju do thumbnail JPG za ArhivaEntry.
    Format: media/thumbnails/arhiva/{pk}.jpg
    """
    thumb_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails', 'arhiva')
    os.makedirs(thumb_dir, exist_ok=True)
    return os.path.join(thumb_dir, f'{entry.pk}.jpg')


def _generate_thumbnail(entry, full_path, thumb_path):
    """
    Generiraj thumbnail (200x280px) od prve stranice PDF-a ili slike.
    Koristi PyMuPDF. Vraca True ako uspjesno.
    """
    try:
        ext = os.path.splitext(full_path)[1].lower()

        if ext == '.pdf':
            doc  = fitz.open(full_path)
            page = doc[0]
            # Render na 150 DPI (dovoljno za thumbnail)
            mat  = fitz.Matrix(150 / 72, 150 / 72)
            pix  = page.get_pixmap(matrix=mat, alpha=False)
            doc.close()

        elif ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
            # Za slike — samo resizaj kroz PyMuPDF
            doc  = fitz.open(full_path)
            page = doc[0]
            mat  = fitz.Matrix(0.5, 0.5)
            pix  = page.get_pixmap(matrix=mat, alpha=False)
            doc.close()

        else:
            return False

        # Spremi kao JPEG
        pix.save(thumb_path, output='jpeg', jpg_quality=75)
        return True

    except Exception as e:
        logger.warning(f'Thumbnail greska za entry {entry.pk}: {e}')
        return False


def _thumbnail_placeholder(entry):
    """Vrati SVG placeholder s tipom dokumenta."""
    icon_map = {
        'invoice_out':  ('#3b82f6', 'R'),
        'invoice_in':   ('#10b981', 'U'),
        'eracun':       ('#8b5cf6', 'E'),
        'document':     ('#6b7280', 'D'),
        'fiscal_cert':  ('#f59e0b', 'C'),
        'otpremnica':   ('#f97316', 'O'),
        'primka':       ('#84cc16', 'P'),
        'otkupni_blok': ('#ec4899', 'B'),
        'cmr':          ('#14b8a6', 'M'),
        'pos_receipt':  ('#a855f7', 'P'),
    }
    color, letter = icon_map.get(entry.source_type, ('#6b7280', '?'))

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
        <rect width="120" height="160" fill="#f8fafc" rx="4"/>
        <rect width="120" height="4" fill="{color}"/>
        <rect x="16" y="24" width="88" height="6" fill="#e2e8f0" rx="3"/>
        <rect x="16" y="36" width="64" height="4" fill="#e2e8f0" rx="2"/>
        <rect x="16" y="48" width="74" height="4" fill="#e2e8f0" rx="2"/>
        <rect x="16" y="60" width="54" height="4" fill="#e2e8f0" rx="2"/>
        <circle cx="60" cy="108" r="24" fill="{color}" opacity="0.15"/>
        <text x="60" y="116" text-anchor="middle" fill="{color}"
              font-size="28" font-family="system-ui,sans-serif" font-weight="700">{letter}</text>
    </svg>'''

    return HttpResponse(svg, content_type='image/svg+xml',
                        headers={'Cache-Control': 'public, max-age=3600'})


# ════════════════════════════════════════════════════════════
# ARHIVA LIST
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_list(request):
    """Arhiva list with HTMX partial rendering, batch operations, and label filter."""

    # ── Batch POST actions ──
    if request.method == 'POST':
        action = request.POST.get('action', '')
        entry_ids = request.POST.getlist('entry_ids[]') or request.POST.getlist('entry_ids')
        company = get_user_company(request)

        if action == 'bulk_label' and entry_ids:
            label_id = request.POST.get('label_id', '')
            if label_id:
                try:
                    label = ArhivaLabel.objects.get(pk=label_id, company=company)
                    entries = ArhivaEntry.objects.filter(pk__in=entry_ids, company=company)
                    for entry in entries:
                        entry.labels.add(label)
                    if request.headers.get('HX-Request'):
                        return JsonResponse({'ok': True, 'message': f'Labela "{label.name}" dodana na {entries.count()} zapisa.'})
                    messages.success(request, f'Labela "{label.name}" dodana na {entries.count()} zapisa.')
                except ArhivaLabel.DoesNotExist:
                    if request.headers.get('HX-Request'):
                        return JsonResponse({'ok': False, 'message': 'Labela ne postoji.'}, status=404)
                    messages.error(request, 'Labela ne postoji.')
            return redirect('documents:arhiva_list')

        elif action == 'bulk_export' and entry_ids:
            # Redirect to bulk download with IDs
            ids_str = ','.join(str(i) for i in entry_ids)
            return redirect(f'/hr/documents/arhiva/bulk-download/?ids={ids_str}')

        elif action == 'bulk_book' and entry_ids:
            entries = ArhivaEntry.objects.filter(pk__in=entry_ids, company=company)
            count = entries.update(is_booked=True)
            if request.headers.get('HX-Request'):
                return JsonResponse({'ok': True, 'message': f'{count} zapisa proknjizeno.'})
            messages.success(request, f'{count} zapisa proknjizeno.')
            return redirect('documents:arhiva_list')

        return redirect('documents:arhiva_list')

    is_superadmin = request.user.is_superuser

    if is_superadmin:
        from companies.models import Company
        from companies.utils import get_managed_companies
        managed = get_managed_companies(request.user)

        if managed.exists() and not request.user.company_memberships.filter(
            is_active=True, is_default=True
        ).first().company.is_platform_owner:
            companies = managed
            qs = ArhivaEntry.objects.select_related('company').filter(
                company__in=managed
            ).exclude(amount=0).order_by('-archived_at')
        else:
            companies = Company.objects.all().order_by('name')
            qs = ArhivaEntry.objects.select_related('company').exclude(amount=0).order_by('-archived_at')

        company_filter = request.GET.get('company', '')
        year_filter = request.GET.get('year', '')
        if company_filter:
            qs = qs.filter(company_id=company_filter)
        if year_filter:
            qs = qs.filter(doc_date__year=year_filter)
    else:
        company = get_user_company(request)
        if not company:
            return render(request, 'documents/arhiva_list.html', {'entries': [], 'is_superadmin': False, 'labels': []})
        # Radnica moze pregledati komitenta iz svog stola
        override_id = request.GET.get('company', '')
        if override_id:
            from accounts.models import CompanyMembership
            has_access = CompanyMembership.objects.filter(
                user=request.user, company_id=override_id, is_active=True
            ).exists()
            if has_access:
                company = Company.objects.filter(pk=override_id).first() or company
        qs = ArhivaEntry.objects.filter(company=company).exclude(amount=0).order_by('-doc_date', '-archived_at')
        company_filter = ''
        companies = []
        year_filter = request.GET.get('year', '')
        if year_filter:
            qs = qs.filter(doc_date__year=year_filter)

    show_all = request.GET.get('all', '') == '1'

    # Filteri
    source_type = request.GET.get('source_type', '')
    q = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    currency = request.GET.get('currency', '')
    has_fiscal = request.GET.get('has_fiscal', '')
    has_file = request.GET.get('has_file', '')

    if source_type:
        qs = qs.filter(source_type=source_type)
    if q:
        qs = qs.filter(Q(doc_number__icontains=q) | Q(partner_name__icontains=q) | Q(barcode__icontains=q))
    if date_from:
        qs = qs.filter(doc_date__gte=date_from)
    if date_to:
        qs = qs.filter(doc_date__lte=date_to)
    if currency:
        qs = qs.filter(currency=currency)
    if has_fiscal == '1':
        qs = qs.exclude(zki='').exclude(zki__isnull=True)
    elif has_fiscal == '0':
        qs = qs.filter(Q(zki='') | Q(zki__isnull=True))
    if has_file == 'pdf':
        qs = qs.filter(has_pdf=True)
    elif has_file == 'xml':
        qs = qs.filter(has_xml=True)
    elif has_file == 'image':
        qs = qs.filter(has_image=True)

    # Label filter
    label_filter = request.GET.get('label', '')
    if label_filter:
        qs = qs.filter(labels__id=label_filter)

    # Hide zero-amount bulk-import entries by default for non-superadmin
    hide_zero = request.GET.get("hide_zero", "")
    if hide_zero == "1" or (hide_zero == "" and not is_superadmin and "hide_zero" not in request.GET):
        qs = qs.exclude(amount=0)

    from django.db.models import Sum, Count, Q as _Q
    stats = qs.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        fiscal_count=Count('id', filter=_Q(zki__isnull=False) & ~_Q(zki='')),
        file_count=Count('id', filter=_Q(has_pdf=True) | _Q(has_xml=True) | _Q(has_image=True)),
    )

    # Bookmark filter
    bookmarked = request.GET.get('bookmarked', '')
    if bookmarked == '1':
        qs = qs.filter(bookmarks__user=request.user)

    # Sorting
    sort = request.GET.get('sort', '')
    order = request.GET.get('order', 'desc')
    SORT_FIELDS = {'date': 'doc_date', 'number': 'doc_number', 'partner': 'partner_name', 'amount': 'amount', 'archived': 'archived_at'}
    if sort in SORT_FIELDS:
        sort_field = SORT_FIELDS[sort]
        if order == 'desc':
            sort_field = '-' + sort_field
        qs = qs.order_by(sort_field)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))

    currencies = ArhivaEntry.objects.values_list('currency', flat=True).distinct().order_by('currency')

    # Labels for current company
    user_company = get_user_company(request)
    labels = ArhivaLabel.objects.filter(company=user_company).order_by('name') if user_company else ArhivaLabel.objects.none()

    # Prefetch labels for entries on this page
    entry_labels = {}
    if page.object_list:
        entry_ids_on_page = [e.id for e in page.object_list]
        labeled_entries = ArhivaEntry.objects.filter(
            id__in=entry_ids_on_page
        ).prefetch_related('labels').only('id')
        for le in labeled_entries:
            entry_labels[le.id] = list(le.labels.all())

    context = {
        'page_obj': page,
        'entries': page,
        'source_types': ArhivaEntry.SOURCE_TYPES,
        'source_type': source_type,
        'q': q,
        'date_from': date_from,
        'date_to': date_to,
        'currency': currency,
        'currencies': currencies,
        'has_fiscal': has_fiscal,
        'has_file': has_file,
        'show_all': show_all,
        'is_superadmin': is_superadmin,
        'companies': companies,
        'company_filter': company_filter,
        'company_filter_name': next((c.name for c in companies if str(c.id) == str(company_filter)), '') if (company_filter and 'companies' in dir()) else '',
        'year_filter': year_filter if is_superadmin else request.GET.get('year', ''),
        'year_filter_val': request.GET.get('year', ''),
        'stats': stats,
        'sort': sort,
        'order': order,
        'bookmarked': bookmarked,
        'hide_zero': hide_zero,
        'bookmarked_ids': set(ArhivaBookmark.objects.filter(
            user=request.user
        ).values_list('entry_id', flat=True)) if request.user.is_authenticated else set(),
        'labels': labels,
        'label_filter': label_filter,
        'entry_labels': entry_labels,
    }

    # HTMX partial rendering — return only the table + pagination
    if request.headers.get('HX-Request'):
        return render(request, 'documents/_arhiva_table_partial.html', context)

    return render(request, 'documents/arhiva_list.html', context)


# ════════════════════════════════════════════════════════════
# UPLOAD
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_upload(request):
    if request.method == 'POST' and request.FILES.get('file'):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Nije moguce odrediti tvrtku.')
            return redirect('documents:arhiva_list')

        uploaded = request.FILES['file']
        source_type = request.POST.get('source_type', 'document')
        backend_name = request.POST.get('backend', '') or None  # Prazan string -> None = auto

        # Odredi backend iz StorageConfig ako postoji
        if backend_name is None:
            try:
                from .models import StorageConfig
                cfg = StorageConfig.objects.get(company=company)
                backend_name = cfg.backend
            except Exception:
                pass

        try:
            file_bytes = uploaded.read()
            result = store_document(
                file_bytes=file_bytes,
                filename=uploaded.name,
                company_id=company.id,
                source_type=source_type,
                backend_name=backend_name,
            )

            # Sprint 2: Smart Upload — OCR partner extraction + fuzzy matching
            partner_name = request.POST.get('partner_name', '').strip()
            matched_partner = None
            ocr_data = {}

            # If image/PDF and no partner_name provided, try FenixScan OCR
            is_image = result.get('content_type', '').startswith('image/')
            is_pdf = uploaded.name.lower().endswith('.pdf')
            if (is_image or is_pdf) and not partner_name:
                try:
                    import base64
                    if is_image and len(file_bytes) < 3_700_000:
                        from core.views_scan import _build_content, _call_anthropic, _parse_json, _post_process
                        b64 = base64.b64encode(file_bytes).decode()
                        content = _build_content([b64], 'invoice')
                        raw = _call_anthropic(content, max_tokens=400)
                        fields = _parse_json(raw)
                        fields = _post_process(fields, 'invoice')
                        ocr_data = fields

                        # Auto-fill from OCR if not manually provided
                        if not partner_name and fields.get('dobavljac'):
                            partner_name = fields['dobavljac']
                        if not request.POST.get('doc_number') and fields.get('broj_racuna'):
                            pass  # Will use below
                        if not request.POST.get('amount') and fields.get('iznos_ukupno'):
                            pass  # Will use below
                        logger.info('arhiva_upload: FenixScan OCR ok, partner=%s, conf=%.2f',
                                    fields.get('dobavljac', '?'), fields.get('confidence', 0))
                except Exception as ocr_err:
                    logger.warning('arhiva_upload: FenixScan OCR failed (non-blocking): %s', ocr_err)

            # Fuzzy match partner
            if partner_name:
                matched_partner, match_score = _fuzzy_match_partner(partner_name, company)
                if matched_partner:
                    logger.info('arhiva_upload: partner matched "%s" -> %s (score=%.2f)',
                                partner_name, matched_partner.name, match_score)

            # Use OCR data as fallback for empty fields
            doc_number = request.POST.get('doc_number', '').strip() or ocr_data.get('broj_racuna', '') or uploaded.name
            amount_raw = request.POST.get('amount', '') or ocr_data.get('iznos_ukupno', 0) or 0
            doc_date = request.POST.get('doc_date') or ocr_data.get('datum', '') or None

            # Kreiraj ArhivaEntry
            entry = ArhivaEntry.objects.create(
                company=company,
                source_type=source_type,
                source_id=result.get('hash', ''),
                doc_number=doc_number,
                partner_name=partner_name or (matched_partner.name if matched_partner else ''),
                partner=matched_partner,
                amount=Decimal(str(amount_raw or 0)),
                currency=request.POST.get('currency', 'EUR'),
                doc_date=doc_date or timezone.now().date(),
                file_path=result['path'],
                has_pdf=uploaded.name.lower().endswith('.pdf'),
                has_xml=uploaded.name.lower().endswith('.xml'),
                has_image=is_image,
                archived_by=request.user,
                session_key=request.session.session_key or '',
            )

            size_kb = result['size'] // 1024
            partner_msg = ''
            if matched_partner:
                partner_msg = ' | Partner: %s' % matched_partner.name
            messages.success(request, 'Datoteka spremljena (%s, %dKB, backend: %s%s)' % (
                uploaded.name, size_kb, result['backend'], partner_msg))

            # Trigeraj AI analizu async
            try:
                from documents.tasks import generate_ai_proposal
                if entry and (entry.has_pdf or entry.has_image):
                    entry.ai_status = 'pending'
                    entry.ai_status_message = 'Čekam AI analizu...'
                    entry.save(update_fields=['ai_status', 'ai_status_message'])
                    generate_ai_proposal.apply_async(
                        args=[entry.pk],
                        countdown=3,
                    )
            except Exception as ai_err:
                logger.warning('arhiva_upload: AI trigger failed: %s', ai_err)

        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            messages.error(request, 'Greska pri uploadu. Provjerite format datoteke.')

        return redirect('documents:arhiva_list')

    return render(request, 'documents/arhiva_upload.html', {
        'source_types': ArhivaEntry.SOURCE_TYPES,
    })


# ════════════════════════════════════════════════════════════
# CSV EXPORT
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_export(request):
    """Export filtered ArhivaEntry to CSV (UTF-8 BOM for Excel)."""
    is_superadmin = request.user.is_superuser

    if is_superadmin:
        qs = ArhivaEntry.objects.select_related('company').all()
        company_filter = request.GET.get('company', '')
        if company_filter:
            qs = qs.filter(company_id=company_filter)
    else:
        company = get_user_company(request)
        if not company:
            return HttpResponse('No company', status=400)
        qs = ArhivaEntry.objects.filter(company=company)

    # Apply same filters as list view
    source_type = request.GET.get('source_type', '')
    q = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    currency = request.GET.get('currency', '')
    has_fiscal = request.GET.get('has_fiscal', '')
    has_file = request.GET.get('has_file', '')
    bookmarked = request.GET.get('bookmarked', '')

    if source_type:
        qs = qs.filter(source_type=source_type)
    if q:
        qs = qs.filter(Q(doc_number__icontains=q) | Q(partner_name__icontains=q))
    if date_from:
        qs = qs.filter(doc_date__gte=date_from)
    if date_to:
        qs = qs.filter(doc_date__lte=date_to)
    if currency:
        qs = qs.filter(currency=currency)
    if has_fiscal == '1':
        qs = qs.exclude(zki='').exclude(zki__isnull=True)
    elif has_fiscal == '0':
        qs = qs.filter(Q(zki='') | Q(zki__isnull=True))
    if has_file == 'pdf':
        qs = qs.filter(has_pdf=True)
    elif has_file == 'xml':
        qs = qs.filter(has_xml=True)
    elif has_file == 'image':
        qs = qs.filter(has_image=True)
    if bookmarked == '1':
        qs = qs.filter(bookmarks__user=request.user)

    qs = qs.order_by('-doc_date')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="arhiva_export_%s.csv"' % date.today().isoformat()
    response.write('\ufeff')  # UTF-8 BOM

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Datum', 'Tvrtka', 'Tip', 'Broj dokumenta', 'Partner', 'Iznos', 'Valuta', 'ZKI', 'JIR', 'PDF', 'XML', 'Slika', 'Arhivirano'])

    for e in qs[:5000]:  # Max 5000 rows
        writer.writerow([
            e.doc_date.strftime('%d.%m.%Y') if e.doc_date else '',
            e.company.name if e.company else '',
            e.get_source_type_display(),
            e.doc_number,
            e.partner_name or '',
            str(e.amount).replace('.', ','),
            e.currency,
            e.zki or '',
            e.jir or '',
            'Da' if e.has_pdf else 'Ne',
            'Da' if e.has_xml else 'Ne',
            'Da' if e.has_image else 'Ne',
            e.archived_at.strftime('%d.%m.%Y %H:%M') if e.archived_at else '',
        ])

    return response


# ════════════════════════════════════════════════════════════
# BULK ZIP DOWNLOAD
# ════════════════════════════════════════════════════════════

@login_required
@require_POST
def arhiva_bulk_download(request):
    """Download multiple archive files as ZIP."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not ids:
        return JsonResponse({'error': 'No IDs provided'}, status=400)
    if len(ids) > 50:
        return JsonResponse({'error': 'Max 50 files per download'}, status=400)

    is_superadmin = request.user.is_superuser
    if is_superadmin:
        entries = ArhivaEntry.objects.filter(id__in=ids)
    else:
        company = get_user_company(request)
        entries = ArhivaEntry.objects.filter(id__in=ids, company=company)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        added = 0
        for entry in entries:
            if not entry.file_path:
                continue
            full_path = os.path.join(settings.MEDIA_ROOT, entry.file_path)
            if os.path.exists(full_path):
                arcname = '%s_%s' % (entry.doc_number or 'doc', os.path.basename(entry.file_path))
                arcname = arcname.replace('/', '_').replace('\\', '_')
                zf.write(full_path, arcname)
                added += 1

    if added == 0:
        return JsonResponse({'error': 'No files found'}, status=404)

    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="arhiva_%s_%d_files.zip"' % (date.today().isoformat(), added)
    return response


# ════════════════════════════════════════════════════════════
# BOOKMARK TOGGLE
# ════════════════════════════════════════════════════════════

@login_required
@require_POST
def arhiva_toggle_bookmark(request, pk):
    """Toggle bookmark on an ArhivaEntry."""
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    # Company isolation
    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return JsonResponse({'error': 'Forbidden'}, status=403)

    bookmark, created = ArhivaBookmark.objects.get_or_create(
        user=request.user, entry=entry
    )
    if not created:
        bookmark.delete()

    return JsonResponse({
        'bookmarked': created,
        'entry_id': pk,
    })


# ════════════════════════════════════════════════════════════
# DETAIL AJAX — Drawer content
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_detail_ajax(request, pk):
    """Return ArhivaEntry detail as JSON for drawer."""
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return JsonResponse({'error': 'Forbidden'}, status=403)

    result = {
        'id': entry.id,
        'doc_number': entry.doc_number,
        'source_type': entry.source_type,
        'source_type_display': entry.get_source_type_display(),
        'partner_name': entry.partner_name or '',
        'amount': str(entry.amount),
        'currency': entry.currency,
        'doc_date': entry.doc_date.strftime('%d.%m.%Y') if entry.doc_date else '',
        'zki': entry.zki or '',
        'jir': entry.jir or '',
        'has_pdf': entry.has_pdf,
        'has_xml': entry.has_xml,
        'has_image': entry.has_image,
        'barcode': entry.barcode or '',
        'file_path': entry.file_path or '',
        'archived_at': entry.archived_at.strftime('%d.%m.%Y %H:%M') if entry.archived_at else '',
        'company_name': entry.company.name if entry.company else '',
        'items': [],
        'module_url': '',
    }

    # Try to fetch line items from source module
    try:
        if entry.source_type == 'invoice_out' and entry.source_id:
            sid = entry.source_id.replace('invoice:', '')
            from invoicing.models import Invoice
            inv = Invoice.objects.filter(pk=sid).first()
            if not inv:
                inv = Invoice.objects.filter(number=entry.doc_number, company=entry.company).first()
            if inv:
                result['module_url'] = '/hr/invoicing/%s/' % inv.pk
                result['extra'] = {
                    'status': inv.status if hasattr(inv, 'status') else '',
                    'payment_method': inv.payment_method if hasattr(inv, 'payment_method') else '',
                    'invoice_type': inv.get_invoice_type_display() if hasattr(inv, 'invoice_type') else '',
                    'tax_classification': inv.tax_classification if hasattr(inv, 'tax_classification') else '',
                }
                for item in inv.items.all():
                    result['items'].append({
                        'name': item.description if hasattr(item, 'description') else str(item),
                        'qty': str(item.quantity) if hasattr(item, 'quantity') else '',
                        'unit': item.unit if hasattr(item, 'unit') else '',
                        'price': str(item.unit_price) if hasattr(item, 'unit_price') else '',
                        'vat': str(item.vat_rate) if hasattr(item, 'vat_rate') else '',
                        'total': str(item.total) if hasattr(item, 'total') else '',
                    })
        elif entry.source_type in ('primka', 'otpremnica', 'otkupni', 'cmr'):
            model_map = {
                'primka': ('Primka', 'primka'),
                'otpremnica': ('Otpremnica', 'otpremnica'),
                'otkupni': ('OtkupniBlok', 'otkupni'),
                'cmr': ('CMR', 'cmr'),
            }
            model_name, url_prefix = model_map[entry.source_type]
            from documents import models as doc_models
            model_cls = getattr(doc_models, model_name, None)
            if model_cls:
                doc = model_cls.objects.filter(doc_number=entry.doc_number, company=entry.company).first()
                if doc:
                    result['module_url'] = '/hr/documents/%s/%s/' % (url_prefix, doc.pk)
                    for item in doc.items.all():
                        result['items'].append({
                            'name': item.product_name if hasattr(item, 'product_name') else str(item),
                            'qty': str(item.quantity) if hasattr(item, 'quantity') else '',
                            'unit': item.unit if hasattr(item, 'unit') else '',
                            'price': str(item.unit_price) if hasattr(item, 'unit_price') else '',
                            'vat': str(item.vat_rate) if hasattr(item, 'vat_rate') else '25',
                            'total': str(item.total_price) if hasattr(item, 'total_price') else '',
                        })
    except Exception as e:
        result['items_error'] = str(e)

    # Email tracking (Sprint 2A)
    result['email_sent_at'] = entry.email_sent_at.strftime('%d.%m.%Y %H:%M') if entry.email_sent_at else None
    result['email_sent_to'] = entry.email_sent_to or ''
    result['email_opened_at'] = entry.email_opened_at.strftime('%d.%m.%Y %H:%M') if entry.email_opened_at else None
    result['email_open_count'] = entry.email_open_count or 0
    result['source_id'] = entry.source_id or ''

    # AI Bookkeeper proposal
    result['ai_proposal'] = entry.ai_proposal
    result['is_booked'] = entry.is_booked
    result['ai_status'] = entry.ai_status
    result['ai_status_message'] = entry.ai_status_message or ''

    # Deep links (Sprint 2C)
    if not result['module_url']:
        sid = (entry.source_id or '').replace('invoice:', '')
        if entry.source_type == 'invoice_out' and sid:
            result['module_url'] = f'/invoicing/{sid}/'
        elif entry.source_type == 'pos_receipt' and sid:
            result['module_url'] = f'/pos/receipt/{sid}/'
        elif entry.source_type == 'eracun' and sid:
            result['module_url'] = f'/einvoice/message/{sid}/'

    # Kontakt podaci komitenta (za slanje)
    result['company_phone'] = entry.company.phone if entry.company else ''
    result['company_email'] = entry.company.email if entry.company else ''

    # Download URL
    result['download_url'] = f'/hr/documents/arhiva/{entry.pk}/download/'

    # Bookmark status
    result['bookmarked'] = ArhivaBookmark.objects.filter(user=request.user, entry=entry).exists()

    return JsonResponse(result)


@login_required
def arhiva_barcode_png(request, pk):
    """Generiraj Code128 barcode kao PNG."""
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)
    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()

    code_value = entry.barcode or str(entry.id)
    try:
        import barcode
        from barcode.writer import ImageWriter
        buf = io.BytesIO()
        code = barcode.get('code128', code_value, writer=ImageWriter())
        code.write(buf, options={'write_text': True, 'module_height': 10, 'font_size': 8, 'text_distance': 3})
        return HttpResponse(buf.getvalue(), content_type='image/png')
    except Exception:
        try:
            import qrcode
            qr = qrcode.make(code_value)
            buf = io.BytesIO()
            qr.save(buf, format='PNG')
            return HttpResponse(buf.getvalue(), content_type='image/png')
        except Exception:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound()


# ════════════════════════════════════════════════════════════
# FILE SERVE
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_file_serve(request, file_path):
    """Serve a file from MEDIA_ROOT."""
    # Security: prevent path traversal + symlink escape
    clean_path = os.path.normpath(file_path)
    if clean_path.startswith('..') or clean_path.startswith('/'):
        return HttpResponse('Invalid path', status=400)

    full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
    real_path = os.path.realpath(full_path)
    media_real = os.path.realpath(settings.MEDIA_ROOT)
    if not real_path.startswith(media_real + os.sep):
        return HttpResponse('Invalid path', status=400)

    if not os.path.exists(real_path):
        return HttpResponse('File not found', status=404)

    content_type, _ = mimetypes.guess_type(real_path)
    if not content_type:
        content_type = 'application/octet-stream'

    with open(real_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
    response['Content-Disposition'] = 'inline; filename="%s"' % os.path.basename(real_path)
    return response


@login_required
def arhiva_download(request, pk):
    """Download pojedinacan fajl iz ArhivaEntry."""
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            raise Http404

    # Try file_path first
    if entry.file_path:
        full_path = entry.file_path
        if not os.path.isabs(full_path):
            full_path = os.path.join('/var/www/fina-connect', full_path)
        if os.path.exists(full_path):
            return FileResponse(
                open(full_path, 'rb'),
                as_attachment=True,
                filename=os.path.basename(full_path),
            )

    # Try to find source file from Invoice
    if entry.source_type == 'invoice_out' and entry.source_id:
        from invoicing.models import Invoice
        sid = entry.source_id.replace('invoice:', '')
        inv = Invoice.objects.filter(pk=sid).first()
        if inv and hasattr(inv, 'pdf_file') and inv.pdf_file:
            return FileResponse(inv.pdf_file, as_attachment=True, filename=f'{inv.number}.pdf')

    # Try DocumentBlob
    blob = DocumentBlob.objects.filter(
        company=entry.company,
        source_type=entry.source_type,
    ).first()
    if blob:
        response = HttpResponse(blob.file_data, content_type=blob.content_type)
        response['Content-Disposition'] = f'attachment; filename="{blob.filename}"'
        return response

    raise Http404


# ════════════════════════════════════════════════════════════
# PREVIEW & THUMBNAIL
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_thumbnail(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/thumbnail/
    Vrati thumbnail JPG za ArhivaEntry.
    """
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return HttpResponse(status=403)

    thumb_path = _get_thumbnail_path(entry)

    # Cache hit
    if os.path.exists(thumb_path):
        return FileResponse(open(thumb_path, 'rb'), content_type='image/jpeg')

    # Cache miss — generiraj
    if entry.file_path:
        full_path = os.path.join(settings.MEDIA_ROOT, entry.file_path)
        if os.path.exists(full_path):
            if _generate_thumbnail(entry, full_path, thumb_path):
                return FileResponse(open(thumb_path, 'rb'), content_type='image/jpeg')

    # Za invoice_out bez file_path — generiraj PDF on-the-fly i uzmi thumbnail
    if entry.source_type == 'invoice_out' and entry.source_id:
        try:
            from invoicing.models import Invoice
            from invoicing.services.pdf_service import generate_invoice_pdf
            import tempfile

            inv = None
            sid = entry.source_id or ''
            if sid.startswith('invoice:'):
                try:
                    inv = Invoice.objects.filter(pk=int(sid.replace('invoice:', ''))).first()
                except (ValueError, TypeError):
                    pass
            if not inv:
                inv = Invoice.objects.filter(
                    number=entry.doc_number, company=entry.company
                ).first()

            if inv:
                pdf_content, _ = generate_invoice_pdf(inv)
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(pdf_content if isinstance(pdf_content, bytes) else pdf_content.read())
                    tmp_path = tmp.name

                success = _generate_thumbnail(entry, tmp_path, thumb_path)
                os.unlink(tmp_path)

                if success:
                    return FileResponse(open(thumb_path, 'rb'), content_type='image/jpeg')
        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            logger.warning(f'Invoice thumbnail greska: {e}')

    # Fallback — SVG placeholder
    return _thumbnail_placeholder(entry)


@login_required
def arhiva_preview(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/preview/
    Vrati PDF za inline pregled.
    """
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return HttpResponse('Zabranjeno', status=403)

    # 1. Ima file_path — serviraj direktno
    if entry.file_path:
        full_path = os.path.join(settings.MEDIA_ROOT, entry.file_path)
        if os.path.exists(full_path):
            ext = os.path.splitext(full_path)[1].lower()

            if entry.has_pdf or ext == '.pdf':
                return FileResponse(
                    open(full_path, 'rb'),
                    content_type='application/pdf',
                    headers={'Content-Disposition': f'inline; filename="{entry.doc_number}.pdf"'}
                )
            elif entry.has_image or ext in ('.jpg', '.jpeg', '.png', '.webp'):
                ct, _ = mimetypes.guess_type(full_path)
                return FileResponse(
                    open(full_path, 'rb'),
                    content_type=ct or 'image/jpeg',
                    headers={'Content-Disposition': 'inline'}
                )

    # 2. Invoice bez file_path — generiraj on-the-fly
    if entry.source_type == 'invoice_out' and entry.source_id:
        try:
            from invoicing.models import Invoice
            from invoicing.services.pdf_service import generate_invoice_pdf

            inv = None
            sid = entry.source_id or ''
            if sid.startswith('invoice:'):
                try:
                    inv = Invoice.objects.filter(pk=int(sid.replace('invoice:', ''))).first()
                except (ValueError, TypeError):
                    pass
            if not inv:
                inv = Invoice.objects.filter(
                    number=entry.doc_number, company=entry.company
                ).first()

            if inv:
                pdf_content, mime = generate_invoice_pdf(inv)
                if isinstance(pdf_content, bytes):
                    data = pdf_content
                else:
                    data = pdf_content.read()

                resp = HttpResponse(data, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="racun_{inv.number}.pdf"'
                resp['Cache-Control'] = 'private, max-age=300'
                return resp

        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            logger.error(f'Invoice preview greska: {e}')

    # 3. Nema nista
    return HttpResponse(
        '<html><body style="font-family:sans-serif;text-align:center;padding:3rem;color:#94a3b8">'
        '<p style="font-size:3rem">&#128196;</p>'
        '<p>Pregled nije dostupan za ovaj tip dokumenta.</p>'
        '</body></html>',
        content_type='text/html',
        status=404
    )


@login_required
def arhiva_preview_info(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/preview-info/
    JSON endpoint koji vraca preview_url i thumbnail_url.
    """
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return JsonResponse({'error': 'Forbidden'}, status=403)

    has_preview = bool(
        entry.file_path or
        (entry.source_type == 'invoice_out' and entry.source_id)
    )

    return JsonResponse({
        'has_preview': has_preview,
        'preview_url': f'/hr/documents/arhiva/{pk}/preview/' if has_preview else None,
        'thumbnail_url': f'/hr/documents/arhiva/{pk}/thumbnail/',
        'file_type': (
            'pdf' if entry.has_pdf else
            'image' if entry.has_image else
            'xml' if entry.has_xml else
            'invoice' if entry.source_type == 'invoice_out' else
            'unknown'
        ),
    })


# ════════════════════════════════════════════════════════════
# PDF & XML DOWNLOAD
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_download_pdf(request, pk):
    """Generiraj i preuzmi PDF za ArhivaEntry."""
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa

    company = get_user_company(request)
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser and entry.company != company:
        raise Http404

    html = render_to_string('documents/arhiva_pdf.html', {
        'entry': entry,
        'company': entry.company,
    })

    result = io.BytesIO()
    pdf = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result, encoding='utf-8')
    if pdf.err:
        return HttpResponse('Greska pri generiranju PDF-a.', status=500)

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    safe_num = (entry.doc_number or 'dokument').replace('/', '-').replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="arhiva_{safe_num}.pdf"'
    return response


@login_required
def arhiva_download_xml(request, pk):
    """Generiraj i preuzmi XML za ArhivaEntry."""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom.minidom import parseString

    company = get_user_company(request)
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser and entry.company != company:
        raise Http404

    root = Element('ArhivaEntry')
    root.set('xmlns', 'urn:limit-connect:arhiva:1.0')

    SubElement(root, 'ArchiveNumber').text = entry.archive_number or ''
    SubElement(root, 'DocumentNumber').text = entry.doc_number or ''
    SubElement(root, 'SourceType').text = entry.source_type or ''
    SubElement(root, 'SourceTypeDisplay').text = entry.get_source_type_display() or ''
    SubElement(root, 'PartnerName').text = entry.partner_name or ''
    SubElement(root, 'Amount').text = str(entry.amount or 0)
    SubElement(root, 'Currency').text = entry.currency or 'EUR'
    SubElement(root, 'DocumentDate').text = str(entry.doc_date or '')
    SubElement(root, 'ArchivedAt').text = str(entry.archived_at or '')

    if entry.zki:
        SubElement(root, 'ZKI').text = entry.zki
    if entry.jir:
        SubElement(root, 'JIR').text = entry.jir

    company_el = SubElement(root, 'Company')
    SubElement(company_el, 'Name').text = entry.company.name or ''
    SubElement(company_el, 'OIB').text = entry.company.oib or ''
    SubElement(company_el, 'Address').text = entry.company.address or ''
    SubElement(company_el, 'City').text = entry.company.city or ''

    SubElement(root, 'IntegrityHash').text = entry.integrity_hash or ''

    if entry.file_path:
        SubElement(root, 'FilePath').text = entry.file_path

    # Pretty print
    raw_xml = tostring(root, encoding='unicode')
    pretty = parseString(raw_xml).toprettyxml(indent='  ', encoding='UTF-8')

    response = HttpResponse(pretty, content_type='application/xml; charset=utf-8')
    safe_num = (entry.doc_number or 'dokument').replace('/', '-').replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="arhiva_{safe_num}.xml"'
    return response


# ════════════════════════════════════════════════════════════
# AUTOCOMPLETE
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_autocomplete(request):
    """JSON autocomplete za arhiva pretragu. Max 8 rezultata."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    company = get_user_company(request)
    if request.user.is_superuser:
        qs = ArhivaEntry.objects.all()
    elif company:
        qs = ArhivaEntry.objects.filter(company=company)
    else:
        return JsonResponse({'results': []})

    matches = qs.filter(
        Q(partner_name__icontains=q) |
        Q(doc_number__icontains=q) |
        Q(archive_number__icontains=q)
    ).values(
        'id', 'partner_name', 'doc_number', 'archive_number', 'amount', 'source_type'
    ).order_by('-archived_at')[:8]

    results = []
    for m in matches:
        # Determine which field matched for label
        if q.lower() in (m['partner_name'] or '').lower():
            label = m['partner_name']
            rtype = 'partner'
        elif q.lower() in (m['doc_number'] or '').lower():
            label = m['doc_number']
            rtype = 'document'
        else:
            label = m['archive_number']
            rtype = 'archive'

        results.append({
            'label': label,
            'value': m['partner_name'] or m['doc_number'] or m['archive_number'],
            'type': rtype,
            'amount': float(m['amount']) if m['amount'] else 0,
            'source_type': m['source_type'],
            'id': m['id'],
        })

    return JsonResponse({'results': results})


# ════════════════════════════════════════════════════════════
# DELETE ENTRY
# ════════════════════════════════════════════════════════════

@login_required
@require_POST
def arhiva_delete_entry(request, pk):
    """AJAX: Obrisi arhivski zapis. Instant delete bez refresha."""
    company = get_user_company(request)
    try:
        entry = ArhivaEntry.objects.get(pk=pk)
        # Provjera prava
        if not request.user.is_superuser and entry.company != company:
            return JsonResponse({'ok': False, 'error': 'Nemas pravo'}, status=403)
        # Zastita od brisanja fiskaliziranih
        if entry.jir and entry.jir.strip():
            return JsonResponse({'ok': False, 'error': 'Fiskalizirani racun se ne moze obrisati'}, status=400)
        entry.delete()
        return JsonResponse({'ok': True})
    except ArhivaEntry.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Zapis ne postoji'}, status=404)


# ════════════════════════════════════════════════════════════
# BLOB SERVE
# ════════════════════════════════════════════════════════════

@login_required
def blob_serve(request, blob_id):
    blob = get_object_or_404(DocumentBlob, id=blob_id)
    response = HttpResponse(blob.file_data, content_type=blob.content_type)
    response['Content-Disposition'] = 'inline; filename="%s"' % blob.filename
    return response


# ════════════════════════════════════════════════════════════
# LIST JSON
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_list_json(request):
    """JSON API za lazy load arhiva liste."""
    company = get_user_company(request)
    if request.user.is_superuser:
        qs = ArhivaEntry.objects.select_related('company').all()
        company_filter = request.GET.get('company', '')
        if company_filter:
            qs = qs.filter(company_id=company_filter)
    elif company:
        qs = ArhivaEntry.objects.filter(company=company)
    else:
        return JsonResponse({'entries': [], 'has_next': False})

    # Filteri
    q = request.GET.get('q', '')
    source_type = request.GET.get('source_type', '')
    if q:
        qs = qs.filter(Q(doc_number__icontains=q) | Q(partner_name__icontains=q))
    if source_type:
        qs = qs.filter(source_type=source_type)

    qs = qs.order_by('-archived_at')

    page = int(request.GET.get('page', 1))
    per_page = 50
    entries = qs[(page-1)*per_page : page*per_page]
    has_next = qs.count() > page * per_page

    data = []
    for e in entries:
        data.append({
            'id': e.pk,
            'company': str(e.company) if hasattr(e, 'company') else '',
            'doc_number': e.doc_number,
            'partner_name': e.partner_name,
            'amount': float(e.amount) if e.amount else 0,
            'currency': e.currency,
            'doc_date': e.doc_date.isoformat() if e.doc_date else None,
            'source_type': e.source_type,
            'has_pdf': e.has_pdf,
            'has_xml': e.has_xml,
            'is_booked': e.is_booked,
            'zki': e.zki or '',
            'jir': e.jir or '',
            'email_sent_at': e.email_sent_at.strftime('%d.%m.%Y %H:%M') if e.email_sent_at else None,
            'email_opened_at': e.email_opened_at.strftime('%d.%m.%Y %H:%M') if e.email_opened_at else None,
            'source_id': e.source_id or '',
            'ai_proposal': bool(e.ai_proposal),
        })

    return JsonResponse({'entries': data, 'has_next': has_next, 'page': page})


# ════════════════════════════════════════════════════════════
# AI Bookkeeper — Proknjizi endpoint (Sprint 2C)
# ════════════════════════════════════════════════════════════

@require_POST
@login_required
def arhiva_proknjizi(request, pk):
    """Proknjiži ArhivaEntry koristeći AI bookkeeper. Podržava dry_run."""
    from documents.models import ArhivaEntry
    company = get_user_company(request)

    try:
        entry = ArhivaEntry.objects.get(pk=pk, company=company)
    except ArhivaEntry.DoesNotExist:
        return JsonResponse({'error': 'Zapis nije pronađen'}, status=404)

    if entry.is_booked:
        return JsonResponse({'error': 'Već proknjiženo'}, status=409)

    # dry_run mode — return proposal without committing
    import json
    dry_run = request.POST.get('dry_run', '0') == '1'

    from konto.ai_bookkeeper import process_archive_entry

    if dry_run:
        # Just generate/return proposal without booking
        from konto.ai_bookkeeper import propose_booking
        proposal = propose_booking(entry)
        return JsonResponse({'ok': True, 'dry_run': True, 'proposal': proposal})

    result = process_archive_entry(pk, auto_commit=True)

    if result.get('status') == 'auto_booked':
        # Log audit
        from documents.models import log_arhiva_action, ArhivaAuditLog
        log_arhiva_action(entry, ArhivaAuditLog.Action.BOOKED, user=request.user, request=request)

        return JsonResponse({
            'ok': True,
            'status': 'booked',
            'journal_entry_id': result.get('journal_entry_id'),
            'proposal': result.get('proposal'),
        })
    elif result.get('status') == 'pending_review':
        return JsonResponse({
            'ok': True,
            'status': 'pending_review',
            'proposal': result.get('proposal'),
            'message': 'Pouzdanost preniska za auto-knjiženje. Prijedlog spremljen za pregled.',
        })
    elif result.get('status') == 'already_booked':
        return JsonResponse({'error': 'Već proknjiženo'}, status=409)
    else:
        return JsonResponse({
            'error': f"Knjiženje neuspješno: {result.get('status', 'unknown')}",
        }, status=400)


# ════════════════════════════════════════════════════════════
# SPREMI NA DISK — Strukturirani ZIP za lokalni/mrezni disk
# Za korisnike koji koriste Synesis i trebaju samo arhivu
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_save_to_disk(request):
    """
    GET: Download SVE dokumente za firmu kao strukturirani ZIP.
    Struktura: Firma/Godina/Mjesec/Partner/racun.ext
    Plus CSV index kompatibilan s Exceom.
    
    Query params:
      ?year=2026         — samo ta godina (default: tekuca)
      ?month=3           — samo taj mjesec
      ?source_type=...   — filter po tipu
    """
    company = get_user_company(request)
    if not company:
        return HttpResponse('Nema aktivne tvrtke', status=400)

    year = request.GET.get('year', str(date.today().year))
    month = request.GET.get('month', '')
    source_type = request.GET.get('source_type', '')

    qs = ArhivaEntry.objects.filter(company=company).order_by('doc_date', 'partner_name')

    if year:
        qs = qs.filter(doc_date__year=int(year))
    if month:
        qs = qs.filter(doc_date__month=int(month))
    if source_type:
        qs = qs.filter(source_type=source_type)

    entries = list(qs[:2000])  # Limit za sigurnost

    if not entries:
        messages.warning(request, 'Nema dokumenata za odabrani period.')
        return redirect('documents:arhiva_list')

    buf = io.BytesIO()
    company_safe = company.name.replace('/', '-').replace('\\', '-')[:40]

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # CSV INDEX (Excel-kompatibilan)
        csv_buf = io.StringIO()
        csv_buf.write('\ufeff')  # BOM za Excel
        writer = csv.writer(csv_buf, delimiter=';')
        writer.writerow([
            'R.br.', 'Datum', 'Tip', 'Broj dokumenta', 'Partner',
            'Iznos', 'Valuta', 'ZKI', 'JIR', 'Datoteka', 'Arhivski broj'
        ])

        added_files = 0
        for idx, e in enumerate(entries, 1):
            # Odredi putanju u ZIP-u
            yr = e.doc_date.strftime('%Y') if e.doc_date else 'Nepoznato'
            mo = e.doc_date.strftime('%m-%B') if e.doc_date else '00'
            # Hrvatski nazivi mjeseci
            mo_names = {
                '01': '01-Sijecanj', '02': '02-Veljaca', '03': '03-Ozujak',
                '04': '04-Travanj', '05': '05-Svibanj', '06': '06-Lipanj',
                '07': '07-Srpanj', '08': '08-Kolovoz', '09': '09-Rujan',
                '10': '10-Listopad', '11': '11-Studeni', '12': '12-Prosinac',
            }
            mo_key = e.doc_date.strftime('%m') if e.doc_date else '00'
            mo = mo_names.get(mo_key, mo_key)

            partner_safe = (e.partner_name or 'Nepoznat').replace('/', '-').replace('\\', '-')[:30]
            type_safe = e.get_source_type_display().replace('/', '-')[:20]

            # Putanja: Firma/2026/03-Ozujak/INA_d.d./racun_123.pdf
            folder = '%s/%s/%s/%s' % (company_safe, yr, mo, partner_safe)

            file_in_zip = None
            if e.file_path:
                full_path = os.path.join(settings.MEDIA_ROOT, e.file_path)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(full_path)[1] or '.bin'
                    safe_num = (e.doc_number or 'dok').replace('/', '-').replace('\\', '-')[:40]
                    file_in_zip = '%s/%s_%s%s' % (folder, type_safe, safe_num, ext)
                    zf.write(full_path, file_in_zip)
                    added_files += 1

            writer.writerow([
                idx,
                e.doc_date.strftime('%d.%m.%Y') if e.doc_date else '',
                e.get_source_type_display(),
                e.doc_number or '',
                e.partner_name or '',
                str(e.amount).replace('.', ','),
                e.currency,
                e.zki or '',
                e.jir or '',
                file_in_zip or '(nema datoteke)',
                e.archive_number or '',
            ])

        # Spremi CSV index
        zf.writestr(
            '%s/INDEX_%s.csv' % (company_safe, year),
            csv_buf.getvalue()
        )

        # README
        zf.writestr('%s/PROCITAJ.txt' % company_safe,
            'DIGITALNA ARHIVA RACUNA\n'
            '=======================\n\n'
            'Tvrtka: %s\n'
            'OIB: %s\n'
            'Period: %s\n'
            'Dokumenata: %d\n'
            'Datoteka: %d\n\n'
            'Struktura mapa:\n'
            '  Firma / Godina / Mjesec / Partner / racun.pdf\n\n'
            'INDEX_%s.csv sadrzi popis svih dokumenata.\n'
            'Otvorite ga u Excelu za pretragu.\n\n'
            'Zakonska obaveza cuvanja: 11 godina\n'
            '(Zakon o racunovodstvu, cl. 10)\n\n'
            'Generirano: %s\n'
            'Sustav: Digitalna Arhiva\n' % (
                company.name,
                getattr(company, 'oib', '') or '',
                year,
                len(entries),
                added_files,
                year,
                date.today().strftime('%d.%m.%Y %H:%M'),
            )
        )

    buf.seek(0)
    filename = 'Arhiva_%s_%s.zip' % (company_safe, year)
    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def arhiva_upute_koristenje(request):
    """Printable upute za koristenje — jedna A4 stranica."""
    return render(request, 'documents/arhiva_upute_koristenje.html')


# ================================================================
# MOJI KOMITENTI — radnica vidi svoje firme sa dugmetom Skeniraj/Arhiva
# ================================================================

@login_required
def moji_komitenti(request):
    """Radnica vidi listu svojih komitenata iz stola."""
    from companies.models import Company, KonjikStol
    from accounts.models import CompanyMembership
    from documents.models import ArhivaEntry
    from django.db.models import Count, Q

    company = get_user_company(request)

    # Pronadji stol radnice
    stol = KonjikStol.objects.filter(
        referent=request.user, ured=company, aktivan=True
    ).first()

    # Komitenti iz stola, ili iz membershipa ako nema stola
    if stol:
        komitenti_qs = stol.komitenti.all().order_by('name')
        stol_naziv = stol.naziv or 'Stol %d' % stol.broj
    else:
        # Fallback: sve firme iz membershipa osim matice
        mem_ids = CompanyMembership.objects.filter(
            user=request.user, is_active=True
        ).exclude(company=company).values_list('company_id', flat=True)
        komitenti_qs = Company.objects.filter(id__in=mem_ids).order_by('name')
        stol_naziv = 'Bez stola'

    # Dodaj statistike po komitentu
    komitenti = []
    total_entries = 0
    pending_entries = 0
    for k in komitenti_qs:
        stats = ArhivaEntry.objects.filter(company=k).aggregate(
            entry_count=Count('id'),
            pending_count=Count('id', filter=Q(is_booked=False) & ~Q(ai_proposal__isnull=True) & ~Q(ai_proposal={}))
        )
        k.entry_count = stats['entry_count'] or 0
        k.pending_count = stats['pending_count'] or 0
        total_entries += k.entry_count
        pending_entries += k.pending_count
        komitenti.append(k)

    return render(request, 'documents/moji_komitenti.html', {
        'komitenti': komitenti,
        'stol_naziv': stol_naziv,
        'total_entries': total_entries,
        'pending_entries': pending_entries,
    })


# ══════════════════════════════════════════════════════════════
# POŠALJI KOMITENTU — ručno slanje (WhatsApp / Email)
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def arhiva_send_komitent(request, pk):
    """Ručno pošalji arhivski dokument komitentu putem WhatsApp ili Email."""
    import json as _json

    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)
    company = get_user_company(request)
    if not request.user.is_superuser and entry.company != company:
        return JsonResponse({'error': 'Nemate pristup.'}, status=403)

    try:
        data = _json.loads(request.body)
    except (ValueError, _json.JSONDecodeError):
        data = {}

    channel = data.get('channel', 'email')  # 'email' ili 'whatsapp'
    recipient = data.get('recipient', '').strip()
    save_contact = data.get('save_contact', True)  # spremi u bazu po defaultu

    if not recipient:
        return JsonResponse({'error': 'Unesite primatelja.'}, status=400)

    # Spremi kontakt podatak na firmu komitenta za buduće slanje
    if save_contact and entry.company:
        update_fields = []
        if channel == 'whatsapp' and recipient != (entry.company.phone or ''):
            entry.company.phone = recipient
            update_fields.append('phone')
        elif channel == 'email' and recipient != (entry.company.email or ''):
            entry.company.email = recipient
            update_fields.append('email')
        if update_fields:
            entry.company.save(update_fields=update_fields)

    subject = f'Dokument {entry.doc_number} — {entry.company.name}'
    body_lines = [
        f'Poštovani,',
        f'',
        f'U prilogu je dokument iz vaše arhive:',
        f'• Broj: {entry.doc_number}',
        f'• Vrsta: {entry.get_source_type_display()}',
        f'• Partner: {entry.partner_name or "—"}',
        f'• Iznos: {entry.amount} {entry.currency}',
        f'• Datum: {entry.doc_date.strftime("%d.%m.%Y") if entry.doc_date else "—"}',
        f'',
        f'Pozdrav,',
        f'{request.user.get_full_name() or request.user.username}',
        f'{entry.company.name}',
    ]
    body = '\n'.join(body_lines)

    if channel == 'whatsapp':
        from core.whatsapp import send_text
        result = send_text(recipient, body)
        if result.get('success'):
            from django.utils import timezone
            entry.email_sent_at = timezone.now()
            entry.email_sent_to = f'WhatsApp: {recipient}'
            entry.save(update_fields=['email_sent_at', 'email_sent_to'])
            return JsonResponse({'ok': True, 'message': f'Poslano na WhatsApp: {recipient}'})
        return JsonResponse({'error': result.get('error', 'Greška pri slanju.')}, status=500)

    elif channel == 'email':
        try:
            from core.email_tasks import send_email_task
            send_email_task.delay(
                subject=subject,
                message=body,
                from_email=None,
                recipient_list=[recipient],
            )
            from django.utils import timezone
            entry.email_sent_at = timezone.now()
            entry.email_sent_to = recipient
            entry.save(update_fields=['email_sent_at', 'email_sent_to'])
            return JsonResponse({'ok': True, 'message': f'Email poslan na: {recipient}'})
        except Exception as e:
            return JsonResponse({'error': str(e)[:200]}, status=500)

    return JsonResponse({'error': 'Nepoznat kanal. Koristite "email" ili "whatsapp".'}, status=400)
