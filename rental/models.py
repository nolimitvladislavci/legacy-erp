from django.db import models
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager
import uuid
import random
import string


class Property(models.Model):
    """A rental property unit (room, apartment, house)."""
    TYPE_CHOICES = [
        ('room', _('Soba')),
        ('apartment', _('Apartman')),
        ('house', _('Kuca')),
        ('suite', _('Suite')),
        ('dorm', _('Dorm / Spavaonica')),
        ('office', _('Ured')),
        ('parking', _('Parking')),
    ]
    STATUS_CHOICES = [
        ('available', _('Slobodna')),
        ('occupied', _('Zauzeta')),
        ('cleaning', _('Ciscenje')),
        ('maintenance', _('Odrzavanje')),
        ('blocked', _('Blokirana')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='rental_properties', verbose_name=_('Tvrtka'),
    )
    owner = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='owned_properties',
        verbose_name='Vlasnik / Iznajmljivač',
        help_text='Osoba kojoj prihod od najma osobno pripada (≠ firma)',
    )
    objects = CompanyManager()

    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='room', verbose_name=_('Tip'))
    floor = models.CharField(max_length=30, blank=True, verbose_name=_('Kat / Zona'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    capacity = models.IntegerField(default=2, verbose_name=_('Kapacitet (osoba)'))
    beds = models.CharField(max_length=100, blank=True, verbose_name=_('Kreveti'),
                             help_text=_('npr. 1x bracni, 2x single'))

    # Pricing
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                           verbose_name=_('Cijena po noci (EUR)'))
    price_weekend = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name=_('Cijena vikend'))
    price_weekly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        verbose_name=_('Cijena tjedna'))
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name=_('Cijena mjesecna'))
    tourist_tax = models.DecimalField(max_digits=5, decimal_places=2, default=1,
                                       verbose_name=_('Boravisna pristojba po osobi/noci'))
    cleaning_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                        verbose_name=_('Naknada za ciscenje'))
    min_nights = models.IntegerField(default=1, verbose_name=_('Min. noci'))

    # Smart Lock / Access
    smart_lock_id = models.CharField(max_length=100, blank=True, verbose_name=_('Smart Lock ID'))
    smart_lock_type = models.CharField(max_length=30, blank=True, verbose_name=_('Tip brave'),
                                        help_text=_('nuki, ttlock, igloohome, yale'))
    wifi_name = models.CharField(max_length=50, blank=True, verbose_name=_('WiFi naziv'))
    wifi_password = models.CharField(max_length=50, blank=True, verbose_name=_('WiFi lozinka'))

    # QR / Access
    qr_code = models.CharField(max_length=32, unique=True, blank=True, verbose_name=_('QR kod'))

    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='available',
                                verbose_name=_('Status'))
    is_assisted_area = models.BooleanField(
        default=False, verbose_name=_('Potpomognuto područje'),
        help_text='I.-IV. razvojna skupina — 20% popust na TZ članarinu (čl.7 st.2 NN 52/19)',
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    location = models.CharField(max_length=200, blank=True, verbose_name=_('Lokacija / Adresa'))
    photo_url = models.URLField(blank=True, verbose_name=_('Foto URL'))

    # EU Rental Tax Engine fields
    razred_mjesta = models.CharField(
        max_length=2, blank=True, default="A",
        choices=[("A", "A - turisticko mjesto"), ("B", "B - ostalo mjesto"),
                 ("C", "C - Zagreb"), ("D", "D - potpomognuto podrucje")],
        verbose_name="Razred mjesta (HR boravisna pristojba)",
    )
    tax_calculation_rule = models.CharField(
        max_length=30, blank=True, default="HR_FIXED_BORAVISNA",
        choices=[
            ("HR_FIXED_BORAVISNA", "HR fiksna boravisna pristojba"),
            ("CITY_TAX_5_PERCENT", "DE City Tax 5%"),
            ("CITY_TAX_7_PERCENT", "DE City Tax 7% (München)"),
            ("AT_ORTSTAXE_PERCENT", "AT Ortstaxe (%)"),
            ("NONE", "Bez turisticke pristojbe"),
        ],
        verbose_name="Pravilo obracuna pristojbe",
    )

    # Amenities
    amenities = models.JSONField(default=list, blank=True, verbose_name=_('Pogodnosti'),
                                  help_text=_('["wifi","parking","ac","tv","kitchen"]'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Nekretnina')
        verbose_name_plural = _('Nekretnine')
        ordering = ['floor', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = uuid.uuid4().hex[:16]
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        return self.status == 'available' and self.is_active


class SeasonalPrice(models.Model):
    """Seasonal pricing overrides."""
    rental_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='seasonal_prices')
    name = models.CharField(max_length=50, verbose_name=_('Sezona'))
    start_date = models.DateField(verbose_name=_('Od'))
    end_date = models.DateField(verbose_name=_('Do'))
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_('Cijena po noci'))

    class Meta:
        verbose_name = _('Sezonska cijena')
        ordering = ['start_date']

    def __str__(self):
        return f'{self.rental_property.name} - {self.name}'


class Booking(models.Model):
    """Guest booking / reservation."""
    STATUS_CHOICES = [
        ('pending', _('Na cekanju')),
        ('confirmed', _('Potvrdena')),
        ('checked_in', _('Prijavljen')),
        ('checked_out', _('Odjavljen')),
        ('cancelled', _('Otkazana')),
        ('no_show', _('No-show')),
    ]
    SOURCE_CHOICES = [
        ('direct', _('Direktno')),
        ('website', _('Web stranica')),
        ('qr', _('QR kod')),
        ('booking_com', _('Booking.com')),
        ('airbnb', _('Airbnb')),
        ('phone', _('Telefon')),
        ('walkin', _('Walk-in')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='rental_bookings', verbose_name=_('Tvrtka'),
    )
    objects = CompanyManager()

    # Reference
    booking_number = models.CharField(max_length=20, unique=True, blank=True, verbose_name=_('Broj rezervacije'))
    rental_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings',
                                  verbose_name=_('Nekretnina'))

    # Guest info
    guest_name = models.CharField(max_length=100, verbose_name=_('Ime gosta'))
    guest_email = models.EmailField(blank=True, verbose_name=_('Email'))
    guest_phone = models.CharField(max_length=30, blank=True, verbose_name=_('Telefon'))
    guest_country = models.CharField(max_length=3, blank=True, verbose_name=_('Drzava'),
                                      help_text=_('ISO 3166 kod (HR, DE, AT...)'))
    guest_id_number = models.CharField(max_length=30, blank=True, verbose_name=_('Broj dokumenta'))
    guest_count = models.IntegerField(default=1, verbose_name=_('Broj gostiju'))

    # Dates
    check_in = models.DateField(verbose_name=_('Check-in'))
    check_out = models.DateField(verbose_name=_('Check-out'))
    actual_check_in = models.DateTimeField(null=True, blank=True, verbose_name=_('Stvarni check-in'))
    actual_check_out = models.DateTimeField(null=True, blank=True, verbose_name=_('Stvarni check-out'))

    # Pricing
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_('Cijena/noc'))
    total_nights = models.IntegerField(default=1, verbose_name=_('Broj noci'))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Podnos'))
    tourist_tax_total = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                             verbose_name=_('Boravisna pristojba'))
    cleaning_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Ukupno'))

    # Access
    access_code = models.CharField(max_length=8, blank=True, verbose_name=_('Pristupni kod'))
    access_qr = models.CharField(max_length=64, unique=True, blank=True, verbose_name=_('QR pristup'))
    access_valid_from = models.DateTimeField(null=True, blank=True)
    access_valid_until = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending',
                                verbose_name=_('Status'))
    source = models.CharField(max_length=15, choices=SOURCE_CHOICES, default='direct',
                                verbose_name=_('Izvor'))
    notes = models.TextField(blank=True, verbose_name=_('Napomene'))
    is_paid = models.BooleanField(default=False, verbose_name=_('Placeno'))

    # Payment link
    payment_id = models.UUIDField(null=True, blank=True, verbose_name=_('Payment ID'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Rezervacija')
        verbose_name_plural = _('Rezervacije')
        ordering = ['-check_in']

    def __str__(self):
        return f'{self.booking_number} - {self.guest_name} ({self.check_in} to {self.check_out})'

    def save(self, *args, **kwargs):
        if not self.booking_number:
            prefix = self.company.name[:2].upper() if self.company else 'RH'
            num = Booking.objects.filter(company=self.company).count() + 1
            self.booking_number = f'{prefix}-{num:05d}'
        if not self.access_code:
            self.access_code = ''.join(random.choices(string.digits, k=6))
        if not self.access_qr:
            self.access_qr = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def calculate_price(self):
        """Calculate total price including tax and fees."""
        from datetime import timedelta
        nights = (self.check_out - self.check_in).days
        if nights < 1:
            nights = 1
        self.total_nights = nights
        self.subtotal = self.price_per_night * nights
        self.tourist_tax_total = self.rental_property.tourist_tax * self.guest_count * nights
        self.cleaning_fee = self.rental_property.cleaning_fee
        self.total_price = self.subtotal + self.tourist_tax_total + self.cleaning_fee
        return self.total_price

    @property

    def is_active_stay(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.status == 'checked_in' and self.check_in <= today <= self.check_out


class HousekeepingLog(models.Model):
    """Cleaning/maintenance log for properties."""
    STATUS_CHOICES = [
        ('pending', _('Za ciscenje')),
        ('in_progress', _('U tijeku')),
        ('done', _('Zavrseno')),
        ('inspected', _('Pregledano')),
    ]
    rental_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='housekeeping_logs')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Zaduzena osoba'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Ciscenje')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rental_property.name} - {self.get_status_display()}'


