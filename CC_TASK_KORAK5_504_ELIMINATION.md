# CC TASK — KORAK 5: 504 Eliminacija
**Datum: 14.04.2026.**
**Pokreni NAKON što KORAK 4 dobije ✅**

---

## Cilj
Nula 504 timeoutova. Regularni view < 2s, PDF < 15s.

---

## Zadatak

### 5.1 — Instaliraj django-silk za profiling

```bash
pip install django-silk --break-system-packages
```

Dodaj privremeno u settings (samo za ovaj audit):
```python
# core/settings.py — privremeno
if DEBUG:
    INSTALLED_APPS += ['silk']
    MIDDLEWARE = ['silk.middleware.SilkyMiddleware'] + MIDDLEWARE
    SILKY_PYTHON_PROFILER = True
```

### 5.2 — Pronađi spore querye bez profiling alata

```bash
# Queryi koji koriste .all() bez select_related na modelima s FK
grep -rn "\.objects\.all()\b" \
  /var/www/fina-connect/ --include="*.py" \
  | grep -v "venv\|migration\|backup\|test\|#" \
  | grep -v "count()\|exists()\|delete()\|update(" \
  | head -30

# Queryi unutar for petlji (N+1 kandidati)
grep -B5 "\.objects\." /var/www/fina-connect/core/views.py \
  | grep -E "for |while " | head -20
```

### 5.3 — select_related za najkorištenije view-ove

Prioritet: `core/views.py`, `pos/views.py`, `invoicing/views.py`

```bash
# Pronađi sve ForeignKey/ManyToMany bez select_related
python manage.py shell -c "
from django.apps import apps
for model in apps.get_models():
    fks = [f.name for f in model._meta.get_fields() 
           if hasattr(f, 'many_to_one') and f.many_to_one]
    if fks:
        print(f'{model.__name__}: FK={fks[:5]}')
" 2>/dev/null | head -30
```

### 5.4 — DB indeksi

```bash
# Provjeri koji queryi nemaju indeks
python manage.py shell -c "
from django.db import connection
# Pokreni EXPLAIN na najčešće querye
from notifications.models import Notification
from django.db.models import Count
# Ovaj query se izvodi svakih 60s za svakog usera:
qs = Notification.objects.filter(recipient_id=1, is_read=False)
print('Notification query:', qs.query)
" 2>/dev/null
```

### 5.5 — Gunicorn worker optimizacija

```bash
# Provjeri trenutno: 6 workers, 2 threads
cat /etc/systemd/system/gunicorn-fina.service | grep ExecStart

# Formula: workers = (2 × CPU) + 1
nproc  # broj CPU jezgri
# Ako je 2 CPU → 5 workers optimalno
# Ako je 4 CPU → 9 workers optimalno
```

---

## Po završetku

```bash
python manage.py check
git add -A
git commit -m "fix(korak5): 504 eliminacija — select_related, DB indeksi, worker optimizacija"

python -c "
c = open('FENIX_STATUS.md').read()
c = c.replace('| 5 504 eliminacija | 🔄 AKTIVAN | 0% |', '| 5 504 eliminacija | ✅ GOTOVO | 100% |')
c = c.replace('| 6 Globalni standardi | 🔄 AKTIVAN (Gemini) | 30% |', '| 6 Globalni standardi | 🔄 AKTIVAN | 60% |')
open('FENIX_STATUS.md', 'w').write(c)
"
git add FENIX_STATUS.md && git commit -m "status: KORAK 5 gotov"

python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text
send_text('4915771998747','KORAK 5 GOTOV — 504 eliminacija. View-ovi brži. Kreće KORAK 6 globalni standardi.')
" 2>/dev/null

systemctl reload gunicorn-fina
```
