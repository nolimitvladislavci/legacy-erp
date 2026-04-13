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
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    location = models.CharField(max_length=200, blank=True, verbose_name=_('Lokacija / Adresa'))
    photo_url = models.URLField(blank=True, verbose_name=_('Foto URL'))

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
