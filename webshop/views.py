import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from partners.models import Partner

from .models import Order, OrderItem, Product
from .serializers import OrderItemSerializer, OrderSerializer, ProductSerializer

# ── PRODUCTS ─────────────────────────────────────────────────


@login_required
def product_list(request):
    q = request.GET.get("q", "")
    category = request.GET.get("category", "")
    active = request.GET.get("active", "1")
    qs = Product.objects.order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category=category)
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)
    low_stock = [p for p in qs if p.stock <= 3 and not p.is_rental]
    return render(
        request,
        "webshop/product_list.html",
        {
            "products": qs,
            "q": q,
            "category": category,
            "active": active,
            "total": qs.count(),
            "category_choices": Product.CATEGORY_CHOICES,
            "low_stock_count": len(low_stock),
        },
    )


@login_required
def product_create(request):
    if request.method == "POST":
        try:
            p = Product(
                sku=request.POST["sku"],
                name=request.POST["name"],
                description=request.POST.get("description", ""),
                category=request.POST.get("category", "other"),
                price=request.POST.get("price", 0) or 0,
                stock=int(request.POST.get("stock", 0) or 0),
                is_rental="is_rental" in request.POST,
                is_active="is_active" in request.POST,
            )
            if "image" in request.FILES:
                p.image = request.FILES["image"]
            p.save()
            messages.success(request, f"Proizvod '{p.name}' kreiran.")
            return redirect("webshop:product_list")
        except (ValueError, TypeError) as e:
            messages.error(request, str(e))
    return render(
        request,
        "webshop/product_form.html",
        {
            "category_choices": Product.CATEGORY_CHOICES,
            "action": "Novi proizvod",
        },
    )


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        try:
            product.sku = request.POST["sku"]
            product.name = request.POST["name"]
            product.description = request.POST.get("description", "")
            product.category = request.POST.get("category", "other")
            product.price = request.POST.get("price", 0) or 0
            product.stock = int(request.POST.get("stock", 0) or 0)
            product.is_rental = "is_rental" in request.POST
            product.is_active = "is_active" in request.POST
            if "image" in request.FILES:
                product.image = request.FILES["image"]
            product.save()
            messages.success(request, f"Proizvod '{product.name}' ažuriran.")
            return redirect("webshop:product_list")
        except (ValueError, TypeError) as e:
            messages.error(request, str(e))
    return render(
        request,
        "webshop/product_form.html",
        {
            "product": product,
            "category_choices": Product.CATEGORY_CHOICES,
            "action": "Uredi proizvod",
        },
    )


# ── ORDERS ───────────────────────────────────────────────────


@login_required
def order_list(request):
    q = request.GET.get("q", "")
    status = request.GET.get("status", "")
    qs = Order.objects.select_related("customer").order_by("-created_at")
    if q:
        qs = qs.filter(Q(order_number__icontains=q) | Q(customer__name__icontains=q))
    if status:
        qs = qs.filter(status=status)
    total_revenue = (
        Order.objects.filter(status__in=["delivered", "shipped", "processing"]).aggregate(s=Sum("total_amount"))["s"]
        or 0
    )
    pending = Order.objects.filter(status="pending").count()
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "webshop/order_list.html",
        {
            "page_obj": page,
            "q": q,
            "status": status,
            "total": qs.count(),
            "total_revenue": total_revenue,
            "pending": pending,
            "status_choices": Order.STATUS_CHOICES,
        },
    )


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    items = order.items.select_related("product")
    return render(
        request,
        "webshop/order_detail.html",
        {
            "order": order,
            "items": items,
            "status_choices": Order.STATUS_CHOICES,
            "shipping_choices": Order.SHIPPING_CHOICES,
        },
    )


