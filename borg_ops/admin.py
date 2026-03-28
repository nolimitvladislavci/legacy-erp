from django.contrib import admin
from .models import CardActivity, StatusTimestamp


@admin.register(CardActivity)
class CardActivityAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'object_id', 'action', 'old_value', 'new_value', 'user', 'created_at')
    list_filter = ('action', 'content_type', 'created_at')
    search_fields = ('object_id', 'action', 'note')
    readonly_fields = ('content_type', 'object_id', 'user', 'action', 'old_value',
                       'new_value', 'note', 'ip_address', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StatusTimestamp)
class StatusTimestampAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'object_id', 'status', 'entered_at', 'exited_at', 'duration_seconds')
    list_filter = ('status', 'content_type')
    search_fields = ('object_id',)
    readonly_fields = ('content_type', 'object_id', 'status', 'entered_at',
                       'exited_at', 'duration_seconds', 'user')
    ordering = ('-entered_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
