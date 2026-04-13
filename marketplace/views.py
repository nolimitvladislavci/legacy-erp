import logging
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)
"""Grossmarkt Online - marketplace views with discount system."""
from decimal import Decimal

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.company_utils import get_user_company

from .discounts import get_discount_for_item, get_cart_with_discounts
from .models import (
    MarketplaceCategory,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplaceProduct,
    PartnerDiscount,
    SellerSubOrder,
)


@login_required
def catalog(request):
    q = request.GET.get('q', '')
    cat_slug = request.GET.get('category', '')
    organic_only = request.GET.get('organic', '')
    sort = request.GET.get('sort', 'name')

    qs = MarketplaceProduct.objects.filter(is_available=True).select_related('seller_company', 'category')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(seller_company__name__icontains=q))
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)
    if organic_only:
        qs = qs.filter(is_organic=True)

    sort_map = {'name': 'name', 'price_asc': 'unit_price', 'price_desc': '-unit_price', 'newest': '-created_at', 'rating': '-avg_rating'}
    qs = qs.order_by(sort_map.get(sort, 'name'))

    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get('page'))
    categories = MarketplaceCategory.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order')
    cart = request.session.get('marketplace_cart', {})
    cart_count = sum(item.get('qty', 0) for item in cart.values())

    # Calculate discounts for current buyer
    company = get_user_company(request)
    products_with_discounts = []
    if company:
        for product in page.object_list:
            disc = get_discount_for_item(product, company)
            products_with_discounts.append({
                'product': product,
                'discount': disc,
                'has_discount': disc['total_percent'] > 0,
            })

    return render(request, 'marketplace/catalog.html', {
        'page_obj': page, 'categories': categories, 'q': q,
        'cat_slug': cat_slug, 'organic_only': organic_only,
        'sort': sort, 'cart_count': cart_count, 'total': qs.count(),
        'products_with_discounts': products_with_discounts,
        'buyer_company': company,
    })


@login_required
def product_detail(request, slug):
    product = get_object_or_404(MarketplaceProduct, slug=slug, is_available=True)
    related = MarketplaceProduct.objects.filter(category=product.category, is_available=True).exclude(pk=product.pk)[:4]
    company = get_user_company(request)
    discount = get_discount_for_item(product, company) if company else None

    # Show all sellers for same product name (price comparison)
    same_name = MarketplaceProduct.objects.filter(
        name=product.name, is_available=True
    ).exclude(pk=product.pk).select_related('seller_company')
    competitors = []
    if company:
        for p in same_name:
            d = get_discount_for_item(p, company)
            competitors.append({'product': p, 'discount': d})
        competitors.sort(key=lambda x: x['discount']['discounted_price'])

    return render(request, 'marketplace/product_detail.html', {
        'product': product, 'related': related,
        'discount': discount, 'competitors': competitors,
    })


