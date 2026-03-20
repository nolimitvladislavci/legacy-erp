from django.contrib import admin
from .models import PayrollRun, Payslip

class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = ('gross_amount', 'net_amount', 'tax_amount', 'is_paid')
    fields = ('user', 'total_hours', 'gross_amount', 'net_amount', 'is_paid')

@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ('company', 'month', 'year', 'status', 'total_gross', 'total_net')
    list_filter  = ('status', 'year', 'company')
    inlines = [PayslipInline]
    readonly_fields = ('finalized_at', 'pain001_generated_at')

@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('payroll_run', 'user', 'total_hours', 'gross_amount', 'net_amount', 'is_paid')
    list_filter  = ('is_paid', 'payroll_run__year', 'payroll_run__company')
    readonly_fields = ('hourly_rate_snapshot', 'overtime_rate_snapshot')
