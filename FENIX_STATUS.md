# FENIX PORTAL — STATUS NAPRETKA
> Zadnji update: 2026-04-13 (Dan 47), commit abdfe6fa + val5

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
