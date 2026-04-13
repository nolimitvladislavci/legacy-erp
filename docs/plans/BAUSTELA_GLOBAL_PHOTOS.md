# BAUSTELA / GLOBAL PHOTOS — ENGINEERING PLAN

**Datum:** 2026-04-13
**Cilj:** Globalni foto modul — sve slike firme na jednom mjestu
**Princip:** PROŠIRI ArhivaEntry, NE kreiraj novi app
**Standard:** 10/10, EU #1

---

## PROBLEM

60+ ImageField/FileField u 25+ appova. Svaki app ima:
- Svoju upload putanju (stolarija/photos/, delivery/photos/, site_photos/...)
- Svoju logiku (neki imaju GPS, većina nema)
- Svoj audit (neki koriste BookingSignature, većina ništa)
- NULA cross-app povezanosti

Rezultat: Zdenko slika na terenu stolariju, ali ne vidi delivery slike za istog kupca.

## RJEŠENJE

Proširiti `documents.ArhivaEntry` s foto/GPS/source poljem.
ArhivaEntry VEĆ IMA: company, source_type, source_id, file_path, has_image,
integrity_hash, deletion_protected_until, audit log, barcode, labels.

### Nova polja na ArhivaEntry:

```python
# GPS / Lokacija
latitude           = FloatField(null=True, blank=True)
longitude          = FloatField(null=True, blank=True)
address            = CharField(max_length=500, blank=True)

# Cross-app source tracking
source_app         = CharField(max_length=50, blank=True, db_index=True)
source_model       = CharField(max_length=100, blank=True)
source_object_id   = PositiveIntegerField(null=True, blank=True)

# Photo metadata
tags               = JSONField(default=list, blank=True)
thumbnail_path     = CharField(max_length=500, blank=True)
captured_at        = DateTimeField(null=True, blank=True)
captured_by        = FK(User, null=True, blank=True, related_name='captured_photos')

# Content type classification
content_category   = CharField(max_length=30, choices=CONTENT_CATEGORIES, default='document')
```

### Novi SOURCE_TYPES:

```python
('site_photo',       'Fotografija s terena'),
('before_photo',     'Stanje prije'),
('after_photo',      'Stanje poslije'),
('delivery_proof',   'Dokaz dostave'),
('transport_photo',  'Transport'),
('return_photo',     'Povrat'),
('qc_photo',         'Kontrola kvalitete'),
('receipt_scan',     'Sken računa'),
('document_scan',    'Sken dokumenta'),
('complaint_photo',  'Reklamacija'),
('inventory_photo',  'Inventura'),
('meter_reading',    'Očitanje brojila'),
('animal_photo',     'Životinja'),
('profile_photo',    'Profilna slika'),
```

### CONTENT_CATEGORIES:

```python
('document',    'Dokument'),
('photo',       'Fotografija'),
('scan',        'Sken'),
('signature',   'Potpis'),
('certificate', 'Certifikat'),
('receipt',     'Račun'),
```

---

## ARHITEKTURA

```
App (stolarija, delivery, worktime...)
  |
  | ImageField.save() → post_save signal
  |    ili
  | archive_photo() explicit call
  ↓
documents.photo_registry.archive_photo(
    company=...,
    file_path=...,
    source_type='site_photo',
    source_app='stolarija',
    source_model='InstallationChecklist',
    source_object_id=42,
    latitude=45.123,
    longitude=15.456,
    captured_by=user,
    tags=['teren', 'ugradnja', 'prije'],
)
  ↓
ArhivaEntry.objects.create(...)
  + auto thumbnail (200px)
  + auto EXIF GPS extract
  + auto integrity_hash
  + auto deletion_protected_until (11 god)
  + ArhivaAuditLog (CREATED)
  ↓
Globalni "Baustela" dashboard
  - Timeline (kronološki)
  - GPS Mapa (Leaflet + OpenStreetMap)
  - Galerija grid (thumbnail)
  - Filteri: app, tip, datum, adresa, korisnik
  - Cross-app: sve slike za istu adresu/partnera
```

