"""
FenixSignal — BORG senzorni sustav.

Svaki signal = korisnik prijavljen problem, bug, zbunjenost ili prijedlog.
Minimalni MVP: model + view + floating gumb. AI triage u v2.
"""
import uuid
from django.db import models, DatabaseError, IntegrityError
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist


class FenixSignal(models.Model):
    """Korisnički signal — prijava greške, pitanje, prijedlog."""

    class SignalType(models.TextChoices):
        BUG = "bug", "Greška / Bug"
        CONFUSION = "confusion", "Zbunjenost / Nejasno"
        SUGGESTION = "suggestion", "Prijedlog"
        AI_BAD = "ai_bad", "AI loš odgovor"
        URGENT = "urgent", "Hitno"

    class Source(models.TextChoices):
        IN_APP = "in_app", "In-app gumb"
        WHATSAPP = "whatsapp", "WhatsApp"
        POS = "pos", "POS terminal"
        API = "api", "API"

    class Status(models.TextChoices):
        NEW = "new", "Novi"
        TRIAGED = "triaged", "Triažiran"
        IN_PROGRESS = "in_progress", "U radu"
        RESOLVED = "resolved", "Riješen"
        WONT_FIX = "wont_fix", "Neće se raditi"
        DUPLICATE = "duplicate", "Duplikat"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fenix_signals",
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fenix_signals",
    )

    signal_type = models.CharField(max_length=12, choices=SignalType.choices, default=SignalType.BUG)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.IN_APP)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)

    # Sadržaj
    message = models.TextField(help_text="Opis problema ili prijedloga")
    page_url = models.CharField(max_length=500, blank=True, help_text="URL stranice gdje je signal poslan")
    user_agent = models.CharField(max_length=300, blank=True)
    screen_width = models.PositiveIntegerField(null=True, blank=True)

    # Kontekst (JSON za fleksibilnost)
    context = models.JSONField(default=dict, blank=True, help_text="Extra kontekst: terminal_id, invoice_id, etc.")

    # Triage
    priority = models.PositiveSmallIntegerField(default=3, help_text="1=critical, 2=high, 3=normal, 4=low")
    triage_note = models.TextField(blank=True)
    assigned_to = models.CharField(max_length=50, blank=True, help_text="cc_code / gemini / ivan / marija")
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Rate limit tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fenix_signal"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="idx_signal_status_date"),
            models.Index(fields=["company", "-created_at"], name="idx_signal_company_date"),
        ]
        verbose_name = "Prijava problema"
        verbose_name_plural = "Prijave problema"

    def __str__(self):
        who = self.user.get_full_name() if self.user else "Anon"
        return f"[{self.signal_type}] {who}: {self.message[:60]}"
