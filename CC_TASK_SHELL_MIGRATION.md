# CC TASK — SHELL MIGRATION: 4 Hamburger panela + Joker fullscreen
# Autor: Sonnet | Datum: 09.04.2026
# Prioritet: 🟡 SREDNJI — prije 15.04.

---

## VIZIJA

Svaki modul u LIMIT Connect dobiva:
- **4 hamburger toggle zone** (lijevo, desno, gore, dolje)
- **Joker forma** — fullscreen overlay za bilo koji modul, bez migracije templatesa

Korisnik može "zoomati" u bilo koji kontekst:
- Unos fakture → joker → fullscreen forma, bez distrakcije
- POS → već ima joker.html, ali i dalje radi kao puni shell
- Konto → desni panel prikazuje AI objašnjenje za odabrani redak

---

## FAZA 1 — ODMAH (09.04., nedestruktivno, 0 migracije templatesa)

### Princip: sve se dodaje U base.html kao additive izmjena

**Problem:**
- base_shell.html postoji (194 linije) ali 0 templatesa ga koristi
- base.html koriste 568 templatesa — "migracija" = 568 izmjena = ne dolazi u obzir
- Jedini pametan pristup: base.html POSTAJE shell

**Izmjene:**

### A) fenix-shell.css → učitaj u base.html
Dosad je fenix-shell.css bio samo u base_shell.html. Dodajemo u base.html head.

### B) RIGHT PANEL — hamburger #2 i #4
Novi `<aside class="shell-right">` ubačen u base.html:
- Desktop: fiksiran desni panel, 280px, collapsed by default
- Mobile: slide-up drawer
- Toggle: gumb u topbaru (hamburger #2) + gumb u bottom nav (hamburger #4)
- Sadržaj: default AI Assist, ali svaki template može overridati via JS:
  `FenixShell.setRightPanel(html, title)`

Ukupno hamburger mapa:
1. ☰ (topbar, lijevo) → otvara sidebar         [VEĆ POSTOJI]
2. ⊞ (topbar, desno) → otvara desni panel       [NOVO — Faza 1]
3. ≡ (sidebar header) → slim mode toggle        [VEĆ POSTOJI]
4. ⋮ (bottom nav, desno) → mobilni desni panel  [NOVO — Faza 1]

### C) JOKER FULLSCREEN MODE
CSS klasa + JS overlay koji se može aktivirati iz BILO KOJEG modula:

```javascript
// Iz bilo kojeg template-a:
FenixShell.openJoker('#moj-div', 'Unos fakture');
// ili
FenixShell.openJoker(htmlString, 'Naslov');
```

URL parameter: `?joker=1` + `<div id="joker-target" data-title="Naslov">` → automatski fullscreen

CSS `.joker-active` sakriva topbar + sidebar + bottom-tabs → čist workspace

---

## FAZA 2 — POST-LAUNCH (nakon 15.04.)

Per-modul right panel sadržaj via Django template blocks:

```django
{% block right_panel_content %}
  <!-- Module-specific AI assist / context -->
  {% include "konto/_context_panel.html" %}
{% endblock %}
```

Prioritet modula za Fazu 2:
1. Arhiva/Fakture — AI "Proknjiri" button → desni panel
2. Konto — AI objašnjenje odabranog retka
3. POS dashboard — live stats
4. Claude Doktor — dijagnoza u desnom panelu

---

## FAZA 3 — Q2 2026 (post-produkcija, planska migracija)

Postupna migracija key modula s base.html na base_shell.html:
- Početi s: arhiva, konto, pos/dashboard
- Koristiti `{% extends "base_shell.html" %}` umjesto `{% extends "base.html" %}`
- base_shell.html nasljeđuje SVE iz base.html (ne rewrite)
- Deadline: 30.06.2026

---

## VERIFIKACIJA (Faza 1)

```bash
# 1. Django check
venv/bin/python manage.py check

# 2. Right panel se renderira
curl -s https://limit-connect.com/hr/login/ | grep -c "shell-right"

# 3. Joker overlay postoji u DOM
curl -s https://limit-connect.com/hr/ | grep -c "joker-overlay"

# 4. fenix-shell.css se učitava
curl -I https://limit-connect.com/static/css/fenix-shell.css
```

---

## COMMITOVI

1. `feat(shell): fenix-shell.css + right panel u base.html`
2. `feat(shell): joker fullscreen mode — FenixShell.openJoker()`
3. `feat(shell): 4. hamburger — mobilni toggle za desni panel`
4. `docs(shell): CC_TASK_SHELL_MIGRATION.md + plan faze 1-3`

---

## STATUS

- [x] Plan napisan (09.04.2026)
- [x] Faza 1 implementirana (09.04.2026, commit 7ace4a6d)
- [x] Faza 2 implementirana (09.04.2026, commit 96e4af4f)
- [ ] Faza 3 (Q2 2026)
