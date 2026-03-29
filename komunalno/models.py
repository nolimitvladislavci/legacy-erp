from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from core.managers import CompanyManager
from borg_ops.mixins import FSMMixin


# ═══════════════════════════════════════════════════════
# ZELENI OTOK / RECIKLAŽNO DVORIŠTE
# ═══════════════════════════════════════════════════════

class WasteStation(models.Model):
    """
    Zeleni otok ili Reciklažno dvorište.
    Jedna općina može imati više lokacija.
    """
    TYPE_CHOICES = [
        ('green_island', _('Zeleni otok')),
        ('recycling_yard', _('Reciklažno dvorište')),
        ('collection_center', _('Sabirno mjesto')),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='waste_stations'
    )
    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    station_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='recycling_yard')
    address = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa'))
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    working_hours = models.CharField(max_length=200, blank=True,
        verbose_name=_('Radno vrijeme'),
        help_text=_('npr. Pon-Pet 07-15, Sub 08-12'))
    is_active = models.BooleanField(default=True)
    operator = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('Zaduženi operater')
    )
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Reciklažno dvorište')
        verbose_name_plural = _('Reciklažna dvorišta')

    def __str__(self):
        return f'{self.name} ({self.get_station_type_display()})'


class WasteCategory(models.Model):
    """
    Ključni broj otpada prema Katalogu otpada (NN 90/15).
    Npr. 20 01 36 = Odbačena električna/elektronička oprema.
    """
    key_number = models.CharField(max_length=10, unique=True,
        verbose_name=_('Ključni broj'),
        help_text=_('Format: XX YY ZZ (npr. 20 01 36)'))
    name = models.CharField(max_length=300, verbose_name=_('Naziv otpada'))
    category_group = models.CharField(max_length=100, blank=True,
        verbose_name=_('Grupa'),
        help_text=_('npr. Komunalni otpad, Građevinski, EE otpad'))
    is_hazardous = models.BooleanField(default=False, verbose_name=_('Opasni otpad'))
    unit = models.CharField(max_length=10, default='kg', verbose_name=_('Jed. mjere'))
    # Defaultna kvota (može se override-ati per-općina)
    default_annual_quota = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Defaultna godišnja kvota'),
        help_text=_('0 = bez limita'))
    price_per_unit_over_quota = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_('Cijena/jed. iznad kvote (EUR)'))
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _('Kategorija otpada')
        verbose_name_plural = _('Kategorije otpada')
        ordering = ['key_number']

    def __str__(self):
        return f'{self.key_number} — {self.name}'


