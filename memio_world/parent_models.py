"""
PLAY.EU Parent Account + Child Progress — Server-side user management
======================================================================
ParentAccount: email-based auth (memio_world baza, nema FK na auth_user)
ChildProgress: XP, razina, zadaci, bedževi — persists across devices
SessionToken: cookie-based auth bez Django auth sistema
"""

import hashlib
import secrets
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class ParentAccount(models.Model):
    """Roditelj — vlasnik pretplate, može imati do 5 djece."""

    PLAN_CHOICES = [
        ("free", _("Besplatno")),
        ("trial", _("7-dnevni trial")),
        ("monthly", _("Mjesečna pretplata")),
        ("yearly", _("Godišnja pretplata")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    name = models.CharField(max_length=100, blank=True)

    # Pretplata
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    plan_started = models.DateTimeField(null=True, blank=True)
    plan_expires = models.DateTimeField(null=True, blank=True)

    # Referral
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.CharField(max_length=20, blank=True)
    referral_count = models.PositiveSmallIntegerField(default=0)

    # Settings
    preferred_language = models.CharField(max_length=5, default="hr")
    max_daily_minutes = models.PositiveSmallIntegerField(default=30)
    notifications_email = models.BooleanField(default=True)

    # GDPR compliance
    gdpr_consent = models.BooleanField(default=False, help_text="Explicit GDPR consent given")
    gdpr_consent_at = models.DateTimeField(null=True, blank=True)
    deletion_requested = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_parent_account"
        verbose_name = _("Roditelj")
        verbose_name_plural = _("Roditelji")

    def __str__(self):
        return f"{self.email} ({self.get_plan_display()})"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    def generate_referral_code(self):
        self.referral_code = "PLAY-" + secrets.token_hex(3).upper()

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.generate_referral_code()
        super().save(*args, **kwargs)


class SessionToken(models.Model):
    """Cookie-based auth — bez Django session frameworka (odvojena baza)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(ParentAccount, on_delete=models.CASCADE, related_name="sessions")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_session_token"

    def __str__(self):
        return f"Session: {self.parent.email}"

    @classmethod
    def create_for(cls, parent):
        from datetime import timedelta

        from django.utils import timezone

        token = secrets.token_hex(32)
        return cls.objects.using("memio_world").create(
            parent=parent,
            token=token,
            expires_at=timezone.now() + timedelta(days=30),
        )


class ChildProgress(models.Model):
    """Server-side progress tracking — XP, razina, zadaci, bedževi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.OneToOneField(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="progress",
    )
    parent = models.ForeignKey(
        ParentAccount,
        on_delete=models.CASCADE,
        related_name="children_progress",
    )

    # Memio Škola progress
    level = models.PositiveSmallIntegerField(default=0)
    xp = models.PositiveIntegerField(default=0)
    total_xp = models.PositiveIntegerField(default=0)
    completed_tasks = models.JSONField(default=list, blank=True)
    earned_badges = models.JSONField(default=list, blank=True)

    # Reading progress
    stories_read = models.JSONField(default=list, blank=True)
    pages_read = models.PositiveIntegerField(default=0)
    quizzes_completed = models.JSONField(default=list, blank=True)
    quiz_avg_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Activity tracking
    total_sessions = models.PositiveIntegerField(default=0)
    total_minutes = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    streak_days = models.PositiveSmallIntegerField(default=0)
    longest_streak = models.PositiveSmallIntegerField(default=0)

    # Interests (Talent Radar data)
    interest_scores = models.JSONField(default=dict, blank=True)

    # Diploma
    diploma_earned = models.BooleanField(default=False)
    diploma_earned_at = models.DateTimeField(null=True, blank=True)
    diploma_id = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_child_progress"
        verbose_name = _("Napredak djeteta")
        verbose_name_plural = _("Napretci djece")

    def __str__(self):
        return f"{self.child.name} — Lvl {self.level} ({self.total_xp} XP)"

    def add_xp(self, amount, task_id=None):
        self.xp += amount
        self.total_xp += amount
        if task_id and task_id not in self.completed_tasks:
            self.completed_tasks.append(task_id)

    def check_level_up(self):
        """Check if enough XP to level up."""
        thresholds = [100, 200, 350, 500]
        if self.level < len(thresholds) and self.xp >= thresholds[self.level]:
            self.xp = 0
            self.level += 1
            return True
        return False
