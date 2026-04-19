"""
memio_world/kum_models.py — Kum sustav
=======================================
Kum je ParentAccount koji sponzorira dijete druge obitelji.
ISTI korisnik može istovremeno biti:
  - Roditelj → ima vlastitu djecu na platformi
  - Kum      → plaća pretplatu tuđoj djeci (uz roditeljsko odobrenje)

Tko može biti Kum: bilo koji ParentAccount (krsni kum, stric, djed,
prijatelj obitelji, učiteljica...).

Flow:
  1. Roditelj šalje pozivnicu Kumu (KumInvitation — email poziv)
  2. Kum prihvati → KumRelationship nastaje (status: active)
  3. Kum može pokloniti pretplatu → KumGift
  4. Roditelj odobri svako plaćanje (parent_approved=True)
  5. Kum vidi napredak djeteta samo ako roditelj dozvoli (can_see_progress)

Arhitektura: svi u istoj memio_world bazi, app_label=memio_world
"""

import secrets
import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ════════════════════════════════════════════════════════════════
# KUM INVITATION — Roditelj poziva Kuma
# ════════════════════════════════════════════════════════════════


class KumInvitation(models.Model):
    """
    Roditelj šalje email pozivnicu potencijalnom Kumu.
    Token je jednosmjerni link — Kum klikne, registrira se/logira,
    i veza je uspostavljena.
    """

    STATUS_CHOICES = [
        ("pending", _("Čeka prihvat")),
        ("accepted", _("Prihvaćeno")),
        ("declined", _("Odbijeno")),
        ("expired", _("Isteklo")),
        ("revoked", _("Povučeno od roditelja")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, db_index=True)

    # Tko poziva
    parent = models.ForeignKey(
        "memio_world.ParentAccount",
        on_delete=models.CASCADE,
        related_name="sent_kum_invitations",
        help_text="Roditelj koji poziva Kuma",
    )

    # Za koje dijete
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="kum_invitations",
        help_text="Dijete za koje se poziva Kum",
    )

    # Kome se šalje
    kum_email = models.EmailField(help_text="Email potencijalnog Kuma")
    kum_name = models.CharField(max_length=100, blank=True, help_text="Ime Kuma (opcionalno)")
    personal_note = models.TextField(
        blank=True,
        max_length=500,
        help_text="Osobna poruka roditelja Kumu (do 500 znakova)",
    )

    # Dozvole koje roditelj unaprijed daje Kumu
    can_pay_subscription = models.BooleanField(
        default=True,
        help_text="Kum smije platiti mjesečnu/godišnju pretplatu",
    )
    can_see_progress = models.BooleanField(
        default=True,
        help_text="Kum vidi napredak djeteta (XP, pročitane priče)",
    )
    can_send_messages = models.BooleanField(
        default=False,
        help_text="Kum može slati poruke djetetu kroz platformu",
    )

    # Status i timing
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    expires_at = models.DateTimeField(help_text="Pozivnica vrijedi 30 dana")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_kum_invitation"
        ordering = ["-created_at"]
        verbose_name = _("Kum pozivnica")
        verbose_name_plural = _("Kum pozivnice")

    def __str__(self):
        return f"Pozivnica za {self.kum_email} → {self.child.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return self.status == "pending" and timezone.now() < self.expires_at

    def accept(self, kum_account):
        """Kum prihvati pozivnicu → kreira KumRelationship."""
        if not self.is_valid:
            raise ValueError("Pozivnica je istekla ili nevažeća.")
        self.status = "accepted"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

        rel, created = KumRelationship.objects.using("memio_world").get_or_create(
            kum=kum_account,
            child=self.child,
            defaults={
                "parent": self.parent,
                "can_pay_subscription": self.can_pay_subscription,
                "can_see_progress": self.can_see_progress,
                "can_send_messages": self.can_send_messages,
                "invitation": self,
            },
        )
        return rel

    def decline(self):
        self.status = "declined"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])


# ════════════════════════════════════════════════════════════════
# KUM RELATIONSHIP — Aktivna veza Kum ↔ Dijete
# ════════════════════════════════════════════════════════════════


