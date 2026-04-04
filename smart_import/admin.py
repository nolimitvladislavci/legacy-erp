from django.contrib import admin
from smart_import.models import (
    ImportBatch, ImportBatchItem, VendorItemMapping, CompanyMailbox,
    FailedImport, ProblemReport,
)
from smart_import.gemini_log import GeminiUsageLog


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display  = ("pk", "company", "supplier", "file_type", "status", "status_message",
                     "original_filename", "retry_count", "created_at")
    list_filter   = ("status", "file_type")
    raw_id_fields = ("supplier", "goods_receipt")
    readonly_fields = ("processing_started_at",)


@admin.register(ImportBatchItem)
class ImportBatchItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "row_index", "vendor_name", "quantity", "purchase_price", "match_score")


@admin.register(VendorItemMapping)
class VendorItemMappingAdmin(admin.ModelAdmin):
    list_display = ("vendor_item_name", "inventory_item", "partner", "company")


@admin.register(GeminiUsageLog)
class GeminiUsageLogAdmin(admin.ModelAdmin):
    list_display    = ("called_at", "caller", "model", "input_tokens", "output_tokens", "cost_eur", "success")
    list_filter     = ("caller", "success", "model")
    date_hierarchy  = "called_at"
    readonly_fields = ("called_at", "caller", "model", "input_tokens", "output_tokens", "cost_eur", "success", "input_hash")


@admin.register(CompanyMailbox)
class CompanyMailboxAdmin(admin.ModelAdmin):
    list_display = ("email_address", "company", "protocol", "is_active", "last_check", "total_imported")
    list_filter = ("is_active", "protocol")
    search_fields = ("email_address", "company__name")
    readonly_fields = ("last_check", "last_error", "total_imported", "created_at", "updated_at")


@admin.register(FailedImport)
class FailedImportAdmin(admin.ModelAdmin):
    list_display = ("filename", "company", "email_sender", "error_message", "created_at")
    list_filter = ("company",)
    readonly_fields = ("created_at",)


@admin.register(ProblemReport)
class ProblemReportAdmin(admin.ModelAdmin):
    list_display = ("pk", "batch", "company", "reported_by", "description", "resolved", "created_at")
    list_filter = ("resolved", "company")
    readonly_fields = ("batch", "company", "reported_by", "description", "created_at")
    actions = ["mark_resolved"]

    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True)
    mark_resolved.short_description = "Oznaci kao rijeseno"


from smart_import.models import FenixInboxItem

@admin.register(FenixInboxItem)
class FenixInboxItemAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'izvor', 'tip', 'partner_naziv', 'iznos', 'valuta', 'status', 'usmjereno_na')
    list_filter = ('izvor', 'tip', 'status')
    search_fields = ('partner_naziv', 'doc_broj', 'ai_summary')
    readonly_fields = ('created_at', 'updated_at', 'ai_summary', 'ai_prijedlog', 'ai_tip_confidence')
    date_hierarchy = 'created_at'
    list_per_page = 50
