"""
Fenix V3 — Pravni Modul | Blok 7 Master Plan
Jedinstven u EU: AI odvjetnik + bilježnik + punomoći + dispute tracker.
"""

import uuid

from core.base_model import TenantModel
from django.db import models
from django.utils import timezone

# ── 7.1 Ugovor / Digitalni Odvjetnik ─────────────────────────────────────────


class ContractTemplate(TenantModel):
    """Predlošci ugovora — AI popunjava iz varijabli."""

    TYPE_CHOICES = [
        ("employment", "Ugovor o radu"),
        ("service", "Ugovor o pružanju usluga"),
        ("sale", "Kupoprodajni ugovor"),
        ("nda", "Ugovor o čuvanju povjerljivosti (NDA)"),
        ("rent", "Ugovor o najmu"),
        ("freelance", "Autorski ugovor / honorar"),
        ("partnership", "Partnerski ugovor"),
        ("supply", "Ugovor o isporuci"),
        ("other", "Ostalo"),
    ]

    name = models.CharField(max_length=200, verbose_name="Naziv predloška")
    slug = models.SlugField(max_length=100, verbose_name="Slug")
    doc_type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name="Vrsta")
    body_html = models.TextField(verbose_name="Tijelo ugovora (HTML + varijable {{var}})")
    variables = models.JSONField(default=list, verbose_name="Varijable (lista)")
    # npr: ["stranka_1", "stranka_2", "datum_pocetka", "plaća", "radno_mjesto"]
    ai_prompt = models.TextField(blank=True, verbose_name="AI prompt za popunjavanje")
    is_active = models.BooleanField(default=True)
    language = models.CharField(
        max_length=5, default="hr", choices=[("hr", "Hrvatski"), ("de", "Deutsch"), ("en", "English")]
    )

    class Meta:
        verbose_name = "Predložak ugovora"
        verbose_name_plural = "Predlošci ugovora"
        unique_together = [("company", "slug")]
        ordering = ["doc_type", "name"]

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.name}"


class Contract(TenantModel):
    """Generirani ugovor — s digitalnim potpisom i arhivom."""

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_SIGNED = "signed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Nacrt"),
        (STATUS_SENT, "Poslan na potpis"),
        (STATUS_SIGNED, "Potpisan"),
        (STATUS_EXPIRED, "Istekao"),
        (STATUS_CANCELLED, "Otkazan"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ContractTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="contracts"
    )
    title = models.CharField(max_length=300, verbose_name="Naslov ugovora")
    doc_type = models.CharField(max_length=30, choices=ContractTemplate.TYPE_CHOICES, verbose_name="Vrsta")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Stranke
    party_a_name = models.CharField(max_length=200, verbose_name="Stranka A — naziv")
    party_a_oib = models.CharField(max_length=11, blank=True, verbose_name="OIB stranke A")
    party_a_address = models.TextField(blank=True, verbose_name="Adresa stranke A")
    party_b_name = models.CharField(max_length=200, verbose_name="Stranka B — naziv")
    party_b_oib = models.CharField(max_length=11, blank=True, verbose_name="OIB stranke B")
    party_b_address = models.TextField(blank=True, verbose_name="Adresa stranke B")

    # Sadržaj
    body_html = models.TextField(verbose_name="Tijelo ugovora (HTML)")
    variables_used = models.JSONField(default=dict, verbose_name="Vrijednosti varijabli")
    ai_generated = models.BooleanField(default=False, verbose_name="AI generiran")

    # Rok i potpis
    valid_from = models.DateField(null=True, blank=True, verbose_name="Na snazi od")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Na snazi do")
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name="Potpisan")
    signed_by = models.CharField(max_length=200, blank=True, verbose_name="Potpisao")

    # eValidacija / Bilježnik
    sha256_hash = models.CharField(max_length=64, blank=True, verbose_name="SHA-256 hash")
    notary_stamp = models.CharField(max_length=200, blank=True, verbose_name="Bilježnički pečat")
    notary_stamped_at = models.DateTimeField(null=True, blank=True)

    # PDF pohrana
    pdf_file = models.FileField(upload_to="legal/contracts/", blank=True, verbose_name="PDF")

    # Audit
    created_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="contracts_created"
    )

    class Meta:
        verbose_name = "Ugovor"
        verbose_name_plural = "Ugovori"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "valid_until"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_expiring_soon(self) -> bool:
        """Ističe unutar 30 dana."""
        if not self.valid_until:
            return False
        return (self.valid_until - timezone.now().date()).days <= 30


# ── 7.3 Punomoć ──────────────────────────────────────────────────────────────