@login_required
def order_create(request):
    if request.method == "POST":
        try:
            customer = Partner.objects.get(pk=request.POST["customer"])
            order_num = "ORD-" + uuid.uuid4().hex[:8].upper()
            order = Order(
                order_number=order_num,
                customer=customer,
                status=request.POST.get("status", "pending"),
                notes=request.POST.get("notes", ""),
                shipping_address=request.POST.get("shipping_address", ""),
                shipping_method=request.POST.get("shipping_method", "osobni_preuzimanje"),
            )
            order.save()
            # Process items
            product_ids = request.POST.getlist("product_id")
            quantities = request.POST.getlist("quantity")
            total = 0
            for pid, qty in zip(product_ids, quantities):
                if pid and qty:
                    try:
                        prod = Product.objects.get(pk=int(pid))
                        q = int(qty)
                        item_total = prod.price * q
                        OrderItem.objects.create(
                            order=order,
                            product=prod,
                            quantity=q,
                            unit_price=prod.price,
                            total_price=item_total,
                        )
                        total += float(item_total)
                    except ObjectDoesNotExist:
                        pass
            order.total_amount = total
            order.save(update_fields=["total_amount"])
            messages.success(request, f"Narudžba {order_num} kreirana.")
            return redirect("webshop:order_detail", pk=order.pk)
        except ObjectDoesNotExist as e:
            messages.error(request, str(e))
    return render(
        request,
        "webshop/order_form.html",
        {
            "customers": Partner.objects.filter(is_active=True).order_by("name"),
            "products": Product.objects.filter(is_active=True).order_by("name"),
            "status_choices": Order.STATUS_CHOICES,
            "shipping_choices": Order.SHIPPING_CHOICES,
            "action": "Nova narudžba",
        },
    )


@login_required
def order_status_change(request, pk):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("status")
    tracking = request.POST.get("tracking_number", "")
    if new_status in dict(Order.STATUS_CHOICES):
        old_status = order.status
        order.status = new_status
        if tracking:
            order.tracking_number = tracking
        order.save(update_fields=["status", "tracking_number"])
        if new_status == "confirmed" and old_status not in ("confirmed", "processing", "shipped", "delivered"):
            try:
                from inventory.models import StockMovement as _SM

                for _oitem in order.items.select_related("product__inventory_item").all():
                    _inv = getattr(_oitem.product, "inventory_item", None)
                    if _inv:
                        _SM.objects.create(
                            item=_inv,
                            movement_type="out",
                            quantity=_oitem.quantity,
                            unit_price=_oitem.unit_price,
                            reason=f"Webshop narudžba #{order.order_number}",
                        )
            except (IntegrityError, DatabaseError):
                pass
        messages.success(request, f"Status narudžbe #{order.order_number} promijenjen.")
    return redirect("webshop:order_detail", pk=pk)


# ── REST ─────────────────────────────────────────────────────


@extend_schema_view(list=extend_schema(tags=["Webshop"]))
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from core.company_utils import get_user_company

        company = get_user_company(self.request)
        if company:
            return Product.objects.filter(company=company)
        return Product.objects.none()


@extend_schema_view(list=extend_schema(tags=["Webshop"]))
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(list=extend_schema(tags=["Webshop"]))
class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 11: Polymorphic Cart API
# ══════════════════════════════════════════════════════════════════════════════

from django.http import JsonResponse


