# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-14 (Dan 48), commit c74c539f — KORAK 10 Onboarding Provjera ✅

---

## SESIJA LOG — Za praćenje bez dupliciranja
> Svaki agent (Sonnet/CC/Gemini) upisuje na početku i kraju sesije.
> Format: `DATUM | AGENT | KORAK | STATUS | COMMIT`

| Datum | Agent | Fokus | Rezultat | Commit |
|-------|-------|-------|----------|--------|
| 2026-04-14 | Sonnet+CC | Korak 1-7 | Inventura, audit, standardi, test coverage | 5ea4e6f1 |
| 2026-04-14 | Sonnet+CC | Korak 8 | Load test: 50VU, P95=850ms, 0 failures | f46bd567 |
| 2026-04-14 | Sonnet+CC | Umbrella patch | CompanyMiddleware — 30+ modula popravljeno | a5e021e2 |
| 2026-04-14 | Sonnet | Korak 9 init | DeepSeek uplata potvrđena. Arhiva×komitent flow analiza. | — |
| 2026-04-14 | CC Code | Korak 9 | Security: Django 5.1.15, rate limit, GDPR audit log, pip-audit 44→2 CRITICAL | b04ec43a |
| 2026-04-14 | Sonnet | Korak 10 analiza | Login flow identificiran: Force2FAMiddleware bloker. CSRF debug. Login URL /hr/login/. | 7541a107 |
| 2026-04-14 | CC Code | Korak 10 | 9 bugova popravljeno, 21/21 smoke testovi zeleni. Svih 5 checkova prošlo. | c74c539f |
| 2026-04-14 | Sonnet | Korak 10 potvrda | CC rezultati verificirani. FENIX ažuriran. Sljedeće: Korak 11 Beta. | c74c539f |

### Kako upisati
```
Početak sesije: pročitaj zadnji red tablice — to je tvoj kontekst
Kraj sesije:    dodaj red + git log --oneline -1 za commit hash
Nije bitno biti opširan — samo datum, agent, fokus, rezultat, commit
```

---

## OCJENE

| Sesija | Ocjena | Delta | Ključno |
|--------|--------|-------|---------|
| Baseline | **6.9** | — | Prva mjerenja |
| Val 1 | **7.75** | +0.85 | Exception refactoring |
| Val 2 | **8.2** | +0.45 | Abstract, i18n, ORM |
| Val 3 | **8.4** | +0.20 | Ruff, CI/CD, API docs |
| Val 4 | **9.2** | +0.80 | Sentry, Vite, mypy, pre-commit |
| Val 5 | **9.5** | +0.30 | Ruff 0, pytest infra, OpenAPI 100% |

## DASHBOARD
```
=== CODE ===
Python LoC:     ~299K
Test LoC:       59,825
Tests:          2,340 collected (pytest) — +21 onboarding smoke
Commits:        952

=== QUALITY ===
Broad catches:  612 (bilo 3,598) = -83%
Ruff errors:    0 (bilo 4,649) = -100% ✓
Ruff format:    1,962 files formatted ✓
Pre-commit:     ruff lint + format + django check ✓
mypy:           configured + django-stubs, clean on core/ ✓
Django check:   0 issues ✓

=== TESTING ===
pytest:         2,340 tests collected, 0 collection errors ✓
pytest-django:  installed, conftest.py with fixtures ✓
pytest-cov:     installed, .coveragerc configured ✓
Test settings:  core/settings_test.py (bypass PgBouncer) ✓
Test DB:        test_fina_connect (PgBouncer configured) ✓
Smoke tests:    core/tests_smoke_views.py ✓
Critical path:  536 tests passing (login, invoice, POS, company switch, onboarding) ✓
Coverage:       40.3% na pos/ + invoicing/ + accounts/ ✓

=== SECURITY ===
csrf_exempt:    45 (bilo 147) = -69%, all documented
Sentry:         LIVE (SDK 2.55, Django+Celery)
Auth:           1,924 decorators, 4-layer

=== PERFORMANCE ===
select_related: 1,221 (bilo 951) = +28%
exists():       436
count()>0:      0 (eliminated) ✓
Vite build:     18 assets, 967ms, minified+gzipped

=== I18N ===
5 languages:    100% coverage, 0 empty, 0 fuzzy ✓

=== API ===
ViewSets:       27/27 tagged with @extend_schema_view ✓
OpenAPI schema: validates ✓
Swagger UI:     /api/docs/ LIVE ✓
ReDoc:          /api/redoc/ LIVE ✓

=== INFRASTRUCTURE ===
CI/CD:          GitHub Actions (lint→test→deploy)
Frontend:       Vite + terser (node v20)
Monitoring:     Sentry production
API docs:       /api/docs/ (Swagger) + /api/redoc/
```

