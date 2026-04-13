from django.contrib import admin

from .models import CompanyRegistration, CompanySubscription, PromoCode, PropterTenant


@admin.register(CompanyRegistration)
class CompanyRegistrationAdmin(admin.ModelAdmin):
    list_display = ['name', 'oib', 'country', 'contact_email', 'selected_plan', 'status', 'created_at']
    list_filter = ['status', 'selected_plan', 'country', 'business_type']
    search_fields = ['name', 'oib', 'contact_email', 'contact_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'approved_at']
    ordering = ['-created_at']


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'monthly_fee', 'valid_from', 'valid_until', 'is_active']
    list_filter = ['plan', 'is_active']
    search_fields = ['company__name']
    readonly_fields = ['id', 'created_at']

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'promo_type', 'name', 'times_used', 'max_uses', 'is_active', 'valid_until', 'created_at']
    list_filter  = ['promo_type', 'is_active', 'is_superadmin_code']
    search_fields = ['code', 'name']
    readonly_fields = ['times_used', 'created_at']



@admin.register(PropterTenant)
class PropterTenantAdmin(admin.ModelAdmin):
    list_display = ['company', 'tier', 'operator_name', 'monthly_fee', 'fina_cert_status', 'eracuni_sent_month', 'is_active']
    list_filter = ['tier', 'is_active', 'fina_cert_status']
    search_fields = ['company__name', 'operator_name', 'company__oib']
    readonly_fields = ['created_at', 'updated_at', 'eracuni_sent_total', 'eracuni_sent_month']
    raw_id_fields = ['company', 'managed_by']


# ── Ugovori i dokumenti ──
from registration.models_contracts import CompanyDocument, ServiceAgreement, ServiceProvider


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "tax_id", "can_sell_software", "is_active"]
    list_filter = ["country", "can_sell_software"]

@admin.register(ServiceAgreement)
class ServiceAgreementAdmin(admin.ModelAdmin):
    list_display = ["agreement_number", "client_company", "provider", "agreement_type", "status", "monthly_fee", "payment_method", "valid_from"]
    list_filter = ["status", "agreement_type", "payment_method", "provider"]
    search_fields = ["agreement_number", "client_company__name"]
    readonly_fields = ["id", "created_at", "signed_at", "signed_ip"]
    date_hierarchy = "created_at"

@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ["company", "doc_type", "title", "issue_date", "created_at"]
    list_filter = ["doc_type"]
    search_fields = ["company__name", "title"]
