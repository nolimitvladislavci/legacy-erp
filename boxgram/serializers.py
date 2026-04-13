from rest_framework import serializers
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    PetProfile, LifeEvent, EventMedia, SocialImport,
    Competition, CompetitionEntry
)


class EventMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMedia
        fields = ['id', 'file', 'file_type', 'source_url', 'thumbnail_url', 'order', 'created_at']


class LifeEventSerializer(serializers.ModelSerializer):
    media = EventMediaSerializer(many=True, read_only=True)
    
    class Meta:
        model = LifeEvent
        fields = ['id', 'pet', 'event_type', 'title', 'description', 'date', 'location', 'source', 'source_url', 'is_public', 'is_verified', 'hearts_count', 'comments_count', 'media', 'created_at']


class PetProfileSerializer(serializers.ModelSerializer):
    life_events = LifeEventSerializer(many=True, read_only=True)
    
    class Meta:
        model = PetProfile
        fields = ['id', 'name', 'species', 'breed', 'birth_date', 'death_date', 'bio', 'avatar', 'cover_photo', 'slug', 'is_public', 'is_memorial', 'is_verified_breeder', 'is_vet_verified', 'followers_count', 'hearts_count', 'life_events', 'created_at']


class SocialImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialImport
        fields = ['id', 'pet', 'platform', 'source_url', 'raw_data', 'status', 'mapped_to', 'created_at']


class CompetitionEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionEntry
        fields = ['id', 'competition', 'pet', 'media', 'votes', 'rank', 'created_at']


class CompetitionSerializer(serializers.ModelSerializer):
    entries = CompetitionEntrySerializer(many=True, read_only=True)
    
    class Meta:
        model = Competition
        fields = ['id', 'title', 'species_filter', 'start_date', 'end_date', 'status', 'winner', 'entries', 'created_at']
