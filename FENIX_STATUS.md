# FENIX STATUS — Koordinacijski fajl
# Zadnje azuriranje: 2026-03-25 — ZAPOVJEDNIČKA SESIJA (Sonnet)
# Git HEAD: f8c58a9
# PRAVILO: Ako nesto pise DONE — NE RADIS PONOVO.

---

## ★ RATNI RASPORED — 7 DANA DO 1.4.2026

| Dan | Datum | Zadatak | Odgovorni | Status |
|-----|-------|---------|-----------|--------|
| 0 | 25.3. | Race condition, PDV, NKD, alert→toast, BUG-05 | Sonnet | ✅ DONE |
| 0 | 25.3. | 6 Gemini/Haiku taskova pokrenuta | Sonnet | 🔄 U TIJEKU |
| 1 | 26.3. | DNS TTL → 60s (Ivan ručno, Hetzner panel) | **IVAN** | ⏳ ČEKA |
| 1 | 26.3. | Putni nalog templates | CC Code | ⏳ ČEKA |
| 2 | 27.3. | Joker Pricing + 3-klik registracija | CC Code | ⏳ ČEKA |
| 3 | 28.3. | Unscoped audit finish + GDPR | CC Code | ⏳ ČEKA |
| 4 | 29.3. | Vatrogasci modul (dnevnik intervencija) | CC Code | ⏳ ČEKA |
| 5 | 30.3. | Novi server naručiti (Hetzner CPX51) | **IVAN** | ⏳ ČEKA |
| 5 | 30.3. | Server priprema + load test | Sonnet+CC | ⏳ ČEKA |
| 7 | 1.4. | **MIGRACIJA 03:00** — 0-downtime | Sonnet | ⏳ ČEKA |
| 7 | 1.4. | **VRATA OTVORENA** — 87 firmi probni pristup | Ivan | ⏳ ČEKA |

---

## ★ AGENTI U ZRAKU (2026-03-25 21:21)

| Task ID | Agent | Zadatak | Status |
|---------|-------|---------|--------|
| d447b1fd | Gemini | VATROGASCI_GTM_REPORT.md | 🔄 |
| b2e45215 | Gemini | PUTNI_NALOG_COMPLIANCE_REPORT.md | 🔄 |
| f7f28532 | Gemini | N+1 fix + N1_FIXES_REPORT.md | 🔄 |
| b6c7079e | Gemini | COMPLIANCE_WATCHDOG_REPORT_20260325.md | 🔄 |
| 8b481281 | Haiku | Unscoped audit + UNSCOPED_FIX_REPORT.md | 🔄 |
| 97128557 | Haiku | TravelExpense ai_classified + Celery task | 🔄 |

---

## ★ DEPLOYAN DANAS (25.03.2026) — STVARAN KOD, NE PLAN

| Što | Commit | Opis |
|-----|--------|------|
| Race condition fix | 19912ac | select_for_update() pos/services.py, fiscal idempotency |
| PDV 5% Šeki | 19912ac | 12 pekarskih artikala 25%→5% direktno u bazi |
| Admin TravelOrder bug | 19912ac | try/except wrap, admin radi |
| NKD 74→331 kodova | c734571 | Hijerarhija, auto-assign 42/42 firmi, 100% pokrivenost |
| NKD 84.25 vatrogasci | 1abf5a1 | + 8 novih kodova za vatrogasni sektor |
| alert()→fenixNetworkError | dee9c89 | 23 mjesta, auto-log u ImprovementSuggestion |
| BUG-05 stari IP | f8c58a9 | 85.9.201.204 uklonjen iz ALLOWED_HOSTS |
| Udruge segment templates | f8c58a9 | DVD, KUD, ribari, pčelari, rakijari, voćari |
| udruge migracija 0009 | f8c58a9 | Destilacija, Kostim, i ostali modeli live |

---

## ★ IVAN — AKCIJE ZA TEBE (ne može nitko drugi)

| Prioritet | Akcija | Zašto hitno |
|-----------|--------|-------------|
| 🔴 1. | DNS TTL → 60s na Hetzner panelu | Mora stajati 24h prije migracije |
| 🔴 2. | Naruči Hetzner CPX51 (35 EUR/mj) | Treba za 1.4. migraciju |
| 🟠 3. | Šeki WhatsApp: "Kruh i pecivo smo ispravili na 5% PDV" | Preventiva za inspekciju |
| 🟡 4. | FINA/Moj-eRacun API key | eRačun live test blokiran bez toga |

---

## TASKOVI ZA CC CODE (redosljed izvršavanja)

### 🔴 ODMAH (blokira otvaranje vrata)
| Fajl | Opis |
|------|------|
| CC_TASK_PUTNI_NALOG_TEMPLATES.md | 3 templates + PDF — KUD/DVD nemaju modul bez ovog |
| CC_TASK_JOKER_PRICING.md | /pricing/?profile= — novi korisnici ne znaju što kliknuti |
| CC_TASK_3KLIK_REGISTRACIJA.md | OIB auto-fill, ServiceProvider seed |
| CC_TASK_PORTAL_BUGFIX_SPRINT.md | BUG-02,04,06,07 + rate limit |

