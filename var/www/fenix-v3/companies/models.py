"""
Fenix v3 — Company Model | 13/10

Temelj tenant isolation sustava.
Svaka firma, svaki obrt, svaki ured.
Umbrella logika: parent → children (1 ured, 80 firmi, 1 klik).

Iz starog sustava prenosimo:
- OIB validacija (Luhn-10, ISO 7064)
- Umbrella parent/child hijerarhija
- Multi-domain support (memio.farm, memio.pet, memio.world)
- Fiscalizacija config per-company
"""
from django.db import models
from django.core.exceptions import ValidationError
from core.base_model import BaseModel


def validate_oib(value):
    """
    OIB validacija — ISO 7064, MOD 11,10.
    Identična logika iz starog sustava.
    Hard-stop: neispravan OIB = nema firme.
    """
    if not value:
        return

    if len(value) != 11 or not value.isdigit():
        raise ValidationError("OIB mora imati točno 11 znamenki.")

    remainder = 10
    for digit in value[:10]:
        remainder = (remainder + int(digit)) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11

    check = 11 - remainder
    if check == 10:
        check = 0

    if check != int(value[10]):
        raise ValidationError("OIB nije valjan (kontrolna znamenka).")


class Company(BaseModel):
    """
    Tvrtka / Obrt / Ured.
    Svaki tenant u sustavu. Umbrella za multi-company.
    """
    # ── Osnovni podaci ────────────────────────
    name = models.CharField(
        max_length=255,
        verbose_name="Naziv tvrtke",
        help_text="Puni naziv kako je upisan u sudski registar"
    )
    short_name = models.CharField(
        max_length=50, blank=True,
        verbose_name="Kratki naziv",
        help_text="Za prikaz u UI (sidebar, breadcrumbs)"
    )
    oib = models.CharField(
        max_length=11, unique=True,
        validators=[validate_oib],
        verbose_name="OIB",
        help_text="Osobni identifikacijski broj — 11 znamenki"
    )

    # ── Adresa ────────────────────────────────
    address = models.CharField(max_length=255, blank=True, verbose_name="Adresa")
    city = models.CharField(max_length=100, blank=True, verbose_name="Grad")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Poštanski broj")
    country = models.CharField(max_length=2, default="HR", verbose_name="Država (ISO)")

    # ── Kontakt ───────────────────────────────
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")
    website = models.URLField(blank=True, verbose_name="Web stranica")

    # ── Umbrella (parent/child) ───────────────
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        verbose_name="Matična tvrtka",
        help_text="Za umbrella ured koji upravlja više firmi"
    )

    # ── Fiscalizacija ─────────────────────────
    fiscalization_enabled = models.BooleanField(
        default=False,
        verbose_name="Fiskalizacija aktivna"
    )
    fiscalization_cert = models.TextField(
        blank=True,
        verbose_name="FINA certifikat (PEM)",
        help_text="Certifikat za potpisivanje fiskalnih računa"
    )
    fiscalization_password = models.CharField(
        max_length=255, blank=True,
        verbose_name="Lozinka certifikata"
    )

    # ── Domain & Branding ─────────────────────
    domain = models.CharField(
        max_length=100, blank=True,
        verbose_name="Domena",
        help_text="Za domain gate: memio.farm, memio.pet, etc."
    )
    logo = models.ImageField(
        upload_to="companies/logos/",
        blank=True,
        verbose_name="Logo"
    )
    primary_color = models.CharField(
        max_length=7, default="#C9A84C",
        verbose_name="Primarna boja"
    )

    # ── Postavke ──────────────────────────────
    language = models.CharField(
        max_length=2, default="hr",
        choices=[("hr", "Hrvatski"), ("de", "Deutsch"), ("en", "English")],
        verbose_name="Jezik"
    )
    timezone = models.CharField(
        max_length=50, default="Europe/Zagreb",
        verbose_name="Vremenska zona"
    )
    currency = models.CharField(
        max_length=3, default="EUR",
        verbose_name="Valuta"
    )

    # ── AI & Integracije ──────────────────────
    ai_enabled = models.BooleanField(
        default=True,
        verbose_name="AI asistent aktivan"
    )
    whatsapp_enabled = models.BooleanField(
        default=False,
        verbose_name="WhatsApp integracija"
    )
    whatsapp_number = models.CharField(
        max_length=30, blank=True,
        verbose_name="WhatsApp broj"
    )

    class Meta:
        verbose_name = "Tvrtka"
        verbose_name_plural = "Tvrtke"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["oib"]),
            models.Index(fields=["domain"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        return self.short_name or self.name

    def clean(self):
        super().clean()
        if self.parent and self.parent == self:
            raise ValidationError("Tvrtka ne može biti sama sebi matična.")

    @property
    def is_umbrella(self):
        return self.children.filter(is_deleted=False).exists()

    @property
    def display_name(self):
        return self.short_name or self.name

    def get_all_children(self):
        """Rekurzivno dohvati sve child firme (umbrella)."""
        children = list(self.children.filter(is_deleted=False))
        all_children = list(children)
        for child in children:
            all_children.extend(child.get_all_children())
        return all_children

    def to_ai_context(self):
        ctx = super().to_ai_context()
        ctx.update({
            "name": self.name,
            "oib": self.oib,
            "country": self.country,
            "language": self.language,
            "is_umbrella": self.is_umbrella,
            "fiscalization": self.fiscalization_enabled,
        })
        return ctx
