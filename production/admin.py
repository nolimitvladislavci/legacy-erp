from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Workstation, BillOfMaterials, BOMLine,
    ProductionOrder, ProductionStep, QualityCheck, ProductionLog,
    MRPPlannedOrder,
)


class BOMLineInline(admin.TabularInline):
    model = BOMLine
    extra = 1
    fields = ('item', 'quantity', 'unit', 'waste_percent', 'sort_order', 'notes')


@admin.register(Workstation)
class WorkstationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'ws_type', 'status', 'capacity_per_hour', 'hourly_cost')
    list_filter = ('ws_type', 'status', 'company')
    search_fields = ('name', 'code')


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'output_item', 'output_quantity', 'version', 'status')
    list_filter = ('status', 'company')
    search_fields = ('name', 'code', 'output_item__name')
    inlines = [BOMLineInline]
    readonly_fields = ('created_at', 'updated_at')


class ProductionStepInline(admin.TabularInline):
    model = ProductionStep
    extra = 0
    fields = ('step_number', 'name', 'workstation', 'estimated_minutes', 'status')


class QualityCheckInline(admin.TabularInline):
    model = QualityCheck
    extra = 0
    fields = ('check_name', 'parameter', 'expected_value', 'actual_value', 'result')


class ProductionLogInline(admin.TabularInline):
    model = ProductionLog
    extra = 0
    readonly_fields = ('action', 'description', 'quantity', 'user', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'company', 'bom', 'planned_quantity',
                    'produced_quantity', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'company')
    search_fields = ('order_number', 'bom__name', 'batch_number')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductionStepInline, QualityCheckInline, ProductionLogInline]


@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ('check_name', 'order', 'parameter', 'expected_value', 'actual_value', 'result')
    list_filter = ('result',)



@admin.register(MRPPlannedOrder)
class MRPPlannedOrderAdmin(admin.ModelAdmin):
    list_display = ('item', 'order_type', 'quantity', 'needed_by', 'order_date', 'status', 'mrp_run_id')
    list_filter = ('order_type', 'status', 'company')
    search_fields = ('item__name', 'mrp_run_id')
    readonly_fields = ('id', 'created_at')
