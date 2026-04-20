from django.db import models
from django.utils.translation import gettext_lazy as _


class AzilPrijava(models.Model):
    naziv = models.CharField(max_length=200, verbose_name="Naziv azila/udruge")
    email = models.EmailField(verbose_name="Email kontakt")
    grad = models.CharField(max_length=100)
    poruka = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    contacted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Prijava azila"
        verbose_name_plural = "Prijave azila"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.naziv} ({self.grad})"


class AmbassadorApplication(models.Model):
    """Prijava za ambasadorsku ulogu u EU zemlji."""

    COUNTRY_CHOICES = [
        ("HR", "Hrvatska"),
        ("DE", "Njemačka"),
        ("AT", "Austrija"),
        ("SI", "Slovenija"),
        ("IT", "Italija"),
        ("HU", "Mađarska"),
        ("CZ", "Češka"),
        ("SK", "Slovačka"),
        ("PL", "Poljska"),
        ("FR", "Francuska"),
        ("NL", "Nizozemska"),
        ("BE", "Belgija"),
        ("SE", "Švedska"),
        ("OTHER", "Ostalo"),
    ]
    STATUS_CHOICES = [
        ("pending", _("Na čekanju")),
        ("review", _("U pregledu")),
        ("approved", _("Odobreno")),
        ("declined", _("Odbijeno")),
        ("active", _("Aktivan ambasador")),
    ]
    ROLE_CHOICES = [
        ("national_coordinator", _("Nacionalni koordinator")),
        ("regional_ambassador", _("Regionalni ambasador")),
        ("institutional_partner", _("Institucionalni partner")),
        ("sponsor", _("Sponzor / Pokrovitelj")),
    ]

    # Osobni podaci
    full_name = models.CharField(max_length=200, verbose_name=_("Puno ime"))
    email = models.EmailField(verbose_name=_("Email"))
    phone = models.CharField(max_length=30, blank=True, verbose_name=_("Telefon"))
    country = models.CharField(max_length=5, choices=COUNTRY_CHOICES, verbose_name=_("Država"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("Grad"))

    # Organizacija
    organization = models.CharField(max_length=200, blank=True, verbose_name=_("Naziv organizacije"))
    organization_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Vrsta organizacije (škola, knjižnica, udruga...)"),
    )

    # Uloga i motivacija
    desired_role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="national_coordinator",
        verbose_name=_("Željena uloga"),
    )
    motivation = models.TextField(verbose_name=_("Motivacija"))
    experience = models.TextField(
        blank=True,
        verbose_name=_("Relevantno iskustvo (pedagoško, digitalno, EU projekti)"),
    )
    languages = models.CharField(max_length=200, blank=True, verbose_name=_("Jezici"))

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.CharField(max_length=100, blank=True, verbose_name=_("Pregledao"))
    review_notes = models.TextField(blank=True, verbose_name=_("Bilješke pregleda"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Datum odobravanja"))

    class Meta:
        verbose_name = "Prijava ambasadora"
        verbose_name_plural = "Prijave ambasadora"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_country_display()}) — {self.get_status_display()}"


