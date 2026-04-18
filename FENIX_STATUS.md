# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-18 (Dan 52), commit e6943688 — Domain split + Cluster Module Gate LIVE

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
| 2026-04-18 | CC Sonnet | Domain split + Cluster | fina-connect.online odvojen, ModuleGateMiddleware, admin inline, nginx fix | e6943688 |
| 2026-04-18 | CC Sonnet | Predforma (scan preview card) | feat: scan result card s preview slike, metapodacima i akcijama iznad arhive popisa | 542a5cfd |
| 2026-04-18 | CC Sonnet | Arhiva bugfix marathon | Login fix (static restauriran), games redesign, arhiva bugfixes × 5, 3 arhiva inovacije | ad40054d→ca85bfc1 |
| 2026-04-18 | CC Sonnet | Fenix V3 PLAN_029-042 | PLAN_031-033 DE Steuerberater+WAHA+DATEV, PLAN_035 invoiceBuilder, PLAN_036-039 UBL+PDF+Email+Payments, PLAN_040 ClientPortal, PLAN_041-042 Accounting+JournalUI — 35/71 DONE |
| 2026-04-18 | CC Sonnet | evalidator 10/10 + Fenix V3 Arhiva | evalidator: CSS tokens, dark/light, i18n HR/EN/DE, OG meta, docs/pricing, 8 tests. Fenix V3: PLAN_025-028 Digitalna Arhiva LIVE (upload, FenixScan OCR, list+drawer). | e073b488/7336660 |
| 2026-04-16 | Sonnet | Security+Bugfixes | Print/copy/screenshot zaštita LIVE. Marija login fix. Mikrofon fix. Trojstvo IntegrityError fix. CC task Stolarija V2 zapisan. | b297a85d |
| 2026-04-15 | Opus CC | PLAY.EU Faza E | PWA shell, 11 views, 12 templates, memory game, quiz JS, night mode | 9dd0ebea |
| 2026-04-15 | Opus CC | DeepSeek Patrol | Fix autodiscovery, Celery Beat registered, nocni run 02:45 | 5cf29da6 |

---

## SESIJA 2026-04-18 — ARHIVA BUGFIX MARATHON (8 commita)

### Commits:
| Commit | Opis |
|--------|------|
| ad40054d | fix(static): KRITIČNO — restaurirani CSS/JS (50 fajlova) obrisani u Antonio test sesiji |
| af3ff0c6 | feat(games): Čovječe redesign + iOS memory fix + kviz score bugfix |
| fde7439f | fix(arhiva): openPreviewModal undefined + paginacija duplicira page param |
| 7968b96c | fix(arhiva): convert flow sada kreira ArhivaEntry + multi-page merge |
| 8b9727f4 | fix(arhiva): dodaj previewModal HTML div — CSS/JS bio ali bez HTML elementa |
| ca85bfc1 | feat(arhiva): 3 inovacije — Skupni Download + Duplikat Radar + Partner Intel |

### Root causes riješeni:
1. **Login blokada** — 6337920c obrisao 50 static fajlova → .fx-hidden nedefiniran → #docScanModal prekrio ekran
2. **Dokument nestao** — arhiva_convert kreirao ConversionRecord ali NIKAD ArhivaEntry (arhiva_entry=None)
   - 2 HEP dokumenta retroaktivno spašena → ARH-2026/19148 i ARH-2026/19149
3. **previewModal HTML** — CSS klase i JS funkcija postojale, ali `<div id="previewModal">` nije bio u DOM-u
4. **Paginacija** — ?page=2&{{ urlencode }} dupliciralo page= param, Django uzima zadnju vrijednost
5. **openPreviewModal undefined** — pozvana u partial ali nikad definirana
6. **Kviz score=0** — `dataset.correct === 'True'` trebalo biti `'true'` (JSON lowercase)

