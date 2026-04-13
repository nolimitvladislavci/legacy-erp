from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from borg_ops.mixins import FSMMixin
from core.managers import CompanyManager

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

    # Vaga integracija
    scale_type = models.CharField(
        max_length=20, blank=True,
        choices=[
            ('none', _('Bez vage')),
            ('serial', _('RS232/USB serijska')),
            ('bluetooth', _('Bluetooth')),
            ('network', _('Mrežna (TCP/IP)')),
            ('manual', _('Ručni unos')),
        ],
        default='none',
        verbose_name=_('Tip vage')
    )
    scale_port = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Port/adresa vage'),
        help_text=_('npr. COM3, /dev/ttyUSB0, 192.168.1.50:4001, ili BT MAC'))
    scale_protocol = models.CharField(
        max_length=30, blank=True,
        choices=[
            ('generic', _('Generički (CR/LF terminiran)')),
            ('kern', _('Kern PCB')),
            ('cas', _('CAS CI/ER')),
            ('ohaus', _('Ohaus Defender')),
            ('radwag', _('Radwag WLC/WPT')),
        ],
        default='generic',
        verbose_name=_('Protokol vage')
    )
    scale_baud_rate = models.PositiveIntegerField(
        default=9600, verbose_name=_('Baud rate'),
        help_text=_('Tipično 9600 ili 2400'))

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

    # Vaga — hardverski povučena težina (Mina #2: anti-korupcija)
    scale_reading = models.ForeignKey(
        'ScaleReading', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries',
        verbose_name=_('Očitanje vage')
    )
    weight_source = models.CharField(
        max_length=10, default='manual',
        choices=[
            ('scale', _('Automatski (vaga)')),
            ('manual', _('Ručni unos')),
        ],
        verbose_name=_('Izvor težine')
    )
    integrity_hash = models.CharField(
        max_length=64, blank=True,
        verbose_name=_('Integrity hash'),
        help_text=_('SHA-256 hash za tamper detection'))
    # POS veza za prekoračenje
    pos_receipt = models.ForeignKey(
        'pos.POSReceipt', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='waste_deliveries',
        verbose_name=_('POS račun (prekoračenje)'))
    # e-ONTO batch veza
    onto_batch = models.ForeignKey(
        'OntoExportBatch', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries',
        verbose_name=_('e-ONTO batch'))

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


class ScaleReading(models.Model):
    """
    Pojedinačno očitanje s industrijske vage.
    Hardverski povučena vrijednost — ljudski faktor eliminiran.
    Anti-tamper: hash se računa iz raw_data + timestamp.
    """
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    station = models.ForeignKey(
        WasteStation, on_delete=models.CASCADE,
        related_name='scale_readings')

    # Sirovi podaci s vage
    raw_data = models.CharField(max_length=200, verbose_name=_('Sirovi podaci s vage'),
        help_text=_('Nekodiran string s vage, npr. "ST,GS,   152.5 kg"'))
    weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name=_('Težina (kg)'))
    is_stable = models.BooleanField(default=True,
        verbose_name=_('Stabilno očitanje'),
        help_text=_('True = vaga se stabilizirala (ST flag)'))

    # Anti-tamper
    integrity_hash = models.CharField(max_length=64,
        verbose_name=_('SHA-256 hash'),
        help_text=_('hash(raw_data + timestamp + station_id + secret)'))
    is_tampered = models.BooleanField(default=False,
        verbose_name=_('Sumnja na manipulaciju'))

    # Izvor
    source = models.CharField(max_length=20,
        choices=[
            ('serial', _('RS232/USB')),
            ('bluetooth', _('Bluetooth')),
            ('network', _('Mrežna')),
            ('web_serial', _('Web Serial API')),
        ],
        default='web_serial')

    read_at = models.DateTimeField(default=timezone.now)
    operator = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Očitanje vage')
        verbose_name_plural = _('Očitanja vage')
        ordering = ['-read_at']

    def __str__(self):
        return f'{self.weight_kg} kg @ {self.station.name} ({self.read_at:%H:%M})'

    def verify_integrity(self):
        """Provjeri je li hash još valjan."""
        import hashlib

        from django.conf import settings
        secret = getattr(settings, 'SCALE_INTEGRITY_SECRET', settings.SECRET_KEY[:16])
        payload = f'{self.raw_data}|{self.read_at.isoformat()}|{self.station_id}|{secret}'
        expected = hashlib.sha256(payload.encode()).hexdigest()
        return self.integrity_hash == expected

    @staticmethod
    def compute_hash(raw_data, timestamp, station_id):
        """Izračunaj integrity hash za novo očitanje."""
        import hashlib

        from django.conf import settings
        secret = getattr(settings, 'SCALE_INTEGRITY_SECRET', settings.SECRET_KEY[:16])
        payload = f'{raw_data}|{timestamp.isoformat()}|{station_id}|{secret}'
        return hashlib.sha256(payload.encode()).hexdigest()


