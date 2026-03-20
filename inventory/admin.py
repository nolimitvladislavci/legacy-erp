from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import InventoryItem, StockMovement


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('movement_type', 'quantity', 'unit_price', 'reason', 'performed_by', 'invoice', 'created_at')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'company', 'category', 'quantity_display',
                    'unit', 'purchase_price', 'unit_price', 'tax_rate', 'is_active')
    search_fields = ('name', 'sku', 'barcode', 'description')
    list_filter = ('company', 'category', 'is_active', 'tax_rate')
    list_per_page = 50
    inlines = [StockMovementInline]
    fieldsets = (
        (_('Identifikacija'), {
            'fields': ('company', 'name', 'sku', 'barcode', 'category', 'description', 'unit', 'is_active'),
        }),
        (_('Zalihe'), {
            'fields': ('quantity', 'min_quantity', 'max_quantity'),
        }),
        (_('Cijene i PDV'), {
            'fields': ('purchase_price', 'unit_price', 'tax_rate'),
        }),
        (_('Logistika'), {
            'fields': ('location', 'supplier'),
        }),
    )

    def quantity_display(self, obj):
        color = '#ef4444' if obj.is_low_stock else '#16a34a'
        return format_html('<strong style="color:{}">{} {}</strong>', color, obj.quantity, obj.unit)
    quantity_display.short_description = _('Zaliha')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'movement_type', 'quantity', 'unit_price', 'invoice', 'performed_by', 'created_at')
    list_filter = ('movement_type', 'item__company')
    search_fields = ('item__name', 'item__sku', 'reason')
    list_per_page = 50
    readonly_fields = ('created_at',)
