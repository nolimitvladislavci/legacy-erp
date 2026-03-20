from django.db import models
from decimal import Decimal
from datetime import date, timedelta


class Member(models.Model):
    MEMBERSHIP_CHOICES = [
        ('basic', 'Osnovno'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ]
    STATUS_CHOICES = [
        ('active', 'Aktivan'),
        ('inactive', 'Neaktivan'),
        ('frozen', 'Zamrznut'),
        ('expired', 'Isteklo'),
    ]
    # 'partners.Partner' se referencira kao string jer je 'Partner' model vjerojatno u drugoj aplikaciji.
    # On_delete=models.SET_NULL je korišteno u postojećem kodu, pratim taj stil.
    partner = models.OneToOneField('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True, related_name='fitness_member')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='Hrvatska')
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='basic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    rfid_tag = models.CharField(max_length=50, unique=True, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Član"
        verbose_name_plural = "Članovi"


class MemberCheckIn(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='check_ins')
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.member.first_name} {self.member.last_name} - {self.check_in_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Prijava člana"
        verbose_name_plural = "Prijave članova"


# Novi modeli - KORAK 2

class MembershipPlan(models.Model):
    """
    Definira različite planove članstva koje teretana nudi.
    """
    BILLING_PERIOD_CHOICES = [
        ('monthly', 'Mjesečno'),
        ('quarterly', 'Kvartalno'),
        ('yearly', 'Godišnje'),
    ]

    name = models.CharField(max_length=100, verbose_name="Naziv plana")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cijena (EUR)")
    duration_days = models.PositiveIntegerField(
        help_text="Trajanje plana u danima (npr. 30 za mjesečni plan)",
        verbose_name="Trajanje (dani)"
    )
    billing_period = models.CharField(
        max_length=20,
        choices=BILLING_PERIOD_CHOICES,
        default='monthly',
        verbose_name="Period naplate"
    )
    auto_renew = models.BooleanField(default=False, verbose_name="Automatsko obnavljanje")
    grace_period_days = models.PositiveIntegerField(
        default=0,
        help_text="Broj dana nakon isteka plana tijekom kojih je pretplata i dalje aktivna.",
        verbose_name="Grejs period (dani)"
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Popust u postotcima (npr. 10.00 za 10%)",
        verbose_name="Postotak popusta"
    )
    # Referenca na 'partners.Partner' kako je već korišteno u Member modelu
    company = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='membership_plans',
        help_text="Firma kojoj pripada ovaj plan članstva.",
        verbose_name="Firma"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan članstva"
        verbose_name_plural = "Planovi članstva"

    def __str__(self):
        return f"{self.name} ({self.price} EUR/{self.billing_period})"


class MemberSubscription(models.Model):
    """
    Prati aktivne i istekle pretplate članova na planove članstva.
    """
    SUBSCRIPTION_STATUS_CHOICES = [
        ('draft', 'Nacrt'), # Čeka da postane aktivna
        ('active', 'Aktivna'),
        ('grace', 'Grejs period'), # Prošlo je valid_until, ali je unutar grace_period_days
        ('suspended', 'Suspendirana'), # Ručno suspendirana
        ('cancelled', 'Otkazana'), # Ručno otkazana
        ('expired', 'Istekla'), # Prošlo je valid_until i grace_period_days
    ]

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name="Član"
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT, # Ne želimo obrisati plan ako postoje pretplate na njega
        related_name='subscriptions',
        verbose_name="Plan članstva"
    )
    valid_from = models.DateField(verbose_name="Vrijedi od")
    valid_until = models.DateField(verbose_name="Vrijedi do")
    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='draft',
        verbose_name="Status"
    )
    payment_reference = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Referenca na uplatu ili račun",
        verbose_name="Referenca uplate"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pretplata člana"
        verbose_name_plural = "Pretplate članova"

    def __str__(self):
        return f"{self.member.first_name} {self.member.last_name} - {self.plan.name} ({self.status})"

    def evaluate_status(self):
        """
        Evaluira i ažurira status pretplate na temelju datuma i grace perioda.
        Ovo je primjer state machine logike.
        """
        today = date.today()
        # Izbjegavamo automatsku promjenu statusa ako je ručno postavljen na suspendiran/otkazan
        if self.status in ['suspended', 'cancelled']:
            return False

        new_status = self.status

        if self.valid_from > today:
            new_status = 'draft' # Ako datum početka još nije došao
        elif self.valid_from <= today and self.valid_until >= today:
            new_status = 'active' # Ako je unutar važećeg perioda
        elif self.valid_until < today:
            # Ako je prošao valid_until, provjeravamo grace period
            grace_period_end = self.valid_until + timedelta(days=self.plan.grace_period_days)
            if today <= grace_period_end:
                new_status = 'grace' # Ako je unutar grace perioda
            else:
                new_status = 'expired' # Ako je prošao i grace period
        
        # Ako je trenutni status 'draft' i valid_from je danas ili ranije, pretplata postaje aktivna
        if self.status == 'draft' and self.valid_from <= today and new_status != 'expired':
            new_status = 'active'

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])
            return True # Status je promijenjen
        return False # Status nije promijenjen


