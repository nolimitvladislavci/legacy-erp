# FENIX STATUS
# Zadnje azuriranje: 2026-04-05 — Sonnet
# Git HEAD: 33951400
# Tabla: 3 AKTIVNA TASKA

---

ZATVORENO:
  33951400  POS Joker final — FenixCamera, dark/light, customer display
  10dcc880  memio.pet dark/light toggle (OS-aware)
  cc2be21b  7 nepravilnosti N1-N7

---

AKTIVNI CC TASKOVI:
  CC_TASK_POS_10_10.md         P0  POS do 10/10 — B1-B7 (R1 UI, loyalty, quick→joker, Z-report)
  CC_TASK_RIST_6_PROBLEMA.md   P0  round→quantize, forex, OIB rate, CT, zombi, hash
  CC_TASK_FRONTEND_GLOBALS.md  P1  Toast conflict, FC proširenje

---

MATEMATIKA ZAŠTO 7.8/10:
  joker.html (primary)         → 9.5/10 ← svi novi featrsi
  quick.html (direktan URL)    → 6.5/10 ← bez split, bez R1 UI, bez stock badge
  Prosjek                      → 7.8/10

  RUPE U JOKERU (backend radi, UI ne):
  - R1 checkbox + OIB input NE POSTOJE u joker.html
  - pay() ne šalje is_r1/buyer_oib serveru
  - loyalty_earned iz response-a se ne prikazuje
  - stock badge postoji u kontekstu, ne u HTML-u

  FIX:
  B1: quick_pos → redirect joker (jednom za svagda)
  B2: R1 OIB UI u joker pay-zone
  B3: loyalty earned u success overlay
  B4: stock badge na prod-btn
  B5: base_pos theme init ispravak
  B7: Z-report: CT, R1, split, loyalty

---

MEMIO.PET STATUS:
  RouteRegistry: memio_pet:* dodano → PUBLIC ✅
  Nginx: /barf/ /hotel/ /dresura/ /badge/ location blokovi ✅
  Restart Nginx potreban: nginx -s reload

MEMIO BAZE:
  fina_erp   → LIMIT Connect ERP ✅
  memio_pets → memio.pet (ljubimci) ✅
  memio_world → NE POSTOJI — treba kreirati
  Plan: nova baza + Django app za memio.world (WaitlistEntry migracija)

---

RATNI RASPORED:
  06.04. | POS 10/10 + RIST fixovi        | CC Code   | 🔥
  06.04. | Nginx reload (memio.pet rute)   | Ivan/CC   | 🔥
  07.04. | QA + final audit 10/10          | CC+Sonnet | 🔥
  08.04. | Marija dry-run                  | Marija    | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA           | Ivan+Marija | ⏳

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
