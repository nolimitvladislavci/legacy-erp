from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import Room, Resident, Relative, MonthlyCharge, StaffShift, Activity


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["number", "floor", "room_type", "capacity", "monthly_price", "is_available"]
    list_filter = ["company", "room_type", "is_available"]


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "room", "status", "admission_date"]
    list_filter = ["status", "company"]
    search_fields = ["first_name", "last_name", "oib"]


@admin.register(Relative)
class RelativeAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "resident", "relation", "is_primary_contact"]
    list_filter = ["relation"]
    search_fields = ["first_name", "last_name"]


@admin.register(MonthlyCharge)
class MonthlyChargeAdmin(admin.ModelAdmin):
    list_display = ["resident", "year", "month", "total_amount", "status"]
    list_filter = ["status", "year", "month"]


@admin.register(StaffShift)
class StaffShiftAdmin(admin.ModelAdmin):
    list_display = ["staff_member", "date", "shift_type"]
    list_filter = ["shift_type", "date"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "date", "organizer"]
    list_filter = ["category", "date"]
