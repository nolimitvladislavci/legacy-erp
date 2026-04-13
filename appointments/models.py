from django.contrib.auth.models import User
from django.db import models, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager

BRANCH_TYPES = [
    ('general',     'Općenito'),
    ('optic',       'Optičar'),
    ('hairdresser', 'Frizer / Kozmetičar'),
    ('tax',         'Porezni savjetnik / Računovođa'),
    ('medical',     'Medicinska ordinacija'),
    ('dental',      'Stomatolog'),
    ('gym',         'Fitness / Teretana'),
    ('beauty',      'Kozmetički salon'),
    ('mechanic',    'Auto servis / Mehaničar'),
    ('bakery',      'Pekara / Uslužno pečenje'),
    ('legal',       'Odvjetnik / Notar'),
]
BRANCH_ICONS = {
    'general':     'fa-calendar-check',
    'optic':       'fa-eye',
    'hairdresser': 'fa-cut',
    'tax':         'fa-file-invoice-dollar',
    'medical':     'fa-stethoscope',
    'dental':      'fa-tooth',
    'gym':         'fa-dumbbell',
    'beauty':      'fa-spa',
    'mechanic':    'fa-car',
    'bakery':      'fa-bread-slice',
    'legal':       'fa-balance-scale',
}


class Appointment(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Tvrtka')
    STATUS_CHOICES = [
        ('scheduled', 'Zakazano'),
        ('confirmed', 'Potvrđeno'),
        ('completed', 'Završeno'),
        ('cancelled', 'Otkazano'),
        ('no_show',   'Nije došao'),
    ]
    TYPE_CHOICES = [
        ('service', 'Kratka usluga'),
        ('rental',  'Dugoročni najam'),
        ('event',   'Događaj'),
        ('meeting', 'Obični sastanak'),
    ]
    title            = models.CharField(max_length=200, verbose_name='Naziv')
    description      = models.TextField(blank=True, verbose_name='Opis')
    start_time       = models.DateTimeField(verbose_name='Početak')
    end_time         = models.DateTimeField(verbose_name='Kraj')
    location         = models.CharField(max_length=200, blank=True, verbose_name='Lokacija')
    is_online        = models.BooleanField(default=False, verbose_name='Online')
    meeting_link     = models.CharField(max_length=200, blank=True, verbose_name='Link za sastanak')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name='Status')
    client           = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments', verbose_name='Klijent')
    employee         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments', verbose_name='Zaposlenik')
    related_project  = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments', verbose_name='Projekt')
    service          = models.ForeignKey('BookingService', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Odabrana usluga')
    resource         = models.ForeignKey('BookingResource', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Zauzeti resurs')
    actor_resource   = models.ForeignKey('BookingResource', on_delete=models.SET_NULL, null=True, blank=True, related_name='actor_appointments', verbose_name='Dodijeljeni izvrsitelj')
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='meeting', verbose_name='Tip termina')
    is_all_day       = models.BooleanField(default=False, verbose_name='Cjelodnevni/Višednevni najam')
    color            = models.CharField(max_length=20, default='#3b82f6', verbose_name='Boja u kalendaru')
    total_price      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Ukupna cijena')
    payment_method   = models.CharField(max_length=50, default='invoice', verbose_name='Način plaćanja')
    whatsapp_number  = models.CharField(max_length=50, blank=True, verbose_name='WhatsApp')
    whatsapp_reminder_sent = models.BooleanField(default=False)

    # Baking intake
    token_number = models.IntegerField(default=0, verbose_name='Limeni broj')
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Tezina (kg)')
    should_salt = models.BooleanField(null=True, blank=True, verbose_name='Soliti')
    intake_notes = models.TextField(blank=True, default='', verbose_name='Napomena prijema')
    intake_at = models.DateTimeField(null=True, blank=True, verbose_name='Zaprimljeno')
    intake_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='intakes', verbose_name='Zaprimio')
    ready_at = models.DateTimeField(null=True, blank=True, verbose_name='Gotovo')
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name='Preuzeto')
    email_reminder_sent    = models.BooleanField(default=False)
    reminder_sent_at       = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        db_table = 'appointments_appointment'
        verbose_name = 'Termin'
        verbose_name_plural = 'Termini'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%d.%m.%Y %H:%M')}"


