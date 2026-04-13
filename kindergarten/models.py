"""
Kindergarten — Modul za privatne vrtiće.

Modeli:
  KindergartenGroup — Grupa (Bubamare, Leptirići...)
  Child — Dijete (GDPR čl.8: pristanak roditelja OBAVEZAN)
  Guardian — Roditelj/skrbnik
  ChildGuardian — M2M s relacijom
  Attendance — Dnevna evidencija dolazaka
  MonthlyBilling — Mjesečna naplata s automatskim odbitkom izostanaka
  DailyReport — Dnevni izvještaj odgajateljice
  Announcement — Obavijest roditeljima
"""
from django.db import models, DatabaseError, IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist

from core.managers import CompanyManager

User = get_user_model()


class KindergartenGroup(models.Model):
    """Vrtićka grupa (Bubamare, Leptirići, Medvjedići...)."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='kindergarten_groups',
    )
    name = models.CharField(max_length=100, verbose_name=_('Naziv grupe'))
    age_from = models.PositiveSmallIntegerField(default=1, verbose_name=_('Dob od (godina)'))
    age_to = models.PositiveSmallIntegerField(default=3, verbose_name=_('Dob do (godina)'))
    capacity = models.PositiveSmallIntegerField(default=20, verbose_name=_('Kapacitet'))
    educator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kindergarten_groups', verbose_name=_('Odgajateljica'),
    )
    monthly_price = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('200.00'),
        verbose_name=_('Mjesečna cijena (EUR)'),
    )
    meal_daily_price = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('3.50'),
        verbose_name=_('Cijena obroka/dan (EUR)'),
        help_text=_('Odbitak po danu izostanka'),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        app_label = "kindergarten"
        ordering = ['name']
        verbose_name = _('Vrtićka grupa')
        verbose_name_plural = _('Vrtićke grupe')

    def __str__(self):
        return self.name

    @property
    def enrolled_count(self):
        return self.children.filter(status='active').count()

    @property
    def available_spots(self):
        return max(0, self.capacity - self.enrolled_count)


class Child(models.Model):
    """Dijete upisano u vrtić. GDPR čl.8: pristanak roditelja OBAVEZAN."""

    class Status(models.TextChoices):
        ACTIVE = 'active', _('Aktivan')
        INACTIVE = 'inactive', _('Neaktivan')
        WAITLIST = 'waitlist', _('Lista čekanja')

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='kindergarten_children',
    )
    group = models.ForeignKey(
        KindergartenGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name=_('Grupa'),
    )
    first_name = models.CharField(max_length=100, verbose_name=_('Ime'))
    last_name = models.CharField(max_length=100, verbose_name=_('Prezime'))
    date_of_birth = models.DateField(verbose_name=_('Datum rođenja'))
    oib = models.CharField(max_length=13, blank=True, verbose_name='OIB')
    gender = models.CharField(max_length=1, choices=[('M', _('Muško')), ('F', _('Žensko'))],
                              blank=True)

    # Zdravstveno (NE medicinski podaci — samo alergije za kuhinju)
    allergies = models.TextField(blank=True, verbose_name=_('Alergije na hranu'),
                                 help_text=_('Bitno za kuhinju — NE medicinski karton'))
    special_needs = models.TextField(blank=True, verbose_name=_('Posebne napomene'))
    dietary_requirements = models.CharField(max_length=200, blank=True,
                                            verbose_name=_('Prehrambeni zahtjevi'),
                                            help_text=_('Vegetarijanac, bez glutena, itd.'))

    # Upis
    enrolled_date = models.DateField(null=True, blank=True, verbose_name=_('Datum upisa'))
    unenrolled_date = models.DateField(null=True, blank=True, verbose_name=_('Datum ispisa'))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    # GDPR
    gdpr_consent = models.BooleanField(default=False,
        verbose_name=_('GDPR pristanak roditelja'),
        help_text=_('Čl.8 GDPR — obavezan za djecu < 16'))
    gdpr_consent_date = models.DateTimeField(null=True, blank=True)
    photo_consent = models.BooleanField(default=False,
        verbose_name=_('Pristanak za fotografije'),
        help_text=_('Smije li se objaviti slika djeteta na portalu'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyManager()

    class Meta:
        app_label = "kindergarten"
        ordering = ['last_name', 'first_name']
        verbose_name = _('Dijete')
        verbose_name_plural = _('Djeca')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    @property
    def primary_guardian(self):
        cg = self.child_guardians.filter(is_primary=True).select_related('guardian').first()
        return cg.guardian if cg else None


class Guardian(models.Model):
    """Roditelj ili skrbnik."""

    class Relation(models.TextChoices):
        MOTHER = 'mother', _('Majka')
        FATHER = 'father', _('Otac')
        GUARDIAN = 'guardian', _('Skrbnik')
        GRANDPARENT = 'grandparent', _('Baka/Djed')
        OTHER = 'other', _('Ostalo')

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='kindergarten_guardians',
    )
    first_name = models.CharField(max_length=100, verbose_name=_('Ime'))
    last_name = models.CharField(max_length=100, verbose_name=_('Prezime'))
    oib = models.CharField(max_length=13, blank=True, verbose_name='OIB')
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=30, verbose_name=_('Telefon'))
    phone_secondary = models.CharField(max_length=30, blank=True, verbose_name=_('Drugi telefon'))
    address = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa'))

    # Portal pristup
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='guardian_profile',
        help_text=_('Ako povezan — roditelj ima pristup portalu'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        app_label = "kindergarten"
        ordering = ['last_name', 'first_name']
        verbose_name = _('Roditelj/Skrbnik')
        verbose_name_plural = _('Roditelji/Skrbnici')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class ChildGuardian(models.Model):
    """M2M veza dijete ↔ roditelj s relacijom."""
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='child_guardians')
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name='guardian_children')
    relation = models.CharField(max_length=15, choices=Guardian.Relation.choices,
                                default=Guardian.Relation.MOTHER)
    is_primary = models.BooleanField(default=False, verbose_name=_('Primarni kontakt'))
    can_pickup = models.BooleanField(default=True, verbose_name=_('Smije preuzeti dijete'))
    is_billing_contact = models.BooleanField(default=False, verbose_name=_('Prima račune'))

    class Meta:
        app_label = "kindergarten"
        unique_together = ['child', 'guardian']
        verbose_name = _('Veza dijete-roditelj')


class Attendance(models.Model):
    """Dnevna evidencija dolazaka."""

    class Status(models.TextChoices):
        PRESENT = 'present', _('Prisutno')
        ABSENT_SICK = 'sick', _('Bolesno')
        ABSENT_EXCUSED = 'excused', _('Opravdano odsutno')
        ABSENT_UNEXCUSED = 'unexcused', _('Neopravdano odsutno')

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(verbose_name=_('Datum'))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    arrival_time = models.TimeField(null=True, blank=True, verbose_name=_('Dolazak'))
    departure_time = models.TimeField(null=True, blank=True, verbose_name=_('Odlazak'))
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = "kindergarten"
        unique_together = ['child', 'date']
        ordering = ['-date', 'child__last_name']
        verbose_name = _('Evidencija dolaska')
        verbose_name_plural = _('Evidencija dolazaka')

    def __str__(self):
        return f'{self.child} — {self.date} — {self.get_status_display()}'

    @property
    def is_absent(self):
        return self.status != self.Status.PRESENT


class MonthlyBilling(models.Model):
    """Mjesečna naplata za dijete — automatski odbitak izostanaka."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Nacrt')
        SENT = 'sent', _('Poslano')
        PAID = 'paid', _('Plaćeno')
        OVERDUE = 'overdue', _('Dospjelo')

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='billings')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()

    base_amount = models.DecimalField(max_digits=8, decimal_places=2,
                                       verbose_name=_('Osnovna cijena'))
    days_absent = models.PositiveSmallIntegerField(default=0,
                                                    verbose_name=_('Dana odsutan'))
    meal_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                          verbose_name=_('Odbitak obroka'))
    total_amount = models.DecimalField(max_digits=8, decimal_places=2,
                                        verbose_name=_('Ukupno za platiti'))

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Rok plaćanja'))
    paid_date = models.DateField(null=True, blank=True)

    # Poziv na broj = OIB roditelja + godina + mjesec
    payment_reference = models.CharField(max_length=30, blank=True,
                                          verbose_name=_('Poziv na broj'))

    invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kindergarten_billings',
        help_text=_('Povezani račun iz invoicing modula'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "kindergarten"
        unique_together = ['child', 'year', 'month']
        ordering = ['-year', '-month']
        verbose_name = _('Mjesečna naplata')
        verbose_name_plural = _('Mjesečne naplate')

    def __str__(self):
        return f'{self.child} — {self.month}/{self.year} — {self.total_amount} EUR'

    def calculate(self):
        """Izračunaj ukupno: osnovna cijena - odbitak za izostanke."""
        group = self.child.group
        if group:
            self.base_amount = group.monthly_price
            # Prebroj dane odsutnosti iz Attendance
            absent_days = Attendance.objects.filter(
                child=self.child,
                date__year=self.year,
                date__month=self.month,
                status__in=['sick', 'excused'],
            ).count()
            self.days_absent = absent_days
            self.meal_deduction = group.meal_daily_price * absent_days
            self.total_amount = max(Decimal('0'), self.base_amount - self.meal_deduction)
        # Payment reference: OIB-GGMM
        guardian = self.child.primary_guardian
        if guardian and guardian.oib:
            self.payment_reference = f'{guardian.oib}-{self.year}{self.month:02d}'


class DailyReport(models.Model):
    """Dnevni izvještaj odgajateljice — vidljiv na roditeljskom portalu."""
    group = models.ForeignKey(KindergartenGroup, on_delete=models.CASCADE,
                               related_name='daily_reports')
    date = models.DateField(verbose_name=_('Datum'))
    content = models.TextField(verbose_name=_('Izvještaj'),
                                help_text=_('Što smo danas radili, učili, jeli...'))
    educator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Slike (JSON lista URL-ova iz media/)
    photos = models.JSONField(default=list, blank=True,
                               help_text=_('Lista URL-ova slika'))

    is_published = models.BooleanField(default=False,
        verbose_name=_('Objavljeno na portalu'),
        help_text=_('Samo objavljeni izvještaji su vidljivi roditeljima'))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "kindergarten"
        unique_together = ['group', 'date']
        ordering = ['-date']
        verbose_name = _('Dnevni izvještaj')
        verbose_name_plural = _('Dnevni izvještaji')

    def __str__(self):
        return f'{self.group} — {self.date}'


class Announcement(models.Model):
    """Obavijest roditeljima (roditeljski sastanak, izlet, promjena jelovnika)."""

    class Priority(models.TextChoices):
        NORMAL = 'normal', _('Normalno')
        IMPORTANT = 'important', _('Važno')
        URGENT = 'urgent', _('Hitno')

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='kindergarten_announcements',
    )
    group = models.ForeignKey(
        KindergartenGroup, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Grupa (prazno = sve grupe)'),
    )
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    content = models.TextField(verbose_name=_('Sadržaj'))
    priority = models.CharField(max_length=10, choices=Priority.choices,
                                 default=Priority.NORMAL)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        app_label = "kindergarten"
        ordering = ['-published_at']
        verbose_name = _('Obavijest')
        verbose_name_plural = _('Obavijesti')

    def __str__(self):
        return self.title
