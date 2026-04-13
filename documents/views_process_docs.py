"""Process Documents Views — Otpremnica, Primka, Otkupni, CMR, doc_confirm."""
import io
from datetime import date

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist

from core.company_utils import get_user_company
from partners.models import Partner

from .models import (
    CMR, CMRItem, OtkupniBlok, OtkupniBlokItem, Otpremnica, OtpremnicaItem,
)

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
    except DatabaseError:
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
    messages.error(request, _("Dokument nije pronađen."))
    return redirect('/documents/')


# ── OTPREMNICA ──
@login_required
def otpremnica_list(request):
    return _doc_list(request, Otpremnica, 'documents/process_list.html', 'Otpremnice')

@login_required
def otpremnica_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
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
                    except ObjectDoesNotExist:
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
    except DatabaseError:
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
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
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
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
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
