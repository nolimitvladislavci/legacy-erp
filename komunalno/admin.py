from django.contrib import admin

from .models import (
    AnnualQuota,
    CitizenCard,
    IllegalDumpReport,
    LightFaultReport,
    OntoExportBatch,
    ScaleReading,
    StreetLight,
    WasteCategory,
    WasteDelivery,
    WasteQuickButton,
    WasteStation,
)


class WasteQuickButtonInline(admin.TabularInline):
    model = WasteQuickButton
    extra = 0
    fields = ['label', 'category', 'icon', 'color', 'sort_order', 'is_active']


@admin.register(WasteStation)
class WasteStationAdmin(admin.ModelAdmin):
    list_display = ['name', 'station_type', 'address', 'scale_type', 'is_active', 'operator']
    list_filter = ['station_type', 'is_active', 'scale_type']
    search_fields = ['name', 'address']
    inlines = [WasteQuickButtonInline]
    fieldsets = (
        (None, {'fields': ('company', 'name', 'station_type', 'address', 'working_hours', 'is_active', 'operator')}),
        ('Geolokacija', {'fields': ('latitude', 'longitude'), 'classes': ('collapse',)}),
        ('Vaga', {'fields': ('scale_type', 'scale_port', 'scale_protocol', 'scale_baud_rate')}),
    )


@admin.register(WasteCategory)
class WasteCategoryAdmin(admin.ModelAdmin):
    list_display = ['key_number', 'name', 'category_group', 'is_hazardous', 'unit', 'default_annual_quota', 'price_per_unit_over_quota']
    list_filter = ['is_hazardous', 'category_group']
    search_fields = ['key_number', 'name']
    list_editable = ['default_annual_quota', 'price_per_unit_over_quota']


@admin.register(CitizenCard)
class CitizenCardAdmin(admin.ModelAdmin):
    list_display = ['card_number', 'partner', 'address', 'household_members', 'is_active', 'issued_date']
    list_filter = ['is_active']
    search_fields = ['card_number', 'partner__name', 'address']
    raw_id_fields = ['partner']


@admin.register(AnnualQuota)
class AnnualQuotaAdmin(admin.ModelAdmin):
    list_display = ['category', 'quota', 'year', 'company']
    list_filter = ['year']


@admin.register(WasteDelivery)
class WasteDeliveryAdmin(admin.ModelAdmin):
    list_display = ['citizen', 'category', 'quantity', 'unit', 'status', 'weight_source',
                    'over_quota', 'charge_amount', 'onto_exported', 'delivery_date']
    list_filter = ['status', 'weight_source', 'onto_exported', 'category']
    search_fields = ['citizen__partner__name', 'citizen__card_number']
    readonly_fields = ['integrity_hash', 'quota_before', 'over_quota', 'charge_amount']
    date_hierarchy = 'delivery_date'
    raw_id_fields = ['citizen', 'scale_reading', 'pos_receipt', 'onto_batch']


@admin.register(ScaleReading)
class ScaleReadingAdmin(admin.ModelAdmin):
    list_display = ['station', 'weight_kg', 'is_stable', 'source', 'is_tampered', 'read_at']
    list_filter = ['source', 'is_stable', 'is_tampered']
    readonly_fields = ['integrity_hash', 'raw_data', 'read_at']


@admin.register(OntoExportBatch)
class OntoExportBatchAdmin(admin.ModelAdmin):
    list_display = ['station', 'date_from', 'date_to', 'delivery_count', 'total_weight_kg',
                    'status', 'retry_count', 'sent_at']
    list_filter = ['status']
    readonly_fields = ['xml_payload', 'xml_hash', 'response_body', 'rejection_details',
                       'created_at', 'sent_at', 'completed_at']
    fieldsets = (
        (None, {'fields': ('company', 'station', 'date_from', 'date_to')}),
        ('Sadržaj', {'fields': ('delivery_count', 'total_weight_kg')}),
        ('Status', {'fields': ('status', 'retry_count', 'max_retries', 'last_error')}),
        ('XML', {'fields': ('xml_payload', 'xml_hash'), 'classes': ('collapse',)}),
        ('Odgovor', {'fields': ('response_code', 'response_body', 'accepted_count',
                                'rejected_count', 'rejection_details'), 'classes': ('collapse',)}),
        ('Datumi', {'fields': ('created_at', 'sent_at', 'completed_at')}),
    )


@admin.register(WasteQuickButton)
class WasteQuickButtonAdmin(admin.ModelAdmin):
    list_display = ['label', 'category', 'color', 'sort_order', 'station', 'is_active']
    list_editable = ['sort_order', 'is_active']


@admin.register(IllegalDumpReport)
class IllegalDumpReportAdmin(admin.ModelAdmin):
    list_display = ['location_description', 'status', 'priority', 'is_hazardous', 'fine_issued', 'reported_at']
    list_filter = ['status', 'priority', 'is_hazardous']
    search_fields = ['location_description', 'address']


@admin.register(StreetLight)
class StreetLightAdmin(admin.ModelAdmin):
    list_display = ['pole_number', 'street', 'lamp_type', 'wattage', 'is_functional', 'last_replaced']
    list_filter = ['lamp_type', 'is_functional']
    search_fields = ['pole_number', 'street']


@admin.register(LightFaultReport)
class LightFaultReportAdmin(admin.ModelAdmin):
    list_display = ['light', 'status', 'reported_by_citizen', 'assigned_to', 'reported_at']
    list_filter = ['status']
