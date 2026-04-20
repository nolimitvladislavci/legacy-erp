"""
synesis/models.py — Konfiguracija i log Synesis sinkronizacije.
Port iz fina-connect/synesis/models.py, adaptirano za Fenix V3 TenantModel.

KRITIČNO: Svaki klijent = zasebna Company instanca!
KONJIK BUG: nikad ne miješaj MDB fajlove raznih klijenata pod jednom Company.
"""

import secrets
import string

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def _generate_token(length=40):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SynesisConfig(models.Model):
    """Konfiguracija Synesis integracije za jednu Company (OneToOne)."""

    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="synesis_config",
        verbose_name=_("Tvrtka"),
    )
    api_token = models.CharField(
        max_length=80,
        default=_generate_token,
        unique=True,
        verbose_name=_("API token"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Aktivno"))

    # Putanje na Windows računalu klijenta
    storage_db_path = models.CharField(max_length=500, blank=True, verbose_name="Storage.mdb putanja")
    journal_db_path = models.CharField(max_length=500, blank=True, verbose_name="Journal.mdb putanja")
    pos_db_path = models.CharField(max_length=500, blank=True, verbose_name="POS baza putanja")
    pos_db_password = models.CharField(max_length=100, blank=True, verbose_name="POS baza lozinka")
    connect_base_path = models.CharField(
        max_length=500, blank=True, default=r"C:\SynesisConnect", verbose_name="Connect bazni folder"
    )
    backup_retention_days = models.IntegerField(default=30, verbose_name="Čuvanje backupa (dana)")
    auto_backup_enabled = models.BooleanField(default=True, verbose_name="Automatski backup")

    # Statistika zadnje sinkronizacije
    last_sync_partners = models.DateTimeField(null=True, blank=True)
    last_sync_items = models.DateTimeField(null=True, blank=True)
    last_sync_pos = models.DateTimeField(null=True, blank=True)
    last_backup_at = models.DateTimeField(null=True, blank=True)

    partners_total = models.IntegerField(default=0, verbose_name="Partneri uvezeni")
    items_total = models.IntegerField(default=0, verbose_name="Artikli uvezeni")
    pos_receipts_total = models.IntegerField(default=0, verbose_name="POS bona")
    pos_name = models.CharField(max_length=100, blank=True, verbose_name="Naziv kase")

    # POS prihodi (kumulativno)
    pos_revenue_today = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pos_revenue_week = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pos_revenue_month = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Synesis konfiguracija"
        verbose_name_plural = "Synesis konfiguracije"

    def __str__(self):
        return f"SynesisConfig — {self.company.name}"

    def regenerate_token(self):
        self.api_token = _generate_token()
        self.save(update_fields=["api_token", "updated_at"])


class SynesisLog(models.Model):
    """Zapis svake sinkronizacije (audit trail)."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="synesis_logs",
    )
    sync_type = models.CharField(max_length=30)
    records_received = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    error_detail = models.TextField(blank=True)
    duration_seconds = models.FloatField(default=0)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Synesis log"
        verbose_name_plural = "Synesis logovi"
        ordering = ["-synced_at"]

    def __str__(self):
        return f"{self.company.name} / {self.sync_type} / {self.synced_at:%d.%m.%Y %H:%M}"


class SynesisExportQueue(models.Model):
    """Red za izvoz promjena iz ERP-a natrag u Synesis MDB."""

    EXPORT_TYPES = [
        ("item", "Artikl"),
        ("partner", "Partner"),
        ("calculation", "Kalkulacija"),
        ("pkv", "PKV"),
    ]
    ACTIONS = [("update", "Ažuriranje"), ("insert", "Dodavanje")]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="synesis_export_queue",
    )
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    action = models.CharField(max_length=10, choices=ACTIONS, default="update")
    synesis_id = models.CharField(max_length=50, blank=True)
    erp_object_id = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)

    is_exported = models.BooleanField(default=False)
    exported_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Synesis export queue"
        verbose_name_plural = "Synesis export queue"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.export_type} #{self.synesis_id or self.erp_object_id}"


class SynesisYearConfig(models.Model):
    """Godišnja konfiguracija Synesis integracije (putanja MDB po godini)."""

    config = models.ForeignKey(
        SynesisConfig,
        on_delete=models.CASCADE,
        related_name="year_configs",
    )
    year = models.IntegerField(verbose_name="Godina")
    storage_db_path = models.CharField(max_length=500, blank=True)
    journal_db_path = models.CharField(max_length=500, blank=True)
    last_sync_invoices = models.DateTimeField(null=True, blank=True)
    invoices_total = models.IntegerField(default=0)

    class Meta:
        unique_together = ("config", "year")
        ordering = ["-year"]

    def __str__(self):
        return f"{self.config.company.name} / {self.year}"
