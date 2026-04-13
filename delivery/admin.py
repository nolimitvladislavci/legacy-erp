# Auto-register all models
import inspect

from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import models as _m
from .models import HACCPIncident

for name, obj in inspect.getmembers(_m):
    if inspect.isclass(obj) and issubclass(obj, _m.models.Model) and obj._meta.app_label == 'delivery':
        try:
            admin.site.register(obj)
        except admin.sites.AlreadyRegistered:
            pass


from .models import Rollwagen, PackagingExchange

try:
    admin.site.unregister(Rollwagen)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(PackagingExchange)
except admin.sites.NotRegistered:
    pass

@admin.register(Rollwagen)
class RollwagenAdmin(admin.ModelAdmin):
    list_display = ('qr_code', 'consolidated_delivery', 'delivery_stop', 'load_order', 'is_loaded', 'loaded_at')
    list_filter = ('is_loaded',)
    search_fields = ('qr_code',)

@admin.register(PackagingExchange)
class PackagingExchangeAdmin(admin.ModelAdmin):
    list_display = ('delivery_stop', 'packaging_type', 'delivered_qty', 'returned_qty', 'balance', 'created_at')
    list_filter = ('packaging_type',)

from .models import SmartBox, DeliveryCostRule, TransportHandoff, DispatchOffer

for _M in [SmartBox, DeliveryCostRule, TransportHandoff, DispatchOffer]:
    try:
        admin.site.unregister(_M)
    except admin.sites.NotRegistered:
        pass

@admin.register(SmartBox)
class SmartBoxAdmin(admin.ModelAdmin):
    list_display = ('box_id', 'box_type', 'status', 'has_sensor', 'has_gps', 'last_temp', 'last_reading_at')
    list_filter = ('box_type', 'status', 'has_sensor', 'has_gps')
    search_fields = ('box_id', 'qr_code')

@admin.register(DeliveryCostRule)
class DeliveryCostRuleAdmin(admin.ModelAdmin):
    list_display = ('hub_company', 'region', 'delivery_method', 'base_fee', 'per_km_fee', 'min_order_value', 'is_active')
    list_filter = ('region', 'delivery_method', 'is_active')
    list_editable = ('base_fee', 'per_km_fee', 'min_order_value', 'is_active')

@admin.register(TransportHandoff)
class TransportHandoffAdmin(admin.ModelAdmin):
    list_display = ('handoff_type', 'delivery_stop', 'performed_by', 'temperature_at_handoff', 'created_at')
    list_filter = ('handoff_type',)
    readonly_fields = ('haccp_checklist',)

@admin.register(DispatchOffer)
class DispatchOfferAdmin(admin.ModelAdmin):
    list_display = ('consolidated_delivery', 'driver', 'status', 'offered_price', 'driver_earnings', 'estimated_km', 'created_at')
    list_filter = ('status', 'requires_cold_chain')

# ── HACCP Incident ──
try:
    admin.site.unregister(HACCPIncident)
except admin.sites.NotRegistered:
    pass

@admin.register(HACCPIncident)
class HACCPIncidentAdmin(admin.ModelAdmin):
    list_display = ['id', 'incident_type', 'severity', 'smart_box', 'breach_start', 'max_temperature', 'duration_minutes', 'is_resolved', 'created_at']
    list_filter = ['incident_type', 'severity', 'is_resolved']
    readonly_fields = ['reading_ids', 'created_at']
    search_fields = ['smart_box__box_id', 'description']
    actions = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True, resolved_by=request.user, resolution_note='Bulk resolved via admin')
    mark_resolved.short_description = 'Mark selected as resolved'

