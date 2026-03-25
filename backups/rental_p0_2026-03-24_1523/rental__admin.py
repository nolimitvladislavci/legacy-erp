from rental.models import Property, Booking, SeasonalPrice, HousekeepingLog, Guest, GuestDocument, RentalInvoice, TrafficRecord
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


# ── F1 Modeli ──────────────────────────────────────────────────

class GuestInline(admin.TabularInline):
    model = Guest
    extra = 0
    fields = ['first_name', 'last_name', 'nationality', 'document_type',
              'document_number', 'is_primary', 'evisitor_synced']
    readonly_fields = ['evisitor_synced']


# Dodaj GuestInline u BookingAdmin
BookingAdmin.inlines = [GuestInline]


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'booking', 'nationality', 'document_type',
                    'is_primary', 'evisitor_synced', 'tourist_tax_category']
    list_filter = ['nationality', 'evisitor_synced', 'is_primary']
    search_fields = ['first_name', 'last_name', 'document_number']
    raw_id_fields = ['booking']


@admin.register(GuestDocument)
class GuestDocumentAdmin(admin.ModelAdmin):
    list_display = ['guest', 'ocr_confidence', 'ocr_processed', 'created_at']
    list_filter = ['ocr_processed']
    readonly_fields = ['ocr_raw', 'ocr_confidence', 'ocr_processed']


@admin.register(RentalInvoice)
class RentalInvoiceAdmin(admin.ModelAdmin):
    list_display = ['booking', 'accommodation_total', 'tourist_tax_total',
                    'cleaning_fee', 'total', 'is_cancelled', 'created_at']
    list_filter = ['is_cancelled']
    raw_id_fields = ['booking', 'invoice']


@admin.register(TrafficRecord)
class TrafficRecordAdmin(admin.ModelAdmin):
    list_display = ['date', 'guest_name', 'rental_property', 'amount',
                    'tourist_tax', 'total', 'invoice_number']
    list_filter = ['company']
    search_fields = ['guest_name', 'invoice_number']
    date_hierarchy = 'date'
