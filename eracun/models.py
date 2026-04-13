from core.fields import FernetEncryptedCharField
"""e-Račun models — multi-tenant e-invoice gateway."""
from django.db import models
from core.managers import CompanyManager
import uuid


class ERacunConfig(models.Model):
    """Per-company e-Račun configuration."""
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='eracun_config'
    )
    is_active = models.BooleanField(default=False, verbose_name='e-Račun aktivan')

    # FINA certifikat — pohranjen IZVAN web roota u /etc/limit-connect/certs/
    # SIGURNOST: FileField je uklonjen (bio je web-dostupan). Koristiti cert_path.
    cert_path = models.CharField(
        max_length=500, blank=True,
        verbose_name='Putanja certifikata',
        help_text='Apsolutna putanja: /etc/limit-connect/certs/firma.p12'
    )
    # NAPOMENA: lozinka se čita iz /etc/limit-connect/certs/.cert_password, ne iz baze
    cert_password_deprecated = models.CharField(
        max_length=100, blank=True,
        verbose_name='[DEPRECATED] Lozinka — koristiti .cert_password fajl',
        help_text='Ne koristiti. Ostaje radi migracije podataka.'
    )
    cert_oib = models.CharField(max_length=11, blank=True, verbose_name='OIB iz certifikata')
    cert_valid_until = models.DateField(null=True, blank=True, verbose_name='Certifikat vrijedi do')

    # Poslovni prostor
    oznaka_prostora = models.CharField(max_length=20, default='P1', verbose_name='Oznaka posl. prostora')
    oznaka_uredjaja = models.CharField(max_length=20, default='1', verbose_name='Oznaka naplatnog uredjaja')

    # Postavke
    use_test_env = models.BooleanField(default=True, verbose_name='Testno okruzenje (CIS test)')
    auto_send = models.BooleanField(default=False, verbose_name='Automatski salji pri kreiranju')
    archive_days = models.IntegerField(default=4015, verbose_name='Cuvaj arhivu (dana)', help_text='Zakonski min 11 godina = 4015 dana')

    # API pristup za vanjske klijente
    api_key = FernetEncryptedCharField(blank=True, unique=True, verbose_name='API kljuc')
    api_enabled = models.BooleanField(default=False, verbose_name='API pristup aktivan')
    api_rate_limit = models.IntegerField(default=100, verbose_name='Max zahtjeva/sat')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'e-Racun konfiguracija'
        verbose_name_plural = 'e-Racun konfiguracije'

    def __str__(self):
        return f'e-Racun: {self.company.name}'

    def save(self, **kwargs):
        if not self.api_key:
            import secrets
            self.api_key = secrets.token_urlsafe(48)
        super().save(**kwargs)


class ERacun(models.Model):
    """Individual e-invoice record with full audit trail."""
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('validating', 'Validacija'),
        ('valid', 'Validan'),
        ('invalid', 'Nevalidan'),
        ('signing', 'Potpisivanje'),
        ('sending', 'Slanje'),
        ('sent', 'Poslan'),
        ('accepted', 'Prihvacen'),
        ('rejected', 'Odbijen'),
        ('error', 'Greska'),
        ('archived', 'Arhiviran'),
    ]

    DOC_TYPES = [
        ('380', 'Racun (Commercial Invoice)'),
        ('381', 'Odobrenje (Credit Note)'),
        ('383', 'Terecenje (Debit Note)'),
        ('386', 'Predracun (Prepayment Invoice)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='eracuni')

    # Veza s LIMIT Connect fakturom (opcionalno - moze doci i preko API-ja)
    invoice = models.OneToOneField(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='eracun'
    )

    # Veza s POS bonom (R1 -> auto e-Racun)
    source_receipt = models.ForeignKey(
        'pos.POSReceipt', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='eracuni',
        verbose_name='POS bon (izvor)',
        help_text='Ako je e-Racun kreiran iz POS R1 bona',
    )

    # Dokument
    doc_type = models.CharField(max_length=3, choices=DOC_TYPES, default='380')
    invoice_number = models.CharField(max_length=50, verbose_name='Broj racuna')
    issue_date = models.DateField(verbose_name='Datum izdavanja')
    delivery_date = models.DateField(null=True, blank=True, verbose_name='Datum isporuke')
    due_date = models.DateField(null=True, blank=True, verbose_name='Rok placanja')
    currency = models.CharField(max_length=3, default='EUR')

    # Izdavatelj
    issuer_name = models.CharField(max_length=200)
    issuer_oib = models.CharField(max_length=11)
    issuer_address = models.CharField(max_length=300, blank=True)
    issuer_city = models.CharField(max_length=100, blank=True)
    issuer_postal = models.CharField(max_length=20, blank=True)
    issuer_country = models.CharField(max_length=2, default='HR')
    issuer_iban = models.CharField(max_length=34, blank=True)
    issuer_swift = models.CharField(max_length=11, blank=True)

    # Primatelj
    recipient_name = models.CharField(max_length=200)
    recipient_oib = models.CharField(max_length=20)  # moze biti i VAT ID za EU
    recipient_address = models.CharField(max_length=300, blank=True)
    recipient_city = models.CharField(max_length=100, blank=True)
    recipient_postal = models.CharField(max_length=20, blank=True)
    recipient_country = models.CharField(max_length=2, default='HR')

    # Iznosi
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Placanje
    payment_means_code = models.CharField(max_length=3, default='30', help_text='30=transfer, 48=card, 10=cash')
    payment_reference = models.CharField(max_length=50, blank=True, verbose_name='Poziv na broj')
    payment_model = models.CharField(max_length=4, blank=True, default='HR00', verbose_name='Model placanja')
    note = models.TextField(blank=True)

    # Fiskalizacija
    zki = models.CharField(max_length=64, blank=True, verbose_name='ZKI')
    jir = models.CharField(max_length=64, blank=True, verbose_name='JIR')

    # Status i rezultat
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=20, blank=True)
    fina_uuid = models.CharField(max_length=64, blank=True, verbose_name='FINA UUID')

    # Anomaly detection
    anomaly_score = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(max_length=10, blank=True)  # low/medium/high

    # XML arhiva
    xml_request = models.TextField(blank=True, verbose_name='XML zahtjev')
    xml_response = models.TextField(blank=True, verbose_name='XML odgovor')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    objects = CompanyManager()

    class Meta:
        verbose_name = 'e-Racun'
        verbose_name_plural = 'e-Racuni'
        ordering = ['-created_at']
        # B-22: Sprječava duplikat broja računa unutar iste tvrtke
        unique_together = [('company', 'invoice_number')]
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['issuer_oib']),
            models.Index(fields=['recipient_oib']),
        ]

    def __str__(self):
        return f'{self.invoice_number} -> {self.recipient_name} ({self.get_status_display()})'


