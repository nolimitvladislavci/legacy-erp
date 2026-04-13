from django.contrib import admin

from .models import TrackedItem, TrackingEvent, TrackingStatus


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(TrackingStatus)
class TrackingStatusAdmin(admin.ModelAdmin):
    list_display = ('tracking_type', 'name', 'slug', 'order', 'color')
    list_filter = ('tracking_type',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TrackedItem)
class TrackedItemAdmin(admin.ModelAdmin):
    list_display = ('pk', 'tracking_type', 'current_status', 'public_token', 'created_at')
    list_filter = ('tracking_type',)
    readonly_fields = ('public_token', 'created_at', 'updated_at')
    inlines = [TrackingEventInline]


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ('tracked_item', 'status', 'user', 'created_at')
    list_filter = ('status__tracking_type',)
    readonly_fields = ('created_at',)
