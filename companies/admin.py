from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Company, CompanyPartnership, NKDCode, TaxRate

try:
    from boxgram.models import PetProfile

    class PetProfileInline(admin.TabularInline):
        fk_name = "company"
        model = PetProfile
        extra = 0
        fields = ["name", "owner", "species", "is_public", "is_memorial"]

    HAS_BOXGRAM = True
except ImportError:
    HAS_BOXGRAM = False


@admin.register(NKDCode)
class NKDCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "level", "section", "name_hr", "parent", "is_active")
    list_filter = ("level", "section", "is_active")
    search_fields = ("code", "name_hr", "name_en")
    list_per_page = 50
    ordering = ("code",)
    raw_id_fields = ("parent",)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    inlines = [PetProfileInline] if HAS_BOXGRAM else []
    list_display = (
        "name",
        "oib",
        "country",
        "business_type",
        "pdv_status",
        "nkd_code",
        "currency",
        "fiscal_system",
        "is_vat_registered",
        "is_platform_owner",
        "grosmarkt_partner",
        "city",
        "created_at",
    )
    search_fields = ("name", "oib", "tax_number", "vat_id")
    list_filter = (
        "country",
        "business_type",
        "pdv_status",
        "currency",
        "fiscal_system",
        "is_vat_registered",
        "is_platform_owner",
        "grosmarkt_partner",
    )
    list_editable = ("pdv_status",)
    autocomplete_fields = ("nkd_code",)
    fieldsets = (
        (
            _("Osnovni podaci"),
            {
                "fields": ("name", "oib", "address", "city", "zip_code", "iban", "logo"),
            },
        ),
        (
            _("Klasifikacija djelatnosti"),
            {
                "fields": ("nkd_code",),
            },
        ),
        (
            _("Međunarodne postavke"),
            {
                "fields": ("country", "business_type", "tax_number", "vat_id", "currency", "fiscal_system"),
            },
        ),
        (
            _("PDV i konfiguracija"),
            {
                "fields": ("pdv_status", "is_vat_registered"),
            },
        ),
        (
            _("Grosmarkt Partner"),
            {
                "fields": ("grosmarkt_partner", "grosmarkt_role", "grosmarkt_description", "grosmarkt_show_name"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ("country", "name", "rate", "is_default", "is_active", "description")
    list_filter = ("country", "is_active", "is_default")
    list_editable = ("is_default", "is_active")
    ordering = ("country", "-rate")


from .models import BusinessProfile, ServiceTemplate


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("company", "profile_type", "workflow_type", "module_list")
    list_filter = ("profile_type", "workflow_type")
    search_fields = ("company__name",)
    fieldsets = (
        (
            _("Tvrtka i profil"),
            {
                "fields": ("company", "profile_type", "workflow_type"),
            },
        ),
        (
            _("Aktivni moduli"),
            {
                "fields": (
                    "module_invoicing",
                    "module_pos",
                    "module_inventory",
                    "module_appointments",
                    "module_projects",
                    "module_worktime",
                    "module_finance",
                    "module_partners",
                    "module_documents",
                    "module_webshop",
                    "module_rental",
                    "module_fitness",
                ),
                "classes": ("wide",),
            },
        ),
        (
            _("Nazivi dokumenata"),
            {
                "fields": ("offer_label", "invoice_label", "workorder_label"),
            },
        ),
        (
            _("Prilagođena polja"),
            {
                "fields": ("custom_invoice_fields",),
                "classes": ("collapse",),
            },
        ),
    )

    def module_list(self, obj):
        from django.utils.html import format_html

        mods = obj.enabled_modules
        badges = "".join(
            f'<span style="background:#e0f2fe;color:#0369a1;padding:1px 6px;'
            f'border-radius:3px;font-size:11px;margin:1px">{m}</span>'
            for m in mods
        )
        return format_html(badges or '<span style="color:#94a3b8">–</span>')

    module_list.short_description = _("Aktivni moduli")


@admin.register(CompanyPartnership)
class CompanyPartnershipAdmin(admin.ModelAdmin):
    list_display = [
        "partner_company",
        "managed_company",
        "billing_type",
        "monthly_fee",
        "access_level",
        "valid_from",
        "valid_until",
        "is_active_display",
    ]
    list_filter = ["billing_type", "access_level", "partner_company"]
    search_fields = ["partner_company__name", "managed_company__name"]
    readonly_fields = ["created_at", "created_by"]
    list_select_related = ["partner_company", "managed_company"]

    def is_active_display(self, obj):
        return obj.is_active

    is_active_display.boolean = True
    is_active_display.short_description = "Aktivan"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ServiceTemplate)
class ServiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("profile_type", "category", "name", "unit", "default_price", "tax_rate", "is_active")
    list_filter = ("profile_type", "category", "is_active")
    list_editable = ("default_price", "is_active")
    search_fields = ("name", "description")
    ordering = ("profile_type", "sort_order", "name")


from .models import WhiteLabelConfig


@admin.register(WhiteLabelConfig)
class WhiteLabelConfigAdmin(admin.ModelAdmin):
    list_display = ("brand_name", "subdomain", "fiscal_system", "is_active", "created_at")
    list_filter = ("fiscal_system", "is_active")


from .models import LicenseToken


@admin.register(LicenseToken)
class LicenseTokenAdmin(admin.ModelAdmin):
    list_display = ("white_label", "status", "valid_until", "monthly_amount_eur", "last_heartbeat")
    list_filter = ("status",)
    raw_id_fields = ("white_label",)


# ═══════════════════════════════════════════════════════════════════════════
#  COMPANY MODULE CONFIG — admin inline za superadmina
# ═══════════════════════════════════════════════════════════════════════════

from django import forms as django_forms
from .models import CompanyModuleConfig
from .module_registry import MODULES


class ModuleCheckboxWidget(django_forms.CheckboxSelectMultiple):
    """Renders module checkboxes grouped by category."""

    pass


class CompanyModuleConfigForm(django_forms.ModelForm):
    """
    Custom form that renders enabled_modules as checkboxes (not raw JSON textarea).
    Each module is shown with its name, icon, category, and tier.
    """

    MODULE_CHOICES = [
        (m["id"], f"[{m.get('category', '').upper()}] {m['name']} — {m.get('description', '')[:60]}") for m in MODULES
    ]

    enabled_modules = django_forms.MultipleChoiceField(
        choices=MODULE_CHOICES,
        widget=ModuleCheckboxWidget,
        required=False,
        label="Aktivni moduli",
        help_text="Odaberite module koji su vidljivi ovoj firmi.",
    )

    class Meta:
        model = CompanyModuleConfig
        fields = ["enabled_modules", "notification_mode"]

    def clean_enabled_modules(self):
        """Convert list back to list (MultipleChoiceField returns list of strings)."""
        return self.cleaned_data.get("enabled_modules", [])


class CompanyModuleConfigInline(admin.StackedInline):
    model = CompanyModuleConfig
    form = CompanyModuleConfigForm
    can_delete = False
    verbose_name_plural = "Konfiguracija modula (Cluster)"
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request)


# Patch existing CompanyAdmin to include the inline
# We must re-register since @admin.register already registered it above
admin.site.unregister(Company)


@admin.register(Company)
class CompanyAdminWithModules(admin.ModelAdmin):
    inlines_list = [CompanyModuleConfigInline]
    if HAS_BOXGRAM:
        inlines_list = [PetProfileInline] + inlines_list

    inlines = inlines_list

    list_display = (
        "name",
        "oib",
        "country",
        "business_type",
        "pdv_status",
        "nkd_code",
        "currency",
        "fiscal_system",
        "is_vat_registered",
        "is_platform_owner",
        "grosmarkt_partner",
        "city",
        "created_at",
        "active_module_count",
    )
    search_fields = ("name", "oib", "tax_number", "vat_id")
    list_filter = (
        "country",
        "business_type",
        "pdv_status",
        "currency",
        "fiscal_system",
        "is_vat_registered",
        "is_platform_owner",
        "grosmarkt_partner",
    )
    list_editable = ("pdv_status",)
    autocomplete_fields = ("nkd_code",)
    fieldsets = (
        (
            _("Osnovni podaci"),
            {
                "fields": ("name", "oib", "address", "city", "zip_code", "iban", "logo"),
            },
        ),
        (
            _("Klasifikacija djelatnosti"),
            {
                "fields": ("nkd_code",),
            },
        ),
        (
            _("Međunarodne postavke"),
            {
                "fields": ("country", "business_type", "tax_number", "vat_id", "currency", "fiscal_system"),
            },
        ),
        (
            _("PDV i konfiguracija"),
            {
                "fields": ("pdv_status", "is_vat_registered"),
            },
        ),
        (
            _("Grosmarkt Partner"),
            {
                "fields": ("grosmarkt_partner", "grosmarkt_role", "grosmarkt_description", "grosmarkt_show_name"),
                "classes": ("collapse",),
            },
        ),
    )

    def active_module_count(self, obj):
        try:
            return f"{len(obj.module_config.enabled_modules)} modula"
        except Exception:
            return "—"

    active_module_count.short_description = "Aktivni moduli"