# ═══════════════════════════════════════════════════════════════
#  F1: Guest, GuestDocument, RentalInvoice, TrafficRecord
# ═══════════════════════════════════════════════════════════════

class Guest(models.Model):
    """Jedan gost u rezervaciji. Booking može imati više gostiju."""

    SEX_CHOICES = [('M', 'Muški'), ('F', 'Ženski'), ('X', 'Ostalo')]

    booking = models.ForeignKey(
        'Booking', on_delete=models.CASCADE, related_name='guests',
    )

    # Osnovni podaci (auto-popunjeno iz OCR)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True)
    nationality = models.CharField(max_length=3, blank=True)  # ISO 3166-1 alpha-3

    # Dokument
    document_type = models.CharField(max_length=20, blank=True)  # passport, id_card
    document_number = models.CharField(max_length=30, blank=True)
    document_country = models.CharField(max_length=3, blank=True)
    document_expiry = models.DateField(null=True, blank=True)

    # eVisitor specific
    residence_country = models.CharField(max_length=3, blank=True)
    residence_city = models.CharField(max_length=100, blank=True)

    # Status
    is_primary = models.BooleanField(default=False)
    evisitor_synced = models.BooleanField(default=False)
    evisitor_synced_at = models.DateTimeField(null=True, blank=True)
    evisitor_status = models.CharField(
        max_length=10, default="pending",
        choices=[("pending", "Na cekanju"), ("sent", "Poslano"), ("error", "Greska"), ("exempt", "Oslobodeno")],
        verbose_name="eVisitor status",
    )

    # GDPR
    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)

    # PII Encryption (GDPR cl.32)
    encrypted_document_number = models.TextField(blank=True, default='', verbose_name='Enkriptirani br. dokumenta')
    encrypted_first_name = models.TextField(blank=True, default='', verbose_name='Enkriptirano ime')
    encrypted_last_name = models.TextField(blank=True, default='', verbose_name='Enkriptirano prezime')
    pii_encrypted = models.BooleanField(default=False, verbose_name='PII enkriptirano')


    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'last_name']
        verbose_name = 'Gost'
        verbose_name_plural = 'Gosti'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def tourist_tax_category(self):
        """Kategorija boravišne pristojbe po dobi."""
        if not self.date_of_birth:
            return 'odrasli'
        from django.utils import timezone
        age = (timezone.now().date() - self.date_of_birth).days // 365
        if age < 12:
            return 'besplatno'
        elif age < 18:
            return 'popust_50'
        return 'odrasli'


