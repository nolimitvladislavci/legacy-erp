# Transport Modul — Kompletna Analiza i Preporuka
## Datum: 21.03.2026.

---

## 1. TRENUTNO STANJE — Što imamo

### Delivery modul (1.219 linija, 18 modela) — 70% gotov
| Model | Status | Što radi |
|-------|--------|----------|
| Vehicle | ✅ | plate, type, cold_chain, GPS, senzor |
| DeliveryRoute | ✅ | datum, vozilo, vozač, status, GPS tracking |
| DeliveryStop | ✅ | pickup/delivery, potpis, foto, temp na primopredaji |
| ConsolidatedDelivery | ✅ | Hub cross-docking, multi-order, cold chain |
| SmartBox | ✅ | Termo kutije sa senzorom, HACCP status |
| SensorReading | ✅ | Temp+GPS očitanja, auto-alert |
| HACCPIncident | ✅ | EU 852/2004 sustav, 3 tipa detekcije |
| ColdChainZone | ✅ | Zone u hladnjači s pragovima |
| TemperatureLog | ✅ | Per-vehicle temp tracking |
| DeliveryTracking | ✅ | GPS pozicije vozila u realnom vremenu |
| Rollwagen | ✅ | LIFO utovar, QR skeniranje |
| PackagingExchange | ✅ | IFCO, euro palete, evidencija |
| TransportHandoff | ✅ | HACCP primopredaja s checklistom |
| DispatchOffer | ✅ | Dispatch za taxi/crowd vozače |
| PickWave + PickTask | ✅ | Warehouse picking |
| DeliveryZone | ✅ | Zone dostave s cijenama |
| DeliveryCostRule | ✅ | Izračun troška dostave |

### Tracking modul (115 linija) — 60% gotov
| Model | Status | Što radi |
|-------|--------|----------|
| TrackedItem | ✅ | Generički tracker s public token |
| TrackingStatus | ✅ | Status definicije po tipu |
| TrackingEvent | ✅ | Event log za svaki status change |

### Documents — CMR
| Model | Status | Što radi |
|-------|--------|----------|
| CMR | ✅ | Sender, receiver, carrier, plate, temp_regime, customs |
| CMRItem | ✅ | Roba, pakiranje, bruto kg, m³ |
| Otpremnica | ✅ | Vehicle plate, driver, delivery address |

### POS — Terenske smjene
| Polje | Status |
|-------|--------|
| POSSession.is_field_session | ✅ |
| POSSession.vehicle_plate | ✅ |
| POSSession.route_name | ✅ |

### ColdChainService (delivery/services/cold_chain.py)
- ingest_reading() — IoT ping
- bulk_ingest() — offline sync
- check_delivery_haccp() — status provjera
- block_goods_receipt() — blokada primke
- get_fleet_status() — dashboard

---

## 2. ŠTO FALI — Gap analiza

### A) Za TERMO KUTIJE (hrana po HR, do 48h):
| Element | Status | Prioritet |
|---------|--------|-----------|
| ATP certifikat evidencija | ❌ | VISOKO — zakonski |
| Temperatura na CMR-u | ✅ temp_regime | OK |
| SmartBox ↔ DeliveryRoute veza | ⚠️ djelomično | SREDNJE |
| Automatski HACCP izvještaj za kupca | ❌ | VISOKO |
| Real-time tracking za kupca | ✅ public token | OK |
| Vozačev mobilni dashboard | ✅ driver_pwa | OK |
| Automatski CMR iz narudžbe | ❌ | VISOKO |

### B) Za KOMBI PRIJEVOZ (DE↔HR↔BA↔RS):
| Element | Status | Prioritet |
|---------|--------|-----------|
| Licenca Zajednice (EU) evidencija | ❌ | KRITIČNO |
| Potvrda za vozače (treće zemlje) | ❌ | KRITIČNO za BA/RS vozače |
| Izjava o upućivanju radnika (posting) | ❌ | OBAVEZNO za DE |
| CMR generiranje iz narudžbe | ❌ | VISOKO |
| Tahograf evidencija (vremena vožnje) | ❌ | ZAKONSKI |
| Carinski dokumenti (T1/T2 za BA/RS) | ⚠️ customs_status postoji | DJELOMIČNO |
| Osiguranje tereta (CMR osiguranje) | ❌ | PREPORUČENO |
| Kabotagža provjera (max 3 u 7 dana) | ❌ | ZAKONSKI u EU |
| Multi-country routing (HR→BA→RS→DE) | ❌ | VISOKO |
| Trošak goriva / kilometraža | ❌ | OPERATIVNO |

### C) Za OBA SCENARIJA:
| Element | Status | Prioritet |
|---------|--------|-----------|
| Vehicle ↔ CMR automatska veza | ❌ | VISOKO |
| Driver app (PWA) kompletni | ⚠️ započeto | SREDNJE |
| Fleet management dashboard | ❌ | VISOKO |
| Održavanje vozila (servis, registracija) | ❌ | SREDNJE |
| Fuel tracking | ❌ | OPERATIVNO |
| Nalog za prijevoz (transport order) | ❌ | VISOKO |

