"""
delivery/models.py - Logistika i dostava za Grossmarkt Online

Vozila, rute, GPS tracking, temperatura hladnog lanca.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class Vehicle(models.Model):
    """Dostavno vozilo."""
    VEHICLE_TYPES = [
        ('van', _('Kombi')),
        ('truck', _('Kamion')),
        ('car', _('Automobil')),
        ('refrigerated', _('Hladnjača')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='vehicles', verbose_name=_('Tvrtka')
    )
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    plate_number = models.CharField(max_length=20, verbose_name=_('Registracija'))
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='van')

    # Hladni lanac
    has_cold_chain = models.BooleanField(default=False, verbose_name=_('Hladni lanac'))
    cold_chain_min_temp = models.IntegerField(null=True, blank=True, verbose_name=_('Min °C'))
    cold_chain_max_temp = models.IntegerField(null=True, blank=True, verbose_name=_('Max °C'))

    # Kapacitet
    max_capacity_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_('Max kg'))
    max_volume_m3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name=_('Max m³'))

    # Tracking
    gps_device_id = models.CharField(max_length=100, blank=True)
    temp_sensor_id = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Vozilo')
        verbose_name_plural = _('Vozila')

    def __str__(self):
        return f"{self.name} ({self.plate_number})"


class DeliveryRoute(models.Model):
    """Dnevna ruta dostave."""
    STATUS_CHOICES = [
        ('planned', _('Planirana')),
        ('in_progress', _('U tijeku')),
        ('completed', _('Završena')),
        ('cancelled', _('Otkazana')),
    ]

    date = models.DateField(verbose_name=_('Datum'))
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='routes', verbose_name=_('Vozilo'))
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_routes',
        verbose_name=_('Vozač')
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    total_stops = models.PositiveIntegerField(default=0)
    total_distance_km = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    estimated_duration_hours = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Ruta dostave')
        verbose_name_plural = _('Rute dostave')
        ordering = ['-date']

    def __str__(self):
        return f"Ruta {self.date} — {self.vehicle}"


class DeliveryStop(models.Model):
    """Stanica na ruti - pickup od OPG-a ili delivery restoranu."""
    STOP_TYPES = [
        ('pickup', _('Preuzimanje')),
        ('delivery', _('Dostava')),
    ]
    STATUS_CHOICES = [
        ('pending', _('Čeka')),
        ('arrived', _('Stigao')),
        ('completed', _('Završeno')),
        ('skipped', _('Preskočeno')),
    ]

    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, related_name='stops')
    stop_order = models.PositiveIntegerField(verbose_name=_('Redoslijed'))
    stop_type = models.CharField(max_length=10, choices=STOP_TYPES)

    # Veze
    seller_suborder = models.ForeignKey(
        'marketplace.SellerSubOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pickup_stops',
        verbose_name=_('Sub-narudžba za pickup')
    )
    marketplace_order = models.ForeignKey(
        'marketplace.MarketplaceOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_stops',
        verbose_name=_('Narudžba za dostavu')
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('OPG / Restoran')
    )

    # Lokacija
    address = models.CharField(max_length=300, verbose_name=_('Adresa'))
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Potvrda
    signature_image = models.ImageField(upload_to='delivery/signatures/', blank=True, null=True)
    delivery_photo = models.ImageField(upload_to='delivery/photos/', blank=True, null=True)
    recipient_name = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    # Temperatura pri primopredaji
    temp_at_handover = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name=_('Temp °C'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Stanica dostave')
        verbose_name_plural = _('Stanice dostave')
        ordering = ['route', 'stop_order']

    def __str__(self):
        return f"Stop {self.stop_order}: {self.get_stop_type_display()} — {self.company}"


class TemperatureLog(models.Model):
    """Log temperature hladnog lanca tijekom transporta."""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='temp_logs')
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, null=True, blank=True, related_name='temp_logs')
    timestamp = models.DateTimeField()
    temperature = models.DecimalField(max_digits=5, decimal_places=1, verbose_name=_('Temperatura °C'))
    zone = models.CharField(max_length=20, default='chilled', choices=[('frozen', 'Zamrznuto'), ('chilled', 'Rashlađeno')])
    is_alert = models.BooleanField(default=False)
    alert_message = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        verbose_name = _('Log temperature')
        verbose_name_plural = _('Logovi temperature')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.vehicle} {self.timestamp:%H:%M} — {self.temperature}°C"


class DeliveryTracking(models.Model):
    """GPS pozicija vozila u realnom vremenu."""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='tracking_points')
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    speed_kmh = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    heading = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = _('GPS pozicija')
        verbose_name_plural = _('GPS pozicije')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['vehicle', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.vehicle} @ {self.timestamp:%H:%M}"



class ConsolidatedDelivery(models.Model):
    """
    Cross-docking: spaja vise marketplace narudzbi u jednu fizicku isporuku.
    Veletrznica prima robu od OPG-ova u hub, prepakira i salje jednim vozilom.
    """
    STATUS_CHOICES = [
        ('collecting', _('Prikupljanje u hub')),
        ('consolidating', _('Konsolidacija / prepakiranje')),
        ('dispatched', _('Otpremljeno')),
        ('in_transit', _('U transportu')),
        ('delivered', _('Dostavljeno')),
        ('cancelled', _('Otkazano')),
    ]

    DELIVERY_METHOD_CHOICES = [
        ('internal', _('Interna dostava (vlastito vozilo)')),
        ('bus', _('Autobusna linija')),
        ('taxi', _('Taxi / brza dostava')),
        ('crowd', _('Crowd-shipping (BlaBlaCar/Gepek)')),
        ('courier', _('Kurirska sluzba')),
        ('pickup', _('Osobno preuzimanje')),
    ]

    # Identifikacija
    delivery_number = models.CharField(max_length=30, unique=True, editable=False, verbose_name=_('Broj konsolidirane isporuke'))
    hub_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='hub_consolidated_deliveries',
        verbose_name=_('Hub (veletrznica)')
    )
    buyer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='buyer_consolidated_deliveries',
        verbose_name=_('Kupac (restoran/trgovina)')
    )

    # Narudzbe koje su spojene u ovu isporuku
    marketplace_orders = models.ManyToManyField(
        'marketplace.MarketplaceOrder', blank=True,
        related_name='consolidated_deliveries',
        verbose_name=_('Spojene narudzbe')
    )

    # Status i metoda
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='collecting')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default='internal')

    # Vozilo i vozac (za internu dostavu)
    route = models.ForeignKey(
        DeliveryRoute, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consolidated_deliveries',
        verbose_name=_('Ruta')
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Vozilo')
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consolidated_deliveries',
        verbose_name=_('Vozac')
    )

    # Vanjski prijevoznik (bus/taxi/crowd)
    external_carrier_name = models.CharField(max_length=200, blank=True, verbose_name=_('Prijevoznik / vozac'))
    external_carrier_contact = models.CharField(max_length=100, blank=True, verbose_name=_('Kontakt'))
    external_carrier_ref = models.CharField(max_length=100, blank=True, verbose_name=_('Ref (linija/reg.oznaka/profil)'))

    # Adresa dostave
    delivery_address = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa dostave'))
    delivery_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Vremena
    hub_cutoff_time = models.DateTimeField(null=True, blank=True, verbose_name=_('Rok dostave u hub'))
    dispatched_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Otpremljeno'))
    eta = models.DateTimeField(null=True, blank=True, verbose_name=_('Ocekivani dolazak'))
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Dostavljeno'))

    # Tracking veza
    tracked_item = models.OneToOneField(
        'tracking.TrackedItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consolidated_delivery',
        verbose_name=_('Tracking')
    )

    # Hladni lanac
    requires_cold_chain = models.BooleanField(default=False, verbose_name=_('Zahtijeva hladni lanac'))
    cold_chain_zone = models.ForeignKey(
        'ColdChainZone', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Zona hladnjace')
    )

    # Tezina / paketi
    total_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_('Ukupna tezina (kg)'))
    package_count = models.PositiveIntegerField(default=1, verbose_name=_('Broj paketa'))

    # Potvrda prijema
    recipient_name = models.CharField(max_length=100, blank=True, verbose_name=_('Preuzeo'))
    recipient_signature = models.ImageField(upload_to='delivery/consolidated/signatures/', blank=True, null=True)
    delivery_photo = models.ImageField(upload_to='delivery/consolidated/photos/', blank=True, null=True)
    delivery_notes = models.TextField(blank=True, verbose_name=_('Napomene'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_consolidated_deliveries'
    )
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Konsolidirana isporuka')
        verbose_name_plural = _('Konsolidirane isporuke')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hub_company', 'status']),
            models.Index(fields=['buyer_company', 'status']),
        ]

    def __str__(self):
        return f"{self.delivery_number} -> {self.buyer_company.name}"

    def save(self, *args, **kwargs):
        if not self.delivery_number:
            from django.utils import timezone
            year = timezone.now().year
            last = ConsolidatedDelivery.objects.filter(
                delivery_number__startswith=f'CD-{year}-'
            ).count()
            self.delivery_number = f'CD-{year}-{last + 1:05d}'
        super().save(*args, **kwargs)

    @property
    def seller_count(self):
        return self.marketplace_orders.values('items__seller_company').distinct().count()

    @property
    def total_value(self):
        return sum(o.total for o in self.marketplace_orders.all())


class ColdChainZone(models.Model):
    """Zona u hladnjaci veletrznice (npr. Hladnjaca 1, Rampa, Zamrzivac)."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='cold_chain_zones', verbose_name=_('Tvrtka')
    )
    name = models.CharField(max_length=100, verbose_name=_('Naziv zone'))
    zone_type = models.CharField(max_length=20, choices=[
        ('chilled', _('Rashladeno (+2 do +8 C)')),
        ('frozen', _('Zamrznuto (-18 C i nize)')),
        ('ambient', _('Sobna temperatura')),
        ('loading_dock', _('Rampa za utovar')),
    ], default='chilled')
    target_min_temp = models.DecimalField(max_digits=5, decimal_places=1, verbose_name=_('Min ciljna temp (C)'))
    target_max_temp = models.DecimalField(max_digits=5, decimal_places=1, verbose_name=_('Max ciljna temp (C)'))

    # Senzor integracija
    sensor_device_id = models.CharField(max_length=100, blank=True, verbose_name=_('ID senzora'))
    sensor_api_url = models.URLField(blank=True, verbose_name=_('API URL senzora'))

    is_active = models.BooleanField(default=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Zona hladnog lanca')
        verbose_name_plural = _('Zone hladnog lanca')

    def __str__(self):
        return f"{self.name} ({self.get_zone_type_display()})"

    @property
    def latest_reading(self):
        return self.sensor_readings.order_by('-timestamp').first()

    @property
    def is_in_range(self):
        r = self.latest_reading
        if not r:
            return None
        return self.target_min_temp <= r.temperature <= self.target_max_temp


class SensorReading(models.Model):
    """Ocitanje temperature iz senzora hladnjace ili transporta."""
    SOURCE_CHOICES = [
        ('zone', _('Zona hladnjace')),
        ('vehicle', _('Vozilo')),
        ('delivery', _('Konsolidirana isporuka')),
    ]

    zone = models.ForeignKey(
        ColdChainZone, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sensor_readings'
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sensor_readings'
    )
    consolidated_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sensor_readings'
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='zone')
    timestamp = models.DateTimeField(verbose_name=_('Vrijeme ocitanja'))
    temperature = models.DecimalField(max_digits=5, decimal_places=1, verbose_name=_('Temperatura (C)'))
    humidity = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name=_('Vlaznost (%)'))

    # Automatski alert
    is_alert = models.BooleanField(default=False)
    alert_message = models.CharField(max_length=200, blank=True)

    # GPS (za transport)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Raw data od senzora
    raw_payload = models.JSONField(null=True, blank=True, verbose_name=_('Sirovi podaci senzora'))

    smart_box = models.ForeignKey(
        'SmartBox', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sensor_readings',
        verbose_name=_('Smart Box')
    )

    class Meta:
        verbose_name = _('Ocitanje senzora')
        verbose_name_plural = _('Ocitanja senzora')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['zone', '-timestamp']),
            models.Index(fields=['consolidated_delivery', '-timestamp']),
        ]

    def __str__(self):
        src = self.zone or self.vehicle or self.consolidated_delivery
        return f"{src} @ {self.timestamp:%H:%M} = {self.temperature}C"

    def save(self, *args, **kwargs):
        if self.zone and not self.is_alert:
            if self.temperature < self.zone.target_min_temp or self.temperature > self.zone.target_max_temp:
                self.is_alert = True
                self.alert_message = (
                    f'Temp {self.temperature}C izvan opsega '
                    f'({self.zone.target_min_temp}-{self.zone.target_max_temp}C)'
                )
        super().save(*args, **kwargs)


