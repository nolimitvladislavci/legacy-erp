# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-24 09:30 — Sonnet (BORG FENIX plan + 4 nova task fajla)
Git HEAD: 8d44bad

---

## ★ NOVI SMJER — BORG SYSTEM FENIX (2026-03-24)
Master plan: /var/www/fina-connect/BORG_FENIX_MASTER_PLAN.md
Filozofija: Asimilacija stvarne materije (zakoni, računi, tržište) u real-time.
90-dnevni plan: 3 faze (Asimilacija → Compliance → Autonomija)
Svi novi taskovi slijede ovaj smjer.

## Aktivni klijenti
| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Frisko | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRacun, Invoicing, Konto | LIVE |
| Niksa Viskovic | Viskovic Bau | DE market, GoBD, TSE, DSFinV-K | ONBOARDING |
| Dragan Jakovljevic | Viskovic Bau | Partner (Strategie), superadmin | ONBOARDING |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš d.o.o. | Livestock, Vet, Arhiva | LIVE |

## Korpa klijenti (22.03.)
| Firma | OIB | User | Email |
|-------|-----|------|-------|
| Korpaš d.o.o. | 92922919857 | katarina.furdi | katarina.furdi@limit-connect.com |
| KUD Dukat Vladislavci | 12817544866 | kud.dukat | kud.dukat@limit-connect.com |
| O.P.G. Kruljac Slađana | 41439993573 | opg_kruljac | opg.kruljac@limit-connect.com |
| Furdi, obrt | 88069902084 | furdi.obrt | furdi.obrt@limit-connect.com |
| Dubinsko Čišćenje Čizo | 69824516722 | cizo.ciscenje | cizo.ciscenje@limit-connect.com |

## Superadmini
| User | Login | Firma |
|------|-------|-------|
| Ivan Brtan | superadmin / antonio.brtan | Platform owner |
| Marija Brtan | marija.brtan | Konjik d.o.o. |
| Niksa Viskovic | niksa.viskovic | Viskovic Bau |
| Dragan Jakovljevic | dragan.jakovljevic | Viskovic Bau |

---

## DONE — NE DIRATI

### BORG FENIX Plan (KOMPLET — 24.03.2026)
- BORG_FENIX_MASTER_PLAN.md — 90-dnevni master plan — DONE
- CC_TASK_SCAN_BATCH_100.md — batch scan do 100, 2-tipke UI — DONE (task spreman)
- GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md — legal exploit engine — DONE (task spreman)
- HAIKU_TASK_REALTIME_CLASSIFIER.md — multi-page grouping — DONE (task spreman)

### Synesis P1 Import (23.03.2026)
- 86 firmi, 33.270 partnera, 11.856 artikala — DONE
- Fakture: 10.206 uvezenih — DONE
- Stavke knjiženja: ~110.000 · Temeljnice: ~17.000 — DONE
- Globalna bilanca: D=P ±94 EUR — BALANSIRA

### Share Modal + Nav Partial + Cashier Wizard (KOMPLET — 23.03.)
- Commit: 7d49022

### Cockpit 10/10 (KOMPLET — 22.03.)
- Commit: 8d44bad, 9d7a68a, 8b5eb7f

### Livestock/Vet modul bugfixi (22.03.) — DONE

### Korpa firme registracija (22.03.) — DONE

### [SVE PRETHODNO — NEPROMIJENJENO]
### Udruge modul, FINA izvjestaji, DE KassenSichV, EU Fondovi, AML, Payments, i18n,
### POS Offline, FenixCamera, Transport Faza 1, Synesis Import, Infrastruktura,
### Sales + Onboarding, Dokumenti + PDF, Mobile, MCP Server, WhatsApp, Tim Chat,
### Country Registry, AI Tools v2, Livestock, Intelligence, VetIS, Institutional API,
### limit_connect_ai Faza 1, GTM Foundation, Invoice Growth Engine, Predarhiva OCR,
### Predkomora, Fiskalizacija fix, Hash Chain, PLG Virus, OIB Validator, POS QR, Robot Plan

---

## TASKOVI ZA AGENTE

### ★ BORG FENIX — VETO AKTIVAN (24.03.)
### CC Code BLOKIRAN dok Gemini ne završi KNOWLEDGE_GRAPH_MODELS

## ★ BORG FENIX — Faza 1
| Fajl | Agent | Prioritet |
|------|-------|-----------|
| CC_TASK_SCAN_BATCH_100.md | CC Code | **VISOK** |
| HAIKU_TASK_REALTIME_CLASSIFIER.md | Haiku (via Celery) | **VISOK** |
| GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md | Gemini | **VISOK** |

### Stari aktivni taskovi
| Fajl | Agent | Prioritet |
|------|-------|-----------|
| CC_TASK_20260322_MULTI_KONOBAR_PRETPLATE.md | CC | **VISOK** |
| CC_TASK_20260323_OFFLINE_POS.md | CC | **VISOK** |
| CC_TASK_POS_REDESIGN_3KLIKA.md | CC | **VISOK** |
| CC_TASK_ROBOT_PRODAVAC_KOMPLET.md | CC | SREDNJI |
| CC_TASK_TESTS_PREDKOMORA.md | CC | SREDNJI |
| GEMINI_TASK_TESTS_HASHCHAIN.md | Gemini | SREDNJI |
| GEMINI_TASK_LIMIT_AI_COMPLIANCE.md | Gemini | SREDNJI |

### Treba napisati (backlog)
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi Faza 2

---

## OTVORENO

### Livestock
- sex polje direktno na modelu — OTVORENO
- Testovi (47) — provjeri rezultate

### DE Compliance
- Fiskaly sandbox (treba API ključeve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO
- Steuernummer validacija — NEDOSTAJE

### Knjiga boljitaka (9/21 preostalo)
- B-01, B-05, B-06, B-09, B-10, B-11, B-13, B-17, B-21

### Transport Faza 2
- CMR auto, multi-country routing, kabotaža, Driver PWA