def api_cart_add(request):
    """
    POST /webshop/api/cart/add/
    Body: {product_id: int, qty: int, attributes: {sph: str, cyl: str, ...}}
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    import json

    from webshop.cart_engine import CartError, add_to_cart

    try:
        data = json.loads(request.body)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Neispravan JSON."}, status=400)

    product_id = data.get("product_id")
    qty = data.get("qty", 1)
    attributes = data.get("attributes", {})

    if not product_id:
        return JsonResponse({"error": "product_id je obavezan."}, status=400)
    if not isinstance(qty, int) or qty < 1:
        return JsonResponse({"error": "qty mora biti pozitivan cijeli broj."}, status=400)

    try:
        cart_item = add_to_cart(
            user=request.user,
            product_id=product_id,
            qty=qty,
            attributes=attributes,
        )
        return JsonResponse(
            {
                "status": "ok",
                "cart_item_id": cart_item.pk,
                "message": f"{cart_item.product.name} x{qty} dodano u kosaricu.",
                "remaining_qty": cart_item.product.available_qty,
            }
        )
    except CartError as e:
        return JsonResponse(
            {
                "error": e.message,
                "code": e.code,
            },
            status=e.status,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# JAVNI WEBSHOP — bez prijave, po kompaniji
# ══════════════════════════════════════════════════════════════════════════════


def public_shop(request, company_slug):
    from django.db.models import Q

    from companies.models import Company

    company = get_object_or_404(Company, booking_slug=company_slug)

    cat = request.GET.get("cat", "")
    q = request.GET.get("q", "")
    sort = request.GET.get("sort", "name")

    qs = Product.objects.filter(company=company, is_active=True)
    if cat:
        qs = qs.filter(category=cat)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if sort == "price_asc":
        qs = qs.order_by("price")
    elif sort == "price_desc":
        qs = qs.order_by("-price")
    else:
        qs = qs.order_by("name")

    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get("page", 1))

    cats = Product.objects.filter(company=company, is_active=True).values_list("category", flat=True).distinct()

    cat_labels = dict(Product.CATEGORY_CHOICES)

    return render(
        request,
        "webshop/public/shop.html",
        {
            "company": company,
            "page": page,
            "products": page,
            "cat": cat,
            "q": q,
            "sort": sort,
            "cats": [(c, cat_labels.get(c, c)) for c in cats],
            "cat_labels": cat_labels,
        },
    )


def public_product(request, company_slug, pk):
    from companies.models import Company

    company = get_object_or_404(Company, booking_slug=company_slug)
    product = get_object_or_404(Product, pk=pk, company=company, is_active=True)

    related = Product.objects.filter(company=company, category=product.category, is_active=True).exclude(pk=pk)[:4]

    return render(
        request,
        "webshop/public/product.html",
        {
            "company": company,
            "product": product,
            "related": related,
            "is_optics": product.category == "OPTICS",
            "requires_sph": product.domain_attrs.get("requires_sph", False),
        },
    )


def public_cart(request, company_slug):
    from companies.models import Company

    company = get_object_or_404(Company, booking_slug=company_slug)

    cart = request.session.get("cart_" + company_slug, {})
    items = []
    total = 0
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(pk=int(pid), company=company, is_active=True)
            subtotal = p.price * qty
            total += subtotal
            items.append({"product": p, "qty": qty, "subtotal": subtotal})
        except Product.DoesNotExist:
            pass

    return render(
        request,
        "webshop/public/cart.html",
        {
            "company": company,
            "items": items,
            "total": total,
        },
    )


def public_cart_add(request, company_slug):
    from django.http import JsonResponse

    from companies.models import Company

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_object_or_404(Company, booking_slug=company_slug)
    try:
        import json as _json

        data = _json.loads(request.body)
        pid = str(int(data.get("product_id", 0)))
        qty = max(1, int(data.get("qty", 1)))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid"}, status=400)

    product = get_object_or_404(Product, pk=pid, company=company, is_active=True)

    key = "cart_" + company_slug
    cart = request.session.get(key, {})
    cart[pid] = cart.get(pid, 0) + qty
    request.session[key] = cart
    request.session.modified = True

    total_qty = sum(cart.values())
    return JsonResponse({"ok": True, "cart_count": total_qty, "name": product.name})


def public_cart_remove(request, company_slug):
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        import json as _json

        data = _json.loads(request.body)
        pid = str(int(data.get("product_id", 0)))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid"}, status=400)

    key = "cart_" + company_slug
    cart = request.session.get(key, {})
    cart.pop(pid, None)
    request.session[key] = cart
    request.session.modified = True
    return JsonResponse({"ok": True, "cart_count": sum(cart.values())})


def public_checkout(request, company_slug):
    from companies.models import Company

    company = get_object_or_404(Company, booking_slug=company_slug)

    cart = request.session.get("cart_" + company_slug, {})
    if not cart:
        from django.shortcuts import redirect

        return redirect("webshop:public_shop", company_slug=company_slug)

    items = []
    total = 0
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(pk=int(pid), company=company, is_active=True)
            subtotal = p.price * qty
            total += subtotal
            items.append({"product": p, "qty": qty, "subtotal": subtotal})
        except Product.DoesNotExist:
            pass

    DELIVERY_METHODS = [
        ("pickup", "Osobno preuzimanje u poslovnici", "0.00"),
        ("hp", "HP Express dostava", "4.99"),
        ("konjik", "Konjik d.o.o. dostava", "3.50"),
    ]
    PAYMENT_METHODS = [
        ("cash", "Gotovina u poslovnici"),
        ("card", "Kartica (u poslovnici)"),
        ("revolut", "Revolut"),
        ("paypal", "PayPal"),
        ("crypto", "Kriptovalute"),
    ]

    return render(
        request,
        "webshop/public/checkout.html",
        {
            "company": company,
            "items": items,
            "total": total,
            "delivery_methods": DELIVERY_METHODS,
            "payment_methods": PAYMENT_METHODS,
        },
    )


def public_checkout_submit(request, company_slug):
    import json as _json

    from django.http import JsonResponse

    from companies.models import Company

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_object_or_404(Company, booking_slug=company_slug)
    cart = request.session.get("cart_" + company_slug, {})
    if not cart:
        return JsonResponse({"error": "Košarica je prazna."}, status=400)

    try:
        data = _json.loads(request.body)
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        delivery_method = data.get("delivery_method", "pickup")
        payment_method = data.get("payment_method", "cash")
        address = data.get("address", "").strip()
        note = data.get("note", "").strip()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not name or not email:
        return JsonResponse({"error": "Ime i email su obavezni."}, status=400)

    # Kreiraj narudžbu
    delivery_prices = {"pickup": 0, "hp": 4.99, "konjik": 3.50}
    delivery_cost = delivery_prices.get(delivery_method, 0)

    items_total = 0
    order_items = []
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(pk=int(pid), company=company, is_active=True)
            subtotal = float(p.price) * qty
            items_total += subtotal
            order_items.append({"name": p.name, "qty": qty, "price": float(p.price), "subtotal": subtotal})
        except Product.DoesNotExist:
            pass

    grand_total = items_total + delivery_cost

    # Nadi ili kreiraj Partner (kupac)
    import uuid as _uuid

    from partners.models import Partner

    partner = Partner.objects.filter(email=email).first()
    if not partner:
        partner = Partner.objects.create(
            company=company,
            name=name,
            email=email,
            phone=phone,
            partner_type="KUPAC",
            oib="WEB" + _uuid.uuid4().hex[:8].upper(),
        )

    order_num = "WEB-" + str(company.pk)[:4].upper() + "-" + str(int(_uuid.uuid4().int % 100000)).zfill(5)
    order = Order.objects.create(
        order_number=order_num,
        customer=partner,
        status="pending",
        total_amount=grand_total,
        shipping_method=delivery_method
        if delivery_method in ["osobni_preuzimanje", "hp", "dostava", "dpd"]
        else "osobni_preuzimanje",
        shipping_address=address,
        notes=("Placanje: " + payment_method + ("\nNapomena: " + note if note else "")),
    )

    # Spremi stavke
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(pk=int(pid), company=company, is_active=True)
            OrderItem.objects.create(
                order=order,
                product=p,
                quantity=qty,
                unit_price=p.price,
                total_price=p.price * qty,
            )
        except ObjectDoesNotExist:
            pass

    # Očisti košaricu
    request.session["cart_" + company_slug] = {}
    request.session.modified = True

    # Email potvrda
    try:
        from core.email_tasks import send_email_task

        subject = "Potvrda narudžbe #" + str(order.pk) + " — " + company.name
        body = (
            "Hvala "
            + name
            + ",\n\nVasa narodzba je primljena.\n\n"
            + "Broj narodzbe: #"
            + str(order.pk)
            + "\n"
            + "Ukupno: "
            + str(grand_total)
            + " EUR\n"
            + "Dostava: "
            + delivery_method
            + "\n"
            + "Placanje: "
            + payment_method
            + "\n\n"
            + "Kontaktirat cemo vas uskoro.\n\n"
            + company.name
        )
        send_email_task.delay(subject, body, "noreply@limit-connect.com", [email])
    except ImportError:
        pass

    return JsonResponse({"ok": True, "order_id": order.pk, "message": "Narudžba #" + str(order.pk) + " je primljena!"})
