from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import PurchaseOrder, PurchaseOrderItem, SupplierPriceList

class POItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'supplier', 'status', 'priority', 'order_date', 'total', 'match_status', 'company']
    list_filter = ['status', 'priority', 'match_status', 'company']
    search_fields = ['po_number', 'supplier__name']
    inlines = [POItemInline]

@admin.register(SupplierPriceList)
class SupplierPriceListAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'inventory_item', 'agreed_price', 'valid_from', 'valid_until', 'company']
    list_filter = ['supplier', 'company']
