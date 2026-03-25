# CC_TASK_LOT_SLIJEDIVOST — LOT/Serija veza checkout→termal
# Agent: CC Code
# Prioritet: VISOK — food safety, HACCP, inspekcija
# Datum: 2026-03-25
# Verificirano: Sonnet direktno na serveru

---

## Što postoji (NE DIRAJ)
- ✅ `inventory/models.py` → `StockBatch` (redak 680+): batch_number, expiry_date, FEFO ordering
- ✅ `pos/models.py` → `ExpiryBatch` (redak 880+): batch_number, expiry_date
- ✅ `pos/services/checkout.py` redak 312: "Fail-fast: jedan batch query" — ali **ne dohvaća LOT**
- ✅ `templates/pos/receipt_thermal.html` postoji — **nema LOT polja**

## Što nedostaje — 3 precizne rupe

### RUPA 1: POSReceiptItem nema FK na StockBatch

`pos/models.py`, klasa `POSReceiptItem` (redak 343) — nema polje koje bilježi koji batch je prodан.

**Dodaj:**
```python
# U klasi POSReceiptItem, nakon inventory_item FK:
stock_batch = models.ForeignKey(
    'inventory.StockBatch',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='pos_items',
    verbose_name=_('LOT / Serija'),
    help_text=_('Automatski odabran pri naplati (FEFO)'),
)
lot_number = models.CharField(
    max_length=100, blank=True,
    verbose_name=_('LOT broj'),
    help_text=_('Kopija iz StockBatch.batch_number — ostaje čak i ako se batch briše'),
)
expiry_date_snapshot = models.DateField(
    null=True, blank=True,
    verbose_name=_('Rok trajanja (snapshot)'),
    help_text=_('Kopija iz StockBatch.expiry_date pri prodaji'),
)
```

**Migracija:** standardna `makemigrations pos`

---

### RUPA 2: Checkout ne odabire LOT (FEFO)

`pos/services/checkout.py` — u metodi `_add_items` ili tamo gdje se kreira `POSReceiptItem`.

Pronađi točno mjesto gdje se kreira `POSReceiptItem.objects.create(...)` i dodaj FEFO logiku:

```python
# FEFO auto-pick za LOT
stock_batch = None
lot_number = ''
expiry_snap = None

if inv_item:  # ako postoji inventory veza
    from inventory.models import StockBatch
    # FEFO: najstariji rok prvi, bez karantene
    batch = StockBatch.objects.filter(
        item=inv_item,
        company=company,
        quarantine_status='active',
        quantity__gt=0,
    ).order_by('expiry_date').first()  # FEFO — expiry_date ASC
    
    if batch:
        stock_batch = batch
        lot_number = batch.batch_number or ''
        expiry_snap = batch.expiry_date
        # Smanji zalihu na batchu
        batch.quantity = models.F('quantity') - qty
        batch.save(update_fields=['quantity'])

# U POSReceiptItem.objects.create():
# Dodaj: stock_batch=stock_batch, lot_number=lot_number, expiry_date_snapshot=expiry_snap
```

**Napomena:** Ako artikl nema batche (99% slučajeva) — fallback na staro ponašanje, lot_number=''.

---

### RUPA 3: Termalni ispis ne prikazuje LOT

`templates/pos/receipt_thermal.html` — u petlji po stavkama (gdje se ispisuje opis, količina, cijena).

Dodaj ispod opisa artikla:
```html
{% if item.lot_number %}
<div style="font-size:6pt;color:#555">
  LOT: {{ item.lot_number }}{% if item.expiry_date_snapshot %} | Rok: {{ item.expiry_date_snapshot|date:"d.m.Y" }}{% endif %}
</div>
{% endif %}
```

---

## Bonus: LOT na PDF računu (invoicing)

Ako `invoicing/templates/invoicing/` ima stavke — isti pattern, isti `{% if item.lot_number %}` blok.

---

## Definition of Done

```bash
# Provjera u bazi:
venv/bin/python manage.py shell -c "
from pos.models import POSReceiptItem
print(hasattr(POSReceiptItem, 'stock_batch'))  # True
print(hasattr(POSReceiptItem, 'lot_number'))    # True
"

# Provjera flow:
# 1. Kreiraj StockBatch za artikl s expiry_date
# 2. Napravi checkout s tim artiklom
# 3. Provjeri: POSReceiptItem.lot_number = batch_number ✅
# 4. Otvori termalni ispis → vidiš LOT ✅
```

Commit: `feat: LOT slijedivost — POSReceiptItem.stock_batch + FEFO checkout + termalni ispis`

---

## Zakonska osnova
- Zakon o hrani (NN 81/13) — slijedivost prehrambenih proizvoda
- EU Uredba 178/2002 — General Food Law, čl. 18 slijedivost
- HACCP — identifikacija kritičnih točaka, lot tracking
- Relevantno za: pekare (Šeki), mesare, OPG, ribare
