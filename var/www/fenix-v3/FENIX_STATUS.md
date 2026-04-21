# FENIX V3 — Status 2026-04-21 (Dan 55)
> Zadnji update: 2026-04-21, commit e23eb53

---

## ⚡ ARHITEKTURA SERVERA — UVIJEK AKTUALNO

| | Fenix V3 (NOVO) | Stari ERP |
|---|---|---|
| Domena | `limit-connect.com` ✅ LIVE | `fina-connect.online` ✅ LIVE |
| Dir | `/var/www/fenix-v3/` | `/var/www/fina-connect/` |
| Servis | `gunicorn-fenix-v3` port **8001** | `gunicorn-fina` unix socket |
| Baza | `fenix_v3_clean` direktno **:5432** | `fina_erp` PgBouncer **:6432** |
| CONN_MAX_AGE | **60** (direktna veza) | **0** (PgBouncer obavezno!) |
| Redis | `127.0.0.1:6379`**/4** | `127.0.0.1:6379`**/1** |
| Venv | `/var/www/fenix-v3/venv/bin/python` | `/var/www/fina-connect/venv/bin/python` |

### Baze (Stari ERP — fina-connect):
```
fina_erp     → PgBouncer :6432  (CONN_MAX_AGE=0 obavezno!)
memio_pets   → direktno  :5432
memio_farm   → direktno  :5432
memio_world  → direktno  :5432
```

### Redis mapping (ne miješati!):
```
/1 → fina-connect Django cache + Celery
/2 → fina-connect Celery broker (backup)
/3 → fina-connect Celery results
/4 → fenix-v3 Celery broker ← odvojeno namjerno!
```

### Servisi:
```
systemctl restart gunicorn-fenix-v3.service   # fenix-v3
systemctl restart gunicorn-fina.service        # stari ERP
systemctl reload nginx                         # nginx
```

> Detalji → `FENIX_ZAKON.md` Zakon 13 | `FENIX_PRAVILA.md` | `CLAUDE.md`

---

## INSTALLIRANI MODULI

| App | Status | Napomena |
|-----|--------|----------|
| accounts | ✅ LIVE | UserProfile, CompanyMembership, UserType (business/child/guest) |
| companies | ✅ LIVE | Company, CompanyModuleConfig (Cluster Gate) |
| invoicing | ✅ LIVE | Invoice, InvoiceLine, PDF, fiskalizacija HR + PEPPOL B2G |
| arhiva | ✅ LIVE | ArhivaEntry, FenixScan OCR, AI proposal + Camera PermManager |
| pos | ✅ LIVE | POS Terminal, SmartPricing, NFC, Ghost Receipt, Free Tier |
| stolarija | ✅ LIVE | MjerenjeProizorVrata, Ponuda, Montaža, Garancija |
| accounting | ✅ LIVE | JournalEntry, kontni plan, DATEV export |
| ai_cockpit | ✅ LIVE | AIGateway (Haiku/DeepSeek/Gemini), TrojstvoEngine, Voice Input |
| employees | ✅ LIVE | Employee, HR+DE payroll, SEPA, JOPPD, TimeLog, DataVault |
| sentinel | ✅ LIVE | SentinelAlert, SentinelScan, TemporalLedgerScore, AuditChain |
| sentinel (advisor) | ✅ LIVE | EUFund, EUMatch, ObrascInstance, KalendarObveza |
| sentinel (ured) | ✅ LIVE | DigitalniUred, UredKonverzacija, UredPoruka |
| evalidator | ✅ LIVE | ChainBlockPOE, javni REST API /api/verify/<token>/ (eIDAS Art.41) |
| agriculture | ✅ LIVE | OPG javna stranica — world-class landing (webshop+edu+ChainBlock) |
| booking | ✅ LIVE | Service, Appointment, public booking flow — i18n 100% (hr/de/en) |

---

## MIDDLEWARE STACK

```
CompanyMiddleware          → request.company iz sessije
ModuleGateMiddleware       ← NOVO: per-company cluster vidljivost
ChildProtectionMiddleware  → child user_type ne ulazi u /hr/
SecurityHeadersMiddleware  → security headers na svaki response
AuditMiddleware            → log svaki mutirajući request
PerformanceMiddleware      → Server-Timing header
```

---

## CLUSTER — MODULE VISIBILITY

Svaka firma može imati selektivnu vidljivost modula:
- Admin: `/__admin__/` → Company → "Cluster — Vidljivost modula"
- Checkbox po modulu (8 modula)
- Prazno = svi moduli dostupni (permissive default)
- `ModuleGateMiddleware` blokira URL ako modul nije aktivan
- Blocked GET → `core/module_blocked.html` (403)
- Blocked HTMX → JSON `{"error": "...", "module": "pos"}` (403)

