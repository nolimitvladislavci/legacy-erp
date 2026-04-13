"""
production/models.py — MRP / Proizvodni modul

3 razine (kao Pupilla Proizvodnja I/II/III):
  I.  BOM + radni nalozi + materijalna kalkulacija
  II. Radne stanice + routing + kapacitet planiranje
  III. QC + šarže/serije + traceability + cost accounting

7 modela:
  Workstation       — stroj/linija/radno mjesto
  BillOfMaterials   — receptura (header)
  BOMLine           — materijal u recepturi
  ProductionOrder   — radni nalog
  ProductionStep    — korak u proizvodnji (routing)
  QualityCheck      — kontrola kvalitete
  ProductionLog     — audit trail
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist


# ════════════════════════════════════════════════════════════════
# WORKSTATION — stroj, linija, radno mjesto
# ════════════════════════════════════════════════════════════════

class Workstation(models.Model):
    """Radna stanica / stroj / proizvodna linija."""
    TYPE_CHOICES = [
        ('machine', _('Stroj')),
        ('line', _('Linija')),
        ('manual', _('Ručni rad')),
        ('oven', _('Peć / sušara')),
        ('mixing', _('Miješalica')),
        ('packaging', _('Pakiranje')),
        ('other', _('Ostalo')),
    ]
    STATUS_CHOICES = [
        ('active', _('Aktivna')),
        ('maintenance', _('Održavanje')),
        ('inactive', _('Neaktivna')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='workstations',
    )
    name = models.CharField(max_length=120, verbose_name=_('Naziv'))
    code = models.CharField(max_length=30, blank=True, verbose_name=_('Šifra'))
    ws_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='machine',
                                verbose_name=_('Tip'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    capacity_per_hour = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Kapacitet/sat'), help_text=_('Jedinica outputa po satu'),
    )
    hourly_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Cijena/sat (EUR)'),
    )
    location = models.CharField(max_length=200, blank=True, verbose_name=_('Lokacija'))
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Radna stanica')
        verbose_name_plural = _('Radne stanice')
        unique_together = [('company', 'code')]

    def __str__(self):
        return f'{self.name} ({self.code})' if self.code else self.name


# ════════════════════════════════════════════════════════════════
# BOM — Bill of Materials (receptura / sastavnica)
# ════════════════════════════════════════════════════════════════

class BillOfMaterials(models.Model):
    """
    Sastavnica / receptura — definira od čega se proizvod sastoji.
    Jedan gotov proizvod (output_item) = N sirovina (BOMLine).
    """
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('active', _('Aktivna')),
        ('archived', _('Arhivirana')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='boms',
    )
    name = models.CharField(max_length=200, verbose_name=_('Naziv recepture'))
    code = models.CharField(max_length=30, blank=True, verbose_name=_('Šifra'))
    output_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.PROTECT,
        related_name='bom_as_output',
        verbose_name=_('Gotov proizvod'),
        help_text=_('Artikl koji se proizvodi iz ove recepture'),
    )
    output_quantity = models.DecimalField(
        max_digits=12, decimal_places=4, default=1,
        verbose_name=_('Količina outputa'),
        help_text=_('Koliko gotovog proizvoda daje jedna serija'),
    )
    output_unit = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica'))
    parent_bom = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sub_boms',
        verbose_name=_('Nadređena sastavnica'),
        help_text=_('Za multi-level BOM: ova sastavnica je podsklop nadređene'),
    )
    level = models.PositiveIntegerField(default=0, verbose_name=_('Razina BOM-a'),
                                         help_text=_('0=vrhunski, 1=podsklop, 2=pod-podsklop'))
    version = models.PositiveIntegerField(default=1, verbose_name=_('Verzija'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    default_workstation = models.ForeignKey(
        Workstation, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Zadana radna stanica'),
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        default=0, verbose_name=_('Procijenjeno trajanje (min)'),
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Sastavnica (BOM)')
        verbose_name_plural = _('Sastavnice (BOM)')
        unique_together = [('company', 'code')]

    def __str__(self):
        return f'{self.name} v{self.version}'

    @property
    def total_material_cost(self):
        """Ukupni trošak materijala za jednu seriju."""
        return sum(
            line.line_cost for line in self.lines.all()
        )

    @property
    def unit_cost(self):
        """Trošak materijala po jedinici gotovog proizvoda."""
        if self.output_quantity:
            return self.total_material_cost / self.output_quantity
        return Decimal('0')

    def explode(self, multiplier=Decimal('1'), depth=0, max_depth=10):
        """
        Recursive BOM explosion — razloži do sirovina.
        Vraća flat listu: [{item, quantity, level, bom_name, is_subassembly}]
        """
        if depth > max_depth:
            return []
        result = []
        for line in self.lines.select_related('item').all():
            qty = line.effective_quantity * multiplier
            # Provjeri ima li ovaj item vlastiti BOM (podsklop)
            sub_bom = BillOfMaterials.objects.filter(
                company=self.company, output_item=line.item, status='active'
            ).first()
            if sub_bom:
                result.append({
                    'item': line.item, 'quantity': qty, 'unit': line.unit,
                    'level': depth, 'bom_name': sub_bom.name,
                    'is_subassembly': True, 'waste_percent': line.waste_percent,
                })
                # Recurse into sub-BOM
                sub_multiplier = qty / sub_bom.output_quantity
                result.extend(sub_bom.explode(sub_multiplier, depth + 1, max_depth))
            else:
                result.append({
                    'item': line.item, 'quantity': qty, 'unit': line.unit,
                    'level': depth, 'bom_name': self.name,
                    'is_subassembly': False, 'waste_percent': line.waste_percent,
                })
        return result

    @property
    def total_exploded_cost(self):
        """Ukupni trošak s recursive BOM explosion."""
        total = Decimal('0')
        for line in self.explode():
            if not line['is_subassembly']:
                price = getattr(line['item'], 'purchase_price', None) or getattr(line['item'], 'unit_price', Decimal('0'))
                total += line['quantity'] * price
        return total


class BOMLine(models.Model):
    """Jedna sirovina/materijal u BOM-u."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.CASCADE,
        related_name='lines',
    )
    item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.PROTECT,
        related_name='bom_as_input',
        verbose_name=_('Materijal / sirovina'),
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=4,
        verbose_name=_('Količina'),
    )
    unit = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica'))
    waste_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Rasip (%)'),
        help_text=_('Postotak materijala koji se gubi u procesu'),
    )
    notes = models.CharField(max_length=200, blank=True)
    is_subassembly = models.BooleanField(default=False, verbose_name=_('Podsklop'),
                                          help_text=_('Označava da je ova stavka sama po sebi BOM'))
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = _('BOM stavka')
        verbose_name_plural = _('BOM stavke')

    def __str__(self):
        return f'{self.item.name} × {self.quantity}'

    @property
    def effective_quantity(self):
        """Stvarna potrebna količina (s rasipom)."""
        return self.quantity * (1 + self.waste_percent / 100)

    @property
    def line_cost(self):
        """Trošak ove stavke."""
        price = getattr(self.item, 'purchase_price', None) or getattr(self.item, 'unit_price', Decimal('0'))
        return self.effective_quantity * price


