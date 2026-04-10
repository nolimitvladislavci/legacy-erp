# FENIX STATUS
# Zadnje azuriranje: 2026-04-10 (Opus — DIO 1 kompletiran, 7/7 stavki)
# Git HEAD: 63092572
# Server: gunicorn OK nginx OK celery OK mcp-fina OK | disk 41%

===============================================================
  CC — STARTUP PROTOKOL (citaj SVAKI PUT)
===============================================================

  KORAK 1: procitaj ovaj fajl
  KORAK 2: git log — exec: "cd /var/www/fina-connect && git log --oneline -5"
  KORAK 3: ls -lt CC_TASK_*.md | head -5
  KORAK 4: read_file na najnoviji task i izvrsavaj

===============================================================

## AKTIVNI TASKOVI (po prioritetu):

  1-8. SVE DONE (sigurnost, memio, doktor, UI audit, azil, wake, security, shell)

---

## DANAS NAPRAVLJENO (10.04.) — OPUS DIO 1:

  1. fix(pos): POSSettings za 10 firmi + Konjik fiscal_active=False
     + open_session guard (ne moze otvoriti smjenu bez POSSettings)
  2. feat(pos): BookingSignature hooks — session open + storno audit trail
  3. feat(registration): archive_readonly plan + auto-downgrade
     + login redirect na /arhiva/ za istekle pretplate
     + Celery task: downgrade_expired_subscriptions (daily)
  4. data: 15,816 ArhivaEntry ai_status none→done (status mismatch fix)
     backfill_ai_proposals task vec postoji za preostalih 4,537
  5. SKIP: Silvija vec u WS#5 (audit bio stale)
  6. feat(shell): server-rendered _panel_*.html za payroll, helpdesk, inventory
     (_shell_right_* JS hookovi vec postojali iz Faza 2)
  7. feat(core): worker dashboard redirect → workspace_home

## DANAS NAPRAVLJENO (10.04.) — SEKI DIO 2:

  8. feat(stolarija): service views, warranty portal, Celery reminders
  9. (u toku)
  10. cleanup(companies): KonjikStol model removed

---

## COMMITOVI DANAS (10.04.):

  63092572 feat(core): worker dashboard redirect → workspace_home
  90916a5e docs: update PLAN.md — tasks 9+10 complete
  447c57f2 feat(stolarija): service views, warranty portal, Celery reminders
  54b93e8f feat(registration): archive_readonly plan + auto-downgrade
  b327513a cleanup(companies): remove KonjikStol model
  3b65e0a3 feat(pos): BookingSignature hooks za session open + storno
  7719d896 fix(pos): POSSettings + Konjik + open_session guard

---

## SLJEDECI PRIORITETI:

  1. Load test priprema (CCX33, 12.04.)
  2. GO/NO-GO priprema (15.04.)
  3. Seki: stolarija servis views dovrsiti (Tjedan 2)

---

## OCJENE (10.04. — post DIO 1+2 sprint):
  LIMIT Connect backend:  9.5/10 (+ audit, archive, POS fix)
  LIMIT Connect UI/UX:    9.5/10
  Claude Doktor:          9/10
  Boxgram/memio.pet:      8.5/10
  memio.world:            6.5/10
  NO LIMIT/azil:          7.5/10
  FenixInput:             7/10
  Server:                 10/10

## POZNATI BUGOVI (otvoreni):
  FenixScan OCR: graceful fallback nedostaje (LOW)
  2 korumpirana backupa: db_20260329+30 (ne utjece na prod)
  nginx: duplicate server_name (kozmeticki)

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
