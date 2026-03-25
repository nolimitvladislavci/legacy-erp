# CC_TASK_INVOICE_SECTIONS — Razdvajanje ponude na sekcije (Teil 1 / Teil 2)

**Agent:** CC Code  
**Prioritet:** VISOK  
**Datum:** 2026-03-25  
**Kontekst:** Ivan potvrdio strukturu — VIS-AN-2026-003 treba biti podijeljena na Arbeitsleistungen i Material.

---

## Cilj

Dodati podršku za **sekcije unutar ponude/računa** (section grouping na InvoiceItem razini), 
odmah primijeniti na VIS-AN-2026-003, i renderirati ih u PDF-u i template-u sa subtotalima po sekciji.

---

## Korak 1 — Migracija: dodaj `section` polje na InvoiceItem

```python
# invoicing/models.py — na InvoiceItem modelu dodaj:
section = models.CharField(max_length=150, blank=True, null=False, default='')
sort_order = models.PositiveIntegerField(default=0)
```

- `section` = naziv sekcije (npr. "Teil 1 — Arbeitsleistungen", "Teil 2 — Material und Ausstattung")
- `sort_order` = redoslijed stavki unutar sekcije (0, 10, 20... — ostavlja mjesta za insert)
- Prazni string `''` = bez sekcije (backward compatible sa svim postojećim fakturama)

```bash
python manage.py makemigrations invoicing
python manage.py migrate
```

---

## Korak 2 — Ažuriraj VIS-AN-2026-003 stavke

Postoji 27 stavki. Dodijeli section i sort_order prema ovoj tablici:

### TEIL 1 — Arbeitsleistungen (17 stavki)

| sort_order | description (sadrži) | section |
|-----------|---------------------|---------|
| 10 | ABBRUCH | Teil 1 — Arbeitsleistungen |
| 20 | Rigipsdecke abgehängt | Teil 1 — Arbeitsleistungen |
| 30 | Vorsatzschale 15cm | Teil 1 — Arbeitsleistungen |
| 40 | Trennwand Dusche | Teil 1 — Arbeitsleistungen |
| 50 | Trinkwasserinstallation | Teil 1 — Arbeitsleistungen |
| 60 | Abwasserinstallation | Teil 1 — Arbeitsleistungen |
| 70 | Heizungsleitung Radiator | Teil 1 — Arbeitsleistungen |
| 80 | Untergrundvorbereitung + Abdichtung | Teil 1 — Arbeitsleistungen |
| 90 | Verlegen Wandfliesen | Teil 1 — Arbeitsleistungen |
| 100 | Verlegen Bodenfliesen | Teil 1 — Arbeitsleistungen |
| 110 | Nischen-Verfliesung | Teil 1 — Arbeitsleistungen |
| 120 | FI-Schutzschalter | Teil 1 — Arbeitsleistungen |
| 130 | LED-Downlight Decke | Teil 1 — Arbeitsleistungen |
| 140 | LED-Spot Nischen | Teil 1 — Arbeitsleistungen |
| 150 | Silikonfugen | Teil 1 — Arbeitsleistungen |
| 160 | Übergangsprofile | Teil 1 — Arbeitsleistungen |
| 170 | Bauendreinigung | Teil 1 — Arbeitsleistungen |

### TEIL 2 — Material und Ausstattung (10 stavki)

| sort_order | description (sadrži) | section |
|-----------|---------------------|---------|
| 10 | Feinsteinzeug 120x60 | Teil 2 — Material und Ausstattung |
| 20 | iBox universal 2 Grundkörper | Teil 2 — Material und Ausstattung |
| 30 | ShowerSelect Comfort Q Thermostat | Teil 2 — Material und Ausstattung |
| 40 | Kopfbrause Pulsify Select | Teil 2 — Material und Ausstattung |
| 50 | Handbrause + Brausegarnitur | Teil 2 — Material und Ausstattung |
| 60 | Waschtisch-UP-Armatur | Teil 2 — Material und Ausstattung |
| 70 | WC wandhängend + Geberit | Teil 2 — Material und Ausstattung |
| 80 | Waschtisch + Unterschrank | Teil 2 — Material und Ausstattung |
| 90 | Duschwanne | Teil 2 — Material und Ausstattung |
| 100 | Accessoires-Set Edelstahl | Teil 2 — Material und Ausstattung |

