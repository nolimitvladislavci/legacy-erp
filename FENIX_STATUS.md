# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-24 sesija — POS Simulacija 25/25 ✅ (Sonnet)
Git HEAD: c76f55a

---


---

## TAX WIZARD — Plan kreiran (2026-03-24)
Fajlovi:
- TAX_WIZARD_MASTER_PLAN.md — master plan + milestone tracker
- CC_TASK_TAX_WIZARD_F1.md — infrastruktura (CC Code)
- GEMINI_TASK_TAX_WIZARD_F2.md — AI motor + deductions (Gemini)
- SONNET_TASK_TAX_WIZARD_F3.md — UX + partner portal + PDF (Sonnet)
- IVAN_TASK_TAX_WIZARD_F4.md — tržište + distribucija (Ivan)

Status: PLAN READY — čeka se F1 pokretanje
MVP target: 2027-02-01 (rok DOH 2026)


---

## POS KAO CENTAR SVIJETA — reBORGanizacija (2026-03-24)
Commit: 2430991

**Što je izgrađeno (229 LOC, 0 promjena u core views.py):**
- POSTerminal.quick_actions (JSONField) + 14 registriranih akcija (QUICK_ACTION_REGISTRY)
- Auto-defaults po pos_type: retail/reception/field/service/restaurant
- Udruga override (business_type override umjesto pos_type)
- QuickActions panel u quick.html (JS Action Registry, dinamički render)
- 3 post-receipt context hooka u pos/signals.py:
  - reception → check_evisitor_pending.delay()
  - udruga → auto_extend_membership_from_receipt.delay()
  - field → send_receipt_whatsapp.delay()
- Open/Closed princip: proširenje bez modifikacije jezgre

**eRacun posrednik:**
- get_cert_pem() bug fix (cert_p12 → cert_path)
- Konjik certifikat: /etc/limit-connect/certs/konjik-doo-fina-certifikat-37590751921.A.1.p12
- Vrijedi do: 2030-07-31
- Pipeline radi: certifikat → validacija → XML → potpis → SOAP
- Bloker: pogrešan FINA endpoint (fiskalizacija vs eRačun)
- CC_TASK_ERACUN_POSREDNIK_F1.md — čeka ispravak endpointa


### UI Templates — DONE (2026-03-24 13:05)
Commit: fb2b82e

**Arhiva:**
- documents/templates/documents/arhiva_list.html — kompletna tablica, filteri, stats, bookmark, paginacija
- documents/templates/documents/scan_batch.html — 5 faza (upload/preview/AI/rezultati/done), drag&drop, kompresija WebP, live polling

**Tax Wizard:**
- tax_wizard/templates/tax_wizard/dashboard.html — obrasci, sesije, rokovi, tierovi
- tax_wizard/templates/tax_wizard/wizard.html — JSON-driven koraci, live kalkulator, AI poruke
- tax_wizard/templates/tax_wizard/no_company.html

**Rental:**
- Sve migracije OK (Guest, GuestDocument, RentalInvoice, TrafficRecord)
- ocr.py, evisitor.py, invoice_service.py — sve importa

Status: Marija može pristupiti arhivi, scan batchu i poreznom savjetniku.


### CC Code sprint — Task A + B + Sandbox + NN fix (2026-03-24 ~14:00)
Commiti: 46539a2, d836b89, 861bcfa, 2430991

**Task A — eRačun Endpoint:**
- FINA_URLS['test'] = 'https://eracun-test.fina.hr/eRacunServis' (bio FiskalizacijaService)
- SOAPAction header dodan u send_to_fina()
- Posrednik fallback ugrađen

**Task B — QuickActions UI Handlers (templates/pos/quick.html):**
- rental_checkin → modal s AJAX listom današnjih dolazaka
- rental_checkout → modal s listom odlazaka + plaćeno/neplaćeno  
- rental_evisitor → modal s pending bookings + 1-klik XML download
- rental_ocr → modal s kamerom + AI OCR + confidence prikaz
- membership_scan → modal s lookup po iskaznici/OIB + obnova
- 5 novih API endpointa POS→Rental/Udruge bridge

**Smart Mailbox UI (d836b89):** swipe-to-approve, push notifikacije, mobile CSS
**EU Rental Tax (861bcfa):** RentalTaxEngine, razred_mjesta, Guest.evisitor_status
**NN Scraper (nn_feed_service.py):** Web scraping umjesto RSS (NN nema javni RSS)

**Čeka:**
- FINA/Moj-eRacun API key → live test eRačun
- Ivan: 3 beta iznajmljivača
- Marija: T&C consent (0/78 firmi)

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

### Ured u džepu — Wizard P0 (KOMPLET — 23.03.2026)
Commit: 8a2fc66

**Što je izgrađeno:**
- `WizardDraft` model (partners/models.py) + migration 0007
  - Polja: session_key, ip_address, tc_accepted+timestamp, nkd_codes_json,
    firma_ime, broj_osnivaca, direktor (ime/oib/email), kapital_tip,
    koristi_konjik, sjediste polja, current_step, completed, pending_company FK,
    accounting_firm FK, created_at/updated_at
