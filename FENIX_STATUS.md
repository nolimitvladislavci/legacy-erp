# FENIX PORTAL — STATUS NAPRETKA

## ⚡ ARHITEKTURA SERVERA — UVIJEK AKTUALNO

| | Fenix V3 (NOVO) | Stari ERP (ovaj) |
|---|---|---|
| Domena | `v3.limit-connect.com` | `fina-connect.online` |
| Dir | `/var/www/fenix-v3/` | `/var/www/fina-connect/` |
| Servis | `gunicorn-fenix-v3` port 8001 | `gunicorn-fina` unix socket |
| Baza | `fenix_v3_clean` direktno :5432 | `fina_erp` PgBouncer :6432 |
| Redis | `127.0.0.1:6379/1` | ← dijele oba! |

> Detalji → `/var/www/fenix-v3/FENIX_ZAKON.md` Zakon 13

---

> Zadnji update: 2026-04-21 (Dan 55), commit 2507a40 — Fenix V3 test suite 96/96: smoke + accounts + booking + comprehensive + ai_gateway syntax fix

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
| 2026-04-21 | CC Sonnet | Fenix V3 test suite do kraja | 96/96 passed (0 failed): smoke, accounts, booking, comprehensive. ai_gateway.py syntax fix. sslib Shamir LIVE. Ambasador forma 4-screen wizard. | 2507a40 |
| 2026-04-20 | CC Sonnet | NO LIMIT: Bunker passkey UI + Small Doors + Booking inovacije + light/dark | login.html passkey gumb, small_doors_views.py (3 tiera), Booking QR+Temporal+Witness+Ambient, landing.html Genesis live hash + #termin sekcija, 10 stranica light theme | ad28627f |
| 2026-04-19 | CC Sonnet | TROJSTVO TOP5 + Lektire seed + Grand Plan finish | OIB blank=False+admin warn, Lektire 31 knjiga seeded, send_advanced modal wire-up, StepUp API, Celery Beat+3 | e52d6d4a |
| 2026-04-19 | CC Sonnet | memio.world Kum + Lektire + bottom nav | KumInvitation/Relationship/Gift, LektiraBook/Chapter/Progress, 7 templates, login_required_play, pnav redesign | 4a54619a |
| 2026-04-19 | CC Sonnet | DATEV 2030 + eValidator Pečat + Glasovni Send | DocumentSeal model+service+verify, DATEV v2 (BelegLink+GUID+SEPA+OSS), arhiva_send_advanced (glas+viral), _send_advanced_modal | 9ae58927 |
| 2026-04-18 | CC Sonnet | Domain split + Cluster | fina-connect.online odvojen, ModuleGateMiddleware, admin inline, nginx fix | e6943688 |
| 2026-04-18 | CC Sonnet | Predforma (scan preview card) | feat: scan result card s preview slike, metapodacima i akcijama iznad arhive popisa | 542a5cfd |
| 2026-04-18 | CC Sonnet | Arhiva bugfix marathon | Login fix (static restauriran), games redesign, arhiva bugfixes × 5, 3 arhiva inovacije | ad40054d→ca85bfc1 |
| 2026-04-18 | CC Sonnet | Fenix V3 PLAN_029-042 | PLAN_031-033 DE Steuerberater+WAHA+DATEV, PLAN_035 invoiceBuilder, PLAN_036-039 UBL+PDF+Email+Payments, PLAN_040 ClientPortal, PLAN_041-042 Accounting+JournalUI — 35/71 DONE |
| 2026-04-18 | CC Sonnet | evalidator 10/10 + Fenix V3 Arhiva | evalidator: CSS tokens, dark/light, i18n HR/EN/DE, OG meta, docs/pricing, 8 tests. Fenix V3: PLAN_025-028 Digitalna Arhiva LIVE (upload, FenixScan OCR, list+drawer). | e073b488/7336660 |
| 2026-04-16 | Sonnet | Security+Bugfixes | Print/copy/screenshot zaštita LIVE. Marija login fix. Mikrofon fix. Trojstvo IntegrityError fix. CC task Stolarija V2 zapisan. | b297a85d |

