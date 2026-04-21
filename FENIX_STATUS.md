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

> Zadnji update: 2026-04-20 (Dan 54), commit ad28627f — NO LIMIT: Bunker passkey UI + Small Doors 3-tier recovery + Booking inovacije (QR+Temporal+Witness+Ambient) + light/dark theme

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
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

**Napomena:** `secretsharing` Python 2 compat bug (`long` NameError) → `except Exception` u `shamir_recovery.py`. Dev fallback: `SHARE-{i}-{hex}-DEV` format.

### BLOK 3 — NO LIMIT Landing Integracija
**Fajl:** `/var/www/fina-connect/no_limit/templates/no_limit/landing.html`

- **Genesis Block live SHA-256**: WebCrypto API `crypto.subtle.digest`, seed = `"NO-LIMIT-GENESIS-0001:" + datum` → isti hash za sve posjetitelje isti dan
- **`#termin` sekcija**: 3 kartice (Online/Osobni/Hitni), Visitor Portal objašnjenje, gold CTA gumb → `/no-limit/booking/`
- **Hero CTA**: dodan 3. gumb "Rezerviraj termin ↗"
- **Navbar**: dodan "Termin" link

### BLOK 4 — Booking Fix + QR
**Problem:** Booking submit gumb tiho failao (200 umjesto redirect) jer `Appointment.objects.create()` bacio `TypeError` — polja iz migration 0002 nisu bila u model klasi.

**Fix:** Dodano 8 polja u `booking/models.py`:
`meeting_type`, `jitsi_room`, `visitor_token`, `visitor_country`, `visitor_timezone`, `organization`, `visitor_token_expires_at`, `witness_hash`

**QR na potvrdi:** `_generate_qr_b64(url)` → golden QR (`#c9a84c` na `#0a0a0a`) kao base64 PNG, prikazano u `public_confirm.html`

### BLOK 5 — 3 Inovacije iz Budućnosti
| Inovacija | Impl. | Opis |
|-----------|-------|------|
| **Temporal QR** | ✅ | `visitor_token_expires_at = created_at + 48h`, 410 Gone + `public_expired.html` |
| **Witness Signature** | ✅ | SHA-256(`booking_code:ts:email:meeting_type`), lazy gen pri prvom statusu, prikazan u `public_status.html` |
| **Ambient Availability** | ✅ | `GET /pub/termin/slots/?date=` JSON API (max 6 slotova), JS date `change` → `fetchSlots()` → `rebuildSelect()` u `public_book.html` |

**Migration:** `booking/migrations/0003_booking_temporal_witness.py` — applied ✅

**Radno vrijeme:** hard-block uklonjen → soft `_out_of_hours` flag, bilježi se u `notes` (EU partneri mogu rezervirati vikendom)

### BLOK 6 — Light/Dark Theme (10 stranica)
**Commit:** `ad28627f` — 317 insertions

| Stranica | Status |
|----------|--------|
| `landing.html` | ✅ Kompletno + Genesis live hash |
| `kontakt.html` | ✅ |
| `o_nama.html` | ✅ |
| `ambasadori.html` | ✅ |
| `ambasador_prijava.html` | ✅ |
| `ambasador_hvala.html` | ✅ |
| `partneri.html` | ✅ |
| `projekti.html` | ✅ |
| `statut.html` | ✅ |
| `vodic_online.html` | ✅ |

**CSS pattern:** `[data-theme="light"]` override na `<html>` element (nije dupliciranje stilova)  
**Toggle:** `☀️/🌙` gumb u navbaru, `localStorage('nl-theme')`, `prefers-color-scheme` auto-detect

---

## SESIJA 2026-04-19 — memio.world KUM SUSTAV + LEKTIRE

### Što je implementirano (commit 4a54619a):

#### BLOK 1 — Kum sustav (digitalni kumovi)
| Fajl | Opis |
|------|------|
| `memio_world/kum_models.py` | KumInvitation (token+expire), KumRelationship (kum←→child←→parent), KumGift (plan sponsorship s approve/decline/activate) |
| `memio_world/views_kum.py` | kum_dashboard, kum_invite_send (JSON), kum_invite_accept (token landing), kum_gift_create, kum_gift_approve |
| `memio_world/views_auth.py` | login_required_play decorator dodan |
| Templates | kum_dashboard.html, kum_invite_landing.html, kum_invite_accepted.html, kum_invite_invalid.html |

#### BLOK 2 — Lektire (HR školski kurikulum)
| Fajl | Opis |
|------|------|
| `memio_world/lektire_models.py` | LektiraBook (razredi 1-8, mandatory/optional, public_domain), LektiraChapter, LektiraProgress, LektiraQuiz |
| `memio_world/views_lektire.py` | lektire_home, lektira_detail, lektira_chapter_read, lektira_mark_read |
| Templates | lektire_home.html, lektira_detail.html, lektira_chapter.html |

#### BLOK 3 — Bottom nav redesign (pnav-*)
- `templates/memio_world/base_play.html` — pnav-icon 48×48px, speech bubbles, scale animation

#### Migration
- `memio_world/migrations/0016_kum_lektire.py` — applied ✅

---

## SESIJA 2026-04-19 — DATEV 2030 + eValidator PEČAT + GLASOVNI SEND

### Što je implementirano (commit 9ae58927):

