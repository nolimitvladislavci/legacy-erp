from django.contrib import admin
from .models import (
    Experience, ExperienceSchedule, ExperienceBooking,
    ExperienceInclusion, ExperienceReview,
    AgroPackage, PackageComponent,
    RecallEvent, RecallNotification,
)


class ExperienceScheduleInline(admin.TabularInline):
    model = ExperienceSchedule
    extra = 1


class ExperienceInclusionInline(admin.TabularInline):
    model = ExperienceInclusion
    extra = 1


class ExperienceBookingInline(admin.TabularInline):
    model = ExperienceBooking
    extra = 0
    readonly_fields = ['price_total', 'deposit_amount']


class PackageComponentInline(admin.TabularInline):
    model = PackageComponent
    extra = 1


class RecallNotificationInline(admin.TabularInline):
    model = RecallNotification
    extra = 0


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ['name', 'experience_type', 'price_per_person', 'capacity', 'duration_minutes', 'is_active', 'company']
    list_filter = ['experience_type', 'is_active', 'company']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ExperienceInclusionInline, ExperienceScheduleInline]


@admin.register(ExperienceSchedule)
class ExperienceScheduleAdmin(admin.ModelAdmin):
    list_display = ['experience', 'date', 'time_from', 'time_to', 'booked_pax', 'max_pax', 'status']
    list_filter = ['status', 'date']
    date_hierarchy = 'date'
    inlines = [ExperienceBookingInline]


@admin.register(ExperienceBooking)
class ExperienceBookingAdmin(admin.ModelAdmin):
    readonly_fields = ('forfeited_invoice',)
    list_display = ['guest_name', 'schedule', 'pax_count', 'price_total', 'deposit_paid', 'status']
    list_filter = ['status', 'deposit_paid']
    search_fields = ['guest_name', 'guest_email']
    readonly_fields = ['price_total', 'deposit_amount']


@admin.register(ExperienceReview)
class ExperienceReviewAdmin(admin.ModelAdmin):
    list_display = ['booking', 'rating', 'is_public', 'created_at']
    list_filter = ['rating', 'is_public']


@admin.register(AgroPackage)
class AgroPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'advertised_price', 'duration_days', 'max_guests', 'is_active', 'company']
    list_filter = ['is_active', 'company']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [PackageComponentInline]

    def tax_breakdown_view(self, obj):
        return str(obj.tax_breakdown())
    tax_breakdown_view.short_description = 'PDV razbijanje'


@admin.register(RecallEvent)
class RecallEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'severity', 'status', 'source_model', 'source_id',
                     'affected_guests_count', 'affected_orders_count', 'created_at']
    list_filter = ['severity', 'status']
    search_fields = ['title', 'lot_number']
    readonly_fields = ['affected_guests_count', 'affected_orders_count']
    inlines = [RecallNotificationInline]


@admin.register(RecallNotification)
class RecallNotificationAdmin(admin.ModelAdmin):
    list_display = ['recall', 'channel', 'recipient_name', 'status', 'sent_at']
    list_filter = ['channel', 'status']