class GuestDocument(models.Model):
    """Slika dokumenta gosta (za OCR i arhivu)."""

    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='documents')
    image = models.ImageField(upload_to='guest_docs/%Y/%m/')

    # OCR rezultat
    ocr_raw = models.JSONField(default=dict, blank=True)
    ocr_confidence = models.FloatField(default=0.0)
    ocr_processed = models.BooleanField(default=False)

    # GDPR — automatsko brisanje 24h nakon check-outa
    delete_after = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dokument gosta'
        verbose_name_plural = 'Dokumenti gostiju'

    def __str__(self):
        return f'{self.guest.full_name} — {self.guest.document_type or "dokument"}'


class RentalInvoice(models.Model):
    """Račun za boravak — vezan za Booking i Invoice modul."""

    booking = models.OneToOneField(
        'Booking', on_delete=models.CASCADE, related_name='rental_invoice',
    )
    invoice = models.OneToOneField(
        'invoicing.Invoice', on_delete=models.SET_NULL, null=True, blank=True,
    )

    accommodation_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tourist_tax_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cleaning_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_cancelled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_to_email = models.EmailField(blank=True)
    sent_via_wa = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Račun za najam'
        verbose_name_plural = 'Računi za najam'

    def __str__(self):
        inv_num = self.invoice.number if self.invoice else 'N/A'
        return f'{inv_num} — {self.booking.guest_name} ({self.total} EUR)'


