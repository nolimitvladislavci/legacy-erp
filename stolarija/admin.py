from django.contrib import admin
from .models import (
    WindowProfile, GlassType, MeasurementSession,
    Measurement, WindowOffer, WindowWarranty, ServiceVisit
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
