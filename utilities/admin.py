from django.contrib import admin
from .models import UtilityContract, MeterReading, UtilityBill


@admin.register(UtilityContract)
class UtilityContractAdmin(admin.ModelAdmin):
    list_display = ('utility_type', 'provider_name', 'company', 'meter_id', 'start_date', 'end_date', 'is_active')
    list_filter = ('utility_type', 'is_active')
    search_fields = ('provider_name', 'contract_number', 'meter_id')


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('contract', 'date', 'value', 'consumption', 'source')
    list_filter = ('source',)
    date_hierarchy = 'date'


@admin.register(UtilityBill)
class UtilityBillAdmin(admin.ModelAdmin):
    list_display = ('contract', 'period_from', 'period_to', 'total', 'is_anomaly', 'status')
    list_filter = ('status', 'is_anomaly', 'contract__utility_type')
    date_hierarchy = 'issue_date'