class ERacunItem(models.Model):
    """Line item on an e-Racun - EN 16931 compliant."""
    UNIT_CODES = [
        ('EA', 'Komad (EA)'),
        ('HUR', 'Sat (HUR)'),
        ('KGM', 'Kilogram (KGM)'),
        ('MTR', 'Metar (MTR)'),
        ('LTR', 'Litra (LTR)'),
        ('MTK', 'Kvadratni metar (MTK)'),
        ('DAY', 'Dan (DAY)'),
        ('MON', 'Mjesec (MON)'),
        ('SET', 'Set (SET)'),
        ('XPK', 'Pakiranje (XPK)'),
    ]

    TAX_CATEGORY_CODES = [
        ('S', 'Standardna stopa'),
        ('Z', 'Nulta stopa'),
        ('E', 'Oslobodjeno'),
        ('AE', 'Obrnuto oporezivanje (Reverse charge)'),
        ('K', 'Intra-community'),
        ('G', 'Izvoz (neoporezivo)'),
        ('O', 'Izvan PDV sustava'),
    ]

    eracun = models.ForeignKey(ERacun, on_delete=models.CASCADE, related_name='items')
    line_number = models.IntegerField(default=1)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit_code = models.CharField(max_length=5, choices=UNIT_CODES, default='EA')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_category = models.CharField(max_length=3, choices=TAX_CATEGORY_CODES, default='S')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25)

    # NKD / klasifikacija
    classification_code = models.CharField(max_length=20, blank=True, verbose_name='KPD/NKD sifra')

    class Meta:
        ordering = ['line_number']

    def __str__(self):
        return f'#{self.line_number}: {self.description}'


class ERacunTaxSummary(models.Model):
    """Tax breakdown per category/rate - EN 16931 BG-23."""
    eracun = models.ForeignKey(ERacun, on_delete=models.CASCADE, related_name='tax_summaries')
    tax_category = models.CharField(max_length=3)  # S, Z, E, AE, K
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ['eracun', 'tax_category', 'tax_rate']


class ERacunLog(models.Model):
    """Audit trail for every e-Racun action."""
    eracun = models.ForeignKey(ERacun, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=30)
    status = models.CharField(max_length=15)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action}: {self.message[:50]}'

class SukladnostTestRun(models.Model):
    """Zapis svakog pokretanja testa sukladnosti za Poreznu upravu."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='sukladnost_runs',
    )
    run_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Rezultati po scenariju
    ts01_cert = models.BooleanField(null=True, verbose_name='TS-01: Certifikat')
    ts02_ubl = models.BooleanField(null=True, verbose_name='TS-02: UBL generacija')
    ts03_validate = models.BooleanField(null=True, verbose_name='TS-03: XSD validacija')
    ts04_fiscal = models.BooleanField(null=True, verbose_name='TS-04: Fiskalizacija')
    ts05_inbox = models.BooleanField(null=True, verbose_name='TS-05: Inbox primanje')

    total_pass = models.PositiveIntegerField(default=0)
    total_fail = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Test sukladnosti'
        verbose_name_plural = 'Testovi sukladnosti'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.company.name} — {self.started_at:%d.%m.%Y %H:%M} ({self.total_pass}/5)'

    @property
    def score_pct(self):
        return int(self.total_pass / 5 * 100) if self.total_pass else 0

    @property
    def all_pass(self):
        return self.total_pass == 5
