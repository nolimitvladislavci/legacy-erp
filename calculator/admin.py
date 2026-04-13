from django.contrib import admin

from .models import Calculation, CalculationItem, Normative


class CalculationItemInline(admin.TabularInline):
    model = CalculationItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price_material', 'labor_hours_per_unit', 'labor_rate_applied')

@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = ('project', 'get_net_total', 'margin_percentage', 'updated_at')
    inlines = [CalculationItemInline]

    def get_net_total(self, obj):
        return obj.calculate_totals()['net_cost']
    get_net_total.short_description = 'Ukupni Trošak (Neto)'

@admin.register(Normative)
class NormativeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'base_material_cost', 'estimated_hours_per_unit')