### 3 Inovacije (ca85bfc1):
| Inovacija | Opis | Endpoints |
|-----------|------|-----------|
| **Skupni Download** | ZIP svih dokumenta jednog dobavljača za period. Smart naming + CSV korice. | /arhiva/monthly-bundle/ + /preview/ |
| **Duplikat Radar** | 3 razine: hash 100%, doc_broj+partner 99%, iznos±1%+datum±14d 85%. Žuti toast pri novom uploadu. | /arhiva/duplicate-check/ |
| **Partner Intel** | 13 mj. trend, gap detekcija, anomalija (avg+1.5σ), YTD delta %. Mini bar chart u UI. | /arhiva/partner-intel/ |

### Multi-page merge (7968b96c):
- Nova ruta /arhiva/convert/merge/ — prima file_0..file_N, PyMuPDF spaja u PDF → jedan ArhivaEntry
- JS toggle u galeriji: "Odvojeni dokumenti" ↔ "Spoji u 1 dokument" (prikaže se >1 slika)

---

## PRIORITETI ZA SLJEDEĆU SESIJU

```
1. ✅ DONE — Domain split (fina-connect.online → port 8000 direktno)
2. ✅ DONE — Cluster/Module Gate (ModuleGateMiddleware + admin inline)
3. ARHIVA-3 — rclone OneDrive backend (StorageConfig 'network')
2. POS free tier — Marija Čačić pilot (obrt kod kuće)
3. Slovarica fix — CC_TASK_SLOVARICA_FIX.md (font Andika, canvas DPI, 30 MP3)
4. Slikovnice — PLAN_SLIKOVNICE.md Glava 1 Backend (ROK CP1: 2026-04-20 ⚠)
5. WhatsApp-IN (ARHIVA-5) — Ivan želi chat-to-archive flow
```

---

## RAZVOJNA PRAVILA

### PRAVILO 1 — Nema zakrpa, samo pravi fix
### PRAVILO 2 — Settings i model choices sinkronizirani
### PRAVILO 3 — Template promjene = gunicorn reload
### PRAVILO 4 — `--preload` zabranjeno
### PRAVILO 5 — Nikad conditional import unutar try/except
### PRAVILO 6 — QR kodovi uvijek kroz /qr/ endpoint
### PRAVILO 7 — Svaka nova javna ruta u RouteRegistry
### PRAVILO 8 — OIBi u testovima validni (ISO 7064 Luhn-10)
### PRAVILO 9 — Bez datuma izvršenja, samo redoslijed

---

## DASHBOARD
```
=== CODE ===             === ARHIVA ===                === MEMIO ===
Python LoC:  ~302K       Konjik komitenti:  75         memio.pet:   LIVE ✅
Tests:       2,340       Arhiva dok.:    10,109        memio.world: Temelj ✅
Commits:       960+      OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    40.3%       ConversionRecord: 2 spašena   No-limit:    NGO portal ✅

=== ARHIVA FEATURESET ===
Upload → ArhivaEntry:  ✅  |  Convert → ArhivaEntry:  ✅ (bio bug, fixano)
Preview slike:         ✅  |  Paginacija:              ✅ (bio bug, fixano)
Multi-page merge:      ✅  |  Skupni download ZIP:     ✅ NEW
Duplikat Radar:        ✅  |  Partner Intel 13mj:      ✅ NEW
```

---

# ZLATNI KOD — PLAN PRODUKCIJE

## KORACI 1-10 ✅ GOTOVO

## KORAK 11 — BETA: KONJIK D.O.O. 🔄 AKTIVAN (35%)
```
Firma:    Konjik d.o.o. — računovodstveni ured, 75 komijenata, 10.109 dok.
Knjigov.: Marija + Ljiljana + Nikolina + Silvija + Anita
Cilj:     Marija kaže "ovo radi, mogu pokazati klijentima"
Status:   Arhiva funkcionalna, konverzija fiksirana, preview radi
Pending:  OneDrive sync, WhatsApp-IN, Skupni download testiran live
```

