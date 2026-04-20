"""
partners/models.py — Poslovni kontakti (kupci, dobavljači, partneri).
Fenix V3 port iz fina-connect/partners/models.py.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.base_model import TenantModel


class Partner(TenantModel):
    TYPE_CHOICES = [
        ("client", _("Klijent (Kupac)")),
        ("supplier", _("Dobavljač")),
        ("both", _("Partner (Oboje)")),
        ("employee", _("Zaposlenik")),
    ]

    # Osnovni podaci
    name = models.CharField(max_length=200, verbose_name=_("Naziv / Ime"))
    oib = models.CharField(max_length=30, blank=True, verbose_name=_("OIB / Steuer-Nr."))

    # Lokacija
    address = models.CharField(max_length=255, blank=True, verbose_name=_("Ulica i broj"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("Grad"))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_("Poštanski broj"))
    country = models.CharField(max_length=50, blank=True, default="Hrvatska", verbose_name=_("Država"))

    # Kontakt
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Telefon"))
    web = models.CharField(max_length=200, blank=True, verbose_name=_("Web stranica"))

    # Tip i uvjeti
    partner_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default="client", verbose_name=_("Tip partnera")
    )
    payment_term = models.IntegerField(default=0, verbose_name=_("Rok plaćanja (dana)"))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_("Rabat (%)"))

    # PDV
    is_vat_registered = models.BooleanField(default=False, verbose_name=_("U sustavu PDV-a"))
    vat_id = models.CharField(max_length=20, blank=True, verbose_name=_("PDV ID"))

    # Bankovni podaci
    iban = models.CharField(max_length=34, blank=True, verbose_name="IBAN")
    swift = models.CharField(max_length=11, blank=True, verbose_name="SWIFT / BIC")

    # Portal token (za klijentski pristup bez lozinke)
    portal_token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    notes = models.TextField(blank=True, verbose_name=_("Interne napomene"))
    is_active = models.BooleanField(default=True, verbose_name=_("Aktivan"))

    class Meta:
        verbose_name = _("Partner")
        verbose_name_plural = _("Partneri")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "oib"]),
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "partner_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.city or 'N/A'})"
