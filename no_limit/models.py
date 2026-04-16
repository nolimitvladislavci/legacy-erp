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
        ("approved", _("Odobreno")),
        ("declined", _("Odbijeno")),
        ("active", _("Aktivan ambasador")),
    ]

    full_name = models.CharField(max_length=200, verbose_name=_("Puno ime"))
    email = models.EmailField(verbose_name=_("Email"))
    phone = models.CharField(max_length=30, blank=True, verbose_name=_("Telefon"))
    country = models.CharField(max_length=5, choices=COUNTRY_CHOICES, verbose_name=_("Država"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("Grad"))
    organization = models.CharField(max_length=200, blank=True, verbose_name=_("Organizacija"))
    motivation = models.TextField(verbose_name=_("Motivacija"))
    languages = models.CharField(max_length=200, blank=True, verbose_name=_("Jezici"))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prijava ambasadora"
        verbose_name_plural = "Prijave ambasadora"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_country_display()}) — {self.get_status_display()}"