class BookingResource(models.Model):
    RESOURCE_TYPES = [
        ('ljudstvo',   'Ljudski resurs (Radnik, Majstor)'),
        ('nekretnina', 'Nekretnina (Soba, Garsonjera, Restoran)'),
        ('oprema',     'Oprema / Vozilo / Aparat'),
    ]
    company        = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Tvrtka')
    name           = models.CharField(max_length=100, verbose_name='Naziv resursa')
    resource_type  = models.CharField(max_length=50, choices=RESOURCE_TYPES, default='nekretnina', verbose_name='Tip resursa')
    is_active      = models.BooleanField(default=True, verbose_name='Aktivan')
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena po satu')
    price_per_day  = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena po danu')
    capacity       = models.PositiveIntegerField(blank=True, null=True, verbose_name='Kapacitet (broj osoba)')
    description    = models.TextField(blank=True, verbose_name='Opis')
    total_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=50, default='invoice')
    whatsapp_number = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'Resurs za najam/rezervaciju'
        verbose_name_plural = 'Resursi'

    def __str__(self):
        return f"{self.name} ({self.get_resource_type_display()})"


class BookingService(models.Model):
    SLOT_DURATIONS = [
        (15, '15 min'), (20, '20 min'), (30, '30 min'),
        (45, '45 min'), (60, '1 sat'), (90, '1h 30min'), (120, '2 sata'),
    ]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="booking_services", null=True, blank=True)
    name                  = models.CharField(max_length=150, verbose_name='Naziv usluge')
    description           = models.TextField(blank=True, verbose_name='Opis usluge')
    duration              = models.DurationField(verbose_name='Trajanje usluge (HH:MM:SS)')
    price                 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena (EUR)')
    resource_type         = models.CharField(max_length=50, choices=BookingResource.RESOURCE_TYPES, default='ljudstvo', verbose_name='Vezano za tip resursa')
    is_active             = models.BooleanField(default=True, verbose_name='Aktivno za javnost')
    branch_type           = models.CharField(max_length=20, choices=BRANCH_TYPES, default='general', verbose_name='Tip djelatnosti')
    slot_duration_minutes = models.PositiveIntegerField(choices=SLOT_DURATIONS, default=15, verbose_name='Korak termina (min)')
    color                 = models.CharField(max_length=20, default='#10b981', verbose_name='Boja usluge')
    icon                  = models.CharField(max_length=60, default='fa-calendar-check', verbose_name='Font Awesome ikona')
    requires_actor    = models.BooleanField(default=True, verbose_name='Zahtijeva izvrsitelja (radnika)')
    requires_resource = models.BooleanField(default=True, verbose_name='Zahtijeva fizicki resurs')
    requires_dossier      = models.BooleanField(default=False, verbose_name='Potreban karton klijenta')
    total_price           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method        = models.CharField(max_length=50, default='invoice')
    whatsapp_number       = models.CharField(max_length=50, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Usluga'
        verbose_name_plural = 'Usluge'

    def __str__(self):
        return f"{self.name} ({self.duration})"

    @property
    def duration_minutes(self):
        return int(self.duration.total_seconds() // 60)

    @property
    def branch_icon(self):
        return BRANCH_ICONS.get(self.branch_type, 'fa-calendar-check')


class WorkingHours(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Ponedjeljak'), (1, 'Utorak'), (2, 'Srijeda'),
        (3, 'Četvrtak'), (4, 'Petak'), (5, 'Subota'), (6, 'Nedjelja')
    ]
    resource       = models.ForeignKey(BookingResource, on_delete=models.CASCADE, related_name='working_hours', verbose_name='Resurs')
    day_of_week    = models.IntegerField(choices=DAYS_OF_WEEK, verbose_name='Dan u tjednu')
    start_time     = models.TimeField(verbose_name='Početak rada')
    end_time       = models.TimeField(verbose_name='Kraj rada')
    is_day_off     = models.BooleanField(default=False, verbose_name='Neradni dan')
    total_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=50, default='invoice')
    whatsapp_number = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'Radno vrijeme'
        verbose_name_plural = 'Radna vremena'
        unique_together = ('resource', 'day_of_week')
        ordering = ['resource', 'day_of_week']

    def __str__(self):
        if self.is_day_off:
            return f"{self.resource.name} - {self.get_day_of_week_display()} (Slobodno)"
        return f"{self.resource.name} - {self.get_day_of_week_display()} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


# ── KLIJENTSKI KARTON (FASCIKL) ───────────────────────────────────────────────

class ClientDossier(models.Model):
    company     = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Tvrtka')
    client      = models.ForeignKey('partners.Partner', on_delete=models.CASCADE, related_name='dossiers', verbose_name='Klijent')
    branch_type = models.CharField(max_length=20, choices=BRANCH_TYPES, default='general', verbose_name='Tip kartona')
    notes       = models.TextField(blank=True, verbose_name='Opće napomene')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dossiers_created')

    class Meta:
        verbose_name = 'Klijentski karton'
        verbose_name_plural = 'Klijentski kartoni'
        unique_together = [('company', 'client')]
        ordering = ['-updated_at']

    def __str__(self):
        return f"Karton: {self.client.name} ({self.get_branch_type_display()})"

    @property
    def branch_icon(self):
        return BRANCH_ICONS.get(self.branch_type, 'fa-folder-open')


class DossierEntry(models.Model):
    ENTRY_TYPES = [
        ('note',         'Bilješka'),
        ('finding',      'Nalaz / Pregled'),
        ('prescription', 'Recept / Nalog'),
        ('measurement',  'Mjerenje'),
        ('document',     'Dokument'),
        ('image',        'Slika'),
        ('treatment',    'Tretman'),
    ]
    ENTRY_ICONS = {
        'note':         'fa-sticky-note',
        'finding':      'fa-microscope',
        'prescription': 'fa-prescription',
        'measurement':  'fa-ruler',
        'document':     'fa-file-alt',
        'image':        'fa-image',
        'treatment':    'fa-magic',
    }
    ENTRY_COLORS = {
        'note':         '#6b7280',
        'finding':      '#3b82f6',
        'prescription': '#10b981',
        'measurement':  '#f59e0b',
        'document':     '#8b5cf6',
        'image':        '#ec4899',
        'treatment':    '#c9a84c',
    }
    dossier         = models.ForeignKey(ClientDossier, on_delete=models.CASCADE, related_name='entries', verbose_name='Karton')
    appointment     = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='dossier_entries', verbose_name='Vezani termin')
    entry_type      = models.CharField(max_length=20, choices=ENTRY_TYPES, default='note', verbose_name='Vrsta unosa')
    title           = models.CharField(max_length=200, verbose_name='Naslov')
    content         = models.TextField(blank=True, verbose_name='Sadržaj / Napomene')
    file            = models.FileField(upload_to='dossier/', null=True, blank=True, verbose_name='Prilog')
    structured_data = models.JSONField(default=dict, blank=True, verbose_name='Strukturirani podaci')
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Unio')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Unos u karton'
        verbose_name_plural = 'Unosi u karton'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.title}"

    @property
    def entry_icon(self):
        return self.ENTRY_ICONS.get(self.entry_type, 'fa-file')

    @property
    def entry_color(self):
        return self.ENTRY_COLORS.get(self.entry_type, '#6b7280')
