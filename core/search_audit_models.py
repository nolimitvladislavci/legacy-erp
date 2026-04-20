"""
core/search_audit_models.py — SearchAuditLog + trending queries

Svaки search → 1 log. Trending = top 5 upita ove sedmice po firmi.
Budućnost 2 (Sigurnost): GDPR compliant, company-isolated, IP-masked.
"""

import uuid

from django.db import models
from django.utils import timezone


class SearchAuditLog(models.Model):
    """
    Svaki search ostavi trag — osnova za trending i AI prijedloge.
    GDPR: ip_address maskiran (zadnja oktet), user FK nullable.
    """

    SOURCE_TEXT = "text"
    SOURCE_VOICE = "voice"
    SOURCE_CAMERA = "camera"
    SOURCE_CHAT = "chat"
    SOURCE_CHOICES = [
        (SOURCE_TEXT, "Tekst"),
        (SOURCE_VOICE, "Glas"),
        (SOURCE_CAMERA, "Kamera"),
        (SOURCE_CHAT, "Chat"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    query = models.CharField(max_length=500)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_TEXT)
    result_count = models.SmallIntegerField(default=0, help_text="Broj rezultata — 0 = ništa pronađeno → AI prijedlog")
    ai_suggested = models.BooleanField(default=False, help_text="True ako je AI predložio kreiranje entiteta")
    searched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_masked = models.CharField(max_length=20, blank=True, help_text="Maskiran IP (GDPR): x.x.x.0 format")

    class Meta:
        app_label = "core"
        verbose_name = "Search audit log"
        verbose_name_plural = "Search audit logovi"
        indexes = [
            models.Index(fields=["company", "searched_at"]),
            models.Index(fields=["company", "query"]),
        ]
        ordering = ["-searched_at"]

    def __str__(self):
        return f"{self.query[:40]} [{self.source}] — {self.result_count} rezultata"

    @classmethod
    def log(
        cls, company, query: str, source: str = SOURCE_TEXT, result_count: int = 0, user=None, ip: str = ""
    ) -> "SearchAuditLog":
        """Factory za brzo logiranje."""
        if not query or not query.strip():
            return None
        ip_masked = ""
        if ip:
            parts = ip.rsplit(".", 1)
            ip_masked = parts[0] + ".0" if len(parts) == 2 else ip
        return cls.objects.create(
            company=company,
            user=user,
            query=query[:500],
            source=source,
            result_count=result_count,
            ip_masked=ip_masked,
        )

    @classmethod
    def trending(cls, company, days: int = 7, limit: int = 5) -> list[str]:
        """
        Top N upita ove sedmice u firmi.
        Vraća listu stringova za prikaz u trending sekciji.
        """
        from datetime import timedelta

        from django.db.models import Count

        since = timezone.now() - timedelta(days=days)
        rows = (
            cls.objects.filter(company=company, searched_at__gte=since)
            .values("query")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")[:limit]
        )
        return [r["query"] for r in rows]


class ChatMessage(models.Model):
    """
    Chat history za Command Center — interaktivni AI razgovor.
    Budućnost 1 (Tehnologija): DeepSeek intent + entity suggestions.
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, "Korisnik"), (ROLE_ASSISTANT, "AI asistent")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    session_id = models.CharField(max_length=64, db_index=True, help_text="Browser session token za grupiranje poruka")
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True, help_text="search_results, suggested_actions, intent itd.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "core"
        verbose_name = "Chat poruka"
        verbose_name_plural = "Chat poruke"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "session_id", "created_at"]),
            models.Index(fields=["company", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