---

## SESIJA 2026-04-21 — FENIX V3 TEST SUITE 96/96

### Što je implementirano (commit 2507a40):

#### BLOK 1 — sslib Shamir Secret Sharing (produkcija)
- `accounts/shamir_recovery.py` — kompletni rewrite: `split_secret()` / `recover_secret()` via sslib
- `prime_mod` pohranjuje se kao `hex()` string (ne bytes), `recover_secret()` prima kompletni dict
- Svi 10 mogućih 3/5 kombinacija verificirani u testovima

#### BLOK 2 — Ambasador forma (4-screen wizard)
- `/var/www/fina-connect/no_limit/templates/no_limit/ambasador_prijava.html` — kompletni rewrite
- Screen 1: landing + start gumb
- Screen 2: QR kod skeniranje (simulacija device detection)
- Screen 3: mini forma s auto-detektiranim chip-ovima (lokacija, platforma, jezik)
- Screen 4: potvrda unosa
- Device fingerprinting: TZ_MAP (40+ zona), FLAG_MAP, `navigator.language`, UA mobile detection
- QR generator: `qrcode` lib, zlatni `#c9a84c` na `#0a0a0a`, base64 PNG

#### BLOK 3 — Fenix V3 Test Suite (96/96)
**Fajlovi:**
- `tests/test_smoke.py` — 12 testova (health, login, company, employee, JOPPD, AI budget, trojstvo)
- `tests/test_comprehensive.py` — 22 testa (OIB, Company, Arhiva, Security, GDPR, Performance, SmallDoors)
- `accounts/tests.py` — 34 testa (Login×9, SmallDoors×10, Shamir×8, Company×2, Security×5)
- `booking/tests.py` — 26 testa (BookingForm×5, SlotsAPI×4, AppointmentModel×5, TemporalQR×6, CompanyIsolation×1, WitnessHash×3, QRGenerator×2)

**Bugfixevi u produkcijskom kodu:**
| Fajl | Bug | Fix |
|------|-----|-----|
| `core/ai_gateway.py` | Docstring i `return` na istoj liniji (SyntaxError) | Razdvojeno na 2 linije |
| `accounts/tests.py` | `datetime.timezone.now()` umjesto `django.utils.timezone.now()` | Dodan `from django.utils import timezone` |
| `booking/tests.py` | `b"\x89PNG"` literal — non-ASCII byte u source fajlu | Ispravljen u `b"\\x89PNG"` escape |

**Pokrivene oblasti:**
- Login/logout, CSRF zaštita, SQL injection, XSS escaping
- Small Doors: Tier A (OTP), Tier B (Shamir 3/5 recovery), Tier C (panic request)
- Booking: javna forma, slots API, model auto-polja, temporal QR (48h), witness hash, company isolation
- GDPR: visitor_token_expires_at (48h window), Shamir hash-only storage
- Performance: login <2s, health <1s, slots <1s, booking form <2s

---

## SESIJA 2026-04-20 — BUNKER + SMALL DOORS + BOOKING INOVACIJE + LIGHT THEME

### BLOK 1 — Bunker Passkey UI (login.html)
**Problem:** Backend 100% gotov mjesecima, login.html nije imao niti jedan gumb za WebAuthn.  
**Fix:** Dodano na `/var/www/fenix-v3/templates/accounts/login.html`:
- "Jednim klikom 🔑" gumb s Alpine.js `x-data="bunkerLogin()"`
- Kompletni `bunkerLogin()` JS (70 linija): `checkSupport()`, WebAuthn begin/complete flow, base64url ↔ ArrayBuffer
- "ili" separator, `.lc-btn-passkey` CSS (gold border), `.lc-passkey-err` error div
- "Mala Vrata 🚪" footer link → `/hr/accounts/small-doors/`

### BLOK 2 — Small Doors 3-tier Account Recovery
**Novi fajl:** `/var/www/fenix-v3/accounts/small_doors_views.py` (296 linija)

