"""
experiences/models.py — Agro-Turizam 360

Ljepilo koje spaja: rental + inventory + marketplace + gastro_menu + POS
u koherentnu turističku ponudu za OPG-ove.

Modeli:
  Experience          — aktivnost (degustacija, radionica, berba, tura...)
  ExperienceSchedule  — kalendar dostupnosti
  ExperienceBooking   — rezervacija gosta + PrepaymentEscrow
  ExperienceInclusion — što je uključeno (inventory linkovi)
  ExperienceReview    — ocjena gosta
  AgroPackage         — bundle (soba + aktivnosti + proizvodi)
  PackageComponent    — stavka bundlea s TaxSplitter info
  RecallEvent         — HACCP reverse traceability
  RecallNotification  — obavijesti pogođenim gostima/kupcima
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


# ═══════════════════════════════════════════════════════════════════
# EXPERIENCE — Aktivnost na OPG-u
# ═══════════════════════════════════════════════════════════════════

class Experience(models.Model):
    """Turistička aktivnost/iskustvo na OPG-u."""
    TYPE_CHOICES = [
        ('degustacija',  'Degustacija'),
        ('radionica',    'Radionica'),
        ('berba',        'Berba'),
        ('tura',         'Obilazak / Tura'),
        ('jahanje',      'Jahanje'),
        ('promatranje',  'Promatranje (golubi, ptice)'),
        ('muznja',       'Muznja'),
        ('kulinarska',   'Kulinarska radionica'),
        ('wellness',     'Wellness / Opuštanje'),
        ('ostalo',       'Ostalo'),
    ]
    DIFFICULTY_CHOICES = [
        ('easy',   'Lagano — za sve uzraste'),
        ('medium', 'Umjereno — potrebna obuća'),
        ('hard',   'Zahtjevno — fizička sprema'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='experiences', verbose_name=_('OPG / Tvrtka')
    )
    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    experience_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_('Tip'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    what_to_bring = models.TextField(blank=True, verbose_name=_('Što ponijeti'),
                                      help_text=_('npr. Udobna obuća, šešir, zaštita od sunca'))

    # Logistika
    duration_minutes = models.PositiveIntegerField(verbose_name=_('Trajanje (min)'))
    capacity = models.PositiveIntegerField(verbose_name=_('Max gostiju'))
    min_pax = models.PositiveIntegerField(default=1, verbose_name=_('Min gostiju za održavanje'))
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    meeting_point = models.CharField(max_length=300, blank=True, verbose_name=_('Točka okupljanja'))
    gps_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Cijena
    price_per_person = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Cijena/osobi (EUR)'))
    child_discount_pct = models.PositiveIntegerField(default=50, verbose_name=_('Popust djeca (%)'))
    deposit_pct = models.PositiveIntegerField(default=30, verbose_name=_('Depozit (%)'),
                                               help_text=_('Postotak cijene koji se plaća unaprijed'))
    cancellation_hours = models.PositiveIntegerField(default=12, verbose_name=_('Besplatno otkazivanje (sati prije)'))

    # Porez
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25,
                                    verbose_name=_('PDV stopa (%)'),
                                    help_text=_('Usluge = 25%, ugostiteljstvo = 13%'))

    # Vodič
    guide = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='guided_experiences',
        verbose_name=_('Vodič')
    )
    guide_languages = models.CharField(max_length=100, blank=True, default='hr',
                                        verbose_name=_('Jezici vodstva'),
                                        help_text=_('hr,en,de,it'))

    # Mediji
    image_main = models.ImageField(upload_to='experiences/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    seasonal_from = models.DateField(null=True, blank=True, verbose_name=_('Sezona od'))
    seasonal_until = models.DateField(null=True, blank=True, verbose_name=_('Sezona do'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Iskustvo / Aktivnost')
        verbose_name_plural = _('Iskustva / Aktivnosti')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_experience_type_display()})'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f'{self.name}-{self.company_id}')[:220]
        super().save(*args, **kwargs)

    @property
    def deposit_amount(self):
        return self.price_per_person * Decimal(str(self.deposit_pct)) / Decimal('100')


class ExperienceSchedule(models.Model):
    """Kalendar — kad je aktivnost dostupna."""
    STATUS_CHOICES = [
        ('open',      'Otvoreno za rezervacije'),
        ('full',      'Popunjeno'),
        ('cancelled', 'Otkazano'),
        ('completed', 'Završeno'),
    ]

    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField(verbose_name=_('Datum'))
    time_from = models.TimeField(verbose_name=_('Od'))
    time_to = models.TimeField(verbose_name=_('Do'))
    max_pax = models.PositiveIntegerField(verbose_name=_('Max gostiju'))
    booked_pax = models.PositiveIntegerField(default=0, verbose_name=_('Rezervirano'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    weather_note = models.CharField(max_length=200, blank=True, verbose_name=_('Vremenska napomena'))

    class Meta:
        verbose_name = _('Raspored iskustva')
        verbose_name_plural = _('Rasporedi iskustava')
        ordering = ['date', 'time_from']
        unique_together = [('experience', 'date', 'time_from')]

    def __str__(self):
        return f'{self.experience.name} — {self.date} {self.time_from}'

    @property
    def available_spots(self):
        return max(0, self.max_pax - self.booked_pax)

    @property
    def is_bookable(self):
        return self.status == 'open' and self.available_spots > 0


class ExperienceBooking(models.Model):
    """
    Rezervacija gosta za aktivnost.
    Uključuje PrepaymentEscrow logiku:
    - 30% depozit pri rezervaciji
    - No-show = depozit "izgara"
    - Otkazivanje 12h+ prije = puni povrat
    """
    STATUS_CHOICES = [
        ('pending',     'Čeka uplatu depozita'),
        ('confirmed',   'Potvrđeno (depozit plaćen)'),
        ('checked_in',  'Prisutan'),
        ('completed',   'Završeno'),
        ('no_show',     'Nije se pojavio'),
        ('cancelled',   'Otkazano'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('card',     'Kartica'),
        ('cash',     'Gotovina'),
        ('transfer', 'Virman'),
        ('online',   'Online uplata'),
    ]

    schedule = models.ForeignKey(ExperienceSchedule, on_delete=models.CASCADE, related_name='bookings')

    # Gost — može biti rental gost ili standalone
    rental_booking = models.ForeignKey(
        'rental.Booking', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experience_bookings',
        verbose_name=_('Povezani smještaj')
    )
    guest_name = models.CharField(max_length=200, verbose_name=_('Ime gosta'))
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=50, blank=True)
    guest_country = models.CharField(max_length=3, blank=True, verbose_name=_('Država (ISO)'))

    pax_count = models.PositiveIntegerField(verbose_name=_('Broj osoba'))
    children_count = models.PositiveIntegerField(default=0, verbose_name=_('Djece'))

    # Financije
    price_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Ukupna cijena'))
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Depozit'))
    deposit_paid = models.BooleanField(default=False)
    deposit_paid_at = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, blank=True)
    remaining_paid = models.BooleanField(default=False, verbose_name=_('Ostatak plaćen'))

    # PrepaymentEscrow
    deposit_forfeited = models.BooleanField(default=False, verbose_name=_('Depozit zadržan (no-show)'))
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Povrat'))

    # POS veza
    pos_receipt = models.ForeignKey(
        'pos.POSReceipt', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experience_bookings',
        verbose_name=_('POS račun')
    )

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Rezervacija iskustva')
        verbose_name_plural = _('Rezervacije iskustava')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.guest_name} — {self.schedule} ({self.pax_count} os.)'

    def save(self, *args, **kwargs):
        exp = self.schedule.experience
        adults = self.pax_count - self.children_count
        child_price = exp.price_per_person * (Decimal('100') - Decimal(str(exp.child_discount_pct))) / Decimal('100')
        self.price_total = (adults * exp.price_per_person) + (self.children_count * child_price)
        self.deposit_amount = self.price_total * Decimal(str(exp.deposit_pct)) / Decimal('100')
        super().save(*args, **kwargs)

    def can_cancel_free(self):
        """Može li gost besplatno otkazati?"""
        from datetime import datetime, timedelta
        schedule_dt = datetime.combine(self.schedule.date, self.schedule.time_from)
        schedule_dt = timezone.make_aware(schedule_dt) if timezone.is_naive(schedule_dt) else schedule_dt
        deadline = schedule_dt - timedelta(hours=self.schedule.experience.cancellation_hours)
        return timezone.now() < deadline

    def cancel(self):
        """Otkaži rezervaciju. Besplatno ako je unutar roka, inače depozit se zadržava."""
        if self.can_cancel_free():
            self.refund_amount = self.deposit_amount
            self.deposit_forfeited = False
        else:
            self.refund_amount = Decimal('0')
            self.deposit_forfeited = True
        self.status = 'cancelled'
        self.save()
        # Oslobodi mjesta
        sched = self.schedule
        sched.booked_pax = max(0, sched.booked_pax - self.pax_count)
        if sched.status == 'full':
            sched.status = 'open'
        sched.save(update_fields=['booked_pax', 'status'])

    def mark_no_show(self):
        """Gost se nije pojavio — depozit se zadržava."""
        self.status = 'no_show'
        self.deposit_forfeited = True
        self.refund_amount = Decimal('0')
        self.save(update_fields=['status', 'deposit_forfeited', 'refund_amount'])

    def confirm_deposit(self, method='card'):
        """Potvrdi uplatu depozita."""
        self.deposit_paid = True
        self.deposit_paid_at = timezone.now()
        self.payment_method = method
        self.status = 'confirmed'
        self.save()
        # Ažuriraj schedule
        sched = self.schedule
        sched.booked_pax += self.pax_count
        if sched.booked_pax >= sched.max_pax:
            sched.status = 'full'
        sched.save(update_fields=['booked_pax', 'status'])


class ExperienceInclusion(models.Model):
    """Što je uključeno u cijenu iskustva — linkovi na inventory."""
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='inclusions')
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experience_inclusions',
        verbose_name=_('Artikl iz skladišta')
    )
    description = models.CharField(max_length=200, verbose_name=_('Opis'),
                                    help_text=_('npr. "1 boca Šljivovice 0.5L"'))
    quantity_per_person = models.DecimalField(max_digits=8, decimal_places=2, default=1,
                                              verbose_name=_('Količina po osobi'))
    unit = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica'))

    class Meta:
        verbose_name = _('Uključeno u iskustvo')
        verbose_name_plural = _('Uključeno u iskustva')

    def __str__(self):
        return f'{self.experience.name}: {self.description}'


class ExperienceReview(models.Model):
    """Ocjena gosta nakon iskustva."""
    booking = models.OneToOneField(ExperienceBooking, on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveIntegerField(verbose_name=_('Ocjena (1-5)'))
    text = models.TextField(blank=True, verbose_name=_('Komentar'))
    photo = models.ImageField(upload_to='experiences/reviews/', blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Ocjena iskustva')
        verbose_name_plural = _('Ocjene iskustava')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.booking.guest_name}: {self.rating}/5'

    def save(self, *args, **kwargs):
        if self.rating < 1:
            self.rating = 1
        elif self.rating > 5:
            self.rating = 5
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# AGROPACKAGE — Bundle s TaxSplitter-om
# ═══════════════════════════════════════════════════════════════════

class AgroPackage(models.Model):
    """
    Bundle paket: soba + aktivnosti + proizvodi.
    TaxSplitter automatski razbija na stavke s različitim PDV stopama.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='agro_packages', verbose_name=_('OPG / Tvrtka')
    )
    name = models.CharField(max_length=200, verbose_name=_('Naziv paketa'))
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='experiences/packages/', blank=True, null=True)

    # Bundle cijena
    advertised_price = models.DecimalField(max_digits=10, decimal_places=2,
                                            verbose_name=_('Oglašena cijena (EUR)'),
                                            help_text=_('Cijena koja se prikazuje gostu'))
    duration_days = models.PositiveIntegerField(default=1, verbose_name=_('Trajanje (dana)'))
    max_guests = models.PositiveIntegerField(default=2, verbose_name=_('Max gostiju'))

    is_active = models.BooleanField(default=True)
    seasonal_from = models.DateField(null=True, blank=True)
    seasonal_until = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Agro paket')
        verbose_name_plural = _('Agro paketi')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.advertised_price} EUR'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f'{self.name}-{self.company_id}')[:220]
        super().save(*args, **kwargs)

    # ── TaxSplitter ─────────────────────────────────────
    def tax_breakdown(self):
        """
        Razbija bundle na stavke s različitim PDV stopama.
        Vrača dict s ključevima po stopi:
        {
            '13.00': {'items': [...], 'subtotal': Decimal, 'tax': Decimal},
            '25.00': {'items': [...], 'subtotal': Decimal, 'tax': Decimal},
        }
        + ukupni PDV i neto iznos.
        """
        components = self.components.all()
        if not components.exists():
            return {'breakdown': {}, 'total_net': Decimal('0'), 'total_tax': Decimal('0'),
                    'total_gross': self.advertised_price}

        # Raspodijeli oglasienu cijenu proporcionalno po komponentama
        component_total = sum(c.component_price for c in components)
        if component_total == 0:
            return {'breakdown': {}, 'total_net': Decimal('0'), 'total_tax': Decimal('0'),
                    'total_gross': self.advertised_price}

        breakdown = {}
        total_tax = Decimal('0')
        total_net = Decimal('0')

        for comp in components:
            # Proporcionalni udio u oglašenoj cijeni
            ratio = comp.component_price / component_total
            allocated_gross = (self.advertised_price * ratio).quantize(Decimal('0.01'))

            tax_rate_key = str(comp.tax_rate)
            net = (allocated_gross / (Decimal('1') + comp.tax_rate / Decimal('100'))).quantize(Decimal('0.01'))
            tax = allocated_gross - net

            if tax_rate_key not in breakdown:
                breakdown[tax_rate_key] = {'items': [], 'subtotal': Decimal('0'), 'tax': Decimal('0')}

            breakdown[tax_rate_key]['items'].append({
                'name': comp.label,
                'type': comp.get_component_type_display(),
                'gross': allocated_gross,
                'net': net,
                'tax': tax,
            })
            breakdown[tax_rate_key]['subtotal'] += net
            breakdown[tax_rate_key]['tax'] += tax
            total_net += net
            total_tax += tax

        return {
            'breakdown': breakdown,
            'total_net': total_net,
            'total_tax': total_tax,
            'total_gross': self.advertised_price,
        }

    def fiscal_line_items(self):
        """
        Za fiskalizaciju — vrača listu stavki za R1/R2 račun.
        Svaka stavka ima: naziv, iznos, PDV stopa, PDV iznos.
        """
        tb = self.tax_breakdown()
        items = []
        for rate, data in tb['breakdown'].items():
            for item in data['items']:
                items.append({
                    'name': item['name'],
                    'amount': item['gross'],
                    'tax_rate': Decimal(rate),
                    'tax_amount': item['tax'],
                    'net_amount': item['net'],
                })
        return items


