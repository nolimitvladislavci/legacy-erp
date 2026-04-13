from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class BusinessLocation(models.Model):
    LOCATION_TYPE = [
        ('P', 'Poslovni prostor (fizički)'),
        ('K', 'Pokretna naplatna naprava'),
        ('O', 'Online / Web'),
    ]
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    location_code = models.CharField(max_length=20, verbose_name=_('Oznaka prostora (PP)'))
    location_type = models.CharField(max_length=1, choices=LOCATION_TYPE, default='P')
    address = models.CharField(max_length=255, verbose_name=_('Adresa'))
    city = models.CharField(max_length=100, verbose_name=_('Grad'))
    oib = models.CharField(max_length=11, default='37590751921', verbose_name=_('OIB tvrtke'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivno'))
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='business_locations', verbose_name=_('Tvrtka'),
        null=True, blank=True,
    )
    branch = models.ForeignKey(
        'companies.CompanyBranch', on_delete=models.SET_NULL,
        related_name='business_locations', verbose_name=_('Poslovnica'),
        null=True, blank=True,
    )
    iban = models.CharField(max_length=34, blank=True, verbose_name=_('IBAN za uplatu'))
    notes = models.TextField(blank=True, verbose_name=_('Napomena'))

    class Meta:
        verbose_name = _('Poslovni prostor')
        verbose_name_plural = _('Poslovni prostori')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.location_code})"

class FiscalOperator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fiscal_operator', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name=_('Ime i prezime'))
    oib = models.CharField(max_length=11, verbose_name=_('OIB operatera'))
    default_location = models.ForeignKey(BusinessLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Zadani poslovni prostor'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Operater')
        verbose_name_plural = _('Operateri')

    def __str__(self):
        return f"{self.name} (OIB: {self.oib})"

