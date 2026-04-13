"""
sales/views.py — Cjenici, Narudžbe kupaca, Saldakonti (25+ views).
"""

import logging
from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from .models import (
    RabatGroup, CustomerPriceList, PriceListLine,
    SalesOrder, SalesOrderLine, OpenItem, IOSReport,
)
from .ai_services import smart_pricing_suggest, order_predictor, payment_predictor, resolve_price
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def _co(request):
    """Shortcut: vrati company ili None."""
    return get_user_company(request)


# ════════════════════════════════════════════════════════════════
#  1. CJENICI — Posebni cjenici za kupce
# ════════════════════════════════════════════════════════════════

@login_required
def price_list_dashboard(request):
    """Pregled svih cjenika, broj partnera, AI sugestije."""
    company = _co(request)
    if not company:
        return redirect('home')

    price_lists = CustomerPriceList.objects.filter(company=company).select_related('partner')
    active_count = price_lists.filter(is_active=True).count()
    ai_count = price_lists.filter(ai_suggested=True).count()
    partner_count = price_lists.exclude(partner=None).values('partner').distinct().count()
    rabat_groups = RabatGroup.objects.filter(company=company).select_related("company")

    return render(request, 'sales/price_list_dashboard.html', {
        'price_lists': price_lists,
        'active_count': active_count,
        'ai_count': ai_count,
        'partner_count': partner_count,
        'rabat_groups': rabat_groups,
    })


@login_required
def price_list_create(request, pk=None):
    """Kreiranje/uređivanje cjenika s inline stavkama."""
    company = _co(request)
    if not company:
        return redirect('home')

    from partners.models import Partner
    from inventory.models import InventoryItem

    obj = None
    if pk:
        obj = get_object_or_404(CustomerPriceList, pk=pk, company=company)

    if request.method == 'POST':
        if not obj:
            obj = CustomerPriceList(company=company)
        obj.name = request.POST.get('name', '').strip()
        partner_id = request.POST.get('partner')
        if partner_id:
            obj.partner = Partner.objects.filter(pk=partner_id, company=company).first()
        else:
            obj.partner = None
        obj.partner_group = request.POST.get('partner_group', '').strip()
        obj.is_active = request.POST.get('is_active') == 'on'
        obj.valid_from = request.POST.get('valid_from') or None
        obj.valid_until = request.POST.get('valid_until') or None
        obj.priority = int(request.POST.get('priority', 10))
        obj.notes = request.POST.get('notes', '')
        obj.save()

        # Obriši stare stavke i kreiraj nove
        obj.lines.all().delete()
        items_ids = request.POST.getlist('line_item')
        rabat_ids = request.POST.getlist('line_rabat_group')
        dtypes = request.POST.getlist('line_discount_type')
        dvalues = request.POST.getlist('line_discount_value')
        min_qtys = request.POST.getlist('line_min_quantity')
        cassa = request.POST.getlist('line_cassa_days')

        for i in range(len(dtypes)):
            dval = Decimal(dvalues[i] or '0') if i < len(dvalues) else Decimal('0')
            if dval == 0 and not (i < len(items_ids) and items_ids[i]):
                continue
            line = PriceListLine(price_list=obj, discount_type=dtypes[i], discount_value=dval)
            if i < len(items_ids) and items_ids[i]:
                line.item_id = items_ids[i]
            if i < len(rabat_ids) and rabat_ids[i]:
                line.rabat_group_id = rabat_ids[i]
            if i < len(min_qtys) and min_qtys[i]:
                line.min_quantity = Decimal(min_qtys[i])
            if i < len(cassa) and cassa[i]:
                line.cassa_days = int(cassa[i])
            line.save()

        action = 'ažuriran' if pk else 'kreiran'
        messages.success(request, f'Cjenik "{obj.name}" {action}.')
        return redirect('sales:price_list_detail', pk=obj.pk)

    partners = Partner.objects.filter(company=company).order_by('name')
    items = InventoryItem.objects.filter(company=company).order_by('name')
    rabat_groups = RabatGroup.objects.filter(company=company).select_related("company")
    lines = obj.lines.all() if obj else []

    return render(request, 'sales/price_list_form.html', {
        'obj': obj,
        'partners': partners,
        'items': items,
        'rabat_groups': rabat_groups,
        'lines': lines,
        'discount_types': PriceListLine.DISCOUNT_TYPE_CHOICES,
    })


