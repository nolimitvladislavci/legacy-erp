from django.contrib import admin
from .models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "barcode", "unit_price", "tax_rate", "company"]
    list_filter = ["is_active"]
    search_fields = ["name", "sku", "barcode"]
