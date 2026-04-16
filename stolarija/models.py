from django.contrib.auth.models import User
from django.db import models


class WindowProfile(models.Model):
    """Katalog profila — jednom definiraš, zauvijek koristiš."""

    MATERIAL = [("alu", "Aluminij"), ("pvc", "PVC"), ("wood", "Drvo")]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="window_profiles")
    name = models.CharField(max_length=100, verbose_name="Naziv")
    system = models.CharField(max_length=100, blank=True, verbose_name="Sustav")
    material = models.CharField(max_length=5, choices=MATERIAL, default="alu")
    color_outer = models.CharField(max_length=50, blank=True, verbose_name="Boja vanjska")
    color_inner = models.CharField(max_length=50, blank=True, verbose_name="Boja unutarnja")
    price_per_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Cijena/m²")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["material", "name"]
        verbose_name = "Profil stolarije"
        verbose_name_plural = "Profili stolarije"

    def __str__(self):
        return f"{self.name} ({self.get_material_display()})"


class GlassType(models.Model):
    """Katalog stakla."""

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="glass_types")
    name = models.CharField(max_length=100, verbose_name="Naziv")
    u_value = models.DecimalField(max_digits=4, decimal_places=2, default=1.1, verbose_name="U vrijednost (W/m²K)")
    price_per_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Cijena/m²")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Vrsta stakla"
        verbose_name_plural = "Vrste stakla"

    def __str__(self):
        return f"{self.name} (U={self.u_value})"


class MeasurementSession(models.Model):
    """
    Jedna obilazak/mjerenje na lokaciji kupca.
    Sadrži N mjerenja (Measurement).
    Vezana na WorkOrder.
    """

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="measurement_sessions")
    work_order = models.ForeignKey(
        "work_orders.WorkOrder", on_delete=models.CASCADE, related_name="measurement_sessions", null=True, blank=True
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="measurement_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=255, blank=True, verbose_name="Adresa objekta")
    notes = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True, verbose_name="GPS lat")
    longitude = models.FloatField(null=True, blank=True, verbose_name="GPS lng")
    gps_accuracy = models.FloatField(null=True, blank=True, verbose_name="GPS točnost (m)")
    gps_altitude = models.FloatField(null=True, blank=True, verbose_name="GPS nadmorska visina (m)")
    gps_captured_at = models.DateTimeField(null=True, blank=True, verbose_name="GPS vrijeme snimanja")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sesija mjerenja"
        verbose_name_plural = "Sesije mjerenja"

    def __str__(self):
        return f"Mjerenje {self.created_at:%d.%m.%Y} — {self.address or self.work_order}"

    @property
    def total_items(self):
        return self.measurements.count()

    @property
    def confirmed_items(self):
        return self.measurements.filter(confirmed=True).count()


