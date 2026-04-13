"""AS4 Message tracking — the backbone of PROPTER e-invoice transport.

Every invoice sent or received through ANY transport (FINA posrednik,
future phase4 AP, B2C portal) is tracked here with full audit trail.

Design principles:
- Transport-agnostic: same model whether FINA, phase4, or email
- Immutable audit trail: events are append-only, never updated
- Multi-tenant: always scoped to company
- Archive-ready: SHA-256 hash for legal compliance
"""

import hashlib
import uuid

from django.db import models
from django.utils import timezone


class MessageDirection(models.TextChoices):
    OUTBOUND = "OUT", "Izlazni (slanje)"
    INBOUND = "IN", "Ulazni (primanje)"


class TransportType(models.TextChoices):
    FINA_POSREDNIK = "FINA", "FINA Posrednik (Faza 1)"
    PHASE4_AP = "PH4", "phase4 Vlastiti AP (Faza 3)"
    B2C_PORTAL = "B2C", "B2C Portal (email + web viewer)"
    EMAIL_FALLBACK = "EMAIL", "Email fallback (PDF attachment)"
    MANUAL = "MANUAL", "Rucna obrada"


class MessageStatus(models.TextChoices):
    # Outbound states
    DRAFT = "DRAFT", "Nacrt"
    VALIDATED = "VALIDATED", "Validirano"
    QUEUED = "QUEUED", "U redu za slanje"
    SUBMITTED = "SUBMITTED", "Predano posredniku"
    SENT = "SENT", "Poslano"
    DELIVERED = "DELIVERED", "Dostavljeno"
    ACKNOWLEDGED = "ACK", "Potvrdeno (MDN)"
    # Inbound states
    RECEIVED = "RECEIVED", "Primljeno"
    PROCESSED = "PROCESSED", "Obradeno"
    BOOKED = "BOOKED", "Proknjizeno"
    # Error states
    VALIDATION_FAILED = "VAL_FAIL", "Validacija neuspjesna"
    SEND_FAILED = "SEND_FAIL", "Slanje neuspjesno"
    REJECTED = "REJECTED", "Odbijeno"
    RETRY = "RETRY", "Ponovni pokusaj"
    # Terminal
    CANCELLED = "CANCELLED", "Otkazano"
    ARCHIVED = "ARCHIVED", "Arhivirano"