@login_required
def price_list_detail(request, pk):
    """Prikaz cjenika sa svim stavkama."""
    company = _co(request)
    if not company:
        return redirect('home')
    obj = get_object_or_404(CustomerPriceList, pk=pk, company=company)
    lines = obj.lines.select_related('item', 'rabat_group').all()
    return render(request, 'sales/price_list_detail.html', {
        'obj': obj,
        'lines': lines,
    })


@login_required
@require_POST
def price_list_delete(request, pk):
    """Brisanje cjenika."""
    company = _co(request)
    if not company:
        return redirect('home')
    obj = get_object_or_404(CustomerPriceList, pk=pk, company=company)
    name = obj.name
    obj.delete()
    messages.success(request, f'Cjenik "{name}" obrisan.')
    return redirect('sales:price_list_dashboard')


@login_required
def ai_price_suggest(request):
    """AJAX: AI preporuka rabata za partnera."""
    company = _co(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)
    partner_id = request.GET.get('partner_id')
    if not partner_id:
        return JsonResponse({'error': 'Nedostaje partner_id'}, status=400)
    from partners.models import Partner
    partner = get_object_or_404(Partner, pk=partner_id, company=company)
    try:
        result = smart_pricing_suggest(company, partner)
        # Serialize Decimal values
        serialized = {}
        for k, v in result.items():
            serialized[k] = float(v) if isinstance(v, Decimal) else v
        return JsonResponse({'ok': True, 'data': serialized})
    except (ValueError, TypeError) as e:
        logger.exception('AI price suggest error')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def resolve_price_api(request):
    """AJAX: Dohvati najbolju cijenu za partner+artikl kombinaciju."""
    company = _co(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)
    partner_id = request.GET.get('partner_id')
    item_id = request.GET.get('item_id')
    quantity = Decimal(request.GET.get('quantity', '1'))
    if not partner_id or not item_id:
        return JsonResponse({'error': 'Nedostaje partner_id ili item_id'}, status=400)

    from partners.models import Partner
    from inventory.models import InventoryItem
    partner = get_object_or_404(Partner, pk=partner_id, company=company)
    item = get_object_or_404(InventoryItem, pk=item_id, company=company)

    try:
        result = resolve_price(company, partner, item, quantity)
        serialized = {}
        for k, v in result.items():
            if isinstance(v, Decimal):
                serialized[k] = float(v)
            elif isinstance(v, dict):
                serialized[k] = {kk: float(vv) if isinstance(vv, Decimal) else vv for kk, vv in v.items()}
            else:
                serialized[k] = v
        return JsonResponse({'ok': True, 'data': serialized})
    except (ValueError, TypeError) as e:
        logger.exception('Resolve price error')
        return JsonResponse({'error': str(e)}, status=500)


# ════════════════════════════════════════════════════════════════
#  2. NARUDŽBE KUPACA — SalesOrder
# ════════════════════════════════════════════════════════════════

@login_required
def order_dashboard(request):
    """Kanban board — draft/confirmed/processing/shipped/invoiced."""
    company = _co(request)
    if not company:
        return redirect('home')
    qs = SalesOrder.objects.filter(company=company).select_related('partner')
    kanban = {
        'draft': qs.filter(status='draft'),
        'confirmed': qs.filter(status='confirmed'),
        'processing': qs.filter(status='processing'),
        'shipped': qs.filter(status='shipped'),
        'invoiced': qs.filter(status='invoiced'),
    }
    stats = {
        'total': qs.count(),
        'total_value': qs.exclude(status='cancelled').aggregate(s=Sum('total'))['s'] or Decimal('0'),
        'draft_count': kanban['draft'].count(),
        'confirmed_count': kanban['confirmed'].count(),
    }
    return render(request, 'sales/order_dashboard.html', {
        'kanban': kanban,
        'stats': stats,
    })


