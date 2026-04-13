"""
lovacki/models.py — Lovački modul za evidenciju divljači.
Zakon o lovstvu (NN 99/2018): obvezna evidencija odstrjela.
CITES: međunarodni certifikat za zaštićene vrste.
"""

from django.conf import settings
from django.db import models

from core.managers import CompanyManager


class HuntingGround(models.Model):
    """Lovište — svaka lovačka udruga upravlja jednim ili više lovišta."""

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="hunting_grounds")
    objects = CompanyManager()

    name = models.CharField(max_length=200, verbose_name="Naziv lovišta")
    code = models.CharField(max_length=30, blank=True, verbose_name="Šifra lovišta")
    area_ha = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Površina (ha)")
    county = models.CharField(max_length=100, blank=True, verbose_name="Županija")
    municipality = models.CharField(max_length=100, blank=True, verbose_name="Općina")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Lovište"
        verbose_name_plural = "Lovišta"

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class GameSpecies(models.Model):
    """Vrsta divljači — referentna tablica."""

    CATEGORY_CHOICES = [
        ("krupna", "Krupna divljač"),
        ("sitna", "Sitna divljač"),
        ("pernata", "Pernata divljač"),
    ]

    name = models.CharField(max_length=100, verbose_name="Naziv (HR)")
    name_latin = models.CharField(max_length=100, blank=True, verbose_name="Latinski naziv")
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="krupna")
    is_cites = models.BooleanField(default=False, verbose_name="CITES zaštićena")
    hunting_season_start = models.CharField(max_length=10, blank=True, verbose_name="Sezona od (dd.mm.)")
    hunting_season_end = models.CharField(max_length=10, blank=True, verbose_name="Sezona do (dd.mm.)")
    barf_compatible = models.BooleanField(default=False, verbose_name="BARF kompatibilna")

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Vrsta divljači"
        verbose_name_plural = "Vrste divljači"

    def __str__(self):
        cites = " [CITES]" if self.is_cites else ""
        return f"{self.name} ({self.name_latin}){cites}"


class HuntingQuota(models.Model):
    """Godišnji plan gospodarenja — kvota po vrsti za lovište."""

    ground = models.ForeignKey(HuntingGround, on_delete=models.CASCADE, related_name="quotas")
    species = models.ForeignKey(GameSpecies, on_delete=models.CASCADE, related_name="quotas")
    year = models.PositiveIntegerField(verbose_name="Lovna godina")
    planned_count = models.PositiveIntegerField(default=0, verbose_name="Planirani odstrjel")
    realized_count = models.PositiveIntegerField(default=0, verbose_name="Realizirani odstrjel", editable=False)

    class Meta:
        unique_together = [("ground", "species", "year")]
        ordering = ["-year", "species__name"]
        verbose_name = "Lovna kvota"
        verbose_name_plural = "Lovne kvote"

    def __str__(self):
        return f"{self.species.name} {self.year}: {self.realized_count}/{self.planned_count}"

    @property
    def utilization_pct(self):
        if self.planned_count == 0:
            return 0
        return int(self.realized_count / self.planned_count * 100)

    @property
    def remaining(self):
        return max(0, self.planned_count - self.realized_count)


class HuntRecord(models.Model):
    """Evidencija odstrjela — zakonska obveza (čl. 62 Zakona o lovstvu)."""

    SPOL_CHOICES = [
        ("M", "Mužjak"),
        ("F", "Ženka"),
        ("N", "Nepoznato"),
    ]

    ground = models.ForeignKey(HuntingGround, on_delete=models.CASCADE, related_name="hunt_records")
    species = models.ForeignKey(GameSpecies, on_delete=models.CASCADE, related_name="hunt_records")
    hunter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hunt_records"
    )

    datum = models.DateField(verbose_name="Datum odstrjela")
    lokacija = models.CharField(max_length=200, blank=True, verbose_name="Lokacija (opis)")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    spol = models.CharField(max_length=1, choices=SPOL_CHOICES, default="N")
    weight_kg = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True, verbose_name="Težina (kg)")
    age_years = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Starost (god)")
    trophy_points = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="CIC bodovi (trofej)"
    )

    # CITES dokumentacija
    cites_number = models.CharField(max_length=50, blank=True, verbose_name="CITES broj")
    cites_issued = models.DateField(null=True, blank=True, verbose_name="CITES izdan")

    # BARF automatsko stvaranje ponude
    barf_listed = models.BooleanField(default=False, verbose_name="Objavljeno na BARF")
    meat_available_kg = models.DecimalField(
        max_digits=7, decimal_places=1, null=True, blank=True, verbose_name="Dostupno mesa (kg)"
    )

    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to="hunting/records/%Y/", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-datum"]
        verbose_name = "Evidencija odstrjela"
        verbose_name_plural = "Evidencije odstrjela"

    def __str__(self):
        return f"{self.species.name} — {self.datum} ({self.ground.name})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-update quota
        quota = HuntingQuota.objects.filter(ground=self.ground, species=self.species, year=self.datum.year).first()
        if quota:
            quota.realized_count = HuntRecord.objects.filter(
                ground=self.ground, species=self.species, datum__year=self.datum.year
            ).count()
            quota.save(update_fields=["realized_count"])
