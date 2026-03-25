# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-25 sesija — Invoicing fixes LIVE + PDF sekcije + WhatsApp + Redirecti (Sonnet)
Git HEAD: c76f55a

---

## ★ JOKER PRICING + ONBOARDING REVOLUTION — Plan (2026-03-25)

### Joker Pricing Page (/pricing/)
**Filozofija:** Korisnik kaže tko je → BORG mu kaže što treba. Bez 11 kartica.

**6 profila → 1-3 kartice po profilu:**
| Profil | Preporuka | URL |
|--------|-----------|-----|
| 🔨 Obrtnik | Paušalac (0 EUR) | /pricing/?profile=obrtnik |
| ❤️ Udruga | Udruga (14.99) | /pricing/?profile=udruga |
| 🛏 Iznajmljivač | Rental (9.99) | /pricing/?profile=rental |
| 🏢 Firma | Starter/Pro/Enterprise | /pricing/?profile=firma |
| 👔 Računovođa | Arhiva+AI/Enterprise/Distributor | /pricing/?profile=racunovodja |
| 🍽 Gastro | POS/POS+Arhiva/Professional | /pricing/?profile=gastro |

**4 kutna dugmeta (uvijek vidljiva):**
- ↗ Usporedi sve  ↖ Registracija
- ↘ Demo          ↙ WhatsApp kontakt

**Status:** PLAN — CC_TASK_JOKER_PRICING.md (treba napisati)

---

### 3-Klik Registracija (NOVO — zamjena za stari flow)
**Model:**
- Registracija → 15 dana sve bez ograničenja (testna faza)
- Nakon 15 dana: POS + Arhiva računa ostaju BESPLATNO 11 godina
- Plaćeni moduli: dostupni tek nakon odabira paketa

**Onboarding flow (odmah nakon registracije):**
1. Dobrodošlica ekran
2. Ugovor o korištenju (prihvati/odbij)
3. Kamera → uslika osobni dokument + rješenje o osnivanju obrta
4. AI agenti popunjavaju sve podatke o firmi/obrtniku automatski
5. IBAN upozorenje: zakonska provjera + upozorenje o rizicima i pravima (uskladiti sa zakonom!)

**Globalni UI — NA SVIM FORMAMA (zamjena Demo+Kontakt):**
- AI ikona — dolje lijevo, pomičan (drag & drop), zamjenjuje "Kontakt" gumb
- Kamera ikona — dolje desno, pomičan (drag & drop), zamjenjuje "Demo" gumb
- Isključiti sve stare popup poruke — zamijenjeni AI pratnjom ("Nisi sam — tu sam ja...")

**Status:** PLAN — CC_TASK_3KLIK_REGISTRACIJA.md + CC_TASK_GLOBAL_AI_CAMERA.md (treba napisati)

---

### VIS-AN-2026-003 — Ponuda Islamović, sekcije (2026-03-25)
**Status:** CC_TASK_INVOICE_SECTIONS.md SPREMAN — čeka CC Code
**Struktura:**
- Teil 1 — Arbeitsleistungen: 17 stavki, neto 17.782,88 €
- Teil 2 — Material und Ausstattung: 10 stavki, neto 6.111,86 €
- Ukupno neto: 23.894,74 € | Bruto: 28.434,72 €
**Nakon CC taska:** Ponuda ide Zlatanu Islamović (+491727203519) — Ivan čeka potvrdu

---

### Growth Plan 2026 — KONKRETAN
| Milestone | Datum | Akcija |
|-----------|-------|--------|
| Testna faza | do 1.4.2026 | 87 firmi na vrata, testiranje kompletnog flowa |
| 50% kapaciteta | cca travanj | Sign za preseljenje u novo gnijezdo |
| Uskrs 2026 | slobodan tjedan | Priprema terena za 1500 korisnika |
| Novo gnijezdo | uskrs/travanj | HW specifikacija za 1500 korisnika (Sonnet priprema) |
| Skaliranje | ovisno o tempu | Potencijalno još jedno preseljenje |

---

## TAX WIZARD — Plan kreiran (2026-03-24)
Status: PLAN READY — čeka se F1 pokretanje
Taskovi: CC_TASK_TAX_WIZARD_F1.md | GEMINI_TASK_TAX_WIZARD_F2.md | SONNET_TASK_TAX_WIZARD_F3.md

---

## POS KAO CENTAR SVIJETA — reBORGanizacija (2026-03-24)
Commit: 2430991 — QuickActions, 14 akcija, 3 post-receipt hooka, Open/Closed princip

**eRacun posrednik — Bloker:**
- FINA endpoint ispravljen, ali treba API key za live test
- CC_TASK_ERACUN_POSREDNIK_F1.md čeka ispravak endpointa

**UI Templates — DONE (2026-03-24)**
Commit: fb2b82e — Arhiva, Tax Wizard, Rental sve templatei

**CC Code sprint Task A+B (2026-03-24)**
Commiti: 46539a2, d836b89, 861bcfa, 2430991

**Čeka:**
- FINA/Moj-eRacun API key → live test eRačun
- Ivan: 3 beta iznajmljivača
- Marija: T&C consent (0/78 firmi)

---

## ★ NOVI SMJER — BORG SYSTEM FENIX (2026-03-24)
Master plan: /var/www/fina-connect/BORG_FENIX_MASTER_PLAN.md

---