---

## FAZE IMPLEMENTACIJE

### FAZA 1: Migracija (30 min)
- Nova polja na ArhivaEntry
- Novi SOURCE_TYPES + CONTENT_CATEGORIES
- `documents/migrations/00XX_photo_registry.py`
- `python manage.py migrate`

### FAZA 2: Photo Registry Service (45 min)
- `documents/photo_registry.py` — archive_photo() funkcija
- Auto EXIF GPS extraction (Pillow)
- Auto thumbnail generation (200px max)
- Auto integrity hash
- Idempotent (duplikat check po file_hash + source)

### FAZA 3: Retrofit postojeće appove (45 min)
- Stolarija: post_save na Measurement, InstallationOrder, InstallationChecklist, WindowWarranty, ServiceVisit, ServiceMessage
- Delivery: post_save na DeliveryStop, ConsolidatedDelivery, PackagingExchange
- Worktime: post_save na ProjectPhoto
- Production: post_save na QualityCheck
- Assessment: post_save na AssessmentPhoto

### FAZA 4: Baustela Dashboard (60 min)
- `documents/views_photos.py` — gallery_dashboard view
- `documents/templates/documents/photo_gallery.html`
- Timeline view (kronološki, lazy load)
- Galerija grid (responsive, lightbox)
- GPS Mapa (Leaflet.js + OpenStreetMap — besplatno, bez API ključa)
- Filteri: source_app, source_type, date range, address search, user
- URL: /hr/arhiva/galerija/

### FAZA 5: Reusable Camera Widget (30 min)
- `templates/includes/_camera_capture.html`
- GPS auto-tag (navigator.geolocation)
- EXIF preserve
- Preview before upload
- AJAX upload to archive_photo API endpoint
- Zamjena za per-app camera code (stolarija, delivery, livestock)

### FAZA 6: Deploy + Test (15 min)
- Django check
- Restart gunicorn
- Commit
- Test galerija s postojećim slikama

---

## KLJUČNE ODLUKE

1. **NE kreiraj novi app** — proširi documents
2. **NE dupliciraj slike** — ArhivaEntry referencira isti file_path, ne kopira
3. **NE mijenjaj postojeće modele** — samo dodaj signal koji kreira ArhivaEntry
4. **Thumbnail ODVOJENO** — ne mijenjaj original, kreiraj thumbnail u arhiva/thumbs/
5. **GPS iz EXIF-a** — Pillow čita GPS tagove iz JPEG-a, ne treba client-side
6. **Leaflet.js** — besplatno, OpenStreetMap, bez API ključa
7. **Retroaktivno** — management command za arhiviranje postojećih slika

---

## FAJLOVI KOJI SE MIJENJAJU

| Fajl | Promjena |
|---|---|
| documents/models.py | +15 polja na ArhivaEntry, +14 SOURCE_TYPES |
| documents/migrations/00XX.py | Nova migracija |
| documents/photo_registry.py | NOVO — archive_photo() service |
| documents/views_photos.py | NOVO — gallery dashboard |
| documents/urls.py | +2 URL-a (galerija, API upload) |
| documents/templates/documents/photo_gallery.html | NOVO — galerija template |
| templates/includes/_camera_capture.html | NOVO — reusable camera widget |
| stolarija/signals.py | NOVO — post_save hookovi |
| delivery/signals.py | NOVO — post_save hookovi |
| worktime/signals.py | NOVO — post_save hookovi |

## NE MIJENJAJU SE

- Postojeći modeli (Measurement, DeliveryStop, ProjectPhoto...) — OSTAJU KAO JESU
- Postojeći upload putanje — OSTAJU
- Postojeći views — OSTAJU
- Postojeći templates — OSTAJU (osim opcionalnog include _camera_capture)