class TaxGroup(models.Model):
    RATE_CHOICES = [
        ('0',  '0% - Oslobođeno PDV-a'),
        ('5',  '5% - Snižena stopa (knjige, hrana)'),
        ('13', '13% - Snižena stopa (ugostiteljstvo)'),
        ('25', '25% - Standardna stopa'),
    ]
    code = models.CharField(max_length=5, unique=True, verbose_name=_('Šifra grupe'))
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    rate = models.CharField(max_length=3, choices=RATE_CHOICES, verbose_name=_('Stopa PDV-a'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('Opis'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('PDV grupa')
        verbose_name_plural = _('PDV grupe')
        ordering = ['rate']

    def __str__(self):
        return f"{self.code} – {self.name} ({self.rate}%)"

class FiscalConfig(models.Model):
    company_name = models.CharField(max_length=255, default='Tvoja Tvrtka d.o.o.', verbose_name='Naziv tvrtke')
    address = models.CharField(max_length=255, default='Ulica 1', verbose_name='Adresa')
    city = models.CharField(max_length=100, default='Zagreb', verbose_name='Grad')
    oib = models.CharField(max_length=11, default='00000000000', verbose_name='OIB')
    email_from = models.EmailField(max_length=255, blank=True, default='', verbose_name='Službeni Email')
    cert_path = models.CharField(max_length=255, blank=True, null=True, default='/var/www/fina-connect/certs/fina_cert.p12')
    cert_file = models.FileField(upload_to='certs/', null=True, blank=True)
    cert_password = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name=_('Lozinka certifikata'),
        help_text=_('Lozinka .p12 datoteke (ostavite prazno ako se koristi .cert_password datoteka)')
    )
    use_production = models.BooleanField(default=False, verbose_name=_('Produkcijski CIS'))
    invoice_prefix_hr = models.CharField(max_length=10, default='KNJ')
    next_invoice_number = models.IntegerField(default=1)
    default_iban = models.CharField(max_length=34, blank=True, default='', verbose_name='Zadani IBAN')

    class Meta:
        verbose_name = _('Konfiguracija fiskalizacije')
        verbose_name_plural = _('Konfiguracija fiskalizacije')

    def __str__(self):
        return f"Fiskalizacija – {self.company_name}"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


COUNTRY_CHOICES = [
    ('HR', 'Hrvatska'),
    ('DE', 'Deutschland'),
]

LANGUAGE_CHOICES = [
    ('hr', 'Hrvatski'),
    ('de', 'Deutsch'),
    ('en', 'English'),
]


class InvoiceProfile(models.Model):
    # Identity
    name = models.CharField(max_length=200, verbose_name=_('Naziv profila'))
    is_default = models.BooleanField(default=False, verbose_name=_('Zadani profil'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivan'))

    # Issuer info
    company_name = models.CharField(max_length=255, verbose_name=_('Naziv tvrtke'))
    address = models.CharField(max_length=255, blank=True, verbose_name=_('Adresa'))
    city = models.CharField(max_length=100, blank=True, verbose_name=_('Grad'))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_('Poštanski broj'))
    country = models.CharField(max_length=5, choices=COUNTRY_CHOICES, default='HR', verbose_name=_('Zemlja'))
    oib = models.CharField(max_length=20, blank=True, verbose_name=_('OIB'))
    vat_id = models.CharField(max_length=20, blank=True, verbose_name=_('USt-IdNr'))
    tax_number = models.CharField(max_length=20, blank=True, verbose_name=_('Steuernummer'))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    email = models.EmailField(blank=True, verbose_name=_('Email'))
    website = models.URLField(blank=True, verbose_name=_('Web'))
    logo = models.ImageField(upload_to='profile_logos/', null=True, blank=True, verbose_name=_('Logo'))

    # Localization
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='hr', verbose_name=_('Jezik'))
    currency = models.CharField(max_length=3, default='EUR', verbose_name=_('Valuta'))
    bilingual = models.BooleanField(default=False, verbose_name=_('Dvojezični račun'))
    secondary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='', blank=True, verbose_name=_('Drugi jezik'))
    default_tax_rate = models.ForeignKey(
        'companies.TaxRate', null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name=_('Zadana porezna stopa'))

    # Banking
    iban = models.CharField(max_length=34, blank=True, verbose_name=_('IBAN'))
    swift = models.CharField(max_length=11, blank=True, verbose_name=_('SWIFT/BIC'))
    bank_name = models.CharField(max_length=200, blank=True, verbose_name=_('Naziv banke'))

    # Numbering
    invoice_prefix = models.CharField(max_length=20, default='KNJ', verbose_name=_('Prefiks računa'))
    next_invoice_number = models.IntegerField(default=1, verbose_name=_('Sljedeći broj'))

    # Fiscal cert
    cert_file = models.FileField(upload_to='certs/', null=True, blank=True, verbose_name=_('Certifikat'))
    cert_path = models.CharField(max_length=255, blank=True, verbose_name=_('Putanja certifikata'))
    cert_password = models.CharField(max_length=255, blank=True, verbose_name=_('Lozinka certifikata'))
    use_production = models.BooleanField(default=False, verbose_name=_('Produkcijski CIS'))

    # Defaults
    footer_note = models.TextField(blank=True, verbose_name=_('Napomena u podnožju'))
    default_due_days = models.PositiveIntegerField(default=15, verbose_name=_('Zadani rok plaćanja (dana)'))
    default_payment_method = models.CharField(max_length=20, default='TRANSAKCIJSKI', verbose_name=_('Zadani način plaćanja'))

    # Optional FK
    company = models.ForeignKey(
        'companies.Company', null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name=_('Tvrtka'))
    branch = models.ForeignKey(
        'companies.CompanyBranch', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='invoice_profiles', verbose_name=_('Poslovnica'),
    )
    business_location = models.ForeignKey(
        'invoicing.BusinessLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='invoice_profiles', verbose_name=_('Poslovni prostor (PP)'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Profil fakturiranja')
        verbose_name_plural = _('Profili fakturiranja')
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            InvoiceProfile.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        profile = cls.objects.filter(is_default=True, is_active=True).first()
        if not profile:
            profile = cls.objects.filter(is_active=True).first()
        return profile

    def get_next_number(self, doctype='R'):
        import datetime
        year = datetime.datetime.now().year
        # Doctype-aware prefix mapping
        dtype_prefix = {
            'R': 'RE',    # Rechnung / Račun
            'PO': 'AN',   # Angebot / Ponuda
            'P': 'KV',    # Kostenvoranschlag / Predračun
            'A': 'AR',    # Abschlagsrechnung / Avansni
            'S': 'ST',    # Storno
            'GS': 'GS',   # Gutschrift
        }
        dp = dtype_prefix.get(doctype, 'RE')
        prefix = f"{self.invoice_prefix}-{dp}"
        # Count existing docs of this type for this year
        from invoicing.models import Invoice
        pattern = f"{prefix}-{year}-"
        existing = Invoice.objects.filter(number__startswith=pattern).count()
        num = existing + 1
        number = f"{prefix}-{year}-{num:04d}"
        while Invoice.objects.filter(number=number).exists():
            num += 1
            number = f"{prefix}-{year}-{num:04d}"
        return number


# ── FISKALNI CERTIFIKAT ───────────────────────────────────────────────────────

class FiscalCertificate(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='fiscal_certificates',
    )
    location = models.ForeignKey(
        BusinessLocation, on_delete=models.CASCADE,
        null=True, blank=True, related_name='fiscal_certificates',
    )
    oib           = models.CharField(max_length=11, blank=True)
    cert_name     = models.CharField(max_length=200, blank=True)
    cert_file     = models.FileField(upload_to='fiscal/certs/')
    cert_password = models.CharField(max_length=200, blank=True)
    is_valid      = models.BooleanField(default=False)
    valid_from    = models.DateTimeField(null=True, blank=True)
    valid_until   = models.DateTimeField(null=True, blank=True)
    cert_subject  = models.TextField(blank=True)
    is_active     = models.BooleanField(default=True)
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    last_test     = models.DateTimeField(null=True, blank=True)
    last_test_result = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Fiskalni certifikat'
        verbose_name_plural = 'Fiskalni certifikati'
        ordering            = ['-uploaded_at']

    def __str__(self):
        return '{} ({})'.format(self.cert_name or self.oib or 'Certifikat', self.company_id)

    @property
    def is_expired(self):
        if not self.valid_until:
            return False
        from django.utils import timezone
        return self.valid_until <= timezone.now()

    @property
    def is_expiring_soon(self):
        if not self.valid_until:
            return False
        import datetime as dt

        from django.utils import timezone
        return (not self.is_expired and
                self.valid_until <= timezone.now() + dt.timedelta(days=30))

    @property
    def days_until_expiry(self):
        if not self.valid_until:
            return None
        from django.utils import timezone
        return (self.valid_until - timezone.now()).days


# ── FISKALNI LOG ──────────────────────────────────────────────────────────────

class FiscalLog(models.Model):
    ACTION_CHOICES = [
        ('sign',     'ZKI potpis'),
        ('send',     'Slanje na CIS'),
        ('response', 'Odgovor CIS-a'),
        ('retry',    'Ponovni pokusaj'),
        ('error',    'Greska'),
        ('manual',   'Rucna provjera'),
    ]
    STATUS_CHOICES = [
        ('success', 'Uspjeh'),
        ('error',   'Greska'),
        ('warning', 'Upozorenje'),
        ('info',    'Info'),
    ]

    invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.CASCADE, related_name='fiscal_logs',
    )
    action       = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='info')
    message      = models.TextField(blank=True)
    request_xml  = models.TextField(blank=True)
    response_xml = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    created_by   = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name        = 'Fiskalni log'
        verbose_name_plural = 'Fiskalni logovi'
        ordering            = ['-created_at']

    def __str__(self):
        ts = self.created_at.strftime('%d.%m.%Y %H:%M') if self.created_at else ''
        return '[{}] {} #{} {}'.format(self.status, self.action, self.invoice_id, ts)

    @classmethod
    def log(cls, invoice, action, status='info', message='',
            request_xml='', response_xml='', user=None):
        return cls.objects.create(
            invoice=invoice, action=action, status=status,
            message=message, request_xml=request_xml,
            response_xml=response_xml, created_by=user,
        )


# ── FISCAL BATCH ──────────────────────────────────────────────────────────────

class FiscalBatch(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Na cekanju'),
        ('processing', 'U tijeku'),
        ('completed',  'Zavrseno'),
        ('partial',    'Djelomicno uspjesno'),
        ('failed',     'Neuspjesno'),
    ]

    company    = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, related_name='fiscal_batches',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='fiscal_batches',
    )
    invoices = models.ManyToManyField(
        'invoicing.Invoice', related_name='fiscal_batches', blank=True,
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_count   = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count   = models.PositiveIntegerField(default=0)
    results_json  = models.JSONField(default=dict, blank=True)
    started_at    = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Batch fiskalizacija'
        verbose_name_plural = 'Batch fiskalizacije'
        ordering            = ['-created_at']

    def __str__(self):
        return 'Batch #{} {} ({}/{})'.format(
            self.pk, self.get_status_display(), self.success_count, self.total_count)

    @property
    def success_rate(self):
        return round(self.success_count / self.total_count * 100) if self.total_count else 0

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
