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


# ── BORG FENIX: Knowledge Graph Admin ──────────────────────────────────────
from .models_knowledge_graph import (
    RegulatorySource, RegulatoryUpdate, ImpactDomain,
    AdaptationRule, LegalOpportunity, ClientOpportunityMatch,
)


@admin.register(RegulatorySource)
class RegulatorySourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'is_active', 'last_scraped', 'scrape_interval_hours']
    list_filter = ['source_type', 'is_active']


class ImpactDomainInline(admin.TabularInline):
    model = ImpactDomain
    extra = 0


class AdaptationRuleInline(admin.TabularInline):
    model = AdaptationRule
    extra = 0
    readonly_fields = ['is_executed', 'executed_at', 'executed_by']


class LegalOpportunityInline(admin.TabularInline):
    model = LegalOpportunity
    extra = 0


@admin.register(RegulatoryUpdate)
class RegulatoryUpdateAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'publication_date', 'effective_date', 'impact_score', 'is_breaking', 'is_processed']
    list_filter = ['category', 'is_processed', 'is_breaking']
    search_fields = ['title', 'nn_number', 'raw_text']
    readonly_fields = ['id', 'created_at']
    inlines = [ImpactDomainInline, AdaptationRuleInline, LegalOpportunityInline]


@admin.register(LegalOpportunity)
class LegalOpportunityAdmin(admin.ModelAdmin):
    list_display = ['name', 'opportunity_type', 'typical_savings_eur', 'deadline', 'is_active']
    list_filter = ['opportunity_type', 'is_active']
    search_fields = ['name', 'description']


@admin.register(ClientOpportunityMatch)
class ClientOpportunityMatchAdmin(admin.ModelAdmin):
    list_display = ['company', 'opportunity', 'calculated_savings', 'status', 'matched_at']
    list_filter = ['status']
    search_fields = ['company__name', 'opportunity__name']
    readonly_fields = ['id', 'matched_at']


# ── BORG Signal Admin ──
from limit_connect_ai.models_signal import FenixSignal

@admin.register(FenixSignal)
class FenixSignalAdmin(admin.ModelAdmin):
    list_display = ["signal_type", "status", "priority", "message_short", "user", "company", "source", "created_at"]
    list_filter = ["signal_type", "status", "source", "priority"]
    search_fields = ["message", "page_url", "user__username"]
    readonly_fields = ["id", "created_at", "ip_address", "user_agent", "context"]
    date_hierarchy = "created_at"
    list_editable = ["status", "priority", "assigned_to"] if False else []

    def message_short(self, obj):
        return obj.message[:80]
    message_short.short_description = "Poruka"
