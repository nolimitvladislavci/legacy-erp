"""
Fenix v3 — Accounts Model | 13/10
"""

import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.utils import timezone
from core.base_model import BaseModel


class UserProfile(BaseModel):
    """
    ZAKON: user_type je kapija. CHILD ne ulazi u /hr/.
    Middleware ChildProtectionMiddleware provjerava ovo pri SVAKOM requestu.
    """

    class UserType(models.TextChoices):
        BUSINESS = "business", "Poslovni korisnik"
        CHILD = "child", "Dijete (playground only)"
        GUEST = "guest", "Gost (read-only)"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.BUSINESS,
        verbose_name="Tip korisnika",
        db_index=True,
    )

    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")
    avatar = models.ImageField(upload_to="accounts/avatars/", blank=True, verbose_name="Avatar")

    language = models.CharField(
        max_length=2,
        default="hr",
        choices=[("hr", "Hrvatski"), ("de", "Deutsch"), ("en", "English")],
        verbose_name="Jezik sucelja",
    )
    theme = models.CharField(
        max_length=10,
        default="auto",
        choices=[("light", "Svijetla"), ("dark", "Tamna"), ("auto", "Automatski")],
        verbose_name="Tema",
    )

    high_contrast = models.BooleanField(default=False, verbose_name="Visoki kontrast")
    large_text = models.BooleanField(default=False, verbose_name="Uvecani tekst")
    screen_reader_mode = models.BooleanField(default=False, verbose_name="Screen reader mod")
    reduce_motion = models.BooleanField(default=False, verbose_name="Smanji animacije")

    ai_enabled = models.BooleanField(default=True, verbose_name="AI oblacic aktivan")
    ai_voice_enabled = models.BooleanField(default=True, verbose_name="Glasovni unos aktivan")
    ai_voice_language = models.CharField(
        max_length=5,
        default="hr-HR",
        choices=[("hr-HR", "Hrvatski"), ("de-DE", "Deutsch"), ("en-US", "English")],
        verbose_name="Jezik glasovnog unosa",
    )
    ai_predictive_enabled = models.BooleanField(default=True, verbose_name="Prediktivni unos aktivan")

    # Lokalizacija
    timezone_name = models.CharField(max_length=50, default="Europe/Zagreb", verbose_name="Vremenska zona")

    # Status
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Zadnji online")
    onboarding_completed = models.BooleanField(default=False, verbose_name="Onboarding zavrsen")
    force_password_change = models.BooleanField(default=False, verbose_name="Promjena lozinke obavezna")

    # ── PIN (PBKDF2-SHA256 — siguran, brute-force resistant) ──────────────────
    PIN_EXPIRY_DAYS = 90

    pin_hash = models.CharField(max_length=256, blank=True, verbose_name="PIN hash")
    pin_set_at = models.DateTimeField(null=True, blank=True, verbose_name="PIN postavljen")
    pin_attempts = models.IntegerField(default=0, verbose_name="PIN pokusaji")
    pin_locked_until = models.DateTimeField(null=True, blank=True, verbose_name="PIN zakljucan do")
    pin_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="PIN istjece")

    # 2FA
    two_factor_enabled = models.BooleanField(default=False, verbose_name="2FA aktivan")
    two_factor_secret = models.CharField(max_length=64, blank=True, verbose_name="2FA secret")

    class Meta:
        verbose_name = "Profil korisnika"
        verbose_name_plural = "Profili korisnika"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    # ── PIN metode ─────────────────────────────────────────────────────────────

    def set_pin(self, raw_pin: str) -> None:
        """Postavi PIN — PBKDF2-SHA256 (Django make_password)."""
        if not raw_pin or len(raw_pin) < 4:
            raise ValueError("PIN mora imati najmanje 4 znamenke.")
        if not raw_pin.isdigit():
            raise ValueError("PIN smije sadrzavati samo znamenke.")
        self.pin_hash = make_password(raw_pin)
        self.pin_attempts = 0
        self.pin_locked_until = None
        self.pin_set_at = timezone.now()
        self.pin_expires_at = timezone.now() + timedelta(days=self.PIN_EXPIRY_DAYS)
        self.save(update_fields=["pin_hash", "pin_attempts", "pin_locked_until", "pin_set_at", "pin_expires_at"])

    def check_pin(self, raw_pin: str) -> bool:
        """Provjeri PIN s lockout zastitom (5 neuspjelih = 15 min lock)."""
        if self.is_pin_locked():
            raise PermissionError("PIN je zakljucan. Pokusajte ponovo za par minuta.")
        result = django_check_password(raw_pin, self.pin_hash) if self.pin_hash else False
        if result:
            self.pin_attempts = 0
            self.pin_locked_until = None
            self.save(update_fields=["pin_attempts", "pin_locked_until"])
        else:
            self.pin_attempts += 1
            if self.pin_attempts >= 5:
                self.pin_locked_until = timezone.now() + timedelta(minutes=15)
            self.save(update_fields=["pin_attempts", "pin_locked_until"])
        return result

    def is_pin_locked(self) -> bool:
        """Vrati True ako je PIN trenutno zakljucan."""
        if self.pin_locked_until and self.pin_locked_until > timezone.now():
            return True
        if self.pin_locked_until and self.pin_locked_until <= timezone.now():
            # Auto-unlock: isteklo je vrijeme lockout-a
            self.pin_locked_until = None
            self.pin_attempts = 0
            self.save(update_fields=["pin_locked_until", "pin_attempts"])
        return False

    def is_pin_expired(self) -> bool:
        """Vrati True ako je PIN istekao (> 90 dana)."""
        if not self.pin_expires_at:
            return False
        return self.pin_expires_at < timezone.now()

    def has_pin(self) -> bool:
        """Ima li korisnik postavljen PIN."""
        return bool(self.pin_hash)

    @property
    def is_business_user(self) -> bool:
        """Poslovni korisnik — moze uci u /hr/ admin prostor."""
        return self.user_type == self.UserType.BUSINESS

    @property
    def is_child(self) -> bool:
        """Dijete — ZABRANJENO u /hr/. Samo /igra/ i /no-limit/ rute."""
        return self.user_type == self.UserType.CHILD

    def get_active_company(self):
        """Vrati prvu firmu gdje je Owner ili Admin."""
        membership = (
            self.user.memberships.filter(role__in=("owner", "admin"), is_deleted=False)
            .select_related("company")
            .first()
        )
        return membership.company if membership else None

    def to_ai_context(self):
        ctx = super().to_ai_context()
        ctx.update({"user": self.user.username, "language": self.language})
        return ctx


