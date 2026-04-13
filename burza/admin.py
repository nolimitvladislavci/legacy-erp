from django.contrib import admin
from django.utils.html import format_html

from .models import LeadActivity, ProjectLead


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ("user", "action", "old_status", "new_status", "created_at")
    can_delete = False


@admin.register(ProjectLead)
class ProjectLeadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status_badge",
        "category",
        "location",
        "contact_name",
        "budget_display",
        "company",
        "taken_by",
        "created_at",
    )
    list_filter = ("status", "category", "is_public")
    search_fields = ("title", "contact_name", "location")
    readonly_fields = ("created_at", "updated_at", "taken_at")
    inlines = [LeadActivityInline]

    def status_badge(self, obj):
        colors = {"NOVI_UPIT": "#3b82f6", "INTERNA_PROCJENA": "#c9a84c", "NA_BURZI": "#10b981", "PREUZETO": "#8b5cf6"}
        c = colors.get(obj.status, "#666")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:4px;font-size:11px">{}</span>',
            c,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "user", "action", "old_status", "new_status", "created_at")
    readonly_fields = ("created_at",)
