from django.contrib import admin
from .models import (
    PetProfile, LifeEvent, EventMedia, SocialImport,
    Competition, CompetitionEntry, CompetitionVote, PetFollower, EventHeart
)


class LifeEventInline(admin.TabularInline):
    model = LifeEvent
    extra = 1


class EventMediaInline(admin.TabularInline):
    model = EventMedia
    extra = 1


@admin.register(PetProfile)
class PetProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'species', 'is_public', 'is_memorial', 'followers_count', 'created_at']
    list_filter = ['species', 'is_public', 'is_memorial', 'created_at']
    search_fields = ['name', 'owner__username', 'slug']
    readonly_fields = ['id', 'sha256_seal', 'created_at', 'updated_at']
    inlines = [LifeEventInline]


@admin.register(LifeEvent)
class LifeEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'pet', 'event_type', 'date', 'is_public', 'hearts_count', 'created_at']
    list_filter = ['event_type', 'is_public', 'date', 'created_at']
    search_fields = ['title', 'pet__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [EventMediaInline]


@admin.register(EventMedia)
class EventMediaAdmin(admin.ModelAdmin):
    list_display = ['event', 'file_type', 'order', 'created_at']
    list_filter = ['file_type', 'created_at']
    search_fields = ['event__title']
    readonly_fields = ['id', 'created_at']


@admin.register(SocialImport)
class SocialImportAdmin(admin.ModelAdmin):
    list_display = ['platform', 'pet', 'status', 'source_url', 'created_at']
    list_filter = ['platform', 'status', 'created_at']
    search_fields = ['pet__name', 'source_url']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'start_date', 'end_date', 'winner', 'created_at']
    list_filter = ['status', 'start_date', 'created_at']
    search_fields = ['title']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CompetitionEntry)
class CompetitionEntryAdmin(admin.ModelAdmin):
    list_display = ['competition', 'pet', 'votes', 'rank', 'created_at']
    list_filter = ['competition', 'created_at']
    search_fields = ['pet__name', 'competition__title']
    readonly_fields = ['id', 'created_at']


@admin.register(CompetitionVote)
class CompetitionVoteAdmin(admin.ModelAdmin):
    list_display = ['entry', 'voter_ip', 'voter_user', 'voted_at']
    list_filter = ['voted_at']
    search_fields = ['voter_ip', 'voter_user__username']
    readonly_fields = ['voted_at']


@admin.register(PetFollower)
class PetFollowerAdmin(admin.ModelAdmin):
    list_display = ['pet', 'follower', 'followed_at']
    list_filter = ['followed_at']
    search_fields = ['pet__name', 'follower__username']
    readonly_fields = ['followed_at']


@admin.register(EventHeart)
class EventHeartAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'ip', 'created_at']
    list_filter = ['created_at']
    search_fields = ['event__title', 'user__username', 'ip']
    readonly_fields = ['created_at']
