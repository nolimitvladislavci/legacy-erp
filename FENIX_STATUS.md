# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-14 (Dan 48), commit 5ea4e6f1 — KORAK 7 Test Coverage ✅

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
Tests:          2,319 collected (pytest)
Commits:        949

=== QUALITY ===
Broad catches:  612 (bilo 3,598) = -83%
Ruff errors:    0 (bilo 4,649) = -100% ✓
Ruff format:    1,962 files formatted ✓
Pre-commit:     ruff lint + format + django check ✓
mypy:           configured + django-stubs, clean on core/ ✓
Django check:   0 issues ✓

=== TESTING ===
pytest:         2,319 tests collected, 0 collection errors ✓
pytest-django:  installed, conftest.py with fixtures ✓
pytest-cov:     installed, .coveragerc configured ✓
Test settings:  core/settings_test.py (bypass PgBouncer) ✓
Test DB:        test_fina_connect (PgBouncer configured) ✓
Smoke tests:    core/tests_smoke_views.py ✓
Critical path:  515 tests passing (login, invoice, POS, company switch) ✓
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
**Cilj:** Svaki klijentski dodir ima test.
**Status:** GOTOVO — 2026-04-14

### Što je napravljeno:
- **Novi test fileovi:** accounts/tests/ (login flow + company switch), invoicing/tests/test_invoice_critical.py, pos/tests/test_pos_critical.py
- **Kritični putevi testirani:** login/password, PIN auth, anonymous redirect, invoice CRUD + client portal (accept/reject), POS bon status + fiscal mock, company switch + session
- **OIB validacija:** Popravljen ISO 7064 Luhn-10 u 15+ test fileova (99988877766→99988877762, 12345678901→12345678903, itd.)
- **HTTPS u testovima:** Dodan `secure=True` svim HTTP test requestima (SECURE_SSL_REDIRECT=True u produkciji)
- **Bugovi nađeni i popravljeni:**
  * `pos/services/checkout.py`: negativna količina clamped na 0 (sigurnosni propust)
  * `pos/views_v2.py`: fiscalize_receipt() pozvan s nepostojećim kwargom naknadna_dostava
  * `invoicing/fiscal_rules.py`: NoneType guard za invoice bez firme
  * `documents/signals.py`: Decimal cast za total usporedbu
  * `core/audit.py`: transaction.atomic() savepoint + DB existence check za user FK
  * `einvoice/signals.py`: guard za invoice bez firme
  * `invoicing/signals.py`: guard za invoice bez firme + Decimal cast

### Rezultat:
```
Coverage: 40.3% (cilj: >40%) ✅
Tests passing: 515 (od kojih 29 kritičnih happy+error path)
Commits: 7 bug fix + 1 test commit
```

---

## KORAK 8 — LOAD TEST ⬅ TRENUTNO AKTIVAN
**Cilj:** 50 konkurentnih korisnika bez pada.
```
[ ] k6 ili locust scenarij: login → dashboard → invoice → switch company
[ ] 50 VU, 10 minuta
[ ] P95 < 3s, 0 x 5xx
[ ] Ako pada: profile → fix → ponovi
```
✅ Gotovo kad: Load test report zeleni.

---

## KORAK 9 — SECURITY HARDENING
**Cilj:** Nema poznatih ranjivosti pri ulasku klijenata.
```
[ ] python manage.py check --deploy → 0 upozorenja
[ ] Rate limiting: login, AI endpoint, PDF, API
[ ] GDPR audit log za company switch
[ ] OWASP Top 10 checklist
```
✅ Gotovo kad: Security checklist = sve zeleno.

---

## KORAK 10 — ONBOARDING PROVJERA
**Cilj:** Nova firma → aktivni korisnik za < 30 minuta bez tehničke pomoći.
```
[ ] Registration wizard: novi korisnik, cijeli flow
[ ] Company setup: OIB, IBAN, logo, fiskalizacija
[ ] Prva faktura → pošalji → kupac prihvati
[ ] POS: prvi bon bez greške
[ ] Dokumenti: upload → AI → arhiva
```
✅ Gotovo kad: Netko tko nikad nije vidio platformu prođe za < 30 min.

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
| 8 Load test | 🔄 AKTIVAN | 0% |
| 9 Security | ⏳ na redu | — |
| 10 Onboarding | ⏳ na redu | — |
| 11 Beta | ⏳ na redu | — |
| 12 EU kampanja | ⏳ na redu | — |

---

