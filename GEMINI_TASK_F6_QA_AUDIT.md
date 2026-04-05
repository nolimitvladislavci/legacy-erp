# GEMINI TASK F6 — Full QA Audit (07.04.2026. prep)
# Prioritet: 🔥 ODMAH | Rok: 07.04.2026. 08:00
# Assignee: Gemini (autonomni agent)
# max_steps: 40

## MISIJA
Sutrašnji dan (07.04.) je QA dan. Marija dry-run je 08.04.
Sve rute moraju biti zelene. Sve kritične funkcije moraju raditi.

## AUDIT LISTA

### A. HTTP Status provjera (sve rute)
```python
import requests
BASE = "https://limit-connect.com"
routes = [
    "/hr/", "/hr/prodaja/", "/hr/nabava/", "/hr/konto/", 
    "/hr/honorari/", "/hr/radnici/", "/hr/pos/",
    "/hr/stanice/", "/hr/sezonski/", "/hr/budzet/",
    "/hr/fakture/", "/hr/pdv/", "/hr/fiskalizacija/",
    "/hr/registracija/", "/hr/login/",
    # memio.pet
    "https://memio.pet/", "https://memio.pet/barf/",
    "https://memio.pet/hotel/", "https://memio.pet/dresura/",
]
# Očekivani: 200 ili 302 (redirect na login) — NE 404, NE 500
```

### B. Kritične poslovne funkcije
Provjeri Django logs za ERROR u zadnjih 24h:
```bash
grep "ERROR\|CRITICAL\|500" /var/log/gunicorn/error.log | tail -50
grep "ERROR" /var/www/fina-connect/logs/django.log | tail -50
```

### C. Celery task status
```bash
celery -A core inspect active
celery -A core inspect scheduled
# Postoje li stalled taskovi?
```

### D. Migracije
```bash
python manage.py showmigrations | grep "\[ \]"
# Sve moraju biti aplicirane — niti jedna [X] ne smije nedostajati
```

### E. Django system check
```bash
python manage.py check --deploy
# Koliko warnings? Ima li novih vs. poznatih 6?
```

### F. Performance provjera
```bash
# Response time na ključnim rutama
for route in "/hr/" "/hr/prodaja/" "/hr/konto/"; do
  time curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://limit-connect.com$route
done
# Sve ispod 2s
```

### G. Statički fajlovi
```bash
python manage.py collectstatic --dry-run 2>&1 | tail -5
# Nema grešaka?
```

### H. Backup provjera
```bash
# Zadnji backup uspješan?
ls -la /var/backups/fina-connect/ | tail -5
```

## OUTPUT FORMAT
Za svaki problem: **SEVERITY (CRITICAL/HIGH/MEDIUM/LOW)** → Opis → Preporuka

CRITICAL = blokira produkciju, fix odmah
HIGH = treba fix prije Marija dry-run
MEDIUM = treba fix do go-live 15.04.
LOW = lijepo imati

## FINISH
Napiši QA_REPORT_07_04.md u /var/www/fina-connect/ sa svim nalazima.
Ako ima CRITICAL problema → odmah generiraj CC_TASK za fix.