## REMAINING FOR 10/10
- App consolidation (89 custom apps — all wired, consolidation is architectural)
- Staging environment

---

## FENIX RAZVOJNA PRAVILA (živući dokument)

### PRAVILO 1 — Nema zakrpa, samo pravi fix
Svaka promjena mora biti na globalnoj razini. Lokalni `<style>` blokovi, one-off template hacks, copy-paste koda — nisu prihvatljivi.
- Globalni CSS → `fenix-ui.css` (`.entity-link`, `.col-actions`, `.btn-action`)
- Globalni Python pattern → shared util, middleware, mixin
- Zakrpa = žuti karton + odmah refaktor na globalnu razinu

### PRAVILO 2 — Settings i model choices moraju biti sinkronizirani
`settings.LANGUAGES` i `preferred_language choices` u modelu — uvijek isti skup.
Kad se dodaje novi jezik u settings, odmah migracija na choices. Bez iznimke.
Kršenje = migration bug koji se otkrije tek kad korisnik ne može odabrati jezik.

### PRAVILO 3 — Template promjene zahtijevaju gunicorn reload
`cached.Loader` je aktivan u produkciji. Svaki commit koji mijenja template mora završiti s `systemctl reload gunicorn-fina`. CI/CD to radi automatski — ručni deploji ne smiju zaboraviti.

### PRAVILO 4 — `--preload` zabranjeno u gunicorn service fajlu
`--preload` zaključava kod u master procesu — template promjene, novi kod, migracije nisu vidljive workerima bez restarta mastera. Zamijenjen s `ExecReload=SIGHUP` + graceful reload.

### PRAVILO 5 — Nikad conditional import unutar try/except bloka
Ako `except` klauzula referira model (npr. `Company.DoesNotExist`), taj model mora biti importan **prije** `try` bloka — ne uvjetno unutar grana. Python scoping: varijabla definirana samo u jednoj `if` grani nije dostupna u `except`.

```python
# ZABRANJENO:
try:
    if uvjet:
        from companies.models import Company
        ...
except Company.DoesNotExist:  # puca ako uvjet nije bio True
    ...

# ISPRAVNO:
from companies.models import Company  # uvijek na vrhu
try:
    ...
except Company.DoesNotExist:
    ...
```

### PRAVILO 6 — QR kodovi uvijek kroz /qr/ endpoint
Nikad `api.qrserver.com` ili bilo koji vanjski QR servis.
Endpoint: `GET /qr/?data=URL&size=200&color=000000&bg=ffffff`
Template: `{% load qr_tags %}` → `{% qr_url data %}`, `{% qr_img data %}`, `{% qr_b64 data %}`
PDF/email: `from core.qr_views import qr_base64`
Razlozi: HTTPS garantiran, radi offline, 24h cache, nema ovisnosti o trećoj strani.

### PRAVILO 7 — Svaka nova javna ruta mora biti u RouteRegistry
DEFAULT_LEVEL = AccessLevel.COMPANY — sve što nije registrirano blokira se za anonimne korisnike.
Javne rute (bez logina): dodati u ROUTE_REGISTRY kao AccessLevel.PUBLIC
Rute s loginom bez kompanije: AccessLevel.AUTHENTICATED
Propust = 302 redirect za vanjske korisnike bez greške u logu (GracefulErrorMiddleware hvata).

