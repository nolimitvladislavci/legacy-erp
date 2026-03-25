from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.managers import CompanyManager


class WorkGroup(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='work_groups')
    objects = CompanyManager()

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='managed_groups')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                     related_name='work_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Project(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Aktivan'), ('PAUSED', 'Pauziran'),
        ('COMPLETED', 'Završen'), ('ARCHIVED', 'Arhiviran'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='worktime_projects')
    objects = CompanyManager()

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    client_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25.00'))
    is_billable = models.BooleanField(default=True)
    budget_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        help_text='Budžet u satima')
    color = models.CharField(max_length=7, default='#3b82f6', help_text='HEX boja za prikaz')
    work_group = models.ForeignKey(WorkGroup, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='projects')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                      related_name='assigned_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.code}] {self.name}"

    @property
    def hours_used(self):
        return self.time_entries.aggregate(s=models.Sum('duration'))['s'] or Decimal('0')

    @property
    def budget_percentage(self):
        if not self.budget_hours or self.budget_hours == 0:
            return 0
        return min(100, round(float(self.hours_used) / float(self.budget_hours) * 100, 1))

    class Meta:
        ordering = ['name']


class EmployeeProfile(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='employee_profiles')
    objects = CompanyManager()

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='employeeprofile')
    employee_id = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField('OIB', max_length=11, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('20.00'))
    overtime_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('30.00'))
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    bank_account = models.CharField('IBAN', max_length=34, blank=True)
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    date_hired = models.DateField(null=True, blank=True)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('40.00'),
                                        help_text='Tjedni fond sati')
    daily_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('8.00'),
                                       help_text='Dnevni fond sati')
    work_group = models.ForeignKey(WorkGroup, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='employees')
    is_manager = models.BooleanField(default=False)

    # Volonter podrska (Zakon o volontiranju NN 58/07)
    is_volunteer = models.BooleanField(
        default=False,
        verbose_name='Volonter',
        help_text='Iskljucuje iz obracuna placa. Sati se monetiziraju za EU fondove.',
    )
    volunteer_hourly_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('5.00'),
        verbose_name='Vrijednost volonterskog sata (EUR)',
        help_text='Za monetizaciju u EU projektima',
    )
    volunteer_annual_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('238.90'),
        verbose_name='Neoporezivi godisnji limit (EUR)',
        help_text='Maks iznos naknada volonteru godisnje (cca 1800 HRK)',
    )
    volunteer_contract_date = models.DateField(
        null=True, blank=True,
        verbose_name='Datum ugovora o volontiranju',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def is_volunteer_active(self):
        return self.is_volunteer and self.volunteer_contract_date is not None

    class Meta:
        ordering = ['user__last_name', 'user__first_name']


class TimeEntry(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Skica'), ('PENDING', 'Na čekanju'),
        ('APPROVED', 'Odobreno'), ('REJECTED', 'Odbijeno'),
    ]
    TASK_TYPES = [
        ('DEVELOPMENT', 'Razvoj'), ('DESIGN', 'Dizajn'),
        ('MEETING', 'Sastanak'), ('SUPPORT', 'Podrška'),
        ('ADMIN', 'Administracija'), ('TESTING', 'Testiranje'),
        ('PLANNING', 'Planiranje'), ('TRAINING', 'Edukacija'),
        ('TRAVEL', 'Putovanje'), ('OTHER', 'Ostalo'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='time_entries')
    objects = CompanyManager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='time_entries')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='time_entries')
    date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    duration = models.DecimalField(max_digits=6, decimal_places=2,
                                    validators=[MinValueValidator(Decimal('0.01'))])
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='DEVELOPMENT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    billing_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_billed = models.BooleanField(default=False)
    is_overtime = models.BooleanField(default=False)
    invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='time_entries')
    project_lead = models.ForeignKey('burza.ProjectLead', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='time_entries',
                                      verbose_name='Burza projekt')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='approved_entries')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, verbose_name='Razlog odbijanja')
    tags = models.CharField(max_length=200, blank=True, help_text='Tagovi odvojeni zarezom')
    from_timer = models.BooleanField(default=False, help_text='Kreirano putem štoperice')

    # EU Grant motor — monetizacija volonterskih sati
    is_volunteer_work = models.BooleanField(default=False, verbose_name='Volonterski rad')
    grant_monetary_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Monetizirana vrijednost (EUR)',
        help_text='Automatski: sati x volunteer_hourly_value',
    )
    grant_project_code = models.CharField(
        max_length=100, blank=True,
        verbose_name='Sifra EU projekta',
        help_text='Npr. HR.3.1.20-0001, ESF-2026-xxx',
    )

    # ── Zakonski podaci (HR Pravilnik NN 55/24 + DE ArbZG/ArbSchG) ──────────
    ABSENCE_TYPES = [
        ('',          '—'),
        ('ANNUAL',    'Godišnji odmor / Jahresurlaub'),
        ('SICK',      'Bolovanje / Krankheit'),
        ('PAID',      'Plaćeni dopust / Bezahlter Sonderurlaub'),
        ('UNPAID',    'Neplaćeni dopust / Unbezahlter Urlaub'),
        ('HOLIDAY',   'Blagdan / Feiertag'),
        ('PATERNITY', 'Očinski dopust / Vaterschaftsurlaub'),
        ('CARE',      'Dopust za njegu / Pflegeurlaub'),
        ('MILITARY',  'Vojna obveza / Wehrdienst'),
        ('ELECTION',  'Izborna odsutnost / Wahlkampf'),
        ('STRIKE',    'Štrajk / Streik'),
        ('LOCKOUT',   'Isključenje / Aussperrung'),
        ('UNJUSTIFIED','Neopravdani izostanak / Unentschuldigtes Fehlen'),
        ('STOPPAGE',  'Zastoj/krivnja poslodavca / Betriebsstörung'),
        ('OTHER',     'Ostalo / Sonstiges'),
    ]
    absence_type   = models.CharField(max_length=20, choices=ABSENCE_TYPES, blank=True, default='',
                                       verbose_name='Vrsta odsutnosti / Abwesenheitsart')
    is_night_work  = models.BooleanField(default=False, verbose_name='Noćni rad / Nachtarbeit')
    is_holiday_work= models.BooleanField(default=False, verbose_name='Rad na blagdan / Feiertagsarbeit')
    # ── Payroll izračun (auto-popunjava save()) ──────────────────
    regular_hours  = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                         verbose_name='Redovni sati / Reguläre Stunden')
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                         verbose_name='Prekovremeni / Überstunden')
    night_hours    = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                         verbose_name='Noćni sati / Nachtstunden')
    compliance_note = models.CharField(max_length=255, blank=True, default='',
                                        verbose_name='Zakonsko upozorenje / Compliance')

    break_minutes  = models.PositiveSmallIntegerField(default=0,
                                                       verbose_name='Pauza (min) / Pause (Min)')
    daily_rest_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                            verbose_name='Dnevni odmor (h) / Ruhezeit (h)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def calculate_payroll(self):
        """Auto-split hours into regular/overtime/night. Efficient interval math."""
        import datetime as _dt
        dur = self.duration or Decimal('0')

        # Regular vs overtime (threshold from EmployeeProfile or 8h default)
        try:
            emp = self.user.employeeprofile
            daily_limit = emp.daily_hours or Decimal('8')
            base_rate = emp.hourly_rate or Decimal('20')
            ot_rate = emp.overtime_rate or Decimal('30')
        except Exception:
            daily_limit = Decimal('8')
            base_rate = Decimal('20')
            ot_rate = Decimal('30')

        if dur > daily_limit:
            self.regular_hours = daily_limit
            self.overtime_hours = dur - daily_limit
            self.is_overtime = True
        else:
            self.regular_hours = dur
            self.overtime_hours = Decimal('0')

        # Night hours — interval overlap math (22:00-06:00), no minute-loop
        night = Decimal('0')
        if self.start_time and self.end_time:
            dummy = _dt.date(2000, 1, 1)
            s = _dt.datetime.combine(dummy, self.start_time)
            e = _dt.datetime.combine(dummy, self.end_time)
            if e <= s:
                e += _dt.timedelta(days=1)
            total_minutes = (e - s).total_seconds() / 60

            # Night windows: 00:00-06:00 (day 0), 22:00-24:00 (day 0), 00:00-06:00 (day 1)
            night_ranges = [
                (_dt.datetime(2000, 1, 1, 0, 0), _dt.datetime(2000, 1, 1, 6, 0)),
                (_dt.datetime(2000, 1, 1, 22, 0), _dt.datetime(2000, 1, 2, 0, 0)),
                (_dt.datetime(2000, 1, 2, 0, 0), _dt.datetime(2000, 1, 2, 6, 0)),
            ]
            night_mins = 0
            for ns, ne in night_ranges:
                overlap_start = max(s, ns)
                overlap_end = min(e, ne)
                if overlap_start < overlap_end:
                    night_mins += (overlap_end - overlap_start).total_seconds() / 60
            night = Decimal(str(round(night_mins / 60, 2)))

        self.night_hours = night
        if night > 0:
            self.is_night_work = True

        # Billing amount
        night_bonus = base_rate * Decimal('0.25')
        self.billing_amount = (
            self.regular_hours * base_rate
            + self.overtime_hours * ot_rate
            + self.night_hours * night_bonus
        )

        # Compliance checks (ArbZG §3 / ZOR čl.65)
        warnings = []
        if dur > Decimal('10'):
            warnings.append('ArbZG §3: >10h rada')
        if dur > Decimal('12'):
            warnings.append('KRITIČNO: >12h rada')
        if self.break_minutes < 30 and dur >= Decimal('6'):
            warnings.append('ArbZG §4: pauza <30min za 6+h')
        if self.break_minutes < 45 and dur >= Decimal('9'):
            warnings.append('ArbZG §4: pauza <45min za 9+h')
        self.compliance_note = '; '.join(warnings)

    def save(self, *args, **kwargs):
        if self.duration and self.duration > 0 and not self.absence_type:
            self.calculate_payroll()
        # EU Grant motor: auto-monetiziraj volonterske sate
        try:
            from worktime.services.volunteer_guard import VolunteerTaxGuard
            VolunteerTaxGuard.monetize_time_entry(self)
        except Exception:
            pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} | {self.project.code} | {self.date} | {self.duration}h"

    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['project', 'date']),
            models.Index(fields=['status']),
        ]


