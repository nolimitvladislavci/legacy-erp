from django.contrib import admin
from einvoice.models import (
    AS4Message, AS4MessageEvent, PeppolParticipant,
    TransportConfiguration, InboundInvoice, DocumentArchive,
    Mandate,
)


class AS4MessageEventInline(admin.TabularInline):
    model = AS4MessageEvent
    extra = 0
    readonly_fields = ["from_status", "to_status", "detail", "created_at"]
    ordering = ["-created_at"]


@admin.register(AS4Message)
class AS4MessageAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "direction", "transport", "status", "sender_name", "receiver_name", "invoice_amount", "created_at"]
    list_filter = ["direction", "transport", "status", "company"]
    search_fields = ["invoice_number", "sender_name", "receiver_name", "external_message_id", "archive_sha256"]
    readonly_fields = ["id", "archive_sha256", "ubl_xml_size", "created_at", "validated_at", "submitted_at", "sent_at", "delivered_at"]
    inlines = [AS4MessageEventInline]
    date_hierarchy = "created_at"


@admin.register(PeppolParticipant)
class PeppolParticipantAdmin(admin.ModelAdmin):
    list_display = ["name", "scheme", "participant_id", "country", "is_active", "source"]
    list_filter = ["country", "is_active", "source"]
    search_fields = ["name", "participant_id"]


@admin.register(TransportConfiguration)
class TransportConfigAdmin(admin.ModelAdmin):
    list_display = ["company", "primary_transport", "b2c_enabled", "auto_send_on_finalize", "peppol_registered"]
    list_filter = ["primary_transport", "peppol_registered"]


@admin.register(InboundInvoice)
class InboundInvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "supplier_name", "gross_amount", "currency", "status", "suggested_konto", "classification_confidence", "received_at"]
    list_filter = ["status", "company"]
    search_fields = ["invoice_number", "supplier_name", "supplier_tax_id"]
    date_hierarchy = "received_at"


@admin.register(DocumentArchive)
class DocumentArchiveAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "document_type", "sha256_hash", "file_size_bytes", "archived_at", "retention_until"]
    list_filter = ["document_type", "company"]
    search_fields = ["sha256_hash", "invoice_number"]
    readonly_fields = ["sha256_hash", "archived_at", "s3_key"]
    date_hierarchy = "archived_at"


@admin.register(Mandate)
class MandateAdmin(admin.ModelAdmin):
    list_display = ["principal_oib", "agent_oib", "mandate_type", "status", "is_active", "valid_from", "valid_until", "registered_with_fina"]
    list_filter = ["status", "mandate_type", "registered_with_fina", "is_active"]
    search_fields = ["principal_oib", "agent_oib", "fina_mandate_id", "notes"]
    readonly_fields = ["id", "created_at", "updated_at", "fina_registered_at"]
    fieldsets = (
        ('Stranke', {'fields': ('principal_company', 'principal_oib', 'agent_company', 'agent_oib')}),
        ('Punomoć', {'fields': ('mandate_type', 'status', 'is_active', 'valid_from', 'valid_until')}),
        ('FINA registracija', {'fields': ('fina_mandate_id', 'registered_with_fina', 'fina_registered_at')}),
        ('Dokument', {'fields': ('mandate_document', 'notes')}),
        ('Audit', {'fields': ('id', 'created_by', 'created_at', 'updated_at')}),
    )
