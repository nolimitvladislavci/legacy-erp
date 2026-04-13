"""
livestock/models.py
Evidencija goveda za OPG. Prati: grlo, zdravlje, mlijeko,
plan ishrane, parcele, usjeve i put prema bio certifikaciji.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import CompanyManager


class Livestock(models.Model):
    """Jedno grlo -- krava, junica, tele, bik."""

    VRSTA_CHOICES = [
        ("krava", "Krava (muzara)"),
        ("junica", "Junica"),
        ("tele", "Tele"),
        ("bik", "Bik"),
        ("vo", "Vo (tov)"),
        # Ovce i koze
        ("ovca", "Ovca"),
        ("janje", "Janje"),
        ("ovan", "Ovan"),
        ("koza", "Koza"),
        ("kozle", "Kozle"),
        ("jarac", "Jarac"),
        # Svinje
        ("svinja", "Svinja"),
        ("prasac", "Prasac"),
        ("krmaca", "Krmača"),
        ("nerast", "Nerast"),
        # Perad
        ("kokoska", "Kokoška / Peradar"),
        ("purica", "Purica"),
        ("patka", "Patka"),
        ("guska", "Guska"),
        # Kućni ljubimci / uzgajivači
        ("pas", "Pas"),
        ("macka", "Mačka"),
        ("konj", "Konj"),
        ("zec", "Zec"),
        ("ostalo_ljubimac", "Ostalo (ljubimac)"),
    ]
    PET_VRSTE = ("pas", "macka", "konj", "zec", "ostalo_ljubimac")
    SPOL_CHOICES = [("M", "Mužjak"), ("F", "Ženka"), ("N", "Nepoznato")]
    STATUS_CHOICES = [
        ("aktivno", "Aktivno"),
        ("gravidno", "Gravidno"),
        ("zasuseno", "Zasuseno"),
        ("tov", "U tovu"),
        ("prodano", "Prodano"),
        ("uginulo", "Uginulo"),
        ("izluceno", "Izluceno"),
        # Azilski statusi
        ("u_azilu", "U azilu"),
        ("karantena", "Karantena"),
        ("rezerviran", "Rezerviran"),
        ("udomljen", "Udomljen"),
        ("eutanaziran", "Eutanaziran"),
    ]
    SHELTER_STATUSES = ("u_azilu", "karantena", "rezerviran", "udomljen", "eutanaziran")

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="livestock", verbose_name="OPG"
    )
    ear_tag = models.CharField(
        max_length=20, verbose_name="Broj usne markice", help_text="HR format: HR + OIB + redni br", db_index=True
    )
    name = models.CharField(max_length=50, blank=True, verbose_name="Ime (opcionalno)")
    vrsta = models.CharField(max_length=15, choices=VRSTA_CHOICES, default="krava")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="aktivno")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Datum rodjenja")
    breed = models.CharField(
        max_length=50, blank=True, verbose_name="Pasmina", help_text="npr. Simentalac, Holstein, Siva"
    )
    weight_kg = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True, verbose_name="Tezina (kg)")
    avg_daily_milk_l = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Prosj. dnevna mlijecnost (L)"
    )
    last_calving = models.DateField(null=True, blank=True, verbose_name="Zadnje teljenje")
    expected_calving = models.DateField(null=True, blank=True, verbose_name="Ocekivano teljenje")
    is_organic = models.BooleanField(default=False, verbose_name="Ekoloski uzgoj")
    organic_since = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # ── Polja za kućne ljubimce / uzgajivače ──────────────────────────
    chip_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Broj mikrocipa / transpondera",
        help_text="ISO 11784/85, 134.2 kHz. Ovce: bolus. Konji: vrat lijevo.",
    )

    # ── Zakonska identifikacija ──────────────────────────────────────
    ID_METHOD_CHOICES = [
        ("ear_tag", "Usna markica"),
        ("ear_tag_2", "Usna markica (obje usi)"),
        ("bolus", "Bolus transponder (zeludac)"),
        ("ear_chip", "Elektronska usna markica"),
        ("implant", "Mikrocip (implant — konji)"),
        ("tattoo", "Tetoviranje (svinje)"),
        ("ring", "Nozni prsten (perad)"),
    ]
    id_method = models.CharField(
        max_length=15, choices=ID_METHOD_CHOICES, default="ear_tag", verbose_name="Metoda identifikacije"
    )
    ear_tag_left = models.CharField(
        max_length=20, blank=True, verbose_name="Markica lijevo uho", help_text="Goveda: ista oznaka u oba uha"
    )
    ear_tag_right = models.CharField(max_length=20, blank=True, verbose_name="Markica desno uho")
    ear_tag_color = models.CharField(
        max_length=10,
        blank=True,
        choices=[("yellow", "Zuta (goveda/ovce)"), ("red", "Crvena (koze)"), ("white", "Bijela")],
        verbose_name="Boja markice",
    )
    passport_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Broj putovnice (konji)",
        help_text="UELN 15-znamenkasti ili HR putovnica kopitara",
    )
    jibg_farm = models.ForeignKey(
        "livestock.FarmIdentification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="animals",
        verbose_name="Gospodarstvo (JIBG)",
    )

    # Datumi evidencije
    marked_at = models.DateField(
        null=True, blank=True, verbose_name="Datum oznacavanja", help_text="Ovce: unutar 9 mjeseci od rodenja"
    )
    registered_in_jrdz = models.BooleanField(default=False, verbose_name="Evidentirano u JRDZ")
    jrdz_registered_at = models.DateField(null=True, blank=True)
    pedigree_number = models.CharField(max_length=50, blank=True, verbose_name="Broj rodovnice")
    spol = models.CharField(
        max_length=1, choices=[("M", "Mužjak"), ("F", "Ženka"), ("N", "Nepoznato")], default="N", blank=True
    )
    color_description = models.CharField(max_length=120, blank=True, verbose_name="Opis boje/šare")
    father_name = models.CharField(max_length=80, blank=True, verbose_name="Otac (ime)")
    mother_name = models.CharField(max_length=80, blank=True, verbose_name="Majka (ime)")
    photo = models.ImageField(upload_to="livestock/pets/%Y/", blank=True, verbose_name="Fotografija")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        db_table = "livestock_animal"
        ordering = ["ear_tag"]
        unique_together = [("company", "ear_tag")]
        verbose_name = "Grlo"
        verbose_name_plural = "Grla"

    def __str__(self):
        return f"{self.ear_tag} -- {self.get_vrsta_display()} ({self.get_status_display()})"

    @property
    def get_spol_display(self):
        return {"M": "Mužjak", "F": "Ženka", "N": "Nepoznato"}.get(self.spol, "Nepoznato")

    @property
    def is_pet(self):
        return self.vrsta in self.PET_VRSTE

    @property
    def age_months(self):
        if not self.date_of_birth:
            return None
        delta = timezone.now().date() - self.date_of_birth
        return delta.days // 30

    @property
    def is_in_karencija(self):
        """True ako grlo ima aktivnu karenciju — zabrana prodaje mlijeka/mesa."""
        today = timezone.now().date()
        return self.health_records.filter(karencija_do__gte=today).exists()

    @property
    def karencija_end(self):
        """Datum isteka karencije (najkasniji)."""
        today = timezone.now().date()
        rec = self.health_records.filter(karencija_do__gte=today).order_by("-karencija_do").first()
        return rec.karencija_do if rec else None

    @property
    def karencija_reason(self):
        """Razlog karencije (zadnji tretman)."""
        today = timezone.now().date()
        rec = self.health_records.filter(karencija_do__gte=today).order_by("-karencija_do").first()
        return "%s (%s)" % (rec.lijek, rec.opis) if rec else ""

    @property
    def calving_soon(self):
        if not self.expected_calving:
            return False
        return (self.expected_calving - timezone.now().date()).days <= 21


class HealthRecord(models.Model):
    """Veterinarski zapis -- cjepiva, bolesti, tretmani."""

    TIP_CHOICES = [
        ("cijepljenje", "Cijepljenje"),
        ("pregled", "Veterinarski pregled"),
        ("tretman", "Tretman / Lijek"),
        ("bolest", "Bolest"),
        ("operacija", "Operacija"),
        ("karantena", "Karantena"),
    ]

    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE, related_name="health_records")
    datum = models.DateField(verbose_name="Datum")
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    opis = models.CharField(max_length=255, verbose_name="Opis")
    veterinar = models.CharField(max_length=100, blank=True, verbose_name="Veterinar")
    lijek = models.CharField(max_length=100, blank=True, verbose_name="Lijek / Preparat")
    kolicina = models.CharField(max_length=50, blank=True, verbose_name="Kolicina doze")
    karencija_do = models.DateField(null=True, blank=True, verbose_name="Karencija do (zabrana mlijeka/mesa)")
    trosak_eur = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Trosak (EUR)")
    photo = models.ImageField(upload_to="livestock/health/%Y/", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "livestock_health_record"
        ordering = ["-datum"]
        verbose_name = "Zdravstveni zapis"
        verbose_name_plural = "Zdravstveni zapisi"

    def __str__(self):
        return f"{self.animal.ear_tag} -- {self.get_tip_display()} ({self.datum})"

    @property
    def u_karenciji(self):
        if not self.karencija_do:
            return False
        return self.karencija_do >= timezone.now().date()


class MilkRecord(models.Model):
    """Dnevna evidencija mlijecnosti -- kontrolni muzni list."""

    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE, related_name="milk_records")
    datum = models.DateField()
    jutarnja_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Jutarnja muza (L)")
    vecernja_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Vecernja muza (L)")
    ukupno_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    masnoca_posto = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True, verbose_name="Masnoca (%)"
    )
    proteini_posto = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True, verbose_name="Proteini (%)"
    )
    notes = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "livestock_milk_record"
        unique_together = [("animal", "datum")]
        ordering = ["-datum"]
        verbose_name = "Muzni zapis"
        verbose_name_plural = "Muzni zapisi"

    def save(self, *args, **kwargs):
        self.ukupno_l = self.jutarnja_l + self.vecernja_l
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.animal.ear_tag} -- {self.datum}: {self.ukupno_l}L"


class Field(models.Model):
    """Parcela -- katastarska cestica ili radna jedinica."""

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="fields")
    naziv = models.CharField(max_length=100, verbose_name="Naziv parcele")
    katastarska_cestica = models.CharField(max_length=50, blank=True, verbose_name="Katastarska cestica")
    povrsina_ha = models.DecimalField(max_digits=8, decimal_places=4, verbose_name="Povrsina (ha)")
    tip_tla = models.CharField(
        max_length=50, blank=True, verbose_name="Tip tla", help_text="npr. ilovaca, pjeskovita ilovaca, cernozem"
    )
    ph_tla = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name="pH tla")
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_organic = models.BooleanField(default=False, verbose_name="Ekoloska parcela")
    arkod_id = models.CharField(
        max_length=50, blank=True, verbose_name="ARKOD ID", help_text="Potreban za APPRRR poticaje"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        db_table = "livestock_field"
        ordering = ["naziv"]
        verbose_name = "Parcela"
        verbose_name_plural = "Parcele"

    def __str__(self):
        return f"{self.naziv} ({self.povrsina_ha} ha) -- {self.company.name}"


class CropPlan(models.Model):
    """Plan sjetve i zetve po parceli i godini."""

    STATUS_CHOICES = [
        ("plan", "U planu"),
        ("posijano", "Posijano"),
        ("raste", "Raste"),
        ("berba", "U berbi"),
        ("zavrseno", "Zavrseno"),
        ("propalo", "Propalo"),
    ]
    KULTURA_CHOICES = [
        ("kukuruz", "Kukuruz (zrno)"),
        ("kukuruz_silaza", "Kukuruz (silaza)"),
        ("djetelina", "Djetelina"),
        ("livada", "Livada / Trava"),
        ("psenica", "Psenica"),
        ("jecam", "Jecam"),
        ("soja", "Soja"),
        ("secerna_repa", "Secerna repa"),
        ("suncokret", "Suncokret"),
        ("jabuka", "Jabuka"),
        ("kruska", "Kruška"),
        ("sljiva", "Šljiva"),
        ("tresnja", "Trešnja"),
        ("visnja", "Višnja"),
        ("breskva", "Breskva"),
        ("marelica", "Marelica"),
        ("orah", "Orah"),
        ("malina", "Malina"),
        ("jagoda", "Jagoda"),
        ("vinova_loza", "Vinova loza"),
        ("ostalo", "Ostalo"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="crop_plans")
    parcela = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="crop_plans", null=True, blank=True)
    godina = models.PositiveSmallIntegerField(verbose_name="Godina")
    kultura = models.CharField(max_length=30, choices=KULTURA_CHOICES)
    sorta = models.CharField(max_length=100, blank=True, verbose_name="Sorta / Hibrid")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="plan")

    datum_sjetve = models.DateField(null=True, blank=True, verbose_name="Planirani datum sjetve")
    datum_berbe = models.DateField(null=True, blank=True, verbose_name="Planirani datum berbe")
    stvarni_datum_berbe = models.DateField(null=True, blank=True)

    planrani_prinos_t_ha = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Planirani prinos (t/ha)"
    )
    stvarni_prinos_t = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Stvarni prinos (t)"
    )

    za_vlastite_potrebe = models.BooleanField(default=True, verbose_name="Za vlastite potrebe (stoka)")
    za_prodaju = models.BooleanField(default=False, verbose_name="Za prodaju")
    procijenjeni_visak_t = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Procijenjeni visak za prodaju (t)"
    )

    is_organic = models.BooleanField(default=False)
    gnojidba_opis = models.CharField(max_length=255, blank=True, verbose_name="Gnojidba (sredstvo, kolicina)")
    zastita_opis = models.CharField(max_length=255, blank=True, verbose_name="Zastita bilja (sredstvo)")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        db_table = "livestock_crop_plan"
        ordering = ["-godina", "kultura"]
        verbose_name = "Plan sjetve"
        verbose_name_plural = "Planovi sjetve"

    def __str__(self):
        return f"{self.get_kultura_display()} {self.godina} -- {self.company.name}"

    @property
    def auto_listing_ready(self):
        """True ako ima procijenjeni visak i berba je u tijeku ili zavrsena."""
        return (
            self.za_prodaju
            and self.procijenjeni_visak_t
            and self.procijenjeni_visak_t > 0
            and self.status in ("berba", "zavrseno")
        )


class InstitutionalAccessToken(models.Model):
    """
    API token za institucije: HAPIH, sanitarna, JRDZ, VetIS.
    Farmer kreira token, daje instituciji, moze opozvati.
    """

    SCOPE_CHOICES = [
        ("hapih", "HAPIH — knjiga lijekova (EU Reg 2019/6)"),
        ("jrdz", "JRDZ — kretanje zivotinja"),
        ("sanitarna", "Sanitarna — blokade mlijeka"),
        ("vetis", "VetIS — veterinarska knjiga"),
        ("full_read", "Kompletni citaj pristup"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="institutional_tokens",
    )
    name = models.CharField(max_length=100, verbose_name="Naziv institucije")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="hapih")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_requests_day = models.PositiveIntegerField(default=1000)
    requests_today = models.PositiveIntegerField(default=0)
    last_request_date = models.DateField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    objects = CompanyManager()

    class Meta:
        db_table = "livestock_institutional_token"
        verbose_name = "Institucijski pristupni token"

    def __str__(self):
        return "%s — %s (%s)" % (self.name, self.get_scope_display(), "aktivan" if self.is_active else "neaktivan")

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets

            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def regenerate(self):
        import secrets

        self.token = secrets.token_urlsafe(32)
        self.save(update_fields=["token"])
        return self.token

    def record_access(self):
        from django.utils import timezone

        today = timezone.now().date()
        if self.last_request_date != today:
            self.requests_today = 1
            self.last_request_date = today
        else:
            self.requests_today += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=["requests_today", "last_request_date", "last_accessed_at"])

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at:
            from django.utils import timezone

            if timezone.now() > self.expires_at:
                return False
        return True

    @property
    def rate_ok(self):
        from django.utils import timezone

        if self.last_request_date != timezone.now().date():
            return True
        return self.requests_today < self.max_requests_day


class InstitutionalAccessLog(models.Model):
    """Audit log za svaki institucijski API poziv."""

    token = models.ForeignKey(InstitutionalAccessToken, on_delete=models.CASCADE, related_name="access_logs")
    endpoint = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    response_code = models.PositiveSmallIntegerField(default=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "livestock_institutional_log"
        ordering = ["-timestamp"]


# ═══════════════════════════════════════════════════════════════════════════
# IDENTIFIKACIJSKA KARTICA GOSPODARSTVA (IKG) — HPA / JRDZ
# Zakon o veterinarstvu (NN 82/13), Pravilnik NN 96/2015
# ═══════════════════════════════════════════════════════════════════════════


class FarmIdentification(models.Model):
    """
    Identifikacijska kartica gospodarstva — IKG.
    Jedna po JIBG-u (lokaciji). Vlasnik može imati više kartica.

    Podaci čitani s kartice:
    - Serijski broj kartice (00234792)
    - JIBG (HR 30157757)
    - Ime i prezime posjednika
    - Naziv gospodarstva
    - Adresa, općina, županija
    - Tetovirni broj (barcode)
    """

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="farm_identifications")

    # Kartica
    card_serial = models.CharField(max_length=20, verbose_name="Serijski broj kartice", help_text="Npr. 00234792")
    jibg = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="JIBG",
        help_text="Jedinstveni identifikacijski broj gospodarstva. Npr. HR 30157757",
    )
    tattoo_number = models.CharField(
        max_length=30, blank=True, verbose_name="Tetovirni broj", help_text="Barcode na kartici"
    )

    # Posjednik
    owner_name = models.CharField(max_length=200, verbose_name="Ime i prezime posjednika")
    farm_name = models.CharField(max_length=200, blank=True, verbose_name="Naziv gospodarstva")

    # Lokacija
    address = models.CharField(max_length=200, verbose_name="Adresa")
    settlement = models.CharField(max_length=100, blank=True, verbose_name="Naselje")
    municipality = models.CharField(max_length=100, blank=True, verbose_name="Općina/Grad")
    zip_code = models.CharField(max_length=10, blank=True, verbose_name="Poštanski broj")
    county = models.CharField(max_length=100, blank=True, verbose_name="Županija")

    # GPS
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Fotografija kartice
    card_photo_front = models.ImageField(
        upload_to="farm_id/cards/", null=True, blank=True, verbose_name="Foto kartice (prednja strana)"
    )
    card_photo_back = models.ImageField(
        upload_to="farm_id/cards/", null=True, blank=True, verbose_name="Foto kartice (stražnja strana)"
    )

    # Vrste životinja na gospodarstvu
    ANIMAL_TYPES = [
        ("cattle", "Goveda"),
        ("pigs", "Svinje"),
        ("sheep", "Ovce"),
        ("goats", "Koze"),
        ("poultry", "Perad"),
        ("horses", "Kopitari (konji, magarci)"),
        ("bees", "Pčele"),
        ("rabbits", "Kunići"),
        ("fish", "Ribe / školjke"),
        ("game", "Divljač (uzgoj)"),
    ]
    animal_types = models.JSONField(
        default=list, blank=True, verbose_name="Vrste životinja", help_text="Lista vrsta na gospodarstvu"
    )

    # Status
    is_active = models.BooleanField(default=True)
    registered_at = models.DateField(null=True, blank=True, verbose_name="Datum registracije u JRDZ")

    # ePosjednik pristup
    eposjednik_username = models.CharField(max_length=50, blank=True, verbose_name="ePosjednik korisničko ime")
    eposjednik_active = models.BooleanField(default=False, verbose_name="ePosjednik aktivan")

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Identifikacijska kartica gospodarstva"
        verbose_name_plural = "Identifikacijske kartice gospodarstva"

    def __str__(self):
        return f"{self.jibg} — {self.owner_name} ({self.farm_name or self.address})"

    @property
    def jibg_display(self):
        """Format: HR 30157757"""
        j = self.jibg.replace(" ", "").upper()
        if j.startswith("HR") and len(j) > 2:
            return f"HR {j[2:]}"
        return j
