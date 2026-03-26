# CC TASK: Borg Skladišni Modul — Sprint W1 (Temelji)
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-27
## Autonomija: Sonnet ovlastio — radi bez odobrenja

---

## OBAVEZNO PROČITAJ PRVO

```bash
cat LEGAL_PARAMS_MASTER.md
cat AGENT_PARAMS_TESTNI_PODACI.md
git log --oneline -5
venv/bin/python manage.py check
# Pročitaj modele:
head -200 inventory/models.py
```

---

## KONTEKST — ŠTO POSTOJI

### inventory/models.py — ključni modeli
- `InventoryItem` — 12.259 zapisa, category choices ima 11 opcija
- `StockMovement` — 191 zapisa, tipovi: in/out/adjustment/transfer/return/donation_in/writeoff
- `Warehouse` — 5 warehousa, tipovi: production/retail/storage/vehicle
- `GoodsReceipt` — 1.044, primka ulaznih računa
- `StockBatch` — šarže, FEFO, karantena
- `WarehouseTransfer` — međuskladišnica (postoji!)
- `Inventura` + `InventuraItem` + `InventuraCommission` — inventura

### Veze prema van (sve postoje, samo nisu sve wire-ane)
- `webshop.Product.inventory_item` FK → InventoryItem
- `pos.POSReceiptItem.inventory_item` FK → InventoryItem
- `invoicing.InvoiceItem` FK → Invoice (ne direktno na Item)
- `procurement.PurchaseOrder` → InventoryItem
- `smart_import.ImportBatchItem` → InventoryItem (email ramp)
- `traceability.ProductTrace` → InventoryItem

---

## SPRINT W1A — Proširenje InventoryItem modela

### VAŽNO: Pročitaj stvarna polja PRIJE pisanja migracije
```bash
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.models import InventoryItem
print([f.name for f in InventoryItem._meta.concrete_fields])
"
```

### Nova polja — dodati u InventoryItem

