from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    KindergartenGroup, Child, Guardian, ChildGuardian,
    Attendance, MonthlyBilling, DailyReport, Announcement,
)


@admin.register(KindergartenGroup)
class KindergartenGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'capacity', 'monthly_price', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'group', 'status', 'date_of_birth']
    list_filter = ['status', 'group', 'company']
    search_fields = ['first_name', 'last_name', 'oib']


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'phone', 'email']
    search_fields = ['first_name', 'last_name', 'oib']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['child', 'date', 'status']
    list_filter = ['status', 'date']


@admin.register(MonthlyBilling)
class MonthlyBillingAdmin(admin.ModelAdmin):
    list_display = ['child', 'year', 'month', 'total_amount', 'status']
    list_filter = ['status', 'year', 'month']


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ['group', 'date', 'is_published']
    list_filter = ['is_published', 'group']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'is_published', 'published_at']
    list_filter = ['priority', 'is_published']


admin.site.register(ChildGuardian)
