# FENIX STATUS
# Zadnje azuriranje: 2026-04-06 (Sonnet — POS bugovi fiksirani)
# Git HEAD: 9cf2a8df
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

  1. ✅ CC_TASK_WAKE.md
  2. ✅ CC_TASK_F1_UI_AUDIT.md         — UI 6.5→8/10
  3. ✅ CC_TASK_F2_MEMIO_PET_ONBOARDING.md
  4. ✅ CC_TASK_F3_MEMIO_WORLD.md
  5. ✅ CC_TASK_F5_NO_LIMIT_AZIL.md
  6. ✅ CLAUDE_DOKTOR — sve napravljeno (9 zadataka, test 97/100)

  ⚠️  PENDING: zamijeni +385XXXXXXX s pravim brojem Marije u .env (MARIJA_PHONE)

---

## STANJE SUSTAVA (06.04.)

### Servisi: sve ✅
### Git HEAD: 9cf2a8df
### Django: 0 errors

### Zadnji commiti:
  d2d2fc19  fix(memio-pet): svjećica — csrf_exempt + brisanje 3 duplikata
  2502d264  feat(memio-pet): GDPR consent kompletni flow
  31a0d1e1  feat(memio-pet): Web Share API — native dijeljenje profila

### CLAUDE DOKTOR — DONE (06.04.)
  ✅ grand_total fix — overdue_30_amount koristi Sum('total')
  ✅ DiagnosisReport import u models.py
  ✅ Migration 0009_add_diagnosis_report primijenjena
  ✅ URL-ovi: /doktor/, /doktor/<id>/, /superadmin/doktor/, /doktor/<id>/trigger/
  ✅ Templates: doktor_dashboard.html + doktor_superadmin.html
  ✅ MARIJA_PHONE dodan u .env i settings.py (placeholder — zamijeniti!)
  ✅ Celery beat: claude-doktor-nightly (svaka 3h)
  ✅ celery.py autodiscover limit_connect_ai.tasks_doktor
  ✅ gunicorn + celery restartani
  📊 Test: Konjik d.o.o. — 97/100, AI summary na HR, status done

### NOVOST: FenixInput modul (fenix_input/)
  GLOBALNI ulazni kanal: VOICE, SMS, BT, EMAIL (faza 2)
  - JS widget: fenix-input.js — <div data-fenix-input></div>
  - API: /api/fenix-input/voice|sms|confirm|history|bluetooth/config
  - Modeli: InputMessage, SMSDevice

### Riješeni bugovi:
  ✅ memio.pet registracija/prijava — email_hash lookup
  ✅ Chip number validacija — ISO 11784 (9-15 znamenki)
  ✅ Dugini Most — memorial auto-create + UI
  ✅ svjećica endpoint — csrf_exempt fix
  ✅ GDPR consent flow komplet

### Live HTTP:
  ✅ limit-connect.com/hr/                          — 200
  ✅ limit-connect.com/api/fenix-input/bluetooth/config/ — 200
  ✅ memio.pet/                                     — 200
  ✅ memio.world/                                   — 200

### Poznati bugovi:
  ⚠️  FenixScan OCR: graceful fallback nedostaje (LOW)
  ⚠️  MARIJA_PHONE: zamijeniti placeholder u .env

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci + TriKey onboarding  | CC        | ✅ gotov
  08.04. | Marija dry-run                               | Marija    | ⏳
  12.04. | Load test CCX33                              | CC        | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                        | Ivan      | ⏳

## OCJENE:
  LIMIT Connect backend:  8.5/10
  LIMIT Connect UI/UX:    8/10
  Claude Doktor:          9/10   (NOVO — 97/100 test)
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10
  NO LIMIT/azil:          7/10
  FenixInput:             7/10
  Server:                 9.5/10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