class KumRelationship(models.Model):
    """
    Aktivna veza između Kuma i djeteta.

    Kum (ParentAccount) ↔ Dijete (ChildProfile)
    uz odobrenje Roditelja (ParentAccount).

    Ista osoba može biti:
      - Kum za više djece (više KumRelationship redaka, kum=isti)
      - Ima vlastitu djecu čiji Kum je netko drugi
    """

    STATUS_CHOICES = [
        ("active", _("Aktivan")),
        ("paused", _("Privremeno pauziran")),
        ("revoked", _("Povučen od roditelja")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    kum = models.ForeignKey(
        "memio_world.ParentAccount",
        on_delete=models.CASCADE,
        related_name="kum_relationships",  # "Za koga sam Kum"
        help_text="Kum (sponsorski roditelj)",
    )
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="kum_relations",  # "Tko mi je Kum"
        help_text="Kumče (dijete koje sponzorira)",
    )
    parent = models.ForeignKey(
        "memio_world.ParentAccount",
        on_delete=models.CASCADE,
        related_name="approved_kum_relations",  # "Čije Kume sam odobrio"
        help_text="Biološki/skrbni roditelj koji je odobrio vezu",
    )
    invitation = models.OneToOneField(
        KumInvitation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resulting_relationship",
    )

    # Dozvole (roditelj može mijenjati u bilo kojem trenutku)
    can_pay_subscription = models.BooleanField(default=True)
    can_see_progress = models.BooleanField(default=True)
    can_send_messages = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_kum_relationship"
        unique_together = [("kum", "child")]
        ordering = ["-created_at"]
        verbose_name = _("Kum veza")
        verbose_name_plural = _("Kum veze")

    def __str__(self):
        return f"{self.kum.name or self.kum.email} → Kum za {self.child.name}"

    @property
    def is_active(self):
        return self.status == "active"


# ════════════════════════════════════════════════════════════════
# KUM GIFT — Poklon pretplate
# ════════════════════════════════════════════════════════════════


class KumGift(models.Model):
    """
    Kum plaća pretplatu za kumče.

    Svaki poklon zahtijeva:
      1. KumRelationship.can_pay_subscription = True
      2. parent_approved = True (roditelj mora potvrditi)

    Nakon odobrenja: child.parent.plan se ažurira,
    ali se bilježi da je KUM platio (transparentnost).
    """

    PLAN_CHOICES = [
        ("monthly", _("Mjesečna pretplata (9.99 EUR)")),
        ("yearly", _("Godišnja pretplata (79.99 EUR)")),
        ("trial_3", _("3-mjesečni poklon (24.99 EUR)")),
    ]

    PLAN_PRICES = {
        "monthly": "9.99",
        "yearly": "79.99",
        "trial_3": "24.99",
    }

    STATUS_CHOICES = [
        ("pending_parent", _("Čeka roditeljsko odobrenje")),
        ("pending_payment", _("Odobreno — čeka plaćanje")),
        ("active", _("Aktivan poklon")),
        ("expired", _("Istekao")),
        ("declined", _("Odbijen od roditelja")),
        ("refunded", _("Refundirano")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    relationship = models.ForeignKey(
        KumRelationship,
        on_delete=models.CASCADE,
        related_name="gifts",
    )

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    amount_eur = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_parent")

    # Roditeljsko odobrenje
    parent_approved = models.BooleanField(default=False)
    parent_approved_at = models.DateTimeField(null=True, blank=True)
    parent_decline_reason = models.CharField(max_length=300, blank=True)

    # Plaćanje (Stripe ili manualno)
    stripe_payment_intent = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Trajanje poklona
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    # Poruka Kuma djetetu (vidljiva nakon aktivacije)
    gift_message = models.TextField(
        blank=True,
        max_length=500,
        help_text="Osobna poruka Kuma kumčetu uz poklon",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_kum_gift"
        ordering = ["-created_at"]
        verbose_name = _("Kum poklon pretplate")
        verbose_name_plural = _("Kum pokloni pretplata")

    def __str__(self):
        return (
            f"{self.relationship.kum.name or self.relationship.kum.email} → "
            f"{self.relationship.child.name} ({self.get_plan_display()}, {self.status})"
        )

    def save(self, *args, **kwargs):
        if not self.amount_eur:
            self.amount_eur = self.PLAN_PRICES.get(self.plan, "9.99")
        super().save(*args, **kwargs)

    def approve(self, parent):
        """Roditelj odobri poklon."""
        if self.relationship.parent_id != parent.id:
            raise PermissionError("Samo roditelj može odobriti poklon.")
        if not self.relationship.can_pay_subscription:
            raise PermissionError("Kum nema dozvolu za plaćanje pretplate.")
        self.parent_approved = True
        self.parent_approved_at = timezone.now()
        self.status = "pending_payment"
        self.save(update_fields=["parent_approved", "parent_approved_at", "status"])

    def decline(self, parent, reason=""):
        """Roditelj odbije poklon."""
        if self.relationship.parent_id != parent.id:
            raise PermissionError("Samo roditelj može odbiti poklon.")
        self.status = "declined"
        self.parent_decline_reason = reason
        self.save(update_fields=["status", "parent_decline_reason"])

    def activate(self):
        """Nakon uspješnog plaćanja — aktiviraj poklon i ažuriraj pretplatu roditelja."""
        from datetime import date, timedelta

        self.status = "active"
        self.paid_at = timezone.now()
        self.valid_from = date.today()

        if self.plan == "monthly":
            self.valid_until = date.today() + timedelta(days=30)
        elif self.plan == "yearly":
            self.valid_until = date.today() + timedelta(days=365)
        elif self.plan == "trial_3":
            self.valid_until = date.today() + timedelta(days=90)

        self.save(update_fields=["status", "paid_at", "valid_from", "valid_until"])

        # Ažuriraj plan roditelja
        parent = self.relationship.parent
        parent.plan = "monthly" if self.plan in ("monthly", "trial_3") else "yearly"
        parent.plan_started = timezone.now()
        from django.utils import timezone as tz
        import datetime

        parent.plan_expires = tz.now() + datetime.timedelta(
            days=30 if self.plan == "monthly" else 90 if self.plan == "trial_3" else 365
        )
        parent.save(update_fields=["plan", "plan_started", "plan_expires"])