class AS4Message(models.Model):
    """Core message tracking model.

    Every e-invoice that flows through PROPTER — in or out —
    gets an AS4Message record. Transport-agnostic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="as4_messages",
    )
    invoice = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="as4_messages",
    )

    direction = models.CharField(max_length=3, choices=MessageDirection.choices, db_index=True)
    transport = models.CharField(
        max_length=10,
        choices=TransportType.choices,
        default=TransportType.FINA_POSREDNIK,
    )

    # Peppol Addressing
    sender_participant_id = models.CharField(max_length=64)
    receiver_participant_id = models.CharField(max_length=64)
    sender_name = models.CharField(max_length=255, blank=True)
    receiver_name = models.CharField(max_length=255, blank=True)

    # Document Info
    document_type = models.CharField(
        max_length=20,
        default="INVOICE",
        choices=[
            ("INVOICE", "Racun"),
            ("CREDIT_NOTE", "Odobrenje"),
            ("DEBIT_NOTE", "Zaduzenje"),
        ],
    )
    invoice_number = models.CharField(max_length=100, blank=True)
    invoice_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    invoice_currency = models.CharField(max_length=3, default="EUR")

    # Status
    status = models.CharField(
        max_length=10,
        choices=MessageStatus.choices,
        default=MessageStatus.DRAFT,
        db_index=True,
    )

    # External References
    external_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    external_conversation_id = models.CharField(max_length=255, blank=True)

    # Payload
    ubl_xml = models.TextField(blank=True)
    ubl_xml_size = models.PositiveIntegerField(default=0)

    # Archive
    archive_s3_key = models.CharField(max_length=512, blank=True)
    archive_sha256 = models.CharField(max_length=64, blank=True, db_index=True)

    # Retry Logic
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Error Info
    error_code = models.CharField(max_length=50, blank=True)
    error_detail = models.TextField(blank=True)

    # Validation
    validation_passed = models.BooleanField(null=True)
    validation_errors = models.JSONField(default=list, blank=True)
    validation_warnings = models.JSONField(default=list, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="as4_messages_created",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "einvoice_as4_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "direction", "status"], name="idx_as4_company_dir_status"),
            models.Index(fields=["company", "direction", "-created_at"], name="idx_as4_company_dir_created"),
            models.Index(fields=["status", "next_retry_at"], name="idx_as4_retry_queue"),
            models.Index(fields=["external_message_id"], name="idx_as4_external_id"),
        ]
        verbose_name = "AS4 Poruka"
        verbose_name_plural = "AS4 Poruke"

    def __str__(self):
        arrow = "\u2192" if self.direction == "OUT" else "\u2190"
        return (
            f"{self.invoice_number or 'N/A'} "
            f"{arrow} {self.receiver_name or self.receiver_participant_id} "
            f"[{self.get_status_display()}]"
        )

    def compute_sha256(self):
        if not self.ubl_xml:
            return ""
        content = self.ubl_xml.encode("utf-8") if isinstance(self.ubl_xml, str) else self.ubl_xml
        return hashlib.sha256(content).hexdigest()

    def set_ubl_xml(self, xml_content):
        self.ubl_xml = xml_content
        self.ubl_xml_size = len(xml_content.encode("utf-8"))
        self.archive_sha256 = self.compute_sha256()

    def can_retry(self):
        return self.status in (MessageStatus.SEND_FAILED, MessageStatus.RETRY) and self.retry_count < self.max_retries

    def calculate_next_retry(self):
        intervals = [60, 300, 900, 3600, 14400]
        delay = intervals[min(self.retry_count, len(intervals) - 1)]
        return timezone.now() + timezone.timedelta(seconds=delay)

    def transition_to(self, new_status, detail="", user=None):
        old_status = self.status
        self.status = new_status

        now = timezone.now()
        timestamp_map = {
            MessageStatus.VALIDATED: "validated_at",
            MessageStatus.SUBMITTED: "submitted_at",
            MessageStatus.SENT: "sent_at",
            MessageStatus.DELIVERED: "delivered_at",
            MessageStatus.ACKNOWLEDGED: "acknowledged_at",
            MessageStatus.ARCHIVED: "archived_at",
        }
        ts_field = timestamp_map.get(new_status)
        if ts_field:
            setattr(self, ts_field, now)

        if new_status == MessageStatus.RETRY:
            self.retry_count += 1
            self.next_retry_at = self.calculate_next_retry()
        elif new_status == MessageStatus.SEND_FAILED:
            if self.can_retry():
                self.status = MessageStatus.RETRY
                self.retry_count += 1
                self.next_retry_at = self.calculate_next_retry()

        self.save()

        event = AS4MessageEvent.objects.create(
            message=self,
            from_status=old_status,
            to_status=self.status,
            detail=detail,
            created_by=user,
        )
        return event

    @property
    def sender_oib(self):
        if ":" in self.sender_participant_id:
            return self.sender_participant_id.split(":")[-1]
        return self.sender_participant_id

    @property
    def receiver_oib(self):
        if ":" in self.receiver_participant_id:
            return self.receiver_participant_id.split(":")[-1]
        return self.receiver_participant_id

    @property
    def is_terminal(self):
        return self.status in (
            MessageStatus.DELIVERED,
            MessageStatus.ACKNOWLEDGED,
            MessageStatus.BOOKED,
            MessageStatus.CANCELLED,
            MessageStatus.ARCHIVED,
            MessageStatus.REJECTED,
        )


class AS4MessageEvent(models.Model):
    """Immutable audit trail for AS4 message lifecycle. NEVER UPDATE OR DELETE."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(AS4Message, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=10, choices=MessageStatus.choices)
    to_status = models.CharField(max_length=10, choices=MessageStatus.choices)
    detail = models.TextField(blank=True)
    external_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "einvoice_as4_message_event"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["message", "created_at"], name="idx_as4_event_msg_time"),
        ]
        verbose_name = "AS4 Dogadaj"
        verbose_name_plural = "AS4 Dogadaji"

    def __str__(self):
        return f"{self.message.invoice_number}: {self.from_status} \u2192 {self.to_status}"
