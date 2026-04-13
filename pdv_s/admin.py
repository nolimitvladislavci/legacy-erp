from django.contrib import admin

from .models import PDVSReport


@admin.register(PDVSReport)
class PDVSReportAdmin(admin.ModelAdmin):
    list_display = ('company', 'year', 'month', 'status', 'iv_razlika', 'generated_at')
    list_filter = ('status', 'year', 'company')
    readonly_fields = ('generated_at',)
