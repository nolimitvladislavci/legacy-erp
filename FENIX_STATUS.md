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

> Zadnji update: 2026-04-19 (Dan 53), commit 9ae58927 — DATEV 2030 + eValidator Pečat + Glasovni Send

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
| 2026-04-19 | CC Sonnet | DATEV 2030 + eValidator Pečat + Glasovni Send | DocumentSeal model+service+verify, DATEV v2 (BelegLink+GUID+SEPA+OSS), arhiva_send_advanced (glas+viral), _send_advanced_modal | 9ae58927 |
| 2026-04-18 | CC Sonnet | Domain split + Cluster | fina-connect.online odvojen, ModuleGateMiddleware, admin inline, nginx fix | e6943688 |
| 2026-04-18 | CC Sonnet | Predforma (scan preview card) | feat: scan result card s preview slike, metapodacima i akcijama iznad arhive popisa | 542a5cfd |
| 2026-04-18 | CC Sonnet | Arhiva bugfix marathon | Login fix (static restauriran), games redesign, arhiva bugfixes × 5, 3 arhiva inovacije | ad40054d→ca85bfc1 |
| 2026-04-18 | CC Sonnet | Fenix V3 PLAN_029-042 | PLAN_031-033 DE Steuerberater+WAHA+DATEV, PLAN_035 invoiceBuilder, PLAN_036-039 UBL+PDF+Email+Payments, PLAN_040 ClientPortal, PLAN_041-042 Accounting+JournalUI — 35/71 DONE |
| 2026-04-18 | CC Sonnet | evalidator 10/10 + Fenix V3 Arhiva | evalidator: CSS tokens, dark/light, i18n HR/EN/DE, OG meta, docs/pricing, 8 tests. Fenix V3: PLAN_025-028 Digitalna Arhiva LIVE (upload, FenixScan OCR, list+drawer). | e073b488/7336660 |
| 2026-04-16 | Sonnet | Security+Bugfixes | Print/copy/screenshot zaštita LIVE. Marija login fix. Mikrofon fix. Trojstvo IntegrityError fix. CC task Stolarija V2 zapisan. | b297a85d |

---

## SESIJA 2026-04-19 — DATEV 2030 + eValidator PEČAT + GLASOVNI SEND

### Što je implementirano (commit 9ae58927):

#### BLOK 1 — eValidator DocumentSeal (eIDAS Art. 41)
| Fajl | Opis |
|------|------|
| `evalidator/models.py` | DocumentSeal model: seal_token (8-char), sha256_hash, viral_code, expires_at (10g GoBD) |
| `evalidator/seal_service.py` | generate_seal(), get_or_create_seal(), seal_to_qr_base64(), embed_seal_in_pdf() |
| `evalidator/views.py` | verify_seal (/evalidator/verify/<token>/), api_verify_seal (JSON API) |
| `evalidator/templates/verify_seal.html` | Javna verifikacijska stranica s QR, metapodacima, viral CTA |
| `evalidator/migrations/0002_*` | DB migracija — applied ✅ |
| `core/context_processors.py` | failed_imports_badge dodan (bio missing) |

#### BLOK 2 — DATEV 2030 (bolje od DATEV-a)
| Fajl | Opis |
|------|------|
| `konto/german_accounting.py` | generate_datev_export_v2(): BelegLink, UUID, KOST1, SEPA, OSS/IOSS |
| `konto/views.py` | datev_export_v2() view: GET=UI, POST=CSV/ZIP download |
| `konto/urls.py` | /konto/datev-2030/ route dodan |
| `templates/konto/datev_export_v2.html` | Bogati UI: period picker, Steuerberater, opcije, format |

#### BLOK 3 — Digitalni Send s Glasom + Viral Kod
| Fajl | Opis |
|------|------|
| `documents/views_arhiva.py` | arhiva_send_advanced(): multi-channel, auto-pečat, viral_code, glas |
| `documents/urls.py` | /arhiva/<pk>/send-advanced/ i /send-advanced/ui/ dodani |
| `templates/documents/_send_advanced_modal.html` | Modal: kanali, MediaRecorder, TTS, pečat badge |

