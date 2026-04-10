from django.contrib import admin
from .models import (
    WindowProfile, GlassType, MeasurementSession,
    Measurement, WindowOffer, WindowWarranty, ServiceVisit,
    ProductionOrder, BOMItem, InstallationOrder,
    InstallationChecklist, HandoverProtocol,
    ServiceRiskProfile, ServiceMessage,
)


@admin.register(WindowProfile)
class WindowProfileAdmin(admin.ModelAdmin):
    list_display  = ['name', 'system', 'material', 'color_outer', 'price_per_m2', 'is_active']
    list_filter   = ['material', 'is_active', 'company']
    search_fields = ['name', 'system']


@admin.register(GlassType)
class GlassTypeAdmin(admin.ModelAdmin):
    list_display  = ['name', 'u_value', 'price_per_m2', 'is_active']
    list_filter   = ['is_active', 'company']


@admin.register(MeasurementSession)
class MeasurementSessionAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'address', 'created_by', 'total_items', 'confirmed_items', 'created_at']
    list_filter   = ['company', 'created_at']
    search_fields = ['address']
    readonly_fields = ['created_at']


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'element_type', 'wing_config', 'area_m2', 'confirmed', 'session']
    list_filter   = ['element_type', 'confirmed', 'session__company']
    readonly_fields = ['voice_raw', 'ai_parsed', 'area_m2', 'created_at']


@admin.register(WindowOffer)
class WindowOfferAdmin(admin.ModelAdmin):
    list_display  = ['offer_number', 'session', 'status', 'total_gross', 'created_at']
    list_filter   = ['status', 'company']
    readonly_fields = ['offer_number', 'created_at']


@admin.register(WindowWarranty)
class WindowWarrantyAdmin(admin.ModelAdmin):
    list_display  = ['warranty_number', 'session', 'issued_at', 'valid_years', 'next_service_date']
    readonly_fields = ['qr_token', 'issued_at']


@admin.register(ServiceVisit)
class ServiceVisitAdmin(admin.ModelAdmin):
    list_display  = ['warranty', 'scheduled', 'completed', 'technician', 'ai_reminder_sent']
    list_filter   = ['ai_reminder_sent']


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display  = ['order_number', 'offer', 'status', 'material_cost', 'estimated_date', 'created_at']
    list_filter   = ['status', 'company']
    search_fields = ['order_number']
    readonly_fields = ['order_number', 'created_at', 'updated_at']


@admin.register(BOMItem)
class BOMItemAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'quantity', 'unit', 'unit_price', 'total_price', 'ordered', 'received']
    list_filter   = ['category', 'ordered', 'received']
    search_fields = ['name']


@admin.register(InstallationOrder)
class InstallationOrderAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'scheduled_date', 'team_lead', 'status', 'completed_at']
    list_filter   = ['status', 'company']
    readonly_fields = ['created_at']


@admin.register(InstallationChecklist)
class InstallationChecklistAdmin(admin.ModelAdmin):
    list_display  = ['installation', 'measurement', 'is_complete', 'old_removed', 'frame_mounted', 'sealed']
    list_filter   = ['installation__company']


@admin.register(HandoverProtocol)
class HandoverProtocolAdmin(admin.ModelAdmin):
    list_display  = ['client_name', 'installation', 'accepted', 'signed_at', 'warranty']
    list_filter   = ['accepted']
    readonly_fields = ['signed_at', 'created_at']


@admin.register(ServiceRiskProfile)
class ServiceRiskProfileAdmin(admin.ModelAdmin):
    list_display  = ['warranty', 'risk_score', 'risk_level', 'predicted_issue', 'location_zone', 'calculated_at']
    list_filter   = ['risk_level', 'location_zone', 'predicted_issue']
    readonly_fields = ['calculated_at']


@admin.register(ServiceMessage)
class ServiceMessageAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'direction', 'channel', 'status', 'ai_sentiment', 'ai_category', 'created_at']
    list_filter   = ['status', 'direction', 'channel', 'ai_sentiment']
    search_fields = ['subject', 'sender_name', 'sender_email']
    readonly_fields = ['created_at', 'sent_at', 'approved_at']
