"""EDIK — e-Porezna status tracking."""
from django.db import models, DatabaseError, IntegrityError
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class TaxFormType(models.Model):
    """Vrsta poreznog obrasca."""
    FREQUENCY_CHOICES = [
        ('monthly', 'Mjesecno'),
        ('quarterly', 'Kvartalno'),
        ('yearly', 'Godisnje'),
    ]
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    deadline_day = models.IntegerField(default=20,
        help_text='Dan u mjesecu do kad treba predati')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Vrsta obrasca'
        verbose_name_plural = 'Vrste obrazaca'

    def __str__(self):
        return f'{self.code} — {self.name}'


class TaxSubmission(models.Model):
    """Evidencija predaje poreznog obrasca."""
    STATUS_CHOICES = [
        ('draft', 'Priprema'),
        ('ready', 'Spremno za predaju'),
        ('submitted', 'Predano'),
        ('accepted', 'Prihvaceno'),
        ('rejected', 'Odbijeno'),
        ('correction', 'Ispravak predan'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='tax_submissions')
    form_type = models.ForeignKey(TaxFormType, on_delete=models.PROTECT)
    period_year = models.IntegerField()
    period_month = models.IntegerField(null=True, blank=True)
    period_quarter = models.IntegerField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    prepared_date = models.DateTimeField(null=True, blank=True)
    submitted_date = models.DateTimeField(null=True, blank=True)
    response_date = models.DateTimeField(null=True, blank=True)
    deadline_date = models.DateField()

    xml_file = models.FileField(upload_to='edik/submissions/', blank=True)
    response_xml = models.FileField(upload_to='edik/responses/', blank=True)

    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    rejection_reason = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        unique_together = [('company', 'form_type', 'period_year', 'period_month')]
        ordering = ['-period_year', '-period_month', 'form_type__code']
        verbose_name = 'Predaja obrasca'
        verbose_name_plural = 'Predaje obrazaca'

    def __str__(self):
        period = f'{self.period_month:02d}/{self.period_year}' if self.period_month else str(self.period_year)
        return f'{self.form_type.code} {period} — {self.get_status_display()}'

    @property
    def is_overdue(self):
        from datetime import date
        return self.status in ('draft', 'ready') and self.deadline_date < date.today()


class TaxCalendar(models.Model):
    """Porezni kalendar — rokovi predaje."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='tax_calendar')
    form_type = models.ForeignKey(TaxFormType, on_delete=models.CASCADE)
    period_year = models.IntegerField()
    period_month = models.IntegerField(null=True, blank=True)
    deadline = models.DateField()
    is_completed = models.BooleanField(default=False)
    submission = models.ForeignKey(TaxSubmission, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['deadline']
        verbose_name = 'Porezni rok'
        verbose_name_plural = 'Porezni rokovi'

    def __str__(self):
        return f'{self.form_type.code} — rok {self.deadline}'
