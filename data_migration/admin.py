from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import MigrationProject, MigrationFile, MigrationLog, PermanentMigrationAudit


class MigrationFileInline(admin.TabularInline):
    model = MigrationFile
    extra = 0
    readonly_fields = ("uploaded_at", "expires_at", "file_size", "row_count")


class MigrationLogInline(admin.TabularInline):
    model = MigrationLog
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(MigrationProject)
class MigrationProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "source_program", "entity_type", "status", "created_at")
    list_filter = ("status", "entity_type", "source_program")
    search_fields = ("name", "company__name")
    readonly_fields = ("created_at", "updated_at", "completed_at")
    inlines = [MigrationFileInline, MigrationLogInline]


@admin.register(MigrationFile)
class MigrationFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "file_format", "file_size", "adapter_used", "row_count", "uploaded_at", "expires_at")
    list_filter = ("file_format",)
    readonly_fields = ("uploaded_at", "expires_at")


@admin.register(MigrationLog)
class MigrationLogAdmin(admin.ModelAdmin):
    list_display = ("project", "level", "entity_type", "row_number", "message", "created_at")
    list_filter = ("level", "entity_type")
    readonly_fields = ("created_at",)


@admin.register(PermanentMigrationAudit)
class PermanentMigrationAuditAdmin(admin.ModelAdmin):
    list_display = (
        "company_name", "user_email", "source_system", "original_filename",
        "entity_type", "records_created", "records_updated", "records_failed",
        "agreed_to_disclaimer", "execution_completed_at", "deletion_protected_until",
    )
    list_filter = ("entity_type", "agreed_to_disclaimer", "source_system")
    search_fields = ("company_name", "company_oib", "user_email", "original_filename")
    readonly_fields = (
        "id", "company_id", "company_name", "company_oib",
        "user_id", "user_email", "user_full_name",
        "source_system", "original_filename", "file_size_bytes", "file_sha256",
        "entity_type", "total_rows_in_file",
        "agreed_to_disclaimer", "disclaimer_text", "field_mapping_snapshot",
        "records_created", "records_updated", "records_skipped", "records_failed",
        "ip_address", "user_agent",
        "execution_started_at", "execution_completed_at", "deletion_protected_until",
    )

    def has_delete_permission(self, request, obj=None):
        """Zabrani brisanje iz admin panela — zakonska zastita."""
        return False

    def has_change_permission(self, request, obj=None):
        """Zabrani editiranje — audit zapis je imutabilan."""
        return False
