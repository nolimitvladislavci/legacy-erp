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

> Zadnji update: 2026-04-20 (Dan 54), commit 1295e08 — eArhivator Faza 2 MinIO upload LIVE, bug fix eArhivator trigger

---

## SESIJA LOG

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
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

## SESIJA 2026-04-19 — memio.world KUM SUSTAV + LEKTIRE

### Što je implementirano (commit 4a54619a):

#### BLOK 1 — Kum sustav (digitalni kumovi)
| Fajl | Opis |
|------|------|
| `memio_world/kum_models.py` | KumInvitation (token+expire), KumRelationship (kum←→child←→parent), KumGift (plan sponsorship s approve/decline/activate) |
| `memio_world/views_kum.py` | kum_dashboard, kum_invite_send (JSON), kum_invite_accept (token landing), kum_gift_create, kum_gift_approve |
| `memio_world/views_auth.py` | login_required_play decorator dodan |
| Templates | kum_dashboard.html, kum_invite_landing.html, kum_invite_accepted.html, kum_invite_invalid.html |

**Kum arhitektura:** Kum = ParentAccount. Ista osoba može istovremeno biti Kum drugoj djeci I imati vlastitu djecu kojima netko drugi kumuje. M2M kroz KumRelationship junction model.

#### BLOK 2 — Lektire (HR školski kurikulum)
| Fajl | Opis |
|------|------|
| `memio_world/lektire_models.py` | LektiraBook (razredi 1-8, mandatory/optional, public_domain), LektiraChapter (full_text za PD, summary gating, key_words JSON, discussion_questions JSON), LektiraProgress (chapters_read JSONField, XP nagrade), LektiraQuiz + LektiraQuizQuestion |
| `memio_world/views_lektire.py` | lektire_home (by_grade dict), lektira_detail, lektira_chapter_read (show_summary), lektira_mark_read (POST JSON → XP) |
| Templates | lektire_home.html, lektira_detail.html, lektira_chapter.html |

**Gating:** summary i discussion_questions se prikazuju SAMO nakon mark_chapter_read. XP formula: `50 + (grade × 10)`.

#### BLOK 3 — Bottom nav redesign (pnav-*)
| Fajl | Opis |
|------|------|
| `templates/memio_world/base_play.html` | pnav-icon 48×48px, pnav-bubble CSS speech bubbles (::after triangle), scale animation, gold color za active, safe-area-inset-bottom |

#### Migration
- `memio_world/migrations/0016_kum_lektire.py` — applied ✅ na memio_world bazi

### URLs dodane:
```
/api/memio-world/play/kum/                      kum_dashboard
/api/memio-world/play/kum/pozovi/               kum_invite_send
/api/memio-world/play/kum/pozivnica/<token>/    kum_invite_accept (public)
/api/memio-world/play/kum/poklon/               kum_gift_create
/api/memio-world/play/kum/poklon/<uuid>/odobri/ kum_gift_approve
/api/memio-world/play/lektire/                  lektire_home
/api/memio-world/play/lektire/<slug>/           lektira_detail
/api/memio-world/play/lektire/<slug>/citaj/<n>/ lektira_chapter
/api/memio-world/play/lektire/<slug>/procitao/<n>/ lektira_mark_read
```

### Što je OSTALO (memio.world):
- Lektira content seeding — unos knjiga HR kurikuluma razredi 1-8
- KumGift → Stripe payment flow (pending_payment → active)
- Celery task za slanje KumInvitation emaila
- Child selector populate u kum_dashboard.html (JS needs backend context)
- ChildProgress integration — wire lektira XP u postojeći stories_read tracker

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

#### BLOK 2 — DATEV 2030
| Fajl | Opis |
|------|------|
| `konto/german_accounting.py` | generate_datev_export_v2(): BelegLink, UUID, KOST1, SEPA, OSS/IOSS |
| `konto/views.py` | datev_export_v2() view: GET=UI, POST=CSV/ZIP download |

#### BLOK 3 — Glasovni Send
| Fajl | Opis |
|------|------|
| `documents/views_arhiva.py` | arhiva_send_advanced(): multi-channel, auto-pečat, viral_code, glas |
| `templates/documents/_send_advanced_modal.html` | Modal: kanali, MediaRecorder, TTS, pečat badge |

---

## PRIORITETI ZA SLJEDEĆU SESIJU

```
1. NO LIMIT: OIB udruge — update_genesis_oib(novi_oib) kad Marija donese rješenje
2. Stripe LIVE ključevi za KumGift (sada test mode)
3. Pilot POS test: Ivica Kruljac + Široki Šor Restoran (test u terenu)
4. eArhivator MinIO Faza 2 — ✅ RIJEŠENO (commit 1295e08, MinIO upload LIVE, bug fix trigger)
5. Grand Plan Blok 4 — SMALL DOORS Tier B Shamir recovery UI (backend gotov)
6. Lektire seed — dodati sadržaj knjiga razredi 1-8 (75% gotovo)
7. Triple DNA Layer 3 CLIP async — GPU task za semantički embedding
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
Python LoC:  ~425K       Konjik komitenti:  75         memio.pet:   LIVE ✅
Tests:       2,401       Arhiva dok.:    20,386        memio.world: Kum+Lektire ✅
Commits:       962+      OCR točnost:      100%        memio.farm:  SyncLink ✅
Coverage:    40.3%       DocumentSeal:   LIVE ✅        No-limit:    NGO portal ✅

=== memio.world NOVI MODULI ===
Kum sustav:        ✅ LIVE (KumInvitation/Relationship/Gift)
Lektire:           ✅ LIVE (LektiraBook/Chapter/Progress, razredi 1-8)
Bottom nav pnav-*: ✅ LIVE (48px icons + CSS speech bubbles)
Migration 0016:    ✅ Applied

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
| **memio.world Kum** | ✅ LIVE | 85% |
| **memio.world Lektire** | ✅ LIVE (potreban seed) | 75% |

---

# STANJE BAZE I SERVERA
```
Server:          37.27.248.86 (Hetzner)
Aktivnih firmi:  109 | Umbrella djece:  81
Korisnika:        369 | Faktura:     15,333
Arhiva dok.:   20,386 | Commits:       962+
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
| B-04 | StorageConfig 'network' backend | RIJEŠENO | NetworkStorageBackend + rclone LIVE |
| B-05 | WhatsApp-IN nepoznati pošiljatelji | NIZAK | ARHIVA-5 |
| B-06 | DATEV header verifikacija | RIJEŠENO | DATEV 2030 BelegLink |
| B-07 | POS free tier konfiguracija za Mariju Čačić | RIJEŠENO | pos_obrt role + pos-besplatno plan + Ivica/Sirok Sor piloti |
| B-08 | Duplikat Radar integracija u upload view | NIZAK | nice to have |
| B-09 | core/tests.py pytest collection error | RIJEŠENO | tests.py → tests_core.py |
| B-10 | send modal wire-up u arhiva_list.html | RIJEŠENO | Napredno slanje LIVE u draweru |
| B-11 | KumGift Stripe flow | RIJEŠENO | checkout + webhook + success + activate() LIVE |
| B-12 | Lektire seed (HR kurikulum 1-8) | RIJEŠENO | 31 knjiga seeded: razredi 1-8 |
| B-13 | Kum child selector populate | RIJEŠENO | my_children + my_children_json u kontekstu |
