from django.contrib import admin
from .models import SentinelAlert, SentinelScan, TemporalLedgerScore, AuditChain
from .models_advisor import EUFund, EUMatch, ObrascTip, ObrascInstance, KalendarObveza
from .models_ured import DigitalniUred, UredKonverzacija


@admin.register(SentinelAlert)
class SentinelAlertAdmin(admin.ModelAdmin):
    list_display = ["title", "severity", "category", "company", "resolved", "created_at"]
    list_filter = ["severity", "category", "resolved"]
    search_fields = ["title", "message"]
    ordering = ["-created_at"]


@admin.register(SentinelScan)
class SentinelScanAdmin(admin.ModelAdmin):
    list_display = ["scan_type", "status", "alerts_created", "duration_ms", "created_at"]
    list_filter = ["scan_type", "status"]
    ordering = ["-created_at"]


@admin.register(TemporalLedgerScore)
class TemporalLedgerScoreAdmin(admin.ModelAdmin):
    list_display = ["company", "content_type", "object_id", "score", "flags", "reviewed"]
    list_filter = ["reviewed"]
    ordering = ["score"]


@admin.register(AuditChain)
class AuditChainAdmin(admin.ModelAdmin):
    list_display = ["company", "content_type", "object_id", "operation", "chain_valid", "created_at"]
    list_filter = ["operation", "chain_valid"]
    ordering = ["-created_at"]


@admin.register(EUFund)
class EUFundAdmin(admin.ModelAdmin):
    list_display = ["title_hr", "program", "status", "max_grant_eur", "deadline"]
    list_filter = ["status", "program"]
    search_fields = ["title", "title_hr"]


@admin.register(EUMatch)
class EUMatchAdmin(admin.ModelAdmin):
    list_display = ["company", "fund", "match_score", "potential_eur", "status"]
    list_filter = ["status"]
    ordering = ["-match_score"]


@admin.register(ObrascTip)
class ObrascTipAdmin(admin.ModelAdmin):
    list_display = ["kod", "naziv", "period", "rok_dana", "institucija"]


@admin.register(ObrascInstance)
class ObrascInstanceAdmin(admin.ModelAdmin):
    list_display = ["company", "tip", "period_od", "rok_podnosenja", "status", "izracunata_vrijednost"]
    list_filter = ["status", "tip"]
    ordering = ["rok_podnosenja"]


@admin.register(KalendarObveza)
class KalendarObvezaAdmin(admin.ModelAdmin):
    list_display = ["company", "naziv", "rok", "kategorija", "is_completed"]
    list_filter = ["kategorija", "is_completed"]
    ordering = ["rok"]


@admin.register(DigitalniUred)
class DigitalniUredAdmin(admin.ModelAdmin):
    list_display = ["company", "total_conversations", "last_active"]


@admin.register(UredKonverzacija)
class UredKonverzacijaAdmin(admin.ModelAdmin):
    list_display = ["ured", "user", "topic", "last_message_at", "is_resolved"]
    list_filter = ["topic", "is_resolved"]
    ordering = ["-last_message_at"]
