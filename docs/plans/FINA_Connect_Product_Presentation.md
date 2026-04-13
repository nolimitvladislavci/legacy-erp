# FINA-Connect ERP — Product Presentation
**Viskovic Group d.o.o. | viskovic-group.de | fina-connect.online**
**Verzija: Mart 2026**

---

## 1. STO JE FINA-CONNECT?

Modularni cloud ERP sustav za malo i srednje poduzece u Hrvatskoj i Njemackoj.
Jedna platforma — sve poslovne operacije.

**Tehnologija:** Django 5, PostgreSQL, Celery, Redis, Nginx, PWA
**Infrastruktura:** Linux server (Ubuntu), supervisor, Let's Encrypt SSL
**Pristup:** Web browser (desktop + mobitel), PWA (instalacija na home screen)

---

## 2. MODULI

### 2.1 CORE — Zajednicko
| Funkcionalnost | Opis |
|---|---|
| Multi-company | Vise tvrtki na jednoj instanci, svaka sa svojim podacima |
| Multi-language | HR, DE, EN (django-modeltranslation + rosetta) |
| Role-based access | superadmin, company_admin, project_manager, worker, partner |
| Module permissions | Svaka tvrtka placa samo module koje koristi |
| Registration flow | 4-step registracija, OIB/Steuernummer validacija, promo kodovi |
| PWA | Service Worker, offline queue, push notifikacije, Add to Home Screen |
| Impersonation | Superadmin moze "uci" u racun klijenta bez lozinke |

### 2.2 INVOICING — Fakturiranje
| Funkcionalnost | Opis |
|---|---|
| E-Racun (UBL XML) | Kreiranje, slanje, fiskalizacija (CIS) |
| Fiskalizacija | FINA CIS integracija, JIR/ZKI, potpisivanje certifikatom |
| Multi-valuta | EUR, HRK (legacy), konverzija |
| Invoice profiles | Razliciti izgledi racuna za razlicite klijente |
| PDF export | A4 + termalni (80mm) + A4-duplex formati |
| DSFinV-K | Njemacki fiskalni standard — export za reviziju |
| Storno | Storniranje s razlogom, automatski novi racun |

### 2.3 POS — Blagajna
| Funkcionalnost | Opis |
|---|---|
| Quick POS | Brza prodaja, barcode scanner, vaga integracija |
| Restaurant POS | Stolovi, narudzbe, kuhinja printer, Gastro modul |
| Smjene | Otvaranje/zatvaranje smjene, prebrojavanje kase |
| POS Detektiv Box | Pametni UI za razlike u kasi (manjak/visak) |
| Blagajnici | Vise blagajnika, PIN login, individualni obracun |
| Bonovi/Vauceri | Kreiranje, skeniranje, evidencija |
| Pfand sustav | Automatski povrat ambalaze (DE regulativa) |

### 2.4 WORKTIME — Radno vrijeme
| Funkcionalnost | Opis |
|---|---|
| Stopwatch timer | START/PAUSE/RESUME/STOP, akumulirano vrijeme |
| Rucni unos | Admin unosi sate za radnika, projekt, datum |
| Payroll engine | regular/overtime/night hours, ArbZG compliance |
| Inspector print | A4 landscape, dvojezicni (DE/HR), za inspekciju |
| Payroll summary | Mjesecni pregled troskova po radniku |
| Camera upload | Radnik slika radiliste, GPS + timestamp |
| Compliance | ArbZG §3 (>10h), §4 (pauze), nocni rad |
| Night hours | Interval overlap matematika (22:00-06:00), O(1) |

### 2.5 DELIVERY — Dostava i logistika
| Funkcionalnost | Opis |
|---|---|
| Konsolidirana dostava | Vise narudzbi u jednu rutu |
| Rollwagen (LIFO) | QR skeniranje kolica, redoslijed utovara |
| SmartBox | Termo kutije sa senzorima (styropor/izolirana/aktivno hladjena) |
| Dispatcher board | Hub manager vidi cekajuce dostave, kreira ponude |
| Driver offers | Taksi/gepek vozac prihvaca ponude |
| Cost calculator | Automatski izracun cijene po regiji, km, hladan lanac |
| Mobile-first UI | Veliki gumbi, inputmode=numeric, Enter navigacija |
| Offline mode | localStorage queue, auto-sync kad se vrati signal |
| Google Maps | Navigacija do adrese jednim klikom |

