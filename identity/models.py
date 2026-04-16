"""
LIMIT Connect — Identity Orchestration Layer
============================================
Bankarski model: Uđi, ali ništa ne možeš dok se ne verificiraš.
Zero-Trust + Progressive Authorization + AI-assisted matching

Stanja identiteta (FSM):
  GHOST     → autentificiran, bez firme, blokiran na /pristup/
  PENDING   → zahtjev poslan, čeka admin odobrenje
  VERIFIED  → OIB/CroValidator potvrđen, čeka assignment
  ACTIVE    → puna autorizacija, vezano na firmu
  SUSPENDED → suspendiran, pristup oduzet
  ORPHANED  → firma ugašena, korisnik bez krovne firme
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ── Invite Token ──────────────────────────────────────────────────────────────
class IdentityInviteToken(models.Model):
    """
    HMAC-signed pozivnica za pridruživanje firmi.
    Bankarski standard: 7 dana, 1x upotreba, admin-issued.
    """
    SCOPE_CHOICES = [
        ("worker", _("Radnik")),
        ("company_admin", _("Administrator")),
        ("accountant", _("Knjigovođa")),
        ("viewer", _("Pregledač")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="invite_tokens", verbose_name=_("Firma")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="issued_invites"
    )
    email_hint = models.EmailField(blank=True, help_text="Opcionalno: invite vezan za email")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="worker")
    
    # Sigurnost
    is_used = models.BooleanField(default=False, db_index=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="used_invites"
    )
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    ip_created = models.GenericIPAddressField(null=True, blank=True)
    ip_used = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = "identity_invite_token"
        verbose_name = _("Pozivnica")
        verbose_name_plural = _("Pozivnice")
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["company", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]

    @classmethod
    def generate(cls, company, created_by, scope="worker", email_hint="", days=7, ip=None):
        raw = secrets.token_urlsafe(32)
        sig = hmac.new(
            settings.SECRET_KEY.encode(),
            raw.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        token = f"{raw[:16]}.{sig}"
        return cls.objects.create(
            token=token,
            company=company,
            created_by=created_by,
            scope=scope,
            email_hint=email_hint,
            expires_at=timezone.now() + timedelta(days=days),
            ip_created=ip,
        )

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def consume(self, user, ip=None):
        if not self.is_valid():
            return False
        self.is_used = True
        self.used_by = user
        self.used_at = timezone.now()
        self.ip_used = ip
        self.save(update_fields=["is_used", "used_by", "used_at", "ip_used"])
        return True

    def __str__(self):
        return f"Invite → {self.company.name} ({self.scope})"


# ── Join Request ──────────────────────────────────────────────────────────────
class IdentityJoinRequest(models.Model):
    """
    Zahtjev korisnika za pridruživanje firmi.
    Admin odobrava/odbija. AI može auto-odobriti uz visoki trust score.
    """
    STATUS_CHOICES = [
        ("pending",   _("Čeka odobrenje")),
        ("approved",  _("Odobreno")),
        ("rejected",  _("Odbijeno")),
        ("auto",      _("AI auto-odobreno")),
        ("expired",   _("Isteklo")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="join_requests"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="join_requests"
    )
    requested_role = models.CharField(max_length=30, default="worker")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    
    # Verifikacija identiteta
    oib_provided = models.CharField(max_length=11, blank=True)
    oib_verified = models.BooleanField(default=False)
    oib_verified_at = models.DateTimeField(null=True, blank=True)
    oib_source = models.CharField(max_length=50, blank=True)  # CroValidator, manual, fina
    
    # AI asistencija
    ai_trust_score = models.FloatField(default=0.0)  # 0.0 - 1.0
    ai_reasoning = models.TextField(blank=True)
    ai_auto_approved = models.BooleanField(default=False)
    
    # Bilješke
    user_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="resolved_requests"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "identity_join_request"
        verbose_name = _("Zahtjev za pridruživanje")
        verbose_name_plural = _("Zahtjevi za pridruživanje")
        unique_together = [("user", "company", "status")]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["company", "status"]),
        ]

    def approve(self, by_user=None, note="", auto=False):
        from accounts.models import UserProfile
        from django.db import transaction
        with transaction.atomic():
            p = UserProfile.objects.select_for_update().get(user=self.user)
            p.company = self.company
            p.role = self.requested_role
            p.save(update_fields=["company", "role"])
            self.status = "auto" if auto else "approved"
            self.resolved_at = timezone.now()
            self.resolved_by = by_user
            self.admin_note = note
            self.save(update_fields=["status", "resolved_at", "resolved_by", "admin_note"])
        return True

    def __str__(self):
        return f"{self.user.username} → {self.company.name} ({self.status})"


# ── Domain Whitelist ──────────────────────────────────────────────────────────
class CompanyDomainWhitelist(models.Model):
    """
    Email domene koje AI može koristiti za auto-matching.
    GDPR: samo ako admin eksplicitno uključi.
    """
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE,
        related_name="domain_whitelist"
    )
    domain = models.CharField(max_length=100, db_index=True)
    allow_discovery = models.BooleanField(
        default=False,
        help_text="Prikaži sugestiju novim korisnicima s ovom domenom (GDPR: opt-in)"
    )
    allow_auto_approve = models.BooleanField(
        default=False,
        help_text="AI može auto-odobriti ako je OIB verificiran + domena matches"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_domain_whitelist"
        unique_together = [("company", "domain")]
        verbose_name = _("Whitelist domene")

    def __str__(self):
        return f"{self.domain} → {self.company.name}"


# ── Identity Audit Log ────────────────────────────────────────────────────────
class IdentityAuditLog(models.Model):
    """
    Svaki sigurnosno-relevantni event u identity sustavu.
    Nepromjenjivo — append-only.
    """
    EVENT_CHOICES = [
        ("login_no_company",   "Login bez firme — Ghost state"),
        ("join_requested",     "Zahtjev za pridruživanje"),
        ("join_approved",      "Odobreno pridruživanje"),
        ("join_rejected",      "Odbijeno pridruživanje"),
        ("join_auto",          "AI auto-odobrilo"),
        ("invite_created",     "Pozivnica kreirana"),
        ("invite_used",        "Pozivnica iskorištena"),
        ("invite_expired",     "Pozivnica istekla"),
        ("oib_verified",       "OIB verificiran (CroValidator)"),
        ("oib_failed",         "OIB verifikacija neuspješna"),
        ("domain_matched",     "Email domena matchana"),
        ("suspicious_attempt", "Sumnjivi pokušaj pristupa"),
        ("account_merged",     "Računi spojeni"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="identity_audit"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL,
        null=True, blank=True
    )
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Integrity hash — lanac nepromjenjivih zapisa
    prev_hash = models.CharField(max_length=64, blank=True)
    entry_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "identity_audit_log"
        verbose_name = _("Identity audit log")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Hash chain — kao blockchain, nepromjenjivi lanac
        if not self.entry_hash:
            last = IdentityAuditLog.objects.order_by("-created_at").first()
            self.prev_hash = last.entry_hash if last else "GENESIS"
            data = f"{self.event}:{self.user_id}:{self.ip_address}:{self.created_at}:{self.prev_hash}"
            self.entry_hash = hashlib.sha256(data.encode()).hexdigest()
        super().save(*args, **kwargs)

    @classmethod
    def log(cls, event, user=None, company=None, detail=None, ip=None, ua=""):
        return cls.objects.create(
            event=event, user=user, company=company,
            detail=detail or {}, ip_address=ip, user_agent=ua[:200]
        )

    def __str__(self):
        return f"{self.event} | {self.user} | {self.created_at:%Y-%m-%d %H:%M}"
