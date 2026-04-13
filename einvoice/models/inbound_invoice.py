"""Smart Mailbox — inbound invoice processing."""
import uuid

from django.db import models


class InboundInvoice(models.Model):
    """Received e-invoice waiting for processing in Smart Mailbox."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="inbound_invoices",
    )
    as4_message = models.OneToOneField(
        "einvoice.AS4Message", on_delete=models.CASCADE,
        related_name="inbound_invoice",
    )
    journal_entry = models.ForeignKey(
        "konto.JournalEntry", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="source_inbound_invoices",
    )

    class ProcessingStatus(models.TextChoices):
        PENDING = "PENDING", "Ceka pregled"
        AUTO_CLASSIFIED = "AUTO", "Automatski klasificirano"
        APPROVED = "APPROVED", "Odobreno"
        BOOKED = "BOOKED", "Proknjizeno"
        REJECTED = "REJECTED", "Odbijeno"
        DUPLICATE = "DUPLICATE", "Duplikat"

    status = models.CharField(
        max_length=10, choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING, db_index=True,
    )

    # Parsed Invoice Data
    invoice_number = models.CharField(max_length=100)
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")

    supplier_name = models.CharField(max_length=255)
    supplier_tax_id = models.CharField(max_length=20, blank=True)
    supplier_address = models.TextField(blank=True)

    net_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2)

    tax_breakdown = models.JSONField(default=list)
    line_items = models.JSONField(default=list)

    # Auto-Classification
    suggested_konto = models.CharField(max_length=20, blank=True)
    suggested_konto_name = models.CharField(max_length=255, blank=True)
    suggested_cost_center = models.CharField(max_length=50, blank=True)
    suggested_vat_treatment = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("FULL_DEDUCTION", "Puni odbitak pretporeza"),
            ("PARTIAL_DEDUCTION", "Djelomicni odbitak"),
            ("NO_DEDUCTION", "Bez odbitka"),
            ("REVERSE_CHARGE", "Prijenos porezne obveze"),
            ("EXEMPT", "Oslobodeno"),
        ],
    )
    classification_confidence = models.FloatField(default=0.0)
    classification_reason = models.TextField(blank=True)

    # User Decisions
    final_konto = models.CharField(max_length=20, blank=True)
    final_cost_center = models.CharField(max_length=50, blank=True)
    approved_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="approved_inbound_invoices",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Duplicate Detection
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="duplicates",
    )

    notes = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    booked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "einvoice_inbound_invoice"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["company", "status", "-received_at"], name="idx_inbound_company_status"),
            models.Index(fields=["supplier_tax_id"], name="idx_inbound_supplier_oib"),
            models.Index(fields=["company", "supplier_tax_id", "invoice_number"], name="idx_inbound_dup_check"),
        ]
        verbose_name = "Ulazni Racun"
        verbose_name_plural = "Ulazni Racuni"

    def __str__(self):
        return f"URA {self.invoice_number} - {self.supplier_name} ({self.gross_amount} {self.currency})"

    def check_duplicate(self):
        existing = InboundInvoice.objects.filter(
            company=self.company,
            supplier_tax_id=self.supplier_tax_id,
            invoice_number=self.invoice_number,
        ).exclude(pk=self.pk).exclude(
            status=self.ProcessingStatus.REJECTED,
        ).first()

        if existing:
            self.is_duplicate = True
            self.duplicate_of = existing
            self.status = self.ProcessingStatus.DUPLICATE
            self.save(update_fields=["is_duplicate", "duplicate_of", "status"])
            return True
        return False