```python
# inventory/models.py — u klasu InventoryItem dodati NOVA polja:

# ── KLASIFIKACIJA ─────────────────────────────────────────────────
ITEM_CLASS_CHOICES = [
    ('tangible',     _('Materijalno (roba/materijal)')),
    ('service',      _('Usluga (ne ide u skladište)')),
    ('intangible',   _('Nematerijalno (IP/licence)')),
    ('asset',        _('Imovina (osnovna sredstva)')),
    ('financial',    _('Financijsko (devize/vrijednosnice)')),
]

FISCAL_TREATMENT_CHOICES = [
    ('standard',     _('Standardno — fiskalizira')),
    ('service_cash', _('Usluga — fiskalizira pri gotovinskoj naplati')),
    ('exempt_pdv',   _('Oslobođeno PDV-a')),
    ('no_fiscal',    _('Ne fiskalizira (imovina/IP)')),
    ('currency',     _('Deviza — posebna evidencija')),
    ('pfand',        _('Ambalaža/Pfand — poseban tretman')),
]

TRADE_TYPE_CHOICES = [
    ('retail',       _('Maloprodaja (B2C)')),
    ('wholesale',    _('Veleprodaja (B2B)')),
    ('both',         _('Oboje')),
    ('internal',     _('Interno — ne prodaje se')),
]

# Klasifikacija (ključno za sve logike)
item_class        = models.CharField(max_length=15, choices=ITEM_CLASS_CHOICES,
                                      default='tangible', verbose_name=_('Klasa artikla'))
fiscal_treatment  = models.CharField(max_length=15, choices=FISCAL_TREATMENT_CHOICES,
                                      default='standard', verbose_name=_('Fiskalni tretman'))
trade_type        = models.CharField(max_length=15, choices=TRADE_TYPE_CHOICES,
                                      default='both', verbose_name=_('Tip prodaje'))

# ── CIJENE (maloprodaja vs. veleprodaja) ──────────────────────────
wholesale_price   = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                         verbose_name=_('Veleprodajna cijena (bez PDV)'),
                                         help_text=_('Cijena za B2B klijente'))
min_order_qty     = models.DecimalField(max_digits=10, decimal_places=2, default=1,
                                         verbose_name=_('Min. narudžba (veleprodaja)'))
price_valid_until = models.DateField(null=True, blank=True,
                                      verbose_name=_('Cijena vrijedi do'))
currency          = models.CharField(max_length=3, default='EUR',
                                      verbose_name=_('Valuta'))

# ── IMOVINA / ASSET ──────────────────────────────────────────────
asset_purchase_date       = models.DateField(null=True, blank=True,
                                              verbose_name=_('Datum nabave imovine'))
asset_useful_life_years   = models.PositiveSmallIntegerField(null=True, blank=True,
                                                              verbose_name=_('Vijek trajanja (god.)'))
asset_depreciation_method = models.CharField(max_length=10, blank=True,
                                              choices=[('linear','Linearna'),('declining','Degresivna')],
                                              verbose_name=_('Metoda amortizacije'))
asset_current_value       = models.DecimalField(max_digits=14, decimal_places=2,
                                                  default=0, verbose_name=_('Sadašnja vrijednost'))
asset_location            = models.CharField(max_length=200, blank=True,
                                              verbose_name=_('Fizička lokacija imovine'))
asset_serial_number       = models.CharField(max_length=100, blank=True,
                                              verbose_name=_('Serijski broj'))
asset_inventory_number    = models.CharField(max_length=50, blank=True,
                                              verbose_name=_('Inventarni broj'))

# ── AUTORSKA PRAVA / IP ───────────────────────────────────────────
ip_author         = models.CharField(max_length=200, blank=True,
                                      verbose_name=_('Autor / nositelj prava'))
ip_valid_until    = models.DateField(null=True, blank=True,
                                      verbose_name=_('Prava vrijede do'))
ip_territory      = models.CharField(max_length=200, blank=True,
                                      verbose_name=_('Teritorijalna ograničenja'))
ip_royalty_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                         verbose_name=_('Royalty % pri prodaji'))
ip_license_type   = models.CharField(max_length=50, blank=True,
                                      choices=[
                                          ('exclusive','Ekskluzivna'),
                                          ('non_exclusive','Neekskluzivna'),
                                          ('public','Javna licenca'),
                                          ('creative_commons','Creative Commons'),
                                      ],
                                      verbose_name=_('Tip licence'))

# ── VELEPRODAJNA POSEBNOST ───────────────────────────────────────
vat_excluded_price = models.BooleanField(default=False,
                                          verbose_name=_('Cijena bez PDV-a (veleprodaja)'),
                                          help_text=_('Ako True: wholesale_price je bez PDV'))
customs_tariff    = models.CharField(max_length=15, blank=True,
                                      verbose_name=_('Carinska tarifa (HS kod)'))
country_of_origin = models.CharField(max_length=2, blank=True,
                                      verbose_name=_('Zemlja podrijetla (ISO)'))
```

### Metode koje treba dodati

```python
# U klasi InventoryItem:

def should_track_stock(self) -> bool:
    """Da li ovaj artikl ide u fizičko skladište?"""
    return self.item_class in ('tangible', 'asset')

def should_fiscalize(self) -> bool:
    """Da li ovaj artikl ide u fiskalizaciju?"""
    return self.fiscal_treatment in ('standard', 'service_cash', 'pfand')

def get_price_for_buyer(self, buyer_type: str = 'b2c', quantity: float = 1) -> dict:
    """
    Vrati ispravnu cijenu ovisno o tipu kupca.
    Returns: {'price': Decimal, 'vat_included': bool, 'price_type': str}
    """
    if buyer_type in ('b2b', 'wholesale') and self.wholesale_price > 0:
        if quantity >= float(self.min_order_qty):
            return {
                'price': self.wholesale_price,
                'vat_included': not self.vat_excluded_price,
                'price_type': 'wholesale',
            }
    return {
        'price': self.unit_price,
        'vat_included': True,
        'price_type': 'retail',
    }

def get_depreciation_this_year(self) -> float:
    """Godišnja amortizacija za imovinu."""
    if self.item_class != 'asset':
        return 0
    if not self.asset_purchase_date or not self.asset_useful_life_years:
        return 0
    if self.asset_depreciation_method == 'linear':
        return float(self.purchase_price) / self.asset_useful_life_years
    return 0

def get_royalty_amount(self, sale_price: float) -> float:
    """Iznos royalty-a za IP artikl."""
    if self.item_class != 'intangible' or self.ip_royalty_pct == 0:
        return 0
    return float(sale_price) * float(self.ip_royalty_pct) / 100

@property
def is_ip_expired(self) -> bool:
    """Da li su autorska prava/licenca istekla?"""
    if not self.ip_valid_until:
        return False
    from django.utils import timezone
    return self.ip_valid_until < timezone.now().date()

@property  
def asset_age_years(self) -> int:
    """Starost imovine u godinama."""
    if not self.asset_purchase_date:
        return 0
    from django.utils import timezone
    delta = timezone.now().date() - self.asset_purchase_date
    return delta.days // 365
```

