from django.contrib import admin
from .models import Payment, PaymentConfig

@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ('company', 'stripe_enabled', 'btcpay_enabled', 'default_currency')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'source', 'method', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('method', 'status', 'source')
    search_fields = ('external_id', 'customer_email', 'source_id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at')