| Tier | Metoda | Flow |
|------|--------|------|
| A — Email OTP | `SmallDoorsTierAInitView` + `SmallDoorsTierAVerifyView` | OTP link (15 min), set new PW + login |
| B — Shamir 3/5 | `SmallDoorsTierBGenerateView` + `SmallDoorsTierBVerifyView` | 5 sharesova, hash verifikacija, reset PW |
| C — Video ID | `SmallDoorsTierCView` | `PanicRecoveryRequest` → email ivan@limit-connect.com |

**URLs dodane** u `accounts/urls.py`:
```
/hr/accounts/small-doors/               landing (odabir tiera)
/hr/accounts/small-doors/tier-a/        email form
/hr/accounts/small-doors/tier-a/<tok>/  verify + reset
/hr/accounts/small-doors/tier-b/        generate shares
/hr/accounts/small-doors/tier-b/verify/ unos sharesova
/hr/accounts/small-doors/tier-c/        panic request
```

### BLOK 3 — Booking Fix + QR + 3 Inovacije
| Inovacija | Impl. | Opis |
|-----------|-------|------|
| **Temporal QR** | ✅ | `visitor_token_expires_at = created_at + 48h`, 410 Gone + `public_expired.html` |
| **Witness Signature** | ✅ | SHA-256(`booking_code:ts:email:meeting_type`), lazy gen pri prvom statusu |
| **Ambient Availability** | ✅ | `GET /pub/termin/slots/?date=` JSON API (max 6 slotova) |

### BLOK 4 — Light/Dark Theme (10 stranica)
**Commit:** `ad28627f` — 317 insertions, CSS `[data-theme="light"]` pattern, `localStorage('nl-theme')`

---

## PRIORITETI ZA SLJEDEĆU SESIJU

```
1. NO LIMIT: OIB udruge — update_genesis_oib(novi_oib) kad Marija donese rješenje
2. Stripe LIVE ključevi za KumGift (sada test mode)
3. Pilot POS test: Ivica Kruljac + Široki Šor Restoran (test u terenu)
4. Fenix V3 nastavak PLANOVA (35/71 DONE → sljedeći batch)
5. Playwright Time Machine journeys proširiti
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
### PRAVILO 19 (ZAKON) — logs/ mora biti www-data:www-data owned. gunicorn pada na startu ako root.
### PRAVILO 20 — Model polja i migracije uvijek u sinkronu. Ako migracija doda polje, model mora imati polje.

---

## DASHBOARD
```
=== CODE ===             === ARHIVA ===                === MEMIO ===
Python LoC:  ~430K       Konjik komitenti:  75         memio.pet:   LIVE ✅
Tests:       96/96 ✅    Arhiva dok.:    20,386        memio.world: Kum+Lektire ✅
Commits:       964+      OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    ~45%        DocumentSeal:   LIVE ✅        No-limit:    light/dark ✅

=== FENIX V3 TEST SUITE ===
test_smoke.py:          12/12 ✅
test_comprehensive.py:  22/22 ✅
accounts/tests.py:      34/34 ✅
booking/tests.py:       26/26 ✅
UKUPNO:                 96/96 ✅ (0 failed)

