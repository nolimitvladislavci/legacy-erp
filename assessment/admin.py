from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import AssessmentPhoto, FieldAssessment


class AssessmentPhotoInline(admin.TabularInline):
    model = AssessmentPhoto
    extra = 0
    readonly_fields = ('uploaded_at',)
    fields = ('photo', 'caption', 'step', 'uploaded_at')


@admin.register(FieldAssessment)
class FieldAssessmentAdmin(admin.ModelAdmin):
    list_display  = ('id', 'client_name', 'assessment_type', 'status',
                     'calculated_price_from', 'calculated_price_to',
                     'created_by', 'created_at')
    list_filter   = ('assessment_type', 'status', 'created_at')
    search_fields = ('client_name', 'client_phone', 'client_email', 'client_address')
    readonly_fields = ('created_at', 'updated_at', 'completion_percent')
    inlines       = [AssessmentPhotoInline]
    fieldsets = (
        ('Klijent', {'fields': ('client_name', 'client_phone', 'client_email', 'client_address')}),
        ('Procjena', {'fields': ('assessment_type', 'status', 'company', 'created_by')}),
        ('Rezultat', {'fields': ('notes', 'calculated_price_from', 'calculated_price_to', 'voice_note')}),
        ('Veze', {'fields': ('linked_offer', 'linked_project')}),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )
