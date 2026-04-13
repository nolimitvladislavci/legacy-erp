"""Peppol Participant Directory — local cache.
Maps tax IDs (OIB) to Peppol routing information."""

import uuid

from django.db import models
from django.utils import timezone


class PeppolParticipant(models.Model):
    """Known Peppol participants — our local routing table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    scheme = models.CharField(max_length=20, default="9934")
    participant_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=2, default="HR")

    access_point_id = models.CharField(max_length=255, blank=True)
    endpoint_url = models.URLField(blank=True)

    supports_invoice = models.BooleanField(default=True)
    supports_credit_note = models.BooleanField(default=True)
    supported_cius = models.CharField(max_length=50, default="HR")

    is_active = models.BooleanField(default=True)

    class DataSource(models.TextChoices):
        MANUAL = "MANUAL", "Rucno uneseno"
        FINA_DIRECTORY = "FINA", "FINA direktorij"
        SMP_LOOKUP = "SMP", "SMP/SML automatski"
        PEPPOL_DIRECTORY = "PDIR", "Peppol Directory"

    source = models.CharField(max_length=10, choices=DataSource.choices, default=DataSource.MANUAL)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "einvoice_peppol_participant"
        unique_together = [("scheme", "participant_id")]
        indexes = [
            models.Index(fields=["scheme", "participant_id"], name="idx_peppol_scheme_id"),
            models.Index(fields=["country", "is_active"], name="idx_peppol_country_active"),
        ]
        verbose_name = "Peppol Sudionik"
        verbose_name_plural = "Peppol Sudionici"

    def __str__(self):
        return f"{self.name or 'N/A'} ({self.scheme}:{self.participant_id})"

    @property
    def full_participant_id(self):
        return f"{self.scheme}:{self.participant_id}"

    @property
    def is_on_peppol(self):
        return bool(self.access_point_id and self.is_active)

    def needs_verification(self, max_age_hours=24):
        if not self.last_verified_at:
            return True
        age = timezone.now() - self.last_verified_at
        return age.total_seconds() > max_age_hours * 3600