class Measurement(models.Model):
    """
    Jedno izmjereno mjesto — prozor, vrata, komarnik.
    Zdenko mjeri na terenu, govori ili tipka.
    KLJUČNO: confirmed=True tek kad Zdenko vizualno potvrdi dimenzije.
    """

    ELEMENT_TYPES = [
        ("window", "Prozor"),
        ("door", "Vrata (ulazna)"),
        ("interior_door", "Sobna vrata"),
        ("balcony_door", "Balkonska vrata"),
        ("mosquito", "Komarnik"),
        ("roller", "Roleta"),
        ("facade", "Fasadna stijena"),
        ("other", "Ostalo"),
    ]
    WING_CONFIGS = [
        ("fixed", "Fiksno"),
        ("single", "Jednokrilno"),
        ("double", "Dvokrilno"),
        ("triple", "Trokrilno"),
        ("sliding", "Klizno"),
        ("tilt_turn", "Kip-turn"),
        ("single_left", "Jednokrilno LIJEVO (L)"),
        ("single_right", "Jednokrilno DESNO (D)"),
        ("double_asym", "Dvokrilno asimetricno"),
        ("pivot", "Pivotirajuce"),
        ("barn", "Klizno na zid (barn door)"),
    ]

    SWING_DIRECTION = [
        ("inward", "U prostoriju"),
        ("outward", "Van prostorije"),
    ]

    DOOR_POSITION = [
        ("north", "Sjever"),
        ("south", "Jug"),
        ("east", "Istok"),
        ("west", "Zapad"),
        ("internal", "Unutarnji zid"),
        ("bathroom", "Kupaonica"),
        ("bedroom", "Spavaca soba"),
        ("kitchen", "Kuhinja"),
        ("living", "Dnevni boravak"),
        ("hallway", "Hodnik"),
        ("storage", "Ostava"),
        ("wc", "WC"),
    ]

    session = models.ForeignKey(MeasurementSession, on_delete=models.CASCADE, related_name="measurements")
    position_number = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Pozicija br.",
        help_text="Automatski redni broj pozicije unutar sesije",
    )
    location_note = models.CharField(max_length=200, blank=True, verbose_name="Lokacija otvora")
    floor = models.SmallIntegerField(default=0, verbose_name="Kat (0=prizemlje)")

    # Sobna vrata specifika
    swing_direction = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="Smjer otvaranja",
        help_text="inward=u prostoriju, outward=van prostorije",
    )
    door_position = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Pozicija vrata / prostorija",
        help_text="Prostorija u koju vrata vode",
    )
    wall_thickness_mm = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Debljina zida (mm)",
        help_text="Za obuhvatni stok — mjeri se na licu mjesta",
    )
    door_standard = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Standard vrata",
        help_text="DIN/HR/BiH/PL/IT/TR — sustav auto-detektira",
    )

    # Komarnik specifika
    mesh_type = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Tip mreze",
        help_text="pvc/alu/fiberglass/plisse",
    )
    mounting_type = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Tip montaze komarnika",
        help_text="fixed_frame/roller/plisse/magnetic/velcro",
    )

    # Dimenzije u mm
    width_mm = models.PositiveIntegerField(verbose_name="Širina (mm)")
    height_mm = models.PositiveIntegerField(verbose_name="Visina (mm)")
    depth_mm = models.PositiveIntegerField(default=0, blank=True, verbose_name="Dubina zida (mm)")

    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES, default="window", verbose_name="Tip")
    wing_config = models.CharField(max_length=20, choices=WING_CONFIGS, default="double", verbose_name="Konfiguracija")
    quantity = models.PositiveSmallIntegerField(default=1, verbose_name="Količina")

    profile = models.ForeignKey(WindowProfile, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Profil")
    glass = models.ForeignKey(GlassType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Staklo")

    # Voice input
    voice_raw = models.TextField(blank=True, verbose_name="Glasovni unos (sirovi)")
    ai_parsed = models.JSONField(default=dict, blank=True, verbose_name="AI parsiranje")

    # KRITIČNO: Zdenko mora potvrditi prije generiranja ponude
    confirmed = models.BooleanField(default=False, verbose_name="Potvrđeno ✓")

    photo_before = models.ImageField(
        upload_to="stolarija/photos/%Y/%m/", null=True, blank=True, verbose_name="Foto prije"
    )
    photo_annotated = models.ImageField(
        upload_to="stolarija/annotated/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Foto s mjerama",
    )
    photo_annotations = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Anotacije na fotografiji",
        help_text='[{"type":"line","x1":10,"y1":20,"x2":300,"y2":20,"label":"1200mm","color":"#ff0000"}]',
    )
    ai_dimensions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="AI očitane dimenzije",
        help_text='{"width_mm":1200,"height_mm":1400,"confidence":0.92,"source":"anthropic_vision"}',
    )
    ai_confidence = models.FloatField(
        default=0,
        verbose_name="AI pouzdanost (0-1)",
    )
    measurement_source = models.CharField(
        max_length=20,
        default="manual",
        blank=True,
        verbose_name="Izvor mjerenja",
        help_text="manual / photo_draw / ai_vision / voice",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position_number", "floor", "id"]
        verbose_name = "Mjerenje"
        verbose_name_plural = "Mjerenja"

    def __str__(self):
        return (
            f"Poz. {self.position_number}: {self.get_element_type_display()} "
            f"{self.width_mm}×{self.height_mm}mm "
            f"×{self.quantity}kom"
        )

    @property
    def area_m2(self):
        from decimal import Decimal

        return round(Decimal(self.width_mm) * Decimal(self.height_mm) / Decimal("1000000"), 3)

    @property
    def total_area_m2(self):
        return round(self.area_m2 * self.quantity, 3)

    def calculate_price(self):
        """Okvirna cijena na temelju profila i stakla."""
        from decimal import Decimal

        total = Decimal("0")
        if self.profile and self.profile.price_per_m2:
            total += self.profile.price_per_m2 * self.total_area_m2
        if self.glass and self.glass.price_per_m2:
            total += self.glass.price_per_m2 * self.total_area_m2
        return total


class WindowOffer(models.Model):
    """Ponuda generirana iz MeasurementSession."""

    STATUS = [
        ("draft", "Nacrt"),
        ("sent", "Poslana"),
        ("accepted", "Prihvaćena"),
        ("rejected", "Odbijena"),
        ("expired", "Istekla"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="window_offers")
    session = models.ForeignKey(MeasurementSession, on_delete=models.CASCADE, related_name="offers")
    offer_number = models.CharField(max_length=20, blank=True, verbose_name="Broj ponude")
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    valid_days = models.PositiveSmallIntegerField(default=30, verbose_name="Valjanost (dana)")

    total_net = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_pct = models.SmallIntegerField(default=30, verbose_name="Avans (%)")

    client_signature = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by_name = models.CharField(max_length=100, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ponuda"
        verbose_name_plural = "Ponude"

    def __str__(self):
        return f"Ponuda {self.offer_number or self.pk} — {self.session}"

    def recalculate(self):
        """Izračunaj ukupne iznose iz mjerenja."""
        from decimal import Decimal

        total = Decimal("0")
        for m in self.session.measurements.filter(confirmed=True):
            total += m.calculate_price()
        self.total_net = total
        self.total_vat = round(total * Decimal("0.25"), 2)
        self.total_gross = self.total_net + self.total_vat
        self.save(update_fields=["total_net", "total_vat", "total_gross"])

    def save(self, *args, **kwargs):
        if not self.offer_number:
            import datetime

            count = WindowOffer.objects.filter(company=self.company).count() + 1
            self.offer_number = f"PON-{datetime.date.today().year}-{count:04d}"
        super().save(*args, **kwargs)


class WindowWarranty(models.Model):
    """Garancija — QR kod → kupac portal."""

    session = models.OneToOneField(
        MeasurementSession, on_delete=models.CASCADE, related_name="warranty", null=True, blank=True
    )
    warranty_number = models.CharField(max_length=30, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_years = models.SmallIntegerField(default=5)
    qr_token = models.CharField(max_length=40, unique=True, blank=True)
    handover_date = models.DateField(null=True, blank=True)
    handover_photo = models.ImageField(upload_to="stolarija/handover/%Y/%m/", null=True, blank=True)
    client_signature = models.TextField(blank=True)
    handover_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Garancija"
        verbose_name_plural = "Garancije"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            import secrets

            self.qr_token = secrets.token_urlsafe(20)
        if not self.warranty_number:
            import datetime

            self.warranty_number = f"GAR-{datetime.date.today().year}-{self.pk or '???'}"
        super().save(*args, **kwargs)

    @property
    def next_service_date(self):
        if self.handover_date:
            return self.handover_date.replace(year=self.handover_date.year + 1)
        return None

    def __str__(self):
        return self.warranty_number


class ServiceVisit(models.Model):
    """Godišnji servisni pregled."""

    warranty = models.ForeignKey(WindowWarranty, on_delete=models.CASCADE, related_name="service_visits")
    scheduled = models.DateField(verbose_name="Zakazano")
    completed = models.DateField(null=True, blank=True, verbose_name="Izvršeno")
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="service_visits")
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to="stolarija/service/%Y/%m/", null=True, blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ai_reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["scheduled"]
        verbose_name = "Servisni posjet"
        verbose_name_plural = "Servisni posjeti"

    def __str__(self):
        return f"Servis {self.scheduled} — {self.warranty}"


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 4: Narudžba u proizvodnju
# ═══════════════════════════════════════════════════════════════════════════


class ProductionOrder(models.Model):
    """Narudžbenica za proizvodnju — generira se iz prihvaćene ponude."""

    STATUS = [
        ("pending", "Na čekanju"),
        ("confirmed", "Potvrđena"),
        ("cutting", "Rezanje profila"),
        ("assembly", "Montaža okvira"),
        ("glazing", "Ugradnja stakla"),
        ("qc", "Kontrola kvalitete"),
        ("ready", "Gotovo za isporuku"),
        ("delivered", "Isporučeno"),
    ]

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="stolarija_production_orders"
    )
    offer = models.OneToOneField(WindowOffer, on_delete=models.CASCADE, related_name="production_order")
    order_number = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")

    estimated_date = models.DateField(null=True, blank=True, verbose_name="Planirani rok")
    actual_date = models.DateField(null=True, blank=True, verbose_name="Stvarni završetak")

    material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Proizvodni nalog"
        verbose_name_plural = "Proizvodni nalozi"

    def __str__(self):
        return f"PRO-{self.order_number or self.pk} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import datetime

            count = ProductionOrder.objects.filter(company=self.company).count() + 1
            self.order_number = f"PRO-{datetime.date.today().year}-{count:04d}"
        super().save(*args, **kwargs)


class BOMItem(models.Model):
    """Bill of Materials stavka — što treba za proizvodnju jedne pozicije."""

    CATEGORIES = [
        ("profile", "Profil"),
        ("glass", "Staklo"),
        ("hardware", "Okov"),
        ("seal", "Brtva"),
        ("sill", "Klupčica"),
        ("anchor", "Ankeri/vijci"),
        ("foam", "PU pjena"),
        ("silicone", "Silikon"),
        ("other", "Ostalo"),
    ]
    UNITS = [
        ("m", "metar"),
        ("m2", "m²"),
        ("kom", "komad"),
        ("kg", "kilogram"),
        ("l", "litar"),
    ]

    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="bom_items")
    measurement = models.ForeignKey(
        Measurement, on_delete=models.SET_NULL, null=True, blank=True, help_text="Koja pozicija iz mjerenja"
    )
    category = models.CharField(max_length=20, choices=CATEGORIES)
    name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(max_length=5, choices=UNITS, default="kom")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    supplier = models.CharField(max_length=200, blank=True)
    ordered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "BOM stavka"
        verbose_name_plural = "BOM stavke"

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} {self.quantity}{self.unit}"


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 6: Ugradnja
# ═══════════════════════════════════════════════════════════════════════════


