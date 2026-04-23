"""
FENIX SENTINEL — Digitalni Ured Models (PLAN_080)
DigitalniUred, UredKonverzacija, UredPoruka, UredInsight
"""

from django.db import models
from django.conf import settings
from core.base_model import TenantModel, BaseModel


class DigitalniUred(TenantModel):
    """Ured per-company — sjećanje, profil, aktivna sesija"""

    memory = models.JSONField(default=dict)
    preferences = models.JSONField(default=dict)

    total_conversations = models.IntegerField(default=0)
    total_insights = models.IntegerField(default=0)
    last_active = models.DateTimeField(null=True, blank=True)

    advisor_name = models.CharField(max_length=100, default="Fenix Savjetnik")
    advisor_tone = models.CharField(max_length=20, default="professional")

    class Meta(TenantModel.Meta):
        db_table = "sentinel_digitalni_ured"
        verbose_name = "Digitalni Ured"

    def __str__(self):
        return f"Ured: {self.company}"


class UredKonverzacija(TenantModel):
    """Jedna sesija razgovora"""

    TOPIC = [
        ("pdv", "PDV i porezi"),
        ("eu", "EU fondovi"),
        ("hr", "Zaposlenici i plaće"),
        ("cashflow", "Novčani tok"),
        ("compliance", "Usklađenost"),
        ("obrasci", "Obrasci"),
        ("general", "Opće"),
    ]

    ured = models.ForeignKey(DigitalniUred, on_delete=models.CASCADE, related_name="conversations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ured_conversations")
    topic = models.CharField(max_length=20, choices=TOPIC, default="general")
    title = models.CharField(max_length=200, blank=True)
    last_message_at = models.DateTimeField(auto_now=True)
    is_resolved = models.BooleanField(default=False)
    summary = models.TextField(blank=True)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_ured_konverzacija"
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Konv #{self.pk}: {self.title or self.topic}"


class UredPoruka(BaseModel):
    """Jedna poruka u konverzaciji"""

    ROLE = [("user", "Korisnik"), ("assistant", "AI"), ("system", "Sustav")]

    konverzacija = models.ForeignKey(UredKonverzacija, on_delete=models.CASCADE, related_name="poruke")
    role = models.CharField(max_length=20, choices=ROLE)
    sadrzaj = models.TextField()

    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    model_used = models.CharField(max_length=50, default="claude-3-5-haiku-20241022")
    latency_ms = models.IntegerField(default=0)

    extracted_actions = models.JSONField(default=list)
    extracted_alerts = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        db_table = "sentinel_ured_poruka"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.sadrzaj[:60]}"


class UredInsight(TenantModel):
    """Proaktivni uvid — AI pronašao nešto važno"""

    PRIORITY = [("low", "Nisko"), ("medium", "Srednje"), ("high", "Visoko")]

    ured = models.ForeignKey(DigitalniUred, on_delete=models.CASCADE, related_name="insights")
    naslov = models.CharField(max_length=200)
    sadrzaj = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY, default="medium")
    topic = models.CharField(max_length=20, default="general")
    is_read = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        db_table = "sentinel_ured_insight"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "is_read"]),
        ]

    def __str__(self):
        return f"[{self.priority}] {self.naslov}"
