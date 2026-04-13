from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .fiscal_models import BusinessLocation, FiscalConfig, FiscalOperator, TaxGroup


@admin.register(BusinessLocation)
class BusinessLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "location_code", "location_type", "address", "city", "is_active", "status_badge"]
    list_editable = ["is_active"]
    list_filter = ["location_type", "is_active"]
    search_fields = ["name", "location_code", "address"]
    fieldsets = (
        (
            _("Osnovni podaci"),
            {
                "fields": ("name", "location_code", "location_type", "is_active"),
            },
        ),
        (
            _("Adresa"),
            {
                "fields": ("address", "city", "oib"),
            },
        ),
        (
            _("Plaćanje"),
            {
                "fields": ("iban",),
            },
        ),
        (
            _("Napomena"),
            {
                "fields": ("notes",),
            },
        ),
    )

    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#16a34a;font-weight:600">● Aktivan</span>')
        return format_html('<span style="color:#ef4444">● Neaktivan</span>')

    status_badge.short_description = _("Status")


@admin.register(FiscalOperator)
class FiscalOperatorAdmin(admin.ModelAdmin):
    list_display = ["name", "oib", "user", "default_location", "is_active"]
    list_filter = ["is_active", "default_location"]
    search_fields = ["name", "oib"]
    fieldsets = (
        (
            _("Operater"),
            {
                "fields": ("name", "oib", "user", "is_active"),
            },
        ),
        (
            _("Zadano prodajno mjesto"),
            {
                "fields": ("default_location",),
            },
        ),
    )


@admin.register(TaxGroup)
class TaxGroupAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "rate_badge", "is_active"]
    list_editable = ["is_active"]
    list_filter = ["rate", "is_active"]

    def rate_badge(self, obj):
        colors = {"0": "#64748b", "5": "#3b82f6", "13": "#f59e0b", "25": "#ef4444"}
        return format_html(
            '<span style="background:{};color:white;padding:2px 10px;border-radius:3px;font-weight:700">{}%</span>',
            colors.get(obj.rate, "#64748b"),
            obj.rate,
        )

    rate_badge.short_description = _("Stopa")


@admin.register(FiscalConfig)
class FiscalConfigAdmin(admin.ModelAdmin):
    list_display = ["company_name", "oib", "endpoint_badge", "pdv_registered", "updated_at"]

    fieldsets = (
        (
            _("Tvrtka"),
            {
                "fields": ("company_name", "oib", "address", "pdv_registered", "pdv_id"),
            },
        ),
        (
            _("Certifikat"),
            {
                "fields": ("cert_path", "cert_password", "use_production"),
                "description": "⚠️ Lozinka certifikata se sprema na server. Koristite jake lozinke.",
            },
        ),
        (
            _("Numeracija računa"),
            {
                "fields": ("invoice_prefix_hr", "invoice_prefix_de", "next_invoice_number"),
            },
        ),
        (
            _("Zadane vrijednosti"),
            {
                "fields": ("default_due_days", "default_iban", "default_swift", "email_from"),
            },
        ),
        (
            _("Napomene na računima"),
            {
                "fields": ("footer_note_hr", "footer_note_de"),
            },
        ),
    )

    def endpoint_badge(self, obj):
        if obj.use_production:
            return format_html(
                '<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:3px;font-size:11px">⚡ PRODUKCIJA</span>'
            )
        return format_html(
            '<span style="background:#3b82f6;color:white;padding:2px 8px;border-radius:3px;font-size:11px">🧪 TEST</span>'
        )

    endpoint_badge.short_description = _("CIS Endpoint")

    def has_add_permission(self, request):
        return not FiscalConfig.objects.exists()
