# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-14 (Dan 48), commit TBD — KORAK 4 Middleware Audit ✅

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
Commits:        948

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
- Test coverage measurement (need full migration of test DB — 511 migrations)
- Coverage target: 30%+ (2,319 tests exist, infrastructure ready)
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

---

# ZLATNI KOD — PLAN PRODUKCIJE
**Donesen: 14.04.2026. | Status: AKTIVAN**

> Cilj: Funkcionalan, stabilan kod bez grešaka → 100+ firmi u produkciji → #1 ERP za malo poduzetništvo u EU
> Koraci su redni, ne datumski. Sljedeći kreće čim prethodni dobije ✅

---

## KORAK 1 — INVENTURA RUŠENJA ⬅ TRENUTNO AKTIVAN
**Cilj:** Potpuni popis svih bugova, tiho preusmjeravanja i 5xx grešaka.
```
[ ] Izvuci sve GracefulErrorMiddleware redirecte (zadnjih 30 dana)
[ ] Sentry 5xx lista po modulu
[ ] Svi "return redirect('/')" za anonimne korisnike — jesu li legitimni?
[ ] OUTPUT: BUGLIST.md — bug | modul | uzrok | prioritet
```
✅ Gotovo kad: BUGLIST.md postoji, svaki red ima uzrok.

---

## KORAK 2 — FIELD NAME AUDIT
**Cilj:** Nula AttributeErrora zbog krivog imena polja.
```
[ ] Za svaki model: popis svih field-a iz models.py
[ ] Pretraži sve views + templates za mismatch
[ ] Fix, test, commit po modulu
[ ] Posebno: Invoice, POSReceipt, UserProfile, Company
```
✅ Gotovo kad: 0 novih AttributeErrora u logovima 24h zaredom.

---

## KORAK 3 — ROUTEREGISTRY KOMPLETNI PROLAZ
**Cilj:** Svaka javna ruta vraća 200 za anonimnog korisnika.
```
[x] Izvuci sve URL nazive iz svih urls.py
[x] Usporedi s RouteRegistry (permissions/route_registry.py)
[x] Svaki bez @login_required → mora biti PUBLIC/AUTHENTICATED
[x] Automatizirani smoke test: curl svaki javni URL bez sessiona
```
✅ Gotovo kad: Smoke test prolazi 100% javnih URL-a.

---

## KORAK 4 — MIDDLEWARE AUDIT
**Cilj:** Nijedan middleware ne blokira legitimnu akciju.
```
[x] Mapiraj 30 middlewara — što svaki radi, koji su SKIP_PREFIXES
[x] Sinkroniziraj exempt liste: Force2FA i ForceTCMiddleware → RouteRegistry ✓
    middleware_tc.py (TCConsentMiddleware) → mrtvi kod, uklonjen
    DomainGateMiddleware → limit-connect.com propušta sve ✓
    UserLanguageMiddleware → samo za auth usere, SKIP_PREFIXES ispravni ✓
[x] Test: anon → COMPANY rute = redirect na login ✓
    anon → PUBLIC rute = 200 ✓
    auth bez company → AUTHENTICATED rute = 200 ✓
```
✅ Gotovo kad: Test suite "anon pristupa svim javnim rutama" prolazi.

