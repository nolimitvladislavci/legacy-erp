# CC_TASK_DESIGN_SYSTEM_F1 — CSS ekstrakcija + dizajn sustav
**Dodjeljeno:** CC Code
**Prioritet:** 🔴 Blokira 01.05. kampanju (UI je prodajni argument)
**Datum:** 02.04.2026
**Ne dira:** Funkcionalni kod, views.py, models.py — SAMO templates i static/css

---

## KONTEKST — Stvarno stanje (izmjereno)

```
base.html: 1.056 linija, 76 CSS varijabli, Bootstrap 5.3 + FA 6.5
fenix-ui.css: 148 linija — foundation postoji ali premalo
Inline <style> blokovi: 676 u cijelom projektu
  - udruge/: 99 fajlova
  - pos/:    73 fajlova
  - konto/:  23 fajlova
  - rental/: 18 fajlova
  - ostali: 463 fajlova
Nema app-level CSS fajlova — sve je inline
```

Temeljni problem: CSS varijable (--bg, --bg-card, --text itd.) su definirane u base.html
ali templatei ne koriste ih — svaki developer je pisao hardcoded hex vrijednosti.

---

## ZADATAK F1a — Proširi fenix-ui.css u pravi design system

### Fajl: `/var/www/fina-connect/static/css/fenix-ui.css`

Dodati (na kraj postojećeg sadržaja, NE brisati ništa):

```css
/* ═══ FENIX DESIGN SYSTEM v2 — 02.04.2026 ═══ */

/* TIPOGRAFIJA */
.fenix-title    { font-size: 1.1rem; font-weight: 700; color: var(--text); }
.fenix-subtitle { font-size: .85rem; color: var(--text-secondary); }
.fenix-label    { font-size: .7rem; font-weight: 600; text-transform: uppercase;
                  letter-spacing: 1.5px; color: var(--text-muted); }
.fenix-value    { font-size: 1.5rem; font-weight: 700; color: var(--text); }
.fenix-price    { font-size: 1.2rem; font-weight: 700; color: var(--gold); }

/* KARTICE */
.fenix-card     { background: var(--bg-card); border: 1px solid var(--border);
                  border-radius: 12px; padding: 1rem 1.25rem;
                  transition: border-color .2s; }
.fenix-card:hover { border-color: var(--gold); }
.fenix-card-header { padding-bottom: .75rem; margin-bottom: .75rem;
                     border-bottom: 1px solid var(--border);
                     display: flex; justify-content: space-between; align-items: center; }

/* STATISTIČKA KARTICA */
.fenix-stat     { background: var(--bg-card); border: 1px solid var(--border);
                  border-radius: 10px; padding: .875rem 1rem; }
.fenix-stat .fenix-label { margin-bottom: .25rem; }
.fenix-stat .fenix-value { line-height: 1.1; }

/* GUMBI */
.fenix-btn      { display: inline-flex; align-items: center; gap: .4rem;
                  padding: .45rem .9rem; border-radius: 8px; font-size: .82rem;
                  font-weight: 600; cursor: pointer; border: none;
                  transition: all .15s; text-decoration: none; }
.fenix-btn-primary { background: var(--accent,#3b82f6); color: #fff; }
.fenix-btn-primary:hover { opacity: .88; }
.fenix-btn-gold { background: var(--gold); color: #000; }
.fenix-btn-ghost { background: transparent; color: var(--text-secondary);
                   border: 1px solid var(--border); }
.fenix-btn-ghost:hover { background: var(--bg); color: var(--text); }
.fenix-btn-danger { background: #dc2626; color: #fff; }
.fenix-btn-sm { padding: .3rem .7rem; font-size: .75rem; border-radius: 6px; }

/* TABLICE */
.fenix-table    { width: 100%; border-collapse: collapse; font-size: .82rem; }
.fenix-table th { background: var(--table-header-bg); color: var(--text-secondary);
                  font-weight: 600; font-size: .7rem; text-transform: uppercase;
                  letter-spacing: 1px; padding: .6rem 1rem;
                  border-bottom: 1px solid var(--border); text-align: left; }
.fenix-table td { padding: .65rem 1rem; border-bottom: 1px solid var(--border-light);
                  color: var(--text); vertical-align: middle; }
.fenix-table tr:hover td { background: var(--table-row-hover); }
.fenix-table tr:last-child td { border-bottom: none; }

/* FORME */
.fenix-input    { width: 100%; background: var(--input-bg); border: 1px solid var(--input-border);
                  border-radius: 8px; padding: .5rem .75rem; font-size: .85rem;
                  color: var(--text); outline: none; transition: border-color .15s; }
.fenix-input:focus { border-color: var(--accent,#3b82f6); }
.fenix-form-group { margin-bottom: 1rem; }
.fenix-form-group label { display: block; margin-bottom: .3rem; font-size: .78rem;
                          font-weight: 600; color: var(--text-secondary); }

/* STATUS BADGES */
.fenix-badge    { display: inline-flex; align-items: center; gap: .3rem;
                  padding: .2rem .6rem; border-radius: 20px; font-size: .7rem; font-weight: 600; }
.fenix-badge-success { background: rgba(34,197,94,.12); color: #16a34a; }
.fenix-badge-warning { background: rgba(245,158,11,.12); color: #d97706; }
.fenix-badge-danger  { background: rgba(239,68,68,.12); color: #dc2626; }
.fenix-badge-info    { background: rgba(59,130,246,.12); color: #2563eb; }
.fenix-badge-gold    { background: rgba(201,168,76,.15); color: var(--gold); }
.fenix-badge-ai      { background: rgba(139,92,246,.12); color: #7c3aed;
                       font-size: .65rem; letter-spacing: .5px; }

/* PAGE HEADER */
.fenix-page-header { display: flex; justify-content: space-between; align-items: flex-start;
                     margin-bottom: 1.5rem; flex-wrap: wrap; gap: .75rem; }
.fenix-page-header h1 { font-size: 1.3rem; font-weight: 700; margin: 0;
                        color: var(--text); }
.fenix-breadcrumb { font-size: .75rem; color: var(--text-muted); margin-top: .2rem; }
.fenix-breadcrumb a { color: var(--text-secondary); text-decoration: none; }
.fenix-breadcrumb a:hover { color: var(--gold); }

/* AI BADGE */
.fenix-ai-action { display: inline-flex; align-items: center; gap: .4rem;
                   padding: .25rem .65rem; border-radius: 6px;
                   background: rgba(139,92,246,.1); border: 1px solid rgba(139,92,246,.2);
                   font-size: .72rem; color: #7c3aed; cursor: pointer;
                   transition: background .15s; }
.fenix-ai-action:hover { background: rgba(139,92,246,.18); }
.fenix-ai-action .ai-icon { font-size: .8rem; }
.fenix-ai-confidence { font-weight: 700; margin-left: .2rem; }

/* PRAZNO STANJE */
.fenix-empty    { text-align: center; padding: 3rem 1.5rem; }
.fenix-empty svg, .fenix-empty i { font-size: 2.5rem; color: var(--gold); opacity: .35;
                                    margin-bottom: 1rem; display: block; }
.fenix-empty h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: .5rem; }
.fenix-empty p  { font-size: .85rem; color: var(--text-muted); }

/* MOBILE */
@media (max-width: 768px) {
  .fenix-card { padding: .875rem 1rem; border-radius: 10px; }
  .fenix-page-header h1 { font-size: 1.1rem; }
  .fenix-table { font-size: .78rem; }
  .fenix-table th, .fenix-table td { padding: .5rem .75rem; }
}
```