class CountryChapter(models.Model):
    """Nacionalni ogranak No-limit udruge."""

    country = models.CharField(max_length=5, unique=True, verbose_name=_("Država (ISO)"))
    country_name = models.CharField(max_length=100, verbose_name=_("Naziv države"))
    coordinator_name = models.CharField(max_length=200, blank=True, verbose_name=_("Koordinator"))
    coordinator_email = models.EmailField(blank=True, verbose_name=_("Email koordinatora"))

    is_active = models.BooleanField(default=False, verbose_name=_("Aktivan"))
    launch_date = models.DateField(null=True, blank=True, verbose_name=_("Datum pokretanja"))

    ambassador_count = models.IntegerField(default=0, verbose_name=_("Broj ambasadora"))
    user_count = models.IntegerField(default=0, verbose_name=_("Broj korisnika"))

    local_description = models.TextField(blank=True, verbose_name=_("Opis projekta na lokalnom jeziku"))
    grant_applications = models.TextField(blank=True, verbose_name=_("EU grant prijave za ovu zemlju"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nacionalni ogranak"
        verbose_name_plural = "Nacionalni ogranci"
        ordering = ["country_name"]

    def __str__(self):
        status = "✓" if self.is_active else "○"
        return f"{status} No-limit {self.country_name}"


class PartnershipLead(models.Model):
    """CRM za potencijalne partnere i sponzore."""

    STATUS_CHOICES = [
        ("new", _("Novi")),
        ("contacted", _("Kontaktiran")),
        ("negotiating", _("U pregovorima")),
        ("signed", _("Potpisano")),
        ("declined", _("Odbijeno")),
        ("inactive", _("Neaktivan")),
    ]
    TYPE_CHOICES = [
        ("sponsor", _("Sponzor")),
        ("partner", _("Partner")),
        ("eu_applicant", _("EU ko-aplikant")),
        ("letter_of_support", _("Letter of Support")),
    ]

    name = models.CharField(max_length=200, verbose_name=_("Ime kontakta"))
    organization = models.CharField(max_length=200, blank=True, verbose_name=_("Organizacija"))
    country = models.CharField(max_length=5, blank=True, verbose_name=_("Država"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    phone = models.CharField(max_length=30, blank=True, verbose_name=_("Telefon"))

    partnership_type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name=_("Tip partnerstva"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", verbose_name=_("Status"))

    notes = models.TextField(blank=True, verbose_name=_("Bilješke"))
    potential_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Potencijalna vrijednost (€)"),
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Izvor (WA, email, preporuka...)"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Partnership lead"
        verbose_name_plural = "Partnership leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_partnership_type_display()}) — {self.get_status_display()}"


# ══════════════════════════════════════════════════════════════════════════════
#  NO LIMIT TERMINI — Personalni kontakt sustav
#  Fizički susret / Video poziv / Telefonski poziv
# ══════════════════════════════════════════════════════════════════════════════
import secrets
import string as _string


def _generate_room_token():
    """8-znakovna velika slova+znamenke, URL-safe za Jitsi room."""
    alphabet = _string.ascii_uppercase + _string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


class NoLimitMeeting(models.Model):
    """Zahtjev za osobnim kontaktom s vodstvom NO LIMIT udruge."""

    TYPE_PHYSICAL = "physical"
    TYPE_ONLINE = "online"
    TYPE_PHONE = "phone"
    MEETING_TYPES = [
        (TYPE_PHYSICAL, "Fizički posjet — sjedište udruge"),
        (TYPE_ONLINE, "Video poziv (Jitsi Meet)"),
        (TYPE_PHONE, "Telefonski poziv"),
    ]

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Na čekanju"),
        (STATUS_CONFIRMED, "Potvrđeno"),
        (STATUS_COMPLETED, "Završeno"),
        (STATUS_CANCELLED, "Otkazano"),
    ]

    COUNTRY_CHOICES = [
        ("HR", "Hrvatska"),
        ("DE", "Njemačka"),
        ("AT", "Austrija"),
        ("SI", "Slovenija"),
        ("IT", "Italija"),
        ("CH", "Švicarska"),
        ("NL", "Nizozemska"),
        ("BE", "Belgija"),
        ("FR", "Francuska"),
        ("SE", "Švedska"),
        ("CZ", "Češka"),
        ("SK", "Slovačka"),
        ("PL", "Poljska"),
        ("HU", "Mađarska"),
        ("US", "SAD"),
        ("GB", "Ujedinjeno Kraljevstvo"),
        ("OTHER", "Ostalo"),
    ]

    # ── Podaci o posjetitelju ────────────────────────────────────────────────
    full_name = models.CharField(max_length=200, verbose_name="Puno ime")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=40, blank=True, verbose_name="Telefon / WhatsApp")
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, default="HR", verbose_name="Država")
    city = models.CharField(max_length=100, blank=True, verbose_name="Grad")
    organization = models.CharField(max_length=200, blank=True, verbose_name="Organizacija / Institucija")
    timezone_name = models.CharField(max_length=60, default="Europe/Zagreb", verbose_name="Vremenska zona")

    # ── Termin ───────────────────────────────────────────────────────────────
    meeting_type = models.CharField(
        max_length=20, choices=MEETING_TYPES, default=TYPE_ONLINE, verbose_name="Vrsta kontakta"
    )
    preferred_date = models.DateField(verbose_name="Željeni datum")
    preferred_time = models.TimeField(verbose_name="Željeno vrijeme (sjedište CET/CEST)")
    topic = models.TextField(verbose_name="Tema razgovora")
    duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        choices=[(15, "15 min"), (30, "30 min"), (60, "60 min"), (90, "90 min")],
        verbose_name="Očekivano trajanje",
    )

    # ── Status i upravljanje (popunjava admin) ───────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Status")
    confirmed_datetime = models.DateTimeField(null=True, blank=True, verbose_name="Potvrđeni datum/sat")
    admin_notes = models.TextField(blank=True, verbose_name="Admin bilješke (interno)")
    jitsi_room = models.CharField(max_length=60, blank=True, verbose_name="Jitsi soba (auto)")
    secure_token = models.CharField(max_length=64, blank=True, verbose_name="Sigurni token (link za posjetitelja)")

    # ── Notifikacije ─────────────────────────────────────────────────────────
    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Termin — No Limit"
        verbose_name_plural = "Termini — No Limit"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["preferred_date"]),
        ]

    def __str__(self):
        return f"{self.full_name} | {self.get_meeting_type_display()} | {self.preferred_date} {self.preferred_time}"

    def save(self, *args, **kwargs):
        if not self.secure_token:
            self.secure_token = secrets.token_urlsafe(32)
        if self.meeting_type == self.TYPE_ONLINE and not self.jitsi_room:
            self.jitsi_room = f"nolimit-{_generate_room_token()}"
        super().save(*args, **kwargs)

    @property
    def jitsi_url(self):
        if self.jitsi_room:
            return f"https://meet.jit.si/{self.jitsi_room}"
        return ""

    @property
    def is_online(self):
        return self.meeting_type == self.TYPE_ONLINE

    @property
    def visitor_portal_url(self):
        return f"/no-limit/termin/status/{self.secure_token}/"


