from django.contrib import admin
from .models import MigrationProject, MigrationFile, MigrationLog


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
