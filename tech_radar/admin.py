from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import TechSignal, CapacityThreshold


@admin.register(TechSignal)
class TechSignalAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'severity', 'db_size_mb', 'disk_used_pct', 'memory_used_pct', 'cpu_load_1m', 'active_sessions')
    list_filter = ('severity', 'source')
    ordering = ('-timestamp',)
    readonly_fields = ('id', 'timestamp', 'alerts', 'ai_summary')


@admin.register(CapacityThreshold)
class CapacityThresholdAdmin(admin.ModelAdmin):
    list_display = ('metric', 'warning_value', 'critical_value', 'is_active')
    list_editable = ('warning_value', 'critical_value', 'is_active')
