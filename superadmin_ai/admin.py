from django.contrib import admin

from .models import AIActionLog, AIModulePermission, PendingAIAction


@admin.register(AIModulePermission)
class AIModulePermissionAdmin(admin.ModelAdmin):
    list_display = ("module", "company", "access_level", "updated_by", "updated_at")
    list_filter = ("access_level", "module", "company")
    search_fields = ("module", "company__name")


@admin.register(PendingAIAction)
class PendingAIActionAdmin(admin.ModelAdmin):
    list_display = ("module", "action_type", "company", "status", "created_at")
    list_filter = ("status", "module")
    readonly_fields = ("id", "created_at")


@admin.register(AIActionLog)
class AIActionLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "module", "action_type", "outcome", "company", "user")
    list_filter = ("outcome", "module")
    readonly_fields = ("id", "timestamp")
    date_hierarchy = "timestamp"
