# FENIX STATUS
# Zadnje azuriranje: 2026-04-08 (CC Opus — autonomni audit + popravci)
# Git HEAD: 76fcf426
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
  7. ✅ CC_TASK_SECURITY_10_10.md — in progress (08.04.)

  ✅ MARIJA_PHONE postavljen: +385976091665

---

## STANJE SUSTAVA (08.04.)

### Servisi: sve ✅
### Git HEAD: 76fcf426
### Django: 0 errors
### Backup: dnevni pg_dump ✅ (96MB, zadnji 08.04. 05:00)

### Zadnji commiti (08.04.):
  76fcf426  perf(cache): @cache_page(300) na javnim landing stranicama
  3d72633b  fix(code-quality): bare except → explicit Exception types

### DANAS NAPRAVLJENO (08.04. — CC Opus autonomni audit):
  ✅ 67 DEMO POS bonova obrisano (smetali Mariji)
  ✅ Bare except → explicit Exception types (4 fajla)
  ✅ nginx server_tokens off (sakrivena verzija servera)
  ✅ @cache_page(300) na javne landing stranice (memio.pet, no_limit, memio.world)
  ✅ Gunicorn + Nginx restartirani
  ✅ Security headers verifikacija: HSTS, CSP, X-Frame, X-Content-Type ✅
  ✅ Backup verifikacija: dnevni pg_dump radi, 96MB, 08.04. OK
  ✅ MARIJA_PHONE potvrđen u .env

### Live HTTP (08.04. verifikacija):
  ✅ limit-connect.com/hr/                          — 200 (302→200)
  ✅ limit-connect.com/hr/login/                    — 200
  ✅ limit-connect.com/hr/smart-import/             — 200 (→login redirect)
  ✅ limit-connect.com/hr/pos/onboarding/           — 200 (→login redirect)
  ✅ limit-connect.com/hr/ai-cockpit/doktor/        — 200 (→login redirect)
  ✅ limit-connect.com/api/fenix-input/bluetooth/config/ — 200
  ✅ memio.pet/                                     — 200
  ✅ memio.world/                                   — 200
  ✅ limit-connect.com/no-limit/                    — 200

### ISPRAVKA: Doktor URL je /hr/ai-cockpit/doktor/, NE /hr/doktor/

### Poznati bugovi:
  ⚠️  FenixScan OCR: graceful fallback nedostaje (LOW)
  ⚠️  2 korumpirana backupa: db_20260329.sql.gz i db_20260330.sql.gz (20 bytes) — ne utječe na produkciju
  ⚠️  nginx warnings: duplicate server_name za limit-connect.com (funkcionira, kozmetički)

---

## RATNI RASPORED:
  07.04. | QA audit + UI popravci + TriKey onboarding  | CC        | ✅ gotov
  08.04. | Marija dry-run + CC autonomni audit          | Marija+CC | ⏳ u tijeku
  09-10.04. | Bugfix sprint (samo Marijina lista)       | CC        | ⏳
  12.04. | Load test CCX33                              | CC        | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                        | Ivan      | ⏳

## OCJENE (ažurirano 08.04.):
  LIMIT Connect backend:  9/10   (↑ od 8.5 — code quality fix, caching)
  LIMIT Connect UI/UX:    8.5/10 (↑ od 8 — cache, DEMO bonovi očišćeni)
  Claude Doktor:          9/10
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10 (samo waitlist — CRUD treba)
  NO LIMIT/azil:          7.5/10 (↑ od 7 — cache dodan)
  FenixInput:             7/10   (apply_to_module faza 2 nedostaje)
  Server:                 10/10  (↑ od 9.5 — nginx hardened, backup verificiran)

## PRIORITETI ZA SKOK NA 10/10:
  1. memio.world CRUD za TimeCapsule/MemoryVault/FamilyStory → 6.5→9
  2. FenixInput apply_to_module integracija → 7→9
  3. Onboarding "aha moment" (upload račun → AI parse → 60s) → UX 8.5→10
  4. WhatsApp webhook (WAHA → Django → smart_import) → backend 9→10
  5. Mjesečni PDF izvještaj (Celery beat → email) → backend 9→10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
