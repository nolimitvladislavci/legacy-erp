from rest_framework import serializers

from einvoice.models import AS4Message, AS4MessageEvent, InboundInvoice


class AS4MessageSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    transport_display = serializers.CharField(source="get_transport_display", read_only=True)
    events_count = serializers.IntegerField(source="events.count", read_only=True)

    class Meta:
        model = AS4Message
        fields = [
            "id", "direction", "direction_display", "transport", "transport_display",
            "status", "status_display", "invoice_number",
            "sender_name", "sender_participant_id", "receiver_name", "receiver_participant_id",
            "invoice_amount", "invoice_currency", "document_type",
            "external_message_id", "validation_passed", "retry_count", "error_detail",
            "created_at", "submitted_at", "sent_at", "delivered_at",
            "archive_sha256", "events_count",
        ]
        read_only_fields = fields


class AS4MessageEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AS4MessageEvent
        fields = ["id", "from_status", "to_status", "detail", "created_at"]
        read_only_fields = fields


class InboundInvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    message_id = serializers.UUIDField(source="as4_message_id", read_only=True)

    class Meta:
        model = InboundInvoice
        fields = [
            "id", "status", "status_display",
            "invoice_number", "issue_date", "due_date", "currency",
            "supplier_name", "supplier_tax_id",
            "net_amount", "tax_amount", "gross_amount",
            "tax_breakdown", "line_items",
            "suggested_konto", "suggested_konto_name", "suggested_cost_center",
            "suggested_vat_treatment", "classification_confidence", "classification_reason",
            "final_konto", "final_cost_center",
            "is_duplicate", "received_at", "approved_at", "booked_at",
            "message_id",
        ]


class InboundApproveSerializer(serializers.Serializer):
    konto = serializers.CharField(max_length=20)
    cost_center = serializers.CharField(max_length=50, required=False, default="")
    notes = serializers.CharField(required=False, default="")