# ════════════════════════════════════════════════════════════════
# PRODUCTION ORDER — radni nalog
# ════════════════════════════════════════════════════════════════

class ProductionOrder(models.Model):
    """
    Radni nalog za proizvodnju — od planiranja do završetka.
    Lifecycle: draft → confirmed → in_progress → done (ili cancelled)
    """
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('confirmed', _('Potvrđen')),
        ('in_progress', _('U tijeku')),
        ('done', _('Završen')),
        ('cancelled', _('Otkazan')),
    ]
    PRIORITY_CHOICES = [
        (1, _('Niska')),
        (2, _('Normalna')),
        (3, _('Visoka')),
        (4, _('Hitna')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='production_orders',
    )
    order_number = models.CharField(max_length=30, verbose_name=_('Broj naloga'))
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.PROTECT,
        related_name='production_orders',
        verbose_name=_('Receptura'),
    )
    planned_quantity = models.DecimalField(
        max_digits=12, decimal_places=4,
        verbose_name=_('Planirana količina'),
    )
    produced_quantity = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name=_('Proizvedena količina'),
    )
    scrap_quantity = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name=_('Škart'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=2)
    workstation = models.ForeignKey(
        Workstation, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Radna stanica'),
    )
    # Batch / lot tracking (Proizvodnja III)
    batch_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj šarže'))
    lot_number = models.CharField(max_length=50, blank=True, verbose_name=_('Lot'))
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_('Rok trajanja'))
    # Dates
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name=_('Planirani početak'))
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name=_('Planirani kraj'))
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name=_('Stvarni početak'))
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name=_('Stvarni kraj'))
    # Cost accounting (Proizvodnja III)
    material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name=_('Trošak materijala'))
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      verbose_name=_('Trošak rada'))
    overhead_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name=_('Režijski troškovi'))
    # Planned costs (za variance analizu)
    planned_material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                 verbose_name=_('Planirani trošak materijala'))
    planned_labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_('Planirani trošak rada'))
    planned_total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_('Planirani ukupni trošak'))
    # Meta
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='production_orders_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Radni nalog')
        verbose_name_plural = _('Radni nalozi')
        unique_together = [('company', 'order_number')]

    def __str__(self):
        return f'{self.order_number} — {self.bom.output_item.name}'

    @property
    def total_cost(self):
        return self.material_cost + self.labor_cost + self.overhead_cost

    @property
    def unit_production_cost(self):
        if self.produced_quantity:
            return self.total_cost / self.produced_quantity
        return Decimal('0')

    @property
    def yield_percent(self):
        """Iskoristivost — koliko % planiranog je proizvedeno."""
        if self.planned_quantity:
            return (self.produced_quantity / self.planned_quantity * 100).quantize(Decimal('0.1'))
        return Decimal('0')

    @property
    def scrap_percent(self):
        total = self.produced_quantity + self.scrap_quantity
        if total:
            return (self.scrap_quantity / total * 100).quantize(Decimal('0.1'))
        return Decimal('0')

    @property
    def cost_variance(self):
        """Razlika između planiranog i stvarnog troška."""
        if self.planned_total_cost:
            return self.total_cost - self.planned_total_cost
        return Decimal('0')

    @property
    def cost_variance_percent(self):
        """Variance kao postotak planiranog."""
        if self.planned_total_cost:
            return ((self.total_cost - self.planned_total_cost) / self.planned_total_cost * 100).quantize(Decimal('0.1'))
        return Decimal('0')

    def calculate_material_requirements(self):
        """Izračunaj potrebne materijale za ovaj nalog."""
        multiplier = self.planned_quantity / self.bom.output_quantity
        requirements = []
        for line in self.bom.lines.select_related('item').all():
            requirements.append({
                'item': line.item,
                'required': line.effective_quantity * multiplier,
                'unit': line.unit,
                'available': getattr(line.item, 'quantity', 0),
            })
        return requirements


