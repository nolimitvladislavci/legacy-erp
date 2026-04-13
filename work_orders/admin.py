from django.contrib import admin

from .models import ClientCard, VehicleCard, WorkOrder, WorkOrderItem


class WorkOrderItemInline(admin.TabularInline):
    model = WorkOrderItem
    extra = 0


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "client", "status", "priority", "date", "total_gross", "company"]
    list_filter = ["status", "priority", "company"]
    search_fields = ["order_number", "client__name", "description"]
    inlines = [WorkOrderItemInline]


@admin.register(VehicleCard)
class VehicleCardAdmin(admin.ModelAdmin):
    list_display = ["registration_plate", "make", "model", "client", "mileage", "company"]
    search_fields = ["registration_plate", "vin", "make", "model", "client__name"]


@admin.register(ClientCard)
class ClientCardAdmin(admin.ModelAdmin):
    list_display = ["client", "card_type", "last_visit", "gdpr_consent", "company"]
    list_filter = ["card_type", "company"]
    search_fields = ["client__name"]
