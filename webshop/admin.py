from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import *


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 5
    fields = ['product', 'quantity', 'unit_price', 'total_price']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'price', 'stock', 'is_active', 'is_rental']
    search_fields = ['name', 'sku', 'description']
    list_filter = ['category', 'is_active', 'is_rental']
    list_per_page = 50
    show_full_result_count = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'total_amount', 'shipping_method', 'created_at']
    search_fields = ['order_number', 'customer__name', 'tracking_number']
    list_filter = ['status', 'shipping_method']
    inlines = [OrderItemInline]
    list_per_page = 50
    show_full_result_count = False

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_per_page = 50
    show_full_result_count = False
