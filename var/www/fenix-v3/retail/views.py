from django.views.generic import ListView
from django.db.models import F, Q
from core.base_view import TenantView
from .models import Product, RetailSale


class ProductListView(TenantView, ListView):
    model = Product
    template_name = "retail/product_list.html"
    context_object_name = "products"

    def get_queryset(self):
        qs = Product.objects.filter(company=self.company, is_active=True).select_related("category")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["low_stock_count"] = Product.objects.filter(
            company=self.company,
            is_active=True,
            stock_quantity__lte=F("min_stock"),
        ).count()
        return ctx


class SaleListView(TenantView, ListView):
    model = RetailSale
    template_name = "retail/sale_list.html"
    context_object_name = "sales"

    def get_queryset(self):
        return RetailSale.objects.filter(company=self.company).order_by("-created_at")[:100]
