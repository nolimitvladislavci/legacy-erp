# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-25 sesija — Compliance Shield + Concurrency Lockovi + PDV Alarm (Sonnet)
Git HEAD: c76f55a

---

## ★ 🔴 NOVI HITNI TASKOVI (2026-03-25 — ova sesija)

### Concurrency + Race Condition
| Fajl | Agent | Prioritet | Opis |
|------|-------|-----------|------|
| CC_TASK_CONCURRENCY_LOCKOVI.md | CC Code | **KRITIČAN** | select_for_update() na 4 mjesta u pos/services.py + fiscal/service.py |

### Cross-tenant GDPR
| Fajl | Agent | Prioritet | Opis |
|------|-------|-----------|------|
| CC_TASK_UNSCOPED_AUDIT.md | CC Code | **KRITIČAN** | 89 unscoped() querija — cross-tenant leak |

### PDV Alarm — Šeki
| Fajl | Agent | Prioritet | Opis |
|------|-------|-----------|------|
| PDV_ALARM_UVIJEK_FRISKO.md | CC Code | **HITNO** | Pekarski artikli na 25% umjesto 5% — provjeri inventory i live promet |

### Compliance Shield (trajni dokument)
| Fajl | Opis |
|------|------|
| COMPLIANCE_SHIELD.md | Sve zakonske prijetnje Ivanu osobno + monitoring pravila |

---

## ★ PORTAL SKEN 2026-03-25 — Kompletni nalazi

### 🔴 Bugovi
| # | Bug | Fajl | Status |
|---|-----|------|--------|
| BUG-01 | direction='IN' → MessageDirection.INBOUND | core/services/ai_hints.py | ✅ POPRAVLJENO |
| BUG-02 | pulse.py metadata__contains SQLite fix | pos/pulse.py | CC Code task |
| BUG-03 | udruga signal item_name → description | pos/signals.py | ✅ VEĆ ISPRAVNO — NE DIRAJ |
| BUG-04 | digitalni_posrednik() definirana DVAPUT | website/views.py | CC Code task |
| BUG-05 | 🔒 SECURITY: 85.9.201.204 stari IP u ALLOWED_HOSTS | core/settings.py | CC Code task — HITNO |
| BUG-06 | pricing_page() ignorira ?profile= parametar | website/views.py | CC Code task |
| BUG-07 | pulse.py fiskalizacija fail: jir kontradikcija | pos/pulse.py | CC Code task |

### 🟡 Prilike
| Prilika | Task |
|---------|------|
| N+1 queriji — analiza i fix | GEMINI_TASK_PORTAL_SCAN_FINDINGS.md |
| Celery beat reliability audit | GEMINI_TASK_PORTAL_SCAN_FINDINGS.md |
| ServiceAgreement views/templates | CC_TASK_3KLIK_REGISTRACIJA.md |
| 89 unscoped() poziva — cross-tenant | CC_TASK_UNSCOPED_AUDIT.md |
| Ghost moduli audit (fitness, gastro_menu, insurance) | GEMINI_TASK_PORTAL_SCAN_FINDINGS.md |
| public_pdf rate limiting | CC_TASK_PORTAL_BUGFIX_SPRINT.md |

### Što je dobro — NE DIRAJ
- Middleware stack: kompletan (T&C, 2FA, RateLimit, GracefulError, Language) ✅
- Security settings: HSTS, CSRF secure, SESSION secure ✅
- Registration flow step1-4: radi ✅
- CompanyManager arhitektura: ispravna ✅
- Celery beat: 40+ taskova ✅

---

## ★ JOKER PRICING + ONBOARDING REVOLUTION — Plan

### Joker Pricing Page (/pricing/)
| Profil | Preporuka | URL |
|--------|-----------|-----|
| 🔨 Obrtnik | Paušalac (0 EUR) | /pricing/?profile=obrtnik |
| ❤️ Udruga | Udruga (14.99) | /pricing/?profile=udruga |
| 🛏 Iznajmljivač | Rental (9.99) | /pricing/?profile=rental |
| 🏢 Firma | Starter/Pro/Enterprise | /pricing/?profile=firma |
| 👔 Računovođa | Arhiva+AI/Enterprise/Distributor | /pricing/?profile=racunovodja |
| 🍽 Gastro | POS/POS+Arhiva/Professional | /pricing/?profile=gastro |

**Status:** PLAN — CC_TASK_JOKER_PRICING.md (treba napisati)

---