## GORIVO
| Što | Status | % |
|-----|--------|---|
| Koraci 1-10 | ✅ | 100% |
| Korak 11 Beta | 🔄 | 35% |
| **ARHIVA-1** Mobile Scan | ✅ LIVE | 95% |
| ARHIVA-2 Magic Link | ✅ LIVE | 100% |
| ARHIVA-3 Network Disk | ⏳ | — |
| ARHIVA-4 WhatsApp Share | ✅ LIVE (arhiva_send_komitent) | 80% |
| ARHIVA-5 WhatsApp-IN | ⏳ | — |
| **Skupni Mjesečni Download** | ✅ LIVE | 100% |
| **Duplikat Radar** | ✅ LIVE | 100% |
| **Partner Intelligence** | ✅ LIVE | 100% |
| **Multi-page Merge (convert)** | ✅ LIVE | 100% |
| ARHIVA-6 DE Steuerberater | ⏳ | — |
| ARHIVA-7 DATEV Export | ⏳ | — |
| **POS free tier** (Marija Čačić) | ⏳ | — |
| **PLAY.EU Sprint 1** | ✅ DONE | 100% |
| Slovarica fix | ⏳ CC Task | — |
| Slikovnice CP1 | ⏳ ROK 20.04 | — |

---

# OPERACIJA: ARHIVA HR-DE

## OCR BENCHMARK (live test, 2026-04-14)
```
4 računa: INA Čepin ×2, Petrol Osijek, Petrol Ljubljana (SI)
Točnost:  100% — dobavljač, datum, iznos, JIR/ZKI
```

## Arhiva Feature Matrix
```
[x] Upload → ArhivaEntry + OCR + AI prijedlog
[x] Convert (kamera) → ArhivaEntry (BUG FIXAN 2026-04-18)
[x] Multi-page merge → jedan PDF → jedan ArhivaEntry
[x] Preview slike/PDF u modalu (BUG FIXAN 2026-04-18)
[x] Paginacija bez URL duplikacije (BUG FIXAN 2026-04-18)
[x] Skupni Mjesečni Download (NEW 2026-04-18)
[x] Duplikat Radar — 3 razine detekcije (NEW 2026-04-18)
[x] Partner Intelligence — 13 mj. trend + anomalije (NEW 2026-04-18)
[ ] ARHIVA-3: rclone OneDrive backend
[ ] ARHIVA-5: WhatsApp-IN
[ ] ARHIVA-7: DATEV Export
```

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  101 | Umbrella djece:  81
Korisnika:        56 | Faktura:     15,330
Arhiva dok.:  10,109 | Commits:       960+
Konjik HEP dok:    4 (ARH-2026/19146-19149, sve OK)
```

## AI SERVISI
```
DeepSeek:   AKTIVAN ✅ (uplata $5.30, 2026-04-14)
Bedrock:    AKTIVAN ✅ (eu-central-1)
Anthropic:  AKTIVAN ✅ (API key u settings)
```

---

# BACKLOG

| # | Nalaz | Ozbiljnost | Uvjet |
|---|-------|------------|-------|
| B-01 | user_edit company isolation | SREDNJE | company_admin self-service |
| B-02 | trojstvo_task suggestion_id type guard | NIZAK | kad se dotakne trojstvo |
| B-04 | StorageConfig 'network' backend | SREDNJE | ARHIVA-3 |
| B-05 | WhatsApp-IN nepoznati pošiljatelji | NIZAK | ARHIVA-5 |
| B-06 | DATEV header verifikacija | VISOK | ARHIVA-7 |
| B-07 | POS free tier konfiguracija za Mariju Čačić | SREDNJE | memio.world MVP |
| B-08 | Duplikat Radar integracija u upload view | NIZAK | nice to have — dual warning |

---

## PLAY.EU — SPRINT 1 ✅ DONE
```
Faza A-E: DONE. 23 modela, 237 sadržaja, PWA shell, games, quiz.
Creative Europe deadline: 2026-05-07
CP1 Slikovnice: ROK 2026-04-20 ⚠ HITNO
```

---

## MEMIO EKOSISTEM
```
memio.pet:   LIVE ✅ (22 rute, 12/12 testovi)
memio.world: Temelj ✅, MVP čeka POS free tier
memio.farm:  SyncLink ✅
No-limit:    NGO portal ✅
```
