# CC_TASK: Stolarija Vertikala — Tjedan 1+2 (MVP koji Zdenko koristi odmah)
# Kreirao: Sonnet — 2026-04-10
# Na temelju: Gemini plana + analize postojećih modela
# Procjena: 5-7 dana
# Cilj: Zdenko Šoš može mjeriti, kreirati ponudu i poslati narudžbu u proizvodnju

---

## ŠTO POSTOJEĆE KORISTIMO (ne diraj, samo proširuj)

WorkOrder          → postaje "Nalog za ugradnju" (FSM već ima draft→in_progress→completed→invoiced)
WorkOrderItem      → stavke (materijal + rad) — bom_deducted flag već postoji
BOM / BOMItem      → sastavnica (calculator app)
ProductionOrder    → narudžba u proizvodnju (production app)
Partner            → Zdenkovi kupci
InventoryItem      → profili, staklo, okovi
Invoice            → završni račun (auto iz WorkOrder)

---

## NOVI APP: `stolarija`

```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp stolarija
# Dodaj 'stolarija' u INSTALLED_APPS (core/settings.py)
```

---

## KORAK 1: Modeli (stolarija/models.py)

PROČITAJ SVE PRIJE PISANJA. Provjeri stvarna polja WorkOrder i InventoryItem prije FK-ova.

