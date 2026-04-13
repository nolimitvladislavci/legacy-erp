from django.contrib import admin

from core.models import SystemAuditLog


@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'company', 'action', 'model_name', 'object_repr']
    list_filter = ['action', 'model_name', 'company']
    search_fields = ['object_repr', 'model_name']
    readonly_fields = [
        'timestamp', 'user', 'company', 'action', 'model_name',
        'object_id', 'object_repr', 'changes', 'ip_address',
    ]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