---

## 3. ZAKONSKI ZAHTJEVI — Kompletna lista

### Za TEMPERATURN PRIJEVOZ (hrana):
1. **ATP certifikat** — vozilo mora imati ATP potvrdu (Centar za vozila HR)
   - Vrijedi 6 godina (novo) ili 3 godine (obnovljeno)
   - Klase: FNA (normalno hlađenje), FRC (pojačano hlađenje)
2. **HACCP plan** — EU 852/2004 + HR NN 81/13
3. **Evidencija temperature** — neprekidna, s dokazom za kupca
4. **CMR** — ako je međunarodni prijevoz
5. **Otpremnica** — za domaći prijevoz

### Za KOMBI PRIJEVOZ (međunarodni):
1. **Licenca Zajednice** — obavezna za EU prijevoz tereta
   - Izdaje: Ministarstvo mora, prometa i infrastrukture
   - Kopija u svakom vozilu
   - Financijski kapacitet: 1.800€ (prvo vozilo >2.5t) + 900€ (svako sljedeće)
2. **Potvrda za vozače** — ako vozač NIJE iz EU (BA, RS, ME...)
3. **CMR tovarni list** — 4 primjerka, potpisi pošiljatelja + prijevoznika + primatelja
4. **Izjava o upućivanju radnika** (Posting Declaration) — za rad u DE
   - Prijava na IMI sustav (Internal Market Information)
5. **Tahograf** — digitalni, obvezna evidencija:
   - Max 9h vožnje/dan (iznimno 10h, 2x tjedno)
   - Min 45 min pauze nakon 4.5h
   - Min 11h dnevni odmor
6. **Carinski dokumenti** — za BA/RS (izvan EU):
   - T1 dokument (tranzitna roba)
   - Carinska deklaracija
   - EUR.1 ili izjava o podrijetlu
7. **CMR osiguranje** — osiguranje prijevoznikove odgovornosti
8. **Kabotaža** — max 3 kabotažne operacije u 7 dana unutar jedne EU države

---

## 4. PREPORUČENI NOVI MODELI

### TransportOrder (Nalog za prijevoz)
```python
class TransportOrder(models.Model):
    """Centralni nalog — spaja sve: vozilo, vozač, ruta, CMR, HACCP."""
    company = FK(Company)
    order_number = CharField (auto: TO-2026-0001)

    # Tip
    transport_type = CharField: 'food_local', 'food_international',
                     'freight_eu', 'freight_non_eu', 'moving'

    # Relacija
    vehicle = FK(Vehicle)
    driver = FK(User)
    route = FK(DeliveryRoute, nullable)
    consolidated_delivery = FK(ConsolidatedDelivery, nullable)

    # Ruta
    origin_address = CharField
    origin_country = CharField (HR/DE/BA/RS/AT/SI)
    destination_address = CharField
    destination_country = CharField
    via_countries = JSONField  # ['AT','HU'] — tranzitne države

    # Datumi
    planned_departure = DateTimeField
    planned_arrival = DateTimeField
    actual_departure = DateTimeField (nullable)
    actual_arrival = DateTimeField (nullable)

    # Dokumenti (auto-generirani)
    cmr = FK(CMR, nullable)
    otpremnica = FK(Otpremnica, nullable)

    # Status
    status = CharField: 'draft', 'planned', 'loading', 'in_transit',
             'border_crossing', 'unloading', 'delivered', 'cancelled'

    # Temperatura
    requires_cold_chain = BooleanField
    temp_min = Decimal (nullable)
    temp_max = Decimal (nullable)
    smart_boxes = M2M(SmartBox)

    # Financije
    estimated_km = Decimal
    fuel_cost = Decimal
    toll_cost = Decimal
    total_cost = Decimal
    client_price = Decimal  # što naplaćujemo

    # Licence / dokumenti provjera
    licence_verified = BooleanField  # Licenca Zajednice provjerena
    driver_cert_verified = BooleanField  # Potvrda za vozača
    posting_declared = BooleanField  # Izjava o upućivanju (za DE)
    atp_valid = BooleanField  # ATP certifikat valjan
    customs_docs_ready = BooleanField  # Carinski dokumenti (za BA/RS)
```

### VehicleDocument (Dokumenti vozila)
```python
class VehicleDocument(models.Model):
    """Dokumenti vozila — registracija, ATP, osiguranje, servis."""
    vehicle = FK(Vehicle)
    doc_type = CharField: 'registration', 'atp_certificate', 'insurance',
               'casco', 'cmr_insurance', 'technical_inspection', 'tachograph_calibration'
    doc_number = CharField
    valid_from = DateField
    valid_until = DateField
    file = FileField
    reminder_days = IntegerField (default 30)  # upozori X dana prije isteka
```

