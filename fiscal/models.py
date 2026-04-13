from django.db import models

from core.managers import CompanyManager


class FiscalProvider(models.TextChoices):
    HR_FINA = 'hr_fina', 'Hrvatska - FINA CIS'
    DE_TSE = 'de_tse', 'Deutschland - KassenSichV/TSE'
    AT_RKSV = 'at_rksv', 'Österreich - RKSV'
    NONE = 'none', 'Bez fiskalizacije'


class FiscalConfiguration(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='fiscal_configs'
    )
    branch = models.ForeignKey(
        'companies.CompanyBranch', on_delete=models.CASCADE,
        null=True, blank=True
    )
    provider = models.CharField(
        max_length=20, choices=FiscalProvider.choices,
        default=FiscalProvider.NONE
    )
    is_active = models.BooleanField(default=False)
    is_test_mode = models.BooleanField(default=True, help_text='Koristi test okolinu')

    # HR FINA
    certificate_file = models.FileField(upload_to='fiscal/certs/', blank=True, help_text='.p12 certifikat od FINA')
    certificate_password = models.CharField(max_length=255, blank=True)
    oib = models.CharField(max_length=11, blank=True, help_text='OIB obveznika')
    business_premise_id = models.CharField(max_length=20, blank=True, verbose_name='Oznaka poslovnog prostora')
    device_id = models.CharField(max_length=20, blank=True, verbose_name='Oznaka naplatnog uredaja')

    # DE TSE (fiskaly)
    tse_api_key = models.CharField(max_length=255, blank=True, help_text='fiskaly API Key')
    tse_api_secret = models.CharField(max_length=255, blank=True, help_text='fiskaly API Secret')
    tse_tss_id = models.CharField(max_length=255, blank=True, help_text='TSS ID iz fiskaly dashboarda')
    tse_client_id = models.CharField(max_length=255, blank=True)

    # AT RKSV (fiskaly AT / PrimeSign / A-Trust)
    rksv_api_key = models.CharField(max_length=255, blank=True, help_text='RKSV signing API Key')
    rksv_api_secret = models.CharField(max_length=255, blank=True, help_text='RKSV signing API Secret')
    rksv_kassen_id = models.CharField(max_length=50, blank=True, help_text='Kassen-ID (FinanzOnline)')
    rksv_cert_serial = models.CharField(max_length=100, blank=True, help_text='Zertifikat-Seriennummer')
    rksv_aes_key = models.CharField(max_length=64, blank=True, help_text='AES-256 Schlüssel (hex) für Umsatzzähler')

    objects = CompanyManager()

    class Meta:
        verbose_name = 'Fiskalna konfiguracija'
        verbose_name_plural = 'Fiskalne konfiguracije'
        unique_together = ['company', 'branch']

    def __str__(self):
        branch_name = self.branch.name if self.branch else 'Svi'
        return f"{self.company} / {branch_name} - {self.get_provider_display()}"


class FiscalLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Uspjesno'),
        ('error', 'Greska'),
        ('pending', 'Na cekanju'),
        ('retry', 'Ponovni pokusaj'),
    ]
    config = models.ForeignKey(FiscalConfiguration, on_delete=models.CASCADE)
    receipt_type = models.CharField(max_length=50)
    receipt_id = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    zki = models.CharField(max_length=64, blank=True, verbose_name='ZKI')
    jir = models.CharField(max_length=40, blank=True, verbose_name='JIR')
    tse_signature = models.TextField(blank=True)
    tse_transaction_number = models.CharField(max_length=100, blank=True)
    tse_start_time = models.DateTimeField(null=True, blank=True)
    tse_end_time = models.DateTimeField(null=True, blank=True)
    request_xml = models.TextField(blank=True, help_text='Poslani zahtjev')
    response_xml = models.TextField(blank=True, help_text='Primljeni odgovor')
    error_message = models.TextField(blank=True)
    qr_code_data = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fiskalni log'
        verbose_name_plural = 'Fiskalni logovi'

    def __str__(self):
        return f"{self.receipt_type}#{self.receipt_id} - {self.status}"