class TrafficRecord(models.Model):
    """Evidencija o prometu (Obrazac EP) — zakonska obveza."""

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='traffic_records',
    )
    rental_property = models.ForeignKey(
        'Property', on_delete=models.CASCADE, null=True, blank=True,
        related_name='traffic_records',
    )
    booking = models.ForeignKey(
        'Booking', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='traffic_records',
    )

    date = models.DateField()
    invoice_number = models.CharField(max_length=30)
    guest_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tourist_tax = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']
        verbose_name = 'EP Evidencija prometa'
        verbose_name_plural = 'EP Evidencije prometa'

    def __str__(self):
        return f'EP {self.date} — {self.guest_name} ({self.total} EUR)'


# ═══════════════════════════════════════════════════════════════
#  P0: LandlordProfile — Osobni podaci iznajmljivača
# ═══════════════════════════════════════════════════════════════

class LandlordProfile(models.Model):
    """
    Kartica iznajmljivača — osobni i porezni podaci fizičke osobe.

    Company model sadrži OIB, IBAN, adresu — ovaj model dodaje:
    - Ime/prezime fizičke osobe (Company.name je "Ana Horvat" ali nema split)
    - Datum rođenja (za obrasce)
    - Porezni status paušalca
    - Porezna ispostava
    - Rješenje o kategorizaciji (klasa, datum, rok)

    OneToOne na Company — svaka firma iznajmljivač ima točno jedan profil.
    """

    class TaxStatus(models.TextChoices):
        PAUSAL      = 'pausal',      'Paušalni porez (čl.57 ZoPD)'
        OBRT_DOH    = 'obrt_doh',    'Obrt (dohodak)'
        OBRT_DOB    = 'obrt_dob',    'Obrt (dobit)'
        DOO         = 'doo',         'd.o.o.'

    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='landlord_profile',
        verbose_name='Firma',
    )

    # Osobni podaci fizičke osobe
    first_name = models.CharField(max_length=100, verbose_name='Ime')
    last_name = models.CharField(max_length=100, verbose_name='Prezime')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Datum rođenja')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon')
    email = models.EmailField(blank=True, verbose_name='Email')

    # Porezni status
    tax_status = models.CharField(
        max_length=20, choices=TaxStatus.choices, default=TaxStatus.PAUSAL,
        verbose_name='Porezni status',
    )
    is_vat_registered = models.BooleanField(
        default=False, verbose_name='PDV obveznik',
    )
    tax_office = models.CharField(
        max_length=100, blank=True, verbose_name='Porezna uprava',
        help_text='Npr. Porezna uprava Split',
    )
    tax_branch = models.CharField(
        max_length=100, blank=True, verbose_name='Ispostava',
        help_text='Npr. Ispostava Makarska',
    )
    nkd_code = models.CharField(
        max_length=10, blank=True, default='55.20',
        verbose_name='NKD šifra',
        help_text='55.20 = Iznajmljivanje stanova, soba i postelja',
    )
    activity_start_date = models.DateField(
        null=True, blank=True,
        verbose_name='Početak obavljanja djelatnosti',
    )

    # Turistička zajednica
    tz_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Nadležna turistička zajednica',
        help_text='Npr. TZ Grada Makarske',
    )
    tz_member_id = models.CharField(
        max_length=50, blank=True,
        verbose_name='Broj člana TZ',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil iznajmljivača'
        verbose_name_plural = 'Profili iznajmljivača'

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.company.name})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def is_pausal(self):
        return self.tax_status == self.TaxStatus.PAUSAL


