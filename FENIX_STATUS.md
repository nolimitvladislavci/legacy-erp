# FENIX STATUS
# Zadnje azuriranje: 2026-04-09 (Sonnet — Shell Faza 1+2+3 SVE DONE)
# Git HEAD: d7af0b55
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

  1-6. ✅ (sigurnost, memio, doktor, UI audit, azil, wake)
  7.  ✅ CC_TASK_SECURITY_10_10.md       — ZAVRŠEN 09.04.
  8.  ✅ CC_TASK_SHELL_MIGRATION.md      — SVE 3 FAZE ZAVRŠENE 09.04.

---

## SHELL MIGRATION — KOMPLETNO ✅

### Faza 1 (commit 7ace4a6d):
  - fenix-shell.css u base.html
  - shell-right aside + Django blokovi shell_right_title/content/mode
  - Hamburger #2 (topbar) + Hamburger #4 (bottom nav)
  - FenixShell JS API: openRight, closeRight, toggleRight, setRightPanel
  - FenixShell.openJoker() + ?joker=1 URL param + Alt+J/P/Esc
  - 568 templatesa automatski dobili feature — 0 migracije

### Faza 2 (commit 96e4af4f):
  - Arhiva list: _hookDrawerData → desni panel + Proknjiri gumbi
  - Konto dashboard: financijski sažetak (JS injection)
  - POS dashboard: terminal status (JS, čita DOM)
  - Doktor dashboard: score + kategorije + preporuke (JS)

### Faza 3 (commit d7af0b55):
  - base.html: openRight/closeRight → .right-panel-open na .app-layout
  - CSS: .app-layout.right-panel-open .main { margin-right:300px }
  - Novi include fajlovi (server-rendered):
      templates/includes/_panel_konto.html
      templates/includes/_panel_doktor.html
      templates/includes/_panel_pos.html
      templates/includes/_panel_row.html   (micro helper)
      templates/includes/_panel_link.html  (micro helper)
  - konto/dashboard.html   → Django blokovi + _panel_konto include
  - doktor_dashboard.html  → Django blokovi + _panel_doktor include
  - pos/dashboard.html     → Django blokovi + _panel_pos include
  - Arhiva OSTAJE na JS hooku (dinamičan per-row sadržaj)

---

## FENIX SHELL — KOMPLETNA DOKUMENTACIJA

### Django template blokovi (za bilo koji modul):
  {% block shell_right_title %}Naslov panela{% endblock %}
  {% block shell_right_content %}
    {% include "includes/_panel_*.html" %}  {# ili inline HTML #}
  {% endblock %}
  {% block shell_mode %}default{% endblock %}
  {# Opcije: default / focus / fullscreen #}

### JS API (za dinamičan sadržaj):
  FenixShell.openRight()                    // otvori panel
  FenixShell.closeRight()                   // zatvori panel
  FenixShell.toggleRight()                  // toggle
  FenixShell.setRightPanel(html, 'Naslov')  // postavi sadržaj + otvori
  FenixShell.openJoker('#selector','Naslov') // fullscreen overlay
  FenixShell.closeJoker()
  // Keyboard: Alt+P = panel, Alt+J = joker, Esc = zatvori joker

### Joker pattern u templateu:
  <div id="joker-target" data-title="Naslov" style="display:none">
    <!-- fullscreen sadržaj -->
  </div>
  <button onclick="FenixShell.openJoker('#joker-target','Naslov')">⛶</button>
  <!-- ili: ?joker=1 u URL-u → auto-open -->

### Micro include helperi:
  {% include "includes/_panel_row.html" with label="Naziv" val=var suffix="€" color="#22c55e" %}
  {% include "includes/_panel_link.html" with href=url icon="fa-book" label="Naziv" %}

---

## DANAS NAPRAVLJENO (09.04.):

  ✅ CC_TASK_SECURITY_10_10 (ljubimac govori PIN strength)
  ✅ Shell Faza 1 — 4 hamburgera + Joker fullscreen
  ✅ Shell Faza 2 — 4 modula s desnim panelom (JS hooks)
  ✅ Shell Faza 3 — Django template blokovi + include fajlovi

---

## SLJEDEĆI PRIORITETI (09-10.04.):

  1. Bugfix sprint po Marijinoj listi (ako postoji)
  2. Load test priprema (CCX33, 12.04.)
  3. GO/NO-GO priprema (15.04.)

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci                      | ✅
  08.04. | Marija dry-run + CC audit                   | ✅
  09.04. | Shell Faza 1+2+3 + Security + Bugfix        | ✅
  09-10. | Bugfix sprint (Marijina lista)              | ⏳
  12.04. | Load test CCX33                             | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                       | ⏳

## OCJENE (09.04. — post Shell sprint):
  LIMIT Connect backend:  9/10
  LIMIT Connect UI/UX:    9.5/10  (↑ — shell kompletno implementiran)
  Claude Doktor:          9/10
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10
  NO LIMIT/azil:          7.5/10
  FenixInput:             7/10
  Server:                 10/10

## POZNATI BUGOVI (otvoreni):
  ⚠️  FenixScan OCR: graceful fallback nedostaje (LOW)
  ⚠️  2 korumpirana backupa: db_20260329+30 (20 bytes, ne utječe na prod)
  ⚠️  nginx: duplicate server_name (kozmetički)

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