class ActiveTimer(models.Model):
    """Aktivna štoperica - jedan korisnik može imati samo jedan aktivan timer"""
    STATUS_CHOICES = [
        ('RUNNING', 'Aktivan'),
        ('PAUSED', 'Pauziran'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='active_timers')
    objects = CompanyManager()

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='active_timer')
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    project_lead = models.ForeignKey('burza.ProjectLead', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='active_timers',
                                      verbose_name='Burza projekt')
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TimeEntry.TASK_TYPES, default='DEVELOPMENT')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='RUNNING')
    started_at = models.DateTimeField(default=timezone.now)
    paused_at = models.DateTimeField(null=True, blank=True)
    accumulated_seconds = models.IntegerField(default=0,
        help_text='Akumulirane sekunde iz prethodnih pauza')
    tags = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def elapsed_seconds(self):
        if self.status == 'PAUSED':
            return self.accumulated_seconds
        now = timezone.now()
        running = int((now - self.started_at).total_seconds())
        return self.accumulated_seconds + running

    @property
    def elapsed_display(self):
        total = self.elapsed_seconds
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def elapsed_hours(self):
        return Decimal(str(round(self.elapsed_seconds / 3600, 2)))

    def pause(self):
        if self.status == 'RUNNING':
            now = timezone.now()
            running = int((now - self.started_at).total_seconds())
            self.accumulated_seconds += running
            self.paused_at = now
            self.status = 'PAUSED'
            self.save()

    def resume(self):
        if self.status == 'PAUSED':
            self.started_at = timezone.now()
            self.paused_at = None
            self.status = 'RUNNING'
            self.save()

    def stop_and_save(self):
        duration = self.elapsed_hours
        if duration < Decimal('0.01'):
            duration = Decimal('0.01')
        now = timezone.now()
        entry_date = self.created_at.date()
        start_time = self.created_at.time()
        end_time = now.time()
        try:
            rate = self.user.employeeprofile.hourly_rate
        except Exception:
            rate = self.project.hourly_rate
        billing = duration * rate if self.project.is_billable else Decimal('0')
        entry = TimeEntry.objects.create(
            company=self.company,
            user=self.user, project=self.project, date=entry_date,
            start_time=start_time, end_time=end_time, duration=duration,
            description=self.description, task_type=self.task_type,
            status='PENDING', billing_amount=billing,
            from_timer=True, tags=self.tags,
            project_lead=self.project_lead,
        )
        self.delete()
        return entry

    def discard(self):
        self.delete()

    def __str__(self):
        return f"⏱ {self.user.username} | {self.project.code} | {self.elapsed_display}"

    class Meta:
        verbose_name = 'Aktivna štoperica'
        verbose_name_plural = 'Aktivne štoperice'