# ═══════════════════════════════════════════════════════════════
#  P0: AccommodationUnit — Smještajne jedinice s krevetima
# ═══════════════════════════════════════════════════════════════

class AccommodationUnit(models.Model):
    """
    Smještajna jedinica unutar objekta (Property).

    Jedan Property (Apartman Sunce) može imati:
      - A1 Studio (2 stalna + 1 pomoćni)
      - A2 Apartman (4 stalna + 2 pomoćna)

    Stalni vs. pomoćni kreveti su ključni za:
      - TZ-2 obrazac (prijava kapaciteta turističkoj zajednici)
      - Paušalni porez (izračunava se po krevetu)
      - eVisitor prijava (smještajna jedinica je obavezno polje)
    """

    class UnitType(models.TextChoices):
        ROOM       = 'room',       'Soba'
        APARTMENT  = 'apartment',  'Apartman'
        STUDIO     = 'studio',     'Studio'
        SUITE      = 'suite',      'Suite'
        HOUSE      = 'house',      'Kuća za odmor'
        CAMP_PITCH = 'camp_pitch', 'Kamp parcela'

    rental_property = models.ForeignKey(
        'Property', on_delete=models.CASCADE,
        related_name='units',
        verbose_name='Objekt',
    )
    name = models.CharField(
        max_length=50, verbose_name='Oznaka/Naziv',
        help_text='Npr. A1, A2, Soba 101, Studio Sunset',
    )
    unit_type = models.CharField(
        max_length=20, choices=UnitType.choices, default=UnitType.APARTMENT,
        verbose_name='Vrsta jedinice',
    )

    # Kreveti — ključno za porezne obračune
    permanent_beds = models.PositiveSmallIntegerField(
        default=2, verbose_name='Stalni kreveti',
        help_text='Kreveti navedeni u rješenju o kategorizaciji',
    )
    auxiliary_beds = models.PositiveSmallIntegerField(
        default=0, verbose_name='Pomoćni kreveti',
        help_text='Dodatni/pomoćni ležajevi (kauč, dječji krevet)',
    )

    # Površina i kat
    area_sqm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Površina (m²)',
    )
    floor = models.CharField(max_length=10, blank=True, verbose_name='Kat')

    # Kategorizacija ove jedinice (može se razlikovati od objekta)
    category_stars = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Kategorija (zvjezdice)',
        help_text='1-5, ako se razlikuje od objekta',
    )

    # Rješenje o kategorizaciji
    categorization_class = models.CharField(
        max_length=100, blank=True,
        verbose_name='Klasa rješenja',
        help_text='Npr. UP/I-334-08/23-01/0234',
    )
    categorization_date = models.DateField(
        null=True, blank=True,
        verbose_name='Datum rješenja',
    )
    categorization_valid_until = models.DateField(
        null=True, blank=True,
        verbose_name='Rješenje vrijedi do',
    )

    is_active = models.BooleanField(default=True, verbose_name='Aktivna')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rental_property', 'name']
        unique_together = [('rental_property', 'name')]
        verbose_name = 'Smještajna jedinica'
        verbose_name_plural = 'Smještajne jedinice'

    def __str__(self):
        return f'{self.name} ({self.get_unit_type_display()}) — {self.rental_property.name}'

    @property
    def total_beds(self):
        return self.permanent_beds + self.auxiliary_beds

    @property
    def categorization_expired(self):
        if not self.categorization_valid_until:
            return False
        from django.utils import timezone
        return self.categorization_valid_until < timezone.now().date()

    @property
    def categorization_days_remaining(self):
        if not self.categorization_valid_until:
            return None
        from django.utils import timezone
        return (self.categorization_valid_until - timezone.now().date()).days
