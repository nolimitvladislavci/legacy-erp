from django.contrib import admin
from .models import Property, Booking, SeasonalPrice, HousekeepingLog

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'type', 'floor', 'capacity', 'price_per_night', 'status', 'is_active')
    list_filter = ('type', 'status', 'company')
    search_fields = ('name',)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_number', 'guest_name', 'rental_property', 'check_in', 'check_out', 'total_price', 'status')
    list_filter = ('status', 'source')
    search_fields = ('booking_number', 'guest_name', 'guest_email')

@admin.register(SeasonalPrice)
class SeasonalPriceAdmin(admin.ModelAdmin):
    list_display = ('rental_property', 'name', 'start_date', 'end_date', 'price_per_night')

@admin.register(HousekeepingLog)
class HousekeepingLogAdmin(admin.ModelAdmin):
    list_display = ('rental_property', 'status', 'assigned_to', 'created_at', 'completed_at')
    list_filter = ('status',)