# ── Rollwagen (LIFO utovar) ─────────────────────────────────────
class Rollwagen(models.Model):
    """
    Kolica za LIFO utovar u kamion.
    Skladište slaže po load_order, vozač skenira QR kod pri ukrcaju.
    Veći load_order = ulazi u kamion prvi (na kraj), izlazi zadnji.
    """
    consolidated_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.CASCADE,
        related_name='rollwagens', verbose_name=_('Konsolidirana isporuka')
    )
    delivery_stop = models.ForeignKey(
        DeliveryStop, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rollwagens',
        verbose_name=_('Stanica dostave')
    )
    qr_code = models.CharField(max_length=100, unique=True, verbose_name='QR Kod')
    load_order = models.PositiveIntegerField(
        default=1, verbose_name=_('Redoslijed utovara (LIFO)'),
        help_text=_('Veći broj = tovari se prvi (kraj kamiona), istovaruje se zadnji')
    )
    is_loaded = models.BooleanField(default=False, verbose_name=_('Ukrcano u kamion'))
    loaded_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    # Genesis Scan: bind rollwagen to order at pack station
    bound_order = models.ForeignKey(
        'marketplace.MarketplaceOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rollwagens',
        verbose_name=_('Vezana narudzba')
    )
    packaging_count = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Ambalaza u rollwagenu'),
        help_text=_('{"ifco": 3, "smartbox": 1}')
    )
    packed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='packed_rollwagens',
        verbose_name=_('Pakirao')
    )
    packed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Rollwagen'
        verbose_name_plural = 'Rollwagen'
        ordering = ['-load_order']

    def __str__(self):
        stop_info = f"Stop {self.delivery_stop.stop_order}" if self.delivery_stop else "Unassigned"
        return f"RW-{self.qr_code} → {stop_info}"


