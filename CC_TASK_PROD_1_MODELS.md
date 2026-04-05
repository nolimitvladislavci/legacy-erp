# CC_TASK_PROD_1_MODELS.md
# PRODUCTION MODULE — TASK 1: Models + Migrations + App Setup
# Agent: CC Code / Gemini
# Nema ovisnosti o drugim taskovima — radi PRVI, ostali čekaju tebe.

---

## CILJ
Kreirati Django app `production/` s kompletnim modelima za MRP modul.
Rezultat: `python manage.py migrate` prolazi, admin registriran, 0 grešaka.

---

## ARHITEKTURA — PRAVILA

- NULA cirkularnih importa — `production` smije importati `inventory`, `partners`, `companies`, `konto`, ali NE SMIJE biti importan iz tih appova
- SVE FK prema InventoryItem, Partner, Company — bez custom modela za iste entitete
- FSMMixin za ProductionOrder (import iz `borg_ops.mixins`)
- CompanyManager na svim modelima s `company` poljem
- Sve Decimal kalkulacije s `quantize(Decimal('0.01'))`

---

## TASK 1A — App kreacija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp production
```

Dodati u `core/settings.py` → INSTALLED_APPS:
```python
'production',
```

---

## TASK 1B — Models (production/models.py)

### Model 1: BillOfMaterials (Sastavnica)
```python
class BillOfMaterials(models.Model):
    """
    Sastavnica — recept za jedan gotov proizvod.
    Jedan InventoryItem može imati točno jednu aktivnu BOM (is_active=True).
    """
    company         # FK Company
    product         # FK InventoryItem (category='product') — gotov proizvod
    name            # CharField (npr. "Jabučni sok 1L — osnovna")
    version         # CharField default='1.0'
    is_active       # BooleanField default=True
    yield_quantity  # DecimalField — koliko gotovog proizvoda daje jedna serija
    yield_unit      # CharField (npr. 'kom', 'L', 'kg')
    notes           # TextField blank
    created_at, updated_at

    class Meta:
        unique_together = [('company', 'product', 'version')]
        verbose_name = 'Sastavnica (BOM)'
```

### Model 2: BOMLine (Stavka sastavnice)
```python
class BOMLine(models.Model):
    """
    Jedna sirovina/poluproizvod u sastavnici.
    """
    bom             # FK BillOfMaterials related_name='lines'
    material        # FK InventoryItem — sirovina ili poluproizvod
    quantity        # DecimalField — potrebna količina PO seriji
    unit            # CharField — prepisati iz material.unit
    scrap_percent   # DecimalField default=0 — % dozvoljenog škarta
    notes           # CharField blank

    @property
    def quantity_with_scrap(self):
        # quantity * (1 + scrap_percent/100)
```

### Model 3: WorkCenter (Radno mjesto)
```python
class WorkCenter(models.Model):
    """
    Radno mjesto / stroj / linija.
    """
    company         # FK Company
    name            # CharField (npr. "Presa 1", "Montaža A")
    code            # CharField unique per company
    capacity_hours_per_day  # DecimalField default=8
    cost_per_hour   # DecimalField — trošak po satu (stroj + režija)
    is_active       # BooleanField default=True

    class Meta:
        unique_together = [('company', 'code')]
```

### Model 4: ProductionOrder (Proizvodni nalog)
```python
class ProductionOrder(FSMMixin, models.Model):
    """
    Srce MRP modula. Jeden nalog = jedna serija gotovog proizvoda.
    """
    STATUS_FIELD = 'status'
    TRANSITIONS = {
        'draft':       ['planned', 'cancelled'],
        'planned':     ['in_progress', 'draft', 'cancelled'],
        'in_progress': ['completed', 'paused', 'cancelled'],
        'paused':      ['in_progress', 'cancelled'],
        'completed':   ['invoiced'],
        'invoiced':    [],      # terminal
        'cancelled':   ['draft'],  # reopen
    }
    STATUS_CHOICES = [
        ('draft',       'Nacrt'),
        ('planned',     'Planirano'),
        ('in_progress', 'U tijeku'),
        ('paused',      'Pauzirano'),
        ('completed',   'Završeno'),
        ('invoiced',    'Fakturirano'),
        ('cancelled',   'Otkazano'),
    ]

    company             # FK Company
    order_number        # CharField — auto-generate: PN-2026-0001
    bom                 # FK BillOfMaterials
    product             # FK InventoryItem — kopija iz BOM (denorm, za brzinu)
    work_center         # FK WorkCenter null=True blank=True
    planned_quantity    # DecimalField — koliko komada planiramo
    actual_quantity     # DecimalField default=0 — stvarno proizvedeno
    status              # CharField choices FSM
    planned_start       # DateField null=True
    planned_end         # DateField null=True
    actual_start        # DateTimeField null=True
    actual_end          # DateTimeField null=True
    # Troškovi (računaju se pri completion)
    cost_materials      # DecimalField default=0
    cost_labor          # DecimalField default=0
    cost_overhead       # DecimalField default=0
    cost_total          # DecimalField default=0
    cost_per_unit       # DecimalField default=0
    # Konto
    konto_entry         # FK konto.KontoEntry null=True blank=True
    # Veze
    sales_order_ref     # CharField blank — referenca na prodajni nalog
    notes               # TextField blank
    created_by          # FK User null=True
    created_at, updated_at

    def generate_order_number(self):
        # Format: PN-YEAR-NNNN, auto iz baze

    def recalculate_costs(self):
        # Zbroji sve ProductionCost za ovaj nalog
        # Postavi cost_total, cost_per_unit

    @property
    def status_color(self):
        # dict: draft=#64748b, planned=#3b82f6, in_progress=#f59e0b,
        #       completed=#22c55e, invoiced=#c9a84c, cancelled=#ef4444
