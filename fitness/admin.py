from django.contrib import admin

from .models import *


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'membership_type', 'status', 'membership_expires', 'phone']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'rfid_card']
    list_filter = ['membership_type', 'status']
    list_per_page = 50
    show_full_result_count = False

@admin.register(MemberCheckIn)
class MemberCheckInAdmin(admin.ModelAdmin):
    list_display = ['member', 'check_in', 'check_out']
    list_per_page = 50
    show_full_result_count = False
