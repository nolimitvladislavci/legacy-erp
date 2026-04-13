from django.contrib import admin

from .models import HitnaIntervencija


@admin.register(HitnaIntervencija)
class HitnaIntervencijaAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "assigned_to", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "client_name", "address")
    raw_id_fields = ("assigned_to",)
