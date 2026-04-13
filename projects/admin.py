from django.contrib import admin

from .models import Project, ProjectPhoto, ProjectUpdate


class ProjectPhotoInline(admin.TabularInline):
    model = ProjectPhoto
    extra = 3
    fields = ["image", "caption", "is_public", "taken_at"]


class ProjectUpdateInline(admin.StackedInline):
    model = ProjectUpdate
    extra = 1
    fields = ["title", "content", "is_public"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "client", "manager", "status", "is_public", "start_date"]
    list_filter = ["status", "is_public", "company"]
    search_fields = ["name", "code", "location", "client__name"]
    inlines = [ProjectUpdateInline, ProjectPhotoInline]
    list_per_page = 30


@admin.register(ProjectPhoto)
class ProjectPhotoAdmin(admin.ModelAdmin):
    list_display = ["project", "uploaded_by", "caption", "is_public", "uploaded_at"]
    list_filter = ["is_public", "project"]
