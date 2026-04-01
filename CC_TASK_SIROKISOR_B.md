# CC_TASK_SIROKISOR_B — Cijenik verifikacija + Print-ready materijali
**Dodjeljeno:** CC Code (računalo) — nakon A
**Deadline:** Prije otvaranja
**Ne dira:** narudžba flow (to je A)

---

## B1 — Cijenik verifikacija iz Cijenik.docx

### Što treba:
Usporediti 66 artikala u bazi s pravim Cijenik.docx dokumentom.
Ispraviti nazive, cijene i kategorije gdje se razlikuju.

### Koraci:

1. Pronađi Cijenik.docx na serveru:
```bash
find /var/www/fina-connect -name "*ijenik*" -o -name "*cjenik*" -o -name "*menu*" 2>/dev/null | grep -i doc
```

2. Ako postoji — parsiraj s python-docx:
```python
from docx import Document
doc = Document('path/to/Cijenik.docx')
for table in doc.tables:
    for row in table.rows:
        cells = [c.text.strip() for c in row.cells]
        print(cells)  # [naziv, cijena, kategorija?]
```

3. Usporedi s MenuItem-ima u bazi:
```python
from gastro_menu.models import MenuItem, MenuCategory, DigitalMenu
menu = DigitalMenu.objects.get(slug='korpas-doo-siroki-sor')
for item in MenuItem.objects.filter(category__menu=menu).order_by('category__sort_order', 'sort_order'):
    print(f'{item.category.name:25s} | {item.name:30s} | {item.price}')
```

4. Za svaki artikl koji se razlikuje — update:
```python
item.name = 'Ispravan naziv'
item.price = Decimal('3.50')
item.save(update_fields=['name', 'price'])
# Sync s InventoryItem
from django.utils.text import slugify
InventoryItem.objects.filter(company=company, sku=slugify(old_name)[:40]).update(
    name='Ispravan naziv', unit_price=Decimal('3.50'))
```

### Output:
- Lista razlika (ako ih ima)
- Potvrda da su svih 66 artikala usklađeni s pravim cijenikom

---

## B2 — Print-ready QR materijali

### Što treba:
Kruljac treba isprintati i zalijepiti QR na stolove.
Kreiraj A4 PDF sa 4 QR koda po stranici (za printanje).

### Skripta: `scripts/generate_qr_print.py`

```python
"""
Generira A4 PDF sa QR kodovima za stolove.
4 QR koda po stranici, s nazivom stola ispod.
Output: media/gastro/siroki_sor_qr_print.pdf
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import sys; sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from gastro_menu.models import TableQR, DigitalMenu

menu = DigitalMenu.objects.get(slug='korpas-doo-siroki-sor')
tables = list(TableQR.objects.filter(menu=menu).order_by('table_zone', 'table_number'))

OUTPUT = '/var/www/fina-connect/media/gastro/siroki_sor_qr_print.pdf'
QR_DIR = '/var/www/fina-connect/media/gastro/table_qr'

c = canvas.Canvas(OUTPUT, pagesize=A4)
width, height = A4

# 4 per page: 2 columns x 2 rows
positions = [
    (2*cm, height - 15*cm),    # top-left
    (11*cm, height - 15*cm),   # top-right
    (2*cm, height - 28*cm),    # bottom-left
    (11*cm, height - 28*cm),   # bottom-right
]

for i, tqr in enumerate(tables):
    pos_idx = i % 4
    if pos_idx == 0 and i > 0:
        c.showPage()
    
    x, y = positions[pos_idx]
    qr_file = os.path.join(QR_DIR, f'qr_{tqr.table_number.replace(" ", "_").lower()}.png')
    
    if os.path.exists(qr_file):
        c.drawImage(qr_file, x, y, width=8*cm, height=8*cm)
    
    # Label
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(x + 4*cm, y - 0.5*cm, tqr.table_number)
    
    # Subtitle
    c.setFont('Helvetica', 10)
    c.drawCentredString(x + 4*cm, y - 1.2*cm, 'Skeniraj za jelovnik')

    # Footer: restaurant name
    c.setFont('Helvetica', 8)
    c.drawCentredString(x + 4*cm, y - 1.8*cm, 'Široki Šor — Izletište · Kušaonica')

c.save()
print(f'PDF generiran: {OUTPUT}')
print(f'{len(tables)} QR kodova, {(len(tables) + 3) // 4} stranica')
```

### Preduvjet:
```bash
pip install reportlab
```

### Output:
- `media/gastro/siroki_sor_qr_print.pdf` — 5 stranica A4
- Kruljac printa, reže, plastificira, lijepi na stolove

---

## B3 — Menu card (digitalni PDF za download)

### Što treba:
Generirati PDF verziju jelovnika (za goste bez mobitela ili za pult).

### Skripta: `scripts/generate_menu_pdf.py`

Koristi reportlab ili xhtml2pdf (već u projektu).
- Naslov: Široki Šor logo + naziv
- Kategorije s artiklima i cijenama
- Footer: adresa, telefon, radno vrijeme
- Dark theme (tamna pozadina, zlatni tekst — kao web menu)

### Output:
- `media/gastro/siroki_sor_jelovnik.pdf`
- Dostupan na `/gastro-menu/menu/korpas-doo-siroki-sor/pdf/`

---

## B4 — Radno vrijeme + kontakt info

### Što treba:
Dodati na DigitalMenu ili CompanyBranch:
- Radno vrijeme (pon-pet, sub, ned)
- Telefon
- Adresa
- Google Maps link

### Model proširenje (ako treba):
```python
# Na BorgBranch ili DigitalMenu dodati:
working_hours = JSONField(default=dict)
# {"pon-pet": "14:00-21:30", "sub": "12:00-22:00", "ned": "Zatvoreno"}
```

### Prikazati na:
- Public menu (header ili footer)
- Landing page (već postoji, samo sync)
- QR print materijal (mali tekst ispod QR koda)

---

## KOORDINACIJA:

| Fajl | Task A | Task B |
|---|---|---|
| scripts/generate_table_qr.py | PIŠE | NE DIRA |
| gastro_menu/views.py (order flow) | PIŠE | NE DIRA |
| templates/gastro_menu/public_menu.html (košarica JS) | PIŠE | NE DIRA |
| scripts/generate_qr_print.py | NE DIRA | PIŠE |
| scripts/generate_menu_pdf.py | NE DIRA | PIŠE |
| Cijenik verifikacija | NE DIRA | PIŠE |

---

## GIT:
```bash
git add scripts/generate_qr_print.py \
        scripts/generate_menu_pdf.py \
        media/gastro/siroki_sor_qr_print.pdf \
        media/gastro/siroki_sor_jelovnik.pdf
git commit -m "feat: Široki Šor print-ready QR + PDF menu + cijenik verifikacija"
```
