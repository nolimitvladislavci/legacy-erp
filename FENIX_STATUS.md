# FENIX STATUS
# Zadnje azuriranje: 2026-04-09 (Sonnet — shell migration Faza 1)
# Git HEAD: 7ace4a6d
# Server: gunicorn ✅ nginx ✅ celery ✅ mcp-fina ✅ | disk 40%

═══════════════════════════════════════════════════════════════
  CC — STARTUP PROTOKOL (čitaj ovo SVAKI PUT kad počinješ)
═══════════════════════════════════════════════════════════════

  SVE datoteke su NA SERVERU. Nikad na lokalnom disku.
  Koristi MCP alat: Fenix LIMIT Connect → read_file
  Putanja projekta: /var/www/fina-connect/

  KORAK 1: pročitaj ovaj fajl (već radiš ✓)
  KORAK 2: git log — exec_command: "cd /var/www/fina-connect && git log --oneline -5"
  KORAK 3: uzmi prvi CC_TASK_*.md s najnovijim datumom:
           exec_command: "ls -lt /var/www/fina-connect/CC_TASK_*.md | head -5"
  KORAK 4: read_file na taj task i počni izvršavati

  NIKAD ne pitaj "gdje je fajl" — uvijek ga traži MCP read_file na serveru.
  Ako task nije jasan → čitaj FENIX_STATUS.md i git log, ne pitaj Ivana.

═══════════════════════════════════════════════════════════════

## AKTIVNI TASKOVI (po prioritetu):

  1. ✅ CC_TASK_WAKE.md
  2. ✅ CC_TASK_F1_UI_AUDIT.md         — UI 6.5→8/10
  3. ✅ CC_TASK_F2_MEMIO_PET_ONBOARDING.md
  4. ✅ CC_TASK_F3_MEMIO_WORLD.md
  5. ✅ CC_TASK_F5_NO_LIMIT_AZIL.md
  6. ✅ CLAUDE_DOKTOR — sve napravljeno (9 zadataka, test 97/100)
  7. ✅ CC_TASK_SECURITY_10_10.md — ZAVRŠEN (09.04.)
  8. ⏳ CC_TASK_SHELL_MIGRATION.md — Faza 1 DONE, Faza 2 post-launch

  ✅ MARIJA_PHONE postavljen: +385976091665

---

## STANJE SUSTAVA (09.04.)

### Servisi: sve ✅
### Git HEAD: 7ace4a6d
### Django: 0 errors
### Backup: dnevni pg_dump ✅ (96MB, zadnji 08.04. 05:00)

### Commiti danas (09.04. — Sonnet sesija):
  7ace4a6d  feat(shell): 4 hamburger panela + Joker fullscreen mode — Faza 1
  7cca1153  feat(ux): ljubimac govori — PIN strength indicator na registraciji

### DANAS NAPRAVLJENO (09.04.):

  ✅ CC_TASK_SECURITY_10_10 ZAVRŠEN:
     — "Ljubimac govori" PIN strength UI na registraciji (trikey_register.html)
     — 7 poruka psa, BANNED_PINS JS set, submit blokada, zelena/crvena feedback

  ✅ SHELL MIGRATION — FAZA 1 (plan + implementacija):
     — CC_TASK_SHELL_MIGRATION.md napisan (3 faze, do Q2 2026)
     — fenix-shell.css sada TRACKIRAN u gitu i učitan u base.html
     — RIGHT PANEL ubačen u base.html (aside#shellRight)
       Desktop: fixed 300px, slide-in s desna
       Mobile: 70vh bottom drawer, border-radius top
     — HAMBURGER #2: ⊞ gumb u topbaru (desktop only, Alt+P)
     — HAMBURGER #4: ⋮ gumb u mobile bottom nav
     — JOKER FULLSCREEN: FenixShell.openJoker(selector, title)
       ?joker=1 URL param → auto-fullscreen #joker-target
       Esc tipka, Alt+J shortcut, fadeIn animacija
     — 568 templatesa AUTOMATSKI dobivaju feature (nema migracije)
     — Backwards aliases: openShellRight/closeShellRight/toggleShellRight

  ⚠️ NAPOMENA: fenix-shell.css bio untracked u gitu — sada je committan

### Live HTTP (08.04. verifikacija — nije ponavljana):
  ✅ limit-connect.com — sve rute OK (vidjeti 08.04. status)

### Poznati bugovi:
  ⚠️  FenixScan OCR: graceful fallback nedostaje (LOW)
  ⚠️  2 korumpirana backupa: db_20260329.sql.gz i db_20260330.sql.gz (20 bytes)
  ⚠️  nginx warnings: duplicate server_name za limit-connect.com (kozmetički)

---

## FENIX SHELL API — za module (dokumentacija):

```javascript
// Desni panel
FenixShell.openRight()
FenixShell.closeRight()
FenixShell.toggleRight()
FenixShell.setRightPanel('<p>HTML sadržaj</p>', 'Naslov panela')

// Joker fullscreen
FenixShell.openJoker('#moj-div', 'Naslov')         // iz DOM elementa
FenixShell.openJoker('<p>HTML</p>', 'Naslov')       // iz HTML stringa
FenixShell.closeJoker()

// Keyboard shortcuts
// Alt+P → toggle desni panel
// Alt+J → joker (ako postoji #joker-target)
// Esc   → zatvori joker
```

HTML pattern za joker u template:
```html
<div id="joker-target" data-title="Moj modul" style="display:none">
  <!-- sadržaj koji se prikazuje u fullscreen -->
</div>
<button onclick="FenixShell.openJoker('#joker-target', 'Moj modul')">
  ⛶ Fullscreen
</button>
```

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci + TriKey onboarding  | CC        | ✅ gotov
  08.04. | Marija dry-run + CC autonomni audit          | Marija+CC | ✅ gotov
  09.04. | Shell Faza 1 + Security task finish          | Sonnet+CC | ✅ gotov
  09-10.04. | Bugfix sprint (samo Marijina lista)       | CC        | ⏳
  12.04. | Load test CCX33                              | CC        | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                        | Ivan      | ⏳

## OCJENE (ažurirano 09.04.):
  LIMIT Connect backend:  9/10
  LIMIT Connect UI/UX:    9/10   (↑ od 8.5 — shell paneli, joker mode)
  Claude Doktor:          9/10
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10
  NO LIMIT/azil:          7.5/10
  FenixInput:             7/10
  Server:                 10/10

## PRIORITETI ZA SKOK NA 10/10:
  1. memio.world CRUD za TimeCapsule/MemoryVault/FamilyStory → 6.5→9
  2. FenixInput apply_to_module integracija → 7→9
  3. Onboarding "aha moment" (upload račun → AI parse → 60s) → UX 9→10
  4. WhatsApp webhook (WAHA → Django → smart_import) → backend 9→10
  5. Shell Faza 2: per-modul right panel sadržaj (arhiva, konto) → UX 10/10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
