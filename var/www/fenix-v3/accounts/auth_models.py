"""
Fenix v3 — Auth Models | Blok B + C + D
- PinRecoveryToken (Blok B)
- MagicToken       (Blok C)
- LoginAttempt     (Blok D)
"""

import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PinRecoveryToken(models.Model):
    """
    Blok B — PIN Recovery.
    Rate limit: 3 zahtjeva/sat po korisniku.
    TTL: 24 sata. Single-use (consumed on use).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pin_recovery_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_pin_recovery_token"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "created_at"]),
        ]

    @classmethod
    def create_for_user(cls, user, ip=None):
        """Kreira token uz rate limit (maks 3/sat)."""
        recent = cls.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= 3:
            raise PermissionError("Previse zahtjeva. Pokusajte za sat vremena.")
        # Invalidate existing unused tokens
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        token = secrets.token_urlsafe(48)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
            ip_address=ip,
        )

    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def consume(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return f"PinRecovery({self.user.username}, expires={self.expires_at:%Y-%m-%d %H:%M})"


class MagicToken(models.Model):
    """
    Blok C — Magic Link (passwordless login).
    Token tip: partner / investitor / radnik / admin.
    TTL: 24 sata (default). Single-use.
    """

    TOKEN_TYPES = [
        ("partner", "Partner"),
        ("investor", "Investitor"),
        ("worker", "Radnik"),
        ("admin", "Admin"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="magic_tokens")
    token = models.CharField(max_length=86, unique=True)
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPES, default="partner")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_magic_token"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "expires_at"]),
        ]

    @classmethod
    def create(cls, user, token_type="partner", context=None, ip=None, ttl_hours=24):
        token = secrets.token_urlsafe(64)
        return cls.objects.create(
            user=user,
            token=token,
            token_type=token_type,
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
            context=context or {},
            ip_address=ip,
        )

    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def consume(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return f"MagicToken({self.user.username}, type={self.token_type}, expires={self.expires_at:%Y-%m-%d %H:%M})"


class LoginAttempt(models.Model):
    """
    Blok D — Concurrent Session Detection.
    Logiraj svaki uspjesni login s IP + UA + session key.
    Signal na user_logged_in automatski kreira zapis.
    """

    METHODS = [
        ("password", "Lozinka"),
        ("pin", "PIN"),
        ("magic", "Magic Link"),
        ("passkey", "Passkey"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_attempts")
    email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=20, choices=METHODS, default="password")
    success = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = "accounts_login_attempt"
        indexes = [
            models.Index(fields=["user", "attempted_at"]),
            models.Index(fields=["ip_address", "attempted_at"]),
        ]
        ordering = ["-attempted_at"]

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.email} [{status}] {self.ip_address} {self.attempted_at:%Y-%m-%d %H:%M}"
