from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _

from borg_ops.mixins import FSMMixin
from core.managers import CompanyManager


class WorkOrder(FSMMixin, models.Model):
    # GenericRelation: cascade delete CardActivity i StatusTimestamp kad se WorkOrder briše
    card_activities = GenericRelation('borg_ops.CardActivity', object_id_field='object_id', content_type_field='content_type')
    sla_timestamps  = GenericRelation('borg_ops.StatusTimestamp', object_id_field='object_id', content_type_field='content_type')

    STATUS_FIELD = 'status'
    TRANSITIONS = {
        'draft':       ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled', 'draft'],
        'completed':   ['invoiced', 'in_progress'],
        'invoiced':    [],   # terminal
        'cancelled':   ['draft'],  # reopen
    }

    STATUS_CHOICES = [
        ('draft',       _('Nacrt')),
        ('in_progress', _('U tijeku')),
        ('completed',   _('Završen')),
        ('invoiced',    _('Fakturiran')),
        ('cancelled',   _('Otkazan')),
    ]
    PRIORITY_CHOICES = [
        ('low',    _('Nisko')),
        ('normal', _('Normalno')),
        ('high',   _('Visoko')),
        ('urgent', _('Hitno')),
    ]

    company         = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Tvrtka'),
    )
    objects         = CompanyManager()

    order_number    = models.CharField(max_length=20, blank=True, verbose_name=_('Broj naloga'))
    date            = models.DateField(auto_now_add=True, verbose_name=_('Datum'))
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name=_('Status'))
    client          = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='work_orders', verbose_name=_('Klijent'),
    )
    assigned_to     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_work_orders', verbose_name=_('Dodijeljen'),
    )
    description     = models.TextField(blank=True, verbose_name=_('Opis radova'))
    notes           = models.TextField(blank=True, verbose_name=_('Napomene'))
    priority        = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', verbose_name=_('Prioritet'))
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name=_('Procijenjeni sati'))
    actual_hours    = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name=_('Stvarni sati'))
    scheduled_date  = models.DateField(null=True, blank=True, verbose_name=_('Planirani datum'))
    scheduled_time  = models.TimeField(null=True, blank=True, verbose_name=_('Planirano vrijeme'))
    completed_date  = models.DateTimeField(null=True, blank=True, verbose_name=_('Datum završetka'))
    deadline        = models.DateField(null=True, blank=True, verbose_name=_('Rok'))
    # Totals (recalculated on save)
    total_labor     = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Ukupno rad'))
    total_materials = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Ukupno materijal'))
    discount        = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Popust (%)'))
    total_net       = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Neto'))
    total_vat       = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('PDV'))
    total_gross     = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Bruto'))
    invoice         = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='work_orders', verbose_name=_('Račun'),
    )
    created_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='work_orders_created', verbose_name=_('Kreirao'),
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Radni nalog')
        verbose_name_plural = _('Radni nalozi')
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.order_number or 'RN-???'} — {self.client or 'Bez klijenta'}"

    def generate_order_number(self):
        import datetime
        year = datetime.date.today().year
        last = WorkOrder.objects.filter(
            company=self.company,
            order_number__startswith=f'RN-{year}-',
        ).order_by('-order_number').first()
        if last and last.order_number:
            try:
                seq = int(last.order_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f'RN-{year}-{seq:04d}'

    def recalculate_totals(self):
        from decimal import Decimal
        labor = Decimal('0')
        materials = Decimal('0')
        total_net = Decimal('0')
        total_vat = Decimal('0')
        for item in self.items.all():
            net = item.total_net
            vat = net * item.tax_rate / Decimal('100')
            total_net += net
            total_vat += vat
            if item.item_type == 'labor':
                labor += net
            else:
                materials += net
        disc_factor = (Decimal('100') - self.discount) / Decimal('100')
        self.total_labor     = (labor     * disc_factor).quantize(Decimal('0.01'))
        self.total_materials = (materials * disc_factor).quantize(Decimal('0.01'))
        self.total_net       = (total_net * disc_factor).quantize(Decimal('0.01'))
        self.total_vat       = (total_vat * disc_factor).quantize(Decimal('0.01'))
        self.total_gross     = (self.total_net + self.total_vat).quantize(Decimal('0.01'))
        self.save(update_fields=['total_labor', 'total_materials', 'total_net', 'total_vat', 'total_gross'])

    def complete(self, user=None):
        import datetime
        self.transition_to('completed', user=user, save=True)
        self.completed_date = datetime.datetime.now()
        super(WorkOrder, self).save(update_fields=['completed_date'])

    @property
    def status_color(self):
        return {
            'draft':       '#64748b',
            'in_progress': '#3b82f6',
            'completed':   '#22c55e',
            'invoiced':    '#c9a84c',
            'cancelled':   '#ef4444',
        }.get(self.status, '#64748b')

    @property
    def priority_color(self):
        return {
            'low':    '#64748b',
            'normal': '#94a3b8',
            'high':   '#f59e0b',
            'urgent': '#ef4444',
        }.get(self.priority, '#94a3b8')


class WorkOrderItem(models.Model):
    ITEM_TYPES = [
        ('labor',    _('Rad / Usluga')),
        ('material', _('Materijal')),
    ]

    work_order      = models.ForeignKey(WorkOrder, on_delete=models.CASCADE,
                                         related_name='items', verbose_name=_('Radni nalog'))
    item_type       = models.CharField(max_length=20, choices=ITEM_TYPES, default='labor',
                                        verbose_name=_('Tip stavke'))
    article         = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Artikl iz zalihe'),
    )
    description     = models.CharField(max_length=200, verbose_name=_('Opis'))
    quantity        = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name=_('Količina'))
    unit            = models.CharField(max_length=20, default='sat', verbose_name=_('JMJ'))
    unit_price      = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Cijena/jed.'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('Popust (%)'))
    tax_rate        = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV (%)'))
    total_net       = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Neto'))
    total_gross     = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Bruto'))
    bom_deducted    = models.BooleanField(default=False, verbose_name=_('BOM razduženo'))

    class Meta:
        verbose_name        = _('Stavka radnog naloga')
        verbose_name_plural = _('Stavke radnog naloga')
        ordering            = ['item_type', 'id']

    def __str__(self):
        return f"{self.description} × {self.quantity} {self.unit}"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        net = self.quantity * self.unit_price * (Decimal('100') - self.discount_percent) / Decimal('100')
        vat = net * self.tax_rate / Decimal('100')
        self.total_net   = net.quantize(Decimal('0.01'))
        self.total_gross = (net + vat).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class VehicleCard(models.Model):
    """Karton vozila — za autoservise"""
    company             = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Tvrtka'),
    )
    objects             = CompanyManager()
    client              = models.ForeignKey(
        'partners.Partner', on_delete=models.CASCADE,
        related_name='vehicle_cards', verbose_name=_('Vlasnik'),
    )
    make                = models.CharField(max_length=50, verbose_name=_('Marka'))
    model               = models.CharField(max_length=50, verbose_name=_('Model'))
    year                = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Godište'))
    registration_plate  = models.CharField(max_length=20, verbose_name=_('Registracija'))
    vin                 = models.CharField(max_length=17, blank=True, verbose_name=_('VIN broj'))
    engine_type         = models.CharField(max_length=50, blank=True, verbose_name=_('Motor'))
    mileage             = models.PositiveIntegerField(default=0, verbose_name=_('Kilometraža'))
    color               = models.CharField(max_length=50, blank=True, verbose_name=_('Boja'))
    notes               = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Karton vozila')
        verbose_name_plural = _('Kartoni vozila')
        ordering            = ['client__name', 'make', 'model']

    def __str__(self):
        return f"{self.make} {self.model} ({self.registration_plate})"