# ── Razmjena ambalaže (Leergut / Ambalaža) ──────────────────────
class PackagingExchange(models.Model):
    """
    Evidencija ambalaže po stanici isporuke.
    Vozač unosi koliko je dostavio punih i koliko vratio praznih.
    Saldo = dug kupca (pozitivan = kupac duguje).
    """
    PACKAGING_TYPES = [
        ('ifco',          'IFCO Gajba'),
        ('euro_pallet',   'Europaleta'),
        ('chep',          'CHEP Paleta'),
        ('crate_plastic', 'Plastična gajba'),
        ('crate_wood',    'Drvena gajba'),
        ('other',         'Ostalo'),
    ]

    delivery_stop = models.ForeignKey(
        DeliveryStop, on_delete=models.CASCADE,
        related_name='packaging_exchanges', verbose_name=_('Stanica dostave')
    )
    packaging_type = models.CharField(
        max_length=50, choices=PACKAGING_TYPES,
        verbose_name=_('Tip ambalaže')
    )
    delivered_qty = models.PositiveIntegerField(default=0, verbose_name=_('Dostavljeno punih'))
    returned_qty = models.PositiveIntegerField(default=0, verbose_name=_('Vraćeno praznih'))
    balance = models.IntegerField(default=0, editable=False, verbose_name=_('Saldo (dug kupca)'))
    photo = models.ImageField(upload_to='delivery/packaging/', blank=True, null=True, verbose_name=_('Foto dokaz'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Razmjena ambalaže')
        verbose_name_plural = _('Razmjene ambalaže')

    def save(self, *args, **kwargs):
        self.balance = self.delivered_qty - self.returned_qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_packaging_type_display()}: {self.delivered_qty}↓ {self.returned_qty}↑ = {self.balance}"


# ── Smart Box (termo kutija sa senzorom i GPS-om) ───────────────
class SmartBox(models.Model):
    """
    Termo kutija za transport hrane.
    - Styropor: lokalna dostava (<15km, <2h)
    - Izolirana: srednja udaljenost, pasivno hlađenje
    - Aktivno hlađena: senzor + GPS, za Dalmaciju/duže rute

    EU 852/2004 + HR NN 81/13: neprekidni temp monitoring za hlađenu hranu.
    """
    BOX_TYPES = [
        ('styrofoam',   _('Styropor (lokalna dostava)')),
        ('insulated',   _('Izolirana kutija (srednja)')),
        ('active_cool', _('Aktivno hlađena (senzor+GPS)')),
    ]
    STATUS_CHOICES = [
        ('available',   _('Dostupna')),
        ('in_use',      _('U upotrebi')),
        ('returning',   _('Vraća se')),
        ('maintenance', _('Na servisu')),
    ]

    owner_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='smart_boxes', verbose_name=_('Vlasnik')
    )
    box_id = models.CharField(max_length=50, unique=True, verbose_name=_('Oznaka kutije'))
    box_type = models.CharField(max_length=20, choices=BOX_TYPES, default='styrofoam')
    qr_code = models.CharField(max_length=100, unique=True, verbose_name='QR kod')

    # Senzor
    has_sensor = models.BooleanField(default=False, verbose_name=_('Ima temperaturni senzor'))
    has_gps = models.BooleanField(default=False, verbose_name=_('Ima GPS tracker'))
    sensor_device_id = models.CharField(max_length=100, blank=True, verbose_name=_('ID senzora/GPS-a'))

    # Temperaturni opseg
    target_min_temp = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('2.0'), verbose_name=_('Min temp (°C)'))
    target_max_temp = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('8.0'), verbose_name=_('Max temp (°C)'))

    # Status i lokacija
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    haccp_status = models.CharField(max_length=20, choices=[
        ('ok', 'OK'),
        ('warning', 'Upozorenje'),
        ('critical', 'CRITICAL — lanac prekinut'),
        ('blocked', 'BLOKIRAN — ceka dispatchera'),
    ], default='ok')
    haccp_blocked_at = models.DateTimeField(null=True, blank=True)
    current_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='smart_boxes'
    )
    current_stop = models.ForeignKey(
        DeliveryStop, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='smart_boxes'
    )

    # Zadnje očitanje (cache za brzi prikaz)
    last_temp = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    last_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    last_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    last_reading_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Smart Box'
        verbose_name_plural = 'Smart Boxes'
        ordering = ['box_id']

    def __str__(self):
        return f"{self.box_id} ({self.get_box_type_display()}) — {self.get_status_display()}"

    @property
    def is_temp_ok(self):
        if self.last_temp is None:
            return None
        return self.target_min_temp <= self.last_temp <= self.target_max_temp

    def update_from_sensor(self, temp, lat=None, lng=None):
        from django.utils import timezone as tz
        self.last_temp = temp
        self.last_reading_at = tz.now()
        if lat:
            self.last_lat = lat
        if lng:
            self.last_lng = lng
        self.save(update_fields=['last_temp', 'last_lat', 'last_lng', 'last_reading_at'])

        # Automatski SensorReading zapis
        SensorReading.objects.create(
            consolidated_delivery=self.current_delivery,
            source='delivery',
            timestamp=tz.now(),
            temperature=temp,
            latitude=lat,
            longitude=lng,
            raw_payload={'smart_box': self.box_id},
        )