```

### Model 5: ProductionOrderLine (Potrošak materijala)
```python
class ProductionOrderLine(models.Model):
    """
    Planirana i stvarna potrošnja materijala po nalogu.
    Generira se automatski iz BOM pri kreiranju naloga.
    """
    order               # FK ProductionOrder related_name='lines'
    material            # FK InventoryItem
    bom_line            # FK BOMLine null=True — odakle dolazi
    planned_quantity    # DecimalField — iz BOM × planned_quantity
    actual_quantity     # DecimalField default=0 — stvarno utrošeno
    unit                # CharField
    unit_cost           # DecimalField — cijena iz inventory (FIFO/AVG)
    total_cost          # DecimalField — actual_quantity × unit_cost
    stock_deducted      # BooleanField default=False — je li inventory razdužen

    def calculate_cost(self):
        # unit_cost × actual_quantity → total_cost
```

### Model 6: ProductionCost (Troškovi)
```python
class ProductionCost(models.Model):
    """
    Evidencija svih troškova po nalogu (materijal, rad, režija).
    """
    COST_TYPE_CHOICES = [
        ('material',  'Materijal'),
        ('labor',     'Radna snaga'),
        ('overhead',  'Režija'),
        ('other',     'Ostalo'),
    ]
    order       # FK ProductionOrder related_name='costs'
    cost_type   # CharField choices
    description # CharField
    quantity    # DecimalField
    unit        # CharField
    unit_cost   # DecimalField
    total_cost  # DecimalField (quantity × unit_cost)
    employee    # FK User null=True — za radnu snagu
    work_center # FK WorkCenter null=True
    date        # DateField auto_now_add
```

### Model 7: ProductionQualityCheck (QC)
```python
class ProductionQualityCheck(models.Model):
    """
    Kontrola kvalitete — jednostavna, bez zasebnog QMS modula.
    """
    QC_RESULT = [('pass','Prošlo'), ('fail','Palo'), ('conditional','Uvjetno')]
    order           # FK ProductionOrder
    checked_by      # FK User
    checked_at      # DateTimeField auto_now_add
    result          # CharField choices
    accepted_qty    # DecimalField — prihvaćena količina
    rejected_qty    # DecimalField — odbačena (škart)
    notes           # TextField blank
```

---

## TASK 1C — Migracije

```bash
venv/bin/python manage.py makemigrations production
venv/bin/python manage.py migrate production
```

Provjeri: `venv/bin/python manage.py migrate --check` → 0 pending

---

## TASK 1D — Admin (production/admin.py)

Registrirati sve modele s inline-ovima:
- `BillOfMaterialsAdmin` + `BOMLineInline` (TabularInline)
- `ProductionOrderAdmin` + `ProductionOrderLineInline` + `ProductionCostInline`
- `WorkCenterAdmin`
- Filter: company, status, work_center
- Search: order_number, product__name, bom__name

---

## TASK 1E — Apps.py i __init__.py

`production/apps.py`:
```python
class ProductionConfig(AppConfig):
    name = 'production'
    verbose_name = 'Proizvodnja (MRP)'
    
    def ready(self):
        import production.signals  # noqa
```

---

## PROVJERA USPJEHA

```bash
cd /var/www/fina-connect
venv/bin/python manage.py check production  # 0 errors
venv/bin/python manage.py migrate --check   # No pending
venv/bin/python -c "
import django; django.setup()
from production.models import BillOfMaterials, ProductionOrder, WorkCenter
print('Models OK:', BillOfMaterials, ProductionOrder, WorkCenter)
"
```

---

## BLOCKER ZA OSTALE TASKOVE
Task 2, 3, 4, 5, 6 NE MOGU početi dok ovaj task nije završen i migriran.
Kad završiš: `echo "TASK1_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