class InstallationOrder(models.Model):
    """Nalog za ugradnju — terenski tim."""

    STATUS = [
        ("scheduled", "Zakazano"),
        ("in_progress", "U tijeku"),
        ("completed", "Završeno"),
        ("issue", "Problem"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="stolarija_installations")
    production_order = models.OneToOneField(ProductionOrder, on_delete=models.CASCADE, related_name="installation")

    scheduled_date = models.DateField(verbose_name="Datum ugradnje")
    team_lead = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="led_installations")
    team_members = models.ManyToManyField(User, blank=True, related_name="installations")

    status = models.CharField(max_length=20, choices=STATUS, default="scheduled")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    notes_before = models.TextField(blank=True, verbose_name="Napomene prije ugradnje")
    notes_after = models.TextField(blank=True, verbose_name="Napomene nakon ugradnje")
    photo_before = models.ImageField(upload_to="stolarija/install/before/%Y/%m/", null=True, blank=True)
    photo_annotated = models.ImageField(
        upload_to="stolarija/annotated/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Foto s mjerama",
    )
    photo_annotations = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Anotacije na fotografiji",
        help_text='[{"type":"line","x1":10,"y1":20,"x2":300,"y2":20,"label":"1200mm","color":"#ff0000"}]',
    )
    ai_dimensions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="AI očitane dimenzije",
        help_text='{"width_mm":1200,"height_mm":1400,"confidence":0.92,"source":"anthropic_vision"}',
    )
    ai_confidence = models.FloatField(
        default=0,
        verbose_name="AI pouzdanost (0-1)",
    )
    measurement_source = models.CharField(
        max_length=20,
        default="manual",
        blank=True,
        verbose_name="Izvor mjerenja",
        help_text="manual / photo_draw / ai_vision / voice",
    )
    photo_after = models.ImageField(upload_to="stolarija/install/after/%Y/%m/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_date"]
        verbose_name = "Ugradnja"
        verbose_name_plural = "Ugradnje"

    def __str__(self):
        return f"Ugradnja {self.scheduled_date} — {self.production_order}"


