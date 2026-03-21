## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Šeki POS readiness check

## Kontekst
Uvijek Friško (shevqet) — prvi pravi POS korisnik.
Ponedjeljak ujutro dolazi s mobitelom i 3 prodajna mjesta.

## Provjeri (samo čitanje, ništa ne mijenjaj bez potrebe)

### 1. Terminal konfiguracija
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import POSTerminal, POSSettings
from companies.models import Company
seki = Company.objects.get(name='UVIJEK FRIŠKO')
terms = POSTerminal.objects.filter(company=seki)
for t in terms:
    print(t.name, t.terminal_code, t.pos_type, 'active:', t.is_active)
try:
    s = POSSettings.objects.get(company=seki)
    print('POS Settings: fiscal_active=', s.fiscal_active, 'printer=', s.printer_type)
except:
    print('NEMA POSSettings — treba kreirati')
"
```

### 2. Inventar za POS — ima li barkodova?
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from inventory.models import InventoryItem
from companies.models import Company
seki = Company.objects.get(name='UVIJEK FRIŠKO')
items = InventoryItem.objects.filter(company=seki, is_active=True)
s_barcode = items.exclude(barcode='').count()
no_barcode = items.filter(barcode='').count()
no_price = items.filter(unit_price=0).count()
print('Ukupno aktivnih:', items.count())
print('S barkodom:', s_barcode)
print('Bez barkoda:', no_barcode)
print('Bez cijene (unit_price=0):', no_price)
# Top 20 pekare s cijenama
pekara = items.filter(unit_price__gt=0).order_by('-unit_price')[:5]
for i in pekara:
    print(' ', i.unit_price, 'EUR |', i.name[:40], '| barcode:', i.barcode or 'NEMA')
"
```

### 3. Korisnik shevqet — može li otvoriti smjenu?
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.get(username='shevqet')
print('active:', u.is_active)
print('last_login:', u.last_login)
print('must_change_password:', u.profile.must_change_password)
print('company:', u.profile.company.name if u.profile.company else 'NEMA')
print('role:', u.profile.role)
"
```

### 4. POSSettings — ako ne postoji, kreiraj
Ako korak 1 kaže 'NEMA POSSettings', kreiraj:
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import POSSettings
from companies.models import Company
seki = Company.objects.get(name='UVIJEK FRIŠKO')
s, created = POSSettings.objects.get_or_create(
    company=seki,
    defaults={
        'printer_type': 'a4',
        'fiscal_active': False,
        'receipt_delivery': 'none',
        'auto_print': False,
    }
)
print('Created:', created, '| fiscal_active:', s.fiscal_active)
"
```

### 5. Simulacija checkout — dry run
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import POSTerminal, POSSession
from companies.models import Company
from django.contrib.auth.models import User
seki = Company.objects.get(name='UVIJEK FRIŠKO')
term = POSTerminal.objects.filter(company=seki, is_active=True).first()
u = User.objects.get(username='shevqet')
# Može li se otvoriti smjena?
last_session = POSSession.objects.filter(terminal=term).order_by('-opened_at').first()
print('Terminal:', term.name)
print('Zadnja smjena:', last_session.status if last_session else 'NIKAD')
print('Sljedeći broj smjene:', (last_session.session_number + 1) if last_session else 1)
print('POS spreman za otvaranje smjene: OK')
"
```

## Output
Javi Ivanu:
- Ima li POSSettings? (ako ne — javi da si kreirao)
- Koliko artikala nema cijenu (unit_price=0)?
- Koliko artikala nema barkod?
- Je li shevqet aktivan i može li ući?
- Status zadnje smjene (open/closed/nikad)?

## Ako nađeš problem
Ne popravljaj sam — javi koordinatoru (Sonetu) s točnim opisom.
Jedina iznimka: POSSettings kreiranje ako ne postoji.
