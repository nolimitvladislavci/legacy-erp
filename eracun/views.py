"""e-Racun views — dashboard, settings, API endpoints."""
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from core.company_utils import get_user_company
from .models import ERacun, ERacunConfig, ERacunLog, ERacunItem, ERacunTaxSummary

logger = logging.getLogger('eracun.views')


@login_required
def dashboard(request):
    """e-Racun dashboard with stats and recent invoices."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    eracuni = ERacun.objects.filter(company=company)
    stats = eracuni.aggregate(
        total_count=Count('id'),
        accepted=Count('id', filter=Q(status='accepted')),
        rejected=Count('id', filter=Q(status='rejected')),
        errors=Count('id', filter=Q(status='error')),
        draft=Count('id', filter=Q(status='draft')),
        pending=Count('id', filter=Q(status__in=['validating', 'signing', 'sending', 'sent'])),
        accepted_amount=Sum('total', filter=Q(status='accepted')),
    )

    recent = eracuni[:20]

    config = ERacunConfig.objects.filter(company=company).first()

    return render(request, 'eracun/dashboard.html', {
        'stats': stats,
        'eracuni': recent,
        'config': config,
    })


@login_required
def settings_view(request):
    """Configure e-Racun settings."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    config, created = ERacunConfig.objects.get_or_create(company=company)

    if request.method == 'POST':
        config.is_active = request.POST.get('is_active') == 'on'
        config.cert_password = request.POST.get('cert_password', '').strip()
        config.cert_oib = request.POST.get('cert_oib', '').strip()
        config.oznaka_prostora = request.POST.get('oznaka_prostora', 'P1').strip()
        config.oznaka_uredjaja = request.POST.get('oznaka_uredjaja', '1').strip()
        config.use_test_env = request.POST.get('use_test_env') == 'on'
        config.auto_send = request.POST.get('auto_send') == 'on'
        config.api_enabled = request.POST.get('api_enabled') == 'on'

        if 'cert_p12' in request.FILES:
            config.cert_p12 = request.FILES['cert_p12']

        config.save()
        messages.success(request, 'Postavke e-Racuna spremljene.')
        return redirect('eracun:settings')

    return render(request, 'eracun/settings.html', {'config': config})


@login_required
def detail(request, pk):
    """View e-Racun details with logs and XML."""
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)
    logs = eracun.logs.all()
    items = eracun.items.all()
    tax_summaries = eracun.tax_summaries.all()

    return render(request, 'eracun/detail.html', {
        'eracun': eracun,
        'logs': logs,
        'items': items,
        'tax_summaries': tax_summaries,
    })


@login_required
@require_POST
def send_eracun(request, pk):
    """Send e-Racun to FINA."""
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)

    if eracun.status in ('accepted', 'archived'):
        messages.warning(request, 'Ovaj e-Racun je vec poslan.')
        return redirect('eracun:detail', pk=pk)

    from .services.engine import process_eracun
    success, message = process_eracun(eracun, user=request.user)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect('eracun:detail', pk=pk)


@login_required
@require_POST
def create_from_invoice(request, invoice_pk):
    """Create e-Racun from existing Invoice."""
    from invoicing.models import Invoice
    company = get_user_company(request)
    invoice = get_object_or_404(Invoice, pk=invoice_pk, company=company)

    # Check if already has eracun
    if hasattr(invoice, 'eracun') and invoice.eracun:
        messages.info(request, 'Ovaj racun vec ima e-Racun.')
        return redirect('eracun:detail', pk=invoice.eracun.pk)

    from .services.engine import create_eracun_from_invoice
    eracun = create_eracun_from_invoice(invoice, user=request.user)

    ERacunLog.objects.create(
        eracun=eracun, action='created', status='draft',
        message=f'Kreiran iz fakture {invoice.number}',
        user=request.user
    )

    messages.success(request, f'e-Racun kreiran: {eracun.invoice_number}')
    return redirect('eracun:detail', pk=eracun.pk)


