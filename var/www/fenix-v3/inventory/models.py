"""
inventory/models.py — Inventar / Zalihe.
Fenix V3 port iz fina-connect/inventory/models.py.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.base_model import TenantModel


class InventoryItem(TenantModel):
    """Artikl / Proizvod / Usluga — za Synesis import i inventory management."""

    name = models.CharField(max_length=200, verbose_name=_("Naziv"))
    sku = models.CharField(max_length=50, blank=True, verbose_name="SKU / Šifra")
    barcode = models.CharField(max_length=50, blank=True, verbose_name="Barkod")
    unit = models.CharField(max_length=20, blank=True, default="kom", verbose_name=_("Jedinica mjere"))

    unit_price = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name=_("Prodajna cijena"))
    purchase_price = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name=_("Nabavna cijena"))

    # PDV — decimal (25.00, 13.00, 5.00, 0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_("Stopa PDV-a (%)"))

    description = models.TextField(blank=True, verbose_name=_("Opis"))
    is_active = models.BooleanField(default=True, verbose_name=_("Aktivan"))

    class Meta:
        verbose_name = _("Artikl")
        verbose_name_plural = _("Artikli")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "sku"]),
            models.Index(fields=["company", "barcode"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku or '—'})"
