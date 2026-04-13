from django.contrib import admin

from .models import ERacun, ERacunConfig, ERacunItem, ERacunLog, ERacunTaxSummary


class ERacunItemInline(admin.TabularInline):
    model = ERacunItem
    extra = 0


class ERacunTaxSummaryInline(admin.TabularInline):
    model = ERacunTaxSummary
    extra = 0


class ERacunLogInline(admin.TabularInline):
    model = ERacunLog
    extra = 0
    readonly_fields = ("action", "status", "message", "created_at", "user")


@admin.register(ERacunConfig)
class ERacunConfigAdmin(admin.ModelAdmin):
    list_display = ("company", "is_active", "cert_oib", "use_test_env", "api_enabled")
    list_filter = ("is_active", "use_test_env", "api_enabled")


@admin.register(ERacun)
class ERacunAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "company", "recipient_name", "total", "status", "created_at")
    list_filter = ("status", "doc_type", "company")
    search_fields = ("invoice_number", "recipient_name", "recipient_oib", "issuer_oib")
    readonly_fields = ("id", "fina_uuid", "xml_request", "xml_response", "created_at", "sent_at", "accepted_at")
    inlines = [ERacunItemInline, ERacunTaxSummaryInline, ERacunLogInline]
    date_hierarchy = "created_at"


from .models import SukladnostTestRun


@admin.register(SukladnostTestRun)
class SukladnostTestRunAdmin(admin.ModelAdmin):
    list_display = ("company", "started_at", "total_pass", "total_fail", "run_by")
    list_filter = ("company",)
    readonly_fields = ("details",)