# ── Cijena dostave ──────────────────────────────────────────────
class DeliveryCostRule(models.Model):
    """
    Pravilo za izračun cijene dostave po regiji i metodi.
    Hub definira cijene, sustav automatski računa trošak.
    """
    REGION_CHOICES = [
        ('osijek_local',    _('Osijek lokalno (<15km)')),
        ('slavonija',       _('Slavonija (15-80km)')),
        ('dalmatia',        _('Dalmacija (80-400km)')),
        ('stuttgart_local', _('Stuttgart lokalno (<20km)')),
        ('bw_region',       _('Baden-Württemberg (20-100km)')),
    ]
    METHOD_CHOICES = [
        ('internal', _('Vlastita dostava')),
        ('taxi',     _('Taxi dostava')),
        ('crowd',    _('Crowd-shipping (Gepek)')),
        ('bus',      _('Autobusna linija')),
        ('courier',  _('Kurirska služba')),
    ]

    hub_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='delivery_cost_rules'
    )
    region = models.CharField(max_length=30, choices=REGION_CHOICES)
    delivery_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    base_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('2.00'), verbose_name=_('Osnovna cijena (€)'))
    per_km_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.50'), verbose_name=_('Cijena po km (€)'))
    min_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('15.00'), verbose_name=_('Min narudžba (€)'))
    max_distance_km = models.PositiveIntegerField(default=50, verbose_name=_('Max udaljenost (km)'))
    cold_chain_surcharge = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.50'), verbose_name=_('Dodatak hladni lanac (€)'))
    is_active = models.BooleanField(default=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Pravilo cijene dostave')
        verbose_name_plural = _('Pravila cijena dostave')
        unique_together = [('hub_company', 'region', 'delivery_method')]

    def __str__(self):
        return f"{self.get_region_display()} / {self.get_delivery_method_display()}: {self.base_fee}€ + {self.per_km_fee}€/km"

    def calculate(self, distance_km, needs_cold_chain=False):
        cost = self.base_fee + (self.per_km_fee * Decimal(str(distance_km)))
        if needs_cold_chain:
            cost += self.cold_chain_surcharge
        return round(cost, 2)


# ── HACCP Primopredajni zapis ───────────────────────────────────
class TransportHandoff(models.Model):
    """
    Zapis primopredaje hrane — EU 852/2004 zahtijeva sljedivost.
    Svaki put kad se roba preda drugoj osobi, bilježi se:
    - Temperatura, GPS, foto, potpis, HACCP lista
    """
    HANDOFF_TYPES = [
        ('hub_to_driver',      _('Hub → Vozač')),
        ('driver_to_customer', _('Vozač → Kupac')),
        ('customer_return',    _('Kupac → Povrat kutije')),
    ]

    handoff_type = models.CharField(max_length=20, choices=HANDOFF_TYPES)
    delivery_stop = models.ForeignKey(
        DeliveryStop, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='handoffs'
    )
    smart_box = models.ForeignKey(
        'SmartBox', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='handoffs'
    )
    consolidated_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.CASCADE,
        null=True, blank=True, related_name='handoffs'
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_handoffs'
    )

    # Mjerenja
    temperature_at_handoff = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name=_('Temp (°C)'))
    photo = models.ImageField(upload_to='delivery/handoffs/', blank=True, null=True)
    recipient_name = models.CharField(max_length=100, blank=True)

    # HACCP kontrolna lista
    haccp_checklist = models.JSONField(default=dict, blank=True, verbose_name=_('HACCP kontrolna lista'))
    # Očekivana struktura:
    # {
    #     "packaging_intact": true,      Ambalaža neoštećena
    #     "temp_in_range": true,         Temperatura u opsegu
    #     "vehicle_clean": true,         Vozilo čisto
    #     "no_cross_contamination": true, Bez křižne kontaminacije
    #     "delivery_time_ok": true,      Dostava unutar 2h
    # }

    notes = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Primopredajni zapis')
        verbose_name_plural = _('Primopredajni zapisi')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_handoff_type_display()} @ {self.created_at:%d.%m. %H:%M}"

    @property
    def is_compliant(self):
        """Provjeri da li su svi HACCP kriteriji zadovoljeni."""
        if not self.haccp_checklist:
            return None
        return all(self.haccp_checklist.values())


# ── Dispatch ponuda za taksiste/gepek vozače ────────────────────
class DispatchOffer(models.Model):
    """
    Ponuda koju hub šalje dostupnim vozačima (taxi, crowd).
    Vozač vidi: ruta, broj stanica, zarada, hladni lanac.
    """
    STATUS_CHOICES = [
        ('pending',   _('Ponuđeno')),
        ('accepted',  _('Prihvaćeno')),
        ('rejected',  _('Odbijeno')),
        ('expired',   _('Isteklo')),
        ('completed', _('Završeno')),
    ]

    consolidated_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.CASCADE,
        related_name='dispatch_offers'
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dispatch_offers'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    offered_price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_('Ponuđena cijena (€)'))
    driver_earnings = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), verbose_name=_('Zarada vozača (€)'))
    estimated_km = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal('0'))
    estimated_stops = models.PositiveIntegerField(default=1)
    pickup_address = models.CharField(max_length=300, blank=True)
    requires_cold_chain = models.BooleanField(default=False)

    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Dispatch ponuda')
        verbose_name_plural = _('Dispatch ponude')
        ordering = ['-created_at']

    def __str__(self):
        driver_name = self.driver.get_full_name() if self.driver else 'Neraspoređeno'
        return f"{self.consolidated_delivery} → {driver_name} ({self.offered_price}€)"

    def accept(self, driver_user):
        from django.utils import timezone as tz
        self.driver = driver_user
        self.status = 'accepted'
        self.accepted_at = tz.now()
        self.save()
        # Assign driver to delivery
        cd = self.consolidated_delivery
        cd.driver = driver_user
        cd.status = 'dispatched'
        cd.dispatched_at = tz.now()
        cd.save(update_fields=['driver', 'status', 'dispatched_at'])