class PowerOfAttorney(TenantModel):
    """Punomoć — kreiranje · potpis · rok · arhiva."""

    TYPE_CHOICES = [
        ("general", "Opća punomoć"),
        ("special", "Posebna punomoć"),
        ("court", "Sudska punomoć"),
        ("tax", "Porezna zastupnička punomoć"),
        ("property", "Punomoć za nekretnine"),
        ("banking", "Bankovna punomoć"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300, verbose_name="Naslov")
    poa_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Vrsta")

    # Opunomoćenik / vlastodavac
    principal_name = models.CharField(max_length=200, verbose_name="Vlastodavac")
    principal_oib = models.CharField(max_length=11, blank=True)
    agent_name = models.CharField(max_length=200, verbose_name="Opunomoćenik")
    agent_oib = models.CharField(max_length=11, blank=True)

    # Opseg ovlasti
    scope = models.TextField(verbose_name="Opseg ovlasti")
    restrictions = models.TextField(blank=True, verbose_name="Ograničenja")

    valid_from = models.DateField(verbose_name="Na snazi od")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Na snazi do")
    is_indefinite = models.BooleanField(default=False, verbose_name="Neodređeno")

    # Digitalni potpis
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.CharField(max_length=200, blank=True)
    sha256_hash = models.CharField(max_length=64, blank=True)
    pdf_file = models.FileField(upload_to="legal/poa/", blank=True)

    is_revoked = models.BooleanField(default=False, verbose_name="Opozvana")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Punomoć"
        verbose_name_plural = "Punomoći"
        ordering = ["-valid_from"]
        indexes = [
            models.Index(fields=["company", "is_revoked"]),
            models.Index(fields=["company", "valid_until"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.agent_name}"

    @property
    def is_active(self) -> bool:
        if self.is_revoked:
            return False
        if self.is_indefinite:
            return True
        if self.valid_until and timezone.now().date() > self.valid_until:
            return False
        return True


# ── 7.6 Sporovi / Dispute Log ────────────────────────────────────────────────


class Dispute(TenantModel):
    """Spor — rokovi · eskalacija · AI preporuka."""

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUS_ESCALATED = "escalated"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Otvoren"),
        (STATUS_IN_PROGRESS, "U tijeku"),
        (STATUS_RESOLVED, "Riješen"),
        (STATUS_ESCALATED, "Eskaliran"),
        (STATUS_CLOSED, "Zatvoren"),
    ]

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Nizak"),
        (PRIORITY_MEDIUM, "Srednji"),
        (PRIORITY_HIGH, "Visok"),
        (PRIORITY_URGENT, "Hitno"),
    ]

    TYPE_CHOICES = [
        ("payment", "Naplata potraživanja"),
        ("contract", "Ugovorni spor"),
        ("employment", "Radni spor"),
        ("property", "Imovinski spor"),
        ("tax", "Porezni spor"),
        ("regulatory", "Regulatorni / inspekcija"),
        ("customer", "Reklamacija kupca"),
        ("supplier", "Spor s dobavljačem"),
        ("other", "Ostalo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300, verbose_name="Naslov spora")
    dispute_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Vrsta")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    # Oponent
    opponent_name = models.CharField(max_length=200, verbose_name="Protustrana")
    opponent_oib = models.CharField(max_length=11, blank=True)
    opponent_contact = models.CharField(max_length=200, blank=True)

    # Iznos
    amount_claimed = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Traženi iznos (€)"
    )
    amount_settled = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Namireni iznos (€)"
    )

    # Rokovi
    deadline = models.DateField(null=True, blank=True, verbose_name="Rok za odgovor")
    court_date = models.DateField(null=True, blank=True, verbose_name="Datum ročišta")
    opened_at = models.DateField(default=timezone.now, verbose_name="Datum otvaranja")
    closed_at = models.DateTimeField(null=True, blank=True)

    # Opis i AI
    description = models.TextField(verbose_name="Opis spora")
    ai_recommendation = models.TextField(blank=True, verbose_name="AI preporuka")
    ai_risk_score = models.IntegerField(null=True, blank=True, verbose_name="AI rizik (0-100)")

    # Veze
    related_contract = models.ForeignKey(
        Contract, null=True, blank=True, on_delete=models.SET_NULL, related_name="disputes"
    )
    assigned_to = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="disputes_assigned"
    )

    class Meta:
        verbose_name = "Spor"
        verbose_name_plural = "Sporovi"
        ordering = ["-priority", "deadline"]
        indexes = [
            models.Index(fields=["company", "status", "priority"]),
            models.Index(fields=["company", "deadline"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        return self.deadline < timezone.now().date() and self.status not in (self.STATUS_RESOLVED, self.STATUS_CLOSED)


class DisputeEvent(models.Model):
    """Kronologija događaja u sporu — audit trail."""

    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(
        max_length=50,
        choices=[
            ("note", "Bilješka"),
            ("status_change", "Promjena statusa"),
            ("document", "Dokument dodan"),
            ("court", "Ročište"),
            ("escalation", "Eskalacija"),
            ("ai_analysis", "AI analiza"),
            ("resolution", "Rješenje"),
        ],
    )
    description = models.TextField()
    created_by = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(upload_to="legal/dispute_events/", blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Događaj u sporu"
        verbose_name_plural = "Događaji u sporovima"
