"""
Client/Partner Portal — Token-based, no login required.
"""
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, Count
from .models import Partner


def _get_partner(token):
    return get_object_or_404(Partner, portal_token=token)


def portal_home(request, token):
    partner = _get_partner(token)
    from invoicing.models import Invoice
    from projects.models import Project
    from documents.models import Document

    invoices = Invoice.objects.filter(partner=partner).order_by('-date_issued')
    projects = Project.objects.filter(client=partner)
    documents = Document.objects.filter(partner=partner)

    inv_total = invoices.filter(status='PAID').aggregate(s=Sum('total'))['s'] or 0
    inv_open = invoices.exclude(status__in=['PAID', 'STORNO', 'CANCELLED']).aggregate(s=Sum('total'))['s'] or 0

    return render(request, 'portal/home.html', {
        'partner': partner,
        'token': token,
        'invoices_recent': invoices[:5],
        'invoices_count': invoices.count(),
        'inv_total': inv_total,
        'inv_open': inv_open,
        'projects': projects,
        'projects_count': projects.count(),
        'documents_count': documents.count(),
    })


def portal_invoices(request, token):
    partner = _get_partner(token)
    from invoicing.models import Invoice
    invoices = Invoice.objects.filter(partner=partner).order_by('-date_issued')
    return render(request, 'portal/invoices.html', {
        'partner': partner,
        'token': token,
        'invoices': invoices,
    })


def portal_invoice_detail(request, token, pk):
    partner = _get_partner(token)
    from invoicing.models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    # Accept / Reject
    if request.method == 'POST' and invoice.status in ('DRAFT', 'SENT'):
        action = request.POST.get('action')
        if action == 'accept':
            invoice.status = 'ACCEPTED'
            invoice.save(update_fields=['status'])
        elif action == 'reject':
            invoice.status = 'REJECTED'
            invoice.save(update_fields=['status'])
        from django.shortcuts import redirect
        return redirect('portal_invoice_detail', token=token, pk=pk)

    return render(request, 'portal/invoice_detail.html', {
        'partner': partner,
        'token': token,
        'invoice': invoice,
        'items': invoice.items.all(),
    })


def portal_invoice_pdf(request, token, pk):
    """Download invoice PDF without requiring login."""
    partner = _get_partner(token)
    from invoicing.models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    # Try to generate PDF inline
    try:
        from django.template.loader import render_to_string
        from weasyprint import HTML
        html_string = render_to_string('invoicing/invoice_form.html', {
            'invoice': invoice,
            'items': invoice.items.all(),
        })
        pdf = HTML(string=html_string).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice.number}.pdf"'
        return response
    except ImportError:
        # weasyprint not available — fallback: serve the invoice page as HTML
        return render(request, 'portal/invoice_detail.html', {
            'partner': partner,
            'token': token,
            'invoice': invoice,
            'items': invoice.items.all(),
        })


def portal_projects(request, token):
    partner = _get_partner(token)
    from projects.models import Project
    projects = Project.objects.filter(client=partner)
    return render(request, 'portal/projects.html', {
        'partner': partner,
        'token': token,
        'projects': projects,
    })


def portal_documents(request, token):
    partner = _get_partner(token)
    from documents.models import Document
    documents = Document.objects.filter(partner=partner).order_by('-date_issued')
    return render(request, 'portal/documents.html', {
        'partner': partner,
        'token': token,
        'documents': documents,
    })


def send_portal_link(request, partner_id):
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    if not request.user.is_authenticated:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    partner = get_object_or_404(Partner, pk=partner_id)
    if not partner.email:
        messages.error(request, f"Partner {partner.name} nema email adresu!")
        return redirect(request.META.get("HTTP_REFERER", "/partners/"))
    portal_url = request.build_absolute_uri(f"/portal/{partner.portal_token}/")
    subject = "Vas klijentski portal - Viskovic Bau"
    html_msg = render_to_string("portal/magic_link_email.html", {
        "partner": partner, "portal_url": portal_url,
        "sender_name": request.user.get_full_name() or "Viskovic Bau",
    })
    try:
        send_mail(subject=subject, message=f"Portal: {portal_url}",
                  from_email="viskovic.bau@gmail.com",
                  recipient_list=[partner.email], html_message=html_msg, fail_silently=False)
        messages.success(request, f"Portal link poslan na {partner.email}")
    except Exception as e:
        messages.error(request, f"Greska: {e}")
    return redirect(request.META.get("HTTP_REFERER", "/partners/"))


