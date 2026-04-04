# FENIX STATUS
# Zadnje azuriranje: 2026-04-05 — Sesija završena
# Git HEAD: 1ee97a7a
# Server: gunicorn ✅ celery ✅ nginx ✅ | disk 39% | RAM 51%

---

SESIJA 04-05.04.2026. — SAŽETAK

Commiti:
  1ee97a7a  chore: RouteRegistry memio_pet PUBLIC, nginx fix, CC taskovi
  33951400  POS Joker final: FenixCamera, dark/light, customer display
  711935c4  POS Joker: AI upsell, stock badge, loyalty, offline, gym
  10dcc880  memio.pet: dark/light toggle OS-aware
  cc2be21b  7 nepravilnosti N1-N7
  eb46fff8  Utilities modul komplet
  99795f51  PDV-S + overtime ZOR 50%
  41bb3e9b  5 konto chain errors
  8620cc6a  7 accounting gaps

---

AKTIVNI CC TASKOVI (novi sprint):

  CC_TASK_POS_10_10.md       → POS 7.8 → 10/10
    B1: quick_pos → redirect joker (eliminira legacy quick.html)
    B2: R1 checkbox + OIB input u joker pay-zone
    B3: loyalty_earned u success overlay
    B4: stock badge na prod-btn
    B5: base_pos.html theme dark default fix
    B6: paySplit() + R1/OIB parametre
    B7: Z-report komplet (CT, R1, split, loyalty)

  CC_TASK_RIST_6_PROBLEMA.md → Matematika + sigurnost
    G1: round() → quantize(ROUND_HALF_UP) u InvoiceItem
    G2: Forex razlika → konto 3415/4700
    G3: OIB lookup rate limit (30 req/60s)
    G4: Consumption tax: dokumentacija po artiklu
    D1: Zombi zaposlenik: termination_date provjera
    D2: Integrity hash: immutable nakon prvog save

  CC_TASK_FRONTEND_GLOBALS.md → JS konsolidacija
    F1: window.showToast conflict (pos-quick vs pos-receipt)
    F2: window.FC proširenje (csrfToken, companyId, userId)

---

MEMIO STATUS:

  memio.pet: RouteRegistry memio_pet:* → PUBLIC (bila 302!)
  Nginx memio.pet: /barf/ /hotel/ /dresura/ /badge/ dodani
  POTREBNO: nginx -s reload (Ivan ili CC Code)

  Baze:
    fina_erp    → LIMIT Connect ERP ✅
    memio_pets  → memio.pet (ljubimci) ✅
    memio_world → NE POSTOJI — potrebno kreirati
    Plan: nova baza + Django app + WaitlistEntry migracija iz memio_pets

---

RATNI RASPORED:
  06.04. | POS 10/10 + RIST + memio.world baza | CC Code  | 🔥
  07.04. | QA + final audit                     | CC+Sonnet| 🔥
  08.04. | Marija dry-run + ambasador brief      | Marija   | ⏳
  12.04. | Load test (CCX33)                    | CC       | ⏳
  14.04. | DNS cutover priprema                  | Ivan     | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                 | Ivan+Marija | ⏳

PENDING (Ivan):
  - nginx -s reload (memio.pet nove rute)
  - Gmail OAuth credentials
  - memio.hr registracija
  - EUIPO MEMIO trademark
  - HZZ Osijek kvotni upit
  - Marija: email 08.04.

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