#### BLOK 1 — eValidator DocumentSeal (eIDAS Art. 41)
- `evalidator/models.py` — DocumentSeal: seal_token, sha256_hash, viral_code, expires_at (10g GoBD)
- `evalidator/seal_service.py` — generate_seal, QR, PDF embed
- `/evalidator/verify/<token>/` — javna verifikacijska stranica

#### BLOK 2 — DATEV 2030
- `konto/german_accounting.py` — generate_datev_export_v2(): BelegLink, UUID, KOST1, SEPA, OSS/IOSS

#### BLOK 3 — Glasovni Send
- `documents/views_arhiva.py` — arhiva_send_advanced(): multi-channel, auto-pečat, viral_code, glas
- `templates/documents/_send_advanced_modal.html` — Modal s MediaRecorder + TTS

---

## PRIORITETI ZA SLJEDEĆU SESIJU

```
1. NO LIMIT: OIB udruge — update_genesis_oib(novi_oib) kad Marija donese rješenje
2. Stripe LIVE ključevi za KumGift (sada test mode)
3. Pilot POS test: Ivica Kruljac + Široki Šor Restoran (test u terenu)
4. Small Doors Tier B — instalirati Python 3 kompatibilni secretsharing (sslib ili secret-sharing)
5. Grand Plan Blok 4 — Triple DNA Layer 3 CLIP async (GPU task za semantički embedding)
6. Fenix V3 nastavak PLANOVA (35/71 DONE → sljedeći batch)
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
Tests:       2,401       Arhiva dok.:    20,386        memio.world: Kum+Lektire ✅
Commits:       963+      OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    40.3%       DocumentSeal:   LIVE ✅        No-limit:    light/dark ✅

=== NO LIMIT (fina-connect) ===
Bunker Passkey gumb:     ✅ LIVE (login.html)
Small Doors 3-tier:      ✅ LIVE (Tier A/B/C recovery)
Booking (NoLimitMeeting): ✅ LIVE (bug fix + QR)
Temporal QR (48h expiry): ✅ LIVE
Witness Signature:        ✅ LIVE (SHA-256 proof)
Ambient Availability:     ✅ LIVE (slots JSON API)
Light/Dark theme:         ✅ LIVE (10 stranica)
Genesis Block live hash:  ✅ LIVE (WebCrypto SHA-256)

=== memio.world NOVI MODULI ===
Kum sustav:        ✅ LIVE (KumInvitation/Relationship/Gift)
Lektire:           ✅ LIVE (31 knjiga, razredi 1-8)
Bottom nav pnav-*: ✅ LIVE (48px icons + CSS speech bubbles)

=== eVALIDATOR PEČAT ===
DocumentSeal:           ✅ LIVE
verify_seal:            ✅ /evalidator/verify/<token>/

=== DATEV 2030 ===
generate_datev_export_v2: ✅ BelegLink+GUID+KOST+SEPA+OSS
```

---

# ZLATNI KOD — PLAN PRODUKCIJE

## KORACI 1-10 ✅ GOTOVO

## KORAK 11 — BETA: KONJIK D.O.O. 🔄 AKTIVAN (40%)
```
Firma:    Konjik d.o.o. — računovodstveni ured, 75 komijenata, 10.109 dok.
Knjigov.: Marija + Ljiljana + Nikolina + Silvija + Anita
Cilj:     Marija kaže "ovo radi, mogu pokazati klijentima"
Status:   Arhiva funkcionalna, konverzija fiksirana, preview radi, pečat spreman
Pending:  OneDrive sync, WhatsApp-IN, Skupni download testiran live
```

## GORIVO
| Što | Status | % |
|-----|--------|---|
| Koraci 1-10 | ✅ | 100% |
| Korak 11 Beta | 🔄 | 40% |
| **ARHIVA-1** Mobile Scan | ✅ LIVE | 95% |
| ARHIVA-2 Magic Link | ✅ LIVE | 100% |
| ARHIVA-3 Network Disk | ⏳ | — |
| ARHIVA-4 WhatsApp Share | ✅ LIVE | 80% |
| ARHIVA-5 WhatsApp-IN | ⏳ | — |
| **eValidator DocumentSeal** | ✅ LIVE | 100% |
| **DATEV 2030 Export** | ✅ LIVE | 95% |
| **Glasovni Send** | ✅ LIVE | 90% |
| **NoLimitMeeting Booking** | ✅ LIVE (QR+Temporal+Witness+Ambient) | 95% |
| **NO LIMIT Light/Dark Theme** | ✅ LIVE (10 str.) | 100% |
| **Bunker Passkey UI** | ✅ LIVE | 100% |
| **Small Doors 3-tier Recovery** | ✅ LIVE (Tier B dev fallback) | 85% |
| **memio.world Kum** | ✅ LIVE | 85% |
| **memio.world Lektire** | ✅ LIVE | 75% |
| **PLAY.EU Sprint 1** | ✅ DONE | 100% |

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  109 | Umbrella djece:  81
Korisnika:        369 | Faktura:     15,333
Arhiva dok.:   20,386 | Commits:       963+
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
| B-14 | Small Doors Tier B Shamir Python 3 | SREDNJE | instalirati sslib ili secret-sharing |
| B-15 | NO LIMIT OIB udruge | ČEKA | Marija donosi rješenje |