### PRAVILO 8 — OIBi u testovima moraju biti validni (ISO 7064 Luhn-10)
Nikad izmišljene OIB vrijednosti u test fixtureima. Koristiti validiranu listu ili generator:
```python
def make_valid_oib(base10):  # base10 = 10 znamenki
    digits = [int(c) for c in base10]
    product = 10
    for d in digits:
        s = (product + d) % 10
        if s == 0: s = 10
        product = (s * 2) % 11
    return base10 + str((11 - product) % 10)
```
Poznati validni OIBi za testove: 12345678903, 98765432106, 11111111119, 22222222226, 55555555551, 66666666664

---

# ZLATNI KOD — PLAN PRODUKCIJE
**Donesen: 14.04.2026. | Status: AKTIVAN**

> Cilj: Funkcionalan, stabilan kod bez grešaka → 100+ firmi u produkciji → #1 ERP za malo poduzetništvo u EU
> Koraci su redni, ne datumski. Sljedeći kreće čim prethodni dobije ✅

---

## KORAK 1 — INVENTURA RUŠENJA ✅
✅ Gotovo

## KORAK 2 — FIELD NAME AUDIT ✅
✅ Gotovo

## KORAK 3 — ROUTEREGISTRY KOMPLETNI PROLAZ ✅
✅ Gotovo

## KORAK 4 — MIDDLEWARE AUDIT ✅
✅ Gotovo

## KORAK 5 — 504 ELIMINACIJA ✅
✅ Gotovo

## KORAK 6 — GLOBALNI STANDARDI (QR + CSS + URL) ✅
✅ Gotovo

---

## KORAK 7 — CRITICAL PATH TEST COVERAGE ✅
**Status:** GOTOVO — 2026-04-14

### Rezultat:
```
Coverage: 40.3% (cilj: >40%) ✅
Tests passing: 515 (od kojih 29 kritičnih happy+error path)
Commits: 7 bug fix + 1 test commit
```

---

## KORAK 8 — LOAD TEST ✅
**Status:** GOTOVO — 2026-04-14

### Rezultat:
- 1,353 requests | **0 failures** | **0 x 5xx** ✅
- P95 = **850ms** (cilj <3000ms) ✅
- Tool: Locust 2.43.3, 50 VU, 10 min, HTTPS produkcija

---

## KORAK 9 — SECURITY HARDENING ✅
**Status:** GOTOVO — 2026-04-14 | Commitovi: cc57e687, b04ec43a

### Što je napravljeno:
- Django 5.1.6 → 5.1.15 (12 CVE-a)
- Rate limiting za auth. korisnike (AI: 10/min, PDF: 20/min, API: 60/min)
- GDPR audit log za company switch
- pip-audit: 44 → 2 CRITICAL preostali (deep-translator bez fixa, django-allauth nekorišten)

---

## KORAK 10 — ONBOARDING PROVJERA ✅
**Cilj:** Nova firma → aktivni korisnik za < 30 minuta bez tehničke pomoći.
**Status:** GOTOVO — 2026-04-14 | commit c74c539f

### 9 bugova popravljeno:
```
Bug#1: register_step4 IntegrityError → 500 (dupli OIB/email → sad jasna poruka)
Bug#2: register_quick UserProfile signal conflict → IntegrityError
Bug#3: register_quick Subscription import nepostojeći model
Bug#4: setup_wizard NameError (get_user_company ne importano → 500 pri svakom POST-u)
Bug#5: setup_wizard_company akceptira nevažeći HR OIB ("123" prolazilo)
Bug#6: setup_wizard_contact string FK dodjela website polju
Bug#7: portal_accept invoice.notes → invoice.note (crash pri prihvaćanju ponude)
Bug#8: get_managed_companies .first().company bez None guard
Bug#9: documents/views_arhiva.py isti None guard pattern
```

### Smoke test suite: 21/21 passed ✅
```
[✅] Registration wizard: novi korisnik, cijeli flow
[✅] Company setup: OIB, IBAN, contact, fiskalizacija
[✅] Prva faktura → PDF → kupac prihvati (client portal)
[✅] POS: terminal + blagajnik + onboarding wizard
[✅] Dokumenti: upload → SHA-256 hash → arhiva
[✅] Error handling: svi 500 pretvoreni u jasne greške
```

---

