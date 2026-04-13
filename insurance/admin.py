from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import *


@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    list_display = ['policy_number', 'insurance_type', 'insurer', 'partner', 'start_date', 'end_date', 'premium', 'status']
    search_fields = ['policy_number', 'insurer', 'partner__name']
    list_filter = ['insurance_type', 'status']
    list_per_page = 50
    show_full_result_count = False
