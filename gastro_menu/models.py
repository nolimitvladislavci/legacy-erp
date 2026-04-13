"""
gastro_menu/models.py - Digitalni meni za restorane

Gost skenira QR kod na stolu → vidi meni s porijeklom namirnica.
Opcionalno naručivanje s mobitela.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class DigitalMenu(models.Model):
    """Digitalni meni restorana."""

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="digital_menus", verbose_name=_("Restoran")
    )
    name = models.CharField(max_length=100, default="Glavni meni", verbose_name=_("Naziv menija"))
    is_active = models.BooleanField(default=True)

    # Dizajn
    logo = models.ImageField(upload_to="gastro/menus/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="gastro/menus/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#c9a84c", verbose_name=_("Primarna boja"))

    # Javni pristup
    slug = models.SlugField(unique=True)
    public_url = models.URLField(blank=True)
    qr_code_image = models.ImageField(upload_to="gastro/qr/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _("Digitalni meni")
        verbose_name_plural = _("Digitalni meniji")

    def __str__(self):
        return f"{self.name} — {self.company.name}"

    def save(self, *args, **kwargs):
        if not self.public_url:
            self.public_url = f"https://meni.limit-connect.com/{self.slug}/"
        super().save(*args, **kwargs)


class MenuCategory(models.Model):
    """Kategorija jela na meniju (Predjela, Glavna jela, Deserti...)"""

    menu = models.ForeignKey(DigitalMenu, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100, verbose_name=_("Naziv"))
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Kategorija menija")
        verbose_name_plural = _("Kategorije menija")
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """Jelo na meniju."""

    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200, verbose_name=_("Naziv jela"))
    description = models.TextField(blank=True, verbose_name=_("Opis"))
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_("Cijena"))
    image = models.ImageField(upload_to="gastro/items/", blank=True, null=True)

    # Alergeni i dijete
    allergens = models.JSONField(default=list, blank=True, verbose_name=_("Alergeni"))
    is_vegetarian = models.BooleanField(default=False, verbose_name=_("Vegetarijansko"))
    is_vegan = models.BooleanField(default=False, verbose_name=_("Vegansko"))
    is_gluten_free = models.BooleanField(default=False, verbose_name=_("Bez glutena"))

    is_available = models.BooleanField(default=True, verbose_name=_("Dostupno"))
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Jelo")
        verbose_name_plural = _("Jela")
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.name} — {self.price}€"


class MenuItemIngredient(models.Model):
    """Namirnica u jelu - s vezom na marketplace proizvod za traceability."""

    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="ingredients")
    marketplace_product = models.ForeignKey(
        "marketplace.MarketplaceProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="used_in_dishes",
        verbose_name=_("Proizvod s tržnice"),
    )
    name = models.CharField(max_length=100, verbose_name=_("Naziv namirnice"))
    origin = models.CharField(max_length=200, blank=True, verbose_name=_("Porijeklo"))
    is_highlighted = models.BooleanField(default=False, verbose_name=_("Prikaži na meniju"))
    trace = models.ForeignKey(
        "traceability.ProductTrace", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Trag proizvoda")
    )

    class Meta:
        verbose_name = _("Namirnica jela")
        verbose_name_plural = _("Namirnice jela")

    def __str__(self):
        return f"{self.name} ({self.origin})"


class TableQR(models.Model):
    """QR kod za stol u restoranu."""

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="table_qrs", verbose_name=_("Restoran")
    )
    menu = models.ForeignKey(DigitalMenu, on_delete=models.CASCADE, related_name="tables")
    table_number = models.CharField(max_length=20, verbose_name=_("Broj stola"))
    table_zone = models.CharField(max_length=50, blank=True, verbose_name=_("Zona"))
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True)
    qr_image = models.ImageField(upload_to="gastro/table_qr/", blank=True, null=True)
    ordering_enabled = models.BooleanField(default=False, verbose_name=_("Naručivanje s mobitela"))
    objects = CompanyManager()

    class Meta:
        verbose_name = _("QR stola")
        verbose_name_plural = _("QR stolova")
        unique_together = ["company", "table_number"]

    def __str__(self):
        return f"Stol {self.table_number} — {self.company.name}"


class TableOrder(models.Model):
    """Narudžba sa stola putem QR-a."""

    STATUS_CHOICES = [
        ("new", _("Nova")),
        ("accepted", _("Prihvaćena")),
        ("preparing", _("U pripremi")),
        ("ready", _("Spremno")),
        ("served", _("Servirano")),
        ("paid", _("Plaćeno")),
    ]

    table_qr = models.ForeignKey(TableQR, on_delete=models.CASCADE, related_name="orders")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    items = models.JSONField(default=list, verbose_name=_("Stavke"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Veza na POS
    pos_receipt = models.ForeignKey(
        "pos.POSReceipt", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("POS račun")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _("Narudžba sa stola")
        verbose_name_plural = _("Narudžbe sa stola")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Stol {self.table_qr.table_number} — {self.get_status_display()}"