### Migracija

```bash
venv/bin/python manage.py makemigrations inventory --name="item_class_fiscal_treatment_asset_ip"
venv/bin/python manage.py migrate inventory
venv/bin/python manage.py check
```

---

## SPRINT W1B — StockInputProcessor (Centralni ulaz)

Kreiraj `inventory/stock_input.py`:

```python
"""
inventory/stock_input.py
Centralni procesor svih ulaza u skladište.
Sve što ulazi u sustav prolazi kroz ovaj layer.

Inputi:
  - MANUAL: korisnik upisuje ručno
  - POS: blagajna (POSReceipt)
  - INVOICE: ulazna faktura (GoodsReceipt)
  - EMAIL: email ramp (SmartImport CompanyMailbox)
  - CAMERA: foto/sken dokumenta (AI vision)
  - BARCODE: sken barkoda
  - OTP: otpremnica (izlaz)
  - WEBSHOP: webshop narudžba
  - TRANSFER: međuskladišnica
  - INVENTURA: korekcija iz inventure
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List
from django.db import transaction

logger = logging.getLogger('inventory.stock_input')


@dataclass
class StockInputLine:
    """Jedna linija unosa."""
    item_id:      Optional[int] = None
    item_sku:     str = ''
    item_barcode: str = ''
    item_name:    str = ''        # Za auto-kreiranje ako ne postoji
    quantity:     Decimal = Decimal('0')
    unit_price:   Decimal = Decimal('0')
    tax_rate:     Decimal = Decimal('25')
    batch_number: str = ''
    expiry_date:  Optional[str] = None
    warehouse_id: Optional[int] = None
    notes:        str = ''


@dataclass
class StockInputDocument:
    """Dokument koji nosi više linija unosa."""
    source:          str = 'manual'   # manual/pos/invoice/email/camera/barcode/otp/webshop
    direction:       str = 'in'       # in/out/adjustment/transfer
    company_id:      int = 0
    document_ref:    str = ''         # Broj dokumenta (faktura, OTP, POS bon...)
    partner_id:      Optional[int] = None
    partner_name:    str = ''
    document_date:   Optional[str] = None
    lines:           List[StockInputLine] = field(default_factory=list)
    
    # AI metadata
    ai_confidence:   float = 100.0
    needs_review:    bool = False
    raw_data:        dict = field(default_factory=dict)


class StockInputProcessor:
    """
    Procesira StockInputDocument i kreira StockMovement zapise.
    Atomska operacija — ili sve ili ništa.
    """
    
    def process(self, doc: StockInputDocument) -> dict:
        """
        Procesira ulaz i kreira kretanje zaliha.
        Vraća: {'success': bool, 'movements': [...], 'errors': [...]}
        """
        errors = []
        movements = []
        
        with transaction.atomic():
            for line in doc.lines:
                # 1. Pronađi ili kreiraj InventoryItem
                item = self._resolve_item(line, doc.company_id, errors)
                if not item:
                    continue
                
                # 2. Provjeri treba li stock tracking
                if not item.should_track_stock():
                    logger.info(
                        'Skip stock tracking for %s (class=%s)',
                        item.name, item.item_class
                    )
                    continue
                
                # 3. Kreiraj StockMovement
                from inventory.models import StockMovement
                movement_type = self._map_direction(doc.direction, doc.source)
                
                movement = StockMovement.objects.create(
                    item=item,
                    movement_type=movement_type,
                    quantity=line.quantity,
                    unit_price=line.unit_price or item.purchase_price,
                    reference_document=doc.document_ref,
                    source=doc.source,
                    notes=f'[{doc.source.upper()}] {doc.document_ref} {line.notes}',
                    company_id=doc.company_id,
                )
                movements.append(movement)
                
                # 4. Ažuriraj količinu na artiklu
                if doc.direction == 'in':
                    item.quantity = (item.quantity or Decimal('0')) + line.quantity
                elif doc.direction == 'out':
                    item.quantity = (item.quantity or Decimal('0')) - line.quantity
                item.save(update_fields=['quantity'])
        
        return {
            'success': len(errors) == 0,
            'movements': movements,
            'errors': errors,
            'ai_confidence': doc.ai_confidence,
            'needs_review': doc.needs_review,
        }
    
    def _resolve_item(self, line, company_id, errors):
        """Pronađi InventoryItem iz linea podataka."""
        from inventory.models import InventoryItem
        
        # Pokušaj po ID
        if line.item_id:
            try:
                return InventoryItem.objects.get(pk=line.item_id, company_id=company_id)
            except InventoryItem.DoesNotExist:
                pass
        
        # Pokušaj po SKU
        if line.item_sku:
            item = InventoryItem.objects.filter(
                company_id=company_id, sku=line.item_sku
            ).first()
            if item:
                return item
        
        # Pokušaj po barkodu
        if line.item_barcode:
            item = InventoryItem.objects.filter(
                company_id=company_id, barcode=line.item_barcode
            ).first()
            if item:
                return item
        
        # Fuzzy match po imenu
        if line.item_name:
            item = InventoryItem.objects.filter(
                company_id=company_id,
                name__icontains=line.item_name[:20]
            ).first()
            if item:
                return item
        
        errors.append(f'Artikl nije pronađen: SKU={line.item_sku}, barcode={line.item_barcode}, name={line.item_name}')
        return None
    
    def _map_direction(self, direction, source):
        mapping = {
            'in':         'in',
            'out':        'out',
            'adjustment': 'adjustment',
            'transfer':   'transfer',
        }
        return mapping.get(direction, 'adjustment')


# Globalna instanca
processor = StockInputProcessor()
```

