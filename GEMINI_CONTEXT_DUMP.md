# Gemini Context Dump — 2026-03-19
# Za: Dual-Routing Fiscal Bypass za udruge (neprofitne)

---

## 1. inventory/models.py — InventoryItem

```python
class InventoryItem(models.Model):
    CATEGORY_CHOICES = [
        ('material',   'Materijal'),
        ('tool',       'Alat'),
        ('equipment',  'Oprema'),
        ('consumable', 'Potrošni materijal'),
        ('product',    'Gotov proizvod'),
        ('service',    'Usluga'),
        ('food',       'Hrana'),
        ('drink',      'Piće'),
        ('dessert',    'Desert'),
        ('special',    'Posebna ponuda'),
        ('other',      'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inventory_items')
    objects = CompanyManager()

    name     = models.CharField(max_length=200)
    sku      = models.CharField(max_length=50)
    barcode  = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    unit     = models.CharField(max_length=20, default='kom')

    quantity     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price     = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    tax_rate = models.ForeignKey('companies.TaxRate', on_delete=models.SET_NULL, null=True, blank=True)

    # DSFinV-K flags
    is_pfand = models.BooleanField(default=False)
    linked_pfand_item = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)
    pfand_tax_override = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    is_tip = models.BooleanField(default=False)
    is_tip_employer = models.BooleanField(default=False)
    kalo_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_weighable = models.BooleanField(default=False)
    dsfinvk_gv_typ = models.CharField(max_length=30, blank=True)

    location = models.CharField(max_length=100, blank=True)
    supplier = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='inventory/', blank=True, null=True)
    webshop_visible = models.BooleanField(default=False)

    class Meta:
        unique_together = [('company', 'sku')]

    # Properties: is_low_stock, margin_percent, stock_value, selling_value
```

### StockMovement.save() — atomic F() update
```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    item = self.item
    if self.movement_type == 'in':
        item.quantity = models.F('quantity') + self.quantity
    elif self.movement_type in ('out', 'return'):
        item.quantity = models.F('quantity') - self.quantity
    elif self.movement_type == 'adjustment':
        item.quantity = self.quantity  # direct set
    item.save(update_fields=['quantity'])
    item.refresh_from_db()
```

---

## 2. pos/services/checkout.py — CheckoutService (FULL)

```python
class CheckoutValidationError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

class CheckoutService:
    """Centralni servis za POS naplatu."""

    @staticmethod
    def _resolve_cashier(cashier_id, company, session):
        """Resolve cashier i dodaj u session.active_cashiers."""
        if not cashier_id: return None
        cashier = POSCashier.objects.filter(pk=cashier_id, company=company, is_active=True).first()
        if cashier: session.active_cashiers.add(cashier)
        return cashier

    @staticmethod
    def _next_receipt_number(session):
        last = session.receipts.order_by('-receipt_number').first()
        return (last.receipt_number + 1) if last else 1

    @staticmethod
    def _deduct_stock(item, qty, unit_price, receipt_number, user):
        """
        B-08 FIX (u /tmp/checkout_fixed.py, čeka root deploy):
        - select_for_update() na InventoryItem za race condition zaštitu
        - Provjera allow_negative_stock na Company
        - Logging kad zaliha ide u minus

        TRENUTNO u produkciji (stara verzija):
        """
        from inventory.models import StockMovement
        StockMovement.objects.create(
            item=item, movement_type='out', quantity=qty,
            unit_price=unit_price, reason='POS bon #%d' % receipt_number,
            performed_by=user,
        )
        # BOM auto-deduction (try/except, non-blocking)

    @staticmethod
    def _fiscalize(receipt):
        """Pokusaj fiskalizirati — ne blokira naplatu ako padne."""
        zki, jir, error = '', '', ''
        try:
            from fiscal.service import fiscalize_pos_receipt
            jir_result = fiscalize_pos_receipt(receipt)
            if jir_result:
                jir = str(jir_result)
                receipt.refresh_from_db()
                zki = receipt.zki or ''
        except Exception as e:
            error = str(e)[:100]
        return zki, jir, error

    @classmethod
    @transaction.atomic
    def process_receipt(cls, company, user, payload):
        """
        Glavni motor naplate.

        Flow:
        1. PARSE payload (session_id, items[], payment_method, amount_paid, ...)
        2. VALIDACIJA (session exists, open, correct company)
        3. PRIPREMA (resolve cashier, next receipt number)
        4. STAVKE (for each item: create POSReceiptItem, deduct stock)
           - Podržava: inventory items, custom items, tips, pfand returns
        5. NAPOJNICA (zasebna stavka ako tip_amount > 0)
        6. RECALCULATE (receipt.recalculate() — subtotal, tax, total)
        7. PLAĆANJE (cash/card/voucher/split payment)
           - Voucher: validate, deduct remaining, split with cash/card
        8. FINALIZE (status=PAID, paid_at=now)
        9. FISKALIZACIJA (non-blocking — cls._fiscalize())
        10. RESULT dict (receipt_id, total, change, zki, jir, pdf_url)
        11. ACTIVITY EVENT (worktime.tracker.track)

        Returns: dict
        Raises: CheckoutValidationError (400)
        """
```

