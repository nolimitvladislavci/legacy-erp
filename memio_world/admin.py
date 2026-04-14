from django.contrib import admin

from .models import FamilyStory, MemoryVault, TimeCapsule, WaitlistEntry
from .play_eu_models import EuropeanaItem, HeritageCard, ParallelStory


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


# ════════════════════════════════════════════════════════════════
# PLAY.EU — Sprint 1
# ════════════════════════════════════════════════════════════════


@admin.register(EuropeanaItem)
class EuropeanaItemAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "provider", "country", "rights", "is_commercially_usable", "is_curated")
    list_filter = ("category", "media_type", "is_commercially_usable", "is_curated", "country")
    search_fields = ("title", "europeana_id", "provider", "description")
    readonly_fields = ("id", "fetched_at", "updated_at")
    list_editable = ("is_curated",)


@admin.register(ParallelStory)
class ParallelStoryAdmin(admin.ModelAdmin):
    list_display = ("title_hr", "story_type", "source", "_languages", "is_published", "is_featured", "view_count")
    list_filter = ("story_type", "source", "is_published", "is_featured")
    search_fields = ("title_hr", "title_en", "title_de", "slug")
    prepopulated_fields = {"slug": ("title_hr",)}
    readonly_fields = ("id", "created_at", "updated_at", "view_count")
    list_editable = ("is_published", "is_featured")

    @admin.display(description="Jezici")
    def _languages(self, obj):
        return ", ".join(obj.available_languages())


@admin.register(HeritageCard)
class HeritageCardAdmin(admin.ModelAdmin):
    list_display = ("front_text", "card_type", "card_set", "position_in_set", "game_type", "is_published")
    list_filter = ("card_type", "card_set", "game_type", "is_published")
    search_fields = ("title", "front_text", "back_text", "slug")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("id", "created_at")
    list_editable = ("position_in_set", "is_published")