### 2.6 HACCP — Hladni lanac
| Funkcionalnost | Opis |
|---|---|
| Senzor ingest API | POST temperatura, vlaznost, GPS iz IoT senzora |
| Sustained Breach | Temp > max 10+ min = incident (ne pali za otvaranje vrata) |
| Critical Failure | Temp > 15C = instant blokada (nema 10min odgode) |
| Offline Retroactive | Bulk 120 ocitanja — retroaktivna analiza otkriva prosle prekrsaje |
| Handoff blocking | Vozac NE MOZE isporuciti ako je SmartBox blokiran |
| HACCPIncident | Revizijski trag — tip, severity, max temp, trajanje, reading IDs |
| Dispatcher resolve | Obavezna biljeska sto je poduzeto, odblokira box |
| Forensic report | A4 print, SHA-256 pecat, senzorski podaci, potpisi |
| EU 852/2004 | Compliance za HR i DE |
| HR NN 81/13 | Hrvatska implementacija EU propisa |
| Ambalaza | IFCO, Europaleta, CHEP — delivered/returned/balance |

### 2.7 PARTNERS — Partneri i CRM
| Funkcionalnost | Opis |
|---|---|
| Partner baza | OIB, adresa, kontakt, NKD klasifikacija |
| Portal token | Partner pristupa svojim dokumentima bez logina |
| Import/Export | CSV/XLSX uvoz i izvoz partnera |

### 2.8 INVENTORY — Skladiste
| Funkcionalnost | Opis |
|---|---|
| Artikli | Barcode, cijena, PDV, slika, tezina |
| Primke | Goods Receipt sa stavkama, automatsko azuriranje zaliha |
| Kalo | Evidencija gubitaka (kvar, istek roka) |
| Pfand | Povezani artikli za ambalazu |
| Price changes | Historija promjena cijena |

### 2.9 SMART IMPORT (AIP)
| Funkcionalnost | Opis |
|---|---|
| XML import | UBL e-Racun parsing |
| PDF import | Gemini 2.5 Flash AI ekstrakcija podataka |
| Image import | Gemini 2.5 Flash Vision — slika racuna |
| Vendor mapping | Automatsko prepoznavanje artikala (exact + fuzzy match) |
| Staging UI | Pregled i potvrda prije knjizenja |

### 2.10 MARKETPLACE — Trznica
| Funkcionalnost | Opis |
|---|---|
| Proizvodi | Kategorije, slike, cijene, dostupnost |
| Narudzbe | Kupac narucuje, prodavac potvrdjuje |
| Recurring orders | Automatske ponavljajuce narudzbe |
| Discount system | Popusti po kolicini, kupcu, periodu |
| Futures | Rezervacija buduce proizvodnje |

### 2.11 SYNESIS — ERP integracija
| Funkcionalnost | Opis |
|---|---|
| Storage.mdb import | Partneri, artikli iz Synesis ERP-a |
| POS import | Blagajnicki podaci iz Kasa2025 |
| BAT installer | Windows setup script za automatsku sinkronizaciju |
| Dashboard widget | ERP + POS statistika na dashboardu |

### 2.12 OSTALI MODULI
| Modul | Opis |
|---|---|
| **Projects** | Projekti, faze, fotografije, azuriranja |
| **Appointments** | Rezervacije, resursi, working hours, Dossier |
| **Documents** | Otpremnice, CMR, procesi |
| **Finance** | Transakcije, kategorije, P&L |
| **Konto** | Porezni periodi, PDV obracun |
| **Tracking** | GPS tracking posiljki, javni tracking URL |
| **Traceability** | Sljedivost hrane od farme do stola |
| **Gastro Menu** | Digitalni jelovnik za restorane |
| **Interventions** | Hitne intervencije, GPS karta, WhatsApp |
| **Insurance** | Police osiguranja, rokovi |
| **Work Orders** | Radni nalozi, zadaci |
| **Outreach** | Email/WhatsApp kampanje |
| **Assessment** | Procjene i evaluacije |
| **Fitness** | Fitness studio booking |
| **Rental** | Najam opreme |
| **Website Builder** | CMS za company website, 5 tema |
| **AI Assistant** | Claude AI chat integracija |

---

## 3. ARHITEKTURA

```
[Browser/PWA] --HTTPS--> [Nginx] --> [Gunicorn :8000] --> [Django 5]
                                                              |
                                   [PostgreSQL] <-------------+
                                   [Redis] <------ [Celery Workers]
                                   [Media/Static] ---> [WhiteNoise]

[IoT Senzori] --POST JSON--> [/delivery/api/cold-chain/ingest/]
                                       |
                              [analyze_readings()] --> [HACCPIncident]
                                       |
                              [SmartBox.haccp_status = 'blocked']
                                       |
                              [driver_handoff() --> 403 FORBIDDEN]
```

---

## 4. SIGURNOST

| Mjera | Implementacija |
|---|---|
| HTTPS | Let's Encrypt, HSTS, SECURE_SSL_REDIRECT |
| CSRF | Django CSRF middleware, token u svim formama |
| Auth | Session-based + Token (API), login_required |
| CORS | Nginx location block, per-origin |
| Subscription | Middleware provjerava modul pristup |
| Impersonation | Samo superadmin, log svake sesije |
| SHA-256 seal | HACCP forenzicki izvjestaji — dokaz integriteta |

---