---

## SPRINT W1C — Kamera/AI unos

Kreiraj `inventory/camera_input.py`:

```python
"""
inventory/camera_input.py
AI pipeline za fizički unos robe putem kamere/slike.

Podržava:
1. Barkod/QR sken → EAN lookup
2. Foto fakture/otpremnice → Claude Haiku vision
3. Foto etikata/pakiranja → naziv + količina
"""
import base64
import logging
from typing import Optional
from inventory.stock_input import StockInputDocument, StockInputLine
from decimal import Decimal

logger = logging.getLogger('inventory.camera')


def scan_barcode_image(image_bytes: bytes) -> Optional[str]:
    """
    Skenira barkod iz slike.
    Vraća EAN/SKU string ili None.
    """
    try:
        from pyzbar.pyzbar import decode
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        results = decode(img)
        if results:
            return results[0].data.decode('utf-8')
    except ImportError:
        # pyzbar nije instaliran — fallback na AI
        pass
    except Exception as e:
        logger.warning('Barcode scan failed: %s', e)
    return None


def ai_extract_from_document(image_bytes: bytes, company_country: str = 'HR') -> StockInputDocument:
    """
    Claude Haiku vision → ekstrahira podatke iz dokumenta.
    Radi s: fakturama, otpremnicama, dostavljačkim listama.
    """
    import anthropic, os, json
    
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    b64 = base64.b64encode(image_bytes).decode()
    
    prompt = f"""Analiziraj ovaj poslovni dokument i izvuci podatke u JSON formatu.
Zemlja: {company_country}

Vrati SAMO JSON:
{{
  "document_type": "invoice|delivery_note|receipt|other",
  "document_number": "broj dokumenta",
  "document_date": "YYYY-MM-DD ili null",
  "partner_name": "naziv dobavljača/kupca",
  "partner_oib": "OIB ili null",
  "direction": "in|out",
  "lines": [
    {{
      "item_name": "naziv artikla",
      "item_sku": "SKU ili šifra ako vidljivo",
      "item_barcode": "EAN/barkod ako vidljiv",
      "quantity": 1.0,
      "unit": "kom/kg/l/m",
      "unit_price": 0.00,
      "tax_rate": 25.0,
      "batch_number": "lot/šarža ili null",
      "expiry_date": "YYYY-MM-DD ili null"
    }}
  ],
  "total": 0.00,
  "confidence": 0-100,
  "warnings": []
}}

Ako nešto nije vidljivo, stavi null. Nikad ne pogađaj OIB."""
    
    try:
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2000,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/jpeg',
                            'data': b64,
                        }
                    },
                    {'type': 'text', 'text': prompt}
                ]
            }]
        )
        
        raw = resp.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        data = json.loads(raw)
        
        doc = StockInputDocument(
            source='camera',
            direction=data.get('direction', 'in'),
            document_ref=data.get('document_number', ''),
            partner_name=data.get('partner_name', ''),
            document_date=data.get('document_date'),
            ai_confidence=float(data.get('confidence', 0)),
            needs_review=float(data.get('confidence', 0)) < 85,
            raw_data=data,
        )
        
        for line_data in data.get('lines', []):
            doc.lines.append(StockInputLine(
                item_name=line_data.get('item_name', ''),
                item_sku=line_data.get('item_sku', ''),
                item_barcode=line_data.get('item_barcode', ''),
                quantity=Decimal(str(line_data.get('quantity', 1))),
                unit_price=Decimal(str(line_data.get('unit_price', 0))),
                tax_rate=Decimal(str(line_data.get('tax_rate', 25))),
                batch_number=line_data.get('batch_number', '') or '',
                expiry_date=line_data.get('expiry_date'),
            ))
        
        logger.info('Camera scan: %d lines, confidence %.1f%%',
                    len(doc.lines), doc.ai_confidence)
        return doc
    
    except Exception as e:
        logger.error('AI camera scan failed: %s', e)
        return StockInputDocument(
            source='camera',
            direction='in',
            ai_confidence=0,
            needs_review=True,
        )


def process_camera_input(image_bytes: bytes, company_id: int, country: str = 'HR') -> dict:
    """
    Glavni entry point za kamera unos.
    1. Proba barcode scan
    2. Fallback na AI document extraction
    3. Procesira kroz StockInputProcessor
    """
    from inventory.stock_input import processor
    
    # Pokušaj barcode
    barcode = scan_barcode_image(image_bytes)
    if barcode:
        doc = StockInputDocument(
            source='barcode',
            direction='in',
            company_id=company_id,
            ai_confidence=100,
            lines=[StockInputLine(item_barcode=barcode, quantity=Decimal('1'))]
        )
        return processor.process(doc)
    
    # AI document extraction
    doc = ai_extract_from_document(image_bytes, country)
    doc.company_id = company_id
    
    if doc.needs_review:
        # Ne procesiramo automatski ako je niska pouzdanost
        return {
            'success': False,
            'needs_review': True,
            'ai_confidence': doc.ai_confidence,
            'extracted': doc,
            'message': f'AI pouzdanost {doc.ai_confidence}% — molimo potvrdite podatke'
        }
    
    return processor.process(doc)
```

