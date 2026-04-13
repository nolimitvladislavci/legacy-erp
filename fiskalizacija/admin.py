from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import FiscalConfig


@admin.register(FiscalConfig)
class FiscalConfigAdmin(admin.ModelAdmin):
    list_display  = ['company', 'is_active', 'is_demo', 'last_test_ok', 'last_test_at']
    list_filter   = ['is_active', 'is_demo']
    readonly_fields = ['last_test_at', 'last_test_ok', 'created_at', 'updated_at']