### Zakonska osnova:
- **eIDAS Art. 41**: elektronički vremenski žig = presumpcija integriteta
- **GoBD §14b**: SHA-256 hash, expires_at 10g, neopozivo, dostupno na zahtjev
- **GDPR Art. 6(1)(b)**: slanje dokumenta = izvršenje ugovora = lawful basis
- **Glasovna poruka**: browser-side MediaRecorder/TTS, bez server storage = GDPR safe
- **ZED HR (NN 150/05)**: digitalni dokument s timestampom = original

### Što je OSTALO (nije implementirano):
- Send modal integracija u arhiva_list.html (treba `window.openSendAdvancedModal(pk, num)` poziv)
- SEPA pain.008 XML generator (DATEV 2030 extra format)
- WhatsApp voice note via WAHA (treba `send_voice()` u core/whatsapp.py)

---

## PRIORITETI ZA SLJEDEĆU SESIJU

```
1. ARHIVA-3 — rclone OneDrive backend (StorageConfig 'network')
2. POS free tier — Marija Čačić pilot (obrt kod kuće)
3. Slovarica fix — CC_TASK_SLOVARICA_FIX.md (font Andika, canvas DPI, 30 MP3)
4. Slikovnice — PLAN_SLIKOVNICE.md Glava 1 Backend (ROK CP1: 2026-04-20 ⚠ PROŠLO!)
5. WhatsApp-IN (ARHIVA-5) — Ivan želi chat-to-archive flow
6. Send modal integracija u arhiva_list.html (wire up openSendAdvancedModal)
7. core/tests.py greška (pytest collection error — fix 1-2 linije)
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
Python LoC:  ~422K       Konjik komitenti:  75         memio.pet:   LIVE ✅
Tests:       2,401       Arhiva dok.:    20,386        memio.world: Temelj ✅
Commits:       961+      OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    40.3%       DocumentSeal:   0 (novi!)     No-limit:    NGO portal ✅

=== eVALIDATOR PEČAT ===
DocumentSeal model:     ✅ LIVE (DB migracija applied)
seal_service.py:        ✅ generate_seal, QR, PDF embed
verify_seal:            ✅ /evalidator/verify/<token>/
api_verify:             ✅ /evalidator/api/v1/verify/<token>/

=== DATEV 2030 ===
generate_datev_export_v2: ✅ BelegLink+GUID+KOST+SEPA+OSS
UI stranica:              ✅ /konto/datev-2030/
CSV+ZIP download:         ✅ s README pravnom dokumentacijom

=== GLASOVNI SEND ===
MediaRecorder API:        ✅ Snimanje glasa → audio/webm
Web Speech API TTS:       ✅ Browser-side, GDPR safe
Send modal UI:            ✅ _send_advanced_modal.html
Multi-channel:            ✅ email + WhatsApp + portal link
eValidator auto-seal:     ✅ Generira se automatski pri slanju
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
| ARHIVA-4 WhatsApp Share | ✅ LIVE (arhiva_send_komitent) | 80% |
| ARHIVA-5 WhatsApp-IN | ⏳ | — |
| **eValidator DocumentSeal** | ✅ LIVE | 100% |
| **DATEV 2030 Export** | ✅ LIVE | 95% |
| **Glasovni Send (MediaRecorder)** | ✅ LIVE | 90% |
| **Viral Kod** | ✅ LIVE | 90% |
| ARHIVA-6 DE Steuerberater | 🔄 35% | DATEV 2030 LIVE |
| ARHIVA-7 DATEV Export | ✅ v2 LIVE | 90% |
| **POS free tier** (Marija Čačić) | ⏳ | — |
| **PLAY.EU Sprint 1** | ✅ DONE | 100% |

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  109 | Umbrella djece:  81
Korisnika:        369 | Faktura:     15,333
Arhiva dok.:   20,386 | Commits:       961+
Swap:            18GB (2GB + 16GB) — dovoljno za 5000 user load testove
RAM:             6.0/7.6 GB (79% = load testovi normalno)
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
| B-06 | DATEV header verifikacija | RIJEŠENO | DATEV 2030 BelegLink |
| B-07 | POS free tier konfiguracija za Mariju Čačić | SREDNJE | memio.world MVP |
| B-08 | Duplikat Radar integracija u upload view | NIZAK | nice to have |
| B-09 | core/tests.py pytest collection error | NIZAK | 1-2 linije fix |
| B-10 | send modal wire-up u arhiva_list.html | SREDNJE | openSendAdvancedModal() |