```python
from django.db import models
from django.contrib.auth.models import User


class WindowProfile(models.Model):
    """Katalog profila — jednom definiraš, zauvijek koristiš."""
    company     = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name        = models.CharField(max_length=100)      # npr. "Schüco AWS 75"
    system      = models.CharField(max_length=100, blank=True)  # Schüco, Rehau, Veka...
    material    = models.CharField(max_length=10,
                    choices=[('alu','Aluminij'),('pvc','PVC'),('wood','Drvo')],
                    default='alu')
    color_outer = models.CharField(max_length=50, blank=True)   # RAL 7016
    color_inner = models.CharField(max_length=50, blank=True)
    price_per_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['material', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_material_display()})"


class GlassType(models.Model):
    """Katalog stakla."""
    company      = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name         = models.CharField(max_length=100)    # npr. "4/16/4 Argon Ug=1.1"
    u_value      = models.DecimalField(max_digits=4, decimal_places=2, default=1.1)
    price_per_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active    = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Measurement(models.Model):
    """
    Centralni model — sve počinje ovdje.
    Zdenko na terenu mjeri i unosi (glas ili ručno).
    Jedan Measurement = jedan otvor (prozor/vrata/komarnik).
    """
    ELEMENT_TYPES = [
        ('window',   'Prozor'),
        ('door',     'Vrata'),
        ('mosquito', 'Komarnik'),
        ('facade',   'Fasadna stijena'),
        ('other',    'Ostalo'),
    ]
    WING_CONFIGS = [
        ('fixed',    'Fiksno'),
        ('single',   'Jednokrilno'),
        ('double',   'Dvokrilno'),
        ('triple',   'Trokrilno'),
        ('sliding',  'Klizno'),
        ('tilt_turn','Kip-turn'),
    ]

    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    work_order    = models.ForeignKey(
        'work_orders.WorkOrder', on_delete=models.CASCADE,
        related_name='measurements', null=True, blank=True
    )
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    # Lokacija otvora
    location_note = models.CharField(max_length=200, blank=True)  # "Spavaća soba, sjever"
    floor         = models.SmallIntegerField(default=0)            # 0=prizemlje

    # Dimenzije (mm)
    width_mm      = models.PositiveIntegerField()
    height_mm     = models.PositiveIntegerField()
    depth_mm      = models.PositiveIntegerField(default=0, blank=True)  # dubina zida

    # Tip i konfiguracija
    element_type  = models.CharField(max_length=20, choices=ELEMENT_TYPES, default='window')
    wing_config   = models.CharField(max_length=20, choices=WING_CONFIGS, default='double')
    quantity      = models.PositiveSmallIntegerField(default=1)

    # Materijal
    profile       = models.ForeignKey(WindowProfile, on_delete=models.SET_NULL,
                                       null=True, blank=True)
    glass         = models.ForeignKey(GlassType, on_delete=models.SET_NULL,
                                       null=True, blank=True)

    # Voice input — surovi tekst koji je AI parsirao
    voice_raw     = models.TextField(blank=True)  # "sto dvadeset puta sto četrdeset bijeli dvokrilni"
    ai_parsed     = models.JSONField(default=dict, blank=True)  # što je AI izvukao
    confirmed     = models.BooleanField(default=False)  # Zdenko potvrdio dimenzije

    # Foto dokumentacija
    photo_before  = models.ImageField(upload_to='stolarija/photos/', null=True, blank=True)
    photo_after   = models.ImageField(upload_to='stolarija/photos/', null=True, blank=True)

    # Izračunata površina
    @property
    def area_m2(self):
        return round((self.width_mm * self.height_mm) / 1_000_000, 3)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_element_type_display()} {self.width_mm}×{self.height_mm}mm × {self.quantity}kom"


class WindowOffer(models.Model):
    """
    Ponuda — generira se iz skupa Measurement zapisa.
    PDF + e-potpis kupca.
    """
    STATUS = [
        ('draft',    'Nacrt'),
        ('sent',     'Poslana'),
        ('accepted', 'Prihvaćena'),
        ('rejected', 'Odbijena'),
        ('expired',  'Istekla'),
    ]

    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    work_order    = models.ForeignKey('work_orders.WorkOrder', on_delete=models.CASCADE,
                                       related_name='window_offers')
    offer_number  = models.CharField(max_length=20, blank=True)
    status        = models.CharField(max_length=20, choices=STATUS, default='draft')

    valid_days    = models.PositiveSmallIntegerField(default=30)
    created_at    = models.DateTimeField(auto_now_add=True)
    sent_at       = models.DateTimeField(null=True, blank=True)
    accepted_at   = models.DateTimeField(null=True, blank=True)

    # Financije
    total_net     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_vat     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gross   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_pct   = models.SmallIntegerField(default=30)  # % avansa

    # E-potpis
    client_signature = models.TextField(blank=True)  # base64 SVG potpis
    signed_at        = models.DateTimeField(null=True, blank=True)
    signed_by_name   = models.CharField(max_length=100, blank=True)

    notes         = models.TextField(blank=True)

    def __str__(self):
        return f"Ponuda {self.offer_number} — {self.work_order}"


class WindowWarranty(models.Model):
    """
    Garancija — generira se nakon primopredaje.
    QR kod → kupac vidi status, sljedeći servis.
    GEMINIJEV SAVJET: servis nije uvjet za garanciju, nego "osvježenje" — podmazivanje, podešavanje.
    """
    work_order     = models.OneToOneField('work_orders.WorkOrder', on_delete=models.CASCADE,
                                           related_name='warranty')
    warranty_number = models.CharField(max_length=30, unique=True)
    issued_at      = models.DateTimeField(auto_now_add=True)
    valid_years    = models.SmallIntegerField(default=5)
    qr_token       = models.CharField(max_length=40, unique=True, blank=True)

    # Primopredaja
    handover_date  = models.DateField(null=True, blank=True)
    handover_notes = models.TextField(blank=True)
    handover_photo = models.ImageField(upload_to='stolarija/handover/', null=True, blank=True)
    client_signature = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.qr_token:
            import secrets
            self.qr_token = secrets.token_urlsafe(20)
        super().save(*args, **kwargs)

    @property
    def next_service_date(self):
        if self.handover_date:
            from datetime import timedelta
            return self.handover_date.replace(year=self.handover_date.year + 1)
        return None

    def __str__(self):
        return f"Garancija {self.warranty_number}"


class ServiceVisit(models.Model):
    """Godišnji servisni pregled — podmazivanje, podešavanje."""
    warranty   = models.ForeignKey(WindowWarranty, on_delete=models.CASCADE,
                                    related_name='service_visits')
    scheduled  = models.DateField()
    completed  = models.DateField(null=True, blank=True)
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes      = models.TextField(blank=True)
    photo      = models.ImageField(upload_to='stolarija/service/', null=True, blank=True)
    cost       = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"Servis {self.scheduled} — {self.warranty}"
```

