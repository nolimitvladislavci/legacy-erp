from django.contrib import admin

from .models import FamilyStory, MemoryVault, TimeCapsule, WaitlistEntry


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "interest", "source", "notified", "created_at")
    list_filter = ("interest", "source", "notified")
    search_fields = ("email", "name")
    readonly_fields = ("id", "created_at")


@admin.register(TimeCapsule)
class TimeCapsuleAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_email", "open_date", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "owner_email")
    readonly_fields = ("id", "created_at", "opened_at")


@admin.register(MemoryVault)
class MemoryVaultAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_email", "category", "is_encrypted", "created_at")
    list_filter = ("category", "is_encrypted")
    search_fields = ("title", "owner_email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FamilyStory)
class FamilyStoryAdmin(admin.ModelAdmin):
    list_display = ("title", "author_email", "location", "is_public", "created_at")
    list_filter = ("is_public",)
    search_fields = ("title", "author_email", "content")
    readonly_fields = ("id", "created_at", "updated_at")
