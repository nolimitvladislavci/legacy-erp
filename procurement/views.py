from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from core.company_utils import get_user_company
from .models import PurchaseOrder, PurchaseOrderItem, SupplierPriceList
from django.db import IntegrityError, DatabaseError


def _get_company(request):
    return get_user_company(request)


@login_required
def po_list(request):
    company = _get_company(request)
    qs = PurchaseOrder.objects.filter(company=company)
    status = request.GET.get('status')
    match = request.GET.get('match_status')
    search = request.GET.get('q')
    if status:
        qs = qs.filter(status=status)
    if match:
        qs = qs.filter(match_status=match)
    if search:
        qs = qs.filter(Q(po_number__icontains=search) | Q(supplier__name__icontains=search))
    stats = {
        'total': qs.count(),
        'draft': qs.filter(status='draft').count(),
        'sent': qs.filter(status='sent').count(),
        'unmatched': qs.filter(match_status='unmatched').exclude(status__in=['draft', 'cancelled']).count(),
        'total_value': qs.exclude(status='cancelled').aggregate(s=Sum('total'))['s'] or 0,
    }
    return render(request, 'procurement/list.html', {'orders': qs, 'stats': stats, 'current_status': status, 'current_match': match, 'q': search or ''})


@login_required
def po_create(request):
    company = _get_company(request)
    if request.method == 'POST':
        po = PurchaseOrder(company=company, created_by=request.user)
        po.po_number = po.generate_po_number()
        po.priority = request.POST.get('priority', 'normal')
        po.notes = request.POST.get('notes', '')
        po.internal_note = request.POST.get('internal_note', '')
        expected = request.POST.get('expected_delivery')
        if expected:
            po.expected_delivery = expected
        supplier_id = request.POST.get('supplier')
        if supplier_id:
            from partners.models import Partner
            po.supplier = Partner.objects.filter(id=supplier_id, company=company).first()
        po.save()
        descriptions = request.POST.getlist('item_description')
        quantities = request.POST.getlist('item_quantity')
        prices = request.POST.getlist('item_price')
        tax_rates = request.POST.getlist('item_tax_rate')
        units = request.POST.getlist('item_unit')
        inv_items = request.POST.getlist('item_inventory')
        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            item = PurchaseOrderItem(
                purchase_order=po,
                description=desc,
                quantity=Decimal(quantities[i] or '1'),
                unit_price=Decimal(prices[i] or '0'),
                tax_rate=Decimal(tax_rates[i] if i < len(tax_rates) else '25'),
                unit=units[i] if i < len(units) else 'kom',
            )
            if i < len(inv_items) and inv_items[i]:
                from inventory.models import InventoryItem
                item.inventory_item = InventoryItem.objects.filter(id=inv_items[i]).first()
            item.save()
        po.recalculate()
        messages.success(request, f'Narudzbenica {po.po_number} kreirana.')
        return redirect('procurement:detail', pk=po.pk)
    from partners.models import Partner
    suppliers = Partner.objects.filter(company=company)
    return render(request, 'procurement/form.html', {'suppliers': suppliers, 'edit': False})


@login_required
def po_detail(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    items = po.items.all()
    warnings = []
    for item in items:
        if item.inventory_item:
            price_entry = SupplierPriceList.objects.filter(
                supplier=po.supplier, inventory_item=item.inventory_item,
                valid_from__lte=timezone.now().date()
            ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date())).first()
            if price_entry and item.unit_price > price_entry.agreed_price:
                diff_pct = ((item.unit_price - price_entry.agreed_price) / price_entry.agreed_price * 100)
                warnings.append({
                    'item': item, 'agreed': price_entry.agreed_price,
                    'actual': item.unit_price, 'diff_pct': round(diff_pct, 1)
                })
    return render(request, 'procurement/detail.html', {'po': po, 'items': items, 'warnings': warnings})


