from django.contrib import admin
from django.utils.html import format_html

from .models import FiscalConfiguration, FiscalLog


@admin.register(FiscalConfiguration)
class FiscalConfigurationAdmin(admin.ModelAdmin):
    list_display = ['company', 'branch', 'provider_badge', 'is_active', 'is_test_mode']
    list_filter = ['provider', 'is_active', 'is_test_mode']
    list_editable = ['is_active']
    fieldsets = (
        ('Opcenito', {
            'fields': ('company', 'branch', 'provider', 'is_active', 'is_test_mode'),
        }),
        ('HR - FINA CIS', {
            'classes': ('collapse',),
            'fields': ('certificate_file', 'certificate_password', 'oib', 'business_premise_id', 'device_id'),
        }),
        ('DE - fiskaly TSE', {
            'classes': ('collapse',),
            'fields': ('tse_api_key', 'tse_api_secret', 'tse_tss_id', 'tse_client_id'),
        }),
    )

    def provider_badge(self, obj):
        colors = {'hr_fina': ('#ef4444', 'HR FINA'), 'de_tse': ('#3b82f6', 'DE TSE'), 'none': ('#64748b', 'NONE')}
        color, label = colors.get(obj.provider, ('#64748b', obj.provider))
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700">{}</span>',
            color, label
        )
    provider_badge.short_description = 'Provider'


@admin.register(FiscalLog)
class FiscalLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'receipt_type', 'receipt_id', 'status_badge', 'zki_short', 'jir_short']
    list_filter = ['status', 'receipt_type', 'config__provider']
    search_fields = ['zki', 'jir', 'tse_transaction_number']
    readonly_fields = ['config', 'receipt_type', 'receipt_id', 'status', 'zki', 'jir',
                       'tse_signature', 'tse_transaction_number', 'tse_start_time', 'tse_end_time',
                       'request_xml', 'response_xml', 'error_message', 'qr_code_data', 'created_at']
    date_hierarchy = 'created_at'

    def status_badge(self, obj):
        colors = {'success': '#16a34a', 'error': '#ef4444', 'pending': '#f59e0b', 'retry': '#3b82f6'}
        return format_html('<span style="color:{}">{}</span>', colors.get(obj.status, '#64748b'), obj.get_status_display())
    status_badge.short_description = 'Status'

    def zki_short(self, obj):
        return (obj.zki[:12] + '...') if obj.zki else '-'
    zki_short.short_description = 'ZKI'

    def jir_short(self, obj):
        return (obj.jir[:12] + '...') if obj.jir else '-'
    jir_short.short_description = 'JIR'