class ClientCard(models.Model):
    """Karton klijenta — za optičare, frizere, kozmetičare"""
    CARD_TYPES = [
        ('optics',    _('Optičar — dioptrija')),
        ('hair',      _('Frizer / Kozmetičar')),
        ('cosmetics', _('Kozmetika')),
        ('general',   _('Opći karton')),
    ]

    company      = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Tvrtka'),
    )
    objects      = CompanyManager()
    client       = models.ForeignKey(
        'partners.Partner', on_delete=models.CASCADE,
        related_name='client_cards', verbose_name=_('Klijent'),
    )
    card_type    = models.CharField(max_length=20, choices=CARD_TYPES, default='general', verbose_name=_('Vrsta kartona'))

    # Optičarski podaci (dioptrija)
    sphere_right   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('Sfero D (sph)'))
    cylinder_right = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('Cilindar D (cyl)'))
    axis_right     = models.IntegerField(null=True, blank=True, verbose_name=_('Os D (axis)'))
    sphere_left    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('Sfero L (sph)'))
    cylinder_left  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('Cilindar L (cyl)'))
    axis_left      = models.IntegerField(null=True, blank=True, verbose_name=_('Os L (axis)'))
    pd             = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name=_('PD (mm)'))
    add_power      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('ADD'))

    # Frizerski / kozmetičarski podaci
    hair_type    = models.CharField(max_length=100, blank=True, verbose_name=_('Tip kose'))
    allergies    = models.TextField(blank=True, verbose_name=_('Alergije'))

    # Opće
    gdpr_consent = models.BooleanField(default=False, verbose_name=_('GDPR suglasnost'))
    last_visit   = models.DateField(null=True, blank=True, verbose_name=_('Zadnji posjet'))
    notes        = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Karton klijenta')
        verbose_name_plural = _('Kartoni klijenata')
        unique_together     = [('company', 'client', 'card_type')]
        ordering            = ['client__name']

    def __str__(self):
        return f"{self.client.name} — {self.get_card_type_display()}"
