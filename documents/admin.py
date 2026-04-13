from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'doc_type', 'partner', 'total_amount', 'is_paid', 'date_issued')
    list_filter = ('is_paid', 'doc_type', 'company', 'date_issued')
    search_fields = ('doc_number', 'partner__name')
    readonly_fields = ('is_paid',) # Finance modul upravlja ovim statusom

from .models import CMR, CMRItem, OtkupniBlok, OtkupniBlokItem, Otpremnica, OtpremnicaItem


class OtpremnicaItemInline(admin.TabularInline):
    model = OtpremnicaItem
    extra = 1

@admin.register(Otpremnica)
class OtpremnicaAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'partner', 'status', 'date_issued', 'driver_name')
    list_filter = ('status', 'company')
    inlines = [OtpremnicaItemInline]

class OtkupniBlokItemInline(admin.TabularInline):
    model = OtkupniBlokItem
    extra = 1

@admin.register(OtkupniBlok)
class OtkupniBlokAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'farmer_name', 'status', 'date_issued', 'payment_method')
    list_filter = ('status', 'company', 'payment_method')
    inlines = [OtkupniBlokItemInline]

class CMRItemInline(admin.TabularInline):
    model = CMRItem
    extra = 1

@admin.register(CMR)
class CMRAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'sender_name', 'receiver_name', 'status', 'date_issued')
    list_filter = ('status', 'company')
    inlines = [CMRItemInline]

from .models import ArhivaEntry


@admin.register(ArhivaEntry)
class ArhivaEntryAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'source_type', 'partner_name', 'amount', 'doc_date', 'archived_at')
    list_filter = ('source_type', 'company', 'doc_date')
    search_fields = ('doc_number', 'partner_name', 'zki', 'jir')
    readonly_fields = ('archived_at',)
    date_hierarchy = 'doc_date'


from .models import ArhivaAuditLog


@admin.register(ArhivaAuditLog)
class ArhivaAuditLogAdmin(admin.ModelAdmin):
    """Read-only admin for append-only audit log."""
    list_display = ('timestamp', 'action', 'entry_archive_number', 'user', 'ip_address', 'company')
    list_filter = ('action', 'company', 'timestamp')
    search_fields = ('entry_archive_number', 'user__username', 'ip_address')
    readonly_fields = (
        'entry', 'entry_archive_number', 'company', 'action',
        'user', 'ip_address', 'user_agent', 'changes', 'timestamp',
    )
    date_hierarchy = 'timestamp'
    list_per_page = 50
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
