"""Per-company transport configuration."""

import uuid

from django.db import models


class TransportConfiguration(models.Model):
    """Per-company transport settings for e-invoice delivery."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="transport_config",
    )

    class PrimaryTransport(models.TextChoices):
        FINA_POSREDNIK = "FINA", "FINA Posrednik API"
        PHASE4_AP = "PH4", "phase4 Vlastiti AP"
        DISABLED = "OFF", "e-Racun onemogucen"

    primary_transport = models.CharField(
        max_length=10,
        choices=PrimaryTransport.choices,
        default=PrimaryTransport.FINA_POSREDNIK,
    )
    b2c_enabled = models.BooleanField(default=True)
    email_fallback_enabled = models.BooleanField(default=True)
    auto_send_on_finalize = models.BooleanField(default=True)

    # FINA Posrednik
    fina_api_key = models.CharField(max_length=255, blank=True)
    fina_participant_id = models.CharField(max_length=64, blank=True)

    # Peppol Registration
    peppol_scheme = models.CharField(max_length=20, default="9934")
    peppol_identifier = models.CharField(max_length=64, blank=True)
    peppol_registered = models.BooleanField(default=False)

    # CIUS Profile
    default_cius_profile = models.CharField(
        max_length=10,
        default="HR",
        choices=[("HR", "CIUS-HR"), ("DE", "CIUS-DE / XRechnung"), ("EU", "EN 16931")],
    )

    # Smart Mailbox
    smart_mailbox_enabled = models.BooleanField(default=True)
    auto_book_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Notifications
    notify_on_delivery = models.BooleanField(default=True)
    notify_on_failure = models.BooleanField(default=True)
    notify_on_incoming = models.BooleanField(default=True)
    notification_email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "einvoice_transport_config"
        verbose_name = "Transport Konfiguracija"
        verbose_name_plural = "Transport Konfiguracije"

    def __str__(self):
        return f"{self.company} - {self.get_primary_transport_display()}"