### 🟠 VISOKI (ovaj tjedan)
| Fajl | Opis |
|------|------|
| CC_TASK_UNSCOPED_AUDIT.md | GDPR — Haiku u tijeku, CC verificira |
| CC_TASK_VATROGASCI_MODUL.md | FireIntervention model + atest alarm |
| CC_TASK_NKD_KOMPLET.md | Management command (Sonnet već dodao 331 kodova direktno) |
| CC_TASK_SUBSCRIPTION_TRACKING.md | ARR/MRR cockpit metrics |
| CC_TASK_BEEKEEPING_MODULE.md | Pčelari — 11k u HR |
| CC_TASK_API_KEY_AUTH.md | Passwordless API |

### 🟡 SREDNJI (travanj)
| Fajl | Opis |
|------|------|
| CC_TASK_SCAN_BATCH_100.md | BORG Faza 1 |
| CC_TASK_INVOICING_BACKLOG.md | Flow diagram, clone, expiry |
| CC_TASK_20260323_OFFLINE_POS.md | Offline POS |
| CC_TASK_POS_REDESIGN_3KLIKA.md | POS redesign |
| CC_TASK_LIMIT_AI_FUNDS.md | EU fondovi workflow |
| CC_TASK_VATROGASCI_MODUL.md | DVD dnevnik intervencija |

---

## TASKOVI ZA GEMINI (u izvršavanju)
→ Vidi tablicu "AGENTI U ZRAKU" gore

### Sljedeći Gemini taskovi (nakon završetka tekućih)
- GEMINI_TASK_CROSS_MODULE_POS_INVOICING.md
- GEMINI_TASK_TAX_WIZARD_F2.md

---

## TRŽIŠNI SEGMENTI — UDRUGE MAPA

| Segment | HR tržište | Status | Što već radi |
|---------|-----------|--------|-------------|
| KUD-ovi | ~2.000 | ✅ Templates live | POS, putni nalozi, volonteri |
| DVD-ovi | ~1.800 | ✅ Templates live | POS, putni nalozi, volonteri |
| ŠRD (ribari) | ~800 | ✅ Templates live | POS, dozvole, reviri |
| Lovačka društva | ~600 | ✅ Templates live | POS, dozvole |
| Pčelari | ~11.000 | ✅ Templates live | POS, košnice, med |
| Voćari/OPG | ~60.000 | ✅ Templates live | POS, berbe, tretmani |
| Rakijari | ~5.000 | ✅ Templates live | Kotlovi, destilacije, trosarina |
| Vatrogasci (JVP) | ~30 | 🔨 CC task | FireIntervention model |

**UKUPNO adresabilno: ~80.000 organizacija u HR. Nebo je plavo.**

---

## AKTIVNI KLIJENTI
| Klijent | Firma | Status |
|---------|-------|--------|
| Seki Temaj | Uvijek Friško | LIVE ⚠️ PDV fix deployan |
| Marija Brtan | Konjik d.o.o. | LIVE — fiskal 2 u toku |
| Niksa Viskovic | Viskovic Bau | ONBOARDING DE |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš | LIVE |
| KUD Dukat Vladislavci | — | KORPA klijent |

---

## KRITIČNI OTVORENI PROBLEMI

| Problem | Hitnost | Tko |
|---------|---------|-----|
| DNS TTL (28 min → 60 sec) | 🔴 Ivan mora danas | Ivan |
| Novi server narudžba | 🔴 Do 30.3. | Ivan |
| T&C consent 0/78 firmi | 🟠 Pravni rizik | CC Code |
| FINA eRačun API key | 🟠 Bloker za live | Ivan |
| buyer_type b2c default 19k partnera | 🟡 | CC Code |

---

## DONE — NE DIRATI

### 2026-03-25 (ova sesija)
- Race condition + fiscal idempotency
- PDV Šeki 25%→5% (12 artikala)
- NKD 74→331, auto-assign 100%
- NKD 84.25 vatrogasci + 8 kodova
- alert()→fenixNetworkError() (23 mjesta)
- BUG-01, BUG-05
- Udruge segment templates (DVD, KUD, ribari, pčelari, rakijari, voćari)
- HW_SPEC_1500_USERS.md
- 6 agenata pokrenuto u pozadinu

### [SVE PRETHODNO — NEPROMIJENJENO]
- Udruge POS bypass, FINA, DE KassenSichV, EU Fondovi, AML, Payments,
- POS Offline, FenixCamera, Transport, Infrastruktura, Dokumenti+PDF,
- Mobile, MCP Server, WhatsApp, Tim Chat, Country Registry, AI Tools v2,
- Livestock, Intelligence, VetIS, Institutional API, limit_connect_ai F1,
- GTM, Invoice Growth, Predarhiva OCR, Fiskalizacija fix, Hash Chain,
- PLV Virus, OIB Validator, POS QR, Robot Plan, Security P0,
- Knowledge Graph, buyer_type, T&C middleware, Cockpit 10/10,
- POS Simulacija 25/25, BORG Plan, Synesis P1, Share Modal, Wizard P0

---

## TRAJNI RESURSI
| Fajl | Opis |
|------|------|
| COMPLIANCE_SHIELD.md | ⚖️ Zakonski štit — Ivan ne ide u zatvor |
| HW_SPEC_1500_USERS.md | Server specifikacija za 1.500 korisnika |
| VATROGASCI_ANALIZA.md | Vatrogasci tržišna analiza |
| EU_FONDOVI_MASTER_MATRIX.md | EU prilike po segmentima |
| BORG_FENIX_MASTER_PLAN.md | 90-dnevni plan |
| CLAUDE.md | Komunikacijski protokol za agente |