**Napomene:**
- Matchaj po `description__icontains` — svaki keyword je jedinstven u ovoj ponudi
- Ukupno: 27 stavki → 17 + 10 = 27 ✓

---

## Korak 3 — Render sekcija u invoice template

**Lokacija templatea:** Pronađi template koji rendira ponude/fakture (PDF i/ili HTML view).
Pretraži: `grep -r "InvoiceItem\|invoice_items\|items.all" invoicing/templates/ --include="*.html" -l`

**Logika renderiranja:**

```python
# U view-u ili templatetagu:
from itertools import groupby

items = invoice.invoiceitem_set.all().order_by('section', 'sort_order')

# Grupiraj po sekciji
sections = []
for section_name, group in groupby(items, key=lambda x: x.section):
    items_list = list(group)
    subtotal = sum(item.total_price for item in items_list)
    sections.append({
        'name': section_name,
        'items': items_list,
        'subtotal': subtotal,
    })
```

**U HTML/PDF template-u:**
```html
{% for section in sections %}
  {% if section.name %}
  <tr class="section-header">
    <td colspan="5"><strong>{{ section.name }}</strong></td>
  </tr>
  {% endif %}
  {% for item in section.items %}
  <tr>
    <td>{{ item.description }}</td>
    <td>{{ item.quantity }}</td>
    <td>{{ item.unit }}</td>
    <td>{{ item.unit_price }}</td>
    <td>{{ item.total_price }}</td>
  </tr>
  {% endfor %}
  {% if section.name %}
  <tr class="section-subtotal">
    <td colspan="4" style="text-align:right"><em>Zwischensumme {{ section.name[:6] }}:</em></td>
    <td><strong>{{ section.subtotal }}</strong></td>
  </tr>
  {% endif %}
{% endfor %}
```

**CSS za section header u PDF-u:**
```css
.section-header td {
    background: #f0f0f0;
    font-weight: 600;
    font-size: 11pt;
    padding: 8px 6px 6px;
    border-top: 1.5px solid #333;
}
.section-subtotal td {
    border-top: 0.5px solid #aaa;
    border-bottom: 1.5px solid #333;
    padding: 4px 6px;
}
```

---

## Korak 4 — InvoiceSerializer i API (ako postoji)

Ako postoji DRF serializer za InvoiceItem, dodaj `section` i `sort_order` polja:
```python
class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [..., 'section', 'sort_order']
```

---

## Korak 5 — Admin

U `invoicing/admin.py`, dodaj `section` i `sort_order` u `InvoiceItemInline`:
```python
fields = [..., 'section', 'sort_order']
```

---

## Verifikacija

Nakon završetka:
```python
from invoicing.models import Invoice, InvoiceItem
inv = Invoice.objects.get(number='VIS-AN-2026-003')
items = InvoiceItem.objects.filter(invoice=inv).order_by('section', 'sort_order')
for item in items:
    print(f"[{item.section[:6] if item.section else '------'}] {item.description[:50]:<50} | {item.total_price}")

# Provjeri subtotale
from django.db.models import Sum
for section in ['Teil 1 — Arbeitsleistungen', 'Teil 2 — Material und Ausstattung']:
    total = InvoiceItem.objects.filter(invoice=inv, section=section).aggregate(Sum('total_price'))['total_price__sum']
    print(f"{section}: {total}")
# Očekivano: Teil 1 = 17782.88 | Teil 2 = 6111.86 | Ukupno neto = 23894.74
```

---

## Backward compatibility

- Postojeće fakture (bez section) se renderiraju IDENTIČNO kao i prije (section='' → bez section headera)
- Nova logika je additivna — samo fakture s definiranim sectionima dobivaju grupiranje
- Nema breaking changea na API-ju (nova polja su nullable/default)

---

## DONE kriterij

- [ ] Migracija primijenjena
- [ ] VIS-AN-2026-003: svih 27 stavki ima section i sort_order
- [ ] PDF ponude renderira sekcije s Zwischensumme-ima
- [ ] Subtotali: Teil 1 = 17.782,88 € | Teil 2 = 6.111,86 €
- [ ] Bruto ukupno ostaje 28.434,72 €
- [ ] Stare fakture ne mijenjaju izgled
- [ ] Commit s porukom: "invoicing: InvoiceItem section grouping + VIS-AN-2026-003 split"