### API endpoint u inventory/views.py

```python
@login_required
def api_camera_scan(request):
    """POST: image → JSON s extracted/processed stock data"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'error': 'Nema slike'}, status=400)
    
    if image_file.size > 15 * 1024 * 1024:
        return JsonResponse({'error': 'Slika prevelika (max 15MB)'}, status=400)
    
    from accounts.models import UserProfile
    try:
        up = UserProfile.objects.get(user=request.user)
        company = up.company
        country = getattr(company, 'country', 'HR') or 'HR'
    except Exception:
        return JsonResponse({'error': 'Korisnik bez firme'}, status=403)
    
    from inventory.camera_input import process_camera_input
    result = process_camera_input(image_file.read(), company.pk, country)
    
    return JsonResponse({
        'success': result.get('success', False),
        'needs_review': result.get('needs_review', False),
        'ai_confidence': result.get('ai_confidence', 0),
        'movements_created': len(result.get('movements', [])),
        'errors': result.get('errors', []),
        'message': result.get('message', ''),
    })
```

URL:
```python
path('api/camera-scan/', views.api_camera_scan, name='api_camera_scan'),
```

---

## SPRINT W1D — Veleprodaja/Maloprodaja logika

### price_engine.py

Kreiraj `inventory/price_engine.py`:

