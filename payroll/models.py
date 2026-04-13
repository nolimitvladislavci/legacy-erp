"""
payroll/models.py — Payroll modul

Arhitektura:
  PayrollRun  → jedan obračun za (company, month, year)
  Payslip     → jedan listić po radniku, agregira TimeEntry podatke
  PayrollJournalLink → veza s konto JournalEntry (audit trail)

Integracija:
  - Podatke vuče iz worktime.TimeEntry (već ima regular/overtime/night hours)
  - EmployeeProfile (hourly_rate, overtime_rate, bank_account IBAN)
  - Pain001Generator iz finance.bank_parsers (SALA plaćanja)
  - konto.services.book_payroll() (TEM-PLACA temeljnica)
  - Company.country (HR/DE) određuje porezni engine
"""

from django.conf import settings
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class PayrollRun(models.Model):
    """
    Jedan obračunski ciklus: (company, year, month).
    Nakon finalizacije, nema izmjena (GoBD/audit).
    """
    STATUS_CHOICES = [
        ('DRAFT',     _('Nacrt')),
        ('LOCKED',    _('Zaključan — obračun u toku')),
        ('FINALIZED', _('Finaliziran — isplata odobrena')),
        ('PAID',      _('Isplaćeno — pain.001 generiran')),
    ]

    company   = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                   related_name='payroll_runs')
    year      = models.IntegerField(verbose_name=_('Godina'))
    month     = models.IntegerField(verbose_name=_('Mjesec'))
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # Ukupni agregirani iznosi (popunjava se pri finalizaciji)
    total_gross  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_net    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax    = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # pain.001 export
    pain001_generated_at = models.DateTimeField(null=True, blank=True)
    pain001_batch_id     = models.CharField(max_length=100, blank=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='payroll_runs_created')
    created_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    objects = CompanyManager()

    class Meta:
        unique_together = ('company', 'year', 'month')
        ordering = ['-year', '-month']
        verbose_name = _('Obračun plaća')
        verbose_name_plural = _('Obračuni plaća')

    def __str__(self):
        return f"{self.company.name} — {self.month:02d}/{self.year}"

    @property
    def period_label(self):
        import calendar
        return f"{calendar.month_name[self.month]} {self.year}"

    def lock(self):
        """
        Zaključava obračun za izmjene dok traje izračun.
        Koristi select_for_update() — atomarno.
        """
        with transaction.atomic():
            run = PayrollRun.objects.select_for_update().get(pk=self.pk)
            if run.status not in ('DRAFT',):
                raise ValueError(f"Ne može se zaključati: status je {run.status}")
            run.status = 'LOCKED'
            run.save(update_fields=['status'])
            self.status = 'LOCKED'

    def unlock_to_draft(self):
        """Vraća u DRAFT (samo ako nije FINALIZED/PAID)."""
        if self.status in ('FINALIZED', 'PAID'):
            raise ValueError("Finalizirani obračun ne može se otvoriti.")
        self.status = 'DRAFT'
        self.save(update_fields=['status'])


class Payslip(models.Model):
    """
    Obračunski listić za jednog radnika.

    Satnica (hourly_rate) se kopira u trenutku obračuna —
    naknadna izmjena EmployeeProfile ne smije retroaktivno
    mijenjati stare obračune (GoBD §146 Abs.4).
    """
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE,
                                     related_name='payslips')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.PROTECT,
                                     related_name='payslips')

    # Sati agregirati iz TimeEntry (APPROVED) za period
    regular_hours  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    night_hours    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_hours    = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Satnice u trenutku obračuna (snapshot — ne mijenja se!)
    hourly_rate_snapshot   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_rate_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Iznosi
    gross_amount         = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name=_('Bruto'))
    # HR porezni engine
    contributions_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name=_('Doprinosi iz'))
    tax_base             = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name=_('Porezna osnovica'))
    tax_amount           = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name=_('Porez + prirez'))
    net_amount           = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name=_('Neto'))

    # Isplata
    employee_iban    = models.CharField(max_length=34, blank=True,
                                         verbose_name=_('IBAN radnika'))
    is_paid          = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=100, blank=True)

    # DATEV export flag (DE kompanije)
    datev_exported   = models.BooleanField(default=False)

    # ArbZG/ZOR upozorenja iz perioda
    compliance_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('payroll_run', 'user')
        ordering = ['user__last_name', 'user__first_name']
        verbose_name = _('Obračunski listić')
        verbose_name_plural = _('Obračunski listići')

    def __str__(self):
        return (f"{self.user.get_full_name() or self.user.username} — "
                f"{self.payroll_run}")

    @property
    def employee_name(self):
        return self.user.get_full_name() or self.user.username