---

## KORAK 2: Voice-to-Form parser (stolarija/voice_parser.py)

```python
"""
Glasovni unos → strukturirani podaci.
GEMINIJEV SAVJET: Zdenko MORA vizualno potvrditi dimenzije prije Spremi.
"""
import re
import json


# Rječnik glasovnih zamjena (HR govor → broj)
WORD_TO_NUM = {
    'sto': 100, 'dvjesto': 200, 'tristo': 300, 'četiristo': 400,
    'petsto': 500, 'šesto': 600, 'sedamsto': 700, 'osamsto': 800, 'devetsto': 900,
    'trideset': 30, 'četrdeset': 40, 'pedeset': 50, 'šezdeset': 60,
    'sedamdeset': 70, 'osamdeset': 80, 'devedeset': 90,
    'deset': 10, 'dvadeset': 20, 'jedanaest': 11, 'dvanaest': 12,
    'nula': 0, 'jedan': 1, 'dva': 2, 'tri': 3, 'četiri': 4,
    'pet': 5, 'šest': 6, 'sedam': 7, 'osam': 8, 'devet': 9,
}

ELEMENT_KEYWORDS = {
    'prozor': 'window', 'vrata': 'door', 'balkonska': 'door',
    'komarnik': 'mosquito', 'mreža': 'mosquito',
}
WING_KEYWORDS = {
    'jednokrilni': 'single', 'dvokrilni': 'double', 'trokrilni': 'triple',
    'fiksni': 'fixed', 'klizni': 'sliding', 'kip': 'tilt_turn',
}
COLOR_KEYWORDS = ['bijeli', 'sivi', 'crni', 'antracit', 'zlatni', 'smeđi', 'boja']


def parse_voice_input(text: str) -> dict:
    """
    Ulaz:  "prozor sto dvadeset puta sto četrdeset bijeli dvokrilni dva komada"
    Izlaz: {
        'element_type': 'window',
        'width_mm': 1200,
        'height_mm': 1400,
        'wing_config': 'double',
        'quantity': 2,
        'color_hint': 'bijeli',
        'confidence': 0.85,
        'raw': '...',
        'warnings': []
    }
    """
    text_lower = text.lower().strip()
    result = {
        'raw': text,
        'element_type': 'window',
        'width_mm': None,
        'height_mm': None,
        'wing_config': 'double',
        'quantity': 1,
        'color_hint': '',
        'confidence': 0.0,
        'warnings': [],
    }

    # Tip elementa
    for kw, val in ELEMENT_KEYWORDS.items():
        if kw in text_lower:
            result['element_type'] = val
            break

    # Konfiguracija krila
    for kw, val in WING_KEYWORDS.items():
        if kw in text_lower:
            result['wing_config'] = val
            break

    # Boja
    for c in COLOR_KEYWORDS:
        if c in text_lower:
            result['color_hint'] = c
            break

    # Dimenzije — traži "X puta Y" ili "X×Y" ili "XxY"
    # Prvo pokušaj direktne brojeve
    dim_match = re.search(r'(\d{2,4})\s*[xX×puta]+\s*(\d{2,4})', text_lower)
    if dim_match:
        result['width_mm'] = int(dim_match.group(1))
        result['height_mm'] = int(dim_match.group(2))
    else:
        # Pokušaj word-to-num konverziju
        normalized = text_lower
        for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: -len(x[0])):
            normalized = normalized.replace(word, f' {num} ')

        nums = re.findall(r'\b(\d{2,4})\b', normalized)
        if len(nums) >= 2:
            result['width_mm'] = int(nums[0])
            result['height_mm'] = int(nums[1])

    # Količina
    qty_match = re.search(r'(\d+)\s*(kom|komad|komada|kos|piece)', text_lower)
    if qty_match:
        result['quantity'] = int(qty_match.group(1))

    # Validacija i confidence
    warnings = []
    confidence = 0.5

    if result['width_mm'] and result['height_mm']:
        confidence += 0.3
        # Upozorenja za nelogične dimenzije
        if result['width_mm'] < 300 or result['width_mm'] > 5000:
            warnings.append(f"Neobična širina: {result['width_mm']}mm — provjeri!")
        if result['height_mm'] < 300 or result['height_mm'] > 4000:
            warnings.append(f"Neobična visina: {result['height_mm']}mm — provjeri!")
        if result['width_mm'] == result['height_mm']:
            warnings.append("Širina = visina — kvadrat, je li ispravno?")
    else:
        warnings.append("Dimenzije nisu prepoznate — unesi ručno")
        confidence -= 0.2

    if result['element_type'] != 'window':
        confidence += 0.1

    result['confidence'] = round(min(max(confidence, 0), 1.0), 2)
    result['warnings'] = warnings

    return result
```