## KORAK 11 — BETA (3-5 firmi)
**Cilj:** Stvarni korisnici, kontrolirani uvjeti.
```
[ ] Odaberi 3-5 firmi iz čekaonice (različite djelatnosti)
[ ] Onboarding uz asistenciju
[ ] 2 tjedna aktivnog korištenja
[ ] Svaki bug → odmah fix
[ ] NPS > 8 od svih beta klijenata
```
✅ Gotovo kad: 3 aktivna klijenta, 0 kritičnih bugova 7 dana.

---

## KORAK 12 — PRODUKCIJA + EU KAMPANJA
**Cilj:** Vrata otvorena, sustav drži, EU tržište.
```
[ ] Automatski onboarding (bez ručne asistencije)
[ ] Pricing aktiviran (18 planova)
[ ] Viskovic Bau DE referenca aktivna
[ ] PR: "Made in Croatia, #1 ERP small business EU"
[ ] LinkedIn kampanja s konkretnim brojevima
```
✅ Gotovo kad: 10 plaćajućih klijenata, 2+ u DE.

---

## GORIVO (praćenje napretka)
| Korak | Status | Postotak |
|-------|--------|----------|
| 1 Inventura | ✅ GOTOVO | 100% |
| 2 Field audit | ✅ GOTOVO | 100% |
| 3 RouteRegistry | ✅ GOTOVO | 100% |
| 4 Middleware | ✅ GOTOVO | 100% |
| 5 504 eliminacija | ✅ GOTOVO | 100% |
| 6 Globalni standardi | ✅ GOTOVO | 100% |
| 7 Test coverage | ✅ GOTOVO | 100% |
| 8 Load test | ✅ GOTOVO | 100% |
| 9 Security | ✅ GOTOVO | 100% |
| 10 Onboarding | ✅ GOTOVO | 100% |
| 11 Beta | ⏳ SLJEDEĆE | — |
| 12 EU kampanja | ⏳ na redu | — |

---

## AI SERVISI STATUS

### DeepSeek
- Direktni API: **AKTIVAN** ✅ (uplata $5.30 — 2026-04-14, PayPal 1B3286619K296815M)
- Model: deepseek-chat (DeepSeek-V3)
- Fallback: Haiku (automatski ako DeepSeek pada)

### AWS Bedrock
- Account: 659220242591 (eu-central-1, GDPR compliant)
- Devstral 123B: authorized, token limit reset 15.04.2026. ponoć UTC
- Pixtral invoice OCR: authorized, isti reset
- Kod: core/deepseek_client.py

---

## VIZIJA 2027 — TRI SMJERA
**Datum: 14.04.2026.**

### 1. INVISIBLE UI — WhatsApp kao primarno sučelje
Pilot: Zdenko Šoš — slika prozora → nalog → WhatsApp potvrda. 3 tjedna do MVP.

### 2. PREDICTIVE ARCHIVING — Q3 2026.
Cross-job pattern detection. ML projekt. Ne žuriti.

### 3. AUTONOMOUS DEVOPS — Najbliži cilj
"Stisni 1 za deploy" — infrastruktura postoji, treba 1 sprint.

---

## OPERACIJA: UMBRELLA COMPANY RESOLUTION — Dan 48
**GOTOVO.** CompanyMiddleware patch — 30+ modula popravljeno jednim commitom (a5e021e2).

### Stanje baze (2026-04-14)
```
Aktivnih firmi:     101  |  Umbrella djece:  81
Aktivnih korisnika:  56  |  Faktura:     15,330
Arhiva dokumenata: 20,373 |  Commits:    952+
Journal entries:  10,732  |  Workspaces:     36
```

---

## PRAVILO 9 — Bez datuma izvršenja, samo redoslijed

Svaki nalaz, task i poboljšanje ima:
- **Datum kreiranja** (kad je nađeno)
- **Redoslijed izvršenja** (prije čega mora biti gotovo)
- **Nikad datum izvršenja** — izvršava se čim dođe red ili čim se dotičeni modul otvori

---

## BACKLOG — Redoslijed bez datuma