### DriverDocument (Dokumenti vozača)
```python
class DriverDocument(models.Model):
    """Dokumenti vozača — vozačka, ADR, potvrda za vozače (non-EU)."""
    driver = FK(User)
    doc_type = CharField: 'driving_licence', 'cpc_card', 'adr_cert',
               'driver_attestation', 'health_cert', 'tachograph_card'
    doc_number = CharField
    categories = CharField  # B, C, CE...
    valid_until = DateField
    issuing_country = CharField
    file = FileField
```

### TachographEntry (Evidencija tahografa)
```python
class TachographEntry(models.Model):
    """Dnevna evidencija vremena vožnje/odmora."""
    driver = FK(User)
    vehicle = FK(Vehicle)
    date = DateField
    driving_time_minutes = IntegerField
    other_work_minutes = IntegerField
    availability_minutes = IntegerField
    rest_minutes = IntegerField
    # Zakonski limiti
    daily_driving_exceeded = BooleanField  # >9h (ili >10h 2x/tjedan)
    weekly_driving_total = Decimal  # max 56h/tjedan
    break_violations = IntegerField  # broj kršenja 45min pauze
```

### FuelEntry (Gorivo)
```python
class FuelEntry(models.Model):
    vehicle = FK(Vehicle)
    date = DateTimeField
    liters = Decimal
    price_per_liter = Decimal
    total_cost = Decimal
    odometer_km = IntegerField
    fuel_station = CharField
    country = CharField
    receipt_photo = ImageField
```

---

## 5. PREPORUKA — FAZNI PRISTUP

### Faza 1 (Odmah) — Povezivanje postojećeg
- [ ] TransportOrder model — spaja Vehicle + Route + CMR + HACCP
- [ ] Automatski CMR iz TransportOrder
- [ ] VehicleDocument + DriverDocument modeli
- [ ] Fleet dashboard (sva vozila, statusi, istekli dokumenti)
- [ ] AI alert za istekle dokumente (ATP, registracija)

### Faza 2 (Tjedan 2) — Kombi prijevoz DE↔HR↔BA↔RS
- [ ] Multi-country routing (via_countries)
- [ ] Carinski status tracking (T1/T2 za BA/RS)
- [ ] Posting declaration generator (za DE rad)
- [ ] Kabotaža counter (max 3 u 7 dana)
- [ ] Tahograf evidencija

### Faza 3 (Tjedan 3) — Optimizacija
- [ ] FuelEntry tracking
- [ ] Route cost calculator (gorivo + cesta + vrijeme)
- [ ] Driver app (PWA) kompletni — s tahografom i CMR-om
- [ ] Klijent tracking page (real-time s temperaturom)
- [ ] Automatski izvještaj za kupca (PDF s temp grafom)

### Faza 4 (Tjedan 4) — Premium
- [ ] GPS live tracking na karti
- [ ] ETA predikcija (AI na temelju historije)
- [ ] Automatska dodjela vozila/vozača
- [ ] Integration s Google Maps / OSM za routing
- [ ] Customer portal (klijent vidi gdje je roba)

---

## 6. FINANCIJSKI IMPACT

### Termo kutije (hrana po HR):
- Target: 10 restorana × 3 dostave/tjedan = 120 dostava/mj
- Cijena dostave: 5-15€ po dostavi
- MRR: 600-1.800€
- Margina: ~60% (bez vozila)

### Kombi prijevoz (DE↔HR↔BA↔RS):
- Target: 4 ture/mj
- Cijena ture: 800-2.000€ (ovisno o relaciji)
- MRR: 3.200-8.000€
- Margina: ~40% (s gorivom i cestom)

### Softver za prijevoznike (SaaS):
- Target: 20 malih prijevoznika × 49€/mj
- MRR: 980€
- Margina: ~85% (čisti SaaS)

---

## Izvori
- [CMR tovarni list](https://www.timocom.ba/blog/cmr-tovarni-list-sve-%C5%A1to-trebate-znati-770598)
- [ATP certifikat — CVH](https://cvh.hr/gradani/ispitivanje/atp-prijevoz-lakopokvarljivih-prehrambenih-proizvoda/)
- [Licenca Zajednice — MMPI](https://mmpi.gov.hr/promet-163/vijesti-338/za-medjunarodni-cestovni-prijevoz-tereta-ili-putnika-od-1-srpnja-2013-potrebna-licencija-zajednice/16112)
- [EU pravila za cestovni prijevoz](https://europa.eu/youreurope/citizens/work/work-abroad/rules-working-road-transport/index_hr.htm)
- [Kabotaža — EU Regulation 1072/2009](https://eur-lex.europa.eu/legal-content/HR/ALL/?uri=LEGISSUM:tr0038)
- [CMR Konvencija](https://plutonlogistics.com/en/drumski-transport/cmr-konvencija-cmr-tovarni-list/)
