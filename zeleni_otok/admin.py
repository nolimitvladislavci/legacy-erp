from django.contrib import admin
from .models import (
    CompetitorProfile, ComparisonFeature, CompetitorFeatureStatus,
    MigrationRequest, ReferralProgram, ReferralRedemption,
    FreeToolUsage, SwitchWeekCampaign,
)


class CompetitorFeatureStatusInline(admin.TabularInline):
    model = CompetitorFeatureStatus
    extra = 0


@admin.register(CompetitorProfile)
class CompetitorProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'vendor', 'price_entry', 'price_top', 'has_ai_features', 'has_unlimited_invoices', 'is_active']
    list_filter = ['is_active', 'country']
    search_fields = ['name', 'vendor']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CompetitorFeatureStatusInline]


@admin.register(ComparisonFeature)
class ComparisonFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'lc_available', 'lc_note', 'is_highlight', 'sort_order']
    list_filter = ['category', 'lc_available', 'is_highlight']
    list_editable = ['sort_order', 'lc_available', 'is_highlight']
    search_fields = ['name']


@admin.register(MigrationRequest)
class MigrationRequestAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'source_system', 'status', 'contact_email', 'assigned_to', 'created_at']
    list_filter = ['status', 'source_system']
    search_fields = ['company_name', 'contact_email', 'oib']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'records_found', 'records_imported']
    fieldsets = (
        ('Tvrtka', {'fields': ('company_name', 'oib', 'contact_name', 'contact_email', 'contact_phone')}),
        ('Izvor', {'fields': ('source_system', 'source_version', 'source_plan')}),
        ('Što migrirati', {'fields': (
            'migrate_partners', 'migrate_articles', 'migrate_chart_of_accounts',
            'migrate_opening_balances', 'migrate_invoices', 'migrate_fixed_assets', 'migrate_employees'
        )}),
        ('Upload', {'fields': ('upload_file', 'upload_format')}),
        ('Status', {'fields': ('status', 'status_message', 'assigned_to', 'notes')}),
        ('Rezultati', {'fields': ('records_found', 'records_imported', 'records_skipped', 'validation_errors')}),
        ('Verifikacija', {'fields': ('verification_report', 'verified_by', 'verified_at')}),
        ('Referral', {'fields': ('referral_code',)}),
        ('Meta', {'fields': ('id', 'company', 'created_at', 'updated_at', 'completed_at')}),
    )


@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ['code', 'referrer_company', 'reward_type', 'times_used', 'total_revenue_generated', 'is_active']
    list_filter = ['reward_type', 'is_active']
    search_fields = ['code', 'referrer_company__name']
    readonly_fields = ['id', 'times_shared', 'times_used', 'total_revenue_generated', 'created_at']


@admin.register(ReferralRedemption)
class ReferralRedemptionAdmin(admin.ModelAdmin):
    list_display = ['new_company', 'referral', 'reward_applied', 'created_at']
    list_filter = ['reward_applied']
    readonly_fields = ['created_at']


@admin.register(FreeToolUsage)
class FreeToolUsageAdmin(admin.ModelAdmin):
    list_display = ['tool', 'email', 'company_name', 'converted_to_signup', 'utm_source', 'created_at']
    list_filter = ['tool', 'converted_to_signup', 'utm_source']
    search_fields = ['email', 'company_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(SwitchWeekCampaign)
class SwitchWeekCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'free_months', 'signups', 'migrations_completed', 'is_active']
    list_filter = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['signups', 'migrations_started', 'migrations_completed']
