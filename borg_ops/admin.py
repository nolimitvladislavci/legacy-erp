from django.contrib import admin

from .models import CardActivity, StatusTimestamp


@admin.register(CardActivity)
class CardActivityAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "action", "old_value", "new_value", "user", "created_at")
    list_filter = ("action", "content_type", "created_at")
    search_fields = ("object_id", "action", "note")
    readonly_fields = (
        "content_type",
        "object_id",
        "user",
        "action",
        "old_value",
        "new_value",
        "note",
        "ip_address",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StatusTimestamp)
class StatusTimestampAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "status", "entered_at", "exited_at", "duration_seconds")
    list_filter = ("status", "content_type")
    search_fields = ("object_id",)
    readonly_fields = ("content_type", "object_id", "status", "entered_at", "exited_at", "duration_seconds", "user")
    ordering = ("-entered_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


from .models import DomainRegistry


@admin.register(DomainRegistry)
class DomainRegistryAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "registrar",
        "purpose",
        "expires_at",
        "days_until_expiry",
        "auto_renew",
        "privacy_protection",
        "ssl_expires_at",
    )
    list_filter = ("registrar", "purpose", "auto_renew")
    search_fields = ("domain", "notes")
    readonly_fields = ("created_at", "updated_at")

    def days_until_expiry(self, obj):
        d = obj.days_until_expiry
        if d <= 7:
            return f"⚠️ {d} dana!"
        elif d <= 30:
            return f"⏰ {d} dana"
        return f"{d} dana"

    days_until_expiry.short_description = "Do isteka"


# ── Fenix Agent Command Center ────────────────────────────────────────────────

from .models import AgentTask, AgentTaskLog  # noqa: E402 (vec importirano gore)


class AgentTaskLogInline(admin.TabularInline):
    model = AgentTaskLog
    extra = 0
    readonly_fields = ["tool_type", "tool_input", "tool_output", "is_approval_gate", "duration_ms", "created_at"]
    can_delete = False
    max_num = 0


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "agent",
        "scope",
        "status",
        "cost_display",
        "requires_approval",
        "created_by",
        "created_at",
    ]
    list_filter = ["agent", "status", "scope", "requires_approval"]
    readonly_fields = ["id", "tokens_in", "tokens_out", "cost_usd", "approved_at", "created_at", "updated_at"]
    search_fields = ["title", "instruction"]
    inlines = [AgentTaskLogInline]
    actions = ["mark_approved", "mark_rejected"]

    def cost_display(self, obj):
        return obj.cost_display

    cost_display.short_description = "Trošak"

    def mark_approved(self, request, queryset):
        queryset.filter(status="awaiting").update(status="approved")

    mark_approved.short_description = "Odobri odabrane"

    def mark_rejected(self, request, queryset):
        queryset.filter(status="awaiting").update(status="rejected")

    mark_rejected.short_description = "Odbaci odabrane"


@admin.register(AgentTaskLog)
class AgentTaskLogAdmin(admin.ModelAdmin):
    list_display = ["task", "tool_type", "is_approval_gate", "duration_ms", "created_at"]
    list_filter = ["tool_type", "is_approval_gate"]
    readonly_fields = ["created_at"]
    search_fields = ["task__title", "tool_input", "tool_output"]