def send_portal_whatsapp(request, partner_id):
    from django.contrib import messages
    from django.shortcuts import redirect
    from core.whatsapp import send_text, normalize_phone, is_gateway_healthy
    if not request.user.is_authenticated:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    partner = get_object_or_404(Partner, pk=partner_id)
    phone = getattr(partner, "phone", "") or getattr(partner, "contact_phone", "") or ""
    if not phone or not normalize_phone(phone):
        messages.error(request, f"Partner nema validan WhatsApp broj.")
        return redirect(request.META.get("HTTP_REFERER", "/partners/"))
    if not is_gateway_healthy():
        messages.error(request, "WhatsApp gateway nije dostupan.")
        return redirect(request.META.get("HTTP_REFERER", "/partners/"))
    portal_url = request.build_absolute_uri(f"/portal/{partner.portal_token}/")
    sender = request.user.get_full_name() or "Viskovic Bau"
    msg = (
        f"Guten Tag,\n\n"
        f"*{sender}* hat Ihnen Zugang zu Ihrem Kundenportal eingerichtet.\n\n"
        f"Angebote, Rechnungen und Bestaetigung direkt:\n{portal_url}\n\nViskovic Bau"
    )
    result = send_text(phone, msg)
    if result["success"]:
        messages.success(request, f"WhatsApp poslan na {phone}")
    else:
        messages.error(request, f"Greska: {result["error"]}")
    return redirect(request.META.get("HTTP_REFERER", "/partners/"))


# ═══════════════════════════════════════════════════
#  DRAG & DROP UPLOAD
# ═══════════════════════════════════════════════════

def portal_upload(request, token):
    """Drag&drop document upload for clients."""
    partner = _get_partner(token)
    from documents.models import Document
    from django.utils import timezone

    if request.method == 'POST':
        files = request.FILES.getlist('files')
        uploaded = 0
        for f in files:
            # Security: max 20MB, only safe extensions
            if f.size > 20 * 1024 * 1024:
                continue
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext not in ('pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'xls', 'csv', 'doc', 'docx', 'xml'):
                continue

            Document.objects.create(
                company=partner.company,
                partner=partner,
                doc_type='bill',
                doc_number=f'UPLOAD-{timezone.now().strftime("%Y%m%d%H%M%S")}-{uploaded+1}',
                date_issued=timezone.now().date(),
                file=f,
                total_amount=0,
            )
            uploaded += 1

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'uploaded': uploaded})
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.success(request, f'{uploaded} dokument(a) uploadano.')
        return redirect('portal_documents', token=token)

    return render(request, 'portal/upload.html', {
        'partner': partner,
        'token': token,
    })


# ═══════════════════════════════════════════════════
#  ONE-TAP PDV APPROVE
# ═══════════════════════════════════════════════════

def portal_pdv_approve(request, token, pk):
    """One-tap PDV approval for invoices."""
    partner = _get_partner(token)
    from invoicing.models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    if request.method == 'POST':
        action = request.POST.get('action', 'approve')
        if action == 'approve' and invoice.status in ('DRAFT', 'SENT', 'ACCEPTED'):
            invoice.tax_status = 'approved'
            invoice.status = 'ACCEPTED'
            invoice.internal_note = (invoice.internal_note or '') + f'\nPDV odobren via portal {__import__("django.utils.timezone", fromlist=["now"]).now().isoformat()}'
            invoice.save(update_fields=['tax_status', 'status', 'internal_note'])
        elif action == 'reject':
            invoice.tax_status = 'rejected'
            invoice.internal_note = (invoice.internal_note or '') + f'\nPDV odbijen via portal'
            invoice.save(update_fields=['tax_status', 'internal_note'])

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': invoice.status, 'tax_status': invoice.tax_status})
        from django.shortcuts import redirect
        return redirect('portal_invoice_detail', token=token, pk=pk)

    return render(request, 'portal/invoice_detail.html', {
        'partner': partner,
        'token': token,
        'invoice': invoice,
        'items': invoice.items.all(),
    })
