from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Transaction, TransactionCategory


@admin.register(TransactionCategory)
class TransactionCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category_type', 'is_active', 'sort_order')
    list_filter = ('category_type', 'is_active')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name', 'code')
    ordering = ('sort_order', 'name')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'direction', 'amount', 'tax_amount', 'category', 'partner',
                    'company', 'invoice', 'is_reconciled', 'reference')
    list_filter = ('direction', 'company', 'category', 'is_reconciled', 'date')
    search_fields = ('partner__name', 'description', 'reference')
    date_hierarchy = 'date'
    list_editable = ('is_reconciled',)
    readonly_fields = ('created_at',)
    fieldsets = (
        (_('Transakcija'), {
            'fields': ('company', 'partner', 'direction', 'category', 'amount', 'tax_amount', 'date', 'value_date'),
        }),
        (_('Opis i referenca'), {
            'fields': ('description', 'reference', 'payment_account'),
        }),
        (_('Veze'), {
            'fields': ('invoice', 'document', 'is_reconciled'),
        }),
        (_('Sustav'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
