from django.contrib import admin

from .models import BankAccount, BankTransaction, JournalEntry, KontoAccount, LedgerLine, TaxLineDetail, TaxPeriod


class LedgerLineInline(admin.TabularInline):
    model = LedgerLine
    extra = 2
    fields = ("account", "side", "amount", "description")


@admin.register(KontoAccount)
class KontoAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "company", "is_active")
    list_filter = ("account_type", "company", "is_active")
    search_fields = ("code", "name")
    ordering = ("company", "code")


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "iban", "bank_name", "currency", "current_balance", "is_primary", "company")
    list_filter = ("company", "is_active", "is_primary")
    search_fields = ("name", "iban")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "transaction_type",
        "amount",
        "counterparty_name",
        "status",
        "is_booked",
        "bank_account",
    )
    list_filter = ("status", "transaction_type", "is_booked", "company")
    search_fields = ("counterparty_name", "description", "reference_number")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_number", "date", "description", "source_type", "is_posted", "company")
    list_filter = ("source_type", "is_posted", "company")
    search_fields = ("entry_number", "description")
    inlines = [LedgerLineInline]


class TaxLineDetailInline(admin.TabularInline):
    model = TaxLineDetail
    extra = 0
    fields = ("tax_rate", "revenue_base", "output_vat")
    readonly_fields = ("tax_rate", "revenue_base", "output_vat")


@admin.register(TaxPeriod)
class TaxPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "period_type",
        "year",
        "month",
        "total_output_vat",
        "total_input_vat",
        "vat_payable",
        "is_filed",
        "filing_deadline",
    )
    list_filter = ("period_type", "is_filed", "company", "year")
    search_fields = ("company__name",)
    ordering = ("-year", "-month")
    inlines = [TaxLineDetailInline]
    list_editable = ("is_filed",)