@login_required
def order_list(request):
    """Filterirani popis narudžbi s pretragom."""
    company = _co(request)
    if not company:
        return redirect('home')
    qs = SalesOrder.objects.filter(company=company).select_related('partner')

    status = request.GET.get('status')
    search = request.GET.get('q', '').strip()
    priority = request.GET.get('priority')

    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=int(priority))
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search) | Q(partner__name__icontains=search)
        )

    stats = {
        'total': qs.count(),
        'total_value': qs.exclude(status='cancelled').aggregate(s=Sum('total'))['s'] or Decimal('0'),
    }

    return render(request, 'sales/order_list.html', {
        'orders': qs,
        'stats': stats,
        'current_status': status,
        'current_priority': priority,
        'q': search,
    })


@login_required
def order_create(request):
    """Kreiranje narudžbe s AI-sugeriranim artiklima, auto-apply cjenika."""
    company = _co(request)
    if not company:
        return redirect('home')

    from partners.models import Partner
    from inventory.models import InventoryItem

    if request.method == 'POST':
        order = SalesOrder(company=company, created_by=request.user)

        # Generiraj broj narudžbe
        now = timezone.now()
        count = SalesOrder.objects.filter(company=company, order_date__year=now.year).select_related("company", "partner", "otpremnica").count() + 1
        order.order_number = f'NAR-{now.year}-{count:04d}'

        partner_id = request.POST.get('partner')
        if partner_id:
            order.partner = get_object_or_404(Partner, pk=partner_id, company=company)
        order.order_date = request.POST.get('order_date', now.date())
        order.delivery_date = request.POST.get('delivery_date') or None
        order.delivery_address = request.POST.get('delivery_address', '')
        order.notes = request.POST.get('notes', '')
        order.internal_notes = request.POST.get('internal_notes', '')
        order.priority = int(request.POST.get('priority', 2))

        price_list_id = request.POST.get('price_list')
        if price_list_id:
            order.price_list = CustomerPriceList.objects.filter(pk=price_list_id, company=company).select_related("company", "partner").first()

        warehouse_id = request.POST.get('warehouse')
        if warehouse_id:
            from inventory.models import Warehouse
            order.warehouse = Warehouse.objects.filter(pk=warehouse_id, company=company).first()

        order.save()

        # Stavke
        item_ids = request.POST.getlist('line_item')
        qtys = request.POST.getlist('line_quantity')
        prices = request.POST.getlist('line_unit_price')
        discounts = request.POST.getlist('line_discount')
        tax_rates = request.POST.getlist('line_tax_rate')
        units = request.POST.getlist('line_unit')
        ai_flags = request.POST.getlist('line_ai_suggested')

        for i, item_id in enumerate(item_ids):
            if not item_id:
                continue
            line = SalesOrderLine(
                order=order,
                item_id=item_id,
                quantity=Decimal(qtys[i]) if i < len(qtys) and qtys[i] else Decimal('1'),
                unit_price=Decimal(prices[i]) if i < len(prices) and prices[i] else Decimal('0'),
                discount_percent=Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal('0'),
                tax_rate=Decimal(tax_rates[i]) if i < len(tax_rates) and tax_rates[i] else Decimal('25'),
                unit=units[i] if i < len(units) and units[i] else 'kom',
                is_ai_suggested=str(i) in ai_flags,
                sort_order=i,
            )
            line.save()

        order.recalculate()
        messages.success(request, f'Narudžba {order.order_number} kreirana.')
        return redirect('sales:order_detail', pk=order.pk)

    partners = Partner.objects.filter(company=company).order_by('name')
    items = InventoryItem.objects.filter(company=company).order_by('name')
    price_lists = CustomerPriceList.objects.filter(company=company, is_active=True).select_related("company", "partner")
    try:
        from inventory.models import Warehouse
        warehouses = Warehouse.objects.filter(company=company)
    except DatabaseError:
        warehouses = []

    return render(request, 'sales/order_form.html', {
        'partners': partners,
        'items': items,
        'price_lists': price_lists,
        'warehouses': warehouses,
        'statuses': SalesOrder.STATUS_CHOICES,
        'priorities': SalesOrder.PRIORITY_CHOICES,
    })


