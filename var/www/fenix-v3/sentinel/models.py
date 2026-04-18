"""
FENIX SENTINEL — Core Models (PLAN_072–075)
SentinelAlert, SentinelScan, TemporalLedgerScore, AuditChain
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from core.base_model import TenantModel


class SentinelAlert(TenantModel):
    SEVERITY = [
        ("critical", "Kritično"),
        ("warning", "Upozorenje"),
        ("info", "Info"),
        ("success", "Uspjeh"),
    ]
    CATEGORY = [
        ("pos", "POS"),
        ("fiscal", "Fiskalizacija"),
        ("hr", "HR"),
        ("accounting", "Računovodstvo"),
        ("compliance", "Usklađenost"),
        ("security", "Sigurnost"),
        ("eu", "EU Fondovi"),
        ("pdv", "PDV"),
        ("ured", "Digitalni Ured"),
    ]

    alert_type = models.CharField(max_length=50, default="general", db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY, default="info", db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY, default="compliance")
    title = models.CharField(max_length=200)
    message = models.TextField()
    detail = models.TextField(blank=True)
    data = models.JSONField(default=dict)

    # Povezani entitet
    entity_type = models.CharField(max_length=50, blank=True)
    entity_id = models.CharField(max_length=50, blank=True)

    # Rješavanje
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="resolved_alerts"
    )
    is_read = models.BooleanField(default=False)

    # AI prijedlog
    ai_suggestion = models.TextField(blank=True)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_alert"
        verbose_name = "Sentinel Alert"
        verbose_name_plural = "Sentinel Alerts"
        indexes = [
            models.Index(fields=["company", "severity", "resolved"]),
            models.Index(fields=["company", "alert_type"]),
            models.Index(fields=["company", "is_read"]),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"

    def resolve(self, user=None):
        from django.utils import timezone

        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save(update_fields=["resolved", "resolved_at", "resolved_by", "updated_at"])


class SentinelScan(TenantModel):
    """Log svakog Celery Beat scana"""

    STATUS = [("running", "U tijeku"), ("completed", "Završen"), ("error", "Greška")]

    scan_type = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS, default="running")
    duration_ms = models.IntegerField(default=0)
    alerts_created = models.IntegerField(default=0)
    alerts_fired = models.IntegerField(default=0)
    alerts_resolved = models.IntegerField(default=0)
    companies_scanned = models.IntegerField(default=0)
    error = models.TextField(blank=True)
    meta = models.JSONField(default=dict)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_scan"
        verbose_name = "Sentinel Scan"
        ordering = ["-created_at"]


class TemporalLedgerScore(TenantModel):
    """Confidence score po transakciji — Temporal Ledger AI"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    score = models.IntegerField(default=100)  # 0-100
    flags = models.JSONField(default=list)  # ['unusual_hour', 'amount_outlier', ...]
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_scores"
    )

    class Meta(TenantModel.Meta):
        db_table = "sentinel_temporal_score"
        verbose_name = "Temporal Ledger Score"
        unique_together = ["content_type", "object_id"]
        indexes = [
            models.Index(fields=["company", "score"]),
        ]

    def __str__(self):
        return f"{self.content_type} #{self.object_id} → {self.score}/100"


class AuditChain(TenantModel):
    """Living Audit Trail — kriptografski SHA-256 lanac"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    operation = models.CharField(max_length=10)  # create/update/delete
    data_hash = models.CharField(max_length=64)  # SHA-256 podataka
    prev_hash = models.CharField(max_length=64)  # hash prethodnog zapisa
    chain_hash = models.CharField(max_length=64)  # SHA-256(data_hash + prev_hash)
    user_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    chain_valid = models.BooleanField(default=True)  # False = lanac probijen

    class Meta(TenantModel.Meta):
        db_table = "sentinel_audit_chain"
        verbose_name = "Audit Chain"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["company", "chain_valid"]),
        ]

    def __str__(self):
        return f"{self.operation} {self.content_type} #{self.object_id}"
