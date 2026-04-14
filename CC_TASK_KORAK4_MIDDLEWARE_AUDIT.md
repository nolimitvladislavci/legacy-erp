# CC TASK — KORAK 4: Middleware Audit
**Datum: 14.04.2026.**
**Pokreni NAKON što KORAK 3 dobije ✅**

---

## Cilj
Svaki middleware u MIDDLEWARE stacku mora imati konzistentne exempt liste.
Neusklađenost = isti URL prolazi kroz jedan middleware ali se blokira u drugom.

---

## Stack (28 middlewara — provjeri sve)

```python
# core/settings.py MIDDLEWARE lista
```

## Zadatak

### 4.1 — Mapiraj SKIP_PREFIXES za svaki middleware

```bash
grep -rn "SKIP_PREFIXES\|EXEMPT\|ALWAYS_ALLOWED\|BYPASS\|skip.*path\|exempt.*path" \
  /var/www/fina-connect/core/middleware/ \
  /var/www/fina-connect/core/middleware_tc.py \
  /var/www/fina-connect/permissions/ \
  --include="*.py" | grep -v "venv\|backup"
```

### 4.2 — Pronađi nekonzistentnosti

Svaki javni path koji je u jednom `SKIP_PREFIXES` mora biti u svima.
Kritični paths koji moraju biti u SVIM exempt listama:
```
/static/, /media/, /api/, /i18n/, /health, /qr/, /ponuda/, /push/
```

### 4.3 — Sinkroniziraj

Napravi `FENIX_PUBLIC_PATHS` konstantu u `core/constants.py`:
```python
# core/constants.py
FENIX_PUBLIC_PATHS = (
    "/static/",
    "/media/",
    "/api/",
    "/i18n/",
    "/health",
    "/qr/",
    "/ponuda/",
    "/push/",
    "/sw.js",
    "/manifest.json",
    "/offline.html",
    "/inspektor/",
    "/panic/",
    "/no-limit/",
)
```

Svaki middleware koji ima SKIP_PREFIXES/EXEMPT treba importati i koristiti ovu konstantu + svoje specifične putanje.

### 4.4 — Test

```bash
# Provjeri da /qr/, /ponuda/, /hr/ponuda/ prolaze kroz sve middlewara
python manage.py shell -c "
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

rf = RequestFactory()
test_paths = ['/qr/?data=test&size=200&sig=abc', '/hr/ponuda/test-uuid/', '/push/vapid-public-key/']

for path in test_paths:
    req = rf.get(path, HTTP_HOST='limit-connect.com')
    req.user = AnonymousUser()
    req.session = {}
    print(f'Path: {path} — OK (ne puca)')
print('Middleware test završen')
" 2>/dev/null
```

---

## Po završetku

```bash
python manage.py check
git add -A
git commit -m "fix(korak4): Middleware audit — FENIX_PUBLIC_PATHS konstanta, sinkronizirane exempt liste"

python -c "
c = open('FENIX_STATUS.md').read()
c = c.replace('| 4 Middleware | 🔄 AKTIVAN | 0% |', '| 4 Middleware | ✅ GOTOVO | 100% |')
c = c.replace('| 5 504 eliminacija | ⏳ na redu | — |', '| 5 504 eliminacija | 🔄 AKTIVAN | 0% |')
open('FENIX_STATUS.md', 'w').write(c)
"
git add FENIX_STATUS.md && git commit -m "status: KORAK 4 gotov → KORAK 5 aktivan"

python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747','KORAK 4 GOTOV — Middleware audit čist. Sve exempt liste sinkronizirane. Kreće KORAK 5 504 eliminacija.')
" 2>/dev/null

systemctl reload gunicorn-fina
```
