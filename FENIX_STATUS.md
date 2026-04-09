# FENIX STATUS
# Zadnje azuriranje: 2026-04-09 (Sonnet — Shell Faza 1+2 done, Faza 3 u tijeku)
# Git HEAD: 8ac5b734
# Server: gunicorn ✅ nginx ✅ celery ✅ mcp-fina ✅ | disk 40%

═══════════════════════════════════════════════════════════════
  CC — STARTUP PROTOKOL (čitaj SVAKI PUT)
═══════════════════════════════════════════════════════════════

  KORAK 1: pročitaj ovaj fajl ✓
  KORAK 2: git log — exec: "cd /var/www/fina-connect && git log --oneline -5"
  KORAK 3: ls -lt CC_TASK_*.md | head -5
  KORAK 4: read_file na najnoviji task i izvršavaj

═══════════════════════════════════════════════════════════════

## AKTIVNI TASKOVI (po prioritetu):

  1-6. ✅ (vidi raniji status)
  7.  ✅ CC_TASK_SECURITY_10_10.md      — ZAVRŠEN 09.04.
  8.  ⏳ CC_TASK_SHELL_MIGRATION.md
        ✅ Faza 1 — 4 hamburgera + Joker fullscreen (commit 7ace4a6d)
        ✅ Faza 2 — per-modul desni panel JS hooks (commit 96e4af4f)
        ⏳ Faza 3 — Django template blokovi za right panel (U TIJEKU)
        ⬜ Faza 4 — post-Q2 (nije planirana za sada)

---

## SHELL MIGRATION — GDJE SMO STALI

### Faza 1 (✅ 09.04. commit 7ace4a6d):
  - fenix-shell.css ubačen u base.html
  - shell-right aside dodан u base.html
  - Hamburger #2 (topbar desno) i #4 (bottom nav mobile)
  - FenixShell.openJoker() + ?joker=1 URL param
  - Alt+P / Alt+J / Esc keyboard shortcuts
  - 568 templatesa automatski dobili feature

### Faza 2 (✅ 09.04. commit 96e4af4f):
  - Arhiva list: _hookDrawerData() → desni panel + Proknjiri gumbi
  - Konto dashboard: financijski sažetak (JS injection iz Django vars)
  - POS dashboard: terminal status (čita iz DOM-a)
  - Doktor dashboard: score + kategorije + preporuke

### Faza 3 (⏳ U TIJEKU — početi ovdje ako nema konteksta):

  **CILJ:** Zamijeniti JS injection s čistim Django template blokovima.
  Umjesto da JS piše HTML za desni panel, modul definira sadržaj
  deklarativno u Django templateu.

  **STRATEGIJA:**
  Dodati u base.html 3 nova Django template bloka:
    1. {% block shell_right_title %}Kontekst{% endblock %}
       → popunjava span#shell-right-title
    2. {% block shell_right_content %}...default AI...{% endblock %}
       → popunjava div#shell-right-content
    3. {% block shell_mode %}default{% endblock %}
       → data-shell-mode atribut na .app-layout div

  Moduli koji žele statički sadržaj panela koriste blokove:
    {% block shell_right_title %}Financije{% endblock %}
    {% block shell_right_content %}
      {% include "konto/_panel_financije.html" %}
    {% endblock %}

  Arhiva ostaje JS (jer je dynamic — mijenja se po kliknutom retku).

  **REDOSLJED IMPLEMENTACIJE:**
  A) base.html: dodaj 3 Django bloka u shell-right + data-shell-mode  [SLJEDEĆE]
  B) konto/dashboard.html: migrirati JS → Django blok + _panel_konto.html
  C) doktor_dashboard.html: migrirati JS → Django blok + _panel_doktor.html
  D) pos/dashboard.html: migrirati JS → Django blok + _panel_pos.html
  E) Bonus: shell_mode focus za forme (create/edit), fullscreen za joker

  **PRAVILO:** Arhiva list OSTAJE na JS hooку (dynamic per-row data).
  Statički moduli (konto, doktor, pos) → Django template blokovi.

---

## DANAS NAPRAVLJENO (09.04.):

  ✅ CC_TASK_SECURITY_10_10 ZAVRŠEN:
     — "Ljubimac govori" PIN strength UI na registraciji

  ✅ SHELL FAZA 1 (commit 7ace4a6d):
     — 4 hamburger panela + Joker fullscreen mode
     — FenixShell JS API u base.html
     — fenix-shell.css tracked u gitu

  ✅ SHELL FAZA 2 (commit 96e4af4f):
     — 4 modula s desnim panelom (Arhiva, Konto, POS, Doktor)

  ⏳ SHELL FAZA 3: u tijeku ove sesije

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci                      | ✅
  08.04. | Marija dry-run + CC audit                   | ✅
  09.04. | Shell Faza 1+2+3 + Security task            | ✅/⏳
  09-10. | Bugfix sprint (Marijina lista)              | ⏳
  12.04. | Load test CCX33                             | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                       | ⏳

## FENIX SHELL API (za module):

```javascript
// Dinamički (runtime) — iz JS-a:
FenixShell.openRight()
FenixShell.closeRight()
FenixShell.toggleRight()
FenixShell.setRightPanel('<p>HTML</p>', 'Naslov')  // JS injection
FenixShell.openJoker('#selector', 'Naslov')        // fullscreen
FenixShell.closeJoker()
// Alt+P = desni panel | Alt+J = joker | Esc = zatvori joker
```

```django
{# Deklarativno (Faza 3) — iz Django templatea: #}
{% block shell_right_title %}Moj modul{% endblock %}
{% block shell_right_content %}
  {% include "modul/_panel.html" %}
{% endblock %}
{% block shell_mode %}focus{% endblock %}  {# default/focus/fullscreen #}
```

```html
<!-- Joker pattern u bilo kojem templateu: -->
<div id="joker-target" data-title="Naslov" style="display:none">
  <!-- sadržaj koji ide u fullscreen -->
</div>
<button onclick="FenixShell.openJoker('#joker-target','Naslov')">⛶</button>
<!-- ili: dodaj ?joker=1 u URL za auto-open -->
```

## OCJENE (09.04.):
  LIMIT Connect backend:  9/10
  LIMIT Connect UI/UX:    9.5/10  (↑ — shell paneli živi i korisni)
  Claude Doktor:          9/10
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10
  NO LIMIT/azil:          7.5/10
  FenixInput:             7/10
  Server:                 10/10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
