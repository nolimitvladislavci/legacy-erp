from django.contrib import admin
from .models import KontoAccount, BankAccount, BankTransaction, JournalEntry, LedgerLine


class LedgerLineInline(admin.TabularInline):
    model = LedgerLine
    extra = 2
    fields = ('account', 'side', 'amount', 'description')


@admin.register(KontoAccount)
class KontoAccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'company', 'is_active')
    list_filter = ('account_type', 'company', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('company', 'code')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'iban', 'bank_name', 'currency', 'current_balance', 'is_primary', 'company')
    list_filter = ('company', 'is_active', 'is_primary')
    search_fields = ('name', 'iban')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'transaction_type', 'amount', 'counterparty_name',
                    'status', 'is_booked', 'bank_account')
    list_filter = ('status', 'transaction_type', 'is_booked', 'company')
    search_fields = ('counterparty_name', 'description', 'reference_number')
    date_hierarchy = 'transaction_date'
    raw_id_fields = ('matched_invoice',)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'date', 'description', 'source_type', 'is_posted', 'company')
    list_filter = ('source_type', 'is_posted', 'company')
    search_fields = ('entry_number', 'description')
    date_hierarchy = 'date'
    inlines = [LedgerLineInline]
    raw_id_fields = ('source_invoice', 'source_transaction')
