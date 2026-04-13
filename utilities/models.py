"""
utilities/models.py — Režije i komunalije: ugovori, očitanja, računi.
Potpuni lanac: Ugovor → Očitanje → Račun → Knjiženje → Anomaly alert.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class UtilityContract(models.Model):
    """Ugovor s dobavljačem režija (HEP, vodovod, INA, HT, najam)."""
    TYPE_CHOICES = [
        ('electricity', _('Električna energija')),
        ('gas',         _('Plin')),
        ('water',       _('Vodoopskrba')),
        ('heating',     _('Grijanje / Toplana')),
        ('telecom',     _('Telekomunikacije')),
        ('internet',    _('Internet')),
        ('rent',        _('Najam prostora')),
        ('waste',       _('Odvoz otpada')),
        ('insurance',   _('Osiguranje')),
        ('other',       _('Ostalo')),
    ]
    KONTO_MAP = {
        'electricity': ('4200', 'Trošak električne energije'),
        'gas':         ('4210', 'Trošak plina'),
        'water':       ('4220', 'Trošak vode'),
        'heating':     ('4230', 'Trošak grijanja'),
        'telecom':     ('4300', 'Trošak telekomunikacija'),
        'internet':    ('4310', 'Trošak interneta'),
        'rent':        ('4060', 'Trošak najma'),
        'waste':       ('4240', 'Trošak odvoza otpada'),
        'insurance':   ('4250', 'Trošak osiguranja'),
        'other':       ('4900', 'Ostali troškovi'),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='utility_contracts')
    objects = CompanyManager()

    utility_type = models.CharField(max_length=15, choices=TYPE_CHOICES, verbose_name=_('Vrsta'))
    provider_name = models.CharField(max_length=200, verbose_name=_('Dobavljač'))
    contract_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj ugovora'))

    # Identifikatori mjesta
    meter_id = models.CharField(max_length=100, blank=True,
                                 verbose_name=_('Broj brojila / EAN / Mjerno mjesto'))
    location = models.CharField(max_length=200, blank=True, verbose_name=_('Lokacija / Adresa'))

    # Ugovorni uvjeti
    start_date = models.DateField(verbose_name=_('Početak ugovora'))
    end_date = models.DateField(null=True, blank=True, verbose_name=_('Kraj ugovora'))
    monthly_fixed_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                             verbose_name=_('Fiksni mjesečni iznos (EUR)'))
    unit_price_eur = models.DecimalField(max_digits=10, decimal_places=4, default=0,
                                          verbose_name=_('Cijena po jedinici (EUR)'))
    unit_name = models.CharField(max_length=20, default='kWh', verbose_name=_('Jedinica'))

    # AI matching
    archiva_keywords = models.CharField(max_length=300, blank=True,
        verbose_name=_('Ključne riječi za Arhiva AI'),
        help_text=_('Npr: HEP, elektra, EAN-12345 — za auto-prepoznavanje računa'))

    # Konto
    konto_code = models.CharField(max_length=10, blank=True, verbose_name=_('Konto rashoda'))

    # Supplier partner link
    supplier = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='utility_contracts')

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['utility_type', 'provider_name']
        verbose_name = _('Ugovor režija')
        verbose_name_plural = _('Ugovori režija')

    def __str__(self):
        return f"{self.get_utility_type_display()} — {self.provider_name}"

    def save(self, *args, **kwargs):
        if not self.konto_code:
            self.konto_code = self.KONTO_MAP.get(self.utility_type, ('4900', ''))[0]
        super().save(*args, **kwargs)

    @property
    def is_expiring_soon(self):
        """True if contract expires within 60 days."""
        if not self.end_date:
            return False
        from django.utils import timezone
        return (self.end_date - timezone.now().date()).days <= 60

    @property
    def days_until_expiry(self):
        if not self.end_date:
            return None
        from django.utils import timezone
        return (self.end_date - timezone.now().date()).days


class MeterReading(models.Model):
    """Očitanje brojila — ručno, HES ili foto AI."""
    SOURCE_CHOICES = [
        ('manual',  _('Ručni unos')),
        ('hes',     _('HES (daljinsko)')),
        ('photo',   _('Foto (AI OCR)')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(UtilityContract, on_delete=models.CASCADE,
                                  related_name='readings')
    date = models.DateField(verbose_name=_('Datum očitanja'))
    value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Stanje brojila'))
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')

    # AI OCR
    photo = models.ImageField(upload_to='utilities/readings/%Y/', blank=True,
                               verbose_name=_('Foto brojila'))
    photo_ai_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          verbose_name=_('AI OCR vrijednost'))
    photo_ai_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True,
                                               verbose_name=_('AI confidence (0-1)'))

    # Computed
    consumption = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_('Potrošnja (auto)'),
                                       help_text=_('Razlika od prethodnog očitanja'))

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = _('Očitanje brojila')
        verbose_name_plural = _('Očitanja brojila')

    def __str__(self):
        return f"{self.contract} — {self.date}: {self.value}"

    def save(self, *args, **kwargs):
        # Auto-calculate consumption from previous reading
        prev = MeterReading.objects.filter(
            contract=self.contract, date__lt=self.date
        ).order_by('-date').first()
        if prev:
            self.consumption = max(Decimal('0'), self.value - prev.value)
        super().save(*args, **kwargs)


class UtilityBill(models.Model):
    """Račun za režije — period, potrošnja, iznosi, PDV."""
    STATUS_CHOICES = [
        ('pending',   _('Na čekanju')),
        ('verified',  _('Verificiran')),
        ('booked',    _('Proknjižen')),
        ('paid',      _('Plaćen')),
        ('disputed',  _('Osporavan')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(UtilityContract, on_delete=models.CASCADE,
                                  related_name='bills')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='utility_bills')
    objects = CompanyManager()

    # Period
    period_from = models.DateField(verbose_name=_('Period od'))
    period_to = models.DateField(verbose_name=_('Period do'))
    issue_date = models.DateField(verbose_name=_('Datum računa'))
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Rok plaćanja'))
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj računa'))

    # Iznosi
    consumption_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name=_('Potrošnja (kWh/m³/...)'))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    verbose_name=_('Iznos bez PDV'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      verbose_name=_('PDV'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                 verbose_name=_('Ukupno'))

    # Anomaly detection
    avg_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_('Prosjek 12 mj (EUR)'))
    deviation_pct = models.DecimalField(max_digits=6, decimal_places=1, default=0,
                                         verbose_name=_('Odstupanje od prosjeka (%)'))
    is_anomaly = models.BooleanField(default=False, verbose_name=_('Anomalija'))
    anomaly_note = models.CharField(max_length=300, blank=True)

    # Arhiva link
    archiva_document = models.ForeignKey('documents.ArhivaEntry', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='utility_bills')
    linked_invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='utility_bills')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']
        verbose_name = _('Račun režija')
        verbose_name_plural = _('Računi režija')

    def __str__(self):
        return f"{self.contract.get_utility_type_display()} {self.period_from}–{self.period_to}: {self.total} EUR"

    def detect_anomaly(self):
        """Check if bill deviates >20% from 12-month average."""
        from django.db.models import Avg
        avg = UtilityBill.objects.filter(
            contract=self.contract,
            status__in=('verified', 'booked', 'paid'),
        ).exclude(pk=self.pk).aggregate(a=Avg('total'))['a']

        if avg and avg > 0:
            self.avg_monthly = avg
            self.deviation_pct = ((self.total - avg) / avg * 100).quantize(Decimal('0.1'))
            self.is_anomaly = abs(self.deviation_pct) > 20
            if self.is_anomaly:
                direction = 'viši' if self.deviation_pct > 0 else 'niži'
                self.anomaly_note = f'{abs(self.deviation_pct)}% {direction} od prosjeka ({avg:.2f} EUR)'
        self.save(update_fields=['avg_monthly', 'deviation_pct', 'is_anomaly', 'anomaly_note'])
        return self.is_anomaly

    def book(self, user=None):
        """Book utility bill to konto: D:expense+D:1400 / P:2200."""
        from konto.models import KontoAccount, JournalEntry, LedgerLine
        if self.status == 'booked':
            return None

        company = self.company
        contract = self.contract
        konto_code = contract.konto_code or '4900'
        konto_name = contract.KONTO_MAP.get(contract.utility_type, ('4900', 'Ostali troškovi'))[1]

        from datetime import date as _date
        year = _date.today().year
        prefix = f'REZ-{year}-'
        from konto.models import JournalEntry as JE
        last = JE.objects.filter(company=company, entry_number__startswith=prefix).order_by('-entry_number').first()
        seq = 1
        if last:
            try:
                seq = int(last.entry_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                pass

        je = JournalEntry.objects.create(
            company=company,
            entry_number=f'{prefix}{seq:04d}',
            date=self.issue_date,
            description=f'{contract.get_utility_type_display()} — {contract.provider_name} ({self.period_from}–{self.period_to})',
            source_type='manual',
            is_posted=True,
            created_by=user,
        )

        # D: Expense
        exp_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=konto_code,
            defaults={'name': konto_name, 'account_type': 'expense'})
        LedgerLine.objects.create(
            journal_entry=je, account=exp_acct,
            side='debit', amount=self.subtotal,
            description=f'{contract.provider_name} {self.invoice_number}')

        # D: Pretporez
        if self.tax_amount > 0:
            vat_acct, _ = KontoAccount.objects.get_or_create(
                company=company, code='1400',
                defaults={'name': 'Pretporez (ulazni PDV)', 'account_type': 'asset'})
            LedgerLine.objects.create(
                journal_entry=je, account=vat_acct,
                side='debit', amount=self.tax_amount,
                description=f'Pretporez {contract.provider_name}')

        # P: Dobavljači
        pay_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code='2200',
            defaults={'name': 'Obveze prema dobavljačima', 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=pay_acct,
            side='credit', amount=self.total,
            description=f'Dobavljač {contract.provider_name}')

        self.status = 'booked'
        self.save(update_fields=['status'])
        return je
