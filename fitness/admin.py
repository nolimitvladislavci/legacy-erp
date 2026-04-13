from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import *


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'membership_type', 'status', 'phone'] # 'membership_expires' removed as it's not a direct field on Member
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'rfid_card']
    list_filter = ['membership_type', 'status']
    list_per_page = 50
    show_full_result_count = False

@admin.register(MemberCheckIn)
class MemberCheckInAdmin(admin.ModelAdmin):
    list_display = ['member', 'check_in_time', 'check_out_time'] # 'check_in' corrected to 'check_in_time'
    search_fields = ['member__first_name', 'member__last_name']
    list_filter = ['check_in_time']
    list_per_page = 50
    show_full_result_count = False

@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'billing_period', 'auto_renew', 'company']
    search_fields = ['name', 'company__name']
    list_filter = ['billing_period', 'auto_renew', 'company']
    list_per_page = 50

@admin.register(MemberSubscription)
class MemberSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['member', 'plan', 'valid_from', 'valid_until', 'status']
    search_fields = ['member__first_name', 'member__last_name', 'plan__name', 'payment_reference']
    list_filter = ['status', 'plan', 'valid_from', 'valid_until']
    raw_id_fields = ['member', 'plan'] # Korisno za odabir povezanih objekata
    list_per_page = 50

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'method', 'date', 'invoice_number', 'linked_subscription']
    search_fields = ['member__first_name', 'member__last_name', 'invoice_number', 'note']
    list_filter = ['method', 'date']
    raw_id_fields = ['member', 'linked_subscription'] # Korisno za odabir povezanih objekata
    list_per_page = 50

@admin.register(WorkoutClass)
class WorkoutClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'instructor', 'scheduled_at', 'capacity', 'location', 'class_type', 'company']
    search_fields = ['name', 'instructor', 'location', 'company__name']
    list_filter = ['class_type', 'instructor', 'scheduled_at', 'location', 'company']
    list_per_page = 50

@admin.register(ClassBooking)
class ClassBookingAdmin(admin.ModelAdmin):
    list_display = ['member', 'workout_class', 'booked_at', 'status']
    search_fields = ['member__first_name', 'member__last_name', 'workout_class__name']
    list_filter = ['status', 'booked_at', 'workout_class']
    raw_id_fields = ['member', 'workout_class'] # Korisno za odabir povezanih objekata
    list_per_page = 50

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'serial_number', 'status', 'location', 'purchase_date', 'last_service_date', 'company']
    search_fields = ['name', 'serial_number', 'location', 'company__name']
    list_filter = ['status', 'location', 'company']
    list_per_page = 50
