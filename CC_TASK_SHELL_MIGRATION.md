# CC TASK — SHELL MIGRATION: 4 Hamburger panela + Joker fullscreen
# Autor: Sonnet | Datum: 09.04.2026
# Prioritet: 🟢 NIZAK — Faza 1 DONE, Faze 2-3 post-launch

---

## VIZIJA

Svaki modul u LIMIT Connect dobiva:
- **4 hamburger toggle zone** (lijevo, desno, gore, dolje)
- **Joker forma** — fullscreen overlay za bilo koji modul
- **Deklarativni right panel** — sadržaj definiran u Django templateu, ne JS-u

---

## FAZA 1 ✅ DONE — 09.04.2026 (commit 7ace4a6d)

Implementacija u base.html (additive, 0 migracije templatesa):

HAMBURGER MAPA:
1. ☰ topbar (lijevo)    → sidebar              [bio je]
2. ⊞ topbar (desno)     → right context panel  [NOVO]
3. ≡ sidebar header     → slim mode            [bio je]
4. ⋮ bottom nav (mob.)  → mobilni panel        [NOVO]

RIGHT PANEL:
- Desktop: fixed 300px, slide-in s desna
- Mobile: 70vh drawer slide-up
- FenixShell.setRightPanel(html, title) JS API
- Alt+P keyboard shortcut

JOKER FULLSCREEN:
- FenixShell.openJoker(selector, title)
- ?joker=1 URL param → auto-fullscreen #joker-target
- Esc tipka, Alt+J shortcut, fadeIn animacija

---

## FAZA 2 ✅ DONE — 09.04.2026 (commit 96e4af4f)

Per-modul JS hooks za desni panel:

| Modul | Pristup | Sadržaj panela |
|-------|---------|----------------|
| Arhiva list | _hookDrawerData() hook | Detalji dokumenta + Proknjiri gumbi |
| Konto dashboard | JS injection iz Django vars | Fin. sažetak, saldo, P&L, audit |
| POS dashboard | DOM čitanje kartica | Terminal status, smjene |
| Claude Doktor | JS + Django template vars | Score, kategorije, preporuke |

---

## FAZA 3 ⏳ U TIJEKU — 09.04.2026

### Cilj
Zamijeniti JS injection s čistim Django template blokovima.
Cleaner kod, server-side rendering, lakše održavanje.

### Implementacija

#### A) base.html — dodaj 3 nova Django bloka [SLJEDEĆE]

U `<aside id="shellRight">` zamijeniti hardcoded sadržaj s blokovima:

```django
<!-- u shell-right-header span: -->
<span id="shell-right-title">{% block shell_right_title %}Kontekst{% endblock %}</span>

<!-- u shell-right-content div: -->
<div class="shell-right-content" id="shell-right-content">
  {% block shell_right_content %}
  <div style="padding:20px 16px;...">
    <div>🧠</div>
    <div>AI Assist</div>
    <p>Odaberite element...</p>
  </div>
  {% endblock %}
</div>
```

I na `.app-layout` div:
```django
<div class="app-layout" data-shell-mode="{% block shell_mode %}default{% endblock %}">
```

#### B) konto/dashboard.html — migrirati JS → Django blok
- Ukloniti `{% block extra_js %}` JS injection
- Dodati `{% block shell_right_title %}Financije{% endblock %}`
- Dodati `{% block shell_right_content %}{% include "konto/_panel_financije.html" %}{% endblock %}`
- Kreirati: `templates/konto/_panel_financije.html`

#### C) doktor_dashboard.html — migrirati JS → Django blok
- Ukloniti `{% block extra_js %}` JS injection
- Dodati `{% block shell_right_title %}Doktor · {{ report.overall_score }}/100{% endblock %}`
- Dodati `{% block shell_right_content %}{% include "limit_connect_ai/_panel_doktor.html" %}{% endblock %}`
- Kreirati: `templates/limit_connect_ai/_panel_doktor.html`

#### D) pos/dashboard.html — migrirati JS → Django blok
- Ukloniti DOM-reading JS
- Dodati `{% block shell_right_content %}{% include "pos/_panel_terminali.html" %}{% endblock %}`
- Kreirati: `templates/pos/_panel_terminali.html`
- Kontekst varijabla `terminals` je dostupna u viewu

#### E) shell_mode focus za forme [BONUS]
- U base.html: JS koji čita `data-shell-mode` i dodaje klasu na `.app-layout`
- focus mode: sakrije .shell-right, smanji sidebar
- forme (create/edit/wizard) mogu imati `{% block shell_mode %}focus{% endblock %}`

### Pravilo za Arhivu
Arhiva list OSTAJE na JS hooку (_hookDrawerData). Dynamic per-row data
ne može biti server-side rendered bez AJAX endpointa u base templateu.

---

## FAZA 4 — Q2 2026 (post-produkcija)

Postupna migracija key modula s base.html na base_shell.html:
- base_shell.html refaktorirati da extends base.html
- Key moduli: arhiva → base_shell (čišći blokovi, manje CSS duplikacije)
- Deadline: 30.06.2026

---

## VERIFIKACIJA (Faza 3)

```bash
# 1. Django check
venv/bin/python manage.py check

# 2. Blokovi postoje u base.html
grep -c "block shell_right" templates/base.html  # mora biti >= 2

# 3. Konto panel se renderira server-side
curl -s https://limit-connect.com/hr/konto/ | grep -c "shell-right-content"

# 4. Nema dupliciranog JS injection u konto/dashboard.html
grep -c "FenixShell.setRightPanel" templates/konto/dashboard.html  # mora biti 0
```

---

## STATUS

- [x] Faza 1 implementirana (09.04.2026, commit 7ace4a6d)
- [x] Faza 2 implementirana (09.04.2026, commit 96e4af4f)
- [ ] Faza 3A — base.html + 3 Django bloka
- [ ] Faza 3B — konto panel migracija
- [ ] Faza 3C — doktor panel migracija
- [ ] Faza 3D — pos panel migracija
- [ ] Faza 3E — shell_mode focus za forme (bonus)
- [ ] Faza 4 (Q2 2026)
