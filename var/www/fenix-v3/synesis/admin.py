from django.contrib import admin
from .models import SynesisConfig, SynesisLog, SynesisExportQueue, SynesisYearConfig


@admin.register(SynesisConfig)
class SynesisConfigAdmin(admin.ModelAdmin):
    list_display = ["company", "is_active", "partners_total", "items_total", "last_sync_partners"]
    raw_id_fields = ["company"]


@admin.register(SynesisLog)
class SynesisLogAdmin(admin.ModelAdmin):
    list_display = ["company", "sync_type", "records_created", "records_updated", "errors", "synced_at"]
    list_filter = ["sync_type"]
    readonly_fields = ["synced_at"]


@admin.register(SynesisExportQueue)
class SynesisExportQueueAdmin(admin.ModelAdmin):
    list_display = ["company", "export_type", "action", "synesis_id", "is_exported", "is_confirmed"]
    list_filter = ["export_type", "is_exported"]


@admin.register(SynesisYearConfig)
class SynesisYearConfigAdmin(admin.ModelAdmin):
    list_display = ["config", "year", "invoices_total", "last_sync_invoices"]