## 5. MOBILNA SPREMNOST

| Provjera | Status |
|---|---|
| Viewport meta tag | OK |
| PWA manifest (standalone) | OK |
| Service Worker + cache | OK |
| Offline queue (localStorage) | OK |
| Background sync | OK |
| Push notifications | OK |
| Apple Web App meta | OK |
| Touch targets >= 48px | OK |
| Responsive breakpoint 768px | OK |
| inputmode=numeric | OK |
| capture=environment (camera) | OK |

---

## 6. TESTOVI

| Suite | Testova | Status |
|---|---|---|
| Payroll matematika | 15 | PASS |
| HACCP scenariji | 6 | PASS |
| Mobile readiness | 42 | PASS |
| Cost Calculator API | 7 | PASS |
| Registration | auto | PASS |
| Fiscal | auto | PASS |
| Core | auto | PASS |

### HACCP Scenariji (automatski testirani):
1. **Otvaranje vrata** — temp skok 2 min, NEMA alarma (lazni alarm prevencija)
2. **Crknut kompresor** — temp > max 12 min, SUSTAINED BREACH, box CRITICAL
3. **Tunel offline** — 120 bulk ocitanja, retroaktivni scan, prekrsaj u proslosti
4. **Critical failure** — temp > 15C, INSTANT blokada, box BLOCKED
5. **Revizijski trag** — dispatcher zatvara incident, box odblokiran
6. **Duplikat prevencija** — ponovljena analiza ne kreira duplikate

---

## 7. PRICING MODEL

| Plan | Cijena | Moduli |
|---|---|---|
| Starter | besplatno | invoicing, partners, documents, calculator, worktime, projects, pos, appointments |
| Professional | 49 EUR/mj | + konto, reports, tracking, assessment, outreach, work_orders, marketplace, delivery, traceability, gastro_menu |
| Enterprise | 149 EUR/mj | + SVE (finance, inventory, insurance, webshop, rental, fitness, interventions, ai_assistant) |

---

## 8. PLATFORME I TRZISTA

### Hrvatska (HR)
- **Osijek** — lokalna dostava, OPG-ovi, veletrznica
- **Slavonija** — srednje rute (15-80km)
- **Dalmacija** — duge rute (80-400km), aktivno hladjenje

### Njemacka (DE)
- **Stuttgart** — Grossmarkt, logisticki hubovi
- **Baden-Wurttemberg** — regionalna dostava

### Grosmarkt Online (grosmarkt-online.eu)
- Digitalna platforma za veletrznice
- Dinamicki prikaz partnera (API)
- Registracija s auto-dodjelom modula
- CORS integracija s FINA-Connect backendom

---

## 9. ZAKONSKA USKLADENOST

| Propis | Podrucje | Implementacija |
|---|---|---|
| EU 852/2004 | Higijena hrane, transport | HACCP senzori, temp monitoring |
| HR NN 81/13 | HR implementacija EU propisa | Isti sustav, HR jezik |
| ArbZG §3 | Radno vrijeme max 10h | Compliance upozorenja |
| ArbZG §4 | Pauze (30min/6h, 45min/9h) | Automatska detekcija |
| ZOR cl.65 | HR Zakon o radu | Dual compliance |
| DSFinV-K | DE fiskalna revizija | Export modul |
| FINA CIS | HR fiskalizacija | Certifikat potpisivanje |

---

## 10. KONKURENTSKE PREDNOSTI

1. **Dual-market** — jedan sustav za HR i DE, dvojezican
2. **HACCP Smart Sensor** — 3-rule breach detection, retroaktivna analiza, SHA-256 forenzika
3. **Offline-first** — vozac radi bez interneta, podaci se sinkroniziraju
4. **Modularno** — platis samo sto koristis
5. **PWA** — nema app store-a, instalira se iz browsera
6. **AI import** — Gemini 2.5 Flash cita racune iz slika i PDF-ova
7. **Taxi dostava** — gepek/taksi model za lokalne dostave (disrupcija!)
8. **SmartBox** — termo kutije s GPS-om i senzorima, cost calculator po km

---

## 11. TECH STACK

| Komponenta | Tehnologija |
|---|---|
| Backend | Django 5.x, Python 3.12 |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7, Celery |
| Web server | Nginx, Gunicorn |
| Frontend | Django Templates, Vanilla JS, Font Awesome |
| AI | Gemini 2.5 Flash (smart import), Claude Haiku (AI assistant chat) |
| Process mgmt | Supervisor |
| SSL | Let's Encrypt (Certbot) |
| Version control | Git, GitHub |
| OS | Ubuntu 22.04 LTS |

---

## 12. KONTAKT

**Viskovic Group d.o.o.**
Web: viskovic-group.de | fina-connect.online | grosmarkt-online.eu
Server: 85.9.201.204

---

*Dokument generiran: Mart 2026*
*FINA-Connect ERP v2.0*
