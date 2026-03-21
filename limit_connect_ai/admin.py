from django.contrib import admin
from .models import (
    AIAgentMission, AIReportLog, FundApplicationDraft,
    ComplianceWatchItem, CampaignPlan,
)


@admin.register(AIAgentMission)
class AIAgentMissionAdmin(admin.ModelAdmin):
    list_display = ['company', 'mission_type', 'title', 'is_active', 'frequency', 'next_run', 'last_run']
    list_filter = ['is_active', 'mission_type', 'frequency', 'notify_channel']
    search_fields = ['title', 'company__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(AIReportLog)
class AIReportLogAdmin(admin.ModelAdmin):
    list_display = ['company', 'report_type', 'sent_via', 'status', 'sent_at', 'ai_tokens_used']
    list_filter = ['status', 'sent_via', 'report_type']
    search_fields = ['company__name', 'content']
    readonly_fields = ['id']


@admin.register(FundApplicationDraft)
class FundApplicationDraftAdmin(admin.ModelAdmin):
    list_display = ['company', 'fund_opportunity', 'status', 'eligibility_score', 'created_at']
    list_filter = ['status']
    search_fields = ['company__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(ComplianceWatchItem)
class ComplianceWatchItemAdmin(admin.ModelAdmin):
    list_display = ['company', 'law_reference', 'status', 'deadline', 'last_checked']
    list_filter = ['status']
    search_fields = ['company__name', 'law_reference', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CampaignPlan)
class CampaignPlanAdmin(admin.ModelAdmin):
    list_display = ['company', 'title', 'campaign_type', 'channel', 'status', 'ai_suggestion', 'planned_date']
    list_filter = ['status', 'campaign_type', 'channel', 'ai_suggestion']
    search_fields = ['company__name', 'title']
    readonly_fields = ['id', 'created_at', 'updated_at']