### 3-Klik Registracija
- CompanyRegistration, CompanySubscription, PricingPlan, PromoCode ✅ postoje
- ServiceAgreement, ServiceProvider, CompanyDocument ✅ postoje
- Registration step1-4 flow ✅ radi
- **Nedostaje:** step za ServiceAgreement + ServiceProvider seed za Konjik d.o.o.
**Status:** PLAN — CC_TASK_3KLIK_REGISTRACIJA.md (treba napisati)

---

### Growth Plan 2026
| Milestone | Datum |
|-----------|-------|
| Testna faza | do 1.4.2026 — 87 firmi |
| Novo gnijezdo | Uskrs 2026 — HW spec za 1500 korisnika |

---

## TAX WIZARD — PLAN READY (2026-03-24)
Taskovi: CC_TASK_TAX_WIZARD_F1.md | GEMINI_TASK_TAX_WIZARD_F2.md | SONNET_TASK_TAX_WIZARD_F3.md

---

## POS KAO CENTAR SVIJETA (2026-03-24)
Commit: 2430991 — 14 QuickActions, 3 post-receipt hooka
Bloker: FINA API key za live eRačun test

---

## ★ BORG SYSTEM FENIX
Master plan: BORG_FENIX_MASTER_PLAN.md | Trenutna faza: FAZA 1

---

## Aktivni klijenti
| Klijent | Firma | Status |
|---------|-------|--------|
| Seki Temaj | Uvijek Frisko | LIVE — POS 3 lok, 5 term ⚠️ PDV alarm |
| Marija Brtan | Konjik d.o.o. | LIVE — fiskal 2 u toku |
| Niksa Viskovic | Viskovic Bau | ONBOARDING — DE |
| Dragan Jakovljevic | Viskovic Bau | ONBOARDING |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš | LIVE |

## Korpa klijenti (22.03.)
Korpaš d.o.o. | KUD Dukat Vladislavci | O.P.G. Kruljac Slađana | Furdi obrt | Dubinsko Čišćenje Čizo

## Superadmini
Ivan Brtan (superadmin) | Marija Brtan | Niksa Viskovic | Dragan Jakovljevic

---

## DONE — NE DIRATI

### Compliance Shield kreiran (25.03.2026) — COMPLIANCE_SHIELD.md
### PDV Alarm dokumentiran (25.03.2026) — PDV_ALARM_UVIJEK_FRISKO.md
### Concurrency task kreiran (25.03.2026) — CC_TASK_CONCURRENCY_LOCKOVI.md
### Unscoped audit task kreiran (25.03.2026) — CC_TASK_UNSCOPED_AUDIT.md
### Portal Sken Faza 2 (25.03.2026) — 7 bugova, 6 taskova
### Portal Sken Faza 1 (25.03.2026) — distribucija taskova
### BUG-01 direction fix (25.03.2026)
### BUG-03 signals.py (ISPRAVNO — potvrđeno, NE DIRAJ)
### Ured u džepu — Wizard P0 (23.03.2026) — Commit: 8a2fc66
### BORG FENIX Plan (24.03.2026)
### Synesis P1 Import (23.03.2026) — 86 firmi, 33.270 partnera, D=P ±94 EUR
### Share Modal + Nav Partial + Cashier Wizard (23.03.) — Commit: 7d49022
### Cockpit 10/10 (22.03.) — Commit: 8d44bad
### POS Simulacija (24.03.) — Commit: c76f55a — 25/25 OK
### [SVE PRETHODNO: Udruge, FINA, DE KassenSichV, EU Fondovi, AML, Payments, i18n,
### POS Offline, FenixCamera, Transport F1, Infrastruktura, Dokumenti+PDF, Mobile,
### MCP Server, WhatsApp, Tim Chat, Country Registry, AI Tools v2, Livestock,
### Intelligence, VetIS, Institutional API, limit_connect_ai F1, GTM, Invoice Growth,
### Predarhiva OCR, Predkomora, Fiskalizacija fix, Hash Chain, PLG Virus,
### OIB Validator, POS QR, Robot Plan, Security P0, Knowledge Graph,
### buyer_type, T&C consent middleware]

---

## TRAJNI RESURSI

| Fajl | Opis |
|------|------|
| COMPLIANCE_SHIELD.md | ⚖️ Zakonski štit — Ivan ne ide u zatvor |
| EU_FONDOVI_MASTER_MATRIX.md | Korisničke grupe + EU prilike |
| BORG_FENIX_MASTER_PLAN.md | 90-dnevni master plan |
| LIMIT_CONNECT_AI_PLAN.md | AI Faze 1-4 |
| GTM_PLAN_LIMIT_CONNECT_V1.md | Prodajni plan |
| CLAUDE.md | Komunikacijski protokol za agente |
| PORTAL_SCAN_2026_03_25.md | Sken Faza 1 |