class CompanyMembership(BaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Vlasnik"
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Voditelj"
        ACCOUNTANT = "accountant", "Knjigovodja"
        EMPLOYEE = "employee", "Zaposlenik"
        VIEWER = "viewer", "Pregledavac"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE, verbose_name="Uloga")
    is_default = models.BooleanField(default=False, verbose_name="Zadana firma")

    class Meta:
        verbose_name = "Clanstvo u tvrtki"
        verbose_name_plural = "Clanstva u tvrtkama"
        unique_together = ["user", "company"]
        indexes = [
            models.Index(fields=["user", "company"]),
            models.Index(fields=["user", "is_default"]),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.company} ({self.get_role_display()})"

    @property
    def is_admin_or_above(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    @property
    def can_manage(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.MANAGER)

    @property
    def can_invoice(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.MANAGER, self.Role.ACCOUNTANT)


class LoginAudit(models.Model):
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


class CompanyInvite(BaseModel):
    """PLAN_023 — Email invite to join a company with a specific role."""

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invites")
    email = models.EmailField(verbose_name="E-mail primaoca")
    role = models.CharField(
        max_length=20,
        choices=CompanyMembership.Role.choices,
        default=CompanyMembership.Role.EMPLOYEE,
        verbose_name="Uloga",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    message = models.TextField(blank=True, verbose_name="Poruka (opcionalno)")

    class Meta(BaseModel.Meta):
        verbose_name = "Pozivnica"
        verbose_name_plural = "Pozivnice"
        indexes = [
            models.Index(fields=["email", "company"]),
            models.Index(fields=["token"]),
        ]

    def __str__(self):
        return f"Pozivnica {self.email} → {self.company} ({self.get_role_display()})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.accepted and not self.is_expired and not self.is_deleted

    def accept(self, user):
        """Accept the invite: create/update CompanyMembership."""
        CompanyMembership.objects.update_or_create(user=user, company=self.company, defaults={"role": self.role})
        self.accepted = True
        self.accepted_at = timezone.now()
        self.save(update_fields=["accepted", "accepted_at"])
