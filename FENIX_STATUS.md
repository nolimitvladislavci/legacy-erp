# FENIX STATUS
# Zadnje azuriranje: 2026-04-04 — Sonnet (verifikacija CC analize)
# Git HEAD: 2d0d4e5d
# Tabla: CISTA

---

VIKEND SPRINT — ZATVOREN (04.04.2026.)
13 commitova | 77+ fajlova | ~4.100+ linija | 9 migracija | 0 errora

DONE:
  Commit 1-5  | +2253 lin | Simbioza, Arhiva, Synesis, Fenix Inbox, Udruge-Konto
  Commit 6    | 5f2fbfc   | Synesis B finalizacija (warm_cache, 35 cache keys)
  Commit 7    | 9da52b9   | DRON3 CSS kirurgija (26 design tokens, 159 hex→var())
  Commit 8    | 9ca77b8   | Notariat PDF (WeasyPrint, SHA-256, tarifa)
  Commit 9    | fb72a80   | DRON2 Onboarding wizard (3-field quick reg, wizard 5 sekcija)
  Commit 10   | 1720fe8   | DRON2 tc_consent fix
  Commit 11   | 39c339a   | REG redizajn 10/10 (theme, mikrofon, pet, FenixCamera/Scan/QR)
  Commit 12   | 2d0d4e5   | BARF Marketplace + Njuškalo Trust Badge SVG ✅

---

CC ANALIZA — VERIFICIRANA 04.04.2026. (Sonnet):

  ✅ Smart Entry /pocni/   — POTVRĐENO: ne postoji, treba kreirati
  ✅ Landing 2026          — POTVRĐENO: ne postoji, treba kreirati
  ✅ WhiteLabel Engine     — POTVRĐENO: ne postoji, treba kreirati
  ✅ Agent Dashboard       — POTVRĐENO: stari view (1045: def agent_dashboard), treba v2
  ✅ LicenseToken          — POTVRĐENO: ne postoji, treba kreirati
  ✅ BARF Badge            — POTVRĐENO: modeli postoje (RawFoodListing, RawFoodOrder,
                             barf_partner bool), views i templates nedostaju
  ✅ Cross-Company Dash    — POTVRĐENO: postoji (SUPERADMIN level), radi
  ✅ Client Portal UX      — POTVRĐENO: portal_upload + portal_pdv_approve u partners/
  ✅ FINA Posrednik        — POTVRĐENO: CIUS-HR UBL pipeline, čeka sandbox test

  BAZA STANJE (verificirano):
    33.299 partnera | 15.327 faktura | 10.732 journal entries
    9 SynesisConfig firmi (meta prazna — uvoz bio direktan u bazu) ← važno za Synesis+

---

AKTIVNI CC TASKOVI (pokrenuti 04.04.):
  CC_TASK_SMART_ENTRY.md          → P0 — /pocni/ + magic link + email detect
  CC_TASK_LANDING_2026.md         → P0 — nova landing page (HR, konverzijska)
  CC_TASK_AGENT_DASHBOARD_10.md   → P0 — /moji-klijenti/ v2 (QR, komisija, ghost)
  CC_TASK_WHITELABEL_ENGINE.md    → P0 — WhiteLabelConfig + middleware + CSS
  CC_TASK_LICENSE_TOKEN.md        → P1 — LicenseToken + heartbeat + suspended.html
  CC_TASK_BARF_BADGE.md           → P2 — views + templates (modeli postoje)

AKTIVNI GEMINI TASKOVI:
  GEMINI_TASK_SYNESIS_PLUS.md     → Analiza Synesis+ asimilacije (kreirati)

---

RATNI RASPORED:

  05.04. | SmartEntry + Landing live         | CC Code   | 🔥
  05.04. | Agent Dashboard v2                | CC Code   | 🔥
  06.04. | WhiteLabel Engine live            | CC Code   | 🔥
  06.04. | LicenseToken + Heartbeat          | CC Code   | 🔥
  07.04. | BARF views + templates            | CC Code   | ⏳
  07.04. | Distributer onboarding form       | CC Code   | ⏳
  08.04. | Marija: JournalEntry --dry-run    | Marija    | ⏳
  12.04. | Load test (CCX33)                 | Sonnet+CC | ⏳
  14.04. | DNS cutover priprema              | Sonnet    | ⏳
  15.04. | GO/NO-GO                          | Ivan+Marija | ⏳
  15.04. | PRODUKCIJA 0-downtime             | Sonnet+CC | ⏳

---

SERVER PLAN:

  Server 1: 85.9.201.204 (stari UpCloud) → dev/staging
  Server 2: 37.27.248.86 (Hetzner) → produkcija #1 (sad)
  Server 3+4: 2x CCX33 → u narudžbi (po planu)
  setup_new_server.sh + warm_cache + prod_monitor.sh: spreman ✅

---

SYNESIS+ ANALIZA — vidi GEMINI_TASK_SYNESIS_PLUS.md

---

BORG FENIX (04.04.2026.):
  Invoicing, POS, Konto, Worktime, Rental, Tax Wizard,
  Udruge (9 segmenata + dvojno knjizenje), Arhiva,
  Transport, BORG Ops, Seasonal, Notariat, memio.pet,
  Fenix Inbox, AI, Registracija, BARF Marketplace — SVI ASIMILIRANI

SIMBIOZA TROKUT: zatvoren ✅
SYNESIS: 92.3% ✅ | Faza B (JournalEntry) ceka Mariju ⏳ 08.04.
GMAIL OAUTH: ceka Ivan ⏳
MARIJA_WHATSAPP: privremeno iskljucen ⏳

---

IVAN — HITNE AKCIJE:
  1. 2x Hetzner CCX33 — u narudžbi (po planu) ✅
  2. Gmail OAuth credentials              → ovaj tjedan
  3. memio.hr registracija                → odmah
  4. Marija: JournalEntry dry-run pregled → 08.04.
  5. MEMIO konzorcij — Marija Cacic       → ovaj tjedan
  6. EUIPO TMview — MEMIO trademark       → ovaj tjedan

---

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
