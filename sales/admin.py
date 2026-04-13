"""
sales/admin.py — Admin za cjenike, narudžbe, saldakonti.
"""

from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    RabatGroup, CustomerPriceList, PriceListLine,
    SalesOrder, SalesOrderLine, OpenItem, IOSReport,
)


# ═══════════════════════════════════════════════════════════════
#  CJENICI
# ═══════════════════════════════════════════════════════════════

@admin.register(RabatGroup)
class RabatGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company')
    list_filter = ('company',)
    search_fields = ('name', 'code')
    ordering = ('name',)


class PriceListLineInline(admin.TabularInline):
    model = PriceListLine
    extra = 1
    fields = ('item', 'rabat_group', 'discount_type', 'discount_value', 'min_quantity', 'cassa_days')
    autocomplete_fields = ('item', 'rabat_group')


@admin.register(CustomerPriceList)
class CustomerPriceListAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner', 'partner_group', 'is_active', 'priority',
                    'valid_from', 'valid_until', 'ai_suggested', 'company')
    list_filter = ('company', 'is_active', 'ai_suggested')
    search_fields = ('name', 'partner__name', 'partner_group')
    ordering = ('priority', 'name')
    inlines = [PriceListLineInline]
    autocomplete_fields = ('partner', 'company')
    date_hierarchy = 'created_at'


@admin.register(PriceListLine)
class PriceListLineAdmin(admin.ModelAdmin):
    list_display = ('price_list', 'item', 'rabat_group', 'discount_type', 'discount_value', 'min_quantity')
    list_filter = ('discount_type', 'price_list__company')
    search_fields = ('item__name', 'rabat_group__name', 'price_list__name')
    autocomplete_fields = ('item', 'rabat_group', 'price_list')


# ═══════════════════════════════════════════════════════════════
#  NARUDŽBE
# ═══════════════════════════════════════════════════════════════

class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1
    fields = ('item', 'quantity', 'unit', 'unit_price', 'discount_percent',
              'tax_rate', 'delivered_quantity', 'is_ai_suggested', 'sort_order')
    autocomplete_fields = ('item',)


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'partner', 'order_date', 'status', 'priority',
                    'total', 'currency', 'company')
    list_filter = ('company', 'status', 'priority', 'ai_predicted')
    search_fields = ('order_number', 'partner__name')
    ordering = ('-order_date',)
    inlines = [SalesOrderLineInline]
    autocomplete_fields = ('partner', 'company', 'price_list')
    date_hierarchy = 'order_date'
    readonly_fields = ('subtotal', 'discount_total', 'tax_total', 'total', 'created_at', 'updated_at')


@admin.register(SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'item', 'quantity', 'unit_price', 'discount_percent',
                    'delivered_quantity', 'is_ai_suggested')
    list_filter = ('is_ai_suggested', 'order__company')
    search_fields = ('item__name', 'order__order_number')
    autocomplete_fields = ('item', 'order')


# ═══════════════════════════════════════════════════════════════
#  SALDAKONTI
# ═══════════════════════════════════════════════════════════════

@admin.register(OpenItem)
class OpenItemAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'partner', 'direction', 'original_amount',
                    'paid_amount', 'remaining', 'due_date', 'is_closed', 'ai_risk_score', 'company')
    list_filter = ('company', 'direction', 'is_closed')
    search_fields = ('document_number', 'partner__name')
    ordering = ('due_date',)
    date_hierarchy = 'due_date'
    readonly_fields = ('created_at', 'updated_at', 'closed_at')

    def remaining(self, obj):
        return obj.remaining
    remaining.short_description = 'Preostalo'


@admin.register(IOSReport)
class IOSReportAdmin(admin.ModelAdmin):
    list_display = ('partner', 'report_date', 'total_receivable', 'total_payable',
                    'net_balance', 'items_count', 'sent_at', 'confirmed_at', 'company')
    list_filter = ('company',)
    search_fields = ('partner__name',)
    ordering = ('-report_date',)
    date_hierarchy = 'report_date'
    readonly_fields = ('created_at',)