@login_required
def download_xml(request, pk):
    """Download UBL 2.1 XML."""
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)

    from .services.ubl_generator import generate_ubl_xml
    xml_bytes = generate_ubl_xml(eracun)

    response = HttpResponse(xml_bytes, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="eracun_{eracun.invoice_number}.xml"'
    return response


@login_required
def download_fina_xml(request, pk):
    """Download FINA request/response XML."""
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)

    xml_type = request.GET.get('type', 'request')
    content = eracun.xml_request if xml_type == 'request' else eracun.xml_response

    if not content:
        messages.warning(request, 'Nema XML-a za preuzimanje.')
        return redirect('eracun:detail', pk=pk)

    response = HttpResponse(content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="fina_{xml_type}_{eracun.invoice_number}.xml"'
    return response


# ============================================================
# API endpoints (for external clients via API key)
# ============================================================

def _api_auth(request):
    """Authenticate API request by API key. Returns (config, error_response)."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, JsonResponse({'error': 'Missing Authorization header'}, status=401)

    api_key = auth[7:]
    try:
        config = ERacunConfig.objects.select_related('company').get(
            api_key=api_key, api_enabled=True, is_active=True
        )
        return config, None
    except ERacunConfig.DoesNotExist:
        return None, JsonResponse({'error': 'Invalid API key'}, status=403)


@csrf_exempt
@require_POST
def api_create(request):
    """
    External API: Create and optionally send e-Racun.

    POST /eracun/api/create/
    Authorization: Bearer <api_key>
    Body: JSON with invoice data
    """
    config, error = _api_auth(request)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Create ERacun from API data
    from decimal import Decimal as D
    try:
        er = ERacun.objects.create(
            company=config.company,
            doc_type=data.get('doc_type', '380'),
            invoice_number=data['invoice_number'],
            issue_date=data.get('issue_date', timezone.now().date()),
            delivery_date=data.get('delivery_date'),
            due_date=data.get('due_date'),
            currency=data.get('currency', 'EUR'),
            issuer_name=data.get('issuer_name', config.company.name),
            issuer_oib=data.get('issuer_oib', config.cert_oib),
            issuer_address=data.get('issuer_address', ''),
            issuer_iban=data.get('issuer_iban', ''),
            recipient_name=data['recipient_name'],
            recipient_oib=data['recipient_oib'],
            recipient_address=data.get('recipient_address', ''),
            recipient_city=data.get('recipient_city', ''),
            recipient_country=data.get('recipient_country', 'HR'),
            subtotal=D(str(data.get('subtotal', 0))),
            tax_amount=D(str(data.get('tax_amount', 0))),
            total=D(str(data.get('total', 0))),
            payment_means_code=data.get('payment_means_code', '30'),
            payment_reference=data.get('payment_reference', ''),
            note=data.get('note', ''),
        )

        # Create items
        for idx, item in enumerate(data.get('items', []), 1):
            ERacunItem.objects.create(
                eracun=er,
                line_number=idx,
                description=item['description'],
                quantity=D(str(item.get('quantity', 1))),
                unit_code=item.get('unit_code', 'EA'),
                unit_price=D(str(item['unit_price'])),
                line_total=D(str(item.get('line_total', item['unit_price']))),
                tax_category=item.get('tax_category', 'S'),
                tax_rate=D(str(item.get('tax_rate', 25))),
            )

        # Create tax summaries
        for ts in data.get('tax_summaries', []):
            ERacunTaxSummary.objects.create(
                eracun=er,
                tax_category=ts.get('tax_category', 'S'),
                tax_rate=D(str(ts.get('tax_rate', 25))),
                taxable_amount=D(str(ts['taxable_amount'])),
                tax_amount=D(str(ts['tax_amount'])),
            )

        result = {
            'id': str(er.pk),
            'invoice_number': er.invoice_number,
            'status': er.status,
        }

        # Auto-send if requested or config says so
        if data.get('auto_send', False) or config.auto_send:
            from .services.engine import process_eracun
            success, message = process_eracun(er, config=config)
            result['status'] = er.status
            result['message'] = message

        return JsonResponse(result, status=201)

    except KeyError as e:
        return JsonResponse({'error': f'Missing field: {e}'}, status=400)
    except Exception as e:
        logger.error(f'API create error: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def api_status(request, pk):
    """External API: Get e-Racun status."""
    config, error = _api_auth(request)
    if error:
        return error

    er = get_object_or_404(ERacun, pk=pk, company=config.company)
    return JsonResponse({
        'id': str(er.pk),
        'invoice_number': er.invoice_number,
        'status': er.status,
        'error_message': er.error_message,
        'fina_uuid': er.fina_uuid,
        'sent_at': er.sent_at.isoformat() if er.sent_at else None,
        'accepted_at': er.accepted_at.isoformat() if er.accepted_at else None,
    })


@csrf_exempt
def api_list(request):
    """External API: List e-Racuni."""
    config, error = _api_auth(request)
    if error:
        return error

    qs = ERacun.objects.filter(company=config.company)

    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    limit = min(int(request.GET.get('limit', 50)), 200)
    qs = qs[:limit]

    return JsonResponse({
        'results': [
            {
                'id': str(er.pk),
                'invoice_number': er.invoice_number,
                'recipient': er.recipient_name,
                'total': str(er.total),
                'status': er.status,
                'created_at': er.created_at.isoformat(),
            }
            for er in qs
        ]
    })



@login_required
def download_zugferd(request, pk):
    """Download ZUGFeRD 2.2 PDF (hybrid: PDF + embedded factur-x.xml)."""
    from django.http import HttpResponse
    from .models import ERacun
    from core.company_utils import get_user_company
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)

    from eracun.services.zugferd import generate_zugferd_pdf
    pdf_bytes = generate_zugferd_pdf(eracun)

    filename = 'ZUGFeRD_%s.pdf' % (eracun.invoice_number or eracun.pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def download_xrechnung(request, pk):
    """Download XRechnung CII XML."""
    from django.http import HttpResponse
    from .models import ERacun
    from core.company_utils import get_user_company
    company = get_user_company(request)
    eracun = get_object_or_404(ERacun, pk=pk, company=company)

    from eracun.services.xrechnung import generate_xrechnung
    xml_str = generate_xrechnung(eracun)

    filename = 'XRechnung_%s.xml' % (eracun.invoice_number or eracun.pk)
    response = HttpResponse(xml_str, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response