```python
"""
inventory/price_engine.py
Centralni engine za određivanje cijena.
Jedan artikl — više cjenovnih slojeva.
"""
from decimal import Decimal
from typing import Optional
from django.utils import timezone


def get_price(item, buyer_type: str = 'b2c', quantity: Decimal = Decimal('1'),
              date=None) -> dict:
    """
    Centralno mjesto za dohvat cijene.
    
    buyer_type: 'b2c' | 'b2b' | 'b2b_exempt' | 'internal'
    quantity: utječe na veleprodajni prag
    
    Returns:
        {
            'base_price': Decimal,     # Cijena bez PDV-a
            'tax_rate': Decimal,       # PDV stopa (%)
            'tax_amount': Decimal,     # Iznos PDV-a
            'total_price': Decimal,    # Ukupno s PDV-om
            'price_type': str,         # 'retail' | 'wholesale'
            'currency': str,
            'is_valid': bool,          # Da li je cijena još važeća
        }
    """
    if date is None:
        date = timezone.now().date()
    
    # Provjeri rok važenja cijene
    price_valid = True
    if item.price_valid_until and item.price_valid_until < date:
        price_valid = False
    
    # Odredi stopu PDV-a (koristi LEGAL_PARAMS_MASTER logiku)
    from invoicing.fiscal_rules import get_hr_pdv_rate
    country = getattr(item.company, 'country', 'HR') or 'HR'
    
    if country == 'HR':
        from datetime import date as date_cls
        if isinstance(date, str):
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            date_obj = date
        tax_rate_raw = get_hr_pdv_rate(date_obj, 'standard')
    else:
        tax_rate_raw = 19.0
    
    # Odabir cijene
    if buyer_type in ('b2b', 'wholesale') and item.wholesale_price > 0:
        if quantity >= item.min_order_qty:
            base_price = item.wholesale_price
            price_type = 'wholesale'
        else:
            base_price = item.unit_price
            price_type = 'retail'
    else:
        base_price = item.unit_price
        price_type = 'retail'
    
    # B2B exempt (EU B2B, nema PDV)
    if buyer_type == 'b2b_exempt':
        tax_rate = Decimal('0')
    elif item.fiscal_treatment in ('no_fiscal', 'asset', 'currency'):
        tax_rate = Decimal('0')
    else:
        tax_rate = Decimal(str(tax_rate_raw))
    
    # Ako je cijena already "retail" (s PDV-om uključenim)
    if price_type == 'retail':
        # Pretpostavljamo da je unit_price s PDV-om (= bruto)
        total_price = base_price
        tax_divisor = (Decimal('100') + tax_rate) / Decimal('100')
        base_price_net = base_price / tax_divisor if tax_rate > 0 else base_price
        tax_amount = total_price - base_price_net
    else:
        # Wholesale = bez PDV-a
        base_price_net = base_price
        tax_amount = base_price_net * tax_rate / Decimal('100')
        total_price = base_price_net + tax_amount
    
    return {
        'base_price': base_price_net.quantize(Decimal('0.01')),
        'tax_rate': tax_rate,
        'tax_amount': tax_amount.quantize(Decimal('0.01')),
        'total_price': total_price.quantize(Decimal('0.01')),
        'price_type': price_type,
        'currency': item.currency or 'EUR',
        'is_valid': price_valid,
    }
```

