# CC Task — FenixCamera: integracija u sve module + knjiga žalbi FAB

## Filozofija (čitaj prije nego kreneš)
Dva modela:
1. KONTEKSTUALNI gumb — unutar forme, tamo gdje ima smisla (udruge, fitness, worktime, partneri)
2. PLOVAJUĆA IKONA (FAB) — SAMO u POS knjizi žalbi jer je tamo kamera primarna radnja

## KORAK 0 — Obavezno pročitaj
```bash
cat /var/www/fina-connect/static/js/fenix-camera.js
grep -n "FenixCamera" /var/www/fina-connect/templates/udruge/clan_form.html | head -5
# Udruge su referentna implementacija — kopiraj pattern
```

## KORAK 1 — POS Knjiga žalbi: migriraj na FenixCamera + FAB

Pročitaj cijeli fajl:
```bash
cat /var/www/fina-connect/templates/pos/prigovori.html
```

Napravi 2 promjene:

### A) Zamijeni stari getUserMedia + handleIdFile s FenixCamera
```javascript
// MAKNI: navigator.mediaDevices.getUserMedia(...)
// MAKNI: function handleIdFile(input) { ... FileReader ... }

// DODAJ: FenixCamera.quick za svaki foto-gumb u formi
// Primjer za dokaz/prilog:
document.getElementById('idCameraBtn').onclick = function() {
  FenixCamera.quick('id-photo-preview', {
    onReady: function(r) {
      window._prigovorPhoto = r.b64;
      document.getElementById('prigovor_photo_b64').value = r.b64;
    }
  });
};
```

### B) Dodaj FAB (Floating Action Button) za hitnu žalbu
Dodaj na dno prigovori.html, IZVAN forme:
```html
<!-- Fenix Kamera FAB — samo na prigovori stranici -->
<button id="fenixCameraFAB"
  onclick="FenixCamera.quick('fab-preview',{onReady:function(r){
    document.getElementById('fab_photo_b64').value=r.b64;
    document.getElementById('fab-preview-wrap').style.display='block';
  }})"
  style="
    position:fixed; bottom:80px; right:20px; z-index:1000;
    width:56px; height:56px; border-radius:50%;
    background:#c9a84c; border:none; cursor:pointer;
    box-shadow:0 4px 12px rgba(0,0,0,.3);
    display:flex; align-items:center; justify-content:center;
    font-size:22px; color:#fff;
  "
  title="Fotografiraj za žalbu">
  📷
</button>
<div id="fab-preview-wrap" style="display:none;position:fixed;bottom:148px;right:16px;z-index:999">
  <div id="fab-preview" style="width:80px;height:80px;border-radius:8px;overflow:hidden;border:2px solid #c9a84c"></div>
</div>
<input type="hidden" id="fab_photo_b64" name="fab_photo">
```

## KORAK 2 — Fitness: dodaj kameru gdje nema

Pročitaj:
```bash
cat /var/www/fina-connect/templates/fitness/member_form.html
cat /var/www/fina-connect/templates/fitness/checkin_dashboard.html
```

### fitness/member_form.html
Dodaj kontekstualni gumb za foto člana (ispod polja za ime ili u sekciji za dokumente):
```html
<div style="margin-top:.75rem">
  <button type="button"
    onclick="FenixCamera.quick('member-photo-preview',{onReady:function(r){
      document.getElementById('member_photo_b64').value=r.b64;
    }})"
    style="background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
           color:#c9a84c;padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem">
    📷 Fotografija člana / osobna iskaznica
  </button>
  <div id="member-photo-preview" style="display:none;margin-top:.5rem"></div>
  <input type="hidden" id="member_photo_b64" name="member_photo_b64">
</div>
```

### fitness/checkin_dashboard.html
Dodaj gumb za brzi check-in skeniranjem kartice ili lica:
```html
<button type="button"
  onclick="FenixCamera.quick('checkin-scan-preview',{onReady:function(r){
    // AI analiza: prepoznaj RFID QR ili lice
    FenixCamera.analyzeWithAI(r.b64,{
      prompt:'Koji je RFID broj ili membership broj na ovoj slici? Vrati samo broj.',
      module:'fitness',
      onResult:function(txt){
        document.getElementById('rfid_input').value=txt.trim();
        document.getElementById('rfid_input').focus();
      }
    });
  }})"
  style="background:rgba(29,158,117,.15);border:1px solid rgba(29,158,117,.4);
         color:#1D9E75;padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem">
  📷 Skeniraj karticu / QR
</button>
```