# ════════════════════════════════════════════════════════════════
# PRODUCTION STEP — routing / korak proizvodnje
# ════════════════════════════════════════════════════════════════

class ProductionStep(models.Model):
    """
    Korak u proizvodnom procesu (routing).
    Svaki radni nalog može imati N koraka.
    Proizvodnja II razina.
    """
    STATUS_CHOICES = [
        ('pending', _('Čeka')),
        ('in_progress', _('U tijeku')),
        ('done', _('Završen')),
        ('skipped', _('Preskočen')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE,
        related_name='steps',
    )
    step_number = models.PositiveIntegerField(verbose_name=_('Korak #'))
    name = models.CharField(max_length=120, verbose_name=_('Naziv koraka'))
    description = models.TextField(blank=True)
    workstation = models.ForeignKey(
        Workstation, on_delete=models.SET_NULL, null=True, blank=True,
    )
    estimated_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Procjena (min)'))
    actual_minutes = models.PositiveIntegerField(default=0, verbose_name=_('Stvarno (min)'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['step_number']
        verbose_name = _('Proizvodni korak')
        verbose_name_plural = _('Proizvodni koraci')
        unique_together = [('order', 'step_number')]

    def __str__(self):
        return f'#{self.step_number} {self.name}'


# ════════════════════════════════════════════════════════════════
# QUALITY CHECK — kontrola kvalitete (Proizvodnja III)
# ════════════════════════════════════════════════════════════════

class QualityCheck(models.Model):
    """
    QC zapis — kontrola kvalitete na radnom nalogu ili koraku.
    """
    RESULT_CHOICES = [
        ('pass', _('Prolazi')),
        ('fail', _('Ne prolazi')),
        ('conditional', _('Uvjetno prolazi')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE,
        related_name='quality_checks',
    )
    step = models.ForeignKey(
        ProductionStep, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quality_checks',
    )
    check_name = models.CharField(max_length=200, verbose_name=_('Naziv provjere'))
    parameter = models.CharField(max_length=100, blank=True,
                                  verbose_name=_('Parametar'), help_text=_('Npr. temperatura, težina, pH'))
    expected_value = models.CharField(max_length=100, blank=True, verbose_name=_('Očekivana vrijednost'))
    actual_value = models.CharField(max_length=100, blank=True, verbose_name=_('Stvarna vrijednost'))
    tolerance = models.CharField(max_length=50, blank=True, verbose_name=_('Tolerancija'))
    result = models.CharField(max_length=15, choices=RESULT_CHOICES, verbose_name=_('Rezultat'))
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    checked_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='production/qc/', blank=True, null=True,
                               verbose_name=_('Fotografija'))

    class Meta:
        ordering = ['-checked_at']
        verbose_name = _('Kontrola kvalitete')
        verbose_name_plural = _('Kontrole kvalitete')

    def __str__(self):
        return f'{self.check_name}: {self.result}'


# ════════════════════════════════════════════════════════════════
# PRODUCTION LOG — audit trail
# ════════════════════════════════════════════════════════════════

class ProductionLog(models.Model):
    """Automatski log svih promjena na radnom nalogu."""
    ACTION_CHOICES = [
        ('created', _('Kreiran')),
        ('confirmed', _('Potvrđen')),
        ('started', _('Pokrenut')),
        ('step_done', _('Korak završen')),
        ('qc_pass', _('QC prolazi')),
        ('qc_fail', _('QC ne prolazi')),
        ('produced', _('Proizvedeno')),
        ('scrap', _('Škart')),
        ('completed', _('Završen')),
        ('cancelled', _('Otkazan')),
        ('material_consumed', _('Materijal utrošen')),
        ('cost_updated', _('Trošak ažuriran')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE,
        related_name='logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Proizvodni log')
        verbose_name_plural = _('Proizvodni logovi')

    def __str__(self):
        return f'{self.order.order_number} — {self.get_action_display()}'


# ════════════════════════════════════════════════════════════════
# MRP PLANNED ORDER — automatski generirani planirani nalozi
# ════════════════════════════════════════════════════════════════

class MRPPlannedOrder(models.Model):
    """
    Planirani nalog iz MRP run-a.
    MRP algoritam generira ovo kad detektira manjak materijala.
    Može se pretvoriti u ProductionOrder ili PurchaseSuggestion.
    """
    TYPE_CHOICES = [
        ('produce', _('Proizvesti')),
        ('purchase', _('Nabaviti')),
    ]
    STATUS_CHOICES = [
        ('planned', _('Planirano')),
        ('confirmed', _('Potvrđeno')),
        ('cancelled', _('Otkazano')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='mrp_planned_orders')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.PROTECT,
                              related_name='mrp_planned_orders')
    order_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    needed_by = models.DateField(verbose_name=_('Potrebno do'))
    order_date = models.DateField(verbose_name=_('Datum narudžbe'),
                                   help_text=_('needed_by - lead_time'))
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.SET_NULL, null=True, blank=True)
    source_order = models.ForeignKey(ProductionOrder, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='mrp_planned_orders')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='planned')
    mrp_run_id = models.CharField(max_length=50, blank=True, help_text=_('ID MRP pokretanja'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order_date']
        verbose_name = _('MRP planirani nalog')
        verbose_name_plural = _('MRP planirani nalozi')

    def __str__(self):
        return f'{self.get_order_type_display()} {self.item.name} × {self.quantity} do {self.needed_by}'