---

## KORAK 3: Views — Mobile-first unos (stolarija/views.py)

Tri ključna viewa za Tjedan 1:

### 3a. Mjerenje (voice + manual)
```
GET  /stolarija/mjeri/<work_order_id>/    → forma za unos
POST /stolarija/mjeri/<work_order_id>/    → spremi Measurement
POST /stolarija/voice-parse/              → JSON API: {text} → {parsed_data}
```

### 3b. Pregled svih mjerenja jednog naloga
```
GET /stolarija/nalog/<work_order_id>/measurements/
```

### 3c. Generiranje ponude iz mjerenja
```
POST /stolarija/nalog/<work_order_id>/ponuda/generate/
GET  /stolarija/ponuda/<offer_id>/
GET  /stolarija/ponuda/<offer_id>/pdf/
```

IMPLEMENTIRAJ OVE 3 VIEWA. Ostalo (garancija, servis, kupac portal) dolazi u Tjedan 3.

---

## KORAK 4: Template — Mjerenje (mobile-first)

`stolarija/templates/stolarija/mjeri.html`

KRITIČNO (Geminijev savjet): Nakon voice inputa, MORA se prikazati veliki vizualni potvrdi:
```
┌─────────────────────────────────────┐
│  PROVJERI DIMENZIJE:                │
│                                     │
│  ████  1200 mm  ████                │
│   ×                                 │
│  ████  1400 mm  ████                │
│                                     │
│  Dvokrilni prozor × 2 kom           │
│                                     │
│  [✓ TOČNO — SPREMI]  [✗ ISPRAVI]   │
└─────────────────────────────────────┘
```
Korisnik MORA kliknuti "TOČNO" da bi se Measurement.confirmed = True.
Ako nije potvrdio → ne može generirati ponudu.

---

## KORAK 5: Voice API endpoint

```python
# stolarija/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
from .voice_parser import parse_voice_input

@login_required
@require_POST
def voice_parse_api(request):
    """
    POST /stolarija/voice-parse/
    Body: {"text": "prozor sto dvadeset puta sto četrdeset bijeli dvokrilni"}
    Response: {"parsed": {...}, "warnings": [...], "confidence": 0.85}
    """
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        if not text:
            return JsonResponse({'error': 'Nema teksta'}, status=400)

        parsed = parse_voice_input(text)
        return JsonResponse({
            'parsed': parsed,
            'warnings': parsed['warnings'],
            'confidence': parsed['confidence'],
            'display': {
                'width': f"{parsed['width_mm']} mm" if parsed['width_mm'] else '?',
                'height': f"{parsed['height_mm']} mm" if parsed['height_mm'] else '?',
                'type': parsed['element_type'],
                'qty': parsed['quantity'],
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

---

## KORAK 6: URLs (stolarija/urls.py)

```python
from django.urls import path
from . import views

app_name = 'stolarija'