class TimeEntryTemplate(models.Model):
    """Predlošci za brzi unos"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='time_templates')
    objects = CompanyManager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='time_templates')
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TimeEntry.TASK_TYPES, default='DEVELOPMENT')
    default_duration = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('8.00'))
    default_start = models.TimeField(null=True, blank=True)
    default_end = models.TimeField(null=True, blank=True)
    tags = models.CharField(max_length=200, blank=True)
    use_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.project.code})"

    class Meta:
        ordering = ['-use_count', 'name']


class DailyNote(models.Model):
    """Dnevne bilješke za radnika"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='daily_notes')
    objects = CompanyManager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='daily_notes')
    date = models.DateField()
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']

class ProjectPhoto(models.Model):
    """Fotografije s gradilišta koje radnici šalju preko mobitela"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='project_photos')
    objects = CompanyManager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_photos')
    project_lead = models.ForeignKey('burza.ProjectLead', on_delete=models.SET_NULL, null=True, blank=True, related_name='site_photos')
    image = models.ImageField(upload_to='site_photos/%Y/%m/')
    note = models.TextField(blank=True, help_text="Bilješka radnika (opcionalno)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Slika - {self.user.username} - {self.created_at.strftime('%d.%m.%Y')}"


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID TIME TRACKING — Clock In/Out + Geofence + ArbZG
# ══════════════════════════════════════════════════════════════════════════════

class TimeLog(models.Model):
    """Physical clock-in/clock-out log with GPS verification."""
    STATUS_CHOICES = [
        ('OPEN', 'Aktivna smjena'),
        ('CLOSED', 'Zatvorena'),
        ('FLAGGED', 'Zastavica'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='time_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='time_logs')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    date = models.DateField(db_index=True)

    # GPS at clock-in/out
    clock_in_lat = models.FloatField(null=True, blank=True)
    clock_in_lon = models.FloatField(null=True, blank=True)
    clock_out_lat = models.FloatField(null=True, blank=True)
    clock_out_lon = models.FloatField(null=True, blank=True)
    clock_in_distance = models.FloatField(null=True, blank=True,
        help_text='Udaljenost od firme pri prijavi (m)')
    clock_out_distance = models.FloatField(null=True, blank=True,
        help_text='Udaljenost od firme pri odjavi (m)')

    # Calculated fields
    gross_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0,
        verbose_name='Bruto sati (bez odbitka)')
    break_minutes = models.PositiveSmallIntegerField(default=0,
        verbose_name='ArbZG pauza (min)')
    payable_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0,
        verbose_name='Neto sati za placu')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    is_audited = models.BooleanField(default=False)
    audit_flag = models.CharField(max_length=255, blank=True,
        help_text='Revizorska zastavica')
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'worktime_timelog'
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.username} | {self.date} | {self.gross_hours}h"

    def calculate_arbzg_break(self):
        """
        ArbZG section 4 — mandatory break deduction:
        - 6-9 hours work: 30 min break
        - >9 hours work: 45 min break
        - <=6 hours: no mandatory break
        """
        if self.gross_hours <= 6:
            return 0
        elif self.gross_hours <= 9:
            return 30
        else:
            return 45

    def close_shift(self):
        """Close shift, calculate ArbZG break, compute payable hours."""
        if not self.end_time or not self.start_time:
            return
        delta = self.end_time - self.start_time
        self.gross_hours = Decimal(str(round(delta.total_seconds() / 3600, 2)))
        self.break_minutes = self.calculate_arbzg_break()
        break_hours = Decimal(str(self.break_minutes)) / Decimal('60')
        self.payable_hours = self.gross_hours - break_hours
        if self.payable_hours < 0:
            self.payable_hours = Decimal('0')
        self.status = 'CLOSED'
        self.save()


class ActivityEvent(models.Model):
    """Physical proof-of-work events from IoT/scanners/app actions."""
    ACTION_CHOICES = [
        ('GENESIS_SCAN', 'Genesis QR sken'),
        ('PALLET_SCAN', 'Sken palete'),
        ('WEIGHT_EVENT', 'Vaganje'),
        ('DELIVERY_SCAN', 'Sken isporuke'),
        ('PHOTO', 'Fotografija'),
        ('APP_ACTION', 'Akcija u aplikaciji'),
        ('VEHICLE_START', 'Pokretanje vozila'),
        ('MANUAL_CHECK', 'Rucna provjera'),
        ('POS_CHECKOUT', 'POS Naplata'),
        ('POS_VOID', 'POS Storno'),
        ('POS_OPEN_SHIFT', 'POS Otvaranje smjene'),
        ('POS_CLOSE_SHIFT', 'POS Zatvaranje smjene'),
        ('GOODS_RECEIPT', 'Primka potvrđena'),
        ('TRANSFER_OUT', 'Izdatnica potvrđena'),
        ('INVENTURA_COMPLETE', 'Inventura završena'),
        ('ARCHIVE_UPLOAD', 'Dokument arhiviran'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='activity_events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='activity_events')
    timestamp = models.DateTimeField(db_index=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'worktime_activity_event'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} | {self.action} | {self.timestamp}"


class TravelOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", "Nacrt"),
        ("approved", "Odobren"),
        ("completed", "Završen"),
        ("cancelled", "Otkazan"),
    ]
    TRANSPORT_CHOICES = [
        ("car_personal", "Osobni automobil"),
        ("car_company", "Službeni automobil"),
        ("bus", "Autobus"),
        ("train", "Vlak"),
        ("plane", "Avion"),
        ("other", "Ostalo"),
    ]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE,
                                null=True, blank=True, related_name="travel_orders")
    objects = CompanyManager()
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="travel_orders")
    order_number = models.CharField(max_length=50)  # PN-2026-0001

    destination = models.CharField(max_length=255)
    purpose = models.TextField()

    departure_date = models.DateTimeField()
    return_date = models.DateTimeField()

    transport_type = models.CharField(max_length=50, choices=TRANSPORT_CHOICES, default="car_personal")

    # Costs
    distance_km = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    per_diem_rate = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("26.55"))
    per_diem_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    per_diem_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mileage_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.40"))
    mileage_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="approved_travel_orders")
    approved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-departure_date"]
        unique_together = [["company", "order_number"]]

    def __str__(self):
        return f"{self.order_number} - {self.destination}"

    def calculate_costs(self):
        self.per_diem_total = self.per_diem_days * self.per_diem_rate
        self.mileage_total = self.distance_km * self.mileage_rate
        self.total_cost = self.per_diem_total + self.mileage_total + self.other_costs

    def save(self, *args, **kwargs):
        self.calculate_costs()
        super().save(*args, **kwargs)

    @staticmethod
    def next_order_number(company):
        year = timezone.now().year
        last = TravelOrder.objects.filter(
            company=company,
            order_number__startswith=f"PN-{year}-"
        ).order_by("-order_number").first()
        if last:
            try:
                num = int(last.order_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"PN-{year}-{num:04d}"


class AnomalyReport(models.Model):
    """AI revizorski nalaz — generira Celery task nocu."""
    SEVERITY_CHOICES = [
        ('low',    'Nisko (Upozorenje)'),
        ('medium', 'Srednje (Istraga)'),
        ('high',   'Visoko (Prekrsaj)'),
    ]
    ANOMALY_TYPES = [
        ('GHOST_SHIFT',    'Smjena bez aktivnosti'),
        ('NO_ACTIVITY',    'Duga pauza bez evidencije'),
        ('GPS_MISMATCH',   'GPS ne odgovara lokaciji firme'),
        ('OVERTIME',       'Prekoracenje zakonskog max'),
        ('MISSING_BREAK',  'Nedostajuca zakonska pauza'),
        ('DOUBLE_SHIFT',   'Dvije paralelne smjene'),
        ('VOLUNTEER_LIMIT', 'Probijen neoporezivi limit volontera'),
        ('VOLUNTEER_NO_CONTRACT', 'Volontiranje bez ugovora'),
    ]

    time_log = models.ForeignKey(
        TimeLog, on_delete=models.CASCADE,
        related_name='anomalies', null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='anomaly_reports'
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True
    )

    detected_at = models.DateTimeField(auto_now_add=True)
    anomaly_type = models.CharField(max_length=30, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)

    description = models.TextField(help_text='AI objasnjenje nalaza')
    ai_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Sigurnost AI-ja 0-100%'
    )

    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_anomalies'
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        db_table = 'worktime_anomaly_report'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['user', 'detected_at']),
            models.Index(fields=['company', 'severity', 'is_resolved']),
        ]

    def __str__(self):
        return f"{self.user.username} -- {self.anomaly_type} ({self.severity})"


# ═══════════════════════════════════════════════════════════════
#  Travel Order Attachments (računi, karte, hotel...)
# ═══════════════════════════════════════════════════════════════

class TravelExpense(models.Model):
    """Pojedinačni trošak na putnom nalogu — s prilogom (račun/karta)."""

    EXPENSE_TYPES = [
        ('fuel', 'Gorivo'),
        ('toll', 'Cestarina'),
        ('parking', 'Parking'),
        ('hotel', 'Smještaj'),
        ('food', 'Prehrana'),
        ('ticket', 'Karta (bus/vlak/avion)'),
        ('taxi', 'Taksi / prijevoz'),
        ('registration', 'Kotizacija / prijava'),
        ('equipment', 'Oprema / materijal'),
        ('costume', 'Kostim / uniforma'),  # KUD
        ('licence', 'Dozvola / licence'),   # Ribolov/Lov
        ('other', 'Ostalo'),
    ]

    travel_order = models.ForeignKey(
        TravelOrder, on_delete=models.CASCADE, related_name='expenses',
    )
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPES, default='other')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_file = models.FileField(upload_to='travel_receipts/%Y/%m/', blank=True)
    receipt_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['receipt_date', 'created_at']
        verbose_name = 'Trošak putnog naloga'
        verbose_name_plural = 'Troškovi putnog naloga'

    def __str__(self):
        return f'{self.get_expense_type_display()}: {self.amount} EUR — {self.description}'
