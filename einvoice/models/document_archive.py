"""Legal document archive with SHA-256 integrity verification.
Croatian law requires 11 years of invoice retention."""

import hashlib
import uuid

from django.db import models
from django.utils import timezone


class DocumentArchive(models.Model):
    """Immutable archive record for e-invoices. Once created, NEVER modified."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="document_archives",
    )
    as4_message = models.OneToOneField(
        "einvoice.AS4Message",
        on_delete=models.CASCADE,
        related_name="archive",
    )

    class DocumentType(models.TextChoices):
        OUTBOUND_INVOICE = "OUT_INV", "Izlazni racun"
        OUTBOUND_CREDIT = "OUT_CRD", "Izlazno odobrenje"
        INBOUND_INVOICE = "IN_INV", "Ulazni racun"
        INBOUND_CREDIT = "IN_CRD", "Ulazno odobrenje"
        DELIVERY_RECEIPT = "MDN", "Potvrda dostave"

    document_type = models.CharField(max_length=10, choices=DocumentType.choices)

    s3_bucket = models.CharField(max_length=100, default="propter-einvoice-archive")
    s3_key = models.CharField(max_length=512, unique=True)
    file_size_bytes = models.PositiveIntegerField()

    sha256_hash = models.CharField(max_length=64, unique=True, db_index=True)

    invoice_number = models.CharField(max_length=100, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    receiver_name = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")

    retention_until = models.DateField()
    is_legally_valid = models.BooleanField(default=True)
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "einvoice_document_archive"
        ordering = ["-archived_at"]
        indexes = [
            models.Index(fields=["sha256_hash"], name="idx_archive_hash"),
            models.Index(fields=["company", "-archived_at"], name="idx_archive_company_date"),
            models.Index(fields=["retention_until"], name="idx_archive_retention"),
        ]
        verbose_name = "Arhivirani Dokument"
        verbose_name_plural = "Arhivirani Dokumenti"

    def __str__(self):
        return f"{self.invoice_number} - {self.sha256_hash[:16]}... ({self.get_document_type_display()})"

    @staticmethod
    def compute_hash(content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def verify_integrity(self, content):
        computed = self.compute_hash(content)
        return computed == self.sha256_hash

    @classmethod
    def generate_s3_key(cls, company_id, message_id, now=None):
        now = now or timezone.now()
        return f"{company_id}/{now.year}/{now.month:02d}/{message_id}.xml"

    @classmethod
    def calculate_retention_date(cls, invoice_date=None):
        from datetime import date

        base = invoice_date or date.today()
        return date(base.year + 11, 12, 31)