@login_required
def order_detail(request, pk):
    """Detalji narudžbe s flow gumbima i povezanim dokumentima."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    lines = order.lines.select_related('item').all()
    return render(request, 'sales/order_detail.html', {
        'order': order,
        'lines': lines,
    })


@login_required
@require_POST
def order_confirm(request, pk):
    """Potvrdi narudžbu, rezerviraj zalihe."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    if order.status != 'draft':
        messages.warning(request, _('Narudžba nije u statusu Nacrt.'))
        return redirect('sales:order_detail', pk=pk)

    order.status = 'confirmed'
    order.save(update_fields=['status', 'updated_at'])

    # Pokušaj rezervacije zaliha (soft — samo log)
    for line in order.lines.select_related('item').all():
        try:
            item = line.item
            if hasattr(item, 'stock_quantity') and item.stock_quantity is not None:
                if item.stock_quantity < line.quantity:
                    messages.warning(request,
                        f'Upozorenje: {item.name} — nedovoljno zaliha '
                        f'({item.stock_quantity} vs. {line.quantity})')
        except AttributeError:
            pass

    messages.success(request, f'Narudžba {order.order_number} potvrđena.')
    return redirect('sales:order_detail', pk=pk)


@login_required
@require_POST
def order_ship(request, pk):
    """Kreiraj Otpremnicu iz narudžbe."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    if order.status not in ('confirmed', 'processing'):
        messages.warning(request, _('Narudžba mora biti potvrđena za isporuku.'))
        return redirect('sales:order_detail', pk=pk)

    try:
        from propter.models import Otpremnica, OtpremnicaItem
        otp = Otpremnica(
            company=company,
            recipient_name=order.partner.name,
            recipient_oib=getattr(order.partner, 'oib', ''),
            recipient_address=order.delivery_address or getattr(order.partner, 'address', ''),
            issue_date=timezone.now().date(),
            delivery_date=order.delivery_date or timezone.now().date(),
            subtotal=order.subtotal,
            tax_amount=order.tax_total,
            total=order.total,
            source='invoice',
            status='issued',
            note=f'Iz narudžbe {order.order_number}',
            created_by=request.user,
        )
        otp.save()

        for line in order.lines.select_related('item').all():
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                description=line.item.name,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
            )
            # Ažuriraj isporučenu količinu
            line.delivered_quantity = line.quantity
            line.save(update_fields=['delivered_quantity'])

        order.otpremnica = otp
        order.status = 'shipped'
        order.save(update_fields=['status', 'otpremnica', 'updated_at'])
        messages.success(request, f'Otpremnica {otp.number} kreirana za narudžbu {order.order_number}.')

    except Exception as e:
        logger.exception('Greška pri kreiranju otpremnice')
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    return redirect('sales:order_detail', pk=pk)


@login_required
@require_POST
def order_invoice(request, pk):
    """Kreiraj fakturu iz narudžbe."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    if order.status not in ('shipped', 'confirmed', 'processing'):
        messages.warning(request, _('Narudžba mora biti isporučena ili potvrđena za fakturiranje.'))
        return redirect('sales:order_detail', pk=pk)

    try:
        from invoicing.models import Invoice, InvoiceItem
        now = timezone.now()
        year = now.year
        count = Invoice.objects.filter(company=company, date_issued__year=year).count() + 1
        inv_number = f'{year}-{count:05d}'

        inv = Invoice(
            company=company,
            doctype='R',
            number=inv_number,
            date_issued=now,
            date_due=now.date() + timedelta(days=15),
            date_delivery=order.delivery_date or now.date(),
            client_name=order.partner.name,
            client_oib=getattr(order.partner, 'oib', ''),
            client_address=getattr(order.partner, 'address', ''),
            client_city=getattr(order.partner, 'city', ''),
            client_email=getattr(order.partner, 'email', ''),
            partner=order.partner,
            status='DRAFT',
            currency=order.currency,
            subtotal=order.subtotal - order.discount_total,
            tax_amount=order.tax_total,
            total=order.total,
            created_by=request.user,
        )
        inv.save()

        for line in order.lines.select_related('item').all():
            InvoiceItem.objects.create(
                invoice=inv,
                description=line.item.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                tax_rate=line.tax_rate,
            )

        order.invoice = inv
        order.status = 'invoiced'
        order.save(update_fields=['status', 'invoice', 'updated_at'])
        messages.success(request, f'Faktura {inv.number} kreirana iz narudžbe {order.order_number}.')

    except Exception as e:
        logger.exception('Greška pri kreiranju fakture')
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    return redirect('sales:order_detail', pk=pk)


