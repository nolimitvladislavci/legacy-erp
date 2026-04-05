# CC_TASK_PROD_3_TEMPLATES.md
# PRODUCTION MODULE — TASK 3: Templates + UI
# Agent: CC Code #3
# ČEKA: Task 1 DONE (models postoje za context reference)
# Paralelno s Task 2 (views) — templates piši prema URL imenima iz Task 2

---

## CILJ
Kompletni UI za proizvodni modul. Dark/light tema, FENIX design system.
Sve varijable iz `var(--gold)`, `var(--card)`, itd. — bez hardkodiranih boja.

---

## TEMPLATE LISTA (kreirati sve)

```
templates/production/
├── base_production.html        ← Sidebar + header za modul
├── dashboard.html
├── bom/
│   ├── list.html
│   ├── detail.html
│   └── form.html               ← Create + Edit (isti template)
├── work_center/
│   ├── list.html
│   └── form.html
├── order/
│   ├── list.html
│   ├── detail.html
│   ├── form.html
│   ├── complete_confirm.html
│   └── print.html              ← Print-friendly, bez sidebar
├── report/
│   ├── cost_analysis.html
│   └── efficiency.html
└── partials/
    ├── _order_status_badge.html
    ├── _bom_lines_table.html
    └── _cost_summary_card.html
```

---

## TASK 3A — base_production.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="prod-layout">
  <!-- Sidebar -->
  <nav class="prod-sidebar">
    <div class="prod-sidebar-title">
      <i class="fas fa-industry"></i> Proizvodnja
    </div>
    <a href="{% url 'production:dashboard' %}" class="prod-nav-item {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}">
      <i class="fas fa-tachometer-alt"></i> Pregled
    </a>
    <a href="{% url 'production:order_list' %}" class="prod-nav-item">
      <i class="fas fa-clipboard-list"></i> Nalozi
    </a>
    <a href="{% url 'production:bom_list' %}" class="prod-nav-item">
      <i class="fas fa-sitemap"></i> Sastavnice (BOM)
    </a>
    <a href="{% url 'production:wc_list' %}" class="prod-nav-item">
      <i class="fas fa-cog"></i> Radna mjesta
    </a>
    <div class="prod-sidebar-section">Izvještaji</div>
    <a href="{% url 'production:report_costs' %}" class="prod-nav-item">
      <i class="fas fa-chart-bar"></i> Troškovnik
    </a>
    <a href="{% url 'production:report_efficiency' %}" class="prod-nav-item">
      <i class="fas fa-chart-line"></i> Učinkovitost
    </a>
  </nav>
  <!-- Main content -->
  <main class="prod-main">
    {% block prod_content %}{% endblock %}
  </main>
</div>