### MIDDLEWARE MAPA (30 middlewara)
| # | Middleware | Exempt strategija | Status |
|---|-----------|-------------------|--------|
| 1 | GracefulErrorMiddleware | exceptions only | ✓ |
| 2 | SecurityMiddleware | Django std | ✓ |
| 3 | WhiteLabelMiddleware | - | ✓ |
| 4 | LicenseCheckMiddleware | BYPASS_PATHS hardcoded | ✓ |
| 5 | WhiteNoiseMiddleware | static files | ✓ |
| 6 | SessionMiddleware | Django std | ✓ |
| 7 | CommonMiddleware | Django std | ✓ |
| 8 | CsrfViewMiddleware | Django std | ✓ |
| 9 | AuthenticationMiddleware | Django std | ✓ |
| 10 | DomainGateMiddleware | ALWAYS_ALLOWED + per-domain | ✓ |
| 11 | MessageMiddleware | Django std | ✓ |
| 12 | AuditMiddleware | - | ✓ |
| 13 | UserLanguageMiddleware | SKIP_PREFIXES, auth only | ✓ |
| 14 | LocaleMiddleware | Django std | ✓ |
| 15 | RolePermissionMiddleware | SKIP_PREFIXES | ✓ |
| 16 | CompanyMiddleware | - | ✓ |
| 17 | ImpersonationMiddleware | superadmin only | ✓ |
| 18 | CompanyBranchMiddleware | auth only | ✓ |
| 19 | AdminLangRedirectMiddleware | admin paths only | ✓ |
| 20 | ForcePasswordChangeMiddleware | path-based | ✓ |
| 21 | Force2FAMiddleware | **RouteRegistry** | ✓ |
| 22 | ForceTCMiddleware | **RouteRegistry** | ✓ |
| 23 | SubscriptionMiddleware | ALWAYS_ALLOWED_PREFIXES | ✓ |
| 24 | ArchiveReadonlyMiddleware | EXEMPT_PATHS | ✓ |
| 25 | ImageQuotaMiddleware | upload only | ✓ |
| 26 | XFrameOptionsMiddleware | Django std | ✓ |
| 27 | IPFilterMiddleware | IP whitelist | ✓ |
| 28 | ApiErrorFormatMiddleware | API paths | ✓ |
| 29 | SecurityHeadersMiddleware | /mcp/ skip | ✓ |
| 30 | RateLimitMiddleware | SKIP_PREFIXES + auth bypass | ✓ |

---

## KORAK 5 — 504 ELIMINACIJA
**Cilj:** Nula 504 timeoutova pod normalnim opterećenjem.
```
[ ] Django Silk na staging instanci — profiliraj sve sporije od 500ms
[ ] select_related/prefetch_related gdje nedostaje
[ ] DB indeksi na najčešćim filterima
[ ] Gunicorn worker count optimizacija
```
✅ Gotovo kad: Regularni view < 2s, PDF < 15s, 0 x 504 u 48h.

---

## KORAK 6 — GLOBALNI STANDARDI (QR + CSS + URL)
**Cilj:** 0 direktnih import qrcode, entity-link/col-actions svugdje, get_portal_url() svugdje.
```
[ ] Gemini GEMINI_TASK_QR_INTEGRATION.md → verificira Sonnet
[ ] CSS pattern (entity-link, col-actions) → sve liste
[ ] get_portal_url() → sve reference na ponuda URL
[ ] FENIX pravila 1-7 → audit compliance
```
✅ Gotovo kad: grep za stare patterne = 0 rezultata.

---

## KORAK 7 — CRITICAL PATH TEST COVERAGE
**Cilj:** Svaki klijentski dodir ima test.
```
Kritični putevi:
[ ] Login / PIN / 2FA
[ ] Kreiranje i slanje fakture
[ ] POS bon + fiskalizacija
[ ] Kupčeva soba (prihvat/odbijanje)
[ ] Company switch
[ ] Upload dokumenta + AI
[ ] Worktime prijava
Cilj: coverage > 40% na pos/, invoicing/, accounts/
```
✅ Gotovo kad: pytest kritični putevi 100%, coverage report > 40%.

---

## KORAK 8 — LOAD TEST
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
| 7 Test coverage | 🔄 AKTIVAN | 0% |
| 8 Load test | ⏳ na redu | — |
| 9 Security | ⏳ na redu | — |
| 10 Onboarding | ⏳ na redu | — |
| 11 Beta | ⏳ na redu | — |
| 12 EU kampanja | ⏳ na redu | — |
