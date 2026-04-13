import logging
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from partners.models import Partner

from .models import InventoryItem, StockMovement
from .serializers import InventoryItemSerializer, StockMovementSerializer
from django.core.exceptions import ObjectDoesNotExist


@login_required
def item_list(request):
    q = request.GET.get("q", "")
    category = request.GET.get("category", "")
    low_stock = request.GET.get("low_stock", "")
    company = get_user_company(request)
    qs = InventoryItem.objects.filter(company=company).select_related("supplier").order_by("name") if company else InventoryItem.objects.none()
    if q:
        qs = qs.filter(Q(name__icontains=q)|Q(sku__icontains=q))
    if category:
        qs = qs.filter(category=category)
    if low_stock == "1":
        qs = [item for item in qs if item.is_low_stock]
    else:
        qs = list(qs)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "inventory/item_list.html", {
        "page_obj": page, "q": q, "category": category, "low_stock": low_stock,
        "total": len(qs), "category_choices": InventoryItem.CATEGORY_CHOICES,
        "low_stock_count": sum(1 for item in InventoryItem.objects.all() if item.is_low_stock),
    })


@login_required
def item_detail(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    movements = item.movements.order_by("-created_at")[:20]
    return render(request, "inventory/item_detail.html", {"item": item, "movements": movements})


@login_required
def item_create(request):
    if request.method == "POST":
        try:
            from core.company_utils import get_user_company
            company = get_user_company(request)
            if not company:
                messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
                return redirect("inventory:list")
            supplier_id = request.POST.get("supplier")
            item = InventoryItem(
                company=company,
                name=request.POST["name"],
                sku=request.POST["sku"],
                category=request.POST.get("category", "other"),
                description=request.POST.get("description", ""),
                unit=request.POST.get("unit", "kom"),
                quantity=request.POST.get("quantity", 0) or 0,
                min_quantity=request.POST.get("min_quantity", 0) or 0,
                unit_price=request.POST.get("unit_price", 0) or 0,
                location=request.POST.get("location", ""),
                supplier=Partner.objects.get(pk=supplier_id) if supplier_id else None,
            )
            item.webshop_visible = 'webshop_visible' in request.POST
            kalo_str = request.POST.get('kalo_percent', '0').strip()
            try:
                from decimal import Decimal as _D
                item.kalo_percent = _D(kalo_str) if kalo_str else _D('0')
            except Exception:
                item.kalo_percent = 0
            if 'image' in request.FILES:
                item.image = request.FILES['image']
            item.save()
            messages.success(request, f"Artikl {item.name} kreiran.")
            return redirect("inventory:detail", pk=item.pk)
        except ObjectDoesNotExist as e:
            messages.error(request, str(e))
    return render(request, "inventory/item_form.html", {
        "suppliers": Partner.objects.filter(partner_type__in=["supplier","both"], is_active=True).order_by("name"),
        "category_choices": InventoryItem.CATEGORY_CHOICES,
        "action": "Novi artikl",
    })


@login_required
def item_edit(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        try:
            supplier_id = request.POST.get("supplier")
            item.name = request.POST["name"]
            item.sku = request.POST["sku"]
            item.category = request.POST.get("category", "other")
            item.description = request.POST.get("description", "")
            item.unit = request.POST.get("unit", "kom")
            item.min_quantity = request.POST.get("min_quantity", 0) or 0
            item.unit_price = request.POST.get("unit_price", 0) or 0
            item.location = request.POST.get("location", "")
            item.supplier = Partner.objects.get(pk=supplier_id) if supplier_id else None
            item.webshop_visible = 'webshop_visible' in request.POST
            item.is_weighable = 'is_weighable' in request.POST
            if 'image' in request.FILES:
                item.image = request.FILES['image']
            item.save()
            messages.success(request, f"Artikl {item.name} ažuriran.")
            return redirect("inventory:detail", pk=item.pk)
        except ObjectDoesNotExist as e:
            messages.error(request, str(e))
    return render(request, "inventory/item_form.html", {
        "item": item,
        "suppliers": Partner.objects.filter(partner_type__in=["supplier","both"], is_active=True).order_by("name"),
        "category_choices": InventoryItem.CATEGORY_CHOICES,
        "action": "Uredi artikl",
    })


@login_required
def stock_movement(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        try:
            movement_type = request.POST["movement_type"]
            qty = float(request.POST["quantity"])
            StockMovement.objects.create(
                item=item,
                movement_type=movement_type,
                quantity=qty,
                reason=request.POST.get("reason", ""),
                performed_by=request.user,
            )
            if movement_type == "in":
                item.quantity += qty
            elif movement_type == "out":
                item.quantity -= qty
            else:
                item.quantity = qty
            item.save(update_fields=["quantity"])
            messages.success(request, f"Kretanje zalihe zabilježeno. Nova kol: {item.quantity} {item.unit}")
        except (ValueError, TypeError) as e:
            messages.error(request, str(e))
    return redirect("inventory:detail", pk=pk)


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer

class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer


import datetime
from decimal import Decimal

from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from core.tenant import get_current_company

from .models import GoodsReceipt, GoodsReceiptItem
from django.views.decorators.csrf import csrf_exempt

# ── PRIMKA VIEWS ───────────────────────────────────────────────────────────────

@login_required
def goods_receipt_list(request):
    company = get_user_company(request)
    qs = GoodsReceipt.objects.filter(company=company).select_related('supplier').order_by('-date', '-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'inventory/goods_receipt_list.html', {
        'page_obj':      page_obj,
        'status_filter': status_filter,
    })


@login_required
def goods_receipt_create(request):
    company   = get_current_company()
    suppliers = Partner.objects.filter(
        company=company, partner_type__in=['supplier', 'both'], is_active=True,
    ).order_by('name')

    if request.method == 'POST':
        date_str    = request.POST.get('date') or str(datetime.date.today())
        supplier_id = request.POST.get('supplier_id') or None
        doc_num     = request.POST.get('document_number', '')
        notes       = request.POST.get('notes', '')

        # Auto-generate receipt_number
        year = datetime.date.today().year
        last = GoodsReceipt.objects.filter(
            company=company,
            receipt_number__startswith=f'PRIMKA-{year}-',
        ).order_by('-receipt_number').first()
        if last and last.receipt_number:
            try:
                seq = int(last.receipt_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        receipt_number = f'PRIMKA-{year}-{seq:04d}'

        receipt = GoodsReceipt(
            company=company,
            receipt_number=receipt_number,
            date=date_str,
            document_number=doc_num,
            notes=notes,
            created_by=request.user,
            status='draft',
        )
        if supplier_id:
            try:
                receipt.supplier_id = int(supplier_id)
            except (ValueError, TypeError):
                pass
        receipt.save()

        # Create items
        def _d(v):
            try:
                return Decimal(str(v).replace(',', '.'))
            except (ValueError, TypeError):
                return Decimal('0')

        item_ids  = request.POST.getlist('item_id[]')
        qtys      = request.POST.getlist('quantity[]')
        pps       = request.POST.getlist('purchase_price[]')
        dcs       = request.POST.getlist('dependent_costs[]')
        margins   = request.POST.getlist('margin_percent[]')
        tax_rates = request.POST.getlist('tax_rate[]')

        for i, item_id in enumerate(item_ids):
            if not item_id:
                continue
            try:
                inv_item = InventoryItem.objects.get(pk=int(item_id), company=company)
            except (InventoryItem.DoesNotExist, ValueError, TypeError):
                continue
            ri = GoodsReceiptItem(
                receipt=receipt,
                inventory_item=inv_item,
                quantity=_d(qtys[i]    if i < len(qtys)      else '1'),
                purchase_price_unit =_d(pps[i]    if i < len(pps)       else '0'),
                dependent_costs_unit=_d(dcs[i]    if i < len(dcs)       else '0'),
                margin_percent      =_d(margins[i] if i < len(margins)   else '0'),
                tax_rate            =_d(tax_rates[i] if i < len(tax_rates) else '25'),
            )
            ri.save()

        messages.success(request, f'Primka {receipt_number} kreirana.')
        return redirect('inventory:receipt_detail', pk=receipt.pk)

    return render(request, 'inventory/goods_receipt_form.html', {
        'suppliers': suppliers,
        'today': datetime.date.today().isoformat(),
    })


@login_required
def goods_receipt_detail(request, pk):
    company = get_current_company()
    receipt = get_object_or_404(GoodsReceipt, pk=pk, company=company)
    items   = receipt.items.select_related('inventory_item').all()
    return render(request, 'inventory/goods_receipt_detail.html', {
        'receipt': receipt,
        'items':   items,
    })




@login_required
def goods_receipt_pdf(request, pk):
    """Generira PDF primke s logom, generalijama i stavkama."""
    import io
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    company = get_current_company()
    receipt = get_object_or_404(GoodsReceipt, pk=pk, company=company)
    items = receipt.items.select_related('inventory_item').all()
    margin_pct = 0
    if receipt.total_purchase and receipt.total_purchase > 0:
        margin_pct = float((receipt.total_selling - receipt.total_purchase) / receipt.total_purchase * 100)
    missing_invoice = not receipt.linked_invoice_number and not receipt.document_number
    ctx = {
        'receipt': receipt,
        'items': items,
        'margin_pct': margin_pct,
        'missing_invoice': missing_invoice,
    }
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse('xhtml2pdf not installed', status=500)
    html = render_to_string('inventory/goods_receipt_pdf.html', ctx, request=request)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), result)
    if pdf.err:
        return HttpResponse('PDF generation error', status=500)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    fn = receipt.receipt_number or ('PRIMKA-%s' % receipt.pk)
    response['Content-Disposition'] = 'inline; filename="%s.pdf"' % fn
    return response

@login_required
@require_POST
def goods_receipt_confirm(request, pk):
    company = get_current_company()
    receipt = get_object_or_404(GoodsReceipt, pk=pk, company=company)
    if receipt.status != 'draft':
        messages.error(request, _('Primka nije u statusu Nacrt.'))
        return redirect('inventory:receipt_detail', pk=pk)
    try:
        receipt.confirm()
        messages.success(request, f'Primka {receipt.receipt_number} potvrđena. Zalihe i cijene ažurirane.')
    except Exception as e:
        messages.error(request, _('Potvrda primke nije uspjela. Provjerite stavke i pokušajte ponovo.'))
    return redirect('inventory:receipt_detail', pk=pk)


@login_required
def stock_overview(request):
    company = get_current_company()
    items   = list(InventoryItem.objects.filter(company=company, is_active=True).select_related('tax_rate').order_by('name'))
    total_purchase_value = sum(i.purchase_price * i.quantity for i in items)
    total_selling_value  = sum(i.unit_price * i.quantity for i in items)
    low_stock = [i for i in items if i.is_low_stock]
    return render(request, 'inventory/stock_overview.html', {
        'items':               items,
        'total_items':         len(items),
        'total_purchase_value': total_purchase_value,
        'total_selling_value':  total_selling_value,
        'low_stock_count':      len(low_stock),
        'low_stock':            low_stock,
    })


# ── Quick-add Article API ──────────────────────────────────────────
@login_required
def api_quick_create_article(request):
    """Create inventory item via AJAX from quick-add modal."""
    import json
    from django.http import JsonResponse
    from core.company_utils import get_user_company

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=400)

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Naziv artikla je obavezan'}, status=400)

        from inventory.models import InventoryItem
        item = InventoryItem(
            company=company,
            name=name,
            sku=data.get('sku', ''),
            unit_price=data.get('unit_price') or 0,
            unit=data.get('unit', 'kom'),
        )
        item.save()
        return JsonResponse({
            'ok': True,
            'id': item.pk,
            'name': item.name,
            'message': f'Artikl "{item.name}" dodan!'
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ── GLOBAL SMART CREATE (3 klika) ─────────────────────────────────────────────

# Kategorije koje NE prate zalihe (quantity nema smisla)
NO_STOCK_CATEGORIES = ('service',)


@login_required
def api_ai_predict_item(request):
    """AI predviđanje kategorije, poreza i barkoda na osnovu imena artikla.
    GET ?name=Burek sa sirom → {"category":"food","tax_rate":13,"tax_rate_id":2,"barcode":"2000001234567"}
    """
    import re
    name = request.GET.get('name', '').strip()
    if not name:
        return JsonResponse({'category': 'other', 'tax_rate': 25})

    from core.company_utils import get_user_company
    company = get_user_company(request)
    country = getattr(company, 'country', 'HR') if company else 'HR'

    # ── Smart category prediction (rule-based, instant) ──
    nl = name.lower()

    food_words = ['kruh', 'pecivo', 'burek', 'pizza', 'sendvic', 'meso', 'sir', 'salata',
                  'juha', 'grah', 'riza', 'tjestenina', 'kroasan', 'kifla', 'strudla',
                  'hamburger', 'hot dog', 'wrap', 'tortilla', 'brot', 'brötchen', 'semmel']
    drink_words = ['kava', 'juice', 'sok', 'voda', 'pivo', 'vino', 'cola', 'fanta', 'sprite',
                   'cedevita', 'cappuccino', 'espresso', 'latte', 'čaj', 'tee', 'kaffee',
                   'mineral', 'gaziran', 'limonada', 'smoothie', 'mlijeko', 'milch']
    dessert_words = ['kolač', 'torta', 'muffin', 'donut', 'krafna', 'čokolad', 'sladoled',
                     'kuchen', 'keks', 'brownie', 'tiramisu', 'palačink', 'waffle']
    service_words = ['usluga', 'servis', 'popravak', 'montaža', 'dostava', 'prijevoz',
                     'dienstleistung', 'reparatur', 'consulting', 'savjetovanje', 'najam',
                     'rent', 'pranje', 'čišćenje', 'frizur', 'šišanje', 'tretman']
    material_words = ['vijak', 'čavao', 'boja', 'cement', 'ljepilo', 'traka', 'žica',
                      'material', 'stoff', 'farbe']

    category = 'other'
    if any(w in nl for w in food_words):
        category = 'food'
    elif any(w in nl for w in drink_words):
        category = 'drink'
    elif any(w in nl for w in dessert_words):
        category = 'dessert'
    elif any(w in nl for w in service_words):
        category = 'service'
    elif any(w in nl for w in material_words):
        category = 'material'

    # ── Smart tax prediction ──
    from companies.models import TaxRate
    tax_rate_pct = 25  # default HR
    tax_rate_id = None

    if country in ('DE', 'AT'):
        # DE: food = 7%, drinks = 19%, services = 19%
        if category in ('food', 'dessert'):
            tax_rate_pct = 7
        else:
            tax_rate_pct = 19
    else:
        # HR: food/drink = 13%, services = 25%, basic bread = 5%
        if category in ('food', 'drink', 'dessert'):
            tax_rate_pct = 13
            # Basic bread/milk = 5%
            if any(w in nl for w in ['kruh', 'mlijeko', 'brašno', 'ulje jestivo']):
                tax_rate_pct = 5
        else:
            tax_rate_pct = 25

    # Find matching TaxRate object
    tr = TaxRate.objects.filter(country=country or 'HR', rate=tax_rate_pct, is_active=True).first()
    if tr:
        tax_rate_id = tr.pk

    # ── Auto barcode (EAN-13 internal range 200-299) ──
    from inventory.models import InventoryItem
    last_barcode = InventoryItem.objects.filter(
        company=company, barcode__startswith='200'
    ).order_by('-barcode').values_list('barcode', flat=True).first()

    if last_barcode and last_barcode.isdigit() and len(last_barcode) == 13:
        next_num = int(last_barcode[:12]) + 1
    else:
        next_num = 200000000000 + (InventoryItem.objects.filter(company=company).count() + 1)

    # EAN-13 check digit
    digits = str(next_num).zfill(12)
    check = (10 - sum((3 if i % 2 else 1) * int(d) for i, d in enumerate(digits))) % 10
    barcode = digits + str(check)

    # Track stock?
    track_stock = category not in NO_STOCK_CATEGORIES

    return JsonResponse({
        'category': category,
        'tax_rate': tax_rate_pct,
        'tax_rate_id': tax_rate_id,
        'barcode': barcode,
        'track_stock': track_stock,
        'unit': 'h' if category == 'service' else 'kom',
    })


@login_required
def api_smart_create(request):
    """Globalni smart create — 3 klika: ime, cijena, spremi.
    AI popunjava ostalo u pozadini. Koristi se iz POS-a, fakturiranja, inventara.
    POST JSON: {name, unit_price, category?, tax_rate_id?, barcode?, unit?}
    """
    import json
    from decimal import Decimal, InvalidOperation

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Naziv je obavezan'}, status=400)

    try:
        price = Decimal(str(data.get('unit_price', 0) or 0))
    except (InvalidOperation, ValueError):
        price = Decimal('0')

    category = data.get('category', 'other')
    unit = data.get('unit', 'kom')
    barcode = data.get('barcode', '').strip()

    # Tax rate
    tax_obj = None
    tax_rate_id = data.get('tax_rate_id')
    if tax_rate_id:
        from companies.models import TaxRate
        tax_obj = TaxRate.objects.filter(pk=tax_rate_id, is_active=True).first()

    # Auto-SKU
    import re
    clean = re.sub(r'[^A-Z0-9]', '', name.upper()[:8])
    from inventory.models import InventoryItem
    count = InventoryItem.objects.filter(company=company).count() + 1
    sku = f'{clean}-{count}'

    # Detect: should we track stock?
    track_stock = category not in NO_STOCK_CATEGORIES

    item = InventoryItem(
        company=company,
        name=name,
        sku=sku,
        barcode=barcode,
        category=category,
        unit=unit,
        unit_price=price,
        quantity=0 if track_stock else Decimal('999999'),
        min_quantity=0,
        tax_rate=tax_obj,
        is_active=True,
    )
    item.save()

    return JsonResponse({
        'ok': True,
        'id': item.pk,
        'name': item.name,
        'sku': item.sku,
        'barcode': item.barcode,
        'unit_price': str(item.unit_price),
        'category': item.category,
        'tax_rate': str(tax_obj.rate) if tax_obj else None,
        'track_stock': track_stock,
        'message': f'Artikl "{name}" kreiran!',
    })


# ── KALO (NATURAL SHRINKAGE) ─────────────────────────────────────────────────

@login_required
def kalo_view(request):
    """View and write off natural shrinkage (kalo) for inventory items."""
    from core.company_utils import get_user_company
    from django.utils.timezone import now
    import calendar

    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('inventory:item_list')

    items_with_kalo = InventoryItem.objects.filter(
        company=company, is_active=True, kalo_percent__gt=0
    ).order_by('name')

    # Annotate kalo values
    from decimal import Decimal
    kalo_data = []
    for item in items_with_kalo:
        kalo_qty   = round(item.quantity * item.kalo_percent / 100, 3)
        kalo_value = round(kalo_qty * item.unit_price, 2)
        kalo_data.append({
            'item': item,
            'kalo_qty': kalo_qty,
            'kalo_value': kalo_value,
        })

    if request.method == 'POST':
        item_ids = request.POST.getlist('item_ids')
        if not item_ids:
            messages.warning(request, _('Nijedan artikl nije odabran.'))
            return redirect('inventory:kalo')

        month_label = now().strftime('%Y-%m')
        written_off = 0
        for row in kalo_data:
            item = row['item']
            if str(item.pk) not in item_ids:
                continue
            kalo_qty = row['kalo_qty']
            if kalo_qty <= 0:
                continue
            StockMovement.objects.create(
                item=item,
                movement_type='out',
                quantity=kalo_qty,
                reason=f'Kalo {month_label}',
                performed_by=request.user,
            )
            # quantity updated by StockMovement.save() signal
            written_off += 1

        messages.success(request, f'Kalo otpisan za {written_off} artikla.')
        return redirect('inventory:kalo')

    return render(request, 'inventory/kalo.html', {
        'kalo_data': kalo_data,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10: Continuous Blind Inventory API
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def api_submit_count(request):
    """
    POST /api/inventory/submit-count/
    Body: {batch_id: int, actual_weight: float, notes: str (optional)}

    Rules:
    1. actual_weight is REQUIRED (no blind counts)
    2. If difference <= kalo_tolerance: OK (natural shrinkage)
    3. If difference > kalo_tolerance: 409 Conflict (theft alert)
    4. If batch is in quarantine: 403 Forbidden
    5. If batch is expired: auto-quarantine, 403

    Returns:
    200: {status: "ok"|"kalo", difference_pct, message}
    400: Missing actual_weight (blind count blocked)
    403: Expired/quarantined batch
    409: Theft alert (difference exceeds tolerance)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as _json
    from decimal import Decimal
    from inventory.models import StockBatch, InventoryCountLog

    try:
        data = _json.loads(request.body)
    except (ValueError, _json.JSONDecodeError):
        return JsonResponse({'error': 'Neispravan JSON.'}, status=400)

    batch_id = data.get('batch_id')
    actual_weight = data.get('actual_weight')

    # Rule 1: Blind count enforcement — actual_weight is mandatory
    if actual_weight is None:
        return JsonResponse({
            'error': 'Količina/težina s vage je obavezna. Nije dozvoljeno potvrđivanje bez mjerenja.',
            'code': 'BLIND_COUNT_BLOCKED',
        }, status=400)

    if not batch_id:
        return JsonResponse({'error': 'batch_id je obavezan.'}, status=400)

    try:
        batch = StockBatch.objects.select_related('item').get(pk=batch_id)
    except StockBatch.DoesNotExist:
        return JsonResponse({'error': 'Sarza ne postoji.'}, status=404)

    # Rule 5: Auto-quarantine expired batches
    if batch.is_expired:
        batch.check_quarantine()
        return JsonResponse({
            'error': 'Sarza ima istekao rok trajanja i prebacena je u HACCP karantenu.',
            'code': 'EXPIRED_QUARANTINE',
        }, status=403)

    # Rule 4: Already quarantined
    if batch.quarantine_status == 'quarantine':
        return JsonResponse({
            'error': 'Sarza je u HACCP karanteni: ' + (batch.quarantine_reason or 'nepoznat razlog'),
            'code': 'QUARANTINE',
        }, status=403)

    actual = Decimal(str(actual_weight))
    expected = batch.expected_weight

    if expected <= 0:
        return JsonResponse({'error': 'Sarza nema postavljenu ocekivanu tezinu.'}, status=400)

    difference_kg = expected - actual
    difference_pct = (difference_kg / expected * 100).quantize(Decimal('0.01'))
    kalo_tol = batch.kalo_tolerance

    # Determine result
    if actual > expected:
        result = 'surplus'
    elif float(difference_pct) <= float(kalo_tol):
        result = 'kalo' if float(difference_pct) > 0 else 'ok'
    else:
        result = 'theft_alert'

    # Log the count
    from django.utils import timezone as tz
    log = InventoryCountLog.objects.create(
        company=batch.company,
        batch=batch,
        expected_weight=expected,
        actual_weight=actual,
        difference_kg=difference_kg,
        difference_pct=difference_pct,
        kalo_tolerance_pct=kalo_tol,
        result=result,
        counted_by=request.user,
        notes=data.get('notes', ''),
    )

    # Update batch
    batch.actual_weight = actual
    batch.last_counted_at = tz.now()
    batch.last_counted_by = request.user
    batch.save(update_fields=['actual_weight', 'last_counted_at', 'last_counted_by', 'updated_at'])

    if result == 'theft_alert':
        return JsonResponse({
            'error': f'Upozorenje na moguce kalo/kradju! Razlika {difference_pct}% premašuje dopušteni kalo od {kalo_tol}%.',
            'code': 'THEFT_ALERT',
            'difference_pct': float(difference_pct),
            'kalo_tolerance_pct': float(kalo_tol),
            'expected': float(expected),
            'actual': float(actual),
            'log_id': log.pk,
        }, status=409)

    msg = 'Inventura zabilježena.'
    if result == 'kalo':
        msg = f'Prirodni kalo: {difference_pct}% (dopušteno do {kalo_tol}%).'
    elif result == 'surplus':
        msg = f'Višak od {abs(float(difference_pct))}%.'

    return JsonResponse({
        'status': result,
        'message': msg,
        'difference_pct': float(difference_pct),
        'kalo_tolerance_pct': float(kalo_tol),
        'log_id': log.pk,
    })


@login_required
def api_check_batch_for_dispatch(request, batch_id):
    """
    GET /api/inventory/batch/<id>/check-dispatch/
    HACCP guard: blocks dispatch of expired or quarantined batches.
    Used by invoice/dispatch views before adding items.
    """
    from inventory.models import StockBatch

    try:
        batch = StockBatch.objects.select_related('item').get(pk=batch_id)
    except StockBatch.DoesNotExist:
        return JsonResponse({'error': 'Sarza ne postoji.'}, status=404)

    # Auto-quarantine if expired
    batch.check_quarantine()

    if batch.quarantine_status == 'quarantine':
        return JsonResponse({
            'allowed': False,
            'error': f'Sarza {batch.batch_number} je u HACCP karanteni i ne smije se otpremiti.',
            'reason': batch.quarantine_reason,
            'code': 'QUARANTINE',
        }, status=403)

    if batch.is_expired:
        return JsonResponse({
            'allowed': False,
            'error': f'Sarza {batch.batch_number} ima istekao rok trajanja ({batch.expiry_date}).',
            'code': 'EXPIRED',
        }, status=403)

    return JsonResponse({
        'allowed': True,
        'batch_number': batch.batch_number,
        'item_name': batch.item.name,
        'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
        'quantity': float(batch.quantity),
    })


@login_required
def blind_count_view(request):
    """Blind inventory count — warehouse tablet UI."""
    return render(request, 'inventory/blind_count.html')


@login_required
def reorder_predictions(request):
    """Predictive reorder dashboard — shows items needing restock."""
    from inventory.reorder import reorder_report
    from core.company_utils import get_user_company
    from procurement.models import PurchaseOrder
    company = get_user_company(request)
    report = reorder_report(company)

    # Auto-generated draft POs
    auto_pos = PurchaseOrder.objects.filter(
        company=company,
        status='draft',
        notes__contains='[AUTO-REORDER]',
    ).select_related('supplier').order_by('-created_at')

    return render(request, 'inventory/reorder_predictions.html', {
        'report': report,
        'auto_pos': auto_pos,
        'auto_po_count': auto_pos.count(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTIVE ANALYTICS ENGINE — Views
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def predictive_dashboard(request):
    """Enhanced predictive analytics dashboard with weekly demand + auto-PO."""
    from core.company_utils import get_user_company
    from inventory.reorder import reorder_report, predict_weekly_demand
    from inventory.models import InventoryItem

    company = get_user_company(request)
    report = reorder_report(company, top_n=30)

    # Enhance with weekly predictions
    enhanced_items = []
    critical_count = 0
    warning_count = 0

    for item_data in report.get('items', []):
        try:
            item = item_data.get('item')
            if item:
                weekly = predict_weekly_demand(item)
                item_data['weekly_prediction'] = weekly
        except Exception:
            pass
        enhanced_items.append(item_data)

        if item_data.get('urgency') == 'critical':
            critical_count += 1
        elif item_data.get('urgency') == 'warning':
            warning_count += 1

    return render(request, 'inventory/predictive_dashboard.html', {
        'items': enhanced_items,
        'total_items': report.get('total_items', 0),
        'insufficient_count': report.get('insufficient_count', 0),
        'has_enough_data': report.get('has_enough_data', False),
        'critical_count': critical_count,
        'warning_count': warning_count,
    })


@login_required
def auto_generate_po(request):
    """AJAX endpoint: auto-generate draft PO from predictions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from core.company_utils import get_user_company
    from inventory.reorder import generate_draft_po, predict_reorder

    company = get_user_company(request)

    # Optional: specific item IDs
    item_ids = request.POST.getlist('item_ids')

    if item_ids:
        from inventory.models import InventoryItem
        items = []
        for iid in item_ids:
            try:
                item = InventoryItem.objects.get(pk=iid, company=company)
                pred = predict_reorder(item)
                if pred and not pred.get('insufficient_data'):
                    items.append({
                        'item_id': item.pk,
                        'suggested_qty': float(pred.get('suggested_qty', 10)),
                        'reorder_point': float(pred.get('reorder_point', 10)),
                        'urgency': pred.get('urgency', 'warning'),
                    })
            except ObjectDoesNotExist:
                continue
        po_ids = generate_draft_po(company, items=items)
    else:
        po_ids = generate_draft_po(company)

    return JsonResponse({
        'success': True,
        'po_count': len(po_ids),
        'po_ids': po_ids,
        'message': f'Generirano {len(po_ids)} nacrt narud\u017ebenica',
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TRIGGER PREDICTIVE REORDER — Manual trigger
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def trigger_reorder(request):
    """Manually trigger predictive reorder check for current company."""
    if request.method == 'POST':
        from inventory.tasks import predictive_reorder_check
        predictive_reorder_check.delay()
        messages.success(request, _('Prediktivna analiza pokrenuta. Rezultati će biti dostupni uskoro.'))
    return redirect('inventory:reorder_predictions')


@login_required
def stock_card(request, item_id):
    """Skladisna kartica — kronoloski pregled svih kretanja artikla (KEUB zahtjev)."""
    from inventory.models import InventoryItem, StockMovement
    from core.company_utils import get_user_company

    company = get_user_company(request)
    item = get_object_or_404(InventoryItem, pk=item_id, company=company)

    # Date filters
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    movements = StockMovement.objects.filter(item=item).order_by('created_at')
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)

    # Calculate running balance
    entries = []
    balance = Decimal('0')
    total_in = Decimal('0')
    total_out = Decimal('0')
    total_in_value = Decimal('0')
    total_out_value = Decimal('0')

    for m in movements:
        if m.movement_type == 'in':
            balance += m.quantity
            total_in += m.quantity
            total_in_value += m.quantity * m.unit_price
        else:
            balance -= m.quantity
            total_out += m.quantity
            total_out_value += m.quantity * m.unit_price

        entries.append({
            'date': m.created_at,
            'type': m.movement_type,
            'quantity': m.quantity,
            'unit_price': m.unit_price,
            'value': m.quantity * m.unit_price,
            'reason': m.reason or '',
            'balance': balance,
            'performed_by': m.performed_by,
        })

    # BOM info
    from calculator.models import BOM
    boms = BOM.objects.filter(article=item, company=company, is_active=True).prefetch_related('items__material')

    return render(request, 'inventory/stock_card.html', {
        'item': item,
        'entries': entries,
        'total_in': total_in,
        'total_out': total_out,
        'total_in_value': total_in_value,
        'total_out_value': total_out_value,
        'current_balance': balance,
        'boms': boms,
        'date_from': date_from,
        'date_to': date_to,
    })


# ════════════════════════════════════════════════════════════
# WAREHOUSE TRANSFER — Medjuskladisnica / Izdatnica
# ════════════════════════════════════════════════════════════

@login_required
def warehouse_list(request):
    """Popis skladista firme."""
    company = get_current_company()
    from inventory.models import Warehouse
    warehouses = Warehouse.objects.filter(company=company, is_active=True)
    return render(request, 'inventory/warehouse_list.html', {'warehouses': warehouses})


@login_required
def transfer_list(request):
    """Popis medjuskladisnica."""
    company = get_current_company()
    from inventory.models import WarehouseTransfer
    qs = WarehouseTransfer.objects.filter(company=company).select_related(
        'source_warehouse', 'destination_warehouse', 'created_by'
    ).order_by('-date', '-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'inventory/transfer_list.html', {
        'transfers': qs[:100],
        'status_filter': status_filter,
    })


@login_required
def transfer_create(request):
    """Kreiraj novu medjuskladisnicu / izdatnicu."""
    company = get_current_company()
    from inventory.models import Warehouse, WarehouseTransfer, WarehouseTransferItem
    from datetime import date as _date

    warehouses = Warehouse.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        src_id = request.POST.get('source_warehouse')
        dst_id = request.POST.get('destination_warehouse')
        if src_id == dst_id:
            messages.error(request, _('Izvor i odrediste ne mogu biti isti.'))
            return redirect('inventory:transfer_create')

        # Auto-broj: MS-YYYY-NNNN
        year = _date.today().year
        prefix = 'MS-%d-' % year
        last = WarehouseTransfer.objects.filter(
            company=company, transfer_number__startswith=prefix
        ).order_by('-transfer_number').first()
        seq = 1
        if last and last.transfer_number:
            try:
                seq = int(last.transfer_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                pass
        transfer_number = '%s%04d' % (prefix, seq)

        transfer = WarehouseTransfer.objects.create(
            company=company,
            transfer_number=transfer_number,
            date=request.POST.get('date', _date.today()),
            source_warehouse_id=src_id,
            destination_warehouse_id=dst_id,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )

        # Stavke
        items_added = 0
        item_ids = request.POST.getlist('item_id')
        quantities = request.POST.getlist('item_qty')
        for item_id, qty in zip(item_ids, quantities):
            if item_id and qty:
                try:
                    q = float(qty)
                    if q > 0:
                        WarehouseTransferItem.objects.create(
                            transfer=transfer,
                            inventory_item_id=int(item_id),
                            quantity=q,
                        )
                        items_added += 1
                except (ValueError, TypeError):
                    pass

        messages.success(request, _('Medjuskladisnica %s kreirana (%d stavki).') % (transfer_number, items_added))
        return redirect('inventory:transfer_detail', pk=transfer.pk)

    items = InventoryItem.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'inventory/transfer_create.html', {
        'warehouses': warehouses,
        'items': items,
    })


@login_required
def transfer_detail(request, pk):
    """Detalj medjuskladisnice."""
    company = get_current_company()
    from inventory.models import WarehouseTransfer
    transfer = get_object_or_404(WarehouseTransfer, pk=pk, company=company)
    items = transfer.items.select_related('inventory_item').all()
    return render(request, 'inventory/transfer_detail.html', {
        'transfer': transfer,
        'items': items,
    })


@login_required
@require_POST
def transfer_confirm(request, pk):
    """Potvrdi izdatnicu — razduzi izvor."""
    company = get_current_company()
    from inventory.models import WarehouseTransfer
    transfer = get_object_or_404(WarehouseTransfer, pk=pk, company=company)
    try:
        transfer.confirm(user=request.user)
        messages.success(request, _('Izdatnica %s potvrdjena. Roba u prijenosu.') % transfer.transfer_number)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('inventory:transfer_detail', pk=pk)


# ═══════════════════════════════════════════════════════════════
# INVENTURA — Godišnji popis s barcode skenerom
# ═══════════════════════════════════════════════════════════════

@login_required
def inventura_list(request):
    """Lista svih inventura za tvrtku."""
    company = get_user_company(request)
    from .models import Inventura
    qs = Inventura.objects.filter(company=company) if company else Inventura.objects.none()
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'inventory/inventura_list.html', {
        'page_obj': page,
        'status_filter': status_filter,
        'status_choices': Inventura.STATUS_CHOICES,
    })


@login_required
def inventura_create(request):
    """Kreiraj novu inventuru i pokreni brojanje."""
    company = get_user_company(request)
    from .models import Inventura, Warehouse, InventuraCommission
    if request.method == 'POST':
        from datetime import date, datetime
        ref_date_str = request.POST.get('reference_date', '')
        try:
            ref_date = datetime.strptime(ref_date_str, '%Y-%m-%d').date() if ref_date_str else date.today()
        except ValueError:
            ref_date = date.today()
        wh_id = request.POST.get('warehouse')
        inv = Inventura(
            company=company,
            inventura_type=request.POST.get('inventura_type', 'annual'),
            date_started=date.today(),
            reference_date=ref_date,
            warehouse=Warehouse.objects.filter(pk=wh_id, company=company).first() if wh_id else None,
            category_filter=request.POST.get('category_filter', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        inv.save()
        # Komisija
        for key in request.POST:
            if key.startswith('commission_user_'):
                idx = key.split('_')[-1]
                uid = request.POST.get(key)
                role = request.POST.get('commission_role_%s' % idx, 'clan')
                if uid:
                    from django.contrib.auth.models import User as AuthUser
                    try:
                        u = AuthUser.objects.get(pk=uid)
                        InventuraCommission.objects.create(inventura=inv, user=u, role=role)
                    except AuthUser.DoesNotExist:
                        pass
        # Generiraj stavke
        inv.start_counting()
        messages.success(request, _('Inventura %s pokrenuta — %d artikala.') % (inv.inventura_number, inv.total_items))
        return redirect('inventory:inventura_detail', pk=inv.pk)

    warehouses = Warehouse.objects.filter(company=company) if company else Warehouse.objects.none()
    from django.contrib.auth.models import User as AuthUser
    # Filtriraj usere po firmi — komisija vidi samo zaposlenike svoje firme
    if company:
        users = AuthUser.objects.filter(
            is_active=True, profile__company=company
        ).order_by('first_name', 'last_name')
    else:
        users = AuthUser.objects.filter(is_active=True).order_by('first_name', 'last_name')
    return render(request, 'inventory/inventura_create.html', {
        'warehouses': warehouses,
        'category_choices': InventoryItem.CATEGORY_CHOICES,
        'type_choices': Inventura.TYPE_CHOICES,
        'users': users,
    })


@login_required
def inventura_detail(request, pk):
    """Pregled inventure — status, napredak, komisija."""
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    items = inv.items.select_related('inventory_item', 'counted_by').all()

    q = request.GET.get('q', '')
    show = request.GET.get('show', '')  # all / uncounted / differences
    if q:
        items = items.filter(
            Q(inventory_item__name__icontains=q) |
            Q(inventory_item__sku__icontains=q) |
            Q(inventory_item__barcode__icontains=q)
        )
    if show == 'uncounted':
        items = items.filter(counted_at__isnull=True)
    elif show == 'differences':
        items = items.filter(counted_at__isnull=False).exclude(difference_qty=0)

    paginator = Paginator(items, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'inventory/inventura_detail.html', {
        'inv': inv,
        'page_obj': page,
        'q': q,
        'show': show,
        'commission': inv.commission.select_related('user').all(),
    })


@login_required
def inventura_count(request, pk):
    """
    Mobile-friendly stranica za brojanje s kamerom.
    Barcode scan → pronađi artikl → unesi količinu.
    """
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    if inv.status not in ('counting', 'in_progress'):
        messages.warning(request, _('Inventura nije u statusu brojanja.'))
        return redirect('inventory:inventura_detail', pk=pk)

    uncounted = inv.items.filter(counted_at__isnull=True).select_related('inventory_item').count()
    counted = inv.items.filter(counted_at__isnull=False).count()
    return render(request, 'inventory/inventura_count.html', {
        'inv': inv,
        'uncounted': uncounted,
        'counted': counted,
    })


def _ai_identify_item(barcode, inventura):
    """
    AI pokušava identificirati artikl po barkodu.
    Šalje barcode + listu artikala AI-u, AI vraća best match.
    """
    import os, logging
    logger = logging.getLogger('inventory')

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        # Fallback: fuzzy match po Levenshtein distanci
        try:
            from rapidfuzz import fuzz
            best_score = 0
            best_item = None
            for inv_item in inventura.items.select_related('inventory_item')[:500]:
                name = inv_item.inventory_item.name.lower()
                sku = inv_item.inventory_item.sku.lower()
                bc = inv_item.inventory_item.barcode.lower()
                # Usporedi barcode sa svim poljima
                score = max(
                    fuzz.partial_ratio(barcode.lower(), name),
                    fuzz.partial_ratio(barcode.lower(), sku),
                    fuzz.ratio(barcode.lower(), bc) if bc else 0,
                )
                if score > best_score:
                    best_score = score
                    best_item = inv_item
            if best_item and best_score > 70:
                return {
                    'found': True,
                    'ai_matched': True,
                    'ai_confidence': best_score,
                    'item_id': best_item.pk,
                    'name': best_item.inventory_item.name,
                    'sku': best_item.inventory_item.sku,
                    'barcode': best_item.inventory_item.barcode,
                    'expected_qty': str(best_item.expected_qty),
                    'counted_qty': str(best_item.counted_qty) if best_item.counted_qty is not None else None,
                    'unit': best_item.unit,
                    'category': best_item.inventory_item.get_category_display(),
                    'already_counted': best_item.counted_at is not None,
                }
        except ImportError:
            pass
        return None

    # Gemini AI — pošalji barcode + nazive artikala
    try:
        from google import genai
        # Uzmi sample artikala za kontekst
        sample_names = [
            '%s|%s|%s' % (it.inventory_item.sku, it.inventory_item.barcode, it.inventory_item.name)
            for it in inventura.items.select_related('inventory_item')[:200]
        ]
        prompt = (
            'Skenirani barcode je: %s\n'
            'Ovo su artikli u skladištu (sku|barcode|ime):\n%s\n\n'
            'Koji artikl iz liste odgovara ovom barkodu? '
            'Odgovori SAMO s SKU kodom artikla (npr. SYN-12345) ili "NONE" ako nema.'
        ) % (barcode, '\n'.join(sample_names[:100]))

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[{'role': 'user', 'parts': [{'text': prompt}]}],
        )
        ai_sku = response.text.strip().split('\n')[0].strip()
        if ai_sku and ai_sku != 'NONE':
            from django.db.models import Q
            match = inventura.items.filter(
                Q(inventory_item__sku=ai_sku) | Q(inventory_item__name__icontains=ai_sku[:20])
            ).select_related('inventory_item').first()
            if match:
                return {
                    'found': True,
                    'ai_matched': True,
                    'ai_confidence': 85,
                    'item_id': match.pk,
                    'name': match.inventory_item.name,
                    'sku': match.inventory_item.sku,
                    'barcode': match.inventory_item.barcode,
                    'expected_qty': str(match.expected_qty),
                    'counted_qty': str(match.counted_qty) if match.counted_qty is not None else None,
                    'unit': match.unit,
                    'category': match.inventory_item.get_category_display(),
                    'already_counted': match.counted_at is not None,
                }
    except Exception as e:
        logger.warning('AI identify failed: %s', e)
    return None


@login_required
@csrf_exempt
def inventura_api_scan(request, pk):
    """
    AJAX: Barcode scan → vrati stavku inventure.
    POST {barcode: "..."} → {item_id, name, sku, expected_qty, counted_qty, unit}
    POST {item_id: N, counted_qty: X} → spremi brojanje
    """
    company = get_user_company(request)
    from .models import Inventura, InventuraItem
    from django.utils import timezone
    import json

    inv = get_object_or_404(Inventura, pk=pk, company=company)
    if inv.status not in ('counting', 'in_progress'):
        return JsonResponse({'error': 'Inventura nije u statusu brojanja.'}, status=400)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()

    # Mode 1: barcode lookup (barcode, sku, ili ime)
    barcode = data.get('barcode', '').strip()
    if barcode:
        inv_item = inv.items.filter(
            Q(inventory_item__barcode=barcode) |
            Q(inventory_item__sku=barcode)
        ).select_related('inventory_item').first()

        # Ako barcode ne nađe, probaj po imenu (fuzzy search)
        if not inv_item:
            inv_item = inv.items.filter(
                Q(inventory_item__name__icontains=barcode)
            ).select_related('inventory_item').first()

        # Ako ni to, vrati listu sličnih (za dropdown odabir)
        if not inv_item:
            suggestions = list(
                inv.items.filter(
                    Q(inventory_item__name__icontains=barcode[:10]) |
                    Q(inventory_item__barcode__icontains=barcode[:6])
                ).select_related('inventory_item')[:5]
            )
            if suggestions:
                return JsonResponse({
                    'found': False,
                    'suggestions': [
                        {'item_id': s.pk, 'name': s.inventory_item.name,
                         'sku': s.inventory_item.sku, 'barcode': s.inventory_item.barcode}
                        for s in suggestions
                    ],
                    'error': 'Nije pronađen, evo sličnih:',
                }, status=200)
            # AI pokušaj — pošalji barcode AI-u da pogodi koji artikl
            ai_match = _ai_identify_item(barcode, inv)
            if ai_match:
                return JsonResponse(ai_match)
            return JsonResponse({'error': 'Artikl s barcodom "%s" nije na popisu. Probaj upisati ime.' % barcode, 'found': False, 'ai_tried': True}, status=404)
        return JsonResponse({
            'found': True,
            'item_id': inv_item.pk,
            'name': inv_item.inventory_item.name,
            'sku': inv_item.inventory_item.sku,
            'barcode': inv_item.inventory_item.barcode,
            'expected_qty': str(inv_item.expected_qty),
            'counted_qty': str(inv_item.counted_qty) if inv_item.counted_qty is not None else None,
            'unit': inv_item.unit,
            'category': inv_item.inventory_item.get_category_display(),
            'already_counted': inv_item.counted_at is not None,
        })

    # Mode 2: submit count
    item_id = data.get('item_id')
    counted_qty = data.get('counted_qty')
    if item_id and counted_qty is not None:
        from decimal import Decimal, InvalidOperation
        try:
            inv_item = inv.items.get(pk=item_id)
        except InventuraItem.DoesNotExist:
            return JsonResponse({'error': 'Stavka ne postoji.'}, status=404)
        try:
            qty = Decimal(str(counted_qty))
        except (InvalidOperation, ValueError):
            return JsonResponse({'error': 'Nevažeća količina.'}, status=400)
        inv_item.counted_qty = qty
        inv_item.counted_by = request.user
        inv_item.counted_at = timezone.now()
        inv_item.barcode_scanned = bool(data.get('barcode_scanned', False))
        inv_item.note = data.get('note', '')[:255]
        inv_item.save()
        return JsonResponse({
            'ok': True,
            'difference_qty': str(inv_item.difference_qty),
            'difference_value': str(inv_item.difference_value),
            'progress': inv.progress_percent,
            'counted_total': inv.counted_items,
            'total_items': inv.total_items,
        })

    return JsonResponse({'error': 'Pošalji barcode ili item_id+counted_qty.'}, status=400)


@login_required
@require_POST
def inventura_complete(request, pk):
    """Zaključi inventuru."""
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    try:
        inv.complete(user=request.user)
        messages.success(request, _('Inventura %s završena.') % inv.inventura_number)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('inventory:inventura_detail', pk=pk)


@login_required
@require_POST
def inventura_approve(request, pk):
    """Odobri inventuru i generiraj korekcije zaliha."""
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    try:
        inv.approve_and_adjust(user=request.user)
        messages.success(request, _('Inventura %s odobrena. Zalihe korigirane.') % inv.inventura_number)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('inventory:inventura_detail', pk=pk)


@login_required
def inventura_pdf(request, pk):
    """
    Inventurni list — zakonski obrazac.
    HR: Pravilnik o provedbi popisa (NN 61/16)
    Sadrži: sve stavke, knjižno stanje, stvarno stanje, razlika, potpisi komisije.
    """
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    commission = inv.commission.select_related('user').all()

    # Filter: ?show=counted (samo prebrojane), ?show=differences (samo razlike), default=sve
    show = request.GET.get('show', 'counted')
    items = inv.items.select_related('inventory_item', 'counted_by')
    if show == 'counted':
        items = items.filter(counted_at__isnull=False)
    elif show == 'differences':
        items = items.filter(counted_at__isnull=False).exclude(difference_qty=0)
    elif show == 'all':
        items = items.all()
    else:
        items = items.filter(counted_at__isnull=False)

    from django.template.loader import render_to_string
    from django.http import HttpResponse
    html = render_to_string('inventory/inventura_pdf.html', {
        'inv': inv,
        'items': items,
        'commission': commission,
        'company': company,
        'show': show,
    })
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="inventurni_list_%s.pdf"' % inv.inventura_number.replace('/', '-')
        return response
    except ImportError:
        return HttpResponse(html)


@login_required
def inventura_difference_pdf(request, pk):
    """
    Inventurna razlika — izvještaj o manjkovima i viškovima.
    Zakonski: temelj za knjiženje rashoda/prihoda.
    """
    company = get_user_company(request)
    from .models import Inventura
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    items = inv.items.filter(counted_at__isnull=False).exclude(difference_qty=0).select_related('inventory_item')
    commission = inv.commission.select_related('user').all()

    shortages = items.filter(difference_qty__lt=0)
    surpluses = items.filter(difference_qty__gt=0)

    from decimal import Decimal
    total_shortage = sum(abs(i.difference_value) for i in shortages)
    total_surplus = sum(abs(i.difference_value) for i in surpluses)

    from django.template.loader import render_to_string
    from django.http import HttpResponse
    html = render_to_string('inventory/inventura_difference_pdf.html', {
        'inv': inv,
        'shortages': shortages,
        'surpluses': surpluses,
        'total_shortage': total_shortage,
        'total_surplus': total_surplus,
        'commission': commission,
        'company': company,
    })
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="inventurna_razlika_%s.pdf"' % inv.inventura_number.replace('/', '-')
        return response
    except ImportError:
        return HttpResponse(html)


@login_required
def inventura_export_csv(request, pk):
    """CSV export inventure — za revizore i računovodstvo."""
    company = get_user_company(request)
    from .models import Inventura
    import csv
    inv = get_object_or_404(Inventura, pk=pk, company=company)
    items = inv.items.select_related('inventory_item').all()

    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inventura_%s.csv"' % inv.inventura_number.replace('/', '-')
    response.write('\ufeff')  # UTF-8 BOM
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'R.br.', 'Šifra', 'Barcode', 'Naziv', 'JMJ', 'Kategorija',
        'Knjižno stanje', 'Stvarno stanje', 'Razlika kol.',
        'Jed. cijena', 'Razlika iznos', 'Prebrojao', 'Napomena',
    ])
    for i, item in enumerate(items, 1):
        writer.writerow([
            i,
            item.inventory_item.sku,
            item.inventory_item.barcode,
            item.inventory_item.name,
            item.unit,
            item.inventory_item.get_category_display(),
            item.expected_qty,
            item.counted_qty if item.counted_qty is not None else '',
            item.difference_qty if item.counted_at else '',
            item.unit_price,
            item.difference_value if item.counted_at else '',
            (item.counted_by.get_full_name() if item.counted_by else ''),
            item.note,
        ])
    return response


@login_required
@require_POST
def transfer_receive(request, pk):
    """Zaprimi robu na odredisnom skladistu."""
    company = get_current_company()
    from inventory.models import WarehouseTransfer
    transfer = get_object_or_404(WarehouseTransfer, pk=pk, company=company)
    try:
        transfer.receive(user=request.user)
        messages.success(request, _('Roba zaprimljena u %s.') % transfer.destination_warehouse.name)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('inventory:transfer_detail', pk=pk)


@login_required
@require_POST
def ai_menu_scan(request):
    """AI Menu Scanner — fotografiraj cjenik, AI parsira i puni InventoryItem."""
    import json
    from django.http import JsonResponse
    from core.company_utils import get_user_company

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    data = json.loads(request.body)
    b64 = data.get('image_b64', '')
    if not b64:
        return JsonResponse({'error': 'Nema slike'}, status=400)

    # AI parsira sliku cjenika
    try:
        import anthropic, os
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2000,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                    {'type': 'text', 'text': (
                        'Ovo je fotografija jelovnika/cjenika. Parsiraj SVE artikle. '
                        'Vrati JSON array: [{"name":"Kava","price":1.80,"category":"drink"}, ...] '
                        'Kategorije: food, drink, dessert, product, service, other. '
                        'Cijene u EUR. Samo JSON, nista drugo.'
                    )},
                ],
            }],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response
        if '```' in text:
            text = text.split('```')[1].strip()
            if text.startswith('json'):
                text = text[4:].strip()
        items = json.loads(text)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'AI nije mogao parsirati cjenik. Pokusajte jasniju sliku.'}, status=400)
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=500)

    # Kreiraj InventoryItem za svaki parsirani artikl
    from inventory.models import InventoryItem
    from decimal import Decimal
    created = 0
    skipped = 0
    results = []

    for item in items:
        name = item.get('name', '').strip()
        price = item.get('price', 0)
        category = item.get('category', 'other')
        if not name:
            continue

        # SKU auto-generate
        import re
        sku = re.sub(r'[^A-Z0-9]', '', name.upper()[:8]) + '-%d' % (created + 1)

        obj, is_new = InventoryItem.objects.get_or_create(
            company=company, name=name,
            defaults={
                'sku': sku,
                'unit_price': Decimal(str(price)),
                'category': category,
                'quantity': 999,
            }
        )
        if is_new:
            created += 1
        else:
            skipped += 1
        results.append({'name': name, 'price': float(price), 'category': category, 'new': is_new})

    return JsonResponse({
        'ok': True,
        'created': created,
        'skipped': skipped,
        'items': results,
        'message': '%d artikala dodano, %d vec postojalo' % (created, skipped),
    })