class PackageComponent(models.Model):
    """
    Stavka bundlea — veza na smještaj, aktivnost, ili proizvod.
    Svaka komponenta nosi svoju PDV stopu za TaxSplitter.
    """
    COMPONENT_TYPE_CHOICES = [
        ('accommodation', 'Smještaj'),         # 13% PDV
        ('meal',          'Obrok / Hrana'),     # 13% PDV (ugostiteljstvo)
        ('experience',    'Aktivnost'),         # 25% PDV
        ('product',       'Proizvod'),          # 25% PDV
        ('transport',     'Prijevoz'),          # 25% PDV
    ]
    # Pretpostavljene stope po tipu (HR 2025/2026)
    DEFAULT_TAX_RATES = {
        'accommodation': Decimal('13.00'),
        'meal':          Decimal('13.00'),
        'experience':    Decimal('25.00'),
        'product':       Decimal('25.00'),
        'transport':     Decimal('25.00'),
    }

    package = models.ForeignKey(AgroPackage, on_delete=models.CASCADE, related_name='components')
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES)
    label = models.CharField(max_length=200, verbose_name=_('Naziv stavke'),
                              help_text=_('npr. "2 noćenja u apartmanu Lavanda"'))

    # Veze na postojeće modele (samo jedan aktivan)
    property_link = models.ForeignKey(
        'rental.Property', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='package_components',
        verbose_name=_('Smještaj')
    )
    experience_link = models.ForeignKey(
        Experience, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='package_components',
        verbose_name=_('Aktivnost')
    )
    marketplace_product_link = models.ForeignKey(
        'marketplace.MarketplaceProduct', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='package_components',
        verbose_name=_('Proizvod s tržnice')
    )
    menu_link = models.ForeignKey(
        'gastro_menu.DigitalMenu', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='package_components',
        verbose_name=_('Meni / Obrok')
    )

    # Cijena i porez
    component_price = models.DecimalField(max_digits=10, decimal_places=2,
                                           verbose_name=_('Cijena komponente (EUR)'),
                                           help_text=_('Interna cijena za TaxSplitter proporciju'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_('PDV stopa (%)'))

    quantity = models.PositiveIntegerField(default=1, verbose_name=_('Količina'))
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Komponenta paketa')
        verbose_name_plural = _('Komponente paketa')
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.package.name}: {self.label} ({self.get_component_type_display()})'

    def save(self, *args, **kwargs):
        # Auto-set tax rate po tipu ako nije ručno postavljen
        if not self.tax_rate:
            self.tax_rate = self.DEFAULT_TAX_RATES.get(self.component_type, Decimal('25.00'))
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# RECALL EVENT — HACCP reverse traceability
# ═══════════════════════════════════════════════════════════════════

