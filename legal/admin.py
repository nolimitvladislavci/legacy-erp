"""Legal Admin — Fenix V3"""

from django.contrib import admin

from .models import Contract, ContractTemplate, Dispute, DisputeEvent, PowerOfAttorney


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "doc_type", "language", "is_active", "company"]
    list_filter = ["doc_type", "language", "is_active"]
    search_fields = ["name"]


class DisputeEventInline(admin.TabularInline):
    model = DisputeEvent
    extra = 0
    readonly_fields = ["created_at", "created_by"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["title", "doc_type", "status", "party_a_name", "party_b_name", "valid_until", "company"]
    list_filter = ["status", "doc_type"]
    search_fields = ["title", "party_a_name", "party_b_name"]
    readonly_fields = ["sha256_hash", "signed_at", "created_at"]


@admin.register(PowerOfAttorney)
class PowerOfAttorneyAdmin(admin.ModelAdmin):
    list_display = ["title", "poa_type", "principal_name", "agent_name", "valid_until", "is_revoked", "company"]
    list_filter = ["poa_type", "is_revoked"]
    search_fields = ["title", "agent_name", "principal_name"]


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "dispute_type",
        "status",
        "priority",
        "opponent_name",
        "deadline",
        "ai_risk_score",
        "company",
    ]
    list_filter = ["status", "priority", "dispute_type"]
    search_fields = ["title", "opponent_name"]
    inlines = [DisputeEventInline]
    readonly_fields = ["ai_risk_score", "ai_recommendation"]