## AWS BEDROCK STATUS — 14.04.2026.

### Što je gotovo
- AWS account: 659220242591 (Limit-connect)
- Credentials u .env: ✅
- Modeli AUTHORIZED: ✅
  - mistral.devstral-2-123b (Trojstvo 3. glasač)
  - eu.mistral.pixtral-large-2502-v1:0 (Invoice OCR)
- Bedrock client kod: ✅ core/deepseek_client.py

### Privremeni blokator
Novi AWS account ima hardkodirani dnevni token limit.
**Resetira se sutra (15.04.2026. ponoć UTC).**
Nema potrebe za ručnom akcijom.

### Od sutra
- Trojstvo dobiva 3. glasača (Devstral 123B)
- Pixtral čita skeniranejakture iz slike → JSON
- Sve ostaje GDPR compliant (eu-central-1)

---

# VIZIJA 2027 — TRI SMJERA
**Datum: 14.04.2026. | Izvor: DeepSeek analiza + Sonnet procjena**

---

## 1. INVISIBLE UI — WhatsApp kao primarno sučelje

**Koncept:** Korisnik šalje sliku/poruku WhatsApp → sustav reagira, bez dashboarda.

**Što već imamo:**
- WhatsApp WAHA integration ✅
- Pixtral vision model (sutra) ✅
- Stolarija model (prozori, vrata) ✅
- Celery async ✅

**Što nedostaje (2-3 sprinta):**
- Intent parser: WhatsApp poruka → tip akcije (nalog/upit/slika)
- WhatsApp → Pixtral → Stolarija workflow
- "Stisni 1 za potvrdu" approval flow

**Pilot:** Zdenko Šoš — slika prozora → nalog kreiran → WhatsApp potvrda.
**Procjena:** 3 tjedna do MVP.

---

## 2. PREDICTIVE ARCHIVING — Arhiva koja sprječava sporove

**Koncept:** AI detektira vizualne uzorke grešaka PRIJE reklamacije.

**Što već imamo:**
- ArhivaEntry s GPS + SHA-256 + timestamp ✅
- Pixtral vision (sutra) ✅

**Što nedostaje (kompleksno):**
- Cross-job pattern detection (usporedba slika s više gradilišta)
- Risk scoring model (85% reklamacija = što točno?)
- Nije sprint — to je ML projekt

**Realna procjena:** Faza 3, Q3 2026. Pilot na Viskovic Bau.
**Upozorenje:** Ne podcijeniti kompleksnost. Pixtral čita jednu sliku dobro.
Usporedba 50 slika s 5 gradilišta = drugačiji problem.

---

## 3. AUTONOMOUS DEVOPS — Portal koji se sam popravlja

**Koncept:** Agent nađe bug → popravi u branchu → WhatsApp "stisni 1 za deploy".

**Što već imamo:**
- Trojstvo Beat ✅
- CC Code autonomni executor ✅
- Git workflow ✅
- WhatsApp approval ✅

**Što nedostaje (1 sprint):**
- "Approval flow" task u Celeryju
- Git branch kreiranje iz agenta
- WhatsApp "1=deploy, 2=odbaci" parser
- Staging environment provjera

**Ovo je NAJBLIŽI cilj od tri.** Infrastruktura postoji.

---

## LATENCIJSKI ŠOK — Upozorenje (kritično)

Sve AI pozive staviti u Celery. NIKAD sync AI call u web requestu.

```python
# ZABRANJENO (blokira user):
def my_view(request):
    result = deepseek_direct(...)  # ← blokira 2-5 sekundi
    return JsonResponse(result)

# ISPRAVNO:
def my_view(request):
    task = deepseek_analyze_task.delay(data)
    return JsonResponse({"task_id": task.id, "status": "processing"})
# Frontend polira /task-status/{id}/ svakih 2s
```

**Provjera:** Koliko direktnih AI poziva ima u views.py?
→ CC Code KORAK 8 mora auditirati ovo.

---

## PRIORITETI (redoslijed nije slučajan)

1. **KORAK 7** — Test coverage 40%+ (imunološki sustav)
   Bez toga autonomni agenti ruše sustav.

2. **Invisible UI MVP** — WhatsApp → Pixtral → Stolarija
   Zdenko kao pilot. 3 tjedna.

3. **Autonomous DevOps** — "Stisni 1 za deploy"
   Infrastruktura postoji, treba 1 sprint.

4. **Predictive Archiving** — Q3 2026.
   Kompleksno, ne žuriti.