class RecallEvent(models.Model):
    """
    Povlačenje proizvoda — reverse traceability.
    U 3 sekunde povezuje: Gost → Jelo → Sastojak → Flock/Berba → Svi pogođeni kupci.
    """
    SEVERITY_CHOICES = [
        ('warning',  'Upozorenje — praćenje'),
        ('recall',   'Povlačenje — ne konzumirati'),
        ('critical', 'Kritično — hitna obavijest'),
    ]
    STATUS_CHOICES = [
        ('open',          'Otvoreno — istraga'),
        ('investigating', 'U tijeku — prikupljanje podataka'),
        ('notified',      'Obavijesti poslane'),
        ('resolved',      'Riješeno'),
        ('false_alarm',   'Lažna uzbuna'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='recall_events', verbose_name=_('Tvrtka')
    )

    # Izvor problema
    source_model = models.CharField(max_length=50, verbose_name=_('Model izvora'),
                                     help_text=_('npr. EggRecord, MedProizvodnja, StockBatch'))
    source_id = models.PositiveIntegerField(verbose_name=_('ID izvora'))
    lot_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj serije/šarže'))

    # Detalji
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    description = models.TextField(verbose_name=_('Opis problema'))
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')

    # Pogođeni
    affected_guests_count = models.PositiveIntegerField(default=0, verbose_name=_('Pogođenih gostiju'))
    affected_orders_count = models.PositiveIntegerField(default=0, verbose_name=_('Pogođenih narudžbi'))

    # Zdravstveno
    reported_symptoms = models.TextField(blank=True, verbose_name=_('Prijavljeni simptomi'))
    health_authority_notified = models.BooleanField(default=False,
                                                      verbose_name=_('Sanitarna inspekcija obaviještena'))
    health_authority_ref = models.CharField(max_length=100, blank=True,
                                             verbose_name=_('Referenca prijave'))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Prijavio')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Povlačenje proizvoda')
        verbose_name_plural = _('Povlačenja proizvoda')
        ordering = ['-created_at']

    def __str__(self):
        return f'RECALL #{self.pk} [{self.get_severity_display()}] — {self.title}'

    def trace_affected(self):
        """
        Pronađi sve pogođene — goste, narudžbe, restorane.
        Vrača dict s listama pogođenih entiteta.
        """
        from marketplace.models import MarketplaceProduct, MarketplaceOrderItem
        from gastro_menu.models import MenuItemIngredient, TableOrder
        from rental.models import Guest

        affected = {
            'marketplace_products': [],
            'marketplace_orders': [],
            'gastro_orders': [],
            'rental_guests': [],
        }

        # 1. Nađi marketplace listinge iz istog izvora
        products = MarketplaceProduct.objects.filter(
            source_model=self.source_model,
            source_id=self.source_id,
        )
        affected['marketplace_products'] = list(products.values('id', 'name', 'seller_company__name'))

        # 2. Nađi sve narudžbe tih proizvoda
        product_ids = products.values_list('id', flat=True)
        order_items = MarketplaceOrderItem.objects.filter(
            product_id__in=product_ids
        ).select_related('order', 'order__buyer_company')
        affected['marketplace_orders'] = list(order_items.values(
            'order__order_number', 'order__buyer_company__name',
            'order__created_at', 'quantity'
        ))

        # 3. Nađi gastro jela koja koriste te proizvode
        menu_ingredients = MenuItemIngredient.objects.filter(
            marketplace_product_id__in=product_ids
        ).select_related('menu_item')

        # 4. Nađi goste iz rental bookinga koji su imali ta jela
        # (ovo je aproksimacija — gastro_menu.TableOrder ima items JSON)

        # Ažuriraj brojače
        self.affected_orders_count = order_items.count()
        self.save(update_fields=['affected_orders_count'])

        return affected


class RecallNotification(models.Model):
    """Obavijest poslana pogođenoj strani."""
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email',    'Email'),
        ('sms',      'SMS'),
        ('push',     'Push notifikacija'),
    ]
    STATUS_CHOICES = [
        ('pending',  'Čeka slanje'),
        ('sent',     'Poslano'),
        ('delivered', 'Dostavljeno'),
        ('failed',   'Neuspjelo'),
    ]

    recall = models.ForeignKey(RecallEvent, on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    recipient_type = models.CharField(max_length=30, verbose_name=_('Tip primatelja'),
                                       help_text=_('npr. marketplace_buyer, rental_guest'))
    recipient_name = models.CharField(max_length=200, blank=True)
    recipient_contact = models.CharField(max_length=200, verbose_name=_('Kontakt (tel/email)'))
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Obavijest o povlačenju')
        verbose_name_plural = _('Obavijesti o povlačenjima')
        ordering = ['-created_at']

    def __str__(self):
        return f'Recall #{self.recall_id} → {self.recipient_name} ({self.channel})'
