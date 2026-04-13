"""tax_wizard/admin.py — Admin panel za Porezni Savjetnik."""

from django.contrib import admin
from django.utils.html import format_html

from tax_wizard.models import (
    OsobniOdbitakKoeficijent,
    PartnerTaxAccount,
    PausalTier,
    PotpomognutoPodručje,
    TaxAuditLog,
    TaxDeadline,
    TaxFormTemplate,
    TaxSimulation,
    TaxWizardSession,
)


@admin.register(TaxFormTemplate)
class TaxFormTemplateAdmin(admin.ModelAdmin):
    list_display = ["form_type", "version", "name", "is_active", "valid_from", "step_count"]
    list_filter = ["form_type", "is_active"]
    search_fields = ["name", "form_type"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            "Osnovni podaci",
            {
                "fields": ("form_type", "version", "name", "name_en", "is_active"),
            },
        ),
        (
            "JSON shema obrasca",
            {
                "fields": ("schema",),
                "description": (
                    "JSON koji definira korake wizarda, polja, validacije i AI hintove. "
                    "Promjene ovdje ODMAH mijenjaju što korisnik vidi na ekranu."
                ),
            },
        ),
        (
            "Primjenjivost",
            {
                "fields": (
                    "applicable_business_types",
                    "applicable_countries",
                    "valid_from",
                    "valid_until",
                    "supersedes",
                ),
            },
        ),
        (
            "Rokovi i XML",
            {
                "fields": ("filing_deadline_rule", "xml_template_name"),
            },
        ),
        (
            "AI pravni štit",
            {
                "fields": ("ai_system_prompt",),
                "description": 'System prompt za AI — NIKADA ne smije sadržavati "preporučujem" ili "savjetujem".',
            },
        ),
        (
            "Meta",
            {
                "fields": ("created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    ]


class TaxAuditLogInline(admin.TabularInline):
    model = TaxAuditLog
    extra = 0
    readonly_fields = ["action", "user", "details", "data_hash_before", "data_hash_after", "ip_address", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TaxWizardSession)
class TaxWizardSessionAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "template_form_type",
        "tax_year",
        "status_badge",
        "progress_percent",
        "referred_by",
        "updated_at",
    ]
    list_filter = ["status", "template__form_type", "tax_year"]
    search_fields = ["company__name", "company__oib", "user__username"]
    readonly_fields = [
        "id",
        "session_key",
        "data_hash",
        "created_at",
        "updated_at",
        "progress_percent",
    ]
    raw_id_fields = ["user", "company", "referred_by", "referral_company", "reviewer"]
    inlines = [TaxAuditLogInline]

    @admin.display(description="Obrazac")
    def template_form_type(self, obj):
        return obj.template.form_type

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "draft": "#6b7280",
            "review": "#f59e0b",
            "correction": "#ef4444",
            "final": "#3b82f6",
            "submitted": "#8b5cf6",
            "accepted": "#10b981",
            "rejected": "#dc2626",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:4px; font-size:11px;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(TaxDeadline)
class TaxDeadlineAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "template_type",
        "tax_year",
        "deadline_date",
        "days_remaining",
        "urgency_badge",
        "is_filed",
    ]
    list_filter = ["is_filed", "template__form_type", "tax_year", "priority"]
    search_fields = ["company__name"]
    raw_id_fields = ["company", "session"]

    @admin.display(description="Obrazac")
    def template_type(self, obj):
        return obj.template.form_type

    @admin.display(description="Hitnost")
    def urgency_badge(self, obj):
        colors = {
            "success": "#10b981",
            "normal": "#6b7280",
            "warning": "#f59e0b",
            "critical": "#ef4444",
            "overdue": "#dc2626",
        }
        level = obj.urgency_level
        color = colors.get(level, "#6b7280")
        labels = {
            "success": "Podneseno",
            "normal": "U redu",
            "warning": "Uskoro",
            "critical": "HITNO",
            "overdue": "PROPUŠTENO",
        }
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px; font-weight:bold;">{}</span>',
            color,
            labels.get(level, level),
        )


@admin.register(TaxSimulation)
class TaxSimulationAdmin(admin.ModelAdmin):
    list_display = ["company", "sim_type", "estimated_savings", "created_at"]
    list_filter = ["sim_type"]
    search_fields = ["company__name"]
    readonly_fields = ["created_at"]


@admin.register(PotpomognutoPodručje)
class PotpomognutoPodručjeAdmin(admin.ModelAdmin):
    list_display = ["name", "county", "group", "osobni_odbitak", "prirez_rate", "is_active"]
    list_filter = ["group", "county", "is_active"]
    search_fields = ["name", "county"]


@admin.register(PausalTier)
class PausalTierAdmin(admin.ModelAdmin):
    list_display = [
        "valid_year",
        "tier_number",
        "min_income",
        "max_income",
        "annual_tax",
        "monthly_tax",
        "monthly_contributions",
    ]
    list_filter = ["valid_year", "is_active"]


@admin.register(OsobniOdbitakKoeficijent)
class OsobniOdbitakKoeficijentAdmin(admin.ModelAdmin):
    list_display = ["valid_year", "category", "coefficient", "monthly_amount", "is_active"]
    list_filter = ["valid_year", "is_active"]
    readonly_fields = ["monthly_amount"]


@admin.register(TaxAuditLog)
class TaxAuditLogAdmin(admin.ModelAdmin):
    list_display = ["session", "action", "user", "created_at"]
    list_filter = ["action"]
    readonly_fields = [
        "id",
        "session",
        "user",
        "action",
        "details",
        "data_hash_before",
        "data_hash_after",
        "ip_address",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PartnerTaxAccount)
class PartnerTaxAccountAdmin(admin.ModelAdmin):
    list_display = [
        "brand_name",
        "company",
        "referral_code",
        "commission_rate",
        "total_referrals",
        "total_sessions",
        "total_earned",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["brand_name", "company__name", "referral_code"]
    readonly_fields = ["id", "total_referrals", "total_sessions", "total_earned", "created_at", "updated_at"]
    raw_id_fields = ["company", "user"]