- 6 URL endpointa: wizard/, save-step/, step-preview/, reset/, suglasnost-pdf/, nkd-semantic/
- AJAX perzistencija — svaki "Dalje" sprema u bazu (wizard nije stateless)
- T&C korak 0 — GDPR gatekeeper s IP+timestamp bilježenjem
- Company factory — na koraku 2 kreira Company(status=pending, OIB=DRAFTxxxxxx)
- CompanyPartnership — automatski veže pending Company na accounting_firm (Marija)
- NKD sync — na koraku 5 upisuje primarni NKD na pending Company
- OnboardingProgress — automatski kreiran na završetku (korak 7)
- CustomEvent arhitektura JS — `wizard:step` event, nema override bugova
- StateValidator — collectState() prisilno povlači DOM podatke prije save-a
- NKD semantic search — keyword + Haiku AI fallback (74 kodova u bazi)
- PDF suglasnosti — WeasyPrint, 13KB, pravno ispravan (ZTD čl.36)
- Resume detection — wizard nastavlja od zadnjeg koraka

**Testirano:**
- Komplet flow test: draft → T&C → NKD → firma → Company factory → direktor →
  kapital → sjedište → NKD sync → OnboardingProgress → završetak ✓
- Haiku semantic: "prodaja kave i kolača online" → 5 točnih NKD-ova s AI obrazloženjem ✓
- PDF: 13KB, generiran za <1s ✓

**URL:** /hr/partners/wizard/

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

### POS Simulacija — DONE (2026-03-24)
Commit: c76f55a
- 6 scenarija: quick, retail, udruga, field, brzi-iznos, reception
- 25/25 OK | 0 ERROR | 12 training računa | 1.418 EUR ukupno
- S3 membership, S4 WhatsApp, S6 eVisitor hookovi potvrđeni


### [SVE PRETHODNO — NEPROMIJENJENO]
### Udruge modul, FINA izvjestaji, DE KassenSichV, EU Fondovi, AML, Payments, i18n,
### POS Offline, FenixCamera, Transport Faza 1, Synesis Import, Infrastruktura,
### Sales + Onboarding, Dokumenti + PDF, Mobile, MCP Server, WhatsApp, Tim Chat,
### Country Registry, AI Tools v2, Livestock, Intelligence, VetIS, Institutional API,
### limit_connect_ai Faza 1, GTM Foundation, Invoice Growth Engine, Predarhiva OCR,
### Predkomora, Fiskalizacija fix, Hash Chain, PLG Virus, OIB Validator, POS QR, Robot Plan,
### Security P0 (certifikati → /etc/limit-connect/certs/), Knowledge Graph (11 opp, 932 match),
### buyer_type + invoice routing (NN 89/25), T&C consent middleware

---

## TASKOVI ZA AGENTE

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
| GEMINI_TASK_CROSS_MODULE_POS_INVOICING.md | Gemini | **VISOK** |

### Treba napisati (backlog)
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi Faza 2
- CC_TASK_WIZARD_NKD_BULK.md — DZS puna NKD lista (~1000 kodova) umjesto 74
- CC_TASK_WIZARD_BILJEZNICK_LISTA.md — statična JSON lista e-Notar bilježnika

---

## OTVORENO — Wizard P1 (sljedeće sesije)

### Wizard P1 — DONE (23.03.2026)
- Celery cleanup task (03:00 dnevno) — DONE
- Haiku retroNKD: 47/86 firmi ažurirano (55%) — DONE
- Funnel widget u dashboard — DONE
- Beat schedule registriran — DONE

### Wizard — što ostaje za P2
| Task | Opis | Prioritet |
|------|------|-----------|
| NKD bulk import | DZS puna lista ~1000 kodova (74 je dovoljno za demo) | SREDNJI |
| OIB validacija na draft | Luhnov algoritam na direktor_oib pri save | SREDNJI |
| Marija dashboard widget | "Aktivni wizard drafti" pregled za Mariju | SREDNJI |
| DE/EN lokalizacija | Template na DE/EN za EU klijente | NIZAK (Q3) |
| Bilježnik lista | Statični JSON 3-5 bilježnika za e-Notar | NIZAK |
| T&C dokument PDF | Pravi pravni dokument za TC consent (ne inline tekst) | SREDNJI |

### Kritični otvoreni problemi (van wizard-a)
| Problem | Opis | Hitnost |
|---------|------|---------|
| T&C consent | View + banner implementiran (commit 8def4fe) | **DONE** |
| NKD NULL 86/86 | Sve firme bez NKD — KG confidence niži | VISOK |
| _build_xml() | IMPLEMENTIRANO (generate_ubl_xml + build_fina_xml) | **DONE** |
| buyer_type b2c default | 19.237 partnera treba reklasifikaciju | VISOK |
| SupplierRiskAlert | _save_alert popravljen + invoice signal (commit cd5b9f6) | **DONE** |

### DE Compliance
- Fiskaly sandbox (treba API ključeve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO
- Steuernummer validacija — NEDOSTAJE

### Livestock
- sex polje direktno na modelu — OTVORENO
- Testovi (47) — provjeri rezultate

### Knjiga boljitaka (9/21 preostalo)
- B-01, B-05, B-06, B-09, B-10, B-11, B-13, B-17, B-21

### Transport Faza 2
- CMR auto, multi-country routing, kabotaža, Driver PWA
