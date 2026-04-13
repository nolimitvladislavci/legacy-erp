from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import TaxFormType, TaxSubmission, TaxCalendar

@admin.register(TaxFormType)
class TaxFormTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'frequency', 'deadline_day')

@admin.register(TaxSubmission)
class TaxSubmissionAdmin(admin.ModelAdmin):
    list_display = ('company', 'form_type', 'period_year', 'period_month', 'status', 'deadline_date')
    list_filter = ('status', 'form_type', 'period_year')

@admin.register(TaxCalendar)
class TaxCalendarAdmin(admin.ModelAdmin):
    list_display = ('company', 'form_type', 'period_year', 'period_month', 'deadline', 'is_completed')
    list_filter = ('is_completed', 'form_type')