@login_required
def cart_add(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    product_id = request.POST.get('product_id')
    qty = float(request.POST.get('qty', 1))
    product = get_object_or_404(MarketplaceProduct, pk=product_id, is_available=True)

    company = get_user_company(request)
    disc = get_discount_for_item(product, company, Decimal(str(qty))) if company else None
    effective_price = disc['discounted_price'] if disc else product.unit_price

    cart = request.session.get('marketplace_cart', {})
    key = str(product_id)
    if key in cart:
        cart[key]['qty'] += qty
    else:
        cart[key] = {
            'product_id': product.pk, 'name': product.name,
            'seller': product.seller_company.name,
            'seller_id': str(product.seller_company.pk),
            'price': str(effective_price),
            'original_price': str(product.unit_price),
            'discount_percent': str(disc['total_percent']) if disc else '0',
            'unit': product.unit, 'qty': qty,
        }
    request.session['marketplace_cart'] = cart
    cart_count = sum(item.get('qty', 0) for item in cart.values())

    msg = f'{product.name} dodan u kosaricu'
    if disc and disc['total_percent'] > 0:
        msg += f' (-{disc["total_percent"]}% rabat!)'

    return JsonResponse({'ok': True, 'cart_count': cart_count, 'message': msg})


@login_required
def cart_view(request):
    cart = request.session.get('marketplace_cart', {})
    company = get_user_company(request)

    items = []
    total = 0
    total_original = 0
    total_savings = 0
    for key, item in cart.items():
        # Recalculate discount (prices may have changed)
        if company:
            try:
                product = MarketplaceProduct.objects.get(pk=item['product_id'])
                disc = get_discount_for_item(product, company, Decimal(str(item['qty'])))
                price = float(disc['discounted_price'])
                orig = float(product.unit_price)
                dpct = float(disc['total_percent'])
            except MarketplaceProduct.DoesNotExist:
                price = float(item['price'])
                orig = float(item.get('original_price', item['price']))
                dpct = 0
        else:
            price = float(item['price'])
            orig = float(item.get('original_price', item['price']))
            dpct = 0

        line_total = price * item['qty']
        line_original = orig * item['qty']
        line_savings = line_original - line_total
        total += line_total
        total_original += line_original
        total_savings += line_savings

        items.append({
            **item,
            'key': key,
            'effective_price': price,
            'original_price': orig,
            'discount_percent': dpct,
            'has_discount': dpct > 0,
            'line_total': line_total,
            'line_original': line_original,
            'line_savings': line_savings,
        })

    sellers = {}
    for item in items:
        sid = item['seller']
        if sid not in sellers:
            sellers[sid] = {'name': item['seller'], 'items': [], 'subtotal': 0, 'subtotal_original': 0}
        sellers[sid]['items'].append(item)
        sellers[sid]['subtotal'] += item['line_total']
        sellers[sid]['subtotal_original'] += item['line_original']

    return render(request, 'marketplace/cart.html', {
        'items': items, 'sellers': sellers,
        'total': total, 'total_original': total_original,
        'total_savings': total_savings,
        'cart_count': len(items),
    })


@login_required
def cart_remove(request, key):
    cart = request.session.get('marketplace_cart', {})
    if key in cart:
        del cart[key]
        request.session['marketplace_cart'] = cart
        messages.success(request, _('Stavka uklonjena.'))
    return redirect('marketplace:cart')


@login_required
def cart_clear(request):
    request.session['marketplace_cart'] = {}
    messages.success(request, _('Kosarica ispraznjena.'))
    return redirect('marketplace:catalog')


def _classify_temp_zone(product):
    """Classify product into temperature zone based on storage_temp_max."""
    t = product.storage_temp_max
    if t is None:
        return 'ambient'
    if t <= -12:
        return 'frozen'
    elif t <= 4:
        return 'chilled'
    elif t <= 8:
        return 'fresh'
    return 'ambient'


TEMP_ZONE_META = {
    'frozen':  {'label': 'Smrznuto',  'icon': '&#10052;',  'color': '#3b82f6'},
    'chilled': {'label': 'Hladjeno',  'icon': '&#129385;', 'color': '#8b5cf6'},
    'fresh':   {'label': 'Svjeze',    'icon': '&#129371;', 'color': '#22c55e'},
    'ambient': {'label': 'Sobna',     'icon': '&#127807;', 'color': '#eab308'},
}


def checkout(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Nemate aktivnu firmu.'))
        return redirect('marketplace:cart')
    cart = request.session.get('marketplace_cart', {})
    if not cart:
        messages.warning(request, _('Kosarica je prazna.'))
        return redirect('marketplace:catalog')

    if request.method == 'POST':
        from django.db import transaction
        from datetime import timedelta

        delivery_method = request.POST.get('delivery_method', 'standard')
        is_recurring = bool(request.POST.get('is_recurring'))
        recurring_interval = request.POST.get('recurring_interval', '')

        with transaction.atomic():
            order = MarketplaceOrder.objects.create(
                buyer_company=company, buyer_user=request.user,
                delivery_date_requested=request.POST.get('delivery_date') or None,
                delivery_time_window=request.POST.get('time_window', ''),
                delivery_address=request.POST.get('delivery_address', company.address),
                delivery_notes=request.POST.get('notes', ''),
                delivery_method=delivery_method,
                cutoff_acknowledged=bool(request.POST.get('cutoff_acknowledged')),
                is_recurring=is_recurring,
                recurring_interval=recurring_interval if is_recurring else '',
            )

            seller_map = {}
            has_cold = False
            for key, item in cart.items():
                product = MarketplaceProduct.objects.get(pk=item['product_id'])
                qty = Decimal(str(item['qty']))
                disc = get_discount_for_item(product, company, qty)

                MarketplaceOrderItem.objects.create(
                    order=order, product=product, seller_company=product.seller_company,
                    quantity=qty,
                    unit_price=disc['discounted_price'],
                    total=disc['discounted_price'] * qty,
                )
                if product.requires_cold_chain:
                    has_cold = True
                sid = str(product.seller_company.pk)
                if sid not in seller_map:
                    seller_map[sid] = product.seller_company

            # Auto-set requires_cold_chain from items
            if has_cold:
                order.requires_cold_chain = True
                order.save(update_fields=['requires_cold_chain'])

            for sid, seller in seller_map.items():
                sub = SellerSubOrder.objects.create(
                    marketplace_order=order, seller_company=seller,
                    pickup_address=seller.address,
                )
                sub.recalculate()
            order.recalculate()

            # Gepek/Taxi — create dispatch offer
            if delivery_method == 'gepek_taxi':
                try:
                    from delivery.models import ConsolidatedDelivery, DispatchOffer
                    cd = ConsolidatedDelivery.objects.create(
                        hub_company=company,
                        buyer_company=company,
                        delivery_number=f'TAXI-{order.order_number}',
                        delivery_address=order.delivery_address,
                        requires_cold_chain=has_cold,
                        status='collecting',
                        package_count=1,
                        delivery_notes='Gepek/Taxi -- hitno',
                        created_by=request.user,
                    )
                    cd.marketplace_orders.add(order)
                    DispatchOffer.objects.create(
                        consolidated_delivery=cd,
                        status='pending',
                        offered_price=Decimal('15.00'),
                        pickup_address=company.address or '',
                        requires_cold_chain=has_cold,
                        expires_at=timezone.now() + timedelta(minutes=15),
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f'DispatchOffer creation failed: {e}')

            # Draft Invoice (deferred fiscalization)
            try:
                from invoicing.models import Invoice
                from django.utils import timezone as _tz
                draft_invoice = Invoice.objects.create(
                    company=company,
                    status='DRAFT',
                    is_fiscalized=False,
                    date_issued=_tz.now(),
                    note=f'Auto-draft za narudzbu {order.order_number}',
                )
                order.invoice = draft_invoice
                order.save(update_fields=['invoice'])
            except (IntegrityError, DatabaseError) as e:
                logger.warning(f'Draft invoice creation failed: {e}')

        # Payment gateway integration
        payment_method = request.POST.get('payment_method', '')
        if payment_method and payment_method != 'invoice':
            try:
                from payments.services import create_payment
                base_url = request.build_absolute_uri('/').rstrip('/')
                payment = create_payment(
                    company=company,
                    source='marketplace',
                    source_id=str(order.pk),
                    amount=order.total_amount,
                    method=payment_method,
                    customer_email=request.user.email or '',
                    customer_name=company.name,
                    description=f'Marketplace narudžba {order.order_number}',
                    success_url=base_url + f'/marketplace/orders/{order.pk}/',
                    cancel_url=base_url + '/marketplace/cart/',
                )
                if payment.external_url:
                    request.session['marketplace_cart'] = {}
                    return redirect(payment.external_url)
            except Exception as e:
                logger.warning(f'Payment creation failed: {e}')

        request.session['marketplace_cart'] = {}
        messages.success(request, f'Narudzba {order.order_number} kreirana!')
        return redirect('marketplace:order_detail', order.pk)

    # -- GET: Smart Checkout --
    items = []
    items_by_zone = {}
    total = 0
    total_savings = 0
    has_cold_chain = False

    for key, item in cart.items():
        try:
            product = MarketplaceProduct.objects.get(pk=item['product_id'])
            disc = get_discount_for_item(product, company, Decimal(str(item['qty'])))
            price = float(disc['discounted_price'])
            orig = float(product.unit_price)
            dpct = float(disc['total_percent'])
            zone = _classify_temp_zone(product)
            cold = product.requires_cold_chain
        except MarketplaceProduct.DoesNotExist:
            price = float(item['price'])
            orig = price
            dpct = 0
            zone = 'ambient'
            cold = False

        if cold:
            has_cold_chain = True

        line_total = price * item['qty']
        line_original = orig * item['qty']
        total += line_total
        total_savings += (line_original - line_total)

        enriched = {
            **item,
            'effective_price': price,
            'original_price': orig,
            'discount_percent': dpct,
            'has_discount': dpct > 0,
            'line_total': line_total,
            'line_original': line_original,
            'temp_zone': zone,
            'temp_zone_meta': TEMP_ZONE_META[zone],
        }
        items.append(enriched)
        items_by_zone.setdefault(zone, []).append(enriched)

    # Pfand Wallet -- aggregate packaging debt for buyer
    pfand_debt = 0
    try:
        from delivery.models import PackagingExchange
        pfand_debt = (
            PackagingExchange.objects
            .filter(delivery_stop__company=company, balance__gt=0)
            .aggregate(total=Sum('balance'))['total'] or 0
        )
    except DatabaseError:
        pass

    # Cut-off warning
    import datetime
    cutoff_warning = False
    delivery_date_str = request.GET.get('delivery_date', '')
    if delivery_date_str:
        try:
            ddate = datetime.date.fromisoformat(delivery_date_str)
            cutoff_dt = timezone.make_aware(
                datetime.datetime.combine(
                    ddate - datetime.timedelta(days=1),
                    datetime.time(22, 0)
                )
            )
            cutoff_warning = timezone.now() > cutoff_dt
        except (ValueError, TypeError):
            pass

    return render(request, 'marketplace/checkout.html', {
        'items': items,
        'items_by_zone': items_by_zone,
        'zone_meta': TEMP_ZONE_META,
        'total': total,
        'total_savings': total_savings,
        'company': company,
        'has_cold_chain': has_cold_chain,
        'pfand_debt': pfand_debt,
        'cutoff_warning': cutoff_warning,
    })


@login_required
def reorder(request, pk):
    """Repeat a previous order — copy items to cart."""
    original = get_object_or_404(MarketplaceOrder, pk=pk)
    company = get_user_company(request)
    if not company or original.buyer_company != company:
        messages.error(request, _('Nemate pristup ovoj narudzbi.'))
        return redirect('marketplace:my_orders')

    cart = {}
    for item in original.items.all().select_related('product'):
        if item.product and item.product.is_available:
            key = str(item.product.pk)
            disc = get_discount_for_item(item.product, company, item.quantity)
            cart[key] = {
                'product_id': item.product.pk,
                'name': item.product.name,
                'seller': item.product.seller_company.name,
                'seller_id': str(item.product.seller_company.pk),
                'price': str(disc['discounted_price']),
                'original_price': str(item.product.unit_price),
                'discount_percent': str(disc['total_percent']),
                'unit': item.product.unit,
                'qty': float(item.quantity),
            }
    request.session['marketplace_cart'] = cart
    messages.success(request, f'Narudzba {original.order_number} kopirana u kosaricu ({len(cart)} stavki).')
    return redirect('marketplace:cart')


@login_required
def my_orders(request):
    company = get_user_company(request)
    orders = MarketplaceOrder.objects.filter(buyer_company=company).order_by('-created_at') if company else MarketplaceOrder.objects.none()
    return render(request, 'marketplace/my_orders.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(MarketplaceOrder, pk=pk)
    items = order.items.all().select_related('product', 'seller_company')
    sub_orders = order.sub_orders.all().select_related('seller_company')
    total_savings = sum(getattr(i, 'discount_amount', 0) or 0 for i in items)
    return render(request, 'marketplace/order_detail.html', {
        'order': order, 'items': items, 'sub_orders': sub_orders,
        'total_savings': total_savings,
    })


@login_required
def seller_dashboard(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Nemate aktivnu firmu.'))
        return redirect('/')
    products = MarketplaceProduct.objects.filter(seller_company=company)
    all_sub_orders = SellerSubOrder.objects.filter(
        seller_company=company
    ).select_related('marketplace_order__buyer_company').order_by('-created_at')
    partner_count = PartnerDiscount.objects.filter(seller_company=company, is_active=True).count()
    stats = {
        'total_products': products.count(),
        'active_products': products.filter(is_available=True).count(),
        'pending_orders': all_sub_orders.filter(status='pending').count(),
        'this_month_revenue': all_sub_orders.filter(
            created_at__month=timezone.now().month,
            status__in=['confirmed', 'ready', 'collected', 'delivered']
        ).aggregate(total=Sum('seller_payout'))['total'] or 0,
        'partner_count': partner_count,
    }
    sub_orders = all_sub_orders[:20]
    return render(request, 'marketplace/seller_dashboard.html', {
        'company': company, 'products': products, 'sub_orders': sub_orders, 'stats': stats,
    })


@login_required
def seller_product_edit(request, pk=None):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    product = None
    if pk:
        product = get_object_or_404(MarketplaceProduct, pk=pk, seller_company=company)
    if request.method == 'POST':
        if not product:
            product = MarketplaceProduct(seller_company=company)
        product.name = request.POST.get('name', '')
        product.slug = request.POST.get('slug', '') or product.name.lower().replace(' ', '-').replace('/', '-')
        product.description = request.POST.get('description', '')
        product.unit_price = request.POST.get('unit_price', 0)
        product.unit = request.POST.get('unit', 'kg')
        product.min_order_qty = request.POST.get('min_order_qty', 1)
        product.available_qty = request.POST.get('available_qty', 0)
        product.is_organic = bool(request.POST.get('is_organic'))
        product.origin_region = request.POST.get('origin_region', '')
        product.requires_cold_chain = bool(request.POST.get('requires_cold_chain'))
        product.is_available = bool(request.POST.get('is_available', True))
        product.delivery_fee_per_unit = request.POST.get('delivery_fee_per_unit', 0)
        product.free_delivery_above = request.POST.get('free_delivery_above') or None
        product.pickup_available = bool(request.POST.get('pickup_available'))
        cat_id = request.POST.get('category')
        if cat_id:
            product.category_id = cat_id
        if 'image_main' in request.FILES:
            product.image_main = request.FILES['image_main']
        product.save()
        messages.success(request, f'Proizvod "{product.name}" spremljen.')
        return redirect('marketplace:seller_dashboard')
    categories = MarketplaceCategory.objects.filter(is_active=True)
    return render(request, 'marketplace/seller_product_form.html', {'product': product, 'categories': categories})


@login_required
def seller_order_action(request, pk):
    if request.method != 'POST':
        return redirect('marketplace:seller_dashboard')
    company = get_user_company(request)
    sub = get_object_or_404(SellerSubOrder, pk=pk, seller_company=company)
    action = request.POST.get('action')
    if action == 'confirm' and sub.status == 'pending':
        sub.status = 'confirmed'
        sub.save(update_fields=['status'])
        messages.success(request, f'Narudzba {sub.marketplace_order.order_number} potvrdjena.')
    elif action == 'ready' and sub.status == 'confirmed':
        sub.status = 'ready'
        sub.save(update_fields=['status'])
        messages.success(request, _('Oznaceno kao spremno za preuzimanje.'))
    elif action == 'reject' and sub.status == 'pending':
        sub.status = 'rejected'
        sub.save(update_fields=['status'])
        messages.warning(request, _('Narudzba odbijena.'))
    return redirect('marketplace:seller_dashboard')


# ── I-3: QR Reklamacija ────────────────────────────────────
def reklamacija_view(request, token):
    """Public-ish complaint form — accessed via QR on invoice."""
    from .models import OrderComplaint
    order = get_object_or_404(MarketplaceOrder, order_number=token)

    if request.method == 'POST':
        item_pk = request.POST.get('item_id')
        item = None
        if item_pk:
            item = order.items.filter(pk=item_pk).first()

        complaint = OrderComplaint.objects.create(
            order=order,
            item=item,
            reason=request.POST.get('reason', 'other'),
            description=request.POST.get('description', ''),
            created_by=request.user if request.user.is_authenticated else None,
        )
        photo = request.FILES.get('photo')
        if photo:
            complaint.photo = photo
            complaint.save(update_fields=['photo'])

        messages.success(request, f'Reklamacija #{complaint.pk} zaprimljena.')
        return redirect('marketplace:reklamacija_done', token=token)

    items = order.items.all().select_related('product')
    return render(request, 'marketplace/reklamacija.html', {
        'order': order,
        'items': items,
    })


def reklamacija_done(request, token):
    """Thank-you page after complaint submission."""
    order = get_object_or_404(MarketplaceOrder, order_number=token)
    return render(request, 'marketplace/reklamacija_done.html', {'order': order})


# ── I-4: Legal Vault ───────────────────────────────────────
@login_required
def legal_vault(request, pk):
    """Download ZIP archive with all documents for an order."""
    import io
    import zipfile
    from django.http import FileResponse

    order = get_object_or_404(MarketplaceOrder, pk=pk)
    company = get_user_company(request)
    if not company or order.buyer_company != company:
        messages.error(request, _('Nemate pristup ovoj narudzbi.'))
        return redirect('marketplace:my_orders')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Order summary
        summary = f"""NARUDZBA: {order.order_number}
Kupac: {order.buyer_company.name}
Datum: {order.created_at.strftime('%d.%m.%Y %H:%M')}
Status: {order.get_status_display()}
Ukupno: {order.total} EUR
Dostava: {order.get_delivery_method_display()}
Adresa: {order.delivery_address}

STAVKE:
"""
        for item in order.items.all().select_related('product'):
            summary += f"  - {item.product.name}: {item.quantity} x {item.unit_price} = {item.total} EUR\n"
        zf.writestr(f'narudzba_{order.order_number}.txt', summary)

        # 2. Invoice PDF (if exists)
        if order.invoice:
            inv = order.invoice
            inv_text = f"""RACUN: {inv.invoice_number if hasattr(inv, 'invoice_number') else inv.pk}
Status: {inv.get_status_display()}
Fiskalizirano: {'DA' if inv.is_fiscalized else 'NE'}
Datum: {inv.created_at.strftime('%d.%m.%Y') if hasattr(inv, 'created_at') else ''}
"""
            zf.writestr(f'racun_{order.order_number}.txt', inv_text)

        # 3. Delivery proof (signatures, photos from DeliveryStop)
        try:
            from delivery.models import DeliveryStop
            stops = DeliveryStop.objects.filter(marketplace_order=order)
            for stop in stops:
                if stop.signature_image:
                    try:
                        zf.write(stop.signature_image.path,
                                 f'potpis_stop_{stop.pk}{os.path.splitext(stop.signature_image.name)[1]}')
                    except OSError:
                        pass
                if stop.delivery_photo:
                    try:
                        zf.write(stop.delivery_photo.path,
                                 f'foto_stop_{stop.pk}{os.path.splitext(stop.delivery_photo.name)[1]}')
                    except OSError:
                        pass
        except OSError:
            pass

        # 4. HACCP incidents (if cold chain)
        if order.requires_cold_chain:
            try:
                from delivery.models import HACCPIncident, ConsolidatedDelivery
                cds = ConsolidatedDelivery.objects.filter(marketplace_orders=order)
                for cd in cds:
                    incidents = HACCPIncident.objects.filter(consolidated_delivery=cd)
                    for inc in incidents:
                        inc_text = f"""HACCP INCIDENT #{inc.pk}
Tip: {inc.get_incident_type_display()}
Severity: {inc.get_severity_display()}
SmartBox: {inc.smart_box.box_id if inc.smart_box else 'N/A'}
Max Temp: {inc.max_temperature} C
Pocetak: {inc.breach_start}
Trajanje: {inc.duration_minutes} min
Resolved: {'DA' if inc.is_resolved else 'NE'}
"""
                        if inc.is_resolved:
                            inc_text += f"Resolved by: {inc.resolved_by}\nNote: {inc.resolution_note}\n"
                        zf.writestr(f'haccp_incident_{inc.pk}.txt', inc_text)
            except DatabaseError:
                pass

        # 5. Complaints
        try:
            from .models import OrderComplaint
            for comp in OrderComplaint.objects.select_related("order", "order__seller").filter(order=order):
                comp_text = f"""REKLAMACIJA #{comp.pk}
Razlog: {comp.get_reason_display()}
Opis: {comp.description}
Status: {comp.get_status_display()}
Datum: {comp.created_at.strftime('%d.%m.%Y %H:%M')}
"""
                zf.writestr(f'reklamacija_{comp.pk}.txt', comp_text)
                if comp.photo:
                    try:
                        zf.write(comp.photo.path,
                                 f'reklamacija_foto_{comp.pk}{os.path.splitext(comp.photo.name)[1]}')
                    except OSError:
                        pass
        except OSError:
            pass

    buf.seek(0)
    return FileResponse(
        buf,
        as_attachment=True,
        filename=f'narudzba_{order.order_number}_vault.zip',
        content_type='application/zip',
    )


# ── WhatsApp Concierge ─────────────────────────────────────
@login_required
def cart_share_create(request):
    """Dispatcher creates a cart snapshot and gets a shareable link."""
    from .models import CartSnapshot
    from datetime import timedelta

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nemate aktivnu firmu.'}, status=400)

    cart = request.session.get('marketplace_cart', {})
    if not cart:
        return JsonResponse({'error': 'Kosarica je prazna.'}, status=400)

    # Build snapshot data with current prices
    snapshot_items = []
    total = Decimal('0')
    for key, item in cart.items():
        try:
            product = MarketplaceProduct.objects.get(pk=item['product_id'])
            disc = get_discount_for_item(product, company, Decimal(str(item['qty'])))
            price = disc['discounted_price']
        except MarketplaceProduct.DoesNotExist:
            price = Decimal(str(item.get('price', 0)))

        line_total = price * Decimal(str(item['qty']))
        total += line_total
        snapshot_items.append({
            'product_id': item['product_id'],
            'name': item.get('name', ''),
            'qty': float(item['qty']),
            'unit_price': str(price),
            'line_total': str(line_total),
            'unit': item.get('unit', 'kg'),
        })

    cart_data = {'items': snapshot_items, 'total': str(total)}
    cart_hash = CartSnapshot.compute_hash(cart_data)

    snapshot = CartSnapshot.objects.create(
        token=CartSnapshot.generate_token(),
        company=company,
        cart_data=cart_data,
        cart_hash=cart_hash,
        total=total,
        delivery_address=request.POST.get('delivery_address', company.address),
        delivery_method=request.POST.get('delivery_method', 'standard'),
        notes=request.POST.get('notes', ''),
        expires_at=timezone.now() + timedelta(minutes=60),
        created_by=request.user,
    )

    share_url = request.build_absolute_uri(f'/marketplace/checkout/shared/{snapshot.token}/')

    # Send via WhatsApp if phone provided
    phone = request.POST.get('phone', '').strip()
    wa_result = {'sent': False}
    if phone:
        from .notifications import send_cart_link
        wa_result = send_cart_link(snapshot, phone)

    return JsonResponse({
        'ok': True,
        'token': snapshot.token,
        'share_url': share_url,
        'expires_in_minutes': 60,
        'wa_sent': wa_result.get('sent', False),
        'wa_method': wa_result.get('method', 'none'),
    })


def cart_shared_checkout(request, token):
    """
    Public checkout page from shared link.
    Security: token expiry (Scenario 2.1), cart_hash validation (Scenario 2.2).
    """
    from .models import CartSnapshot, OrderComplaint

    snapshot = get_object_or_404(CartSnapshot, token=token)

    # Scenario 2.1: Token expired
    if snapshot.is_expired:
        return render(request, 'marketplace/cart_shared_expired.html', {
            'snapshot': snapshot,
        }, status=403)

    # Already used
    if snapshot.is_used:
        return render(request, 'marketplace/cart_shared_used.html', {
            'snapshot': snapshot,
            'order': snapshot.order,
        })

    if request.method == 'POST':
        from django.db import transaction

        # Scenario 2.2: Re-check hash — cart may have changed
        current_hash = CartSnapshot.compute_hash(snapshot.cart_data)
        if current_hash != snapshot.cart_hash:
            return render(request, 'marketplace/cart_shared_changed.html', {
                'snapshot': snapshot,
            }, status=409)

        # Re-check expiry at submit time
        if snapshot.is_expired:
            return render(request, 'marketplace/cart_shared_expired.html', {
                'snapshot': snapshot,
            }, status=403)

        with transaction.atomic():
            # Lock snapshot to prevent double-submit
            snap = CartSnapshot.objects.select_for_update().get(pk=snapshot.pk)
            if snap.is_used:
                return render(request, 'marketplace/cart_shared_used.html', {
                    'snapshot': snap, 'order': snap.order,
                })

            order = MarketplaceOrder.objects.create(
                buyer_company=snap.company,
                buyer_user=snap.created_by,
                delivery_address=snap.delivery_address,
                delivery_method=snap.delivery_method,
                delivery_notes=snap.notes,
            )

            seller_map = {}
            for item_data in snap.cart_data.get('items', []):
                try:
                    product = MarketplaceProduct.objects.get(pk=item_data['product_id'])
                except MarketplaceProduct.DoesNotExist:
                    continue

                qty = Decimal(str(item_data['qty']))
                price = Decimal(str(item_data['unit_price']))

                MarketplaceOrderItem.objects.create(
                    order=order, product=product,
                    seller_company=product.seller_company,
                    quantity=qty, unit_price=price,
                    total=price * qty,
                )
                sid = str(product.seller_company.pk)
                if sid not in seller_map:
                    seller_map[sid] = product.seller_company

            for sid, seller in seller_map.items():
                sub = SellerSubOrder.objects.create(
                    marketplace_order=order, seller_company=seller,
                    pickup_address=seller.address,
                )
                sub.recalculate()

            order.recalculate()

            # Draft invoice
            try:
                from invoicing.models import Invoice
                draft = Invoice.objects.create(
                    company=snap.company,
                    status='DRAFT',
                    is_fiscalized=False,
                    notes=f'Auto-draft via WA link {snap.token[:8]}',
                )
                order.invoice = draft
                order.save(update_fields=['invoice'])
            except (IntegrityError, DatabaseError):
                pass

            snap.is_used = True
            snap.order = order
            snap.save(update_fields=['is_used', 'order'])

        messages.success(request, f'Narudzba {order.order_number} kreirana!')
        return redirect('marketplace:order_detail', order.pk)

    # GET — show shared checkout
    items = snapshot.cart_data.get('items', [])
    return render(request, 'marketplace/cart_shared_checkout.html', {
        'snapshot': snapshot,
        'items': items,
        'total': snapshot.total,
    })


def traceability_view(request, pk):
    """Farm-to-Fork QR traceability page — public."""
    from .models import MarketplaceProduct
    from django.shortcuts import get_object_or_404
    import base64
    from io import BytesIO

    product = get_object_or_404(MarketplaceProduct, pk=pk)

    # Generate QR code pointing to this page
    qr_base64 = None
    try:
        import qrcode
        qr_url = request.build_absolute_uri()
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        qr_base64 = base64.b64encode(buf.read()).decode()
    except IOError:
        pass

    # Check karenca status for egg products
    karenca_active = False
    karenca_end = None
    if product.source_model == 'EggRecord' and product.source_id:
        try:
            from udruge.models import EggRecord
            egg = EggRecord.objects.select_related('flock').get(pk=product.source_id)
            if egg.flock.has_active_karenca:
                karenca_active = True
                karenca_end = egg.flock.karenca_end_date
        except Exception:
            pass

    return render(request, 'marketplace/traceability.html', {
        'product': product,
        'qr_base64': qr_base64,
        'karenca_active': karenca_active,
        'karenca_end': karenca_end,
    })



@login_required
def gastro_bridge(request, pk):
    """
    Gastro bridge: 1-click prebacivanje marketplace listinga u POS gastro meni.
    Marketplace oglas se gasi, POS dobiva novi artikl s -30% popustom.
    """
    from .models import MarketplaceProduct
    from django.shortcuts import get_object_or_404
    from decimal import Decimal

    product = get_object_or_404(MarketplaceProduct, pk=pk, seller_company=get_user_company(request))

    if request.method == 'POST':
        discount = Decimal('0.30')
        gastro_price = product.unit_price * (1 - discount)
        gastro_name = 'Dnevni specijal: %s (Last call)' % product.name[:80]

        # Kreiraj POS artikl
        try:
            from inventory.models import InventoryItem
            item, created = InventoryItem.objects.get_or_create(
                company=product.seller_company,
                sku='GASTRO-BRIDGE-%d' % product.pk,
                defaults={
                    'name': gastro_name,
                    'price': gastro_price,
                    'unit': product.unit,
                    'category': 'Dnevni specijal',
                    'is_active': True,
                    'track_stock': False,
                    'description': 'Auto-bridge s Marketplace. Izvorni: %s. Popust: 30%%.' % product.name,
                }
            )
            if not created:
                item.name = gastro_name
                item.price = gastro_price
                item.is_active = True
                item.save(update_fields=['name', 'price', 'is_active'])

            # Deaktiviraj marketplace listing
            product.is_available = False
            product.save(update_fields=['is_available'])

            messages.success(
                request,
                '"%s" prebaceno u gastro meni! Cijena: %.2f EUR (-30%%). '
                'Vidljivo na digitalnom meniju.' % (gastro_name, gastro_price)
            )
        except Exception as e:
            messages.error(request, _('Prebacivanje nije uspjelo. Pokušajte ponovo.'))

        return redirect('marketplace:seller_dashboard')

    # GET — confirmation page
    gastro_price = product.unit_price * Decimal('0.70')
    return render(request, 'marketplace/gastro_bridge.html', {
        'product': product,
        'gastro_price': gastro_price,
        'discount_percent': 30,
    })


def auction_live(request, pk):
    """Live auction page with WebSocket connection."""
    from .models import MarketplaceProduct
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(MarketplaceProduct, pk=pk, is_auction=True)
    return render(request, 'marketplace/auction_live.html', {'product': product})


def auction_state_api(request, pk):
    """HTTP fallback for auction state (when WebSocket unavailable)."""
    from .models import MarketplaceProduct
    from django.http import JsonResponse
    from django.utils import timezone

    try:
        product = MarketplaceProduct.objects.get(pk=pk, is_auction=True)
    except MarketplaceProduct.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    now = timezone.now()
    remaining = (product.expires_at - now).total_seconds() if product.expires_at else 0
    remaining = max(0, remaining)

    top_bids = list(
        product.bids.select_related('bidder_company')
        .order_by('-amount')[:5]
        .values('bidder_company__name', 'amount', 'created_at')
    )
    for b in top_bids:
        b['amount'] = str(b['amount'])
        b['created_at'] = b['created_at'].isoformat()

    return JsonResponse({
        'type': 'state',
        'product_id': product.pk,
        'current_bid': str(product.current_bid or product.starting_bid or product.unit_price),
        'bid_count': product.bid_count,
        'remaining_seconds': int(remaining),
        'expires_at': product.expires_at.isoformat() if product.expires_at else None,
        'auction_status': product.auction_status,
        'top_bids': top_bids,
        'is_ending_soon': remaining < 60,
    })