---

## TASKOVI ZA AGENTE

### 🔴 KRITIČNO (radi odmah, redosljed)
| Fajl | Agent | Opis |
|------|-------|------|
| CC_TASK_CONCURRENCY_LOCKOVI.md | CC Code | select_for_update(), idempotency fiskalizacija |
| CC_TASK_UNSCOPED_AUDIT.md | CC Code | 89 unscoped() → GDPR |
| PDV_ALARM_UVIJEK_FRISKO.md | CC Code | Provjeri inventory tax_rate za Šekija |
| CC_TASK_PORTAL_BUGFIX_SPRINT.md | CC Code | BUG-02,04,05,06,07 + rate limit |

### ★ VISOKI PRIORITET
| Fajl | Agent | Prioritet |
|------|-------|-----------|
| GEMINI_TASK_PORTAL_SCAN_FINDINGS.md | Gemini | VISOK |
| GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md | Gemini | VISOK |
| GEMINI_TASK_CROSS_MODULE_POS_INVOICING.md | Gemini | VISOK |
| CC_TASK_INVOICING_BACKLOG.md | CC Code | VISOK |
| CC_TASK_API_KEY_AUTH.md | CC Code | VISOK |
| CC_TASK_SUBSCRIPTION_TRACKING.md | CC Code | VISOK |
| CC_TASK_BEEKEEPING_MODULE.md | CC Code | VISOK |
| CC_TASK_LIMIT_AI_FUNDS.md | CC Code | VISOK |
| CC_TASK_SCAN_BATCH_100.md | CC Code | VISOK — BORG Faza 1 |
| HAIKU_TASK_REALTIME_CLASSIFIER.md | Haiku | VISOK — BORG Faza 1 |
| CC_TASK_20260322_MULTI_KONOBAR_PRETPLATE.md | CC Code | VISOK |
| CC_TASK_20260323_OFFLINE_POS.md | CC Code | VISOK |
| CC_TASK_POS_REDESIGN_3KLIKA.md | CC Code | VISOK |

### SREDNJI PRIORITET
| Fajl | Agent |
|------|-------|
| CC_TASK_ROBOT_PRODAVAC_KOMPLET.md | CC Code |
| CC_TASK_TESTS_PREDKOMORA.md | CC Code |
| GEMINI_TASK_TESTS_HASHCHAIN.md | Gemini |
| GEMINI_TASK_LIMIT_AI_COMPLIANCE.md | Gemini |

### Treba napisati (backlog)
- CC_TASK_JOKER_PRICING.md
- CC_TASK_3KLIK_REGISTRACIJA.md
- CC_TASK_GLOBAL_AI_CAMERA.md
- HW_SPEC_1500_USERS.md — za Uskrs
- CC_TASK_WIZARD_NKD_BULK.md
- CC_TASK_WIZARD_BILJEZNICK_LISTA.md

### NIZAK PRIORITET
| Fajl | Agent |
|------|-------|
| CC_TASK_CLEANUP_PRINT_LOGS.md | CC Code |

---

## OTVORENO — Kritični problemi

| Problem | Hitnost |
|---------|---------|
| Race condition pos/services.py | 🔴 KRITIČAN — CC_TASK_CONCURRENCY_LOCKOVI.md |
| 89 unscoped() — GDPR rizik | 🔴 KRITIČAN — CC_TASK_UNSCOPED_AUDIT.md |
| PDV 25% za pekarske artikle Šeki | 🔴 HITNO — PDV_ALARM_UVIJEK_FRISKO.md |
| BUG-05: stari IP u ALLOWED_HOSTS | 🔴 SECURITY |
| BUG-07: pulse.py jir fail alarm | 🔴 VISOK |
| NKD NULL 86/86 firmi | VISOK |
| buyer_type b2c default (19.237 partnera) | VISOK |
| FINA/Moj-eRacun API key | VISOK |
| T&C consent 0/78 firmi | VISOK |

### DE Compliance
- Fiskaly sandbox API ključevi — CEKA
- DATEV SKR03/04 + Buchungsstapel — OTVORENO

### Wizard P2
- NKD bulk import, OIB validacija, Marija widget, T&C PDF

### Transport Faza 2, Livestock sex polje, Knjiga boljitaka (9/21)
