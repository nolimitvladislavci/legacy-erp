from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AgentPayout, AgentReferral, Partner


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


@admin.register(AgentReferral)
class AgentReferralAdmin(admin.ModelAdmin):
    list_display = ('agent', 'referred_company', 'referral_code', 'status',
                    'commission_percent', 'total_earned', 'total_paid', 'created_at')
    list_filter = ('status',)
    search_fields = ('agent__name', 'referred_company__name', 'referral_code')
    readonly_fields = ('id', 'created_at', 'contract_signed_at', 'contract_ip')


@admin.register(AgentPayout)
class AgentPayoutAdmin(admin.ModelAdmin):
    list_display = ('agent', 'period_month', 'period_year', 'amount',
                    'referrals_count', 'status', 'paid_at')
    list_filter = ('status', 'period_year')
    list_editable = ('status',)
    readonly_fields = ('id', 'created_at', 'breakdown')