class MeetingActivityLog(models.Model):
    """Svaka interakcija oko termina — bilježi komunikaciju i promjene."""

    EVENT_SUBMITTED = "submitted"
    EVENT_CONFIRMED = "confirmed"
    EVENT_CANCELLED = "cancelled"
    EVENT_COMPLETED = "completed"
    EVENT_NOTE = "note"
    EVENT_REMINDER = "reminder"
    EVENT_CALL_START = "call_started"
    EVENT_TYPES = [
        (EVENT_SUBMITTED, "Zahtjev poslan"),
        (EVENT_CONFIRMED, "Termin potvrđen"),
        (EVENT_CANCELLED, "Otkazano"),
        (EVENT_COMPLETED, "Razgovor završen"),
        (EVENT_NOTE, "Bilješka"),
        (EVENT_REMINDER, "Podsjetnik poslan"),
        (EVENT_CALL_START, "Poziv počeo"),
    ]

    meeting = models.ForeignKey(NoLimitMeeting, on_delete=models.CASCADE, related_name="activity_log")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    actor = models.CharField(max_length=100, default="sustav")  # "admin", "Ivan Brtan", "posjetitelj", "sustav"
    content = models.TextField(blank=True)
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ts"]
        verbose_name = "Aktivnost termina"

    def __str__(self):
        return f"{self.meeting} — {self.event_type} @ {self.ts.strftime('%d.%m. %H:%M')}"
