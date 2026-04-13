from django.contrib import admin

from .models import Campaign, CampaignContact, Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["email", "firm_name", "name", "city", "contact_type", "status", "source", "created_at"]
    list_filter = ["status", "contact_type", "source"]
    search_fields = ["email", "firm_name", "name", "city"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "active", "stat_sent", "stat_replied", "created_at"]


@admin.register(CampaignContact)
class CampaignContactAdmin(admin.ModelAdmin):
    list_display = ["campaign", "contact", "status", "sent_at"]
    list_filter = ["status", "campaign"]
