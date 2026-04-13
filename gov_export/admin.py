from django.contrib import admin

from .models import GovDocumentType, GovExport, GovExportLog, GovInstitution


class GovExportLogInline(admin.TabularInline):
    model = GovExportLog
    extra = 0
    readonly_fields = ("timestamp", "step", "status", "message", "duration_ms", "actor")


@admin.register(GovInstitution)
class GovInstitutionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "transport", "requires_signature", "is_active")


@admin.register(GovDocumentType)
class GovDocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "institution", "period_type", "is_active")
    list_filter = ("institution",)


@admin.register(GovExport)
class GovExportAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "document_type", "company", "status", "xml_size", "created_at")
    list_filter = ("status", "document_type__institution")
    inlines = [GovExportLogInline]
    readonly_fields = ("xml_hash", "xml_size", "validated_at", "signed_at", "sent_at", "accepted_at")