@login_required
def po_edit(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if po.status not in ('draft', 'sent'):
        messages.error(request, _('Samo nacrt/poslane narudzbenice se mogu uredjivati.'))
        return redirect('procurement:detail', pk=po.pk)
    if request.method == 'POST':
        po.priority = request.POST.get('priority', po.priority)
        po.notes = request.POST.get('notes', '')
        po.internal_note = request.POST.get('internal_note', '')
        expected = request.POST.get('expected_delivery')
        if expected:
            po.expected_delivery = expected
        supplier_id = request.POST.get('supplier')
        if supplier_id:
            from partners.models import Partner
            po.supplier = Partner.objects.filter(id=supplier_id, company=company).first()
        po.save()
        po.items.all().delete()
        descriptions = request.POST.getlist('item_description')
        quantities = request.POST.getlist('item_quantity')
        prices = request.POST.getlist('item_price')
        tax_rates = request.POST.getlist('item_tax_rate')
        units = request.POST.getlist('item_unit')
        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            PurchaseOrderItem.objects.create(
                purchase_order=po, description=desc,
                quantity=Decimal(quantities[i] or '1'),
                unit_price=Decimal(prices[i] or '0'),
                tax_rate=Decimal(tax_rates[i] if i < len(tax_rates) else '25'),
                unit=units[i] if i < len(units) else 'kom',
            )
        po.recalculate()
        messages.success(request, _('Narudzbenica azurirana.'))
        return redirect('procurement:detail', pk=po.pk)
    from partners.models import Partner
    suppliers = Partner.objects.filter(company=company)
    return render(request, 'procurement/form.html', {'po': po, 'suppliers': suppliers, 'edit': True})


@login_required
def po_send(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if po.status == 'draft':
        po.status = 'sent'
        po.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Narudzbenica {po.po_number} poslana dobavljacu.')
    return redirect('procurement:detail', pk=po.pk)


@login_required
def po_receive(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if request.method == 'POST':
        all_received = True
        for item in po.items.all():
            qty_key = f'qty_{item.pk}'
            qty = request.POST.get(qty_key)
            if qty:
                qty = Decimal(qty)
                item.quantity_received += qty
                item.save(update_fields=['quantity_received'])
                if item.quantity_received < item.quantity:
                    all_received = False
            else:
                if item.quantity_received < item.quantity:
                    all_received = False
        po.actual_delivery = timezone.now().date()
        po.status = 'received' if all_received else 'partial'
        po.save(update_fields=['status', 'actual_delivery', 'updated_at'])
        try:
            from inventory.models import GoodsReceipt, GoodsReceiptItem
            gr = GoodsReceipt.objects.create(
                company=company,
                supplier=po.supplier,
                reference=po.po_number,
                created_by=request.user,
            )
            for item in po.items.all():
                if item.quantity_received > 0 and item.inventory_item:
                    GoodsReceiptItem.objects.create(
                        goods_receipt=gr,
                        inventory_item=item.inventory_item,
                        quantity=item.quantity_received,
                        unit_price=item.unit_price,
                    )
            messages.success(request, f'Primka {gr.pk} automatski kreirana.')
        except (IntegrityError, DatabaseError) as e:
            messages.warning(request, f'Prijem evidentiran, ali automatska primka nije kreirana: {e}')
        messages.success(request, _('Prijem robe evidentiran.'))
        return redirect('procurement:detail', pk=po.pk)
    return render(request, 'procurement/receive.html', {'po': po, 'items': po.items.all()})


@login_required
def po_cancel(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if po.status not in ('received', 'invoiced'):
        po.status = 'cancelled'
        po.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Narudzbenica {po.po_number} otkazana.')
    else:
        messages.error(request, _('Ne moze se otkazati vec isporucena/fakturirana narudzbenica.'))
    return redirect('procurement:detail', pk=po.pk)


@login_required
def po_match(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if request.method == 'POST':
        invoice_id = request.POST.get('invoice_id')
        if invoice_id:
            from invoicing.models import Invoice
            inv = Invoice.objects.filter(id=invoice_id, company=company).first()
            if inv:
                po.matched_invoice = inv
                diff = abs(po.total - inv.total_amount)
                po.match_diff_amount = diff
                tolerance_pct = po.total * Decimal('0.005')
                tolerance_abs = Decimal('1.00')
                if diff <= max(tolerance_pct, tolerance_abs):
                    po.match_status = 'matched'
                    messages.success(request, f'Narudzbenica uparena s fakturom. Razlika: {diff} EUR')
                else:
                    po.match_status = 'mismatch'
                    messages.warning(request, f'Nepodudaranje! Razlika: {diff} EUR')
                po.save(update_fields=['matched_invoice', 'match_status', 'match_diff_amount', 'updated_at'])
                return redirect('procurement:detail', pk=po.pk)
    from invoicing.models import Invoice
    invoices = Invoice.objects.filter(company=company).order_by('-created_at')[:50]
    return render(request, 'procurement/match.html', {'po': po, 'invoices': invoices})


@login_required
def po_approve_match(request, pk):
    company = _get_company(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if po.match_status in ('matched', 'mismatch'):
        po.match_status = 'approved'
        po.approved_by = request.user
        po.status = 'invoiced'
        po.save(update_fields=['match_status', 'approved_by', 'status', 'updated_at'])
        messages.success(request, _('Uparivanje odobreno.'))
    return redirect('procurement:detail', pk=po.pk)


@login_required
def price_list(request):
    company = _get_company(request)
    prices = SupplierPriceList.objects.filter(company=company).select_related('supplier', 'inventory_item')
    return render(request, 'procurement/price_list.html', {'prices': prices})


@login_required
def procurement_dashboard(request):
    company = _get_company(request)
    qs = PurchaseOrder.objects.filter(company=company)
    now = timezone.now().date()
    stats = {
        'total': qs.count(),
        'draft': qs.filter(status='draft').count(),
        'sent': qs.filter(status='sent').count(),
        'received': qs.filter(status='received').count(),
        'unmatched': qs.filter(match_status='unmatched').exclude(status__in=['draft', 'cancelled']).count(),
        'overdue': qs.filter(expected_delivery__lt=now, status__in=['sent', 'confirmed']).count(),
        'total_value': qs.exclude(status='cancelled').aggregate(s=Sum('total'))['s'] or 0,
        'month_value': qs.filter(order_date__month=now.month, order_date__year=now.year).exclude(status='cancelled').aggregate(s=Sum('total'))['s'] or 0,
    }
    top_suppliers = qs.exclude(status='cancelled').values('supplier__name').annotate(
        cnt=Count('id'), total=Sum('total')
    ).order_by('-total')[:5]
    recent = qs.order_by('-created_at')[:10]
    return render(request, 'procurement/dashboard.html', {'stats': stats, 'top_suppliers': top_suppliers, 'recent': recent})
