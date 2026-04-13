from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import SeasonalWorker, SeasonalContract, SeasonalPayment


@admin.register(SeasonalWorker)
class SeasonalWorkerAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'oib', 'nationality', 'phone', 'company', 'is_active']
    search_fields = ['first_name', 'last_name', 'oib']
    list_filter   = ['is_active', 'nationality']


@admin.register(SeasonalContract)
class SeasonalContractAdmin(admin.ModelAdmin):
    list_display  = ['worker', 'contract_type', 'status', 'start_date', 'end_date',
                     'gross_amount', 'hzmo_prijava_sent', 'hzmo_odjava_sent']
    list_filter   = ['status', 'contract_type', 'hzmo_prijava_sent']
    search_fields = ['worker__first_name', 'worker__last_name', 'worker__oib']
    date_hierarchy = 'start_date'


@admin.register(SeasonalPayment)
class SeasonalPaymentAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'gross_amount', 'net_amount', 'tax_amount',
                     'status', 'payment_date', 'joppd_generated']
    list_filter   = ['status', 'payment_method', 'joppd_generated']
