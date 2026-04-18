"""
Fenix v3 — Accounts Model | 13/10

Koristimo Django auth.User + profilni model.
Zašto ne custom User? Jer Django admin, third-party, i session
framework ovise o auth.User. Profile pattern je čišći.

Iz starog sustava:
- CompanyMembership (user ↔ company, s rolama)
- UserPreferences (jezik, tema, AI postavke, accessibility)
- LoginAudit (GDPR log svakog logina)
"""

from django.db import models
from django.contrib.auth.models import User
from core.base_model import BaseModel


class UserProfile(BaseModel):
    """
    Profil korisnika — sve što auth.User nema.
    1:1 veza s User. Kreira se automatski.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # ── Osobni podaci ─────────────────────────
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")
    avatar = models.ImageField(upload_to="accounts/avatars/", blank=True, verbose_name="Avatar")

    # ── Postavke ──────────────────────────────
    language = models.CharField(
        max_length=2,
        default="hr",
        choices=[("hr", "Hrvatski"), ("de", "Deutsch"), ("en", "English")],
        verbose_name="Jezik sučelja",
    )
    theme = models.CharField(
        max_length=10,
        default="auto",
        choices=[("light", "Svijetla"), ("dark", "Tamna"), ("auto", "Automatski")],
        verbose_name="Tema",
    )

    # ── Accessibility ─────────────────────────
    high_contrast = models.BooleanField(
        default=False, verbose_name="Visoki kontrast", help_text="WCAG AAA pojačani kontrast"
    )
    large_text = models.BooleanField(default=False, verbose_name="Uvećani tekst", help_text="18px umjesto 16px baza")
    screen_reader_mode = models.BooleanField(
        default=False, verbose_name="Screen reader mod", help_text="Dodatne aria-live regije i opisi"
    )
    reduce_motion = models.BooleanField(
        default=False, verbose_name="Smanji animacije", help_text="Za korisnike osjetljive na pokret"
    )

    # ── AI postavke ───────────────────────────
    ai_enabled = models.BooleanField(default=True, verbose_name="AI oblačić aktivan")
    ai_voice_enabled = models.BooleanField(default=True, verbose_name="Glasovni unos aktivan")
    ai_voice_language = models.CharField(
        max_length=5,
        default="hr-HR",
        choices=[
            ("hr-HR", "Hrvatski"),
            ("de-DE", "Deutsch"),
            ("en-US", "English"),
        ],
        verbose_name="Jezik glasovnog unosa",
    )
    ai_predictive_enabled = models.BooleanField(default=True, verbose_name="Prediktivni unos aktivan")

    class Meta:
        verbose_name = "Profil korisnika"
        verbose_name_plural = "Profili korisnika"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    def to_ai_context(self):
        ctx = super().to_ai_context()
        ctx.update(
            {
                "user": self.user.username,
                "language": self.language,
                "accessibility": {
                    "high_contrast": self.high_contrast,
                    "large_text": self.large_text,
                    "screen_reader": self.screen_reader_mode,
                    "reduce_motion": self.reduce_motion,
                },
            }
        )
        return ctx


class CompanyMembership(BaseModel):
    """
    User ↔ Company veza.
    Jedan user može biti u više firmi (umbrella pattern).
    Svaka veza ima rolu i dozvole.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Vlasnik"
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Voditelj"
        ACCOUNTANT = "accountant", "Knjigovođa"
        EMPLOYEE = "employee", "Zaposlenik"
        VIEWER = "viewer", "Pregledavač"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE, verbose_name="Uloga")
    is_default = models.BooleanField(
        default=False, verbose_name="Zadana firma", help_text="Firma koja se otvara pri loginu"
    )

    class Meta:
        verbose_name = "Članstvo u tvrtki"
        verbose_name_plural = "Članstva u tvrtkama"
        unique_together = ["user", "company"]
        indexes = [
            models.Index(fields=["user", "company"]),
            models.Index(fields=["user", "is_default"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.company} ({self.get_role_display()})"

    @property
    def is_admin_or_above(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    @property
    def can_manage(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.MANAGER)


class LoginAudit(models.Model):
    """
    GDPR audit log za login pokušaje.
    Ne nasljeđuje BaseModel jer nema soft delete — log je trajan.
    """

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="login_audits")
    username_attempted = models.CharField(max_length=150)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Login audit"
        verbose_name_plural = "Login audit log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.username_attempted} [{status}] {self.timestamp}"
