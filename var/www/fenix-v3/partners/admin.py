from django.contrib import admin
from .models import Partner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "oib", "city", "partner_type", "company"]
    list_filter = ["partner_type", "is_active"]
    search_fields = ["name", "oib", "email"]
