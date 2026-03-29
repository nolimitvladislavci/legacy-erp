"""
seasonal/models.py — Sezonski radnici

Arhitektura:
  SeasonalWorker   → radnik bez Django login pristupa (OIB obvezan)
  SeasonalContract → ugovor, 5 tipova po HR zakonu, HZMO tracking
  SeasonalPayment  → isplata s poreznim obračunom po tipu ugovora

Integracija:
  - payroll.hr_calculator → obračun za ugovor o radu
  - core.whatsapp → HZMO alarmi
  - core.managers.CompanyManager → multi-tenant izolacija
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class SeasonalWorker(models.Model):
    """Sezonski radnik — ne mora imati Django korisnički račun."""

    NATIONALITY_CHOICES = [
        ('HR', 'Hrvatska'),
        ('DE', 'Njemačka'),
        ('AT', 'Austrija'),
        ('BA', 'Bosna i Hercegovina'),
        ('RS', 'Srbija'),
        ('SI', 'Slovenija'),
        ('OTHER', 'Ostalo'),
    ]

    company     = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='seasonal_workers'
    )
    objects = CompanyManager()

    first_name    = models.CharField(max_length=100, verbose_name=_('Ime'))
    last_name     = models.CharField(max_length=100, verbose_name=_('Prezime'))
    oib           = models.CharField(max_length=11, verbose_name='OIB')
    nationality   = models.CharField(
        max_length=10, choices=NATIONALITY_CHOICES,
        default='HR', verbose_name=_('Državljanstvo')
    )
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_('Datum rođenja'))
    address       = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa'))
    phone         = models.CharField(max_length=30, blank=True, verbose_name=_('Mobitel'))
    email         = models.EmailField(blank=True, verbose_name=_('Email'))
    iban          = models.CharField(max_length=34, blank=True, verbose_name='IBAN')
    notes         = models.TextField(blank=True, verbose_name=_('Napomene'))
    is_active     = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Sezonski radnik')
        verbose_name_plural = _('Sezonski radnici')
        ordering            = ['last_name', 'first_name']
        unique_together     = [('company', 'oib')]

    def __str__(self):
        return f'{self.last_name} {self.first_name} ({self.oib})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def active_contract(self):
        return self.contracts.filter(
            status__in=['active', 'pending']
        ).order_by('-start_date').first()


class SeasonalContract(models.Model):
    """Ugovor za sezonskog radnika."""

    CONTRACT_TYPE_CHOICES = [
        ('djelo',      _('Ugovor o djelu (čl. 590 ZOO)')),
        ('privremeni', _('Privremeni i povremeni (ZOR čl. 10) — max 90 dana/god')),
        ('odredjeno',  _('Ugovor o radu na određeno (ZOR čl. 12)')),
        ('autorski',   _('Ugovor o autorskom djelu')),
        ('studentski', _('Studentski ugovor (preko servisa)')),
    ]
    STATUS_CHOICES = [
        ('pending',   _('Na čekanju')),
        ('active',    _('Aktivan')),
        ('completed', _('Završen')),
        ('cancelled', _('Otkazano')),
    ]
    PAYMENT_CYCLE_CHOICES = [
        ('daily',    _('Dnevna nadoknada')),
        ('weekly',   _('Tjedna isplata')),
        ('monthly',  _('Mjesečna plaća')),
        ('lump_sum', _('Jednokratno po završetku')),
    ]

    worker        = models.ForeignKey(
        SeasonalWorker, on_delete=models.CASCADE,
        related_name='contracts', verbose_name=_('Radnik')
    )
    company       = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='seasonal_contracts'
    )
    objects = CompanyManager()

    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_TYPE_CHOICES,
        verbose_name=_('Vrsta ugovora')
    )
    status        = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )
    start_date    = models.DateField(verbose_name=_('Datum početka'))
    end_date      = models.DateField(verbose_name=_('Datum završetka'))
    gross_amount  = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name=_('Bruto iznos (EUR)')
    )
    payment_cycle = models.CharField(
        max_length=15, choices=PAYMENT_CYCLE_CHOICES,
        default='lump_sum', verbose_name=_('Ciklus isplate')
    )
    position      = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Radno mjesto / opis posla')
    )

    # HZMO — M-1/M-2 (samo za ugovor o radu na određeno)
    hzmo_prijava_sent = models.BooleanField(default=False, verbose_name=_('M-1 prijava poslana'))
    hzmo_prijava_date = models.DateField(null=True, blank=True, verbose_name=_('Datum M-1'))
    hzmo_odjava_sent  = models.BooleanField(default=False, verbose_name=_('M-2 odjava poslana'))
    hzmo_odjava_date  = models.DateField(null=True, blank=True, verbose_name=_('Datum M-2'))

    contract_pdf  = models.FileField(
        upload_to='seasonal/contracts/', null=True, blank=True,
        verbose_name=_('Ugovor PDF')
    )
    signed_at     = models.DateTimeField(null=True, blank=True)
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )

    class Meta:
        verbose_name        = _('Sezonski ugovor')
        verbose_name_plural = _('Sezonski ugovori')
        ordering            = ['-start_date']

    def __str__(self):
        return (f'{self.worker.full_name} — '
                f'{self.get_contract_type_display()} '
                f'({self.start_date} → {self.end_date})')

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def days_worked_so_far(self):
        today = timezone.localdate()
        if today < self.start_date:
            return 0
        return (min(today, self.end_date) - self.start_date).days + 1

    @property
    def needs_hzmo_prijava(self):
        return self.contract_type == 'odredjeno' and not self.hzmo_prijava_sent

    @property
    def hzmo_prijava_deadline(self):
        from datetime import timedelta
        return self.start_date + timedelta(days=8)

    @property
    def hzmo_odjava_deadline(self):
        from datetime import timedelta
        return self.end_date + timedelta(days=8)

    def net_estimate(self):
        """Procjena neto iznosa — informativno."""
        try:
            from payroll.hr_calculator import izracunaj_placu
            result = izracunaj_placu(self.gross_amount)
            return result.get('neto', self.gross_amount * Decimal('0.70'))
        except Exception:
            if self.contract_type in ('djelo', 'privremeni', 'autorski'):
                return self.gross_amount * Decimal('0.80')  # 20% porez
            elif self.contract_type == 'studentski':
                return self.gross_amount
            return self.gross_amount * Decimal('0.70')


class SeasonalPayment(models.Model):
    """Isplata sezonskom radniku."""

    STATUS_CHOICES = [
        ('planned',  _('Planirana')),
        ('approved', _('Odobrena')),
        ('paid',     _('Isplaćena')),
    ]
    METHOD_CHOICES = [
        ('bank', _('Bankovni transfer')),
        ('cash', _('Gotovina')),
    ]

    contract      = models.ForeignKey(
        SeasonalContract, on_delete=models.CASCADE,
        related_name='payments', verbose_name=_('Ugovor')
    )
    company       = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='seasonal_payments'
    )
    objects = CompanyManager()

    payment_date   = models.DateField(verbose_name=_('Datum isplate'))
    gross_amount   = models.DecimalField(max_digits=10, decimal_places=2,
                      verbose_name=_('Bruto iznos'))
    tax_amount     = models.DecimalField(max_digits=10, decimal_places=2,
                      default=0, verbose_name=_('Porez'))
    net_amount     = models.DecimalField(max_digits=10, decimal_places=2,
                      default=0, verbose_name=_('Neto za isplatu'))
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='bank')
    status         = models.CharField(max_length=15, choices=STATUS_CHOICES, default='planned')

    joppd_generated = models.BooleanField(default=False)
    joppd_date      = models.DateField(null=True, blank=True)
    joppd_xml       = models.TextField(blank=True)

    reference     = models.CharField(max_length=100, blank=True)
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    approved_by   = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )

    class Meta:
        verbose_name        = _('Isplata sezonce')
        verbose_name_plural = _('Isplate sezonskim radnicima')
        ordering            = ['-payment_date']

    def __str__(self):
        return (f'{self.contract.worker.full_name} — '
                f'{self.gross_amount}€ ({self.payment_date})')

    def calculate_and_approve(self, approved_by=None):
        """Izračunaj porez i odobri isplatu."""
        ctype = self.contract.contract_type

        if ctype in ('djelo', 'privremeni', 'autorski'):
            self.tax_amount = (self.gross_amount * Decimal('0.20')).quantize(Decimal('0.01'))
            self.net_amount = self.gross_amount - self.tax_amount
        elif ctype == 'odredjeno':
            try:
                from payroll.hr_calculator import izracunaj_placu
                r = izracunaj_placu(self.gross_amount)
                self.tax_amount = r.get('porez', Decimal('0')) + r.get('prirez', Decimal('0'))
                self.net_amount = r.get('neto', self.gross_amount * Decimal('0.70'))
            except Exception:
                self.tax_amount = (self.gross_amount * Decimal('0.30')).quantize(Decimal('0.01'))
                self.net_amount = self.gross_amount - self.tax_amount
        else:
            # studentski — bez poreza do limita
            self.tax_amount = Decimal('0')
            self.net_amount = self.gross_amount

        self.status = 'approved'
        self.approved_by = approved_by
        self.save(update_fields=['tax_amount', 'net_amount', 'status', 'approved_by'])
        return self
