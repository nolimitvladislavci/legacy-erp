import os
from django.utils import timezone
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from core.company_utils import get_user_company
from partners.models import Partner

from .models import Document
from .serializers import DocumentSerializer


@login_required
def document_list(request):
    # Redirect to Arhiva (unified document archive)
    return redirect("documents:arhiva_list")


def document_list_legacy(request):
    q = request.GET.get("q", "")
    doc_type = request.GET.get("doc_type", "")
    is_paid = request.GET.get("is_paid", "")
    company = get_user_company(request)
    qs = Document.objects.filter(company=company).select_related("company", "partner").order_by("-date_issued") if company else Document.objects.none()
    if q:
        qs = qs.filter(Q(doc_number__icontains=q)|Q(partner__name__icontains=q))
    if doc_type:
        qs = qs.filter(doc_type=doc_type)
    if is_paid == "1":
        qs = qs.filter(is_paid=True)
    elif is_paid == "0":
        qs = qs.filter(is_paid=False)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "documents/document_list.html", {
        "page_obj": page, "q": q, "doc_type": doc_type, "is_paid": is_paid,
        "total": qs.count(), "type_choices": Document.TYPE_CHOICES,
    })


@login_required
def document_create(request):
    if request.method == "POST":
        try:
            company = get_user_company(request)
            if not company:
                messages.error(request, 'Nema aktivne firme.')
                return redirect('documents:list')
            partner_id = request.POST.get("partner")
            partner = Partner.objects.get(pk=partner_id) if partner_id else None
            doc = Document(
                company=company,
                partner=partner,
                doc_type=request.POST["doc_type"],
                doc_number=request.POST["doc_number"],
                date_issued=request.POST["date_issued"],
                total_amount=request.POST.get("total_amount", 0) or 0,
                is_paid="is_paid" in request.POST,
            )
            date_due = request.POST.get("date_due")
            if date_due:
                doc.date_due = date_due
            if "file" in request.FILES:
                doc.file = request.FILES["file"]
            doc.save()
            messages.success(request, f"Dokument {doc.doc_number} kreiran.")
            return redirect("documents:list")
        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            messages.error(request, str(e))
    company = get_user_company(request)
    return render(request, "documents/document_form.html", {
        "company": company,
        "partners": Partner.objects.filter(company=company, is_active=True).order_by("name") if company else Partner.objects.none(),
        "type_choices": Document.TYPE_CHOICES,
        "action": "Novi dokument",
    })


@login_required
def document_detail(request, pk):
    company = get_user_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    return render(request, "documents/document_detail.html", {"doc": doc})


@login_required
def document_toggle_paid(request, pk):
    company = get_user_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    doc.is_paid = not doc.is_paid
    doc.save(update_fields=["is_paid"])
    status = "plaćeno" if doc.is_paid else "neplaćeno"
    messages.success(request, f"Dokument {doc.doc_number} označen kao {status}.")
    return redirect("documents:list")


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        if company:
            return Document.objects.filter(company=company)
        return Document.objects.none()


# ════════════════════════════════════════════════════════════
# Process Documents Views (Otpremnica, Primka, Otkupni, CMR)
# ════════════════════════════════════════════════════════════
import io
from datetime import date

from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import CMR, CMRItem, OtkupniBlok, OtkupniBlokItem, Otpremnica, OtpremnicaItem

DOC_MAP = {
    'otpremnica': (Otpremnica, OtpremnicaItem, 'OTP'),
    'otkupni': (OtkupniBlok, OtkupniBlokItem, 'OTK'),
    'cmr': (CMR, CMRItem, 'CMR'),
}


def _next_doc_number(model_cls, prefix, company):
    """Generate next sequential doc number: PREFIX-YYYY-NNNN"""
    year = date.today().year
    pattern = f"{prefix}-{year}-"
    last = model_cls.objects.filter(
        company=company, doc_number__startswith=pattern
    ).order_by('-doc_number').first()
    if last:
        try:
            seq = int(last.doc_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}-{year}-{seq:04d}"


# ── Generic list view ──
def _doc_list(request, model_cls, template, title):
    company = get_user_company(request)
    qs = model_cls.objects.filter(company=company) if company else model_cls.objects.none()
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(doc_number__icontains=q) | Q(partner__name__icontains=q))
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, template, {
        'page_obj': page, 'q': q, 'status_filter': status,
        'total': qs.count(), 'title': title,
    })


# ── Generic detail view ──
def _doc_detail(request, pk, model_cls, template, title):
    doc = get_object_or_404(model_cls, pk=pk)
    ctx = {'doc': doc, 'title': title}
    try:
        from django.contrib.contenttypes.models import ContentType
        from tracking.models import TrackedItem, TrackingStatus
        ct = ContentType.objects.get_for_model(doc)
        ctx['tracked_item'] = TrackedItem.objects.filter(content_type=ct, object_id=str(doc.pk)).first()
        ctx['shipment_statuses'] = TrackingStatus.objects.filter(tracking_type='shipment').order_by('order')
    except Exception:
        pass
    return render(request, template, ctx)


# ── Generic confirm ──
@login_required
def doc_confirm(request, pk):
    """Confirm any process document by UUID."""
    for name, (model_cls, _, _) in DOC_MAP.items():
        try:
            doc = model_cls.objects.get(pk=pk)
            doc.confirm()
            messages.success(request, f"{doc} potvrđen.")
            return redirect(request.META.get('HTTP_REFERER', '/documents/'))
        except model_cls.DoesNotExist:
            continue
    messages.error(request, "Dokument nije pronađen.")
    return redirect('/documents/')


# ── OTPREMNICA ──
@login_required
def otpremnica_list(request):
    return _doc_list(request, Otpremnica, 'documents/process_list.html', 'Otpremnice')