urlpatterns = [
    path('mjeri/<int:work_order_id>/', views.measurement_view, name='mjeri'),
    path('voice-parse/', views.voice_parse_api, name='voice_parse'),
    path('nalog/<int:work_order_id>/measurements/', views.measurements_list, name='measurements'),
    path('nalog/<int:work_order_id>/ponuda/generate/', views.generate_offer, name='gen_offer'),
    path('ponuda/<int:offer_id>/', views.offer_detail, name='offer_detail'),
    path('ponuda/<int:offer_id>/pdf/', views.offer_pdf, name='offer_pdf'),
    # Kupac portal (Tjedan 3)
    # path('garancija/<str:qr_token>/', views.warranty_portal, name='warranty_portal'),
]
```

Dodaj u `core/urls.py`:
```python
path('stolarija/', include('stolarija.urls', namespace='stolarija')),
```

---

## KORAK 7: Migracija i test

```bash
venv/bin/python manage.py makemigrations stolarija
venv/bin/python manage.py migrate stolarija

# Test voice parsera
venv/bin/python manage.py shell -c "
from stolarija.voice_parser import parse_voice_input
tests = [
    'prozor sto dvadeset puta sto četrdeset bijeli dvokrilni dva komada',
    'vrata 900x2100 antracit jednokrilna',
    '120 puta 140 prozor',
    'komarnik 80x120 jedan komad',
]
for t in tests:
    r = parse_voice_input(t)
    print(f'IN:  {t}')
    print(f'OUT: {r[\"width_mm\"]}×{r[\"height_mm\"]}mm | {r[\"element_type\"]} | qty={r[\"quantity\"]} | conf={r[\"confidence\"]}')
    if r[\"warnings\"]: print(f'WARN: {r[\"warnings\"]}')
    print()
"
```

---

## KORAK 8: Admin (stolarija/admin.py)

```python
from django.contrib import admin
from .models import WindowProfile, GlassType, Measurement, WindowOffer, WindowWarranty, ServiceVisit

@admin.register(WindowProfile)
class WindowProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'system', 'material', 'price_per_m2', 'is_active']
    list_filter = ['material', 'is_active']

@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'element_type', 'wing_config', 'confirmed', 'created_at']
    list_filter = ['element_type', 'confirmed']
    readonly_fields = ['voice_raw', 'ai_parsed']

@admin.register(WindowOffer)
class WindowOfferAdmin(admin.ModelAdmin):
    list_display = ['offer_number', 'work_order', 'status', 'total_gross', 'created_at']
    list_filter = ['status']

@admin.register(WindowWarranty)
class WindowWarrantyAdmin(admin.ModelAdmin):
    list_display = ['warranty_number', 'work_order', 'issued_at', 'valid_years', 'next_service_date']
```

---

## KORAK 9: Git commit

```bash
git add stolarija/
git add core/urls.py core/settings.py
git commit -m "feat: stolarija vertikala — Tjedan 1

- Nov app stolarija: WindowProfile, GlassType, Measurement, WindowOffer, WindowWarranty, ServiceVisit
- Voice parser (HR govor → dimenzije) s confidence scorom i upozorenjima
- Obavezna vizualna potvrda dimenzija (Gemini sigurnosni ventil)
- Voice API endpoint /stolarija/voice-parse/
- Mobile-first: Zdenko mjeri na terenu, gleda i potvrđuje na velikom ekranu
- Koristi postojeće: WorkOrder, Partner, InventoryItem, Invoice"
```

---

## TJEDAN 2 (sljedeće — ne sad)
- PDF ponuda (WeasyPrint — već imamo)
- E-potpis kupca (canvas signature)
- WhatsApp slanje ponude (WAHA — već imamo)
- Auto-BOM generiranje iz Measurement → ProductionOrder

## TJEDAN 3+
- Kupac portal (/garancija/<qr_token>/)
- Servisni podsjetnici (Celery + WhatsApp)
- Vizualizator konfiguracije (SVG preview prozora)

## ZABRANJENA ZONA
- Ne diraj WorkOrder FSM (transitions)
- Ne diraj base.html
- Ne diraj core/settings.py osim INSTALLED_APPS + URL include