class OntoExportBatch(models.Model):
    """
    Batch export prema e-ONTO (Elektronički očevidnik o nastanku i tijeku otpada).
    
    Mina #3: Mrtvi državni serveri — async pattern.
    Lokalno sprema, Celery worker u 02:00 gura prema Ministarstvu.
    Retry logika: 3 pokušaja s exponential backoff.
    """
    STATUS_CHOICES = [
        ('pending', _('Čeka slanje')),
        ('generating', _('Generiranje XML-a')),
        ('sending', _('Slanje u tijeku')),
        ('accepted', _('Prihvaćeno')),
        ('partial', _('Djelomično prihvaćeno')),
        ('rejected', _('Odbijeno')),
        ('error', _('Greška')),
        ('retry', _('Čeka ponovni pokušaj')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    station = models.ForeignKey(
        WasteStation, on_delete=models.CASCADE,
        related_name='onto_batches')

    # Period
    date_from = models.DateField(verbose_name=_('Od datuma'))
    date_to = models.DateField(verbose_name=_('Do datuma'))

    # Sadržaj
    delivery_count = models.PositiveIntegerField(default=0,
        verbose_name=_('Broj zapisa'))
    total_weight_kg = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name=_('Ukupna težina (kg)'))

    # XML payload
    xml_payload = models.TextField(blank=True,
        verbose_name=_('XML za e-ONTO'),
        help_text=_('Generirani XML prema e-ONTO shemi'))
    xml_hash = models.CharField(max_length=64, blank=True,
        verbose_name=_('SHA-256 XML-a'))

    # Status i retry
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    last_error = models.TextField(blank=True, verbose_name=_('Zadnja greška'))

    # Odgovor Ministarstva
    response_code = models.CharField(max_length=20, blank=True)
    response_body = models.TextField(blank=True)
    accepted_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    rejection_details = models.JSONField(default=list, blank=True)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('e-ONTO batch')
        verbose_name_plural = _('e-ONTO batchevi')
        ordering = ['-created_at']
        unique_together = [('company', 'station', 'date_from', 'date_to')]

    def __str__(self):
        return f'e-ONTO {self.station.name} {self.date_from}–{self.date_to} [{self.get_status_display()}]'

    def can_retry(self):
        return self.status in ('error', 'retry') and self.retry_count < self.max_retries

    def generate_xml(self):
        """
        Generira XML prema e-ONTO shemi iz WasteDelivery zapisa.
        Poziva se iz Celery taska.
        """
        import hashlib
        from xml.etree.ElementTree import Element, SubElement, tostring

        deliveries = WasteDelivery.objects.filter(
            onto_batch=self,
            status='confirmed'
        ).select_related('citizen__partner', 'category', 'station')

        root = Element('eONTO')
        root.set('version', '1.0')
        root.set('xmlns', 'http://onto.mzoe.hr/schema/v1')

        header = SubElement(root, 'Zaglavlje')
        SubElement(header, 'OIB').text = self.company.oib
        SubElement(header, 'NazivObveznika').text = self.company.name
        SubElement(header, 'DatumOd').text = self.date_from.isoformat()
        SubElement(header, 'DatumDo').text = self.date_to.isoformat()
        SubElement(header, 'BrojZapisa').text = str(deliveries.count())

        zapisi = SubElement(root, 'Zapisi')
        total_kg = Decimal('0')

        for d in deliveries:
            zapis = SubElement(zapisi, 'Zapis')
            SubElement(zapis, 'RedniBroj').text = str(d.pk)
            SubElement(zapis, 'DatumVrijeme').text = d.delivery_date.isoformat()
            SubElement(zapis, 'KljucniBroj').text = d.category.key_number
            SubElement(zapis, 'NazivOtpada').text = d.category.name
            SubElement(zapis, 'Kolicina').text = str(d.quantity)
            SubElement(zapis, 'JedinicaMjere').text = d.unit
            SubElement(zapis, 'OpasniOtpad').text = 'DA' if d.category.is_hazardous else 'NE'
            SubElement(zapis, 'IzvorTezine').text = d.weight_source
            SubElement(zapis, 'Lokacija').text = d.station.name
            total_kg += d.quantity

        xml_str = tostring(root, encoding='unicode', xml_declaration=True)
        self.xml_payload = xml_str
        self.xml_hash = hashlib.sha256(xml_str.encode()).hexdigest()
        self.delivery_count = deliveries.count()
        self.total_weight_kg = total_kg
        self.status = 'generating'
        self.save()
        return xml_str


class WasteQuickButton(models.Model):
    """
    Brzi gumbi za terenski kiosk — Mina #1: prljave ruke.
    Umjesto padajućeg izbornika s 200 ključnih brojeva,
    operater vidi 8-12 velikih gumba u boji.
    """
    COLOR_CHOICES = [
        ('#4CAF50', _('Zelena (papir/karton)')),
        ('#2196F3', _('Plava (plastika)')),
        ('#FF9800', _('Narančasta (metal)')),
        ('#795548', _('Smeđa (bio)')),
        ('#9E9E9E', _('Siva (šuta/građevinski)')),
        ('#F44336', _('Crvena (opasni)')),
        ('#FFEB3B', _('Žuta (staklo)')),
        ('#9C27B0', _('Ljubičasta (EE otpad)')),
        ('#00BCD4', _('Tirkizna (tekstil)')),
        ('#607D8B', _('Tamno siva (glomazni)')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    station = models.ForeignKey(
        WasteStation, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='quick_buttons',
        verbose_name=_('Dvorište (prazno=sva)'))
    category = models.ForeignKey(
        WasteCategory, on_delete=models.CASCADE,
        related_name='quick_buttons',
        verbose_name=_('Kategorija otpada'))

    label = models.CharField(max_length=30, verbose_name=_('Tekst na gumbu'),
        help_text=_('Kratko: "PAPIR", "PLASTIKA", "ŠUTA"'))
    icon = models.CharField(max_length=50, blank=True,
        verbose_name=_('Font Awesome ikona'),
        help_text=_('npr. fa-newspaper, fa-recycle'))
    color = models.CharField(max_length=7, choices=COLOR_CHOICES, default='#4CAF50',
        verbose_name=_('Boja gumba'))
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Brzi gumb')
        verbose_name_plural = _('Brzi gumbi')
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.label} → {self.category.key_number}'


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
