"""
eracun/views_inbox.py
Views for receiving e-invoices — upload, API, dashboard.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from core.company_utils import get_user_company


@login_required
def inbox_dashboard(request):
    """Dashboard for incoming e-invoices."""
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    from .models import ERacun
    incoming = ERacun.objects.filter(company=company, direction='incoming').order_by('-received_at')

    stats = {
        'total': incoming.count(),
        'unbooked': incoming.filter(is_booked=False).count(),
        'booked': incoming.filter(is_booked=True).count(),
        'this_month': incoming.filter(
            received_at__year=2026, received_at__month=3
        ).count(),
    }

    return render(request, 'eracun/inbox.html', {
        'incoming': incoming[:50],
        'stats': stats,
    })


@login_required
@require_POST
def inbox_upload(request):
    """Upload UBL XML file as incoming e-invoice."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=400)

    xml_file = request.FILES.get('xml_file')
    if not xml_file:
        messages.error(request, 'Odaberite XML datoteku.')
        return redirect('eracun:inbox')

    try:
        xml_string = xml_file.read().decode('utf-8')
    except UnicodeDecodeError:
        xml_string = xml_file.read().decode('utf-8-sig', errors='replace')

    from .services.inbox import receive_eracun
    result = receive_eracun(company, xml_string, received_via='upload', user=request.user)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, _('Radnja nije uspjela. Pokušajte ponovo.'))

    return redirect('eracun:inbox')


@login_required
def inbox_detail(request, pk):
    """Detail view for an incoming e-invoice."""
    from .models import ERacun
    eracun = get_object_or_404(ERacun, pk=pk, direction='incoming')
    return render(request, 'eracun/inbox_detail.html', {
        'eracun': eracun,
        'items': eracun.items.all(),
        'tax_summaries': eracun.tax_summaries.all(),
        'logs': eracun.logs.all()[:20],
    })


@login_required
@require_POST
def inbox_book(request, pk):
    """Book incoming e-invoice into URA (create purchase invoice)."""
    from .models import ERacun, ERacunLog
    from invoicing.models import Invoice, InvoiceItem
    from partners.models import Partner

    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, direction='incoming', company=company)

    if eracun.is_booked:
        messages.warning(request, 'Vec proknjizeno.')
        return redirect('eracun:inbox_detail', pk=pk)

    # Find or create supplier partner
    partner = None
    if eracun.issuer_oib:
        partner = Partner.objects.filter(company=company, oib=eracun.issuer_oib).first()
    if not partner:
        partner = Partner.objects.filter(company=company, name__icontains=eracun.issuer_name[:20]).first()
    if not partner:
        partner = Partner.objects.create(
            company=company,
            name=eracun.issuer_name,
            oib=eracun.issuer_oib or f'ER-{eracun.invoice_number[:8]}',
            address=eracun.issuer_address,
            city=eracun.issuer_city,
            partner_type='supplier',
        )

    # Create purchase invoice (URA)
    inv = Invoice.objects.create(
        company=company,
        doctype='URA',
        country=eracun.issuer_country or 'HR',
        number=f'URA-{eracun.invoice_number}',
        date_issued=eracun.issue_date,
        date_due=eracun.due_date,
        client_name=eracun.issuer_name,
        client_address=eracun.issuer_address,
        client_city=eracun.issuer_city,
        client_oib=eracun.issuer_oib,
        subtotal=eracun.subtotal,
        tax_amount=eracun.tax_amount,
        total=eracun.total,
        status='CONFIRMED',
        source='eracun',
        partner=partner,
        note=f'Uvezeno iz e-Racuna: {eracun.invoice_number}',
        created_by=request.user,
    )

    for item in eracun.items.all():
        InvoiceItem.objects.create(
            invoice=inv,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit_code,
            unit_price=item.unit_price,
            total_price=item.line_total,
            tax_rate=item.tax_rate,
        )

    # Mark as booked
    eracun.is_booked = True
    eracun.booked_invoice = inv
    eracun.save(update_fields=['is_booked', 'booked_invoice'])

    ERacunLog.objects.create(
        eracun=eracun,
        action='booked',
        status='accepted',
        message=f'Proknjizeno kao {inv.number}',
        details={'invoice_id': inv.pk, 'invoice_number': inv.number},
        user=request.user,
    )

    messages.success(request, f'Proknjizeno kao {inv.number}')
    return redirect('eracun:inbox_detail', pk=pk)


# === API ENDPOINT — for external systems to send e-invoices ===

@csrf_exempt
@require_POST
def api_receive(request):
    """
    API endpoint for receiving e-invoices.
    POST /eracun/api/receive/
    Header: Authorization: Bearer <api_key>
    Body: raw UBL XML
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return JsonResponse({'error': 'Missing Authorization header'}, status=401)

    api_key = auth[7:]
    from .models import ERacunConfig
    config = ERacunConfig.objects.filter(api_key=api_key, api_enabled=True).first()
    if not config:
        return JsonResponse({'error': 'Invalid API key'}, status=403)

    content_type = request.content_type or ''
    if 'xml' in content_type or 'text' in content_type:
        xml_string = request.body.decode('utf-8')
    elif 'json' in content_type:
        try:
            body = json.loads(request.body)
            xml_string = body.get('xml', '')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        xml_string = request.body.decode('utf-8')

    if not xml_string:
        return JsonResponse({'error': 'Empty body'}, status=400)

    from .services.inbox import receive_eracun
    result = receive_eracun(config.company, xml_string, received_via='api')

    if result['success']:
        return JsonResponse({
            'success': True,
            'id': str(result['eracun'].id),
            'message': result['message'],
        }, status=201)
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Unknown error'),
        }, status=400)
