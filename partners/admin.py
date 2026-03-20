from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Partner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'city', 'partner_type', 'oib',
                    'is_vat_registered', 'payment_term', 'cached_balance', 'is_active')
    list_filter = ('company', 'partner_type', 'country', 'is_vat_registered', 'is_active')
    search_fields = ('name', 'oib', 'vat_id', 'email', 'city', 'contact_person')
    readonly_fields = ('cached_balance', 'created_at', 'updated_at')
    fieldsets = (
        (_('Osnovno'), {
            'fields': ('company', 'name', 'oib', 'partner_type', 'is_active'),
        }),
        (_('Adresa'), {
            'fields': ('address', 'city', 'zip_code', 'country'),
        }),
        (_('Kontakt'), {
            'fields': ('email', 'phone', 'web'),
        }),
        (_('Kontakt osoba'), {
            'fields': ('contact_person', 'contact_phone', 'contact_email'),
            'classes': ('collapse',),
        }),
        (_('Bankovni podaci'), {
            'fields': ('iban', 'swift'),
            'classes': ('collapse',),
        }),
        (_('PDV'), {
            'fields': ('is_vat_registered', 'vat_id'),
        }),
        (_('Uvjeti poslovanja'), {
            'fields': ('payment_term', 'discount_percent', 'credit_limit'),
        }),
        (_('Financije (automatski)'), {
            'fields': ('cached_balance',),
        }),
        (_('Napomene'), {
            'fields': ('notes',),
        }),
        (_('Sustav'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
