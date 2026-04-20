from django.contrib import admin

from core.models import SystemAuditLog


@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "company", "action", "model_name", "object_repr"]
    list_filter = ["action", "model_name", "company"]
    search_fields = ["object_repr", "model_name"]
    readonly_fields = [
        "timestamp",
        "user",
        "company",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "changes",
        "ip_address",
    ]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# QR Registry admin
from core.qr_registry_models import QRToken, QRScanLog


@admin.register(QRToken)
class QRTokenAdmin(admin.ModelAdmin):
    list_display = [
        "short",
        "object_type",
        "label",
        "company_name",
        "scan_count",
        "tamper_flag",
        "is_active",
        "created_at",
    ]
    list_filter = ["object_type", "tamper_flag", "is_active"]
    search_fields = ["token", "short", "label", "company_name", "object_ref"]
    readonly_fields = [
        "token",
        "short",
        "scan_count",
        "last_scan",
        "geo_log",
        "vc_payload",
        "viral_code",
        "viral_clicks",
        "viral_conversions",
        "created_at",
    ]
    list_select_related = False


@admin.register(QRScanLog)
class QRScanLogAdmin(admin.ModelAdmin):
    list_display = ["qr_token", "scanned_at", "ip_address", "country", "converted"]
    list_filter = ["converted", "country"]
    readonly_fields = ["qr_token", "scanned_at", "ip_address", "country", "user_agent", "referrer", "converted"]
    list_select_related = ["qr_token"]
