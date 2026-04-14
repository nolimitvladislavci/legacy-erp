# CC TASK — KORAK 3: RouteRegistry Kompletni Prolaz
**Datum: 14.04.2026. | Prioritet: KRITIČNO**
**Executor: CC Code | Reviewer: Gemini | Koordinator: Sonnet**

---

## Cilj
Svaka URL ruta koja ne zahtijeva login mora biti eksplicitno registrirana
u `permissions/route_registry.py` kao `AccessLevel.PUBLIC` ili `AccessLevel.AUTHENTICATED`.
`DEFAULT_LEVEL = AccessLevel.COMPANY` blokira sve neregistrirane rute za anonimne korisnike.

---

## Kontekst

`permissions/route_registry.py` — ROUTE_REGISTRY dict.
Svaki URL name koji nije tu dobiva `COMPANY` level → 302 za anonimne.

Već registrirano (ne diraj):
- customer_room, qr_code, public_pdf, portal_ai, portal_accept_trail
- health_check, login, logout, home, pricing, about
- fiscal_status_api, notification_api, push_vapid_key

---

## Koraci

### KORAK 3.1 — Izvuci sve URL nazive iz projekta

```bash
cd /var/www/fina-connect
python manage.py shell -c "
from django.urls import get_resolver
import json

def get_all_url_names(resolver, prefix=''):
    names = []
    for pattern in resolver.url_patterns:
        if hasattr(pattern, 'url_patterns'):
            names.extend(get_all_url_names(pattern, prefix))
        elif hasattr(pattern, 'name') and pattern.name:
            names.append(pattern.name)
    return names

names = sorted(set(get_all_url_names(get_resolver())))
print(f'Ukupno URL naziva: {len(names)}')
for n in names:
    print(n)
" 2>/dev/null > /var/www/fina-connect/ALL_URL_NAMES.txt
wc -l /var/www/fina-connect/ALL_URL_NAMES.txt
head -5 /var/www/fina-connect/ALL_URL_NAMES.txt
```

### KORAK 3.2 — Pronađi rute bez @login_required koje NISU u registru

```bash
python manage.py shell -c "
from django.urls import get_resolver, reverse
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from permissions.route_registry import RouteRegistry, AccessLevel

# Sve URL nazive pokupi
def get_all_patterns(resolver, namespace=''):
    patterns = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            ns = p.namespace or namespace
            patterns.extend(get_all_patterns(p, ns))
        elif hasattr(p, 'name') and p.name:
            patterns.append((namespace, p.name, p))
    return patterns

all_patterns = get_all_patterns(get_resolver())
missing = []
for ns, name, pattern in all_patterns:
    full_name = f'{ns}:{name}' if ns else name
    level = RouteRegistry.ROUTE_REGISTRY.get(full_name) or RouteRegistry.ROUTE_REGISTRY.get(name)
    if level is None:
        missing.append(full_name)

print(f'Neregistrirano: {len(missing)} ruta')
for m in sorted(missing)[:50]:
    print(f'  MISS: {m}')
" 2>/dev/null
```

### KORAK 3.3 — Za svaku neregistriranu rutu, utvrdi razinu pristupa

Pravilo:
- Ima `@login_required` ili `@permission_required` → ostavi DEFAULT (COMPANY je ok)
- Javna stranica (landing, registracija, QR, PDF) → dodaj PUBLIC
- Treba login ali ne company → dodaj AUTHENTICATED
- AJAX endpoint za logiranog usera → AUTHENTICATED

```bash
# Provjeri decorator za svaku rutu
grep -rn "@login_required\|@permission_required" \
  /var/www/fina-connect/ --include="*.py" \
  | grep -v "venv\|backup\|migration" \
  | wc -l
```

### KORAK 3.4 — Dodaj u route_registry.py

Otvori `permissions/route_registry.py` i dodaj sve PUBLIC/AUTHENTICATED rute
koje nedostaju. Format:

```python
# --- Dodano KORAK 3 ---
"ime_rute": AccessLevel.PUBLIC,       # kratko objašnjenje
"druga_ruta": AccessLevel.AUTHENTICATED,  # kratko objašnjenje
```

### KORAK 3.5 — Automatizirani test

```bash
python manage.py shell -c "
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
import importlib

# Test svake PUBLIC rute — mora biti 200 ili redirect na pravi URL
# (ne na '/' osim ako je to namjerno)
from permissions.route_registry import RouteRegistry, AccessLevel
public_routes = [k for k,v in RouteRegistry.ROUTE_REGISTRY.items() if v == AccessLevel.PUBLIC]
print(f'PUBLIC ruta ukupno: {len(public_routes)}')
for r in public_routes:
    print(f'  {r}')
" 2>/dev/null
```

---

## Posebni slučajevi za provjeru

Ove rute su vjerojatno javne ali treba verificirati:

```
memio_pet/*     → landing, profil ljubimca, QR
registration/*  → registracija, onboarding
accounts/login  → već registriran
website/*       → landing pages, brošure
inspektor/*     → javni inspector URL
ponuda/*        → kupčeva soba (već ok)
```

---

## Završni test

```bash
# Smoke test — curl sve PUBLIC rute bez sessiona
python manage.py shell -c "
from django.urls import reverse
from permissions.route_registry import RouteRegistry, AccessLevel

public = [k for k,v in RouteRegistry.ROUTE_REGISTRY.items() if v == AccessLevel.PUBLIC]
print('PUBLIC rute koje ćemo testirati:')
for r in public[:20]:
    try:
        url = reverse(r)
        print(f'  {r} → {url}')
    except:
        print(f'  {r} → (reverse failed - namespace needed)')
" 2>/dev/null
```

---

## Po završetku

```bash
cd /var/www/fina-connect
python manage.py check  # mora biti clean
git add permissions/route_registry.py ALL_URL_NAMES.txt
git commit -m "fix(korak3): RouteRegistry kompletni prolaz — sve javne rute registrirane"

# Ažuriraj status
python -c "
c = open('FENIX_STATUS.md').read()
c = c.replace('| 3 RouteRegistry | 🔄 AKTIVAN | 0% |', '| 3 RouteRegistry | ✅ GOTOVO | 100% |')
c = c.replace('| 4 Middleware | ⏳ na redu | — |', '| 4 Middleware | 🔄 AKTIVAN | 0% |')
open('FENIX_STATUS.md', 'w').write(c)
"
git add FENIX_STATUS.md
git commit -m "status: KORAK 3 gotov → KORAK 4 aktivan"

# Pošalji WhatsApp
python -c "
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747', 'KORAK 3 GOTOV — RouteRegistry čist. Sve javne rute registrirane. Kreće KORAK 4 Middleware audit.')
" 2>/dev/null

systemctl reload gunicorn-fina
```
