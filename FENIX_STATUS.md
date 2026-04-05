# FENIX STATUS
# Zadnje azuriranje: 2026-04-06 01:15 — Sonnet verifikacija
# Git HEAD: 82355bd4
# Server: gunicorn ✅ nginx ✅ celery ✅ mcp-fina ✅ | disk 39%

═══════════════════════════════════════════════════════════════
  CC STARTUP — čitaj ovo SVAKI PUT
═══════════════════════════════════════════════════════════════
  KORAK 1: exec_command → cd /var/www/fina-connect && git log --oneline -5
  KORAK 2: exec_command → ls -lt /var/www/fina-connect/CC_TASK_*.md | head -5
  KORAK 3: read_file → /var/www/fina-connect/CC_TASK_<NAJNOVIJI>.md
  SVE datoteke su NA SERVERU. Koristi MCP, nikad lokalni disk.
═══════════════════════════════════════════════════════════════

## AKTIVNI TASKOVI (CC radi redom):

  1. CC_TASK_F3_MEMIO_WORLD.md    ← SLJEDEĆI
  2. CC_TASK_F5_NO_LIMIT_AZIL.md
  3. GEMINI_TASK_F6_QA_AUDIT.md  ← Gemini
  (CC_TASK_PROD_* i CC_TASK_RIST_* su stariji, nakon F3+F5)

---

## VERIFICIRANO GOTOVO — sesija 05-06.04.2026.

### Commiti (redom):
  82355bd4  docs: F1+F2 complete
  4dcee040  fix(ui): sidebar light mode
  abb6be66  feat(memio-pet): landing + dashboard + add animal
  6459a4c0  docs: status update
  d62f170c  fix(ui): login mobile
  248323f5  fix(ui): TriKey PIN tab na login
  75d58c6c  fix(ui): breadcrumbs + form validation
  fa85895d  fix(ui): dashboard mobile
  2ecf5a81  fix(ui): POS mobile touch targets
  b373dff6  feat(trikey): 350 profila + login template
  a9b25e8c  docs(cc): CLAUDE.md startup protokol
  95f0a6f9  fix(pdf): 22 templates CSS var() crash
  fb5703b2  fix(boxgram): signals + video_downloader

### Live HTTP audit (06.04. 01:15):
  ✅ memio.pet/                        — 200 (nova landing page)
  ✅ memio.pet/registracija/           — 200 (NE vodi na LIMIT Connect!)
  ✅ memio.pet/moj-profil/             — 200 (breeder dashboard)
  ✅ memio.pet/ljubimac/novi/          — 200 (dodaj ljubimca)
  ✅ memio.pet/boxgram/feed/           — 200
  ✅ memio.pet/barf/                   — 200
  ✅ limit-connect.com/hr/login/       — 200
  ✅ limit-connect.com/accounts/trikey/login/ — 302→login ✅
  ✅ Django check: 0 errors
  ✅ TriKey: 350 profila kreirano

### Ocjene (verificirano):
  LIMIT Connect UI/UX:    8/10  (bilo 6.5)
  memio.pet onboarding:   8/10  (bilo 4)
  Boxgram:                7.5/10
  memio.world:            4/10  ← F3 čeka
  NO LIMIT / azil:        5/10  ← F5 čeka
  Server:                 9.5/10

### Što ostaje za UI 9/10:
  - Detaljan POS flow test (Šeki/Kruljac)
  - Faktura preview
  - Dark/light mode audit po svim stranicama

---

## RATNI RASPORED:
  07.04. | F3+F5+QA audit              | CC+Gemini | 🔥
  08.04. | Marija dry-run              | Marija    | ⏳
  12.04. | Load test CCX33             | CC        | ⏳
  15.04. | GO/NO-GO PRODUKCIJA         | Ivan      | ⏳

## PENDING (Ivan):
  - Konjik: Scenarij A (639€/mj) — razgovor
  - Email Mariji: MARIJA_BRIEF_08_04.md je spreman
  - memio.hr — registracija domene
  - EUIPO MEMIO trademark
  - Vučak test: https://memio.pet/pas/191031000312345/

## FISCAL SOS (HIGH — ne zaboravi):
  ⚠️ ImprovementSuggestion #30: "3 bonova bez JIR-a (47h+)" — provjeri sutra ujutro!

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