## KORAK 3 — Worktime: foto za putni nalog i dokaz prisutnosti

Pročitaj:
```bash
cat /var/www/fina-connect/templates/worktime/travel_order_form.html | head -100
cat /var/www/fina-connect/templates/worktime/ts_add.html | head -60
```

### worktime/travel_order_form.html
Putni nalog mora imati foto računa/priznanice:
```html
<!-- Dodaj u sekciju za troškove/prilog: -->
<button type="button"
  onclick="FenixCamera.quick('travel-receipt-preview',{onReady:function(r){
    document.getElementById('travel_receipt_b64').value=r.b64;
  }})"
  style="background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
         color:#c9a84c;padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem">
  📷 Fotografiraj račun / prilog
</button>
<div id="travel-receipt-preview" style="margin-top:.5rem"></div>
<input type="hidden" id="travel_receipt_b64" name="receipt_photo_b64">
```

### worktime/ts_add.html
Opcionalni foto dokaz za time entry (terenska provjera prisutnosti):
```html
<!-- Dodaj kao opcioni collapse/toggle: -->
<details style="margin-top:.5rem">
  <summary style="cursor:pointer;color:var(--color-text-secondary);font-size:.85rem">
    📷 Dodaj foto dokaz (opcionalno)
  </summary>
  <div style="margin-top:.5rem">
    <button type="button"
      onclick="FenixCamera.quick('ts-photo-preview',{onReady:function(r){
        document.getElementById('ts_photo_b64').value=r.b64;
      }})"
      style="background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
             color:#c9a84c;padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem">
      📷 Fotografiraj lokaciju / dokaz
    </button>
    <div id="ts-photo-preview" style="margin-top:.5rem"></div>
    <input type="hidden" id="ts_photo_b64" name="ts_photo_b64">
  </div>
</details>
```

## KORAK 4 — Partneri: foto dokumenta / pečata

Pročitaj:
```bash
cat /var/www/fina-connect/templates/partners/partner_form.html | head -80
```

Dodaj u formu partnera (npr. ispod OIB polja):
```html
<button type="button"
  onclick="FenixCamera.quick('partner-doc-preview',{onReady:function(r){
    document.getElementById('partner_doc_b64').value=r.b64;
  }})"
  style="background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
         color:#c9a84c;padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem">
  📷 Skeniraj pečat / rješenje / dokument
</button>
<div id="partner-doc-preview" style="margin-top:.5rem"></div>
<input type="hidden" id="partner_doc_b64" name="partner_doc_b64">
```

## KORAK 5 — SW offline: dodaj fenix-camera.js u precache

U `/var/www/fina-connect/static/sw.js`, PRECACHE_URLS dodaj:
```javascript
'/static/js/fenix-camera.js',
'/static/js/worktime-offline.js',
'/static/js/fenix-permissions.js',
```

Fenix camera radi offline jer koristi samo FileReader + Canvas — nema servera.
AI analiza (analyzeWithAI) NEĆE raditi offline — to je OK, samo tiho fail.

## KORAK 6 — Collectstatic i provjera

```bash
cd /var/www/fina-connect
venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -5
# Provjeri da su svi templates promijenjeni
grep -l "FenixCamera" templates/fitness/member_form.html
grep -l "FenixCamera" templates/worktime/travel_order_form.html
grep -l "FenixCamera" templates/pos/prigovori.html
grep -l "fenixCameraFAB" templates/pos/prigovori.html
```

## Definicija DONE
- [ ] pos/prigovori.html: FAB ikona + migracija s getUserMedia na FenixCamera
- [ ] fitness/member_form.html: foto člana / iskaznica
- [ ] fitness/checkin_dashboard.html: skeniraj karticu
- [ ] worktime/travel_order_form.html: foto računa
- [ ] worktime/ts_add.html: opcioni foto dokaz
- [ ] partners/partner_form.html: foto dokumenta
- [ ] sw.js: fenix-camera.js u PRECACHE_URLS
- [ ] Collectstatic OK
- [ ] Napiši /tmp/camera_integracija_done.txt

## NAPOMENA
NE dodavaj FAB plutajuću ikonu nigdje osim prigovori.html.
U svim ostalim modulima — SAMO kontekstualni gumb unutar forme.
Pattern za kontekstualni gumb: kopiraj iz udruge/clan_form.html (linija 68).