# ── HACCP Incident (revizijski trag) ────────────────────────────
class HACCPIncident(models.Model):
    """
    Zapis o prekrsaju temperature u hladnom lancu.
    EU 852/2004, HR NN 81/13 — obavezan audit trail.

    Pravila:
    - sustained_breach: temp > max_temp kontinuirano > 10 minuta
    - critical_failure: temp > 15C odmah (nema odgode)
    - offline_retroactive: bulk ingest otkriva prosli prekrsaj
    """
    INCIDENT_TYPES = [
        ('sustained_breach', 'Sustained Breach (>10min)'),
        ('critical_failure', 'Critical Failure (>15C)'),
        ('offline_retroactive', 'Offline Retroactive Detection'),
    ]
    SEVERITY_CHOICES = [
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('blocked', 'Blocked'),
    ]
    HACCP_STATUS_CHOICES = [
        ('ok', 'OK'),
        ('warning', 'Upozorenje'),
        ('critical', 'CRITICAL — lanac prekinut'),
        ('blocked', 'BLOKIRAN — ceka dispatchera'),
    ]

    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='critical')

    smart_box = models.ForeignKey(
        SmartBox, on_delete=models.CASCADE,
        null=True, blank=True, related_name='haccp_incidents'
    )
    consolidated_delivery = models.ForeignKey(
        ConsolidatedDelivery, on_delete=models.CASCADE,
        null=True, blank=True, related_name='haccp_incidents'
    )

    breach_start = models.DateTimeField(verbose_name=_('Pocetak prekrsaja'))
    breach_end = models.DateTimeField(null=True, blank=True, verbose_name=_('Kraj prekrsaja'))
    max_temperature = models.DecimalField(max_digits=5, decimal_places=1, verbose_name=_('Max temp (C)'))
    duration_minutes = models.IntegerField(default=0, verbose_name=_('Trajanje prekrsaja (min)'))
    description = models.TextField(blank=True)

    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        'auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='resolved_haccp_incidents'
    )
    resolution_note = models.TextField(blank=True, verbose_name=_('Sto je poduzeto'))
    resolved_at = models.DateTimeField(null=True, blank=True)

    reading_ids = models.JSONField(default=list, blank=True, verbose_name=_('ID-jevi ocitanja'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'HACCP Incident'
        verbose_name_plural = 'HACCP Incidents'
        ordering = ['-created_at']

    def __str__(self):
        box = self.smart_box.box_id if self.smart_box else '?'
        return f"HACCP {self.get_incident_type_display()} — Box {box} @ {self.breach_start:%H:%M}"

    def resolve(self, user, note):
        from django.utils import timezone as tz
        self.is_resolved = True
        self.resolved_by = user
        self.resolution_note = note
        self.resolved_at = tz.now()
        self.save(update_fields=['is_resolved', 'resolved_by', 'resolution_note', 'resolved_at'])
        # Unblock SmartBox if all incidents resolved
        if self.smart_box:
            open_incidents = self.smart_box.haccp_incidents.filter(is_resolved=False).count()
            if open_incidents == 0:
                self.smart_box.haccp_status = 'ok'
                self.smart_box.haccp_blocked_at = None
                self.smart_box.save(update_fields=['haccp_status', 'haccp_blocked_at'])


# ── HACCP Analysis Engine ───────────────────────────────────────
def analyze_readings(smart_box, readings_qs=None):
    """
    Analizira ocitanja temperature za SmartBox i kreira HACCPIncident ako je potrebno.

    Pravila:
    1. SUSTAINED BREACH: temp > max_temp kontinuirano > 10 min -> incident
    2. CRITICAL FAILURE: temp > 15C -> instant incident
    3. Radi i retroaktivno (za bulk offline ingest)

    Args:
        smart_box: SmartBox instanca
        readings_qs: QuerySet ocitanja (default: sva za taj box, zadnjih 24h)

    Returns:
        list[HACCPIncident]: kreirani incidenti (ako ima)
    """
    from django.utils import timezone as tz
    from datetime import timedelta

    SUSTAINED_THRESHOLD_MIN = 10  # minuta
    CRITICAL_TEMP = Decimal('15.0')

    max_temp = smart_box.target_max_temp

    if readings_qs is None:
        cutoff = tz.now() - timedelta(hours=24)
        readings_qs = SensorReading.objects.filter(
            smart_box=smart_box, timestamp__gte=cutoff
        )

    readings = list(readings_qs.order_by('timestamp').values('id', 'timestamp', 'temperature'))
    if not readings:
        return []

    incidents = []

    # ── Critical Failure Check (instant, any reading > 15C) ──
    for r in readings:
        if r['temperature'] >= CRITICAL_TEMP:
            # Check if we already have a critical incident covering this timestamp
            existing = HACCPIncident.objects.filter(
                smart_box=smart_box,
                incident_type='critical_failure',
                breach_start__lte=r['timestamp'],
                created_at__gte=r['timestamp'] - timedelta(minutes=5),
            ).exists()
            if not existing:
                inc = HACCPIncident.objects.create(
                    incident_type='critical_failure',
                    severity='blocked',
                    smart_box=smart_box,
                    consolidated_delivery=smart_box.current_delivery,
                    breach_start=r['timestamp'],
                    max_temperature=r['temperature'],
                    duration_minutes=0,
                    description=f"CRITICAL: {r['temperature']}C (prag: {CRITICAL_TEMP}C) u {r['timestamp']:%H:%M}",
                    reading_ids=[r['id']],
                )
                incidents.append(inc)
                # Block the box immediately
                smart_box.haccp_status = 'blocked'
                smart_box.haccp_blocked_at = tz.now()
                smart_box.save(update_fields=['haccp_status', 'haccp_blocked_at'])

    # ── Sustained Breach Check (>max_temp for >10min) ──
    breach_start = None
    breach_readings = []
    breach_max = Decimal('0')

    for r in readings:
        if r['temperature'] > max_temp:
            if breach_start is None:
                breach_start = r['timestamp']
                breach_readings = []
                breach_max = Decimal('0')
            breach_readings.append(r['id'])
            if r['temperature'] > breach_max:
                breach_max = r['temperature']
        else:
            # Temp back to normal — check if breach was long enough
            if breach_start is not None:
                duration = (r['timestamp'] - breach_start).total_seconds() / 60
                if duration >= SUSTAINED_THRESHOLD_MIN and breach_max < CRITICAL_TEMP:
                    # Don't duplicate if critical already covers it
                    existing = HACCPIncident.objects.filter(
                        smart_box=smart_box,
                        breach_start=breach_start,
                        incident_type__in=['sustained_breach', 'offline_retroactive'],
                    ).exists()
                    if not existing:
                        inc_type = 'offline_retroactive' if len(readings) > 10 else 'sustained_breach'
                        inc = HACCPIncident.objects.create(
                            incident_type=inc_type,
                            severity='critical',
                            smart_box=smart_box,
                            consolidated_delivery=smart_box.current_delivery,
                            breach_start=breach_start,
                            breach_end=r['timestamp'],
                            max_temperature=breach_max,
                            duration_minutes=int(duration),
                            description=(
                                f"Temp > {max_temp}C neprekidno {int(duration)} min "
                                f"(max: {breach_max}C, {breach_start:%H:%M}-{r['timestamp']:%H:%M})"
                            ),
                            reading_ids=breach_readings,
                        )
                        incidents.append(inc)
                        if smart_box.haccp_status == 'ok':
                            smart_box.haccp_status = 'critical'
                            smart_box.save(update_fields=['haccp_status'])
            breach_start = None
            breach_readings = []
            breach_max = Decimal('0')

    # Handle case where breach is still ongoing at end of readings
    if breach_start is not None:
        last_r = readings[-1]
        duration = (last_r['timestamp'] - breach_start).total_seconds() / 60
        if duration >= SUSTAINED_THRESHOLD_MIN and breach_max < CRITICAL_TEMP:
            existing = HACCPIncident.objects.filter(
                smart_box=smart_box,
                breach_start=breach_start,
                incident_type__in=['sustained_breach', 'offline_retroactive'],
            ).exists()
            if not existing:
                inc_type = 'offline_retroactive' if len(readings) > 10 else 'sustained_breach'
                inc = HACCPIncident.objects.create(
                    incident_type=inc_type,
                    severity='critical',
                    smart_box=smart_box,
                    consolidated_delivery=smart_box.current_delivery,
                    breach_start=breach_start,
                    breach_end=last_r['timestamp'],
                    max_temperature=breach_max,
                    duration_minutes=int(duration),
                    description=(
                        f"Temp > {max_temp}C neprekidno {int(duration)} min "
                        f"(max: {breach_max}C, {breach_start:%H:%M}-{last_r['timestamp']:%H:%M}) — JOS TRAJE"
                    ),
                    reading_ids=breach_readings,
                )
                incidents.append(inc)
                smart_box.haccp_status = 'critical'
                smart_box.save(update_fields=['haccp_status'])

    return incidents


# ── Warehouse Pick & Pack ───────────────────────────────────
class PickWave(models.Model):
    """
    Wave picking: aggregates items across multiple orders for a route.
    Warehouse staff picks ALL tomatoes for Stuttgart route at once,
    then distributes to individual orders at pack station.
    """
    STATUS_CHOICES = [
        ('open', _('Otvorena')),
        ('picking', _('U komisioniranju')),
        ('picked', _('Prikupljeno')),
        ('packing', _('Pakiranje')),
        ('packed', _('Zapakirano')),
        ('loaded', _('Utovareno')),
    ]

    wave_number = models.CharField(max_length=30, unique=True, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='pick_waves', verbose_name=_('Hub tvrtka')
    )
    route = models.ForeignKey(
        DeliveryRoute, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pick_waves',
        verbose_name=_('Ruta')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    picker = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pick_waves',
        verbose_name=_('Skladistar')
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Pick Wave')
        verbose_name_plural = _('Pick Waves')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.wave_number} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.wave_number:
            from django.utils import timezone
            import random
            ts = timezone.now().strftime('%y%m%d%H%M')
            self.wave_number = f"WV-{ts}-{random.randint(10,99)}"
        super().save(*args, **kwargs)


class PickTask(models.Model):
    """
    Individual pick task within a wave.
    Aggregated: product X, total 50kg across 5 orders.
    """
    STATUS_CHOICES = [
        ('pending', _('Ceka')),
        ('picked', _('Prikupljeno')),
        ('packed', _('Zapakirano')),
    ]

    wave = models.ForeignKey(
        PickWave, on_delete=models.CASCADE,
        related_name='tasks', verbose_name=_('Wave')
    )
    product = models.ForeignKey(
        'marketplace.MarketplaceProduct', on_delete=models.CASCADE,
        verbose_name=_('Proizvod')
    )
    total_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Ukupna kolicina za wave')
    )
    picked_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name=_('Stvarno prikupljeno')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    location_hint = models.CharField(max_length=100, blank=True, verbose_name=_('Lokacija u skladistu'))

    class Meta:
        verbose_name = _('Pick Task')
        verbose_name_plural = _('Pick Tasks')

    def __str__(self):
        return f"{self.product.name}: {self.total_quantity} ({self.get_status_display()})"


# ── Zona dostave (retail / pekara) ──────────────────────────────
class DeliveryZone(models.Model):
    """
    Zona dostave za retail kupce (pekare, webshop, itd.).
    Definira cijenu, vremenski prozor, dane i besplatnu dostavu.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='delivery_zones', verbose_name=_('Tvrtka')
    )
    name = models.CharField(max_length=100, verbose_name=_('Naziv zone'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    price = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name=_('Cijena dostave (EUR)')
    )
    min_distance_km = models.DecimalField(
        max_digits=5, decimal_places=1, default=0,
        verbose_name=_('Min udaljenost (km)')
    )
    max_distance_km = models.DecimalField(
        max_digits=5, decimal_places=1, default=0,
        verbose_name=_('Max udaljenost (km)')
    )
    free_delivery_above = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name=_('Besplatna dostava iznad (EUR)'),
        help_text=_('Ako narudzba prelazi ovaj iznos, dostava je besplatna.')
    )
    delivery_time_from = models.TimeField(
        null=True, blank=True, verbose_name=_('Dostava od')
    )
    delivery_time_to = models.TimeField(
        null=True, blank=True, verbose_name=_('Dostava do')
    )
    delivery_days = models.CharField(
        max_length=50, default='mon,tue,wed,thu,fri,sat',
        verbose_name=_('Dani dostave'),
        help_text=_('Odvojeno zarezima: mon,tue,wed,thu,fri,sat,sun')
    )
    postal_codes = models.TextField(
        blank=True, verbose_name=_('Postanski brojevi'),
        help_text=_('Odvojeno zarezima, npr: 31431,31400,31000')
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    sort_order = models.IntegerField(default=0, verbose_name=_('Redoslijed'))
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['sort_order', 'price']
        verbose_name = _('Zona dostave')
        verbose_name_plural = _('Zone dostave')

    def __str__(self):
        return f"{self.name} — {self.price} EUR"

    def is_free_for(self, order_total):
        """Provjeri je li dostava besplatna za dani iznos narudzbe."""
        if self.free_delivery_above and order_total >= self.free_delivery_above:
            return True
        return False

    def get_price_for(self, order_total):
        """Vrati stvarnu cijenu dostave (0 ako besplatna)."""
        if self.is_free_for(order_total):
            return Decimal('0.00')
        return self.price

    @property
    def time_window(self):
        if self.delivery_time_from and self.delivery_time_to:
            return f"{self.delivery_time_from.strftime('%H:%M')} - {self.delivery_time_to.strftime('%H:%M')}"
        return ''

    @property
    def days_display(self):
        day_map = {
            'mon': 'Pon', 'tue': 'Uto', 'wed': 'Sri',
            'thu': 'Cet', 'fri': 'Pet', 'sat': 'Sub', 'sun': 'Ned'
        }
        days = [d.strip() for d in self.delivery_days.split(',') if d.strip()]
        return ', '.join(day_map.get(d, d) for d in days)


# ═══════════════════════════════════════════════════════════════
# TRANSPORT MODULE — Faza 1
# ═══════════════════════════════════════════════════════════════

class VehicleDocument(models.Model):
    """Dokumenti vozila — registracija, ATP, osiguranje, servis, tahograf."""
    DOC_TYPES = [
        ('registration', _('Prometna dozvola')),
        ('atp_certificate', _('ATP certifikat (temp. prijevoz)')),
        ('insurance', _('Obvezno osiguranje')),
        ('casco', _('Kasko osiguranje')),
        ('cmr_insurance', _('CMR osiguranje prijevoznika')),
        ('technical_inspection', _('Tehnički pregled')),
        ('tachograph_calibration', _('Baždarenje tahografa')),
        ('community_licence', _('Licenca Zajednice (EU)')),
        ('other', _('Ostalo')),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES, verbose_name=_('Tip dokumenta'))
    doc_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj dokumenta'))
    valid_from = models.DateField(verbose_name=_('Vrijedi od'))
    valid_until = models.DateField(verbose_name=_('Vrijedi do'))
    file = models.FileField(upload_to='vehicles/docs/%Y/', blank=True, verbose_name=_('Datoteka'))
    reminder_days = models.PositiveSmallIntegerField(default=30, verbose_name=_('Podsjetnik (dana prije)'))
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Dokument vozila')
        verbose_name_plural = _('Dokumenti vozila')
        ordering = ['valid_until']

    def __str__(self):
        return '%s — %s (do %s)' % (self.vehicle.plate_number, self.get_doc_type_display(), self.valid_until)

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.valid_until < timezone.now().date()

    @property
    def days_until_expiry(self):
        from django.utils import timezone
        return (self.valid_until - timezone.now().date()).days

    @property
    def needs_renewal_alert(self):
        d = self.days_until_expiry
        return 0 < d <= self.reminder_days


class DriverDocument(models.Model):
    """Dokumenti vozača — vozačka, CPC, ADR, potvrda za non-EU vozače."""
    DOC_TYPES = [
        ('driving_licence', _('Vozačka dozvola')),
        ('cpc_card', _('CPC kartica (kvalifikacija)')),
        ('adr_cert', _('ADR certifikat (opasne tvari)')),
        ('driver_attestation', _('Potvrda za vozače (non-EU)')),
        ('health_cert', _('Liječnička potvrda')),
        ('tachograph_card', _('Tahograf kartica')),
        ('id_passport', _('Osobna / Putovnica')),
        ('work_permit', _('Radna dozvola')),
        ('posting_declaration', _('Izjava o upućivanju (DE Posting)')),
        ('other', _('Ostalo')),
    ]

    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='driver_documents')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='driver_documents',
                                null=True, blank=True)
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES, verbose_name=_('Tip dokumenta'))
    doc_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj dokumenta'))
    categories = models.CharField(max_length=20, blank=True, verbose_name=_('Kategorije'),
                                   help_text=_('B, C, CE...'))
    issuing_country = models.CharField(max_length=5, blank=True, verbose_name=_('Država izdavanja'))
    valid_from = models.DateField(null=True, blank=True, verbose_name=_('Vrijedi od'))
    valid_until = models.DateField(verbose_name=_('Vrijedi do'))
    file = models.FileField(upload_to='drivers/docs/%Y/', blank=True, verbose_name=_('Datoteka'))
    reminder_days = models.PositiveSmallIntegerField(default=30, verbose_name=_('Podsjetnik (dana prije)'))
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Dokument vozača')
        verbose_name_plural = _('Dokumenti vozača')
        ordering = ['valid_until']

    def __str__(self):
        return '%s — %s (do %s)' % (self.driver.get_full_name(), self.get_doc_type_display(), self.valid_until)

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.valid_until < timezone.now().date()

    @property
    def days_until_expiry(self):
        from django.utils import timezone
        return (self.valid_until - timezone.now().date()).days

    @property
    def is_non_eu_driver(self):
        eu_countries = {'HR','DE','AT','SI','HU','IT','FR','ES','NL','BE','CZ','SK','PL','RO','BG'}
        return self.issuing_country and self.issuing_country not in eu_countries


class TransportOrder(models.Model):
    """
    Centralni nalog za prijevoz — spaja vozilo, vozača, rutu, CMR, HACCP.
    Jedinstven dokument koji pokriva sve scenarije:
    - Termo kutije (hrana po HR)
    - Kombi prijevoz (DE↔HR↔BA↔RS)
    - Terenska prodaja (POS field session)
    """
    TRANSPORT_TYPES = [
        ('food_local', _('Hrana — lokalna dostava')),
        ('food_regional', _('Hrana — regionalna (do 48h)')),
        ('food_international', _('Hrana — međunarodni')),
        ('freight_eu', _('Teret — EU')),
        ('freight_non_eu', _('Teret — izvan EU (BA/RS/ME)')),
        ('moving', _('Selidba / kombi prijevoz')),
        ('field_sales', _('Terenska prodaja')),
    ]
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('planned', _('Planirano')),
        ('docs_check', _('Provjera dokumenata')),
        ('loading', _('Utovar')),
        ('in_transit', _('U tranzitu')),
        ('border_crossing', _('Carinski prijelaz')),
        ('unloading', _('Istovar')),
        ('delivered', _('Isporučeno')),
        ('cancelled', _('Otkazano')),
    ]
    COUNTRY_CHOICES = [
        ('HR', 'Hrvatska'), ('DE', 'Njemačka'), ('AT', 'Austrija'),
        ('SI', 'Slovenija'), ('HU', 'Mađarska'), ('BA', 'Bosna i Hercegovina'),
        ('RS', 'Srbija'), ('ME', 'Crna Gora'), ('IT', 'Italija'),
        ('CZ', 'Češka'), ('SK', 'Slovačka'), ('PL', 'Poljska'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='transport_orders')
    order_number = models.CharField(max_length=30, unique=True, verbose_name=_('Broj naloga'))
    transport_type = models.CharField(max_length=25, choices=TRANSPORT_TYPES, verbose_name=_('Tip prijevoza'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Vozilo i vozač
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_orders')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='transport_orders_as_driver')

    # Ruta
    origin_address = models.CharField(max_length=300, verbose_name=_('Polazište'))
    origin_country = models.CharField(max_length=5, choices=COUNTRY_CHOICES, default='HR')
    destination_address = models.CharField(max_length=300, verbose_name=_('Odredište'))
    destination_country = models.CharField(max_length=5, choices=COUNTRY_CHOICES, default='HR')
    via_countries = models.JSONField(default=list, blank=True, verbose_name=_('Tranzitne države'),
                                     help_text=_('["AT","HU"] za rutu kroz Austriju i Mađarsku'))
    estimated_km = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True,
                                        verbose_name=_('Procjena km'))

    # Datumi
    planned_departure = models.DateTimeField(verbose_name=_('Planirani polazak'))
    planned_arrival = models.DateTimeField(verbose_name=_('Planirani dolazak'))
    actual_departure = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)

    # Povezani dokumenti (auto-generirani)
    cmr = models.ForeignKey('documents.CMR', on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='transport_orders')
    otpremnica = models.ForeignKey('documents.Otpremnica', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='transport_orders')
    delivery_route = models.ForeignKey(DeliveryRoute, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='transport_orders')
    consolidated_delivery = models.ForeignKey(ConsolidatedDelivery, on_delete=models.SET_NULL, null=True, blank=True,
                                               related_name='transport_orders')

    # Temperatura (za hranu)
    requires_cold_chain = models.BooleanField(default=False, verbose_name=_('Zahtijeva hladni lanac'))
    temp_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                    verbose_name=_('Min temp (°C)'))
    temp_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                    verbose_name=_('Max temp (°C)'))

    # Teret
    cargo_description = models.TextField(blank=True, verbose_name=_('Opis tereta'))
    total_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                           verbose_name=_('Ukupna težina (kg)'))
    total_volume_m3 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                           verbose_name=_('Ukupni volumen (m³)'))
    package_count = models.PositiveIntegerField(default=1, verbose_name=_('Broj koleta'))

    # Financije
    fuel_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Trošak goriva'))
    toll_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Cestarina'))
    other_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Ostali troškovi'))
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Ukupni trošak'))
    client_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name=_('Cijena za klijenta'))

    # Zakonske provjere (AI kontrola)
    licence_verified = models.BooleanField(default=False, verbose_name=_('Licenca Zajednice ✓'))
    driver_cert_verified = models.BooleanField(default=False, verbose_name=_('Potvrda za vozača ✓'))
    posting_declared = models.BooleanField(default=False, verbose_name=_('Posting declaration ✓'))
    posting_document = models.ForeignKey(DriverDocument, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='posting_orders', verbose_name=_('Posting Declaration dokument'),
                                          help_text=_('FK na DriverDocument tipa posting_declaration s IMI referencom'))
    atp_valid = models.BooleanField(default=False, verbose_name=_('ATP certifikat ✓'))
    customs_docs_ready = models.BooleanField(default=False, verbose_name=_('Carinski dokumenti ✓'))
    cabotage_check_passed = models.BooleanField(default=False, verbose_name=_('Kabotaža provjera ✓'))

    # Klijent / naručitelj
    client_name = models.CharField(max_length=200, blank=True, verbose_name=_('Naručitelj'))
    client_phone = models.CharField(max_length=30, blank=True)
    client_reference = models.CharField(max_length=50, blank=True, verbose_name=_('Referenca naručitelja'))

    # Tracking
    tracking_token = models.CharField(max_length=32, unique=True, blank=True)

    notes = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='created_transport_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Nalog za prijevoz')
        verbose_name_plural = _('Nalozi za prijevoz')
        ordering = ['-planned_departure']

    def __str__(self):
        return '%s %s→%s (%s)' % (self.order_number, self.origin_country, self.destination_country, self.get_status_display())

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_number()
        if not self.tracking_token:
            import uuid
            self.tracking_token = uuid.uuid4().hex[:16]
        # Auto-calculate total cost only from sub-costs (ne pregazi ručno setiran total)
        auto_total = (self.fuel_cost or 0) + (self.toll_cost or 0) + (self.other_cost or 0)
        if auto_total > 0 or not self.total_cost:
            self.total_cost = auto_total
        super().save(*args, **kwargs)

    def _generate_number(self):
        from django.utils import timezone
        year = timezone.now().year
        last = TransportOrder.objects.filter(
            order_number__startswith='TO-%d-' % year
        ).order_by('-order_number').first()
        seq = 1
        if last:
            try:
                seq = int(last.order_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                pass
        return 'TO-%d-%04d' % (year, seq)

    @property
    def is_international(self):
        return self.origin_country != self.destination_country

    @property
    def crosses_eu_border(self):
        non_eu = {'BA', 'RS', 'ME'}
        all_countries = {self.origin_country, self.destination_country} | set(self.via_countries or [])
        return bool(all_countries & non_eu)

    @property
    def needs_posting_declaration(self):
        """DE zahtijeva Posting Declaration za sve upućene radnike."""
        return 'DE' in {self.origin_country, self.destination_country} | set(self.via_countries or [])

    @property
    def profit(self):
        return self.client_price - self.total_cost

    def verify_documents(self):
        """AI provjera svih dokumenata prije polaska."""
        from django.utils import timezone
        today = timezone.now().date()
        issues = []

        # 1. Vozilo
        if self.vehicle:
            # ATP
            if self.requires_cold_chain:
                atp = VehicleDocument.objects.filter(
                    vehicle=self.vehicle, doc_type='atp_certificate',
                    valid_until__gte=today
                ).first()
                self.atp_valid = bool(atp)
                if not atp:
                    issues.append('ATP certifikat istekao ili ne postoji')

            # Licenca Zajednice (za međunarodni)
            if self.is_international:
                lic = VehicleDocument.objects.filter(
                    vehicle=self.vehicle, doc_type='community_licence',
                    valid_until__gte=today
                ).first()
                self.licence_verified = bool(lic)
                if not lic:
                    issues.append('Licenca Zajednice nije validna')

            # Registracija
            reg = VehicleDocument.objects.filter(
                vehicle=self.vehicle, doc_type='registration',
                valid_until__gte=today
            ).first()
            if not reg:
                issues.append('Prometna dozvola istekla')

        # 2. Vozač
        if self.driver:
            # Vozačka dozvola
            dl = DriverDocument.objects.filter(
                driver=self.driver, doc_type='driving_licence',
                valid_until__gte=today
            ).first()
            if not dl:
                issues.append('Vozačka dozvola istekla')

            # Potvrda za non-EU vozače — obavezna za SVAKI međunarodni prijevoz
            if self.is_international or self.crosses_eu_border:
                # Provjeri je li vozač non-EU (po bilo kojem dokumentu)
                is_non_eu = False
                if dl and dl.is_non_eu_driver:
                    is_non_eu = True
                else:
                    any_non_eu = DriverDocument.objects.filter(
                        driver=self.driver, issuing_country__in=['BA','RS','ME','XK','AL','MK']
                    ).exists()
                    if any_non_eu:
                        is_non_eu = True

                if is_non_eu:
                    att = DriverDocument.objects.filter(
                        driver=self.driver, doc_type='driver_attestation',
                        valid_until__gte=today
                    ).first()
                    if att:
                        self.driver_cert_verified = True
                    else:
                        issues.append('Non-EU vozač nema Potvrdu za vozače')

        # 3. Posting declaration (DE)
        if self.needs_posting_declaration:
            if not self.posting_declared:
                issues.append('Potrebna Posting Declaration za DE')

        # 4. Carinski dokumenti (BA/RS)
        if self.crosses_eu_border:
            if not self.customs_docs_ready:
                issues.append('Carinski dokumenti nisu spremni (T1/T2)')

        self.save(update_fields=[
            'atp_valid', 'licence_verified', 'driver_cert_verified',
            'posting_declared', 'customs_docs_ready',
        ])

        return issues


class TachographEntry(models.Model):
    """Dnevna evidencija tahografa — zakonski obavezno."""
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tachograph_entries')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='tachograph_entries')
    transport_order = models.ForeignKey(TransportOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='tachograph_entries')
    date = models.DateField(verbose_name=_('Datum'))
    driving_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Vožnja (min)'))
    other_work_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Ostali rad (min)'))
    availability_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Raspoloživost (min)'))
    rest_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Odmor (min)'))
    odometer_start = models.PositiveIntegerField(default=0, verbose_name=_('km start'))
    odometer_end = models.PositiveIntegerField(default=0, verbose_name=_('km kraj'))
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Tahograf zapis')
        verbose_name_plural = _('Tahograf zapisi')
        unique_together = [('driver', 'date')]
        ordering = ['-date']

    def __str__(self):
        return '%s %s — %d min vožnje' % (self.driver.get_full_name(), self.date, self.driving_minutes)

    @property
    def driving_hours(self):
        return self.driving_minutes / 60

    @property
    def km_driven(self):
        return self.odometer_end - self.odometer_start

    @property
    def daily_driving_exceeded(self):
        """Max 9h (540 min), iznimno 10h (600 min) 2x/tjedan."""
        return self.driving_minutes > 540

    @property
    def break_violation(self):
        """Pauza 45 min obavezna nakon 4.5h (270 min) vožnje."""
        return self.driving_minutes > 270 and self.rest_minutes < 45


class FuelEntry(models.Model):
    """Evidencija goriva po vozilu."""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='fuel_entries')
    transport_order = models.ForeignKey(TransportOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='fuel_entries')
    date = models.DateTimeField(verbose_name=_('Datum'))
    liters = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_('Litara'))
    price_per_liter = models.DecimalField(max_digits=6, decimal_places=3, verbose_name=_('Cijena/L'))
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Ukupno'))
    odometer_km = models.PositiveIntegerField(verbose_name=_('Kilometraža'))
    fuel_station = models.CharField(max_length=100, blank=True, verbose_name=_('Postaja'))
    country = models.CharField(max_length=5, default='HR', verbose_name=_('Država'))
    receipt_photo = models.ImageField(upload_to='fuel/%Y/%m/', blank=True, verbose_name=_('Foto računa'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Gorivo')
        verbose_name_plural = _('Gorivo')
        ordering = ['-date']

    def __str__(self):
        return '%s %s — %.1fL (%.2f EUR)' % (self.vehicle.plate_number, self.date.strftime('%d.%m.'), self.liters, self.total_cost)

    def save(self, *args, **kwargs):
        self.total_cost = self.liters * self.price_per_liter
        super().save(*args, **kwargs)
