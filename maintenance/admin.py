from django.contrib import admin
from .models import Asset, MaintenanceSchedule, MaintenanceLog

class ScheduleInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0

class LogInline(admin.TabularInline):
    model = MaintenanceLog
    extra = 0

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['asset_code', 'name', 'category', 'status', 'location', 'assigned_to', 'company']
    list_filter = ['category', 'status', 'company']
    search_fields = ['asset_code', 'name', 'serial_number']
    inlines = [ScheduleInline, LogInline]

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ['task_name', 'asset', 'frequency', 'next_due', 'is_active']
    list_filter = ['frequency', 'is_active']

@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ['title', 'asset', 'maintenance_type', 'date_performed', 'total_cost']
    list_filter = ['maintenance_type']
