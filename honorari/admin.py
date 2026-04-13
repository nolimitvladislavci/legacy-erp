from django.contrib import admin

from .models import (
    HonorarCalculation,
    HonorarContract,
    HonorarJOPPD,
    HonorarPayment,
)


@admin.register(HonorarContract)
class HonorarContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 'company', 'contractor', 'contract_type',
        'gross_amount', 'start_date', 'end_date', 'status',
    ]
    list_filter = ['status', 'contract_type', 'company']
    search_fields = ['contract_number', 'description', 'contractor__name']
    raw_id_fields = ['contractor', 'company', 'created_by']


@admin.register(HonorarCalculation)
class HonorarCalculationAdmin(admin.ModelAdmin):
    list_display = [
        'contract', 'calculation_date', 'gross_amount',
        'tax_base', 'income_tax', 'net_amount', 'is_posted',
    ]
    list_filter = ['is_posted', 'calculation_date']
    search_fields = ['contract__contract_number']
    raw_id_fields = ['contract', 'journal_entry']


@admin.register(HonorarJOPPD)
class HonorarJOPPDAdmin(admin.ModelAdmin):
    list_display = [
        'joppd_date', 'joppd_oznaka', 'oib_primatelja',
        'bruto', 'porez', 'neto', 'is_reported',
    ]
    list_filter = ['is_reported', 'joppd_date', 'joppd_oznaka']
    search_fields = ['oib_primatelja']


@admin.register(HonorarPayment)
class HonorarPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'calculation', 'payment_date', 'amount',
        'bank_account', 'is_paid',
    ]
    list_filter = ['is_paid', 'payment_date']
    search_fields = ['reference']
    raw_id_fields = ['calculation', 'bank_account']
