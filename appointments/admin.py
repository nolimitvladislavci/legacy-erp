from django.contrib import admin

from .models import *


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "employee", "start_time", "end_time", "status", "is_online"]
    search_fields = ["title", "client__name", "employee__username", "location"]
    list_filter = ["status", "is_online"]
    list_per_page = 50
    show_full_result_count = False


@admin.register(BookingService)
class BookingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "duration", "price", "resource_type", "is_active")
    list_filter = ("resource_type", "is_active")
    search_fields = ("name",)


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("resource", "get_day_of_week_display", "start_time", "end_time", "is_day_off")
    list_filter = ("resource", "day_of_week", "is_day_off")


from .models import BookingResource


@admin.register(BookingResource)
class BookingResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "resource_type", "is_active")
    list_filter = ("resource_type", "is_active")
    search_fields = ("name",)


@admin.register(ClientDossier)
class ClientDossierAdmin(admin.ModelAdmin):
    list_display = ("client", "company", "branch_type", "created_at", "updated_at")
    list_filter = ("branch_type", "company")
    search_fields = ("client__name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(DossierEntry)
class DossierEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "entry_type", "dossier", "created_by", "created_at")
    list_filter = ("entry_type",)
    search_fields = ("title", "content", "dossier__client__name")
    readonly_fields = ("created_at", "updated_at")