---

## KONTEKST SESIJE (2026-04-21)

Sesija je pokrila 4 velika zadatka:

**1. i18n 100% coverage (hr/de/en)**
Systematično preneseni svi untranslated stringovi (762 ukupno). Booking i evalidator
templates dobili `{% load i18n %}` + `{% trans %}` omotače. DE i EN .po fajlovi
popunjeni u dva prolaza (162 + 594 + 2 edge cases). `compilemessages` ispravan,
0 untranslated stringova u oba jezika.

**2. Globalni Camera Permission Manager**
Kreiran `/static/js/fenix-permissions.js` (Alpine.js store `fenixPerms`).
Sticky bottom bar u `base.html` — prikazuje se kad ima problema s kamerom/lokacijom.
Torch s AmbientLightSensor + video luma fallback (auto-off na 80 lux).
Upload template (`arhiva/upload.html`) prešao s generičke poruke "nema kamere"
na actionable gumbe po tipu greške (NotAllowedError → "Dopusti pristup", itd.).

**3. ChainBlock javni REST API**
`/api/verify/<seal_token>/` (GET, bez autentikacije) — vraća JSON s `verified`,
`tsa_timestamp`, `block_hash`, `issuer`, `doc_count`, standard eIDAS Art. 41 + ZED HR.
`ChainBlockPublicVerifyAPI(View)` dodan u `evalidator/views.py`, URL u `config/urls.py`.
Commit zabetoniран, live na produkciji.

**4. OPG Kruljac Sladana — world-class landing page**
Kompletna rekonstrukcija `templates/agriculture/opg_public.html` (933 linije).
Dark agri theme (Space Grotesk, --bg:#070d08, --green, --gold).
9-sekcija sticky nav: WEBSHOP (primarno, 6 proizvoda + order modal),
EDUKACIJE (5 paketa + booking forma), FARMA (Lely A5 specs, herd, energy),
EU PROJEKTI (3 KPI bar + cards), CHAINBLOCK (curl example + live verify links),
BURZA (live fetch /api/burza/ svakih 15min), KONTAKT + FOOTER.
View context proširen: webshop_products, edu_paketi, chainblocks, latest_seal,
total_ha, total_animals. HTTP 200 potvrđen. Commit: e23eb53.

**Open threads:**
- Order forma i edu booking forma su front-end simulacija — backend endpoint treba
- OPG proizvodi su hardcodirani u viewu — razmotriti OPGProduct model ili retail.Product
- Crontab backup: `0 3 * * * /var/www/fenix-v3/_scripts/backup_pg.sh` (Ivan ručno)
- QA_PASS env var za journey_runner.py (Ivan ručno: `export QA_PASS=lozinka`)

---

## SESIJA LOG

| Datum | Agent | Fokus | Commit |
|-------|-------|-------|--------|
| 2026-04-21 | CC Sonnet | i18n 100%, Camera PermMgr, ChainBlock API, OPG Landing | e23eb53 |
| 2026-04-18 | CC Sonnet | Domain split + Cluster Gate (fina-connect) | e6943688 |
| 2026-04-18 | CC Sonnet | Cluster Gate fenix-v3 (ModuleGateMiddleware + admin) | 98d31d2 |
| 2026-04-18 | CC Sonnet | FENIX SENTINEL bugfixes (4 buga, ZAKON) | cca186d |
| 2026-04-18 | CC Sonnet | FENIX SENTINEL implementacija (14 modela, 8 Celery) | b67f46f |
| Ranije | CC Sonnet | 71/71 planova DONE (POS, Arhiva, Stolarija, Employee...) | — |

---

## PRIORITETI

```
1. OPG order forma backend (webshop narudžba → email/DB)
2. OPG edu booking → spojiti na booking modul API
3. PLAN_084 — InvoiceLine VAT fields za pravi PDV izračun (trenutno STUB)
4. Testirati cluster gate u browseru (login → /hr/pos/ → mora proći)
5. Marija onboarding test (POS free tier, arhiva flow)
```

---

## PRAVILA (kopija iz FENIX_ZAKON.md)

1. Čitaj field nazive iz models.py PRIJE pisanja koda
2. Nikad `Company.active.first()` bez membership provjere
3. `venv/bin/python manage.py check` = 0 errors nakon svakog commita
4. Commit format: `tip(modul): opis`
5. Stub > lažni podaci (ZAKON 2)
6. Dijete ne ulazi /hr/ (ZAKON 3)
7. Lokalno vrijeme, ne UTC (ZAKON 5)
8. Memory chunking za bulk querysets (ZAKON 6)