class Payment(models.Model):
    """
    Bilježi uplate članova, s opcijom povezivanja na pretplatu.
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Gotovina'),
        ('card', 'Kartica'),
        ('transfer', 'Uplata na račun'),
        ('pos', 'POS terminal'),
        ('other', 'Ostalo'),
    ]

    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL, # Ne želimo obrisati uplatu ako član bude obrisan, ali želimo zadržati podatak o uplati
        null=True, blank=True,
        related_name='payments',
        verbose_name="Član"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Iznos")
    method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        verbose_name="Metoda plaćanja"
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name="Datum uplate")
    invoice_number = models.CharField(
        max_length=100, blank=True, null=True, unique=True,
        verbose_name="Broj računa"
    )
    note = models.TextField(blank=True, verbose_name="Napomena")
    linked_subscription = models.ForeignKey(
        MemberSubscription,
        on_delete=models.SET_NULL, # Ne želimo obrisati uplatu ako se pretplata obriše
        null=True, blank=True,
        related_name='payments',
        verbose_name="Povezana pretplata"
    )
    # Referenca na 'partners.Partner'
    company = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='fitness_payments',
        help_text="Firma kojoj pripada ova uplata.",
        verbose_name="Firma"
    )

    class Meta:
        verbose_name = "Uplata"
        verbose_name_plural = "Uplate"
        ordering = ['-date']

    def __str__(self):
        member_name = f"{self.member.first_name} {self.member.last_name}" if self.member else "Nepoznat član"
        return f"Uplata {self.amount} EUR od {member_name} ({self.date.strftime('%Y-%m-%d %H:%M')})"


class WorkoutClass(models.Model):
    """
    Definira klase vježbanja (npr. joga, crossfit) s detaljima.
    """
    CLASS_TYPE_CHOICES = [
        ('yoga', 'Joga'),
        ('crossfit', 'CrossFit'),
        ('pilates', 'Pilates'),
        ('zumba', 'Zumba'),
        ('spinning', 'Spinning'),
        ('strength', 'Trening snage'),
        ('cardio', 'Kardio'),
        ('other', 'Ostalo'),
    ]

    name = models.CharField(max_length=150, verbose_name="Naziv klase")
    instructor = models.CharField(max_length=100, verbose_name="Instruktor")
    capacity = models.PositiveIntegerField(
        default=10,
        help_text="Maksimalan broj polaznika",
        verbose_name="Kapacitet"
    )
    scheduled_at = models.DateTimeField(verbose_name="Zakazano za")
    location = models.CharField(
        max_length=100, blank=True,
        help_text="Lokacija ili dvorana",
        verbose_name="Lokacija"
    )
    duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Trajanje klase u minutama",
        verbose_name="Trajanje (min)"
    )
    class_type = models.CharField(
        max_length=50,
        choices=CLASS_TYPE_CHOICES,
        default='other',
        verbose_name="Tip klase"
    )
    # Referenca na 'partners.Partner'
    company = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='workout_classes',
        help_text="Firma kojoj pripada ova klasa.",
        verbose_name="Firma"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Klasa vježbanja"
        verbose_name_plural = "Klase vježbanja"
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.name} ({self.class_type}) - {self.scheduled_at.strftime('%Y-%m-%d %H:%M')} by {self.instructor}"

    def available_spots(self):
        """Vraća broj dostupnih mjesta u klasi (računajući samo 'booked' statuse)."""
        # Trebali bismo računati samo aktivne rezervacije
        booked_count = self.bookings.filter(status='booked').count()
        return max(0, self.capacity - booked_count)

    def is_full(self):
        """Provjerava je li klasa puna."""
        return self.available_spots() == 0


class ClassBooking(models.Model):
    """
    Evidencija rezervacija članova za pojedine klase vježbanja.
    """
    BOOKING_STATUS_CHOICES = [
        ('booked', 'Rezervirano'),
        ('cancelled', 'Otkazano'),
        ('attended', 'Pohađano'),
        ('no_show', 'Nije se pojavio'),
    ]

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='class_bookings',
        verbose_name="Član"
    )
    workout_class = models.ForeignKey(
        WorkoutClass,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="Klasa vježbanja"
    )
    booked_at = models.DateTimeField(auto_now_add=True, verbose_name="Datum rezervacije")
    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUS_CHOICES,
        default='booked',
        verbose_name="Status rezervacije"
    )

    class Meta:
        unique_together = ('member', 'workout_class') # Jedan član može rezervirati jednu klasu samo jednom
        verbose_name = "Rezervacija klase"
        verbose_name_plural = "Rezervacije klasa"
        ordering = ['booked_at']

    def __str__(self):
        return f"Rezervacija: {self.member.first_name} {self.member.last_name} za {self.workout_class.name} - {self.status}"


class Equipment(models.Model):
    """
    Evidencija opreme u teretani s podacima o servisu i statusu.
    """
    EQUIPMENT_STATUS_CHOICES = [
        ('ok', 'Ispravno'),
        ('needs_service', 'Potreban servis'),
        ('broken', 'Pokvareno'),
        ('retired', 'Izvan upotrebe'),
    ]

    name = models.CharField(max_length=150, verbose_name="Naziv opreme")
    serial_number = models.CharField(
        max_length=100, blank=True, null=True, unique=True,
        verbose_name="Serijski broj"
    )
    purchase_date = models.DateField(blank=True, null=True, verbose_name="Datum kupnje")
    last_service_date = models.DateField(blank=True, null=True, verbose_name="Datum zadnjeg servisa")
    status = models.CharField(
        max_length=20,
        choices=EQUIPMENT_STATUS_CHOICES,
        default='ok',
        verbose_name="Status"
    )
    location = models.CharField(
        max_length=100, blank=True,
        help_text="Lokacija opreme (npr. 'Teretana 1', 'Skladište')",
        verbose_name="Lokacija"
    )
    # Referenca na 'partners.Partner'
    company = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='fitness_equipment',
        help_text="Firma kojoj pripada ova oprema.",
        verbose_name="Firma"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Oprema"
        verbose_name_plural = "Oprema"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.serial_number or 'N/A'}) - {self.status}"
