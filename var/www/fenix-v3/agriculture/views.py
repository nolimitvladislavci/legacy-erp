from django.views.generic import ListView, DetailView
from django.db.models import Sum
from core.base_view import TenantView
from .models import Field, LivestockHerd


class FieldListView(TenantView, ListView):
    model = Field
    template_name = "agriculture/field_list.html"
    context_object_name = "fields"

    def get_queryset(self):
        return Field.objects.filter(company=self.company)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_ha"] = Field.objects.filter(company=self.company).aggregate(total=Sum("area_ha"))["total"] or 0
        ctx["herds"] = LivestockHerd.objects.filter(company=self.company)
        return ctx


class FieldDetailView(TenantView, DetailView):
    model = Field
    template_name = "agriculture/field_detail.html"
    context_object_name = "field"

    def get_queryset(self):
        return Field.objects.filter(company=self.company)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["crops"] = self.object.crops.order_by("-year")
        ctx["activities"] = self.object.activities.order_by("-date")[:20]
        return ctx