---

## SPRINT W1E — Amortizacija Celery Task

```python
# inventory/tasks.py — dodati:

@shared_task(name='inventory.annual_depreciation', bind=True)
def calculate_annual_depreciation(self):
    """
    Pokreće se 31.12. svake godine u 23:00.
    Izračunava amortizaciju za sve asset artikle.
    """
    from inventory.models import InventoryItem, StockMovement
    from django.utils import timezone
    import logging
    logger = logging.getLogger('inventory.depreciation')
    
    year = timezone.now().year
    assets = InventoryItem.objects.filter(
        item_class='asset',
        is_active=True,
        asset_purchase_date__isnull=False,
        asset_useful_life_years__gt=0,
    )
    
    processed = 0
    for asset in assets:
        annual_dep = asset.get_depreciation_this_year()
        if annual_dep <= 0:
            continue
        
        # Smanji sadašnju vrijednost
        new_value = float(asset.asset_current_value or asset.purchase_price) - annual_dep
        asset.asset_current_value = max(0, new_value)
        asset.save(update_fields=['asset_current_value'])
        
        # Konto knjiženje (amortizacija)
        try:
            from konto.services import book_depreciation
            book_depreciation(asset, annual_dep, year)
        except Exception as e:
            logger.warning('Depreciation booking failed for %s: %s', asset.name, e)
        
        processed += 1
    
    logger.info('Depreciation calculated for %d assets (year %d)', processed, year)
    return {'processed': processed, 'year': year}
```

Registriraj u Celery Beat:
```python
'inventory-annual-depreciation': {
    'task': 'inventory.annual_depreciation',
    'schedule': crontab(month_of_year='12', day_of_month='31', hour='23', minute='0'),
},
```

---

## DONE KRITERIJ Sprint W1

```bash
# 1. Migracija
venv/bin/python manage.py showmigrations inventory | tail -5

# 2. Nova polja
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.models import InventoryItem
item = InventoryItem.objects.first()
print('item_class:', item.item_class)
print('fiscal_treatment:', item.fiscal_treatment)
print('should_track_stock:', item.should_track_stock())
print('should_fiscalize:', item.should_fiscalize())
"

# 3. StockInputProcessor
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.stock_input import StockInputProcessor, StockInputDocument, StockInputLine
from decimal import Decimal
print('StockInputProcessor importiran OK')
"

# 4. Camera scan endpoint
curl -sI https://limit-connect.com/hr/inventory/api/camera-scan/ | head -3

# 5. Price engine
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.price_engine import get_price
from inventory.models import InventoryItem
item = InventoryItem.objects.filter(unit_price__gt=0).first()
if item:
    p = get_price(item, 'b2c')
    print('B2C price:', p)
    p2 = get_price(item, 'b2b')
    print('B2B price:', p2)
"

# 6. System check
venv/bin/python manage.py check

# 7. Commit
git log --oneline -5
```

---

## NAPOMENE

1. **Migracija safe** — sva nova polja moraju biti `null=True, blank=True` osim `item_class` i `fiscal_treatment` koji imaju default
2. **Ne mijenjaj** postojeće polje `category` — dodaješ novo `item_class` pored njega
3. **NE breakaš POS** — POSReceiptItem.inventory_item veza mora ostati netaknuta
4. **StockMovement** — provjeri stvarna polja prije pisanja koda:
   ```bash
   venv/bin/python -c "
   import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
   from inventory.models import StockMovement
   print([f.name for f in StockMovement._meta.concrete_fields])
   "
   ```
5. **pyzbar** — može biti nije instaliran. Koristiti try/except i AI fallback.
6. Commit po svakom sprintu: W1A, W1B, W1C, W1D, W1E zasebno
