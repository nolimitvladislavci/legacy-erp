import secrets
from django.db import models
from core.managers import CompanyManager


def _token():
    return secrets.token_urlsafe(32)


class SynesisConfig(models.Model):
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='synesis_config', verbose_name='Tvrtka',
    )
    api_token = models.CharField(max_length=64, unique=True, default=_token, verbose_name='API Token')
    storage_db_path = models.CharField(
        max_length=500, blank=True,
        default=r'C:\Synesis\FIRMA\Storage.mdb',
        verbose_name='Putanja do Storage.mdb',
        help_text=r'Npr. C:\Synesis\KONJIK2025\Storage.mdb',
    )
    journal_db_path = models.CharField(
        max_length=500, blank=True,
        default=r'C:\Synesis\FIRMA\Journal.mdb',
        verbose_name='Putanja do Journal.mdb',
    )
    pos_db_path = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Putanja do SynesisPOS baze (kasa)',
        help_text=r'Npr. C:\Synesis\POS\SynesisPOS.mdb',
    )
    pos_db_password = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='SynesisPOS lozinka baze',
    )
    pos_name = models.CharField(max_length=100, blank=True, default='Kasa')
    last_sync_pos = models.DateTimeField(null=True, blank=True)
    pos_receipts_total = models.IntegerField(default=0)
    pos_revenue_today = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pos_revenue_week = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pos_revenue_month = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    last_sync_partners = models.DateTimeField(null=True, blank=True)
    last_sync_items = models.DateTimeField(null=True, blank=True)
    partners_total = models.IntegerField(default=0)
    items_total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Synesis konfiguracija'

    def __str__(self):
        return f'Synesis: {self.company.name}'

    def regenerate_token(self):
        self.api_token = _token()
        self.save(update_fields=['api_token'])
        return self.api_token


class SynesisLog(models.Model):
    TYPES = [('partners', 'Partneri'), ('items', 'Artikli'), ('invoices', 'Racuni')]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='synesis_logs')
    sync_type = models.CharField(max_length=20, choices=TYPES)
    records_received = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    error_detail = models.TextField(blank=True)
    duration_seconds = models.FloatField(default=0)
    synced_at = models.DateTimeField(auto_now_add=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-synced_at']

    def __str__(self):
        return f'{self.company.name} - {self.sync_type} - {self.synced_at:%d.%m.%Y %H:%M}'



class SynesisExportQueue(models.Model):
    """Red cekanja za podatke koji se salju iz ERP-a natrag u Synesis MDB."""
    TYPE_CHOICES = [('item', 'Artikl'), ('partner', 'Partner'), ('calculation', 'Kalkulacija'), ('pkv', 'PKV primka'), ('invoice', 'Faktura')]
    ACTION_CHOICES = [('update', 'Update'), ('insert', 'Insert')]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='synesis_exports',
    )
    export_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='update')
    synesis_id = models.CharField(max_length=50, blank=True, default='',
                                   help_text='Synesis ITEM_ID or PARTNER_ID')
    erp_object_id = models.CharField(max_length=50, blank=True, default='')
    payload = models.JSONField(default=dict, help_text='MDB fields to write')
    description = models.CharField(max_length=300, blank=True)

    is_exported = models.BooleanField(default=False)
    exported_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
    )
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Synesis export'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.export_type}/{self.action}: {self.description}"


class SynesisYearConfig(models.Model):
    """Konfiguracija putanja po godini za višegodišnji Synesis sync."""
    config = models.ForeignKey(
        SynesisConfig, on_delete=models.CASCADE,
        related_name='year_configs',
    )
    year = models.PositiveIntegerField(verbose_name='Godina')
    storage_db_path = models.CharField(
        max_length=500,
        verbose_name='Putanja do Storage.mdb',
    )
    journal_db_path = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Putanja do Journal.mdb',
    )
    last_sync_invoices = models.DateTimeField(null=True, blank=True)
    invoices_total = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('config', 'year')
        ordering = ['-year']
        verbose_name = 'Synesis godišnja konfiguracija'

    def __str__(self):
        return f'{self.config.company.name} {self.year}'