=== NO LIMIT (fina-connect) ===
Bunker Passkey gumb:     ✅ LIVE (login.html)
Small Doors 3-tier:      ✅ LIVE + sslib Shamir produkcija
Booking (NoLimitMeeting): ✅ LIVE (QR+Temporal+Witness+Ambient)
Ambasador forma:         ✅ LIVE (4-screen wizard + device detect)
Light/Dark theme:        ✅ LIVE (10 stranica)
Genesis Block live hash: ✅ LIVE (WebCrypto SHA-256)
```

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  109 | Umbrella djece:  81
Korisnika:        369 | Faktura:     15,333
Arhiva dok.:   20,386 | Commits:       964+
Swap:            18GB (2GB + 16GB)
RAM:             6.0/7.6 GB (79%)
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
| B-04 | StorageConfig 'network' backend | RIJEŠENO | NetworkStorageBackend + rclone LIVE |
| B-05 | WhatsApp-IN nepoznati pošiljatelji | NIZAK | ARHIVA-5 |
| B-06 | DATEV header verifikacija | RIJEŠENO | DATEV 2030 BelegLink |
| B-07 | POS free tier konfiguracija | RIJEŠENO | pos_obrt role + pos-besplatno plan |
| B-08 | Duplikat Radar integracija u upload view | NIZAK | nice to have |
| B-09 | core/tests.py pytest collection error | RIJEŠENO | tests.py → tests_core.py |
| B-10 | send modal wire-up u arhiva_list.html | RIJEŠENO | Napredno slanje LIVE |
| B-11 | KumGift Stripe flow | RIJEŠENO | checkout + webhook + activate() LIVE |
| B-12 | Lektire seed (HR kurikulum 1-8) | RIJEŠENO | 31 knjiga seeded |
| B-13 | Kum child selector populate | RIJEŠENO | my_children + my_children_json u kontekstu |
| B-14 | Small Doors Tier B Shamir Python 3 | RIJEŠENO | sslib instaliran, full 3/5 recovery LIVE |
| B-15 | NO LIMIT OIB udruge | ČEKA | Marija donosi rješenje |
| B-16 | ai_gateway.py SyntaxError (docstring+return) | RIJEŠENO | Razdvojeno, trojstvo testovi prolaze |

---

## KONTEKST SESIJE

### [S-012] --- 2026-04-22 (E-Račun generator na evalidator.eu)
**Branch:** master
**Zadnji commit:** 7b112982 feat(evalidator): E-Račun generator UBL 2.1 + OCR import
**Kontekst:** evalidator.eu dobio standalone e-invoice generator — potpuno neovisan od Fenix V3,
radi bez modela (stateless). invoice_service.py: UBL 2.1 XML generator (dict-based),
PEPPOL BIS 3.0, EN 16931, ISO 7064 units, TaxTotal grupiran po stopi.
views_invoice.py: GET forma, POST→preview+XML+PDF, session download, rate 10/h.
views_invoice_ocr.py: Gemini Vision 1.5-flash — foto/PDF DOS programa → JSON auto-fill
forme (5 OCR/sat, 10MB max). PDF via WeasyPrint s eIDAS pečatom (QR kod verifikacije).
3 jezika: HR/DE/EN — label dict + lang auto-detect iz Accept-Language i seller_country.
landing.html dobio 6. tab E-Račun s feature gridom i CTA. Open: FENIX V3 integracija
(copy invoice XML iz arhivator TempArhivaEntry), .dokarh format za export, bunker veza.


### [S-011] --- 2026-04-22 (eValidator V2 + Trojan Horse PWA)
**Branch:** master
**Zadnji commit:** 40e51af6 feat(evalidator): batch API + VIES + company lookup + Redis
**Kontekst:** Dva sustava unaprijeđena iste sesije. (1) Fenix V3: novi PWA modul arhivator.eu
— TempUploader/TempArhivaEntry modeli, magic link auth, 10 besplatnih skenova, Celery OCR,
SSE real-time via Redis pub/sub, CSV export, UTM upgrade funnel — Trojan Horse za Synesis 
akviziciju računovođa. Nginx arhivator.eu→/pub/arhiva/* proxy live. (2) Fina-Connect: 
eValidator V2 — batch API (max 100, OIB/IBAN/VAT), _vies_lookup() VIES EU REST, 
_sudreg_lookup() Sudski registar + 24h cache, validate_company view, Redis HyperLogLog
live counters (ev:cnt:total/today, ev:hll:ips), 5 tabova na landing (novi Batch+Firma),
eArhivator CTA block. api_status v2.0 sa live stats. Dokarh.py untracked — .dokarh format
stub čeka integraciju. Open: arhivator.eu SSL (certbot nakon DNS), .dokarh integracija u
TempArhivaEntry export, CC_TASK_COMMAND_CENTER_FAZA2.


### [S-010] --- 2026-04-21 (Global Notary — Stari ERP)
**Branch:** master
**Zadnji commit:** 203de5f3 feat(notary): auto DocumentSeal za sve fakture
**Kontekst:** Stari ERP (fina-connect.online) dobio auto DocumentSeal za sve fakture pri 
status prijelazu u SENT/CONFIRMED/FISCALIZED. Idempotentno po sha256_hash metapodataka. 
GoBD 10g čuvanje (expires_at = now + 3652d). Hookano na isti pre_save signal koji 
prati status promjene za auto-knjiženje. Globalno: radi za sve 109 aktivnih kompanija 
bez konfiguracije.




### [S-009] --- 2026-04-21 16:10
**Branch:** master
**Zadnji commit:** 1ebfab7c feat(chainblock): live verification UI + trust-badge.js widget na NO LIMIT landingu
**Kontekst:** ChainBlock Objelodanjivanje task DONE: live verification UI na landing.html, trust-badge.js embeddable widget. Kolateralna provjera: fenix-v3 OPG narudžba + edu booking backend LIVE.
### [S-008] --- 2026-04-21 13:15
**Sustav:** fina-connect (fina-connect.online) + fenix-v3 (limit-connect.com)
**Zadnji commit fina:** 978594e feat(chainblock): live verification UI + Trust Badge widget
**Zadnji commit fenix:** 0d81c55 feat(chainblock): LC-DS-2026-001/002/003 pecaceni
**Kontekst:** ChainBlock Objelodanjivanje DONE (P0): (A) Genesis card live API fetch + custom token verify input na landing.html. (B) 3 Ustav dokumenta zapecacena kao ChainBlock blokovi 1-3 (LC-DS-2026-001/002/003) — sve 3 verified:true, integrity:ok. LIMIT_CONNECT_USTAV_v1.md: real genesis hash 66c8d286. (C) trust-badge.js embeddable widget 3 linije ugradnje. Open: collectstatic za trust-badge.js.


### [S-007] --- 2026-04-21 12:45
**Sustav:** fenix-v3 (limit-connect.com)
**Branch:** master
**Zadnji commit:** 576659f feat(celery): POS beat schedule
**Kontekst:** POS Integration sesija DOVRSENA: 5 faza, 61 testova, migracije 0009-0014. HashChain+Shamir, AI Anomaly z-score, Industry Benchmark k-anonimnost. Sve 3 ideje iz buducnosti implementirane. Celery Beat: anomaly 6h + benchmark 02:30. gunicorn-fenix-v3 reloadan.



### [S-003] --- 2026-04-21 11:15
**Branch:** master
**Zadnji commit:** 97df8291 docs(memory): log-session S-002 verifikacija dual-system alata
**Kontekst:** POS modul audit + fix: 6 production crasheva (signals.py rewrite, POSReceipt 7 novih polja, POSCompany country/fiscal_exempt, POSTierConfig cancelled→is_cancelled typo, tasks.py pos_settings+buyer_oib, views.py slug→terminal_id, close_session Decimal TypeError). Migracija 0009. Tests: 29/29 (0→29). Open: DE/AT/SI fiscal stubs, templates/components prazni, inventory model nedostaje.

### [S-002] --- 2026-04-21 10:21
**Branch:** master
**Zadnji commit:** 9c1656b7 docs(memory): implement 3-layer session memory system
**Kontekst:** Verifikacija dual-system log-session alata — fina-connect strana.

### [S-001] — 2026-04-21 10:13
**Branch:** master  
**Zadnji commit:** fix(no-limit): send_whatsapp → send_text alias; ruff exclude var/ i _scripts/  
**Kontekst:** Implementiran 3-slojni memory sistem: ADR, IDEAS, KONTEKST SESIJE, pre-commit hook, log-session CLI. Open: weekly digest odgođen za sprint +2.
> CC ažurira ovu sekciju na kraju svake sesije.
> Maksimalno 10 rečenica. Što je razgovarano, koje su open threads.


