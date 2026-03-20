from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.managers import CompanyManager

class Asset(models.Model):
    CATEGORY_CHOICES = [
        ('vehicle', _('Vozilo')), ('equipment', _('Oprema')), ('it', _('IT oprema')),
        ('pos_device', _('POS uredjaj')), ('cold_chain', _('Hladnjaca/Termobox')),
        ('furniture', _('Namjestaj')), ('tool', _('Alat')), ('other', _('Ostalo')),
    ]
    STATUS_CHOICES = [
        ('active', _('Aktivno')), ('maintenance', _('Na servisu')),
        ('retired', _('Otpisano')), ('sold', _('Prodano')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True)
    objects = CompanyManager()
    name = models.CharField(max_length=255)
    asset_code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='equipment')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    make = models.CharField(max_length=100, blank=True, default='')
    model_name = models.CharField(max_length=100, blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='')
    photo = models.ImageField(upload_to='assets/', null=True, blank=True)
    registration_plate = models.CharField(max_length=20, blank=True, default='')
    vin = models.CharField(max_length=17, blank=True, default='')
    mileage = models.PositiveIntegerField(default=0)
    fuel_type = models.CharField(max_length=20, blank=True, default='')
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    warranty_until = models.DateField(null=True, blank=True)
    insurance_until = models.DateField(null=True, blank=True)
    insurance_policy = models.CharField(max_length=50, blank=True, default='')
    registration_until = models.DateField(null=True, blank=True)
    leasing_until = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_assets')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    depreciation_method = models.CharField(max_length=20, choices=[('linear', 'Linearna'), ('declining', 'Degresivna')], default='linear')
    useful_life_months = models.PositiveIntegerField(default=60)
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_depreciation_date = models.DateField(null=True, blank=True)
    accumulated_depreciation = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Imovina'
        verbose_name_plural = 'Imovina'
        ordering = ['name']
    def __str__(self):
        return f"{self.asset_code} - {self.name}"

    def generate_asset_code(self):
        prefix = self.category[:3].upper() if self.category else 'AST'
        last = Asset.objects.filter(asset_code__startswith=prefix).order_by('-asset_code').first()
        seq = 1
        if last:
            try: seq = int(last.asset_code.split('-')[-1]) + 1
            except Exception: pass
        return f'{prefix}-{seq:04d}'


class MaintenanceSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('weekly', _('Tjedno')), ('monthly', _('Mjesecno')),
        ('quarterly', _('Kvartalno')), ('semi_annual', _('Polugodisnje')),
        ('annual', _('Godisnje')), ('mileage', _('Po kilometrazi')),
        ('once', _('Jednokratno')),
    ]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='schedules')
    task_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    next_due = models.DateField()
    mileage_interval = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_provider = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    notify_days_before = models.PositiveIntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_due']

    def __str__(self):
        return f"{self.task_name} -> {self.asset.name}"

    @property
    def is_overdue(self):
        return self.next_due < timezone.now().date()

    def advance_schedule(self):
        from datetime import timedelta
        freq_map = {
            'weekly': timedelta(weeks=1), 'monthly': timedelta(days=30),
            'quarterly': timedelta(days=91), 'semi_annual': timedelta(days=182),
            'annual': timedelta(days=365),
        }
        delta = freq_map.get(self.frequency)
        if delta:
            self.next_due = timezone.now().date() + delta
            self.save(update_fields=['next_due'])


class MaintenanceLog(models.Model):
    TYPE_CHOICES = [
        ('preventive', _('Preventivno')), ('corrective', _('Korektivno')),
        ('inspection', _('Inspekcija')), ('calibration', _('Kalibracija')),
        ('repair', _('Popravak')),
    ]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='logs')
    schedule = models.ForeignKey(MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    maintenance_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='preventive')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    date_performed = models.DateField(default=timezone.now)
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parts_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mileage_at_service = models.PositiveIntegerField(default=0)
    service_provider = models.CharField(max_length=200, blank=True, default='')
    invoice_number = models.CharField(max_length=50, blank=True, default='')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_performed')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_logged')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_performed']

    def save(self, *args, **kwargs):
        self.total_cost = self.labor_cost + self.parts_cost
        super().save(*args, **kwargs)
        if self.mileage_at_service and self.mileage_at_service > self.asset.mileage:
            self.asset.mileage = self.mileage_at_service
            self.asset.save(update_fields=['mileage'])
        if self.schedule:
            self.schedule.advance_schedule()


class DepreciationLog(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='depreciation_logs')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='depreciation_logs')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    journal_entry_number = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['asset', 'year', 'month']]
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.asset.asset_code} {self.year}-{self.month:02d} {self.amount}"