| # | Nalaz | Kreiran | Ozbiljnost | Uvjet za izvršenje |
|---|-------|---------|------------|-------------------|
| B-01 | `user_edit` — company isolation (samo superadmin može editirati bilo kojeg korisnika bez company provjere) | 2026-04-14 | SREDNJE | Kad company_admin dobije self-service |
| B-02 | `trojstvo_task.py` — `suggestion_id` type guard (None/string ne pada elegantno) | 2026-04-14 | NIZAK | U istom sprintu kad se dotakne trojstvo_task.py |
| B-03 | `accounts/views.py user_edit` — dodati company scope za budući company_admin self-service | 2026-04-14 | SREDNJE | Isti kao B-01 |

---

## MEMIO.PET — KORAK A: END-TO-END LIVE (Dan 48)

### Stanje PRIJE
- DomainGate blokirao sve memio_pet rute na memio.pet domeni
- /registracija/ → 302 redirect
- /pas/{id}/ → 302 redirect  
- XSS test podatak u bazi

### Fix
- DomainGate: 22 memio_pet ruta dodano u whitelist za memio.pet domenu
- XSS test životinja obrisana iz memio_pets baze

### End-to-End Test — SVE ZELENO
```
memio.pet/                         → 200 ✅ Landing page
memio.pet/registracija/            → 200 ✅ Registracija uzgajivača
memio.pet/prijava/                 → 200 ✅ Login
memio.pet/pas/191031000312345/     → 200 ✅ Profil psa (Rex, Labrador)
memio.pet/pas/{id}/qr/             → 200 ✅ QR PNG (2.3KB, image/png)
memio.pet/uzgajivac/{uuid}/        → 200 ✅ Profil uzgajivača
memio.pet/udomljavanje/            → 200 ✅ Životinje za udomljavanje
memio.pet/barf/                    → 200 ✅ BARF tržnica
memio.pet/krematoriji/             → 200 ✅ Direktorij krematorija
memio.pet/hoteli/                  → 200 ✅ Direktorij hotela
memio.pet/privatnost/              → 200 ✅ Privacy policy
```

### Za 2 uzgajivača — linkovi:
- Registracija: https://memio.pet/registracija/
- Primjer profila: https://memio.pet/pas/191031000312345/
- QR za Rex-a: https://memio.pet/pas/191031000312345/qr/

### Baza (memio_pets):
- 2 životinje (Rex + Vučko memorial)
- 13 profila (hoteli, krematoriji, vlasnici, OPG)

---

## MEMIO EKOSISTEM — Koraci A-D GOTOVI (Dan 48)

### KORAK A: memio.pet LIVE ✅
- DomainGate: 22 ruta whitelistano za memio.pet domenu
- End-to-end: 12/12 ruta testirano (landing, registracija, profil, QR, BARF, udomljavanje...)
- XSS test podatak očišćen iz baze
- Link za uzgajivače: https://memio.pet/registracija/

### KORAK B: Azil Bridge ✅  
- NO LIMIT udruga: is_shelter=true, shelter_sponsor aktiviran
- Demo Azil: is_shelter=true, pushat u memio_pets
- Auto-sync signal: Company.save(is_shelter=true) → BreederProfile(shelter) u memio_pets
- 2 shelter profila LIVE na memio.pet

### KORAK C: Livestock SyncLink ✅
- farm_animal_uuid: UUID referenca na memio_farm bazu (ne FK, cross-DB safe)
- memio_pet_profile_id: UUID referenca na memio_pets bazu
- public_farm_url + public_pet_url properties
- Migracija: livestock.0008_add_farm_pet_synclink

### KORAK D: memio.world Encryption ✅
- MEMIO_WORLD_FERNET_KEY: zasebni AES ključ (ne dijeli se s ERP ni memio_pets)
- WorldEncryptedField: transparentni AES-128-CBC za TextField
- Enkriptirano: TimeCapsule.message, MemoryVault.description, FamilyStory.content,
  MemoryEntry.content, ChildProfile.guardian_emails
- Migracija: memio_world.0003_encrypt_sensitive_fields
- Verifikacija: encrypt→decrypt roundtrip OK

### Tri odvojene baze — tri odvojena ključa
```
fina_erp       → FERNET_KEY            (ERP podaci)
memio_pets     → MEMIO_PETS_FERNET_KEY (PII ljubimaca/vlasnika)
memio_world    → MEMIO_WORLD_FERNET_KEY (digitalne uspomene, 18yr)
```