class InstallationChecklist(models.Model):
    """Checklist stavka za ugradnju."""

    installation = models.ForeignKey(InstallationOrder, on_delete=models.CASCADE, related_name="checklist")
    measurement = models.ForeignKey(Measurement, on_delete=models.SET_NULL, null=True, blank=True)

    # Obavezni koraci
    old_removed = models.BooleanField(default=False, verbose_name="Demontaža starog")
    opening_prepared = models.BooleanField(default=False, verbose_name="Priprema otvora")
    frame_mounted = models.BooleanField(default=False, verbose_name="Montaža okvira")
    glass_inserted = models.BooleanField(default=False, verbose_name="Umetanje stakla")
    sealed = models.BooleanField(default=False, verbose_name="Brtvljenje")
    adjusted = models.BooleanField(default=False, verbose_name="Podešavanje")
    cleaned = models.BooleanField(default=False, verbose_name="Čišćenje")

    photo_result = models.ImageField(upload_to="stolarija/install/result/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Checklist ugradnje"
        verbose_name_plural = "Checklisti ugradnje"

    @property
    def is_complete(self):
        return all(
            [
                self.old_removed,
                self.opening_prepared,
                self.frame_mounted,
                self.glass_inserted,
                self.sealed,
                self.adjusted,
                self.cleaned,
            ]
        )

    def __str__(self):
        status = "✓" if self.is_complete else "○"
        return f"{status} {self.measurement or 'Stavka'}"


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 7 proširenje: Primopredaja
# ═══════════════════════════════════════════════════════════════════════════


class HandoverProtocol(models.Model):
    """Zapisnik primopredaje — kupac potpisuje, dobiva garanciju."""

    installation = models.OneToOneField(InstallationOrder, on_delete=models.CASCADE, related_name="handover")

    client_name = models.CharField(max_length=200, verbose_name="Ime kupca")
    client_signature = models.TextField(blank=True, verbose_name="Potpis (base64)")
    signed_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(blank=True, verbose_name="Primjedbe kupca")
    accepted = models.BooleanField(default=False, verbose_name="Kupac prihvatio")

    warranty = models.OneToOneField(
        WindowWarranty, on_delete=models.SET_NULL, null=True, blank=True, related_name="handover"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zapisnik primopredaje"
        verbose_name_plural = "Zapisnici primopredaje"

    def __str__(self):
        return f"Primopredaja — {self.client_name} ({self.signed_at or 'nepotpisano'})"


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 9: Predictive Service — AI risk scoring
# ═══════════════════════════════════════════════════════════════════════════


class ServiceRiskProfile(models.Model):
    """
    AI-generated risk profile per warranty.
    Recalculated weekly by Celery. Rule-based Phase 1, ML Phase 2.
    """

    RISK_LEVELS = [
        ("low", "Nizak"),
        ("medium", "Srednji"),
        ("high", "Visok"),
        ("critical", "Kritičan"),
    ]
    ISSUE_CATEGORIES = [
        ("seal", "Brtva — propuštanje, starenje"),
        ("hardware", "Okov — korozija, habanje"),
        ("condensation", "Kondenzacija — vlaga između stakala"),
        ("deformation", "Deformacija — PVC širenje/skupljanje"),
        ("glass", "Staklo — oštećenje, U-degradacija"),
        ("frame", "Okvir — pucanje, savijanje"),
        ("drainage", "Odvodnja — začepljenje kanala"),
    ]
    LOCATION_ZONES = [
        ("coastal", "Primorje (slana sredina)"),
        ("continental", "Kontinentalna (velika amplituda)"),
        ("mountain", "Planinska (snijeg, vjetar)"),
        ("urban", "Urbana (standardna)"),
    ]

    warranty = models.OneToOneField(WindowWarranty, on_delete=models.CASCADE, related_name="risk_profile")
    risk_score = models.PositiveSmallIntegerField(default=0, help_text="0-100, higher = more risk")
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default="low")

    # Predicted primary issue
    predicted_issue = models.CharField(max_length=20, choices=ISSUE_CATEGORIES, default="seal")
    issue_confidence = models.FloatField(default=0.0, help_text="0.0-1.0 confidence in prediction")

    # Risk factors (stored for transparency)
    factors = models.JSONField(default=dict, blank=True, help_text="Breakdown of risk factors and scores")

    # Location classification
    location_zone = models.CharField(max_length=15, choices=LOCATION_ZONES, default="urban")

    # Recommended action
    recommendation = models.TextField(blank=True, help_text="AI-generated maintenance recommendation")
    optimal_service_window = models.CharField(max_length=100, blank=True, help_text='e.g. "Prije zime 2026"')

    # Meta
    calculated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveSmallIntegerField(default=1, help_text="Algorithm version")

    class Meta:
        ordering = ["-risk_score"]
        verbose_name = "Risk profil"
        verbose_name_plural = "Risk profili"

    def __str__(self):
        return f"Risk {self.risk_score}/100 ({self.get_risk_level_display()}) — {self.warranty}"


class ServiceMessage(models.Model):
    """
    AI-managed service communication — inbound from client, outbound drafts.
    Human-in-the-loop: AI drafts, human approves.
    """

    DIRECTION = [
        ("inbound", "Primljeno od kupca"),
        ("outbound", "Poslano kupcu"),
    ]
    STATUS = [
        ("received", "Primljeno"),
        ("ai_draft", "AI nacrt"),
        ("approved", "Odobreno"),
        ("sent", "Poslano"),
        ("escalated", "Eskalirano"),
    ]
    CHANNELS = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("sms", "SMS"),
        ("portal", "Portal"),
    ]

    warranty = models.ForeignKey(
        WindowWarranty, on_delete=models.CASCADE, related_name="messages", null=True, blank=True
    )
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="service_messages")
    direction = models.CharField(max_length=10, choices=DIRECTION)
    channel = models.CharField(max_length=10, choices=CHANNELS, default="email")
    status = models.CharField(max_length=10, choices=STATUS, default="received")

    # Content
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    sender_email = models.EmailField(blank=True)
    sender_name = models.CharField(max_length=200, blank=True)

    # AI analysis
    ai_draft = models.TextField(blank=True, help_text="AI-generated reply draft")
    ai_sentiment = models.CharField(max_length=20, blank=True, help_text="positive/neutral/negative/urgent")
    ai_category = models.CharField(max_length=30, blank=True, help_text="complaint/service_request/info/scheduling")
    ai_image_analysis = models.JSONField(default=dict, blank=True, help_text="Multimodal image analysis results")
    ai_confidence = models.FloatField(default=0.0)

    # Attachments
    attachment = models.FileField(upload_to="stolarija/messages/%Y/%m/", null=True, blank=True)
    attachment_thumbnail = models.ImageField(upload_to="stolarija/messages/thumbs/%Y/%m/", null=True, blank=True)

    # Human-in-the-loop
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_messages"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    edited_body = models.TextField(blank=True, help_text="Human-edited version of AI draft")

    # Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Servisna poruka"
        verbose_name_plural = "Servisne poruke"

    def __str__(self):
        return f"[{self.get_direction_display()}] {self.subject or 'Bez predmeta'} ({self.get_status_display()})"

    @property
    def final_body(self):
        """Return edited body if exists, else AI draft."""
        return self.edited_body or self.ai_draft or self.body