<style>
.prod-layout { display:flex; gap:0; min-height:calc(100vh - 60px); }
.prod-sidebar { width:220px; min-width:220px; background:var(--surface); border-right:1px solid var(--border); padding:1rem 0; }
.prod-sidebar-title { padding:.5rem 1rem 1rem; font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); display:flex; align-items:center; gap:.5rem; }
.prod-nav-item { display:flex; align-items:center; gap:.6rem; padding:.6rem 1rem; color:var(--text-dim); font-size:.875rem; text-decoration:none; transition:all .15s; border-left:3px solid transparent; }
.prod-nav-item:hover { background:var(--dark); color:var(--text); border-left-color:var(--gold-dim); }
.prod-nav-item.active { background:var(--gold-dim); color:var(--gold); border-left-color:var(--gold); font-weight:600; }
.prod-nav-item i { width:16px; text-align:center; }
.prod-sidebar-section { padding:.75rem 1rem .25rem; font-size:.65rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); margin-top:.5rem; border-top:1px solid var(--border); }
.prod-main { flex:1; padding:1.5rem; overflow-y:auto; }
@media (max-width:768px) { .prod-sidebar { display:none; } }
</style>
{% endblock %}
```

---

## TASK 3B — dashboard.html

KPI kartice u grid-u (4 kartice):
1. **Aktivni nalozi** (planned + in_progress) — ikona: fa-play-circle, boja: gold
2. **Završeno ovaj mj.** — ikona: fa-check-circle, boja: green
3. **Ukupni trošak ovaj mj.** — iznos u EUR, ikona: fa-euro-sign
4. **Škart (%)** — prosječni % za ovaj mj.

Ispod: 2 tablice side-by-side:
- Zadnjih 5 naloga (broj, proizvod, status badge, datum)
- Zadnjih 5 BOM-ova (naziv, proizvod, aktivna?)

Status badge: koristiti `_order_status_badge.html` partial.

---

## TASK 3C — order/list.html

Tablica s filterima:
- Filter: status (dropdown), work_center (dropdown), period (ovaj mj / prethodni / godišnje)
- Search: order_number, product name
- Stupci: Broj naloga | Proizvod | BOM | Planirano | Stvarno | Status | WC | Datum | Akcije
- Akcije: Detalj / Pokreni (ako planned) / Završi (ako in_progress)
- Boja retka prema status_color
- Pagination (20/stranici)

---

## TASK 3D — order/detail.html ← NAJVAŽNIJI TEMPLATE

Strukturirano u sekcije:

### 1. Header
```
[PN-2026-0001]  [Jabučni sok 1L]  [STATUS BADGE]  [Gumbi: Pokreni/Završi/Otkaži]
```

### 2. Info kartice (2-kolumne grid)
- Lijevo: BOM verzija, Radno mjesto, Planirani start/end, Napomene
- Desno: Planirano: X kom | Stvarno: Y kom | Trošak: Z EUR | Po komadu: W EUR/kom

### 3. Tab navigacija (3 taba, JS bez refresh-a)
**Tab 1 — Materijali:**
Tablica: Materijal | Planirano | Stvarno | JMJ | Cijena/jed | Ukupno | Razduženo? ✓/✗
Form za ažuriranje actual_quantity po liniji (inline edit)

**Tab 2 — Troškovi:**
Tablica: Tip | Opis | Kol | JMJ | Cijena/jed | Ukupno
Gumb: + Dodaj trošak (AJAX modal)
Footer: Materijal: X | Rad: Y | Režija: Z | **Ukupno: W EUR | Po komadu: V EUR**

**Tab 3 — QC / Kvaliteta:**
Lista QC provjera (datum, djelatnik, rezultat, prihvaćeno/odbačeno)
Forma za novu QC provjeru

### 4. Historia (FSM log)
Lista card_activities s ikonom, statusom, korisnikom, datumom.

---

## TASK 3E — bom/form.html

Forma u 2 dijela:
1. Gornji dio: BOM metadata (naziv, verzija, proizvod FK select, yield_quantity, yield_unit)
2. Dinamička tablica linija (JS dodaj/ukloni red):
   | # | Materijal (select + search) | Količina | JMJ | Škart % | Ukupno s škartom | Briši |
   
Gumbi: Spremi BOM | Spremi i dodaj nalog

JS: Kad se odabere materijal iz selecta, auto-popuni JMJ i prikaži trenutnu cijenu iz inventory.
AJAX call: `/production/api/bom/[id]/linije/`

---

## TASK 3F — order/form.html

Forma za novi nalog:
1. Odabir BOM-a (select s pretraživanjem)
2. Po odabiru BOM-a — AJAX poziv dohvaća linije i prikazuje preview materijala
3. Unos: Planirana količina, Planirani start, Planirani end, Radno mjesto, Napomene
4. Preview tablice: "Za X kom trebate:" — lista materijala s potrebnim količinama
5. Alert ako neka sirovina ima nedovoljno zaliha (crvena oznaka)

---

## TASK 3G — order/complete_confirm.html

Jednostavna potvrda:
- "Završiti nalog PN-2026-0001?"
- Input: Stvarno proizvedena količina (default=planned)
- Checkbox: "Automatski razdužiti inventar" (default: checked)
- Warning: "Ova akcija je nepovrativa. Inventar će biti automatski smanjen."
- Gumbi: Završi / Odustani

---

## TASK 3H — _order_status_badge.html (partial)

```html
{# Koristi se: {% include 'production/partials/_order_status_badge.html' with order=order %} #}
<span class="prod-status-badge" style="
  background:{{ order.status_color }}22;
  color:{{ order.status_color }};
  border:1px solid {{ order.status_color }}55;
  padding:2px 10px; border-radius:99px; font-size:.75rem; font-weight:600
">
  {{ order.get_status_display }}
</span>
```

---

## TASK 3I — report/cost_analysis.html

Filter: period (datepicker range), BOM, WorkCenter
Tablica: Nalog | Proizvod | Kol | Materijal € | Rad € | Režija € | Ukupno € | Po kom €
Footer: SUM svih kolona
Gumb: Eksport CSV

---

## TASK 3J — order/print.html

Printable layout (bez base.html, bez sidebar):
```html
<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: Arial; font-size:11pt; color:#000; background:#fff; }
  @media print { .no-print { display:none; } }
  table { width:100%; border-collapse:collapse; }
  th,td { border:1px solid #ccc; padding:4px 8px; }
</style>
</head>
```
Sadržaj: Zaglavlje firme | Broj naloga | BOM | Materijali (tablica) | Troškovi | Potpis

---

## PROVJERA USPJEHA

```bash
# Sve template fajlove provjeri sintaksu
cd /var/www/fina-connect
venv/bin/python -c "
import django; django.setup()
from django.template.loader import get_template
import os
for root, dirs, files in os.walk('templates/production'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root,f).replace('templates/','')
            try:
                get_template(path); print(f'OK  {path}')
            except Exception as e: print(f'ERR {path}: {e}')
" 2>/dev/null
```

Kad završiš: `echo "TASK3_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