class CitizenCard(models.Model):
    """
    Iskaznica građanina za pristup reciklažnom dvorištu.
    Veza na Partners (kućanstvo/osoba).
    QR kod na iskaznici = brzi scan na ulazu.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='citizen_cards'
    )
    partner = models.ForeignKey(
        'partners.Partner', on_delete=models.CASCADE,
        related_name='citizen_cards',
        verbose_name=_('Građanin/Kućanstvo')
    )
    card_number = models.CharField(max_length=30, verbose_name=_('Broj iskaznice'))
    address = models.CharField(max_length=300, blank=True,
        verbose_name=_('Adresa kućanstva'))
    household_members = models.PositiveSmallIntegerField(
        default=1, verbose_name=_('Broj članova kućanstva'))
    is_active = models.BooleanField(default=True)
    issued_date = models.DateField(default=timezone.localdate)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Iskaznica građanina')
        verbose_name_plural = _('Iskaznice građana')
        unique_together = [('company', 'card_number')]

    def __str__(self):
        return f'{self.partner.name} [{self.card_number}]'

    def get_quota_usage(self, category, year=None):
        """Koliko je građanin donio ove godine za danu kategoriju."""
        year = year or timezone.localdate().year
        used = WasteDelivery.objects.filter(
            citizen=self,
            category=category,
            delivery_date__year=year,
            status='confirmed'
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or Decimal('0')
        return used

    def get_remaining_quota(self, category, year=None):
        """Koliko još može donijeti."""
        quota = self._get_quota(category)
        if quota <= 0:
            return None  # Bez limita
        used = self.get_quota_usage(category, year)
        return max(Decimal('0'), quota - used)

    def _get_quota(self, category):
        """Dohvati kvotu — specifična za općinu ili default."""
        try:
            override = AnnualQuota.objects.get(
                company=self.company, category=category,
                year=timezone.localdate().year
            )
            return override.quota
        except AnnualQuota.DoesNotExist:
            return category.default_annual_quota


class AnnualQuota(models.Model):
    """
    Godišnja kvota po kategoriji — override defaulta iz WasteCategory.
    Svaka općina može imati vlastite limite.
    """
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    category = models.ForeignKey(WasteCategory, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(default=2026)
    quota = models.DecimalField(max_digits=10, decimal_places=2,
        verbose_name=_('Kvota (kg ili kom)'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Godišnja kvota')
        verbose_name_plural = _('Godišnje kvote')
        unique_together = [('company', 'category', 'year')]

    def __str__(self):
        return f'{self.category.key_number} — {self.quota} {self.category.unit} ({self.year})'


class WasteDelivery(models.Model):
    """
    Zapis dolaska građanina — jezgra sustava.
    Operater na reciklažnom dvorištu:
    1. Skenira QR iskaznice
    2. Odabere kategoriju otpada
    3. Unese količinu (vaga ili ručno)
    4. Sustav provjeri kvotu
    5. Ako prekoračenje → POS naplata
    """
    STATUS_CHOICES = [
        ('pending', _('U obradi')),
        ('confirmed', _('Potvrđeno')),
        ('rejected', _('Odbijeno')),
        ('invoiced', _('Naplaćeno (prekoračenje)')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    station = models.ForeignKey(
        WasteStation, on_delete=models.CASCADE,
        related_name='deliveries', verbose_name=_('Dvorište')
    )
    citizen = models.ForeignKey(
        CitizenCard, on_delete=models.CASCADE,
        related_name='deliveries', verbose_name=_('Građanin')
    )
    category = models.ForeignKey(
        WasteCategory, on_delete=models.CASCADE,
        related_name='deliveries', verbose_name=_('Vrsta otpada')
    )

    delivery_date = models.DateTimeField(default=timezone.now, verbose_name=_('Datum/vrijeme'))
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name=_('Količina'))
    unit = models.CharField(max_length=10, default='kg')

    # Kvota provjera
    quota_before = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Preostala kvota prije'))
    over_quota = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Prekoračenje'))
    charge_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0,
        verbose_name=_('Naknada za prekoračenje (EUR)'))

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    operator = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Operater'))
    notes = models.CharField(max_length=500, blank=True)
    # e-ONTO
    onto_exported = models.BooleanField(default=False, verbose_name=_('Poslano u e-ONTO'))
    onto_export_date = models.DateTimeField(null=True, blank=True)

    objects = CompanyManager()

    class Meta:
        verbose_name = _('Zaprimanje otpada')
        verbose_name_plural = _('Zaprimanja otpada')
        ordering = ['-delivery_date']

    def __str__(self):
        return f'{self.citizen.partner.name} — {self.category.key_number} — {self.quantity}{self.unit}'

    def process_delivery(self):
        """
        Procesira dostavu: provjeri kvotu, izračunaj naknadu.
        Poziva se iz view-a nakon unosa.
        """
        remaining = self.citizen.get_remaining_quota(self.category)
        self.unit = self.category.unit

        if remaining is None:
            # Bez limita
            self.quota_before = Decimal('0')
            self.over_quota = Decimal('0')
            self.charge_amount = Decimal('0')
        else:
            self.quota_before = remaining
            if self.quantity > remaining:
                self.over_quota = self.quantity - remaining
                self.charge_amount = self.over_quota * self.category.price_per_unit_over_quota
            else:
                self.over_quota = Decimal('0')
                self.charge_amount = Decimal('0')

        self.status = 'confirmed'
        self.save()
        return self


# ═══════════════════════════════════════════════════════
# KOMUNALNI REDAR
# ═══════════════════════════════════════════════════════

class IllegalDumpReport(FSMMixin, models.Model):
    """
    Prijava divljeg odlagališta.
    Redar na terenu: slika, GPS, opis → radni nalog za čišćenje.
    """
    TRANSITIONS = {
        'reported':   ['investigating', 'rejected'],
        'investigating': ['work_order_created', 'rejected'],
        'work_order_created': ['cleaned'],
        'cleaned':    ['verified'],
        'verified':   [],
        'rejected':   [],
    }
    STATUS_CHOICES = [
        ('reported',           _('Prijavljeno')),
        ('investigating',      _('U istrazi')),
        ('work_order_created', _('Nalog kreiran')),
        ('cleaned',            _('Očišćeno')),
        ('verified',           _('Verificirano')),
        ('rejected',           _('Odbijeno')),
    ]
    PRIORITY_CHOICES = [
        ('low',    _('Nisko')),
        ('medium', _('Srednje')),
        ('high',   _('Visoko')),
        ('urgent', _('Hitno')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='reported')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    # Lokacija
    location_description = models.CharField(max_length=500, verbose_name=_('Opis lokacije'))
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    address = models.CharField(max_length=300, blank=True)

    # Sadržaj
    waste_description = models.TextField(verbose_name=_('Opis otpada'))
    estimated_volume = models.CharField(max_length=50, blank=True,
        verbose_name=_('Procjena obujma'),
        help_text=_('npr. ~2m³, puna prikolica'))
    is_hazardous = models.BooleanField(default=False, verbose_name=_('Opasni otpad'))

    # Slike
    photo_1 = models.ImageField(upload_to='komunalno/dumps/%Y/%m/', blank=True)
    photo_2 = models.ImageField(upload_to='komunalno/dumps/%Y/%m/', blank=True)
    photo_3 = models.ImageField(upload_to='komunalno/dumps/%Y/%m/', blank=True)

    # Počinitelj
    suspected_source = models.CharField(max_length=300, blank=True,
        verbose_name=_('Mogući počinitelj'))
    fine_issued = models.BooleanField(default=False)
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Radni nalog
    work_order = models.ForeignKey(
        'work_orders.WorkOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dump_reports'
    )

    # Meta
    reported_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dump_reports',
        verbose_name=_('Prijavio'))
    reported_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Divlje odlagalište')
        verbose_name_plural = _('Divlja odlagališta')
        ordering = ['-reported_at']

    def __str__(self):
        return f'Divlje odlagalište — {self.location_description[:50]}'

    def _on_transition(self, old_status, new_status, user=None):
        if new_status == 'verified':
            self.resolved_at = timezone.now()
            self.save(update_fields=['resolved_at'])


# ═══════════════════════════════════════════════════════
# JAVNA RASVJETA
# ═══════════════════════════════════════════════════════

class StreetLight(models.Model):
    """Stup javne rasvjete — asset pod upravljanjem općine."""
    LAMP_CHOICES = [
        ('led', 'LED'),
        ('sodium', 'Natrijeva (HPS)'),
        ('metal_halide', 'Metal-halogena'),
        ('mercury', 'Živina (zamijeni!)'),
        ('unknown', 'Nepoznato'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    pole_number = models.CharField(max_length=30, verbose_name=_('Broj stupa'))
    street = models.CharField(max_length=200, verbose_name=_('Ulica'))
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lamp_type = models.CharField(max_length=20, choices=LAMP_CHOICES, default='unknown')
    wattage = models.PositiveSmallIntegerField(default=0, verbose_name=_('Snaga (W)'))
    last_replaced = models.DateField(null=True, blank=True, verbose_name=_('Zadnja zamjena'))
    is_functional = models.BooleanField(default=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Javna rasvjeta')
        verbose_name_plural = _('Javna rasvjeta')
        unique_together = [('company', 'pole_number')]

    def __str__(self):
        return f'Stup {self.pole_number} — {self.street}'


class LightFaultReport(FSMMixin, models.Model):
    """Prijava kvara javne rasvjete — građanin ili redar."""
    TRANSITIONS = {
        'reported':  ['assigned', 'rejected'],
        'assigned':  ['in_progress'],
        'in_progress': ['fixed'],
        'fixed':     ['verified'],
        'verified':  [],
        'rejected':  [],
    }
    STATUS_CHOICES = [
        ('reported',    _('Prijavljeno')),
        ('assigned',    _('Dodijeljeno')),
        ('in_progress', _('U popravku')),
        ('fixed',       _('Popravljeno')),
        ('verified',    _('Verificirano')),
        ('rejected',    _('Odbijeno')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    light = models.ForeignKey(
        StreetLight, on_delete=models.CASCADE,
        related_name='fault_reports', verbose_name=_('Stup'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='reported')
    description = models.TextField(blank=True, verbose_name=_('Opis kvara'))
    photo = models.ImageField(upload_to='komunalno/lights/%Y/%m/', blank=True)
    reported_by_citizen = models.CharField(max_length=200, blank=True,
        verbose_name=_('Prijavio građanin (ime/telefon)'))
    reported_at = models.DateTimeField(default=timezone.now)
    assigned_to = models.CharField(max_length=200, blank=True,
        verbose_name=_('Dodijeleno koncesionaru'))
    resolved_at = models.DateTimeField(null=True, blank=True)
    work_order = models.ForeignKey(
        'work_orders.WorkOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='light_faults')
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Kvar rasvjete')
        verbose_name_plural = _('Kvarovi rasvjete')
        ordering = ['-reported_at']

    def __str__(self):
        return f'Kvar: Stup {self.light.pole_number} — {self.get_status_display()}'

    def _on_transition(self, old_status, new_status, user=None):
        if new_status == 'fixed':
            self.light.is_functional = True
            self.light.last_replaced = timezone.localdate()
            self.light.save(update_fields=['is_functional', 'last_replaced'])
        elif new_status == 'verified':
            self.resolved_at = timezone.now()
            self.save(update_fields=['resolved_at'])