@login_required
def otpremnica_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('documents:list')
    if request.method == 'POST':
        doc = Otpremnica(
            company=company,
            doc_number=_next_doc_number(Otpremnica, 'OTP', company),
            date_issued=request.POST.get('date_issued', date.today()),
            delivery_address=request.POST.get('delivery_address', ''),
            vehicle_plate=request.POST.get('vehicle_plate', ''),
            driver_name=request.POST.get('driver_name', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        partner_id = request.POST.get('partner')
        if partner_id:
            doc.partner_id = partner_id
        doc.save()
        # Save items
        names   = request.POST.getlist('item_name')
        qtys    = request.POST.getlist('item_qty')
        units   = request.POST.getlist('item_unit')
        prices  = request.POST.getlist('item_price')
        vats    = request.POST.getlist('item_vat')
        batches = request.POST.getlist('item_batch')
        ebatch_ids = request.POST.getlist('item_expiry_batch')
        for i in range(len(names)):
            if names[i].strip():
                eb_id = ebatch_ids[i] if i < len(ebatch_ids) else ''
                item = OtpremnicaItem(
                    document=doc,
                    product_name=names[i],
                    quantity=qtys[i] or 1,
                    unit=units[i] if i < len(units) else 'kg',
                    unit_price=prices[i] if i < len(prices) else 0,
                    vat_rate=vats[i] if i < len(vats) else 25,
                    batch_number=batches[i] if i < len(batches) else '',
                )
                if eb_id:
                    try:
                        from pos.models import ExpiryBatch
                        item.expiry_batch_id = int(eb_id)
                        # Auto-fill batch_number from ExpiryBatch if empty
                        if not item.batch_number:
                            eb = ExpiryBatch.objects.get(pk=int(eb_id))
                            item.batch_number = eb.batch_number or f'LOT-{eb.expiry_date}'
                    except Exception:
                        pass
                item.save()
        messages.success(request, f"Otpremnica {doc.doc_number} kreirana.")
        return redirect('documents:otpremnica_detail', pk=doc.pk)

    partners = Partner.objects.filter(is_active=True).order_by('name') if Partner else []
    try:
        from pos.models import ExpiryBatch
        available_lots = ExpiryBatch.objects.filter(
            company=company, is_removed=False, quantity__gt=0
        ).select_related('inventory_item').order_by('expiry_date')
    except Exception:
        available_lots = []
    return render(request, 'documents/otpremnica_form.html', {
        'partners': partners, 'title': 'Nova otpremnica',
        'next_number': _next_doc_number(Otpremnica, 'OTP', company),
        'available_lots': available_lots,
    })

@login_required
def otpremnica_detail(request, pk):
    return _doc_detail(request, pk, Otpremnica, 'documents/process_detail.html', 'Otpremnica')


# ── PRIMKA ──
@login_required
def primka_list(request):
    # Primka moved to inventory.GoodsReceipt
    from django.shortcuts import redirect
    return redirect('inventory:receipt_list')

@login_required
def primka_create(request):
    # Primka moved to inventory.GoodsReceipt
    return redirect('inventory:receipt_create')

@login_required
def primka_detail(request, pk):
    # Primka moved to inventory.GoodsReceipt
    from django.shortcuts import redirect
    return redirect('inventory:receipt_list')


# ── OTKUPNI BLOK ──
@login_required
def otkupni_list(request):
    return _doc_list(request, OtkupniBlok, 'documents/process_list.html', 'Otkupni blokovi')

@login_required
def otkupni_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('documents:list')
    if request.method == 'POST':
        doc = OtkupniBlok(
            company=company,
            doc_number=_next_doc_number(OtkupniBlok, 'OTK', company),
            date_issued=request.POST.get('date_issued', date.today()),
            farmer_name=request.POST.get('farmer_name', ''),
            farmer_oib=request.POST.get('farmer_oib', ''),
            farmer_address=request.POST.get('farmer_address', ''),
            farmer_iban=request.POST.get('farmer_iban', ''),
            payment_method=request.POST.get('payment_method', 'virman'),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        doc.save()
        names = request.POST.getlist('item_name')
        qtys = request.POST.getlist('item_qty')
        units = request.POST.getlist('item_unit')
        prices = request.POST.getlist('item_price')
        origins = request.POST.getlist('item_origin')
        qualities = request.POST.getlist('item_quality')
        for i in range(len(names)):
            if names[i].strip():
                OtkupniBlokItem.objects.create(
                    document=doc, product_name=names[i],
                    quantity=qtys[i] or 1, unit=units[i] if i < len(units) else 'kg',
                    unit_price=prices[i] if i < len(prices) else 0,
                    origin_country=origins[i] if i < len(origins) else 'HR',
                    quality_class=qualities[i] if i < len(qualities) else '',
                )
        messages.success(request, f"Otkupni blok {doc.doc_number} kreiran.")
        return redirect('documents:otkupni_detail', pk=doc.pk)

    return render(request, 'documents/otkupni_form.html', {
        'title': 'Novi otkupni blok',
        'next_number': _next_doc_number(OtkupniBlok, 'OTK', company),
    })

@login_required
def otkupni_detail(request, pk):
    return _doc_detail(request, pk, OtkupniBlok, 'documents/process_detail.html', 'Otkupni blok')


# ── CMR ──
@login_required
def cmr_list(request):
    return _doc_list(request, CMR, 'documents/process_list.html', 'CMR teretni listovi')

@login_required
def cmr_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('documents:list')
    if request.method == 'POST':
        doc = CMR(
            company=company,
            doc_number=_next_doc_number(CMR, 'CMR', company),
            date_issued=request.POST.get('date_issued', date.today()),
            sender_name=request.POST.get('sender_name', ''),
            sender_address=request.POST.get('sender_address', ''),
            receiver_name=request.POST.get('receiver_name', ''),
            receiver_address=request.POST.get('receiver_address', ''),
            carrier_name=request.POST.get('carrier_name', ''),
            vehicle_plate=request.POST.get('vehicle_plate', ''),
            place_of_loading=request.POST.get('place_of_loading', ''),
            place_of_delivery=request.POST.get('place_of_delivery', ''),
            temp_regime=request.POST.get('temp_regime', ''),
            customs_status=request.POST.get('customs_status', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        partner_id = request.POST.get('partner')
        if partner_id:
            doc.partner_id = partner_id
        doc.save()
        names = request.POST.getlist('item_name')
        qtys = request.POST.getlist('item_qty')
        units = request.POST.getlist('item_unit')
        prices = request.POST.getlist('item_price')
        packagings = request.POST.getlist('item_packaging')
        weights = request.POST.getlist('item_weight')
        for i in range(len(names)):
            if names[i].strip():
                CMRItem.objects.create(
                    document=doc, product_name=names[i],
                    quantity=qtys[i] or 1, unit=units[i] if i < len(units) else 'kg',
                    unit_price=prices[i] if i < len(prices) else 0,
                    packaging=packagings[i] if i < len(packagings) else '',
                    gross_weight_kg=weights[i] if i < len(weights) and weights[i] else None,
                )
        messages.success(request, f"CMR {doc.doc_number} kreiran.")
        return redirect('documents:cmr_detail', pk=doc.pk)

    partners = Partner.objects.filter(is_active=True).order_by('name') if Partner else []
    return render(request, 'documents/cmr_form.html', {
        'partners': partners, 'title': 'Novi CMR',
        'next_number': _next_doc_number(CMR, 'CMR', company),
    })

@login_required
def cmr_detail(request, pk):
    return _doc_detail(request, pk, CMR, 'documents/process_detail.html', 'CMR')


# ── PDF GENERATION ──
def _render_pdf(request, template_name, context):
    """Render HTML template to PDF using xhtml2pdf."""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse("xhtml2pdf not installed", status=500)
    html = render_to_string(template_name, context, request=request)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), result)
    if pdf.err:
        return HttpResponse("PDF generation error", status=500)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{context.get("filename", "document")}.pdf"'
    return response


@login_required
def otpremnica_pdf(request, pk):
    doc = get_object_or_404(Otpremnica, pk=pk)
    return _render_pdf(request, 'documents/pdf/otpremnica_pdf.html', {
        'doc': doc, 'items': doc.items.all(), 'filename': f'OTP-{doc.doc_number}',
        'user': request.user,
    })

@login_required
def primka_pdf(request, pk):
    # Primka moved to inventory.GoodsReceipt
    return redirect('inventory:receipt_list')

@login_required
def otkupni_pdf(request, pk):
    doc = get_object_or_404(OtkupniBlok, pk=pk)
    return _render_pdf(request, 'documents/pdf/otkupni_pdf.html', {
        'doc': doc, 'items': doc.items.all(), 'filename': f'OTK-{doc.doc_number}',
    })

@login_required
def cmr_pdf(request, pk):
    doc = get_object_or_404(CMR, pk=pk)
    return _render_pdf(request, 'documents/pdf/cmr_pdf.html', {
        'doc': doc, 'items': doc.items.all(), 'filename': f'CMR-{doc.doc_number}',
    })


# ════════════════════════════════════════════════════════════
# ARHIVA — Centralizirana arhiva svih dokumenata
# ════════════════════════════════════════════════════════════

from .models import ArhivaEntry
def _safe_err(e, default="Greska pri obradi. Kontaktirajte administratora."):
    """Sanitizira exception poruku — ne salje stack trace korisniku."""
    msg = str(e)
    if len(msg) > 80 or any(x in msg for x in ['File "', 'line ', 'Traceback', 'django.', 'psycopg']):
        return default
    return msg[:80]



from .models import ArhivaEntry

@login_required
def arhiva_list(request):
    is_superadmin = request.user.is_superuser

    if is_superadmin:
        from companies.models import Company
        from companies.utils import get_managed_companies
        managed = get_managed_companies(request.user)

        if managed.exists() and not request.user.company_memberships.filter(
            is_active=True, is_default=True
        ).first().company.is_platform_owner:
            # Reseller superadmin - vidi samo svoje firme
            companies = managed
            qs = ArhivaEntry.objects.select_related('company').filter(
                company__in=managed
            ).exclude(amount=0).order_by('-archived_at')
        else:
            # Platform owner - vidi sve
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
            return render(request, 'documents/arhiva_list.html', {'entries': [], 'is_superadmin': False})
        qs = ArhivaEntry.objects.filter(company=company).exclude(amount=0).order_by('-doc_date', '-archived_at')
        company_filter = ''
        companies = []
        # Show all company documents by default

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
    from .models import ArhivaBookmark
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

    return render(request, 'documents/arhiva_list.html', {
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
        'year_filter': year_filter if is_superadmin else '',
        'year_filter_val': request.GET.get('year', '') if is_superadmin else '',
        'stats': stats,
        'sort': sort,
        'order': order,
        'bookmarked': bookmarked,
        'hide_zero': hide_zero,
        'bookmarked_ids': set(ArhivaBookmark.objects.filter(
            user=request.user
        ).values_list('entry_id', flat=True)) if request.user.is_authenticated else set(),
    })


# ════════════════════════════════════════════════════════════
# BLOB SERVE — Servira datoteke iz baze
# ════════════════════════════════════════════════════════════

from .models import DocumentBlob

@login_required
def blob_serve(request, blob_id):
    from django.http import HttpResponse
    blob = get_object_or_404(DocumentBlob, id=blob_id)
    response = HttpResponse(blob.file_data, content_type=blob.content_type)
    response['Content-Disposition'] = 'inline; filename="%s"' % blob.filename
    return response


# ════════════════════════════════════════════════════════════
# UPLOAD — Upload datoteke u arhivu (sve 3 opcije)
# ════════════════════════════════════════════════════════════

from .storage_backends import store_document

@login_required
def arhiva_upload(request):
    if request.method == 'POST' and request.FILES.get('file'):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Nije moguce odrediti tvrtku.')
            return redirect('documents:arhiva_list')

        uploaded = request.FILES['file']
        source_type = request.POST.get('source_type', 'document')
        backend_name = request.POST.get('backend', None)  # None = default iz .env

        # Odredi backend iz StorageConfig ako postoji
        if backend_name is None:
            try:
                from .models import StorageConfig
                cfg = StorageConfig.objects.get(company=company)
                backend_name = cfg.backend
            except Exception:
                pass

        try:
            result = store_document(
                file_bytes=uploaded.read(),
                filename=uploaded.name,
                company_id=company.id,
                source_type=source_type,
                backend_name=backend_name,
            )

            # Kreiraj ArhivaEntry
            ArhivaEntry.objects.create(
                company=company,
                source_type=source_type,
                source_id=result.get('hash', ''),
                doc_number=request.POST.get('doc_number', uploaded.name),
                partner_name=request.POST.get('partner_name', ''),
                amount=Decimal(str(request.POST.get('amount', 0) or 0)),
                currency=request.POST.get('currency', 'EUR'),
                doc_date=request.POST.get('doc_date') or timezone.now().date(),
                file_path=result['path'],
                has_pdf=uploaded.name.lower().endswith('.pdf'),
                has_xml=uploaded.name.lower().endswith('.xml'),
                has_image=result.get('content_type', '').startswith('image/'),
                archived_by=request.user,
                session_key=request.session.session_key or '',
            )

            size_kb = result['size'] // 1024
            messages.success(request, 'Datoteka spremljena (%s, %dKB, backend: %s)' % (uploaded.name, size_kb, result['backend']))

            # Trigeraj AI analizu async
            try:
                from documents.tasks import generate_ai_proposal
                new_entry = ArhivaEntry.objects.filter(
                    company=company,
                    source_id=result.get('hash', ''),
                ).order_by('-archived_at').first()
                if new_entry and (new_entry.has_pdf or new_entry.has_image):
                    generate_ai_proposal.apply_async(
                        args=[new_entry.pk],
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
import csv
import io
import json
import zipfile
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST


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

    from datetime import date
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
        import os
        from django.conf import settings
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
    from datetime import date
    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="arhiva_%s_%d_files.zip"' % (date.today().isoformat(), added)
    return response


# ════════════════════════════════════════════════════════════
# BOOKMARK TOGGLE
# ════════════════════════════════════════════════════════════

from .models import ArhivaBookmark

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

    # Bookmark status
    result['bookmarked'] = ArhivaBookmark.objects.filter(user=request.user, entry=entry).exists()

    return JsonResponse(result)


@login_required
def arhiva_barcode_png(request, pk):
    """Generiraj Code128 barcode kao PNG."""
    import io
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
# KONVERZIJA — Slika ulaznog racuna -> XML
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_convert(request):
    """Upload slike ulaznog racuna za konverziju u XML."""
    if request.method == 'POST' and request.FILES.get('file'):
        company = get_user_company(request)
        if not company:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Nema aktivne tvrtke'}, status=400)
            messages.error(request, 'Nema aktivne tvrtke.')
            return redirect('documents:arhiva_list')

        uploaded = request.FILES['file']
        file_bytes = uploaded.read()

        # Validate file type
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Samo slike (JPG, PNG, WebP). PDF koristite Smart Import.'}, status=400)
            messages.error(request, 'Samo slike (JPG, PNG, WebP).')
            return redirect('documents:arhiva_list')

        try:
            from documents.conversion_service import convert_image_to_xml
            record = convert_image_to_xml(
                file_bytes=file_bytes,
                filename=uploaded.name,
                company=company,
                user=request.user,
            )

            result = {
                'success': True,
                'record_id': str(record.id),
                'status': record.status,
                'confidence': record.ai_confidence,
                'confidence_score': record.ai_confidence_score,
                'fields_extracted': record.fields_extracted,
                'items_extracted': record.items_extracted,
                'original_size': record.original_size,
                'xml_size': record.xml_size,
                'size_reduction_pct': round(record.size_reduction_pct, 1),
                'is_valid': record.is_valid,
                'validation_errors': record.validation_errors,
                'extracted_data': record.extracted_data,
                'savings': record.savings_display,
                'message': 'Konverzija zavrsena: %s -> XML (%s usteda)' % (uploaded.name, record.savings_display),
            }

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(result)

            if record.is_valid:
                messages.success(request, result['message'])
            else:
                messages.warning(request, 'Konverzija zavrsena s upozorenjima: %s' % '; '.join(record.validation_errors))

        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            logger.error('Conversion error: %s', e, exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
            messages.error(request, _safe_err(e))

        return redirect('documents:arhiva_list')

    # GET: show conversion page
    from documents.models import ConversionRecord
    company = get_user_company(request)
    if request.user.is_superuser:
        recent = ConversionRecord.objects.all()[:20]
    elif company:
        recent = ConversionRecord.objects.filter(company=company)[:20]
    else:
        recent = []

    return render(request, 'documents/arhiva_convert.html', {
        'recent_conversions': recent,
    })


@login_required
def conversion_detail(request, pk):
    """API: detalji konverzije."""
    from documents.models import ConversionRecord
    record = get_object_or_404(ConversionRecord, pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if record.company != company:
            return JsonResponse({'error': 'Forbidden'}, status=403)

    return JsonResponse({
        'id': str(record.id),
        'status': record.status,
        'status_display': record.get_status_display(),
        'original_filename': record.original_filename,
        'original_size': record.original_size,
        'original_hash': record.original_hash,
        'ai_model': record.ai_model,
        'ai_confidence': record.ai_confidence,
        'ai_confidence_score': record.ai_confidence_score,
        'ai_cost_eur': str(record.ai_cost_eur),
        'fields_extracted': record.fields_extracted,
        'items_extracted': record.items_extracted,
        'xml_size': record.xml_size,
        'xml_hash': record.xml_hash,
        'size_reduction_pct': round(record.size_reduction_pct, 1),
        'is_valid': record.is_valid,
        'validation_errors': record.validation_errors,
        'extracted_data': record.extracted_data,
        'savings': record.savings_display,
        'created_at': record.created_at.strftime('%d.%m.%Y %H:%M') if record.created_at else '',
        'completed_at': record.completed_at.strftime('%d.%m.%Y %H:%M') if record.completed_at else '',
    })




@login_required
@require_POST
def conversion_create_primka(request, pk):
    """Kreira GoodsReceipt primku iz ConversionRecord extracted_data.

    Kontrole:
    - Duplikat: ako vec postoji primka iz iste konverzije, vraca link na postojecu
    - Auto-broj: PRIMKA-YYYY-NNNN sekvencijalni (HR propisi, ZOR cl. 9)
    - Ako nema broja ulaznog racuna: napomena za rucnu provjeru
    """
    from datetime import date as _date
    from documents.models import ConversionRecord
    from documents.conversion_service import _parse_date_obj
    from inventory.models import GoodsReceipt, GoodsReceiptItem, InventoryItem
    from partners.models import Partner

    record = get_object_or_404(ConversionRecord, pk=pk)
    company = get_user_company(request)

    if not request.user.is_superuser and record.company != company:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # ── Duplikat kontrola: trazi primku s istim conversion ID u notes ──
    conv_marker = 'conversion:%s' % record.id
    existing = GoodsReceipt.objects.filter(
        company=company,
        notes__contains=conv_marker,
    ).first()
    if existing:
        return JsonResponse({
            'ok': True,
            'duplicate': True,
            'primka_id': existing.pk,
            'primka_url': '/inventory/receipts/%s/' % existing.pk,
            'message': 'Primka %s vec postoji iz ove konverzije' % existing.receipt_number,
        })

    data = record.extracted_data or {}
    seller = data.get('seller', {})

    # ── Partner: pronadi po OIB-u ili imenu ──
    partner = None
    oib = seller.get('oib', '').strip()
    if oib:
        partner = Partner.objects.filter(company=company, oib=oib).first()
    if not partner and seller.get('name'):
        partner = Partner.objects.filter(
            company=company,
            name__icontains=seller['name'][:20]
        ).first()

    # ── Auto-broj primke: PRIMKA-YYYY-NNNN ──
    year = _date.today().year
    prefix = 'PRIMKA-%d-' % year
    last = GoodsReceipt.objects.filter(
        company=company,
        receipt_number__startswith=prefix,
    ).order_by('-receipt_number').first()
    seq = 1
    if last and last.receipt_number:
        try:
            seq = int(last.receipt_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            pass
    receipt_number = '%s%04d' % (prefix, seq)

    # ── Broj ulaznog racuna ──
    invoice_number = (data.get('invoice_number') or '').strip()
    notes_parts = ['[conversion:%s]' % record.id]
    if not invoice_number:
        notes_parts.append('NAPOMENA: Broj ulaznog racuna nije prepoznat iz slike - provjeriti rucno i unijeti u polje "Broj ulaznog racuna"')
    notes_parts.append('Izvor: AI konverzija slike %s' % record.original_filename)

    # ── Vrsta primke (iz POST body ili default) ──
    import json as _json
    try:
        body = _json.loads(request.body) if request.content_type == 'application/json' else {}
    except (ValueError, TypeError):
        body = {}
    receipt_type = body.get('receipt_type', 'supplier')
    valid_types = ('supplier', 'return', 'transfer', 'inventory', 'consignment', 'complaint')
    if receipt_type not in valid_types:
        receipt_type = 'supplier'

    # ── Kreiraj primku ──
    issue_date = _parse_date_obj(data.get('issue_date', ''))

    primka = GoodsReceipt.objects.create(
        company=company,
        supplier=partner,
        receipt_number=receipt_number,
        date=issue_date or _date.today(),
        document_number=invoice_number,
        linked_invoice_number=invoice_number,
        notes='\n'.join(notes_parts),
        status='draft',
        created_by=request.user,
        receipt_type=receipt_type,
    )

    # ── Stavke ──
    items_added = 0
    items_skipped = 0
    skipped_names = []
    for item_data in data.get('items', []):
        desc = item_data.get('description', '')
        inv_item = None
        if desc:
            inv_item = InventoryItem.objects.filter(
                company=company,
                name__icontains=desc[:30]
            ).first()

        if not inv_item:
            items_skipped += 1
            skipped_names.append(desc[:40] if desc else '?')
            continue

        gi = GoodsReceiptItem(
            receipt=primka,
            inventory_item=inv_item,
            quantity=item_data.get('quantity', 1),
            purchase_price_unit=item_data.get('unit_price', 0),
            tax_rate=item_data.get('vat_rate', 25),
        )
        gi.calculate()
        gi.save()
        items_added += 1

    msg = 'Primka %s kreirana' % receipt_number
    details = []
    if items_added:
        details.append('%d stavki dodano' % items_added)
    if items_skipped:
        details.append('%d preskoceno (artikl nije pronadjen)' % items_skipped)
    if not invoice_number:
        details.append('broj racuna nije prepoznat')
    if details:
        msg += ' (%s)' % ', '.join(details)

    return JsonResponse({
        'ok': True,
        'primka_id': primka.pk,
        'primka_url': '/inventory/receipts/%s/' % primka.pk,
        'receipt_number': receipt_number,
        'items_added': items_added,
        'items_skipped': items_skipped,
        'skipped_items': skipped_names[:5],
        'missing_invoice_number': not bool(invoice_number),
        'message': msg,
    })


# ════════════════════════════════════════════════════════════
# KNJIGA URA / IRA — Pogled iz arhive
# ════════════════════════════════════════════════════════════

@login_required
def knjiga_ura_ira(request):
    """Knjiga ulaznih (URA) i izlaznih (IRA) racuna.
    Cita podatke iz ArhivaEntry + ConversionRecord.extracted_data (URA)
    i Invoice modela (IRA). Jedan izvor, vise pogleda.
    """
    from documents.models import ArhivaEntry, ConversionRecord
    from decimal import Decimal
    from datetime import date as _date
    import json as _json

    company = get_user_company(request)

    # Superadmin/staff moze birati firmu
    company_id = request.GET.get('company', '')
    all_companies = []
    if request.user.is_superuser or request.user.is_staff:
        from companies.models import Company
        from django.db.models import Q
        # Samo firme koje imaju fakture ili ulazne racune
        from invoicing.models import Invoice as _Inv
        from documents.models import ArhivaEntry as _AE
        has_ira = set(_Inv.objects.values_list('company_id', flat=True).distinct())
        has_ura = set(_AE.objects.filter(source_type__in=['invoice_in','eracun','fiscal_cert']).values_list('company_id', flat=True).distinct())
        active_ids = has_ira | has_ura
        if active_ids:
            all_companies = list(Company.objects.filter(pk__in=active_ids).order_by('name'))
        else:
            all_companies = list(Company.objects.all().order_by('name'))
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                pass

    if not company:
        return render(request, 'documents/knjiga_ura_ira.html', {'entries': [], 'book_type': 'URA', 'all_companies': all_companies})

    book_type = request.GET.get('type', 'URA').upper()
    if book_type not in ('URA', 'IRA'):
        book_type = 'URA'

    # Period filter
    year = int(request.GET.get('year', _date.today().year))
    month = request.GET.get('month', '')
    quarter = request.GET.get('quarter', '')

    date_from = _date(year, 1, 1)
    date_to = _date(year, 12, 31)
    period_label = str(year)

    if month and month.isdigit():
        m = int(month)
        if 1 <= m <= 12:
            date_from = _date(year, m, 1)
            if m == 12:
                date_to = _date(year, 12, 31)
            else:
                date_to = _date(year, m + 1, 1)
                from datetime import timedelta
                date_to = date_to - timedelta(days=1)
            period_label = '%02d/%d' % (m, year)
    elif quarter and quarter.isdigit():
        q = int(quarter)
        if 1 <= q <= 4:
            from datetime import timedelta
            date_from = _date(year, (q - 1) * 3 + 1, 1)
            end_month = q * 3
            if end_month == 12:
                date_to = _date(year, 12, 31)
            else:
                date_to = _date(year, end_month + 1, 1) - timedelta(days=1)
            period_label = 'Q%d/%d' % (q, year)

    # Partner filter
    partner_q = request.GET.get('partner', '').strip()

    entries = []
    totals = {
        'base_0': Decimal('0'), 'base_5': Decimal('0'), 'base_13': Decimal('0'), 'base_25': Decimal('0'),
        'vat_5': Decimal('0'), 'vat_13': Decimal('0'), 'vat_25': Decimal('0'),
        'total_with_vat': Decimal('0'), 'total_vat': Decimal('0'), 'total_base': Decimal('0'),
        'count': 0,
    }

    if book_type == 'URA':
        # Ulazni racuni iz arhive
        qs = ArhivaEntry.objects.filter(
            company=company,
            source_type__in=['invoice_in', 'eracun', 'fiscal_cert'],
            doc_date__gte=date_from,
            doc_date__lte=date_to,
        ).order_by('doc_date', 'pk')

        if partner_q:
            qs = qs.filter(partner_name__icontains=partner_q)

        # Dohvati extracted_data iz ConversionRecord
        conv_map = {}
        conv_ids = []
        for a in qs:
            if a.source_id and a.source_id.startswith('conversion:'):
                conv_ids.append(a.source_id.replace('conversion:', ''))
        if conv_ids:
            for cr in ConversionRecord.objects.filter(id__in=conv_ids):
                conv_map[str(cr.id)] = cr.extracted_data or {}

        for idx, a in enumerate(qs, 1):
            conv_id = a.source_id.replace('conversion:', '') if a.source_id and a.source_id.startswith('conversion:') else ''
            data = conv_map.get(conv_id, {})

            # Izracunaj PDV po stopama iz extracted_data
            total = Decimal(str(data.get('total', 0) or a.amount or 0))
            subtotal = Decimal(str(data.get('subtotal', 0) or 0))
            vat_amount = Decimal(str(data.get('vat_amount', 0) or 0))

            # Razvrstaj po stopama
            b0 = b5 = b13 = b25 = Decimal('0')
            v5 = v13 = v25 = Decimal('0')

            items = data.get('items', [])
            if items:
                for item in items:
                    rate = int(item.get('vat_rate', 0) or 0)
                    line = Decimal(str(item.get('line_total', 0) or 0))
                    item_vat = Decimal(str(item.get('unit_price', 0) or 0)) * Decimal(str(item.get('quantity', 0) or 0))
                    # line_total moze biti s ili bez PDV-a, koristimo kao osnovicu
                    base = line
                    vat = (base * Decimal(str(rate)) / Decimal('100')).quantize(Decimal('0.01'))

                    if rate == 0:
                        b0 += base
                    elif rate == 5:
                        b5 += base; v5 += vat
                    elif rate in (10, 13):
                        b13 += base; v13 += vat
                    else:
                        b25 += base; v25 += vat
            elif subtotal:
                # Nema stavki, koristimo ukupne iznose
                b25 = subtotal
                v25 = vat_amount

            if not subtotal and not items:
                b25 = total
                v25 = Decimal('0')

            total_with = total if total else (b0 + b5 + b13 + b25 + v5 + v13 + v25)

            seller = data.get('seller', {})
            entry = {
                'seq': idx,
                'doc_number': data.get('invoice_number', '') or a.doc_number,
                'doc_date': a.doc_date,
                'partner_name': seller.get('name', '') or a.partner_name,
                'partner_address': (seller.get('address', '') + ' ' + seller.get('city', '')).strip() if seller else '',
                'partner_oib': seller.get('oib', '') or '',
                'oib_type': 2 if (seller.get('country', 'HR') != 'HR' and seller.get('oib', '')) else 1,
                'base_0': b0, 'base_5': b5, 'base_13': b13, 'base_25': b25,
                'vat_5': v5, 'vat_13': v13, 'vat_25': v25,
                'total_vat': v5 + v13 + v25,
                'total_with_vat': total_with,
                'archive_number': a.archive_number if hasattr(a, 'archive_number') else '',
                'pk': a.pk,
                'currency': data.get('currency', a.currency),
            }
            entries.append(entry)

            totals['base_0'] += b0; totals['base_5'] += b5; totals['base_13'] += b13; totals['base_25'] += b25
            totals['vat_5'] += v5; totals['vat_13'] += v13; totals['vat_25'] += v25
            totals['total_vat'] += entry['total_vat']
            totals['total_with_vat'] += total_with
            totals['count'] += 1

    else:  # IRA
        try:
            from invoicing.models import Invoice
            qs = Invoice.objects.filter(
                company=company,
                date_issued__year__gte=date_from.year,
                date_issued__year__lte=date_to.year,
                status__in=['confirmed','fiscalized','sent','paid','unpaid','overdue','CONFIRMED','FISCALIZED','SENT','PAID','UNPAID','OVERDUE'],
            ).select_related('partner').order_by('date_issued')
            # Dodatni filter po mjesecu/kvartalu ako je odabran
            if month and month.isdigit():
                qs = qs.filter(date_issued__month=int(month))
            elif quarter and quarter.isdigit():
                q = int(quarter)
                qs = qs.filter(date_issued__month__gte=(q-1)*3+1, date_issued__month__lte=q*3)

            if partner_q:
                qs = qs.filter(client_name__icontains=partner_q)

            for idx, inv in enumerate(qs, 1):
                subtotal = inv.subtotal or Decimal('0')
                tax_pct = inv.tax_percent or Decimal('0')
                tax_amt = inv.tax_amount or Decimal('0')
                total = inv.total or Decimal('0')

                b0 = b5 = b13 = b25 = Decimal('0')
                v5 = v13 = v25 = Decimal('0')

                if tax_pct == 5:
                    b5 = subtotal; v5 = tax_amt
                elif tax_pct in (10, 13):
                    b13 = subtotal; v13 = tax_amt
                elif tax_pct == 25:
                    b25 = subtotal; v25 = tax_amt
                elif tax_pct == 0:
                    b0 = subtotal
                else:
                    b25 = subtotal; v25 = tax_amt

                entry = {
                    'seq': idx,
                    'doc_number': inv.number,
                    'doc_date': inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued,
                    'partner_name': inv.client_name or (inv.partner.name if inv.partner else ''),
                    'partner_address': inv.client_address or '',
                    'partner_oib': inv.client_oib or '',
                    'oib_type': 1,
                    'base_0': b0, 'base_5': b5, 'base_13': b13, 'base_25': b25,
                    'vat_5': v5, 'vat_13': v13, 'vat_25': v25,
                    'total_vat': v5 + v13 + v25,
                    'total_with_vat': total,
                    'archive_number': '',
                    'pk': inv.pk,
                    'currency': 'EUR',
                    'jir': getattr(inv, 'jir', ''),
                    'zki': getattr(inv, 'zki', ''),
                }
                entries.append(entry)

                totals['base_0'] += b0; totals['base_5'] += b5; totals['base_13'] += b13; totals['base_25'] += b25
                totals['vat_5'] += v5; totals['vat_13'] += v13; totals['vat_25'] += v25
                totals['total_vat'] += entry['total_vat']
                totals['total_with_vat'] += total
                totals['count'] += 1
        except ImportError:
            pass

    totals['total_base'] = totals['base_0'] + totals['base_5'] + totals['base_13'] + totals['base_25']

    # Export?
    fmt = request.GET.get('format', '')
    if fmt == 'xml':
        return _knjiga_xml(request, book_type, entries, totals, company, date_from, date_to, period_label)
    if fmt == 'pdf':
        return _knjiga_pdf(request, book_type, entries, totals, company, date_from, date_to, period_label)

    return render(request, 'documents/knjiga_ura_ira.html', {
        'entries': entries,
        'totals': totals,
        'book_type': book_type,
        'year': year,
        'month': month,
        'quarter': quarter,
        'period_label': period_label,
        'partner_q': partner_q,
        'company': company,
        'years': list(range(_date.today().year, 2022, -1)),
        'all_companies': all_companies,
        'selected_company_id': str(company.pk) if company else '',
    })


def _knjiga_xml(request, book_type, entries, totals, company, date_from, date_to, period_label):
    """Generira URA/IRA XML za ePorezna."""
    from django.http import HttpResponse
    from xml.etree.ElementTree import Element, SubElement, tostring

    ns = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/%s/v1-0' % book_type
    root = Element('{%s}Obrazac%s' % (ns, book_type))
    root.set('xmlns', ns)
    root.set('verzijaSheme', '1.0')

    # Zaglavlje
    meta = SubElement(root, 'Metapodaci')
    SubElement(meta, 'Naslov').text = 'Knjiga %s racuna' % ('primljenih (ulaznih)' if book_type == 'URA' else 'izdanih (izlaznih)')
    SubElement(meta, 'Autor').text = 'LIMIT Connect ERP'
    SubElement(meta, 'Datum').text = date_from.isoformat()
    SubElement(meta, 'Format').text = 'text/xml'

    # Zaglavlje s obveznikovim podacima
    zag = SubElement(root, 'Zaglavlje')
    razd = SubElement(zag, 'Razdoblje')
    SubElement(razd, 'DatumOd').text = date_from.isoformat()
    SubElement(razd, 'DatumDo').text = date_to.isoformat()

    obv = SubElement(zag, 'Obveznik')
    SubElement(obv, 'OIB').text = company.oib or ''
    SubElement(obv, 'Naziv').text = company.name or ''
    SubElement(obv, 'Adresa').text = company.address or ''
    SubElement(obv, 'Mjesto').text = company.city or ''

    # Tijelo - racuni
    tijelo = SubElement(root, 'Tijelo')
    for e in entries:
        r = SubElement(tijelo, 'Racun')
        SubElement(r, 'R1').text = str(e['seq'])
        SubElement(r, 'R2').text = e['doc_number']
        SubElement(r, 'R3').text = e['doc_date'].isoformat() if e['doc_date'] else ''
        SubElement(r, 'R4').text = e['partner_name']
        SubElement(r, 'R5').text = e.get('partner_address', '')
        SubElement(r, 'R6').text = str(e.get('oib_type', 1))
        SubElement(r, 'R7').text = e['partner_oib']

        if book_type == 'URA':
            SubElement(r, 'R8').text = str(e['base_5'])
            SubElement(r, 'R9').text = str(e['base_13'])
            SubElement(r, 'R10').text = str(e['base_25'])
            SubElement(r, 'R11').text = str(e['total_with_vat'])
            SubElement(r, 'R12').text = str(e['total_vat'])
            SubElement(r, 'R13').text = str(e['vat_5'])
            SubElement(r, 'R14').text = '0'
            SubElement(r, 'R15').text = str(e['vat_13'])
            SubElement(r, 'R16').text = '0'
            SubElement(r, 'R17').text = str(e['vat_25'])
            SubElement(r, 'R18').text = '0'
            SubElement(r, 'R19').text = str(e['base_0'])
        else:
            SubElement(r, 'R6col').text = str(e['total_with_vat'])
            SubElement(r, 'R17').text = str(e['base_5'])
            SubElement(r, 'R18').text = str(e['vat_5'])
            SubElement(r, 'R19').text = str(e['base_13'])
            SubElement(r, 'R20').text = str(e['vat_13'])
            SubElement(r, 'R21').text = str(e['base_25'])
            SubElement(r, 'R22').text = str(e['vat_25'])

    xml_bytes = tostring(root, encoding='utf-8', xml_declaration=True)
    response = HttpResponse(xml_bytes, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename="%s_%s.xml"' % (book_type, period_label.replace('/', '-'))
    return response


def _knjiga_pdf(request, book_type, entries, totals, company, date_from, date_to, period_label):
    """Generira URA/IRA PDF — landscape A4."""
    import io
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse('xhtml2pdf not installed', status=500)

    html = render_to_string('documents/knjiga_ura_ira_pdf.html', {
        'entries': entries, 'totals': totals, 'book_type': book_type,
        'company': company, 'date_from': date_from, 'date_to': date_to,
        'period_label': period_label,
    })
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), result)
    if pdf.err:
        return HttpResponse('PDF error', status=500)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="%s_%s.pdf"' % (book_type, period_label.replace('/', '-'))
    return response



# ════════════════════════════════════════════════════════════
# QR SCAN — Remote skeniranje s mobitela
# ════════════════════════════════════════════════════════════
import uuid as _uuid
import redis as _redis
import qrcode as _qrcode
import io as _io
import base64 as _b64
import time as _time

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
    url = request.build_absolute_uri('/scan/%s/' % token)
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
    import json
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
    import json
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
# PDV OBRAZAC — Mjesečni/kvartalni zbirni izvještaj
# ════════════════════════════════════════════════════════════

@login_required
def pdv_obrazac(request):
    """PDV obrazac — Sekcija II (izlaz iz IRA) + Sekcija III (pretporez iz URA)."""
    from documents.models import ArhivaEntry, ConversionRecord
    from decimal import Decimal
    from datetime import date as _date

    company = get_user_company(request)

    # Staff moze birati firmu
    company_id = request.GET.get('company', '')
    all_companies = []
    if request.user.is_superuser or request.user.is_staff:
        from companies.models import Company
        from invoicing.models import Invoice as _Inv
        has_data = set(_Inv.objects.values_list('company_id', flat=True).distinct())
        has_ura = set(ArhivaEntry.objects.filter(source_type__in=['invoice_in','eracun','fiscal_cert']).values_list('company_id', flat=True).distinct())
        all_companies = list(Company.objects.filter(pk__in=has_data | has_ura).order_by('name'))
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except:
                pass

    if not company:
        return render(request, 'documents/pdv_obrazac.html', {'all_companies': all_companies})

    # Period
    year = int(request.GET.get('year', _date.today().year))
    month = request.GET.get('month', '')
    quarter = request.GET.get('quarter', '')

    date_from = _date(year, 1, 1)
    date_to = _date(year, 12, 31)
    period_label = str(year)
    period_type = 'yearly'

    if month and month.isdigit():
        m = int(month)
        if 1 <= m <= 12:
            from datetime import timedelta
            date_from = _date(year, m, 1)
            date_to = _date(year, m + 1, 1) - timedelta(days=1) if m < 12 else _date(year, 12, 31)
            period_label = '%02d/%d' % (m, year)
            period_type = 'monthly'
    elif quarter and quarter.isdigit():
        q = int(quarter)
        if 1 <= q <= 4:
            from datetime import timedelta
            date_from = _date(year, (q-1)*3+1, 1)
            end_m = q * 3
            date_to = _date(year, end_m + 1, 1) - timedelta(days=1) if end_m < 12 else _date(year, 12, 31)
            period_label = 'Q%d/%d' % (q, year)
            period_type = 'quarterly'

    D = Decimal

    # ── SEKCIJA II — Izlazni PDV (iz Invoice/IRA) ──
    try:
        from invoicing.models import Invoice
        ira_qs = Invoice.objects.filter(
            company=company,
            date_issued__year__gte=date_from.year,
            date_issued__year__lte=date_to.year,
            status__in=['confirmed','fiscalized','sent','paid','unpaid','overdue',
                        'CONFIRMED','FISCALIZED','SENT','PAID','UNPAID','OVERDUE'],
        )
        if period_type == 'monthly' and month:
            ira_qs = ira_qs.filter(date_issued__month=int(month))
        elif period_type == 'quarterly' and quarter:
            q = int(quarter)
            ira_qs = ira_qs.filter(date_issued__month__gte=(q-1)*3+1, date_issued__month__lte=q*3)

        sec2 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
                'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
                'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

        for inv in ira_qs:
            sub = inv.subtotal or D('0')
            tax_pct = float(inv.tax_percent or 0)
            tax_amt = inv.tax_amount or D('0')
            total = inv.total or D('0')

            if tax_pct >= 23:
                sec2['base_25'] += sub; sec2['vat_25'] += tax_amt
            elif tax_pct >= 10:
                sec2['base_13'] += sub; sec2['vat_13'] += tax_amt
            elif tax_pct >= 3:
                sec2['base_5'] += sub; sec2['vat_5'] += tax_amt
            else:
                sec2['base_0'] += sub

            sec2['total_base'] += sub
            sec2['total_vat'] += tax_amt
            sec2['total'] += total
            sec2['count'] += 1
    except ImportError:
        sec2 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
                'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
                'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

    # ── SEKCIJA III — Pretporez (iz ArhivaEntry/URA) ──
    ura_qs = ArhivaEntry.objects.filter(
        company=company,
        source_type__in=['invoice_in', 'eracun', 'fiscal_cert'],
        doc_date__gte=date_from,
        doc_date__lte=date_to,
    )

    sec3 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
            'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
            'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

    # Try to get extracted_data for VAT breakdown
    conv_map = {}
    conv_ids = [a.source_id.replace('conversion:','') for a in ura_qs if a.source_id and a.source_id.startswith('conversion:')]
    if conv_ids:
        for cr in ConversionRecord.objects.filter(id__in=conv_ids):
            conv_map[str(cr.id)] = cr.extracted_data or {}

    for a in ura_qs:
        amount = a.amount or D('0')
        if amount <= 0:
            continue

        # Try extracted_data for precise VAT
        conv_id = a.source_id.replace('conversion:','') if a.source_id and a.source_id.startswith('conversion:') else ''
        data = conv_map.get(conv_id, {})
        vat_bd = data.get('vat_breakdown', {})

        if vat_bd:
            sec3['base_25'] += D(str(vat_bd.get('base_25', 0)))
            sec3['vat_25'] += D(str(vat_bd.get('vat_25', 0)))
            sec3['base_13'] += D(str(vat_bd.get('base_13', 0)))
            sec3['vat_13'] += D(str(vat_bd.get('vat_13', 0)))
            sec3['base_5'] += D(str(vat_bd.get('base_5', 0)))
            sec3['vat_5'] += D(str(vat_bd.get('vat_5', 0)))
            sec3['base_0'] += D(str(vat_bd.get('base_0', 0)))
        else:
            # Default: assume 25% for Croatian invoices
            base = (amount / D('1.25')).quantize(D('0.01'))
            vat = amount - base
            sec3['base_25'] += base
            sec3['vat_25'] += vat

        sec3['total'] += amount
        sec3['count'] += 1

    sec3['total_base'] = sec3['base_0'] + sec3['base_5'] + sec3['base_13'] + sec3['base_25']
    sec3['total_vat'] = sec3['vat_5'] + sec3['vat_13'] + sec3['vat_25']

    # ── OBRAČUN — razlika izlaz - ulaz ──
    vat_payable = sec2['total_vat'] - sec3['total_vat']

    ctx = {
        'company': company,
        'year': year, 'month': month, 'quarter': quarter,
        'period_label': period_label, 'period_type': period_type,
        'date_from': date_from, 'date_to': date_to,
        'sec2': sec2, 'sec3': sec3,
        'vat_payable': vat_payable,
        'is_refund': vat_payable < 0,
        'all_companies': all_companies,
        'selected_company_id': str(company.pk),
        'years': list(range(_date.today().year, 2022, -1)),
    }

    fmt = request.GET.get('format', '')
    if fmt == 'pdf':
        return _pdv_pdf(request, ctx)
    if fmt == 'xml':
        return _pdv_xml(request, ctx)

    return render(request, 'documents/pdv_obrazac.html', ctx)


def _pdv_pdf(request, ctx):
    """PDF PDV obrasca."""
    import io as _io
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse('xhtml2pdf not installed', status=500)
    html = render_to_string('documents/pdv_obrazac_pdf.html', ctx)
    result = _io.BytesIO()
    pdf = pisa.pisaDocument(_io.BytesIO(html.encode('utf-8')), result)
    if pdf.err:
        return HttpResponse('PDF error', status=500)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="PDV_%s.pdf"' % ctx['period_label'].replace('/', '-')
    return response


def _pdv_xml(request, ctx):
    """XML PDV obrasca za ePorezna."""
    from django.http import HttpResponse
    from xml.etree.ElementTree import Element, SubElement, tostring

    ns = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/PDV/v2-0'
    root = Element('{%s}ObrazacPDV' % ns)
    root.set('verzijaSheme', '2.0')

    meta = SubElement(root, 'Metapodaci')
    SubElement(meta, 'Naslov').text = 'PDV obrazac'
    SubElement(meta, 'Autor').text = 'LIMIT Connect ERP'

    zag = SubElement(root, 'Zaglavlje')
    razd = SubElement(zag, 'Razdoblje')
    SubElement(razd, 'DatumOd').text = ctx['date_from'].isoformat()
    SubElement(razd, 'DatumDo').text = ctx['date_to'].isoformat()
    obv = SubElement(zag, 'Obveznik')
    co = ctx['company']
    SubElement(obv, 'OIB').text = co.oib or ''
    SubElement(obv, 'Naziv').text = co.name or ''

    # Sekcija II - Izlaz
    s2 = SubElement(root, 'Isporuke')
    for tag, key in [('II_1_Osnovica5', 'base_5'), ('II_1_PDV5', 'vat_5'),
                     ('II_2_Osnovica13', 'base_13'), ('II_2_PDV13', 'vat_13'),
                     ('II_3_Osnovica25', 'base_25'), ('II_3_PDV25', 'vat_25'),
                     ('II_Neoporezivo', 'base_0'), ('II_UkupnoIsporuke', 'total')]:
        SubElement(s2, tag).text = str(ctx['sec2'][key])

    # Sekcija III - Pretporez
    s3 = SubElement(root, 'Pretporez')
    for tag, key in [('III_1_Osnovica5', 'base_5'), ('III_1_Pretporez5', 'vat_5'),
                     ('III_2_Osnovica13', 'base_13'), ('III_2_Pretporez13', 'vat_13'),
                     ('III_3_Osnovica25', 'base_25'), ('III_3_Pretporez25', 'vat_25'),
                     ('III_UkupnoPretporez', 'total_vat')]:
        SubElement(s3, tag).text = str(ctx['sec3'][key])

    # Obveza
    obr = SubElement(root, 'Obracun')
    SubElement(obr, 'PDV_Obveza').text = str(max(ctx['vat_payable'], 0))
    SubElement(obr, 'PDV_Povrat').text = str(abs(min(ctx['vat_payable'], 0)))

    xml_bytes = tostring(root, encoding='utf-8', xml_declaration=True)
    response = HttpResponse(xml_bytes, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename="PDV_%s.xml"' % ctx['period_label'].replace('/', '-')
    return response

# ════════════════════════════════════════════════════════════
# FILE SERVE — Serve files from local storage
# ════════════════════════════════════════════════════════════

@login_required
def arhiva_file_serve(request, file_path):
    """Serve a file from MEDIA_ROOT."""
    import os
    import mimetypes
    from django.conf import settings

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
    import os
    from django.http import FileResponse, Http404

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
    from documents.models import DocumentBlob
    blob = DocumentBlob.objects.filter(
        company=entry.company,
        source_type=entry.source_type,
    ).first()
    if blob:
        from django.http import HttpResponse
        response = HttpResponse(blob.file_data, content_type=blob.content_type)
        response['Content-Disposition'] = f'attachment; filename="{blob.filename}"'
        return response

    raise Http404


# ═══════════════════════════════════════════════════════════════════════════════
# ARHIVA PDF PREVIEW — dodati na kraj /var/www/fina-connect/documents/views.py
# ═══════════════════════════════════════════════════════════════════════════════
#
# Novi URL-ovi za dodati u documents/urls.py:
#   path('arhiva/<int:pk>/preview/', views.arhiva_preview, name='arhiva_preview'),
#   path('arhiva/<int:pk>/thumbnail/', views.arhiva_thumbnail, name='arhiva_thumbnail'),
#

import fitz  # PyMuPDF — već instaliran


def _get_thumbnail_path(entry):
    """
    Vrati putanju do thumbnail JPG za ArhivaEntry.
    Format: media/thumbnails/arhiva/{pk}.jpg
    """
    import os
    from django.conf import settings
    thumb_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails', 'arhiva')
    os.makedirs(thumb_dir, exist_ok=True)
    return os.path.join(thumb_dir, f'{entry.pk}.jpg')


def _generate_thumbnail(entry, full_path, thumb_path):
    """
    Generiraj thumbnail (200x280px) od prve stranice PDF-a ili slike.
    Koristi PyMuPDF. Vraća True ako uspješno.
    """
    import os
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
        import logging
        logging.getLogger(__name__).warning(f'Thumbnail greška za entry {entry.pk}: {e}')
        return False


@login_required
def arhiva_thumbnail(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/thumbnail/
    Vrati thumbnail JPG za ArhivaEntry.
    Generira se pri prvom pozivu, cachira se na disku.
    Za zapise bez file_path — vrati placeholder ikonu.
    """
    import os
    from django.conf import settings
    from django.http import FileResponse, HttpResponse

    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if entry.company != company:
            return HttpResponse(status=403)

    thumb_path = _get_thumbnail_path(entry)

    # Cache hit — vrati cached thumbnail
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

            # source_id može biti 'invoice:pk', 'syn:uuid:num' ili samo broj
            # Uvijek fallback na doc_number + company
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
                # Privremeni fajl za PyMuPDF
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(pdf_content if isinstance(pdf_content, bytes) else pdf_content.read())
                    tmp_path = tmp.name

                success = _generate_thumbnail(entry, tmp_path, thumb_path)
                os.unlink(tmp_path)

                if success:
                    return FileResponse(open(thumb_path, 'rb'), content_type='image/jpeg')
        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            import logging
            logging.getLogger(__name__).warning(f'Invoice thumbnail greška: {e}')

    # Fallback — SVG placeholder s ikonom tipa dokumenta
    return _thumbnail_placeholder(entry)


def _thumbnail_placeholder(entry):
    """Vrati SVG placeholder s tipom dokumenta."""
    from django.http import HttpResponse

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


@login_required
def arhiva_preview(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/preview/
    Vrati PDF za inline pregled:
      - Za zapise s file_path → serviraj direktno
      - Za invoice_out → generiraj on-the-fly
      - Za ostalo → redirect na file_serve
    """
    import os
    from django.conf import settings
    from django.http import HttpResponse, FileResponse

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
                import mimetypes
                ct, _ = mimetypes.guess_type(full_path)
                return FileResponse(
                    open(full_path, 'rb'),
                    content_type=ct or 'image/jpeg',
                    headers={'Content-Disposition': 'inline'}
                )

    # 2. Invoice bez file_path → generiraj on-the-fly
    if entry.source_type == 'invoice_out' and entry.source_id:
        try:
            from invoicing.models import Invoice
            from invoicing.services.pdf_service import generate_invoice_pdf

            # source_id može biti 'invoice:pk', 'syn:uuid:num' ili samo broj
            # Uvijek fallback na doc_number + company
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
            import logging
            logging.getLogger(__name__).error(f'Invoice preview greška: {e}')

    # 3. Nema ništa
    return HttpResponse(
        '<html><body style="font-family:sans-serif;text-align:center;padding:3rem;color:#94a3b8">'
        '<p style="font-size:3rem">📄</p>'
        '<p>Pregled nije dostupan za ovaj tip dokumenta.</p>'
        '</body></html>',
        content_type='text/html',
        status=404
    )


@login_required
def arhiva_preview_info(request, pk):
    """
    GET /hr/documents/arhiva/{pk}/preview-info/
    JSON endpoint koji vraća preview_url i thumbnail_url za AJAX.
    Dodaje preview_url i thumbnail_url u detail response.
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


# ═══════════════════════════════════════════════════════════════════════════════
# ARHIVA PDF & XML DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def arhiva_download_pdf(request, pk):
    """Generiraj i preuzmi PDF za ArhivaEntry."""
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    company = get_user_company(request)
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser and entry.company != company:
        from django.http import Http404
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
    from django.http import HttpResponse
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom.minidom import parseString

    company = get_user_company(request)
    entry = get_object_or_404(ArhivaEntry.objects.unscoped(), pk=pk)

    if not request.user.is_superuser and entry.company != company:
        from django.http import Http404
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



# ═══════════════════════════════════════════════════════════════
# AI INBOX — 693 dokumenata ceka knjizenje
# ═══════════════════════════════════════════════════════════════

@login_required
def ai_inbox(request):
    """AI Inbox — svi dokumenti s AI prijedlogom koji nisu proknjizeni."""
    from documents.models import ArhivaEntry
    from django.db.models import Count, Sum

    is_superadmin = request.user.is_superuser
    if is_superadmin:
        qs = ArhivaEntry.objects.filter(is_booked=False).exclude(
            ai_proposal__isnull=True
        ).exclude(ai_proposal={}).select_related('company').order_by('-archived_at')
    else:
        company = get_user_company(request)
        if not company:
            return render(request, 'documents/ai_inbox.html', {'entries': [], 'stats': {}})
        qs = ArhivaEntry.objects.filter(
            company=company, is_booked=False
        ).exclude(ai_proposal__isnull=True).exclude(ai_proposal={}).order_by('-archived_at')

    # Filteri
    company_filter = request.GET.get('company', '')
    if company_filter and is_superadmin:
        qs = qs.filter(company_id=company_filter)

    # Stats
    total_pending = qs.count()
    by_company = qs.values('company__name', 'company__id').annotate(
        cnt=Count('id'), total_amt=Sum('amount')
    ).order_by('-cnt')

    # Paginacija
    page = int(request.GET.get('page', 1))
    per_page = 50
    entries = qs[(page-1)*per_page : page*per_page]
    has_next = qs.count() > page * per_page

    total_amount = qs.aggregate(t=Sum('amount'))['t'] or 0
    stats = {
        'total_pending': total_pending,
        'total_amount': total_amount,
        'company_count': by_company.count() if hasattr(by_company, 'count') else len(list(by_company)),
        'by_company': list(by_company),
    }

    if request.GET.get('format') == 'json':
        data = []
        for e in entries:
            data.append({
                'id': e.pk,
                'company': str(e.company),
                'company_id': str(e.company_id),
                'doc_number': e.doc_number,
                'partner_name': e.partner_name,
                'amount': float(e.amount) if e.amount else 0,
                'currency': e.currency,
                'doc_date': e.doc_date.isoformat() if e.doc_date else None,
                'source_type': e.source_type,
                'ai_proposal': e.ai_proposal,
                'is_booked': e.is_booked,
            })
        return JsonResponse({'entries': data, 'has_next': has_next, 'page': page, 'total': total_pending})

    return render(request, 'documents/ai_inbox.html', {
        'entries': entries,
        'stats': stats,
        'page': page,
        'has_next': has_next,
        'is_superadmin': is_superadmin,
    })


@login_required
@require_POST
def ai_inbox_accept(request, entry_id):
    """Prihvati AI prijedlog — proknjizi dokument."""
    from documents.models import ArhivaEntry
    entry = get_object_or_404(ArhivaEntry, pk=entry_id)

    # Security check
    if not request.user.is_superuser:
        company = get_user_company(request)
        if company and entry.company_id != company.pk:
            return JsonResponse({'error': 'Nemate pristup'}, status=403)

    entry.is_booked = True
    entry.save(update_fields=['is_booked'])

    # Opcionalno: kreiraj temeljnicu iz ai_proposal
    # TODO: ako zelimo auto-kreirati JournalEntry iz proposal

    return JsonResponse({'ok': True, 'id': entry.pk, 'message': 'Proknjizeno!'})


@login_required
@require_POST
def ai_inbox_bulk_accept(request):
    """Bulk prihvati sve AI prijedloge za odabranu firmu."""
    from documents.models import ArhivaEntry
    import json

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    company_id = data.get('company_id') or request.POST.get('company_id', '')
    if not company_id:
        return JsonResponse({'error': 'company_id required'}, status=400)

    # Security
    if not request.user.is_superuser:
        user_company = get_user_company(request)
        if user_company and str(user_company.pk) != str(company_id):
            return JsonResponse({'error': 'Nemate pristup'}, status=403)

    updated = ArhivaEntry.objects.filter(
        company_id=company_id, is_booked=False
    ).exclude(ai_proposal__isnull=True).exclude(ai_proposal={}).update(is_booked=True)

    return JsonResponse({'ok': True, 'count': updated, 'message': f'{updated} dokumenata proknjizeno!'})

@login_required
@require_POST
def ai_inbox_send_email(request):
    """Rucni trigger email sazetka za trenutnu kompaniju."""
    from documents.tasks import send_ai_inbox_summary_email
    company = get_user_company(request)
    if company:
        send_ai_inbox_summary_email.delay(company_id=company.pk)
    elif request.user.is_superuser:
        send_ai_inbox_summary_email.delay()
    return JsonResponse({'ok': True, 'message': 'Email sazetak je u redu cekanja'})



# ── ZADATAK 3: Paginated JSON za arhiva_list ──
@login_required
def arhiva_list_json(request):
    """JSON API za lazy load arhiva liste."""
    from documents.models import ArhivaEntry
    from django.db.models import Q

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
        })

    return JsonResponse({'entries': data, 'has_next': has_next, 'page': page})



# ═══════════════════════════════════════════════════════════════
# REVIZORSKI PAKET — ZIP export za reviziju
# ═══════════════════════════════════════════════════════════════

@login_required
def revizija_page(request):
    """Forma za generiranje revizorskog paketa."""
    from companies.models import Company
    if request.user.is_superuser:
        companies = Company.objects.all().order_by('name')
    else:
        company = get_user_company(request)
        companies = [company] if company else []
    return render(request, 'documents/revizija.html', {'companies': companies})


@login_required
@require_POST
def revizija_export(request):
    """Generiraj ZIP s kompletnim revizorskim paketom."""
    import zipfile, csv, io, os
    from documents.models import ArhivaEntry
    from invoicing.models import Invoice
    from companies.models import Company
    from django.conf import settings as _s
    from datetime import datetime

    company_id = request.POST.get('company_id', '')
    date_from = request.POST.get('date_from', '')
    date_to = request.POST.get('date_to', '')

    if not company_id or not date_from or not date_to:
        messages.error(request, 'Sva polja su obavezna.')
        return redirect('documents:revizija')

    company = get_object_or_404(Company, pk=company_id)

    # Security
    if not request.user.is_superuser:
        user_co = get_user_company(request)
        if not user_co or str(user_co.pk) != str(company_id):
            messages.error(request, 'Nemate pristup.')
            return redirect('documents:revizija')

    # Query entries
    entries = ArhivaEntry.objects.filter(
        company=company,
        doc_date__gte=date_from,
        doc_date__lte=date_to,
    ).order_by('doc_date', 'archive_number')

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 1. CSV Index
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf, delimiter=';')
        writer.writerow(['Arhivski broj', 'Vrsta', 'Broj dokumenta', 'Partner',
                         'Iznos', 'Valuta', 'Datum', 'ZKI', 'JIR', 'PDF'])
        for e in entries:
            writer.writerow([
                e.archive_number, e.source_type, e.doc_number,
                e.partner_name, str(e.amount), e.currency,
                e.doc_date.strftime('%d.%m.%Y') if e.doc_date else '',
                e.zki or '', e.jir or '',
                'DA' if e.has_pdf else 'NE',
            ])
        zf.writestr('INDEX.csv', csv_buf.getvalue())

        # 2. URA (ulazni racuni)
        ura = entries.filter(source_type__in=['invoice_in', 'eracun', 'purchase'])
        if ura.exists():
            ura_csv = io.StringIO()
            w = csv.writer(ura_csv, delimiter=';')
            w.writerow(['R.br.', 'Datum', 'Broj racuna', 'Dobavljac', 'Osnovica', 'PDV 25%', 'PDV 13%', 'PDV 5%', 'Ukupno'])
            for i, e in enumerate(ura, 1):
                total = float(e.amount or 0)
                # Dohvati pravi PDV iz Invoice ako postoji
                pdv25 = pdv13 = pdv5 = 0.0
                base = total
                try:
                    inv = Invoice.objects.get(pk=int(e.source_id))
                    for line in inv.lines.all():
                        rate = float(getattr(line, 'vat_rate', 25) or 25)
                        line_pdv = float(line.total or 0) - float(line.total or 0) / (1 + rate/100)
                        if rate >= 24:
                            pdv25 += line_pdv
                        elif rate >= 12:
                            pdv13 += line_pdv
                        else:
                            pdv5 += line_pdv
                    base = total - pdv25 - pdv13 - pdv5
                except Exception:
                    # Fallback: 25% standard
                    pdv25 = total - total / 1.25
                    base = total - pdv25
                w.writerow([i, e.doc_date, e.doc_number, e.partner_name,
                            f'{base:.2f}', f'{pdv25:.2f}', f'{pdv13:.2f}', f'{pdv5:.2f}', f'{total:.2f}'])
            zf.writestr('KNJIGA_URA.csv', ura_csv.getvalue())

        # 3. IRA (izlazni racuni)
        ira = entries.filter(source_type__in=['invoice_out'])
        if ira.exists():
            ira_csv = io.StringIO()
            w = csv.writer(ira_csv, delimiter=';')
            w.writerow(['R.br.', 'Datum', 'Broj racuna', 'Kupac', 'Osnovica', 'PDV 25%', 'PDV 13%', 'PDV 5%', 'Ukupno'])
            for i, e in enumerate(ira, 1):
                total = float(e.amount or 0)
                pdv25 = pdv13 = pdv5 = 0.0
                base = total
                try:
                    inv = Invoice.objects.get(pk=int(e.source_id))
                    for line in inv.lines.all():
                        rate = float(getattr(line, 'vat_rate', 25) or 25)
                        line_pdv = float(line.total or 0) - float(line.total or 0) / (1 + rate/100)
                        if rate >= 24:
                            pdv25 += line_pdv
                        elif rate >= 12:
                            pdv13 += line_pdv
                        else:
                            pdv5 += line_pdv
                    base = total - pdv25 - pdv13 - pdv5
                except Exception:
                    pdv25 = total - total / 1.25
                    base = total - pdv25
                w.writerow([i, e.doc_date, e.doc_number, e.partner_name,
                            f'{base:.2f}', f'{pdv25:.2f}', f'{pdv13:.2f}', f'{pdv5:.2f}', f'{total:.2f}'])
            zf.writestr('KNJIGA_IRA.csv', ira_csv.getvalue())

        # 4. PDV summary
        from django.db.models import Sum
        total_in = ura.aggregate(t=Sum('amount'))['t'] or 0
        total_out = ira.aggregate(t=Sum('amount'))['t'] or 0
        # Approx PDV at standard 25% rate (real rates in CSV files)
        pdv_in = float(total_in) - float(total_in) / 1.25
        pdv_out = float(total_out) - float(total_out) / 1.25
        pdv_diff = pdv_out - pdv_in

        pdv_txt = f"""PDV PREGLED
Tvrtka: {company.name}
OIB: {company.oib}
Period: {date_from} — {date_to}

IZLAZNI RACUNI (IRA):
  Ukupno: {float(total_out):,.2f} EUR
  PDV (approx): {pdv_out:,.2f} EUR
  Broj racuna: {ira.count()}

ULAZNI RACUNI (URA):
  Ukupno: {float(total_in):,.2f} EUR
  PDV (approx): {pdv_in:,.2f} EUR
  Broj racuna: {ura.count()}

RAZLIKA PDV:
  Za uplatu: {pdv_diff:,.2f} EUR
  (Pozitivno = za uplatu, Negativno = pretplata)

Generirano: {datetime.now().strftime('%d.%m.%Y %H:%M')}
LIMIT Connect ERP
"""
        zf.writestr('PDV_PREGLED.txt', pdv_txt)

        # 5. PDF fakture
        pdf_count = 0
        for e in entries.filter(has_pdf=True, file_path__isnull=False).exclude(file_path=''):
            full_path = os.path.join(_s.MEDIA_ROOT, e.file_path)
            if os.path.isfile(full_path):
                arcname = f'PDF/{e.source_type}/{e.archive_number}.pdf'
                zf.write(full_path, arcname)
                pdf_count += 1

        # 6. Summary
        summary = f"""REVIZORSKI PAKET — {company.name}
Period: {date_from} do {date_to}
Generirano: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Sadrzaj:
- INDEX.csv — {entries.count()} dokumenata
- KNJIGA_URA.csv — {ura.count()} ulaznih racuna
- KNJIGA_IRA.csv — {ira.count()} izlaznih racuna
- PDV_PREGLED.txt — PDV summary
- PDF/ — {pdf_count} PDF faktura

LIMIT Connect ERP — limit-connect.com
"""
        zf.writestr('README.txt', summary)

    buf.seek(0)
    filename = f'revizija_{company.oib or company.pk}_{date_from}_{date_to}.zip'

    zip_bytes = buf.read()

    # Email opcija
    send_email = request.POST.get('send_email', '')
    if send_email:
        try:
            from django.core.mail import EmailMessage as _EM
            email_to = request.POST.get('email_to', '').strip()
            if not email_to:
                email_to = getattr(company, 'email', '') or ''
            if email_to and '@' in email_to:
                em = _EM(
                    subject=f'Revizorski paket — {company.name} ({date_from} do {date_to})',
                    body=f'U prilogu je revizorski paket za {company.name}.\nPeriod: {date_from} — {date_to}\n\nLIMIT Connect ERP',
                    to=[email_to],
                )
                em.attach(filename, zip_bytes, 'application/zip')
                em.send()
                messages.success(request, f'ZIP poslan na {email_to}')
        except Exception as mail_err:
            import logging
            logging.getLogger('documents').warning('Revizija email: %s', mail_err)
            messages.warning(request, f'ZIP generiran, ali email slanje nije uspjelo: {mail_err}')

    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



# ═══════════════════════════════════════════════════════════════
# SMART AUTOCOMPLETE — pretraga dok korisnik tipka
# ═══════════════════════════════════════════════════════════════

@login_required
def arhiva_autocomplete(request):
    """JSON autocomplete za arhiva pretragu. Max 8 rezultata."""
    from documents.models import ArhivaEntry
    from django.db.models import Q

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



@login_required
@require_POST
def arhiva_delete_entry(request, pk):
    """AJAX: Obrisi arhivski zapis. Instant delete bez refresha."""
    from django.http import JsonResponse
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


def arhiva_upute(request):
    """Public guide page for archive module — no login required."""
    return render(request, "documents/arhiva_upute.html")


def arhiva_guide_pdf(request):
    """Printable A4 guide for archive module."""
    return render(request, "documents/arhiva_guide_pdf.html")


@login_required
def verfahrensdokumentation(request):
    """Verfahrensdokumentation page — online signature, download, call buttons."""
    company = get_user_company(request)
    return render(request, 'documents/verfahrensdokumentation.html', {
        'company': company,
    })


@login_required
@require_POST
def verfahren_sign(request):
    """Accept digital signature for Verfahrensdokumentation."""
    from django.http import JsonResponse
    import json as json_lib
    company = get_user_company(request)
    data = json_lib.loads(request.body)

    signature_b64 = data.get('signature', '')
    signer_name = data.get('signer_name', '')

    if not signature_b64 or not signer_name:
        return JsonResponse({'error': 'Potpis i ime su obavezni'}, status=400)

    # Audit trail — pravno neoboriv potpis
    import hashlib
    # SHA-256 hash verzije dokumenta u trenutku potpisa
    doc_path = '/var/www/fina-connect/docs/Verfahrensdokumentation_LIMIT_Connect.md'
    try:
        with open(doc_path, 'rb') as df:
            doc_hash = hashlib.sha256(df.read()).hexdigest()
    except Exception:
        doc_hash = 'FILE_NOT_FOUND'

    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]

    from documents.models import ArhivaEntry

    # Duplicate check
    existing = ArhivaEntry.objects.filter(
        company=company, source_type='verfahren_sign',
    ).first()
    if existing:
        return JsonResponse({
            'ok': True,
            'message': 'Dokument je vec potpisan (%s).' % existing.doc_date,
            'already_signed': True,
        })

    entry = ArhivaEntry(
        company=company,
        source_type='verfahren_sign',
        source_id='verfahren_%s_%s' % (request.user.pk, doc_hash[:8]),
        doc_number='VD-%s' % timezone.now().strftime('%Y%m%d'),
        partner_name=signer_name,
        amount=0,
        currency='EUR',
        doc_date=timezone.now().date(),
    )
    entry.save()

    # Store audit trail metadata
    try:
        from superadmin_ai.models import PendingAIAction
        PendingAIAction.objects.create(
            company=company,
            module='verfahren_sign',
            action_type='audit_signature',
            description='Verfahrensdokumentation potpisan: %s (%s)' % (signer_name, company.name),
            payload={
                'signer_name': signer_name,
                'client_ip': client_ip,
                'user_agent': user_agent,
                'document_hash': doc_hash,
                'timestamp': str(timezone.now()),
                'entry_id': entry.pk,
            },
            status='completed',
        )
    except Exception:
        pass

    # Save signature image
    import base64, os
    sig_dir = os.path.join('/var/www/fina-connect/media/signatures')
    os.makedirs(sig_dir, exist_ok=True)
    sig_path = os.path.join(sig_dir, 'verfahren_%s_%s.png' % (company.oib, timezone.now().strftime('%Y%m%d_%H%M%S')))
    with open(sig_path, 'wb') as f:
        f.write(base64.b64decode(signature_b64.split(',')[1] if ',' in signature_b64 else signature_b64))

    # Save immutable PDF snapshot of document version
    try:
        import markdown as md_lib
        from weasyprint import HTML as WeasyprintHTML
        doc_md = '/var/www/fina-connect/docs/Verfahrensdokumentation_LIMIT_Connect.md'
        pdf_path = sig_path.replace('.png', '_document.pdf')
        html_content = '<html><body style="font-family:Arial;max-width:800px;margin:auto;padding:20px">'
        with open(doc_md) as md_f:
            html_content += md_lib.markdown(md_f.read(), extensions=['tables'])
        html_content += '<hr><p>Unterzeichnet von: %s<br>Datum: %s<br>IP: %s<br>Dokument-Hash: %s</p>' % (
            signer_name, str(timezone.now()), client_ip, doc_hash)
        html_content += '</body></html>'
        WeasyprintHTML(string=html_content).write_pdf(pdf_path)
    except Exception as e:
        logging.getLogger('documents').warning('Immutable PDF failed: %s', e)

    return JsonResponse({
        'ok': True,
        'message': 'Verfahrensdokumentation erfolgreich unterzeichnet.',
        'entry_id': entry.pk,
    })

