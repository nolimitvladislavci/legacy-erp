from django.contrib import admin
from .models import BillingPeriod, Otpremnica, OtpremnicaItem, PropterConfig, EkoStats


class OtpremnicaItemInline(admin.TabularInline):
    model = OtpremnicaItem
    extra = 0
    readonly_fields = ("line_number", "description", "quantity", "unit",
                       "unit_price", "tax_rate", "line_total")


@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    list_display  = ("company", "year", "month", "status",
                     "otpremnica_count", "total_with_tax", "invoiced_at")
    list_filter   = ("status", "year", "month")
    search_fields = ("company__name",)
    readonly_fields = ("opened_at", "closed_at", "invoiced_at",
                       "total_net", "total_tax", "total_with_tax",
                       "otpremnica_count", "zbirni_eracun_id", "zbirni_invoice_number")
    actions = ["action_close_period", "action_aggregate"]

    def action_close_period(self, request, queryset):
        from propter.services.aggregate import close_period
        n = 0
        for p in queryset.filter(status__in=("open", "closing")):
            try:
                close_period(p)
                n += 1
            except Exception as e:
                self.message_user(request, f"Greska: {e}", level="error")
        self.message_user(request, f"{n} perioda zatvoreno.")
    action_close_period.short_description = "Zatvori period(e)"

    def action_aggregate(self, request, queryset):
        from propter.services.aggregate import aggregate_to_eracun
        n = 0
        for p in queryset.filter(status="closed"):
            try:
                aggregate_to_eracun(p, user=request.user)
                n += 1
            except Exception as e:
                self.message_user(request, f"Greska: {e}", level="error")
        self.message_user(request, f"{n} zbirnih e-Racuna kreirano.")
    action_aggregate.short_description = "Kreiraj zbirni e-Racun"


@admin.register(Otpremnica)
class OtpremnicaAdmin(admin.ModelAdmin):
    list_display  = ("number", "company", "recipient_name", "issue_date",
                     "total", "source", "status", "billing_period")
    list_filter   = ("status", "source", "issue_date")
    search_fields = ("number", "recipient_name", "recipient_oib")
    readonly_fields = ("id", "created_at", "updated_at", "billing_period",
                       "pos_receipt_id", "invoice_id")
    inlines = [OtpremnicaItemInline]


@admin.register(PropterConfig)
class PropterConfigAdmin(admin.ModelAdmin):
    list_display  = ("company", "tier", "monthly_fee", "cert_status",
                     "is_active", "eco_badge_enabled")
    list_filter   = ("tier", "cert_status", "is_active")
    search_fields = ("company__name", "operator_name")


@admin.register(EkoStats)
class EkoStatsAdmin(admin.ModelAdmin):
    list_display  = ("company", "year", "month", "eracuni_sent",
                     "paper_saved_sheets", "co2_saved_grams", "badge_level")
    list_filter   = ("badge_level", "year")
    search_fields = ("company__name",)
    readonly_fields = ("calculated_at",)
