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
