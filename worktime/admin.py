from django.contrib import admin

from .models import ActiveTimer, DailyNote, EmployeeProfile, Project, TimeEntry, TimeEntryTemplate, WorkGroup


@admin.register(WorkGroup)
class WorkGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'manager', 'created_at']
    list_filter = ['company']
    filter_horizontal = ['members']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'company', 'client_name', 'status', 'hourly_rate', 'is_billable']
    list_filter = ['company', 'status', 'is_billable']
    search_fields = ['code', 'name', 'client_name']
    filter_horizontal = ['members']

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'employee_id', 'hourly_rate', 'department', 'is_manager']
    list_filter = ['company', 'is_manager', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'project', 'date', 'duration', 'task_type', 'status', 'billing_amount']
    list_filter = ['company', 'status', 'task_type', 'is_billed']
    search_fields = ['user__username', 'project__name', 'description']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ActiveTimer)
class ActiveTimerAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'project', 'status', 'elapsed_display', 'started_at']
    list_filter = ['status']
    readonly_fields = ['elapsed_display', 'elapsed_seconds', 'elapsed_hours']

@admin.register(TimeEntryTemplate)
class TimeEntryTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'project', 'task_type', 'default_duration', 'use_count']
    list_filter = ['user', 'project']

@admin.register(DailyNote)
class DailyNoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'note']
    list_filter = ['user']
    date_hierarchy = 'date'


try:
    from worktime.models import TravelExpense, TravelOrder

    class TravelExpenseInline(admin.TabularInline):
        model = TravelExpense
        extra = 1

    @admin.register(TravelOrder)
    class TravelOrderAdmin(admin.ModelAdmin):
        list_display = ['order_number', 'employee', 'destination', 'departure_date', 'status', 'total_cost']
        list_filter = ['status', 'transport_type']
        search_fields = ['order_number', 'destination', 'employee__username']
        inlines = [TravelExpenseInline]
except ImportError as _e:
    import logging
    logging.getLogger(__name__).warning("TravelOrder admin skip: %s", _e)