## Aktivni klijenti
| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Frisko | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRacun, Invoicing, Konto | LIVE — fiskal 2 u toku |
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
| Ivan Brtan | superadmin / antonio.brtan | Platform owner |
| Marija Brtan | marija.brtan | Konjik d.o.o. |
| Niksa Viskovic | niksa.viskovic | Viskovic Bau |
| Dragan Jakovljevic | dragan.jakovljevic | Viskovic Bau |

---

## DONE — NE DIRATI

### Ured u džepu — Wizard P0 (KOMPLET — 23.03.2026) — Commit: 8a2fc66
### BORG FENIX Plan (KOMPLET — 24.03.2026)
### Synesis P1 Import (23.03.2026) — 86 firmi, 33.270 partnera, 10.206 faktura, D=P ±94 EUR
### Share Modal + Nav Partial + Cashier Wizard (KOMPLET — 23.03.) — Commit: 7d49022
### Cockpit 10/10 (KOMPLET — 22.03.) — Commit: 8d44bad
### POS Simulacija (KOMPLET — 24.03.) — Commit: c76f55a — 25/25 OK

### [SVE PRETHODNO — NEPROMIJENJENO]
### Udruge, FINA, DE KassenSichV, EU Fondovi, AML, Payments, i18n, POS Offline,
### FenixCamera, Transport F1, Infrastruktura, Dokumenti+PDF, Mobile, MCP Server,
### WhatsApp, Tim Chat, Country Registry, AI Tools v2, Livestock, Intelligence, VetIS,
### Institutional API, limit_connect_ai F1, GTM, Invoice Growth, Predarhiva OCR,
### Predkomora, Fiskalizacija fix, Hash Chain, PLG Virus, OIB Validator, POS QR,
### Robot Plan, Security P0, Knowledge Graph, buyer_type, T&C consent middleware

---

## TRAJNI RESURSI — REFERENTNI FAJLOVI

| Fajl | Opis |
|------|------|
| EU_FONDOVI_MASTER_MATRIX.md | Sve korisničke grupe + EU prilike + promo argumenti |
| BORG_FENIX_MASTER_PLAN.md | 90-dnevni master plan |
| LIMIT_CONNECT_AI_PLAN.md | AI Faze 1-4 |
| GTM_PLAN_LIMIT_CONNECT_V1.md | Prodajni plan |
| CLAUDE.md | Komunikacijski protokol za agente |

---

## TASKOVI ZA AGENTE

### ★ HITNO — Invoice Sections (2026-03-25)
| Fajl | Agent | Prioritet | Napomena |
|------|-------|-----------|---------|
| CC_TASK_INVOICING_BACKLOG.md | CC Code | **VISOK** | U1-U3+Z1-Z3: flow diagram, clone, expiry, client accept |
| CC_TASK_INVOICE_SECTIONS.md | CC Code | **HITNO** | VIS-AN-2026-003 za Zlatana — čeka slanje | → DONE: sekcije aplicirane direktno
| CC_TASK_API_KEY_AUTH.md | CC Code | **VISOK** | Passwordless API ključ — nova registracija + portal |
| CC_TASK_SUBSCRIPTION_TRACKING.md | CC Code | **VISOK** | ARR/MRR tracking, trial management, cockpit metrics |
| CC_TASK_BEEKEEPING_MODULE.md | CC Code | **VISOK** | Apiary+Hive+EPP Prilog3+berba meda — ~11k pčelara HR |
| CC_TASK_LIMIT_AI_FUNDS.md | CC Code | **VISOK** | EU fondovi workflow — pčelari+rental+udruge+MSP+DE |
| GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md | Gemini | **VISOK** | Ažurirano: +pčelari, +rental, 20 izvora, fund scanner |
| CC_TASK_CLEANUP_PRINT_LOGS.md | CC Code | NIZAK | print()→logger, tools_archive arhiviranje |

### ★ NOVO — Joker Pricing + 3-klik Onboarding
| Fajl | Agent | Prioritet |
|------|-------|-----------|
| CC_TASK_JOKER_PRICING.md | CC Code | **VISOK** |
| CC_TASK_3KLIK_REGISTRACIJA.md | CC Code | **VISOK** |
| CC_TASK_GLOBAL_AI_CAMERA.md | CC Code | **VISOK** |

### ★ BORG FENIX — Faza 1
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
| GEMINI_TASK_CROSS_MODULE_POS_INVOICING.md | Gemini | **VISOK** |

### Treba napisati (backlog)
- CC_TASK_JOKER_PRICING.md
- CC_TASK_3KLIK_REGISTRACIJA.md
- CC_TASK_GLOBAL_AI_CAMERA.md
- HW_SPEC_1500_USERS.md — za Uskrs
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi Faza 2
- CC_TASK_WIZARD_NKD_BULK.md
- CC_TASK_WIZARD_BILJEZNICK_LISTA.md

---

## OTVORENO

### Kritični problemi
| Problem | Hitnost |
|---------|---------|
| NKD NULL 86/86 firmi | VISOK |
| buyer_type b2c default (19.237 partnera) | VISOK |
| FINA/Moj-eRacun API key za eRačun live | VISOK |

### DE Compliance
- Fiskaly sandbox (treba API ključeve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO

### Wizard P2 backlog
- NKD bulk import (~1000 kodova), OIB validacija, Marija widget, T&C PDF

### Transport Faza 2, Livestock sex polje, Knjiga boljitaka (9/21)
