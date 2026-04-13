# DIO 3: ORM OPTIMIZACIJA & PERFORMANCE (GEMINI/SONNET)
> Pattern-baziran posao — svaki app ima isti recept: nađi N+1, dodaj select/prefetch

## CILJ
Povećati ORM optimization coverage sa 10% na 60%+.
Eliminirati N+1 query probleme u svim kritičnim viewsima.

## TRENUTNO STANJE
```
Ukupno ORM .objects. poziva:  9,330
select_related/prefetch:        951 (10.2%)
Subquery/Prefetch():              3 (!)
bulk_create/update:              28
annotate/aggregate:             840
transaction.atomic:             157
```

## SCOPE — PO APPOVIMA (ORM pozivi : optimizacije = GAP):
```
pos/          950 : 93  = 10% optimizirano — KRITIČNO (POS = core revenue)
core/         925 : 50  = 5%  — KRITIČNO (dashboard, umbrella)
udruge/       467 : 52  = 11%
konto/        362 : 35  = 10%
worktime/     316 : 20  = 6%  — KRITIČNO (employee modul)
invoicing/    291 : 18  = 6%  — KRITIČNO (fakture)
delivery/     204 : 23  = 11%
synesis/      179 : 4   = 2%  — NAJGORE
inventory/    143 : 26  = 18%
appointments/ 139 : 9   = 6%
marketplace/  136 : 31  = 23%
registration/ 125 : 8   = 6%
companies/    113 : 10  = 9%
memio_pet/    86  : 4   = 5%
rental/       53  : 13  = 25%
stolarija/    50  : 10  = 20%
```

## PRAVILA OPTIMIZACIJE

### 1. select_related() — za ForeignKey/OneToOne (JOIN u SQL)
```python
# LOŠE — N+1
orders = Order.objects.filter(company=company)
for order in orders:
    print(order.customer.name)  # 1 query per order!

# DOBRO — 1 query
orders = Order.objects.filter(company=company).select_related('customer')
```

**KADA:** Svaki put kad se u template/view pristupa `obj.fk_field.attribute`

### 2. prefetch_related() — za ManyToMany/reverse FK (2 querya)
```python
# LOŠE — N+1
for company in companies:
    branches = company.branch_set.all()  # 1 query per company!

# DOBRO — 2 querya ukupno
companies = Company.objects.prefetch_related('branch_set')
```

**KADA:** Svaki put kad se u template koristi `{% for item in obj.related_set.all %}`

### 3. Prefetch() objekt — za filtrirane reverse relacije
```python
from django.db.models import Prefetch

# Prefetch samo aktivne narudžbe
Company.objects.prefetch_related(
    Prefetch('orders', queryset=Order.objects.filter(status='active'))
)
```

### 4. only() / defer() — kad ne treba sve kolone
```python
# LOŠE — dohvaća SVE kolone uključujući text/blob
docs = Document.objects.filter(company=company)

# DOBRO — samo ID, naslov, datum
docs = Document.objects.filter(company=company).only('id', 'title', 'created_at')
```

### 5. values() / values_list() — za dashboard aggregacije
```python
# LOŠE — instancira Model objekte
totals = []
for inv in Invoice.objects.filter(company=company):
    totals.append(inv.total)

# DOBRO — raw values, nema Model overhead
totals = Invoice.objects.filter(company=company).values_list('total', flat=True)
```

### 6. exists() umjesto count() ili bool queryset
```python
# LOŠE
if Model.objects.filter(...).count() > 0:

# DOBRO
if Model.objects.filter(...).exists():
```

### 7. bulk operacije
```python
# LOŠE — N querya
for item in items:
    Item.objects.create(**item)

# DOBRO — 1 query
Item.objects.bulk_create([Item(**i) for i in items])
```

## RED RADA (po business impact):

### Faza 1: KRITIČNI MODULI (core revenue/compliance)
1. **pos/views.py** (5,890 linija!) — POS dashboard, transakcije, izvještaji
2. **core/views.py** (3,024 linija) — umbrella dashboard, company switching
3. **invoicing/views.py** (2,333 linija) — fakture, URA/IRA
4. **worktime/views.py** — evidencija rada, TimeLogRevision

### Faza 2: SEKUNDARNI MODULI
5. **appointments/views.py** (1,865 linija) — booking kalendar
6. **konto/views.py** (1,652 linija) — računovodstvo
7. **synesis/views.py** (1,637 linija) — 2% optimizirano!
8. **registration/views.py** (1,861 linija)

### Faza 3: VERTIKALE
9. **udruge/** — 467 querya
10. **delivery/** — 204 querya
11. **marketplace/** — 136 querya
12. **stolarija/** — 50 querya ali pilot vertikala
13. **memio_pet/** — 86 querya
14. **companies/** — 113 querya

## PROCEDURA ZA SVAKI VIEW:

1. Otvori views.py
2. Nađi svaki `.objects.` poziv
3. Provjeri postoji li chain sa `.select_related()` ili `.prefetch_related()`
4. Ako NE:
   - Pogledaj koje FK/M2M relacije se koriste niže u kodu ili u template-u
   - Dodaj odgovarajuće `select_related('fk1', 'fk2')` ili `prefetch_related('m2m_rel')`
5. Za list viewse: dodaj `.only()` ako se koristi mali subset polja
6. Za count provjere: zamijeni `.count() > 0` sa `.exists()`
7. Za dashboard aggregacije: koristi `annotate()` / `aggregate()` umjesto Python petlji

## DODATNO: Template optimizacija (ako se nađe)
```html
<!-- LOŠE — N+1 u templateu -->
{% for order in orders %}
  {{ order.customer.name }}  {# ← upit ako nije select_related #}
{% endfor %}

<!-- Nema promjene u template-u, FIX JE U VIEW-U -->
```

## NE DIRATI:
- Exception handling (DIO 1 — Opus)
- csrf_exempt (DIO 2 — Haiku)
- Ghost appove (DIO 2)
- Modele — NEMA schema promjena, samo queryset optimizacija
- NEMA novih indeksa bez prethodne analize

## METRIKA USPJEHA
- `grep -rn "select_related\|prefetch_related" | wc -l` > 2000 (sa 951)
- `grep -rn "\.exists()" | wc -l` > 200
- Nula `count() > 0` pattern u views
- POS dashboard load time < 500ms (mjeriti s django-debug-toolbar ili logging)
- `python manage.py check` prolazi
- Gunicorn restart bez grešaka

## COMMIT PORUKE
```
perf(pos): add select_related/prefetch_related to N views — eliminate N+1

perf(core): optimize umbrella dashboard queries — X → Y queries

perf(invoicing): batch optimize invoice list/detail views

perf(worktime): eliminate N+1 in timelog views

perf(secondary): optimize appointments, konto, synesis queries

perf(verticals): optimize udruge, delivery, marketplace queries
```

## PROVJERA NAKON SVEGA
```bash
# Quick smoke test — svaki modul mora importirati
python -c "from pos.views import *; print('OK')"
python -c "from core.views import *; print('OK')"
python -c "from invoicing.views import *; print('OK')"

# Full check
python manage.py check
python manage.py migrate --check
systemctl restart gunicorn
```
