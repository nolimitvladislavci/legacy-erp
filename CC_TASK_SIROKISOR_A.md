# CC_TASK_SIROKISOR_A — Široki Šor: Popuni bazu, frontend već postoji
**Dodjeljeno:** CC Code Instance A
**Ne dira:** delivery/, gastro_menu/ (ostaje kao je), Task B fajlove
**Status:** TODO
**Datum:** 01.04.2026 (revidirano — frontend postoji u pos/)

---

## VAŽNO — PROČITAJ PRVO

Frontend ZA GOSTE već postoji i funkcionira:
- Template: `/var/www/fina-connect/templates/pos/gastro/qr_menu.html` (428 linija, mobilni dark UI)
- View: `pos/views.py` → `gastro_qr(request, qr_code)` — linija ~2333
- Koristi modele: `pos.Table`, `pos.GastroOrder`, `pos.GastroOrderItem`, `inventory.InventoryItem`

NE TREBA graditi novi frontend. Treba samo POPUNITI BAZU za Korpaš d.o.o.

Company: Korpaš d.o.o. — id: `0240b7d9-a993-4062-81ff-14b587edbb98`
Cijenik: `/var/www/fina-connect/Korpa/cijenik.docx` — 66 artikala, 2 stupca: naziv | cijena

---

## ZADATAK A1 — setup_sirokisor.py

Skripta koja puni bazu. Idempotentna (get_or_create svugdje).

### Korak 1 — Parsiranje cijenik.docx:
```python
import docx
doc = docx.Document('/var/www/fina-connect/Korpa/cijenik.docx')
table = doc.tables[0]  # 66 redova, 2 stupca
# row.cells[0].text = naziv, row.cells[1].text = cijena (zarez → točka)
```

### Korak 2 — Mapiranje u kategorije za InventoryItem.category:
| category | ključne riječi u nazivu |
|---|---|
| drink | PIVO, GIN, VODKA, WHISKY, JACK, KONJAK, LAVOV, STOCK, LOZOV, MEDICA, PELINKOV, ŠLJIVOV, TRAVAR, VILJAM, VIŠNJEV, BLACKY, JAGER, VINO, DECI, CAPPY, CEDEVITA, COCA, COCKTA, FANTA, HIDRA, RED BULL, SCHWEPPES, ROMER, JANA |
| food | SIR, KESTEN |
| dessert | SLADOLED |
| drink | KAVA, CAPPUCCINO, CAFFA, ČAJ, NESCAFE, TOPLA ČOKO, BIJELA KAVA |

### Korak 3 — Kreiranje InventoryItem za svaki artikal:
```python
from inventory.models import InventoryItem
from companies.models import Company

company = Company.objects.get(id='0240b7d9-a993-4062-81ff-14b587edbb98')

# Za svaki artikal iz docx-a:
InventoryItem.objects.get_or_create(
    company=company,
    sku=f'SS-{i:03d}',
    defaults={
        'name': naziv,
        'category': kategorija,  # 'food', 'drink', 'dessert'
        'unit_price': Decimal(cijena),
        'purchase_price': Decimal(cijena) * Decimal('0.4'),  # procjena nabavne
        'quantity': 50,
        'min_quantity': 5,
        'unit': 'kom',
        'is_active': True,
        'item_class': 'tangible',
    }
)
```

PAZI: Provjeri točna polja u `inventory/models.py` — posebno `is_active` i `item_class` choices.

### Korak 4 — Kreiranje 20 pos.Table zapisa:
```python
from pos.models import Table

stolovi = [
    # (name, table_type, floor)
    *[(f'Stol {i}', 'table', 'lokal') for i in range(1, 9)],   # 8 stolova
    *[(f'Šank {i}', 'bar', 'sank') for i in range(1, 5)],       # 4 šank
    *[(f'Terasa {i}', 'terrace', 'terasa') for i in range(1, 9)], # 8 terasa
]

for name, table_type, floor in stolovi:
    Table.objects.get_or_create(
        company=company,
        name=name,
        defaults={
            'table_type': table_type,
            'floor': floor,
            'capacity': 4,
            'is_active': True,
        }
    )
```

### Korak 5 — Provjeri URL za QR narudžbu:
```python
from pos.models import Table
t = Table.objects.filter(company=company).first()
print(f"QR URL: /pos/gastro/qr/{t.qr_code}/")
```
Otvori taj URL u browseru — meni treba raditi odmah.

### Output:
```
✓ InventoryItems kreirani: 66
  - drink: ~58 artikala
  - food: ~3 artikala
  - dessert: 1 artikal
✓ pos.Table zapisi: 20
  - lokal: 8 stolova
  - sank: 4 šanka
  - terasa: 8 terasa
✓ QR URL za test: /pos/gastro/qr/XXXX/
```

---

## ZADATAK A2 — Gastro Admin Panel (POS admin za Široki Šor)

Provjeri je li gastro_dashboard view dostupan:
```bash
grep -n "gastro_dashboard\|gastro-dashboard" /var/www/fina-connect/pos/urls.py
```

Ako postoji URL → provjeri radi li za Korpaš d.o.o.
Ako ne postoji → dodaj u `pos/urls.py`:
```python
path('gastro/dashboard/', views.gastro_dashboard, name='gastro_dashboard'),
path('gastro/kitchen/', views.gastro_kitchen, name='gastro_kitchen'),
path('gastro/table/<int:table_id>/order/', views.gastro_table_order, name='gastro_table_order'),
path('gastro/order/<int:order_id>/update/', views.gastro_order_update, name='gastro_order_update'),
```

Provjeri `pos/views.py` funkciju `gastro_dashboard` (linija ~2029) što prikazuje i je li templateom pokrivena.

---

## ZADATAK A3 — Kitchen tablet URL

View `kitchen_tablet` postoji (linija ~3442 u pos/views.py).
Provjeri URL pattern i osiguraj da radi:
```bash
grep -n "kitchen_tablet\|kitchen-tablet" /var/www/fina-connect/pos/urls.py
```

Ako URL postoji → testiraj. Ako ne → dodaj.

---

## PROVJERA FINALNOG STANJA:

```bash
cd /var/www/fina-connect

# 1. Artikli u bazi
venv/bin/python manage.py shell -c "
from inventory.models import InventoryItem
from companies.models import Company
c = Company.objects.get(id='0240b7d9-a993-4062-81ff-14b587edbb98')
qs = InventoryItem.objects.filter(company=c, category__in=['food','drink','dessert'])
print('InventoryItems Široki Šor:', qs.count())
for cat in ['food','drink','dessert']:
    print(f'  {cat}:', qs.filter(category=cat).count())
"

# 2. Stolovi u bazi
venv/bin/python manage.py shell -c "
from pos.models import Table
from companies.models import Company
c = Company.objects.get(id='0240b7d9-a993-4062-81ff-14b587edbb98')
print('Stolovi:', Table.objects.filter(company=c).count())
t = Table.objects.filter(company=c).first()
print('QR test URL: /pos/gastro/qr/' + t.qr_code + '/')
"

# 3. Restart i test
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/pos/gastro/qr/TEST/
```

---

## GIT COMMIT:
```bash
git add -A
git commit -m "feat(gastro): Široki Šor seed — 66 artikala, 20 stolova, QR meni aktivan"
git log --oneline -3
```
Update FENIX_STATUS.md.
