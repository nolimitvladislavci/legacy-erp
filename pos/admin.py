from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    ExpiryBatch,
    GastroOrder,
    GastroOrderItem,
    POSPaymentLine,
    POSReceipt,
    POSReceiptItem,
    POSSession,
    POSSettings,
    POSTerminal,
    Table,
)


class POSReceiptItemInline(admin.TabularInline):
    model = POSReceiptItem
    extra = 0
    readonly_fields = ("total_price",)
    fields = (
        "barcode",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "discount_percent",
        "tax_rate_obj",
        "tax_rate",
        "total_price",
        "inventory_item",
    )


class POSPaymentLineInline(admin.TabularInline):
    model = POSPaymentLine
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("method", "amount", "change_given", "card_reference", "created_at")


class POSSessionInline(admin.TabularInline):
    model = POSSession
    extra = 0
    readonly_fields = ("opened_at", "closed_at", "session_number", "status")
    fields = ("session_number", "operator", "status", "opened_at", "closed_at", "opening_cash", "closing_cash")
    show_change_link = True


@admin.register(POSTerminal)
class POSTerminalAdmin(admin.ModelAdmin):
    list_display = ("name", "terminal_code", "company", "business_location", "is_active")
    list_filter = ("company", "is_active")
    search_fields = ("name", "terminal_code")
    inlines = [POSSessionInline]


@admin.register(POSSession)
class POSSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_number",
        "terminal",
        "operator",
        "status_badge",
        "opened_at",
        "closed_at",
        "opening_cash",
        "closing_cash",
        "receipt_count",
    )
    list_filter = ("terminal__company", "terminal", "status")
    search_fields = ("terminal__name", "operator__username")
    readonly_fields = ("opened_at",)

    def status_badge(self, obj):
        colors = {"open": "#16a34a", "closed": "#94a3b8", "z_done": "#3b82f6"}
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, "#94a3b8"),
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def receipt_count(self, obj):
        n = obj.receipts.filter(status="paid").count()
        return format_html("<strong>{}</strong>", n)

    receipt_count.short_description = _("Plaćenih bonova")


@admin.register(POSReceipt)
class POSReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "session", "status_badge", "total_display", "table_number", "paid_at", "invoice")
    list_filter = ("status", "session__terminal__company", "session__terminal")
    search_fields = ("receipt_number", "note", "table_number")
    readonly_fields = ("uuid", "created_at", "paid_at", "subtotal", "tax_amount", "total")
    inlines = [POSReceiptItemInline, POSPaymentLineInline]

    def status_badge(self, obj):
        colors = {"open": "#f59e0b", "paid": "#16a34a", "cancelled": "#ef4444", "refunded": "#8b5cf6"}
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, "#94a3b8"),
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def total_display(self, obj):
        color = "#16a34a" if obj.status == "paid" else "#0f172a"
        return format_html('<strong style="color:{}">{} EUR</strong>', color, obj.total)

    total_display.short_description = _("Ukupno")


# ── Gastro Admin ──────────────────────────────────────────────────────────────


class GastroOrderItemInline(admin.TabularInline):
    model = GastroOrderItem
    extra = 0
    raw_id_fields = ("inventory_item",)


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("name", "table_type", "capacity", "floor", "is_active", "is_occupied", "company")
    list_filter = ("company", "table_type", "is_active", "is_occupied")
    search_fields = ("name", "qr_code")
    readonly_fields = ("qr_code",)


@admin.register(GastroOrder)
class GastroOrderAdmin(admin.ModelAdmin):
    list_display = ("pk", "table", "status", "guest_name", "created_at", "company")
    list_filter = ("status", "company")
    search_fields = ("guest_name", "tracking_token")
    readonly_fields = ("tracking_token", "created_at", "updated_at")
    inlines = [GastroOrderItemInline]


# ── Expiry Admin ──────────────────────────────────────────────────────────────


@admin.register(ExpiryBatch)
class ExpiryBatchAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "batch_number",
        "quantity",
        "expiry_date",
        "alert_days_before",
        "is_removed",
        "company",
    )
    list_filter = ("company", "is_removed")
    search_fields = ("inventory_item__name", "batch_number")
    date_hierarchy = "expiry_date"


# ── POS Settings (porez na potrošnju) ─────────────────────────────────────


@admin.register(POSSettings)
class POSSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "fiscal_active",
        "consumption_tax_active",
        "consumption_tax_rate",
        "consumption_tax_jls_name",
    )
    list_filter = ("consumption_tax_active", "fiscal_active")
    fieldsets = (
        ("Tvrtka", {"fields": ("company",)}),
        ("Pisač", {"fields": ("printer_type", "printer_ip", "printer_port")}),
        ("Fiskalizacija", {"fields": ("fiscal_cert", "fiscal_cert_password", "fiscal_oib", "fiscal_active")}),
        ("Dostava računa", {"fields": ("receipt_delivery", "auto_print", "drawer_kick")}),
        (
            "Porez na potrošnju (čl.20 ZLP)",
            {
                "fields": ("consumption_tax_active", "consumption_tax_rate", "consumption_tax_jls_name"),
                "description": "Lokalni porez na ugostiteljske usluge. JLS propisuje stopu do 3%.",
            },
        ),
    )
