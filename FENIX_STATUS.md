# FENIX STATUS
# Zadnje azuriranje: 2026-04-06 00:30
# Git HEAD: a9737466
# Server: gunicorn ✅ nginx ✅ celery ✅ mcp-fina ✅ | disk 39%

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

  1. CC_TASK_WAKE.md            ← KRENI OVDJE (TriKey + login template)
  2. CC_TASK_F1_UI_AUDIT.md     ← UI/UX audit LIMIT Connect
  3. CC_TASK_F2_MEMIO_PET_ONBOARDING.md  ← memio.pet registracija
  4. CC_TASK_F3_MEMIO_WORLD.md  ← memio.world landing
  5. CC_TASK_F5_NO_LIMIT_AZIL.md ← azil mobile POS

  Čitaj svaki s: read_file /var/www/fina-connect/CC_TASK_IME.md

---

## STANJE SUSTAVA (06.04. 00:30)

### Servisi: sve ✅
### Git HEAD: a9737466
### Django: 0 errors

### Novi commiti ove sesije:
  a9737466  docs(status): FENIX_STATUS.md ažuriran
  95f0a6f9  fix(pdf): CSS var() → inline (22 templates, xhtml2pdf crash fix)
  fb5703b2  fix(boxgram): signals + video_downloader

### Izgrađeno (CC ova sesija):
  ✅ boxgram/       — PetProfile, Feed, Competition, SocialImport, bridge
  ✅ memio_world/   — WaitlistEntry, TimeCapsule, MemoryVault, FamilyStory
  ✅ no_limit/      — AzilPrijava, PDF vodič, azil prijava, dashboard

### Live HTTP:
  ✅ memio.pet/boxgram/ljubimac/rex-pas-232d99f5/   — 200
  ✅ memio.pet/boxgram/ljubimac/bella-pas-c94b0fa2/ — 200
  ✅ memio.pet/boxgram/feed/                        — 200
  ✅ limit-connect.com/no-limit/vodic/              — 200
  ✅ limit-connect.com/hr/                          — 302→login

### Poznati bugovi:
  ⚠️  TriKey: 0 profila — nitko nema PIN (CC_TASK_WAKE.md)
  ⚠️  FenixScan OCR: graceful fallback nedostaje (LOW)
  ✅  PDF xhtml2pdf crash: RIJEŠEN (95f0a6f9)

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci + TriKey onboarding  | CC+Gemini | 🔥
  08.04. | Marija dry-run                               | Marija    | ⏳
  12.04. | Load test CCX33                              | CC        | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                        | Ivan      | ⏳

## PENDING (Ivan odlučuje):
  - Konjik: Scenarij A (639€/mj)
  - MARIJA_BRIEF_08_04.md — Ivan šalje email Mariji
  - memio.hr — registracija domene
  - EUIPO MEMIO trademark

## OCJENE:
  LIMIT Connect backend:  8.5/10
  LIMIT Connect UI/UX:    6.5/10 ← F1 task
  Boxgram/memio.pet:      7.5/10
  memio.world:            4/10
  NO LIMIT/azil:          5/10
  Server:                 9.5/10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