@login_required
@require_POST
def order_cancel(request, pk):
    """Otkaži narudžbu."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    if order.status in ('invoiced', 'closed'):
        messages.warning(request, _('Fakturirana ili zatvorena narudžba se ne može otkazati.'))
        return redirect('sales:order_detail', pk=pk)
    order.status = 'cancelled'
    order.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Narudžba {order.order_number} otkazana.')
    return redirect('sales:order_detail', pk=pk)


@login_required
def order_pdf(request, pk):
    """Generiraj PDF narudžbe."""
    company = _co(request)
    if not company:
        return redirect('home')
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    lines = order.lines.select_related('item').all()

    try:
        from weasyprint import HTML
        html_str = render(request, 'sales/order_pdf.html', {
            'order': order,
            'lines': lines,
            'company': company,
        }).content.decode('utf-8')
        pdf = HTML(string=html_str).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="narudzba_{order.order_number}.pdf"'
        return response
    except ImportError:
        # Fallback: HTML prikaz za print
        return render(request, 'sales/order_pdf.html', {
            'order': order,
            'lines': lines,
            'company': company,
        })


@login_required
def ai_suggest_items(request):
    """AJAX: AI predviđa artikle za narudžbu kupca."""
    company = _co(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)
    partner_id = request.GET.get('partner_id')
    if not partner_id:
        return JsonResponse({'error': 'Nedostaje partner_id'}, status=400)
    from partners.models import Partner
    partner = get_object_or_404(Partner, pk=partner_id, company=company)
    try:
        suggestions = order_predictor(company, partner)
        return JsonResponse({'ok': True, 'data': suggestions})
    except Exception as e:
        logger.exception('AI suggest items error')
        return JsonResponse({'error': str(e)}, status=500)


# ════════════════════════════════════════════════════════════════
#  3. SALDAKONTI — Otvorene stavke, IOS obrasci
# ════════════════════════════════════════════════════════════════

@login_required
def saldakonti_dashboard(request):
    """Aging pregled, ukupna potraživanja/obveze, AI risk."""
    company = _co(request)
    if not company:
        return redirect('home')

    qs = OpenItem.objects.filter(company=company, is_closed=False).select_related("company", "partner", "invoice")
    today = timezone.now().date()

    receivables = qs.filter(direction='receivable')
    payables = qs.filter(direction='payable')

    def aging_buckets(items):
        buckets = {'current': Decimal('0'), '1-30': Decimal('0'),
                   '31-60': Decimal('0'), '61-90': Decimal('0'), '90+': Decimal('0')}
        for item in items:
            buckets[item.aging_bucket] += item.remaining
        return buckets

    recv_aging = aging_buckets(receivables)
    pay_aging = aging_buckets(payables)

    total_receivable = receivables.aggregate(s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')
    total_payable = payables.aggregate(s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')

    # Top rizični partneri
    risky = receivables.filter(ai_risk_score__gte=50).select_related('partner').order_by('-ai_risk_score')[:10]

    # Zadnji IOS-ovi
    recent_ios = IOSReport.objects.filter(company=company).select_related('partner')[:5]

    return render(request, 'sales/saldakonti_dashboard.html', {
        'recv_aging': recv_aging,
        'pay_aging': pay_aging,
        'total_receivable': total_receivable,
        'total_payable': total_payable,
        'net_balance': total_receivable - total_payable,
        'open_count': qs.count(),
        'risky_items': risky,
        'recent_ios': recent_ios,
    })


@login_required
def partner_open_items(request, partner_id):
    """Otvorene stavke za specifičnog partnera."""
    company = _co(request)
    if not company:
        return redirect('home')
    from partners.models import Partner
    partner = get_object_or_404(Partner, pk=partner_id, company=company)

    qs = OpenItem.objects.filter(company=company, partner=partner).select_related("company", "partner", "invoice")
    direction = request.GET.get('direction')
    show_closed = request.GET.get('show_closed') == '1'

    if not show_closed:
        qs = qs.filter(is_closed=False)
    if direction:
        qs = qs.filter(direction=direction)

    total_recv = qs.filter(direction='receivable').aggregate(
        s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')
    total_pay = qs.filter(direction='payable').aggregate(
        s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')

    return render(request, 'sales/partner_open_items.html', {
        'partner': partner,
        'items': qs,
        'total_recv': total_recv,
        'total_pay': total_pay,
        'net_balance': total_recv - total_pay,
        'show_closed': show_closed,
        'direction': direction,
    })


@login_required
def ios_generate(request, partner_id):
    """Generiraj IOS izvod za partnera."""
    company = _co(request)
    if not company:
        return redirect('home')
    from partners.models import Partner
    partner = get_object_or_404(Partner, pk=partner_id, company=company)
    today = timezone.now().date()

    open_items = OpenItem.objects.filter(
        company=company, partner=partner, is_closed=False
    )
    total_recv = open_items.filter(direction='receivable').aggregate(
        s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')
    total_pay = open_items.filter(direction='payable').aggregate(
        s=Sum(F('original_amount') - F('paid_amount')))['s'] or Decimal('0')

    ios = IOSReport.objects.create(
        company=company,
        partner=partner,
        report_date=today,
        total_receivable=total_recv,
        total_payable=total_pay,
        net_balance=total_recv - total_pay,
        items_count=open_items.count(),
        created_by=request.user,
    )
    messages.success(request, f'IOS izvod za {partner.name} generiran.')
    return redirect('sales:ios_pdf', pk=ios.pk)


@login_required
def ios_pdf(request, pk):
    """Render IOS kao PDF — A4, zakonski format."""
    company = _co(request)
    if not company:
        return redirect('home')
    ios = get_object_or_404(IOSReport, pk=pk, company=company)
    open_items = OpenItem.objects.filter(
        company=company, partner=ios.partner, is_closed=False
    )

    ctx = {
        'ios': ios,
        'company': company,
        'partner': ios.partner,
        'items': open_items,
        'today': timezone.now().date(),
    }

    try:
        from weasyprint import HTML
        html_str = render(request, 'sales/ios_pdf.html', ctx).content.decode('utf-8')
        pdf = HTML(string=html_str).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="IOS_{ios.partner.name}_{ios.report_date}.pdf"'
        return response
    except ImportError:
        return render(request, 'sales/ios_pdf.html', ctx)


@login_required
@require_POST
def ios_send_email(request, pk):
    """Pošalji IOS partneru emailom."""
    company = _co(request)
    if not company:
        return redirect('home')
    ios = get_object_or_404(IOSReport, pk=pk, company=company)
    partner = ios.partner

    email = getattr(partner, 'email', '') or ''
    if not email:
        messages.warning(request, f'Partner {partner.name} nema email adresu.')
        return redirect('sales:saldakonti_dashboard')

    try:
        from django.core.mail import EmailMessage
        open_items = OpenItem.objects.filter(
            company=company, partner=partner, is_closed=False
        )
        ctx = {
            'ios': ios, 'company': company, 'partner': partner,
            'items': open_items, 'today': timezone.now().date(),
        }
        html_str = render(request, 'sales/ios_pdf.html', ctx).content.decode('utf-8')

        subject = f'IOS — Izvod otvorenih stavki — {company.name}'
        body = (
            f'Poštovani,\n\n'
            f'U privitku Vam šaljemo Izvod otvorenih stavki na dan {ios.report_date}.\n'
            f'Neto saldo: {ios.net_balance} EUR\n\n'
            f'Molimo Vas za potvrdu ili primjedbe u roku 8 dana.\n\n'
            f'Srdačan pozdrav,\n{company.name}'
        )

        msg = EmailMessage(subject, body, to=[email])

        # Pokušaj generirati PDF privitak
        try:
            from weasyprint import HTML
            pdf = HTML(string=html_str).write_pdf()
            msg.attach(f'IOS_{partner.name}_{ios.report_date}.pdf', pdf, 'application/pdf')
        except ImportError:
            msg.body += '\n\n(PDF privitak nije dostupan — molimo kontaktirajte nas.)'

        msg.send(fail_silently=False)

        ios.sent_at = timezone.now()
        ios.save(update_fields=['sent_at'])
        messages.success(request, f'IOS poslan na {email}.')

    except ImportError as e:
        logger.exception('IOS send email error')
        messages.error(request, _('Slanje nije uspjelo. Provjerite internetsku vezu i pokušajte ponovo.'))

    return redirect('sales:saldakonti_dashboard')


@login_required
@require_POST
def payment_register(request, pk):
    """Registriraj uplatu na otvorenu stavku (parcijalna ili potpuna)."""
    company = _co(request)
    if not company:
        return redirect('home')
    item = get_object_or_404(OpenItem, pk=pk, company=company)
    amount = Decimal(request.POST.get('amount', '0'))

    if amount <= 0:
        messages.warning(request, _('Iznos mora biti veći od 0.'))
        return redirect('sales:partner_open_items', partner_id=item.partner_id)

    if amount > item.remaining:
        amount = item.remaining

    item.paid_amount += amount
    if item.paid_amount >= item.original_amount:
        item.close()
        messages.success(request, f'Stavka {item.document_number} — u potpunosti plaćena.')
    else:
        item.save(update_fields=['paid_amount', 'updated_at'])
        messages.success(request, f'Uplaćeno {amount} EUR na {item.document_number}. '
                         f'Preostalo: {item.remaining} EUR.')

    return redirect('sales:partner_open_items', partner_id=item.partner_id)


@login_required
def ai_payment_risk(request):
    """AJAX: AI predikcija plaćanja — risk score."""
    company = _co(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    partner_id = request.GET.get('partner_id')
    from partners.models import Partner
    partner = None
    if partner_id:
        partner = Partner.objects.filter(pk=partner_id, company=company).first()

    try:
        predictions = payment_predictor(company, partner)
        data = []
        for p in predictions:
            data.append({
                'document_number': p['item'].document_number,
                'partner_name': p['item'].partner.name,
                'remaining': float(p['item'].remaining),
                'days_overdue': p['item'].days_overdue,
                'predicted_days': p['predicted_days'],
                'risk_score': p['risk_score'],
                'risk_level': p['risk_level'],
            })
        return JsonResponse({'ok': True, 'data': data})
    except (ValueError, TypeError) as e:
        logger.exception('AI payment risk error')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def open_items_sync(request):
    """Sinkroniziraj otvorene stavke iz invoicing — kreiraj OpenItem za neplaćene fakture."""
    company = _co(request)
    if not company:
        return redirect('home')

    from invoicing.models import Invoice

    # Sve neplaćene fakture (izlazne)
    unpaid_invoices = Invoice.objects.filter(
        company=company,
        status__in=('SENT', 'CONFIRMED', 'UNPAID', 'OVERDUE'),
    ).exclude(
        doctype='URA',
    )

    created = 0
    skipped = 0
    for inv in unpaid_invoices:
        # Provjeri postoji li već OpenItem za ovaj račun
        exists = OpenItem.objects.filter(
            company=company,
            document_number=inv.number,
        ).exists()
        if exists:
            skipped += 1
            continue

        partner = inv.partner
        if not partner:
            skipped += 1
            continue

        OpenItem.objects.create(
            company=company,
            partner=partner,
            direction='receivable',
            document_type='racun',
            document_number=inv.number,
            document_date=inv.date_issued.date() if inv.date_issued else timezone.now().date(),
            due_date=inv.date_due or (inv.date_issued.date() + timedelta(days=15)) if inv.date_issued else timezone.now().date(),
            original_amount=inv.total,
            paid_amount=Decimal('0'),
            currency=inv.currency,
            invoice=inv,
        )
        created += 1

    # URA (ulazni računi) — obveze
    unpaid_ura = Invoice.objects.filter(
        company=company,
        doctype='URA',
        status__in=('SENT', 'CONFIRMED', 'UNPAID', 'OVERDUE'),
    )
    for inv in unpaid_ura:
        exists = OpenItem.objects.filter(
            company=company,
            document_number=inv.number,
        ).exists()
        if exists:
            skipped += 1
            continue
        partner = inv.partner
        if not partner:
            skipped += 1
            continue

        OpenItem.objects.create(
            company=company,
            partner=partner,
            direction='payable',
            document_type='racun',
            document_number=inv.number,
            document_date=inv.date_issued.date() if inv.date_issued else timezone.now().date(),
            due_date=inv.date_due or (inv.date_issued.date() + timedelta(days=15)) if inv.date_issued else timezone.now().date(),
            original_amount=inv.total,
            paid_amount=Decimal('0'),
            currency=inv.currency,
            invoice=inv,
        )
        created += 1

    messages.success(request, f'Sinkronizacija: {created} novih stavki, {skipped} preskočeno.')
    return redirect('sales:saldakonti_dashboard')