---

## 3. Company model — relevantna polja

```python
class Company(models.Model):
    name = models.CharField(max_length=200)
    oib = models.CharField(max_length=50, unique=True)  # Porezni broj

    # Lokacija (za geofence)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    geofence_radius = models.PositiveIntegerField(default=200)

    # Stock config
    allow_negative_stock = models.BooleanField(default=False)

    # NAPOMENA: Nema fiscal_exempt / is_nonprofit polja — to treba dodati!
```

---

## 4. fiscal/service.py — Fiskalizacija engine

```python
def fiscalize_pos_receipt(receipt):
    """
    Delegira na fiskalizacija.fisk (WS-Security SOAP za FINA CIS).
    Returns: JIR string or None.
    Non-blocking — exception se logira ali ne blokira naplatu.
    """
    from fiskalizacija.fisk import fiscalize_receipt as fisk_fiscalize
    jir = fisk_fiscalize(receipt)
    _log_pos_fiscal(receipt, success=True, jir=jir)
    return jir
```

---

## 5. POSReceipt model — fiskalna polja

```python
class POSReceipt(models.Model):
    Status = TextChoices: OPEN, PAID, CANCELLED, REFUNDED

    session = FK(POSSession)
    receipt_number = IntegerField
    invoice = OneToOne(Invoice, null=True)
    subtotal, tax_amount, total = DecimalField
    discount = DecimalField
    status = CharField (OPEN → PAID / CANCELLED / REFUNDED)
    table_number, note = CharField
    created_at, paid_at = DateTimeField
    cancel_reason = CharField
    cashier = FK(POSCashier)

    # Fiskalizacija
    zki = CharField(max_length=32, null=True, blank=True)
    jir = CharField(max_length=40, null=True, blank=True)
    fiscal_datetime = DateTimeField(null=True, blank=True)

    # B-04 FIX (već migrirano):
    fiscal_retry_count = PositiveSmallIntegerField(default=0)
    fiscal_last_error = CharField(max_length=200, blank=True)
```

---

## 6. Današnje B-fixevi (već implementirano)

### B-04: Fiskalizacija offline bonova
- `fiscal_retry_count` + `fiscal_last_error` polja dodana (migration 0027)
- `retry_fiscalization()` task poboljšan:
  - 48h CRITICAL alert (zakonski rok)
  - 24h WARNING notifikacija
  - Eksponencijalni backoff (0-5 odmah, 6-10 svaki 5., 11+ svaki 15.)
  - Superadmin push notifikacija

### B-08: Stock race condition
- `select_for_update()` u `_deduct_stock()` (čeka root deploy)
- `allow_negative_stock` guard na Company

### B-02: Otvoreni bonovi na logout
- `smart_logout()` provjerava otvorene bonove
- GET = upozorenje s brojevima bonova
- POST = auto-cancel otvorenih bonova

---

## 7. Kontekst za Dual-Routing Fiscal Bypass

### Što treba za udruge:
1. **Company.fiscal_exempt** = BooleanField — udruge bez PDV obveze
2. **CheckoutService._fiscalize()** — preskoči ako `company.fiscal_exempt`
3. **Račun se generira normalno** — broj, PDF, stavke — ali bez ZKI/JIR
4. **Audit log** — bilježi da je fiskalizacija preskočena i zašto
5. **retry_fiscalization()** — preskoči fiscal_exempt račune

### Zakonski okvir:
- ZOR (NN 133/12) NE pokriva neprofitne bez PDV-a
- Udruge koje JESU u sustavu PDV-a MORAJU fiskalizirati
- Flag mora biti zaštićen — samo superadmin može uključiti/isključiti
- Revizorski paket mora jasno označiti exempt račune

### Arhitekturna preporuka (CC#2):
Bypass treba biti u `_fiscalize()` metodi — NE u `process_receipt()`.
Razlog: process_receipt je već 300 linija, dodavanje if/else unutra povećava kompleksnost.
Čišći pristup: `_fiscalize()` sam odlučuje treba li fiskalizirati.

```python
# Predloženi pristup:
@staticmethod
def _fiscalize(receipt):
    company = receipt.session.terminal.company
    if getattr(company, 'fiscal_exempt', False):
        logger.info('Fiscal skip: company %s is exempt (nonprofit)', company.name)
        return '', '', ''  # no zki, no jir, no error
    # ... postojeća fiskalizacija logika ...
```