---

## ZADATAK F1b — Refaktor TOP 10 najzagađenijih templatea

Poredak po broju `<style>` blokova (mjereno):
1. `udruge/` — 99 blokova → počni s 5 najčešćih screena
2. `pos/` — 73 blokova → dashboard i table order
3. `konto/` — 23 blokova
4. `rental/` — 18 blokova

Za svaki refaktor:
1. Zamijeni hardcoded boje s CSS varijablama: `#0f172a` → `var(--text)`, `#f1f5f9` → `var(--bg)` itd.
2. Zamijeni custom gumb klase s `.fenix-btn`
3. Zamijeni custom kartica klase s `.fenix-card`
4. Zamijeni custom tablice s `.fenix-table`
5. **OBAVEZNO:** Svaki zamijenjen `<style>` blok → stavi komentar `<!-- REFAKTORANO F1 02.04.2026 -->`

### Počni s ovim fajlovima (high-impact):
```
templates/udruge/dvd_dashboard.html
templates/udruge/kud_dashboard.html
templates/pos/gastro/qr_menu.html
templates/konto/dashboard.html
templates/rental/property_list.html
```

---

## ZADATAK F1c — app-level CSS fajlovi

Kreirati za svaki veliki app:
```
static/css/apps/pos.css        ← iz pos/ inline stilova
static/css/apps/udruge.css     ← iz udruge/ inline stilova
static/css/apps/konto.css      ← iz konto/ inline stilova
static/css/apps/rental.css     ← iz rental/ inline stilova
```

Dodati u base.html `{% block app_css %}{% endblock %}` pa u svakom app templateu:
```html
{% block app_css %}
<link rel="stylesheet" href="{% static 'css/apps/pos.css' %}">
{% endblock %}
```

---

## PROVJERA:
```bash
# Broj inline <style> mora pasti ispod 400 (s 676)
grep -r "<style>" /var/www/fina-connect/templates | wc -l

# Fenix-ui.css mora biti veći od 400 linija
wc -l /var/www/fina-connect/static/css/fenix-ui.css
```

## GIT:
```bash
git add static/css/ templates/
git commit -m "feat(ui): design system v2 — fenix-ui.css + app CSS + top 10 refaktor"
```
