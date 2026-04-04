# CC_TASK: UI Revolution 10/10 — Globalni Design System
**Datum:** 03.04.2026. | **Rok:** 07.04.2026.
**Vođa:** Sonnet | **Izvršava:** CC Code

---

## ARHITEKTURA — JASNA PODJELA (ISPRAVAK)

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (UI teme — korisnikov ekran)                  │
│                                                         │
│  1. 🌑 TAMNO   → dark gold, fokus, produkcija           │
│  2. ☀️ SVJETLO  → bijelo, klijent, preglednost          │
│                                                         │
│  Prebacuje se: gumb u topbaru (per user, localStorage)  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  ISPISI (PDF teme — WeasyPrint dokument)                │
│                                                         │
│  1. ⚜️  VISKOVIĆ  → navy + gold, premium, HR/DE         │
│  2. 🌑 TAMNI     → dark navy topbar, moderni startuppi  │
│  3. 📋 DATEV     → bijeli, minimalistički, DE standard  │
│                                                         │
│  Bira se: Company.pdf_template (već u bazi ✅)          │
│  Pokriva: fakture, potvrde, worktime, payslip, PDF sve  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┘
│  BONUS (ako ostane vremena)                             │
│  + Kamera ikona na svakom form polju                    │
│  + AI Sufljer u pozadini (Haiku, 45s interval)         │
└─────────────────────────────────────────────────────────┘
```

---

## PROVJERI STANJE PRIJE PISANJA KODA

```bash
# Što postoji u template mapi
cat invoicing/services/pdf_service.py | head -40
# Company model — pdf_template choices
grep -A 10 "PDF_TEMPLATE_CHOICES" companies/models.py
# booking_theme — za UI temu (postoji li ui_theme field?)
grep -n "ui_theme\|frontend_theme\|user_theme" companies/models.py core/models.py
# Kako se trenutno bira tema (localStorage, UserProfile, Company?)
grep -n "fina-theme\|data-theme\|toggleTheme" templates/base.html
# Worktime, payslip, work_order PDF — koriste li pdf_template?
grep -rn "pdf_template\|TEMPLATE_MAP" worktime/ templates/payroll/ templates/work_orders/ --include="*.py"
```

---

## SPRINT 1 — FRONTEND UI: POBOLJŠANJE 2 TEME (DAN 1)
**Fajl:** `static/css/global_themes.css`

### 1.1 Stanje — što postoji

```css
/* ✅ POSTOJI — tamna tema (default) */
:root { --gold: #c9a84c; --surface: #181a1d; ... }

/* ✅ POSTOJI — svjetla tema (parcijalna) */
html[data-theme="light"] { --dark: #f1f5f9; --surface: #ffffff; ... }
```

### 1.2 Što treba popraviti u TAMNOJ temi:
```css
/* DODATI u :root — nedostaju varijable koje fenix-ui.css traži */
:root {
    /* Topbar */
    --topbar-bg: #0d0f11;
    --topbar-text: #e2e8f0;
    --topbar-border: rgba(201,168,76,0.2);

    /* Sidebar */
    --sidebar-bg: #111214;
    --sidebar-item-hover: rgba(201,168,76,0.08);
    --sidebar-item-active: rgba(201,168,76,0.15);
    --sidebar-text: #94a3b8;
    --sidebar-text-active: #c9a84c;

    /* Forme */
    --input-bg: #1e293b;
    --input-border: #334155;
    --input-focus: rgba(201,168,76,0.4);
    --input-text: #e2e8f0;

    /* Tablice */
    --table-header-bg: #0d0f11;
    --table-row-hover: rgba(201,168,76,0.04);
    --table-border: #1e2130;

    /* Gumbi */
    --btn-primary-bg: #c9a84c;
    --btn-primary-text: #0a0a0a;
    --btn-secondary-bg: #1e293b;
    --btn-secondary-text: #94a3b8;
}
```

### 1.3 Što treba popraviti u SVJETLOJ temi:

```css
html[data-theme="light"] {
    /* Papir bijeli, ne sivi */
    --black: #ffffff;
    --dark: #f8fafc;
    --surface: #ffffff;
    --surface2: #f1f5f9;
    --surface3: #e8edf2;

    --border: #cbd5e1;
    --border-light: rgba(0,0,0,0.08);

    --text: #0f172a;
    --text-dim: #475569;
    --muted: #94a3b8;
    --muted2: #e2e8f0;

    /* Prilagođene varijable */
    --topbar-bg: #ffffff;
    --topbar-text: #0f172a;
    --topbar-border: #e2e8f0;

    --sidebar-bg: #f8fafc;
    --sidebar-item-hover: #f1f5f9;
    --sidebar-item-active: #e0f2fe;
    --sidebar-text: #475569;
    --sidebar-text-active: #0369a1;
    --sidebar-text-active-border: #0369a1;

    --input-bg: #ffffff;
    --input-border: #cbd5e1;
    --input-focus: rgba(3,105,161,0.3);
    --input-text: #0f172a;

    --table-header-bg: #f1f5f9;
    --table-row-hover: #f8fafc;
    --table-border: #e2e8f0;

    --gold: #b8962e;           /* Tamniji gold za čitljivost na bijelom */
    --gold-dim: rgba(184,150,46,0.1);
    --gold-border: rgba(184,150,46,0.25);

    --btn-primary-bg: #0369a1;
    --btn-primary-text: #ffffff;
    --shadow: 0 2px 8px rgba(0,0,0,0.08);

    --green: #059669;
    --red: #dc2626;
    --amber: #d97706;
    --blue: #0369a1;
}
```

### 1.4 Glatke tranzicije — dodati u `fenix-ui.css`:

```css
/* Tranzicija pri promjeni teme */
*, *::before, *::after {
    transition:
        background-color 0.25s ease,
        border-color 0.25s ease,
        color 0.2s ease,
        box-shadow 0.2s ease;
}
/* Izuzeci — ne animirati transformacije i visibility */
*, *::before, *::after {
    transition-property: background-color, border-color, color, box-shadow;
}
```

### 1.5 Theme switcher — poboljšanje u `templates/base.html`:

```html
<!-- Zamijeni stari theme-toggle button -->
<div id="theme-switcher"
    style="display:flex;align-items:center;border:1px solid var(--border);
           border-radius:20px;padding:2px;background:var(--surface2);gap:1px">
    <button class="theme-btn" data-theme="dark" onclick="setTheme('dark')"
        title="Tamna tema"
        style="border:none;padding:5px 9px;border-radius:16px;cursor:pointer;
               background:none;color:var(--text-dim);font-size:.8rem;
               transition:all .2s;display:flex;align-items:center;gap:4px">
        <i class="fas fa-moon"></i>
    </button>
    <button class="theme-btn" data-theme="light" onclick="setTheme('light')"
        title="Svjetla tema"
        style="border:none;padding:5px 9px;border-radius:16px;cursor:pointer;
               background:none;color:var(--text-dim);font-size:.8rem;
               transition:all .2s;display:flex;align-items:center;gap:4px">
        <i class="fas fa-sun"></i>
    </button>
</div>
```

```javascript
// Zamijeni toggleTheme() s:
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('fina-theme', theme);
    document.querySelectorAll('.theme-btn').forEach(function(btn) {
        var active = btn.dataset.theme === theme;
        btn.style.background = active ? 'var(--gold-dim)' : 'none';
        btn.style.color = active ? 'var(--gold)' : 'var(--text-dim)';
        btn.style.fontWeight = active ? '700' : '400';
    });
}
// Init (zamijeni stari inline script)
(function(){
    var t = localStorage.getItem('fina-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', t);
    document.addEventListener('DOMContentLoaded', function(){ setTheme(t); });
})();
```

---

## SPRINT 2 — ISPISI: PROŠIRITI PDF SUSTAV NA SVE DOKUMENTE (DAN 1-2)

### Stanje — što postoji ✅

```python
# invoicing/services/pdf_service.py — TEMPLATE_MAP (postoji)
TEMPLATE_MAP = {
    'viskovic': {'de': '...invoice_de.html', 'hr': '...invoice_hr.html'},
    'datev':    {'de': '...invoice_de_datev.html', 'hr': '...invoice_hr_datev.html'},
    'modern':   {'de': '...invoice_de_modern.html', 'hr': '...invoice_hr_modern.html'},
}
# Company.pdf_template = 'viskovic' | 'datev' | 'modern' (postoji)
```

**PROBLEM:** `TEMPLATE_MAP` koristi samo `invoicing/`. Worktime, payroll, work_orders,
livestock PDF-ovi ne znaju za `pdf_template`. Svaki tvrdo kodira jedan template.

### 2.1 Globalna PDF helper funkcija — dodati u `core/pdf_utils.py` (novi fajl):

```python
# core/pdf_utils.py
"""
Globalni PDF helper — sve WeasyPrint generacije idu kroz ovu funkciju.
Čita Company.pdf_template i vraća pravi template.
"""

from django.template.loader import render_to_string
from django.conf import settings

# ── Mapa modula → varijante predložaka ─────────────────────────────────────
# Format: {modul: {pdf_template_key: template_path}}
# 'viskovic' = HR premium gold
# 'tamni'    = modern dark navy (koristimo 'modern' ključ iz modela)
# 'datev'    = minimalistički, monokroman, DATEV kompatibilan

PDF_TEMPLATE_REGISTRY = {

    'invoice': {
        'viskovic': {'hr': 'invoicing/invoice_hr.html',
                     'de': 'invoicing/invoice_de.html'},
        'modern':   {'hr': 'invoicing/invoice_hr_modern.html',
                     'de': 'invoicing/invoice_de_modern.html'},
        'datev':    {'hr': 'invoicing/invoice_hr_datev.html',
                     'de': 'invoicing/invoice_de_datev.html'},
    },

    'worktime': {
        'viskovic': 'worktime/templates/worktime/timesheet_pdf.html',
        'modern':   'worktime/templates/worktime/timesheet_pdf.html',  # TODO: modern
        'datev':    'worktime/templates/worktime/timesheet_pdf.html',  # TODO: datev
    },

    'payslip': {
        'viskovic': 'payroll/payslip_pdf.html',
        'modern':   'payroll/payslip_pdf.html',  # TODO
        'datev':    'payroll/payslip_pdf.html',  # TODO
    },

    'work_order': {
        'viskovic': 'work_orders/work_order_to_invoice.html',
        'modern':   'work_orders/work_order_to_invoice.html',  # TODO
        'datev':    'work_orders/work_order_to_invoice.html',  # TODO
    },

    'livestock_inspection': {
        'viskovic': 'livestock/inspection_pdf_viskovic.html',
        'modern':   'livestock/inspection_pdf_modern.html',
        'datev':    'livestock/inspection_pdf_datev.html',
    },

    'notariat': {
        'viskovic': 'notariat/pdf_viskovic.html',   # Sprint 1 notariat
        'modern':   'notariat/pdf_modern.html',
        'datev':    'notariat/pdf_datev.html',
    },

    'dimnjak': {
        'viskovic': 'notariat/potvrda_dimnjaka_viskovic.html',
        'modern':   'notariat/potvrda_dimnjaka_modern.html',
        'datev':    'notariat/potvrda_dimnjaka_datev.html',
    },
}


def get_pdf_template(modul: str, company, lang: str = 'hr') -> str:
    """
    Vrati template path za dani modul i company.

    Args:
        modul:   'invoice' | 'worktime' | 'payslip' | 'livestock_inspection' | ...
        company: Company instanca (ima .pdf_template atribut)
        lang:    'hr' | 'de'

    Returns:
        Template path (string)
    """
    # Provjeri postoji li field (migracija možda nije primijenjena)
    pdf_key = getattr(company, 'pdf_template', 'viskovic') or 'viskovic'
    lang = lang if lang in ('hr', 'de') else 'hr'

    templates = PDF_TEMPLATE_REGISTRY.get(modul, {})
    if not templates:
        raise ValueError(f"Nepoznati PDF modul: {modul}")

    variant = templates.get(pdf_key, templates.get('viskovic'))

    if isinstance(variant, dict):
        # Invoice tip — ima hr/de varijantu
        return variant.get(lang, variant.get('hr'))
    else:
        return variant


def render_pdf_html(modul: str, company, context: dict, lang: str = 'hr') -> str:
    """
    Renderaj HTML za PDF.
    Koristi pravi template prema company.pdf_template postavci.
    """
    template_path = get_pdf_template(modul, company, lang)
    return render_to_string(template_path, context)


def generate_weasyprint_pdf(modul: str, company, context: dict, lang: str = 'hr') -> bytes:
    """
    Generiraj PDF bytes putem WeasyPrint.
    Pozivaj iz view-a umjesto direktnog render_to_string.
    """
    from weasyprint import HTML, CSS
    from django.templatetags.static import static

    html_string = render_pdf_html(modul, company, context, lang)
    base_url = getattr(settings, 'WEASYPRINT_BASE_URL', 'https://limit-connect.com')

    return HTML(
        string=html_string,
        base_url=base_url
    ).write_pdf()
```

### 2.2 Zamjeniti direktni WeasyPrint poziv u `invoicing/views.py`:

```python
# STARO (u generate_pdf view):
# html = render_to_string('invoicing/invoice_hr.html', context)
# pdf = HTML(string=html).write_pdf()

# NOVO:
from core.pdf_utils import generate_weasyprint_pdf
company = invoice.company
lang = 'de' if company.country == 'DE' else 'hr'
pdf_bytes = generate_weasyprint_pdf('invoice', company, context, lang)
```

### 2.3 Zamjeniti u `worktime/views.py`, `payroll/views.py`, `work_orders/views.py`:

```python
# Isto — uvijek:
from core.pdf_utils import generate_weasyprint_pdf
pdf_bytes = generate_weasyprint_pdf('worktime', company, context)
```

### 2.4 PDF stil selector u Company settings UI:

```python
# Dodati u Company settings formu (gdje god postoji edit forme za Company)
# Provjeri: grep -rn "CompanyForm\|company_edit\|pdf_template" companies/forms.py companies/views.py

# Ako postoji CompanyForm:
class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [..., 'pdf_template', ...]
        widgets = {
            'pdf_template': forms.RadioSelect(
                attrs={'class': 'pdf-style-radio'}
            )
        }
```

HTML preview kartica za radio izbor:

```html
<!-- U company settings template — vizualni izbor PDF stila -->
<div class="f-grid-3" style="margin:12px 0">
    {% for value, label in form.pdf_template.field.choices %}
    <label style="cursor:pointer">
        <input type="radio" name="pdf_template" value="{{ value }}"
               {% if form.pdf_template.value == value %}checked{% endif %}
               style="display:none">
        <div class="f-card pdf-style-card {% if form.pdf_template.value == value %}active{% endif %}"
             style="border-radius:8px;overflow:hidden;border:2px solid var(--border);
                    transition:border-color .2s;cursor:pointer"
             onclick="this.closest('label').querySelector('input').checked=true;
                      document.querySelectorAll('.pdf-style-card').forEach(c=>c.classList.remove('active'));
                      this.classList.add('active')">
            <!-- Minijatura ovisno o vrijednosti -->
            {% if value == 'viskovic' %}
            <div style="height:80px;background:#1a1a2e;display:flex;align-items:center;
                        justify-content:center;border-bottom:3px solid #c9a84c">
                <span style="color:#c9a84c;font-weight:700;font-size:.9rem">⚜ VISKOVIĆ</span>
            </div>
            {% elif value == 'modern' %}
            <div style="height:80px;background:#111827;display:flex;align-items:center;
                        justify-content:center;border-bottom:3px solid #3b82f6">
                <span style="color:#60a5fa;font-weight:700;font-size:.9rem">◼ TAMNI</span>
            </div>
            {% elif value == 'datev' %}
            <div style="height:80px;background:#ffffff;display:flex;align-items:center;
                        justify-content:center;border-bottom:2px solid #000;border:1px solid #ccc">
                <span style="color:#000;font-weight:700;font-size:.9rem">▣ DATEV</span>
            </div>
            {% endif %}
            <div style="padding:8px 10px;font-size:.8rem;font-weight:600;
                        color:var(--text)">{{ label }}</div>
        </div>
    </label>
    {% endfor %}
</div>
<style>
.pdf-style-card.active { border-color: var(--gold) !important; }
</style>
```

---

## SPRINT 3 — KAMERA NA FORMI (DAN 2-3)
**Fajl:** `static/js/fenix-form-camera.js`

Svaki `<input>` s ovim imenima automatski dobiva kameru ikonu:
`oib`, `iban`, `mbs`, `adresa`, `naziv`, `ime`, `prezime`, `iznos`, `broj`

```javascript
// static/js/fenix-form-camera.js
// Puna implementacija iz prethodnog CC_TASK-a (kopirati)
// Jedina izmjena: openCamera poziva FenixScan.openForField ako postoji
```

---

## SPRINT 4 — AI SUFLJER (DAN 3)
**Fajl:** `static/js/fenix-ai-sufler.js` + `/api/fenix/ai-hint/`

```
Haiku prati formu (45s interval).
Čita popunjena i prazna polja.
Šapće: "Iznos nije unesen. Zadnji račun Kruljac Ivici = 1.250 EUR."
Gumb: "Kopiraj" → popuni polje.
Ne smeta. Ne blokira. Tiho nestaje za 12s.
```

---

## COMMIT FORMAT

```bash
# S1 — UI teme
git commit -m "feat(ui): dark/light tema polish — CSS varijable, tranzicije, 2-way switcher"

# S2a — pdf_utils
git commit -m "feat(pdf): core/pdf_utils.py — globalni PDF template registry"

# S2b — invoice refactor
git commit -m "refactor(invoice): generate_pdf koristi pdf_utils umjesto tvrdog template"

# S2c — ostali moduli
git commit -m "refactor(pdf): worktime/payslip/work_order koriste pdf_utils"

# S2d — company settings UI
git commit -m "feat(company): vizualni PDF stil selector (visković/tamni/datev)"

# S3 — kamera
git commit -m "feat(ui): FenixFormCamera — kamera ikona na form poljima, AI auto-fill"

# S4 — sufljer
git commit -m "feat(ui): AI Sufljer — Haiku savjeti u pozadini (45s, dismiss, auto-fill)"
```

---

## STATUS TABLICA

| # | Feature | Gdje | Status |
|---|---------|------|--------|
| 1 | Tamna tema — polish | global_themes.css | ⏳ |
| 2 | Svjetla tema — kompletna | global_themes.css | ⏳ |
| 3 | 2-way switcher (tamna/svjetla) | base.html | ⏳ |
| 4 | PDF: Visković stil (invoice) | ✅ POSTOJI | ✅ |
| 5 | PDF: Tamni/Modern stil (invoice) | ✅ POSTOJI | ✅ |
| 6 | PDF: DATEV stil (invoice) | ✅ POSTOJI | ✅ |
| 7 | pdf_utils.py — globalni registry | core/pdf_utils.py | ⏳ |
| 8 | worktime PDF → pdf_utils | worktime/ | ⏳ |
| 9 | payslip PDF → pdf_utils | payroll/ | ⏳ |
| 10 | notariat PDF → pdf_utils | notariat/ | ⏳ |
| 11 | Vizualni PDF selector u settings | company settings | ⏳ |
| 12 | Kamera ikona na form poljima | fenix-form-camera.js | ⏳ |
| 13 | AI Sufljer (Haiku, 45s) | fenix-ai-sufler.js | ⏳ |

---

## NAPOMENA ZA CC CODE

```
NE izmišljaj nove template-e gdje već postoje.
Visković/DATEV/Modern predlošci za fakture SU GOTOVI.
Jedino što treba: spojiti ih u jedan sustav (pdf_utils.py)
i proširiti na sve module (worktime, payroll, notariat...).

Redoslijed: S1 → S2 → S3 → S4
S1 i S2 mogu ići paralelno (različiti fajlovi).
S3 i S4 su bonus — ako ostane vremena do 07.04.
```
