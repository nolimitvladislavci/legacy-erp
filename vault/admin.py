from django.contrib import admin

from .models import VaultAccessLog, VaultEntry, VaultMember


@admin.register(VaultMember)
class VaultMemberAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "trojstvo", "is_active", "can_write", "added_at"]
    list_filter = ["trojstvo", "is_active", "can_write"]
    raw_id_fields = ["user", "added_by"]


@admin.register(VaultEntry)
class VaultEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "priority", "visible_to", "username_hint", "updated_at"]
    list_filter = ["category", "priority", "visible_to", "is_active"]
    readonly_fields = ["_content_enc", "created_at", "updated_at"]
    exclude = ["_content_enc"]  # Nikad ne prikazuj šifrirani sadržaj direktno


@admin.register(VaultAccessLog)
class VaultAccessLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "entry", "ip_address"]
    list_filter = ["action", "user"]
    readonly_fields = ["timestamp", "user", "action", "entry", "ip_address"]

    def has_add_permission(self, request):
        return False  # Log je samo čitanje

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
