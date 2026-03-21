# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-21 11:00 — Sonnet (Ivan sesija) — LIMIT Connect AI Master Plan kreiran i odobren
2026-03-21 10:30 — CC Code (Opus) — Session end: Transport 35/36, Korpa 1833 faktura, memorija komplet
SLJEDEĆI TASK: CC_TASK_LIMIT_AI_FOUNDATION.md (limit_connect_ai app — 5 modela, 4 taska, 4 viewa)

## Git HEAD
094162f — Institutional API: HAPIH/JRDZ/Sanitarna/VetIS endpoints + token management + vet/accountant/inspector roles + audit log
369 migracija aplicirano, 0 čeka.

## Aktivni klijenti
| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Frisko | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRacun, Invoicing, Konto | LIVE |
| Niksa Viskovic | Viskovic Bau | DE market, GoBD, TSE, DSFinV-K | ONBOARDING |
| Dragan Jakovljevic | Viskovic Bau | Partner (Strategie), superadmin | ONBOARDING |

## Superadmini
| User | Login | Firma |
|------|-------|-------|
| Ivan Brtan | superadmin / antonio.brtan | Platform owner |
| Marija Brtan | marija.brtan | Konjik d.o.o. |
| Niksa Viskovic | niksa.viskovic | Viskovic Bau |
| Dragan Jakovljevic | dragan.jakovljevic | Viskovic Bau |

---

## DONE — NE DIRATI

### Udruge modul (KOMPLET)
- is_nonprofit, nonprofit_fiscal_mode, requires_simplified_accounting — DONE
- InventoryItem.is_nonprofit_activity + POSReceiptItem.is_nonprofit_activity — DONE
- CheckoutService._should_fiscalize() guard — DONE
- MIXED_RECEIPT blokada (commercial + nonprofit na istom bonu) — DONE
- Clanarina + Donacija + KnjigaPrimitaka modeli — DONE
- MembershipPlan + MemberSubscription state machine — DONE
- paying_sponsor (kisobran naplata) — DONE
- _resolve_member_discount u CheckoutService — DONE
- evaluate_subscriptions Celery (dunning + auto-renew) — DONE
- Neprofitni kontni plan (144 konta, 4-digit analitika) — DONE
- Auto-setup signal (apps.py post_save Company) — DONE
- 10 HTML templatea za udruge — DONE
- Dogadjaji + Kampanje (EU fond tracking) + Email kampanje (AI + Celery) — DONE
- 10 views, 8 templates, 5 modela (Dogadjaj, Kampanja...) — DONE
- Email campaign rate limiting (50/batch, 2s delay, bounce skip) — DONE

### FINA izvjestaji (KOMPLET)
- PR-RAS-NPF XLSX (145 AOP pozicija iz pravog FINA XLS-a) — DONE
- BIL-NPF XLSX (aktiva/pasiva) — DONE
- G-PR-IZ-NPF XLSX (jednostavno racunovodstvo) — DONE
- Donatorska potvrda HTML — DONE

### DE KassenSichV (KOMPLET)
- Fiskaly Cloud TSE adapter (pos/tse_adapter.py) — DONE
- Tri-routing u CheckoutService (nonprofit→DE TSE→HR FINA) — DONE
- TSE Ausfall handling ("TSE AUSGEFALLEN" klauzel) — DONE
- DSFinV-K Export (7 CSV ZIP) — DONE
- test_fiskaly_tse management command — DONE
- XRechnung CII XML generator — DONE
- ZUGFeRD 2.2 hybrid PDF — DONE
- Verfahrensdokumentation stranica + online potpis — DONE
- Kassenbuch/Blagajnicki dnevnik — DONE
- DE 250 EUR Kleinbetragsrechnung hard-stop — DONE

### EU Fondovi + Volonteri (KOMPLET)
- is_volunteer, volunteer_hourly_value, volunteer_annual_limit — DONE
- Payroll giljotina (skip volunteer) — DONE
- TimeEntry auto-monetizacija — DONE
- VolunteerTaxGuard (limit check) — DONE
- EUAuditGuard (double-dipping, monthly fund) — DONE
- EU Timesheet + In-Kind Report + Godisnje izvjesce — DONE

### AML + Napojnice + Voucheri
- AML Guard (10k EUR prag, KYC status) — DONE
- Materijalne donacije (donation_in StockMovement) — DONE
- TipTracker (HR 3.360 EUR godisnji limit) — DONE
- FINA <Napojnica> XML cvor — DONE
- Voucher Mehrzweck/Einzweck PDV logika — DONE
- R1 racun (buyer_oib, FINA OibKupca) — DONE
- Auto e-Racun za B2B/R1 transakcije — DONE

### Payments (KOMPLET)
- 5 gatewaya: cash, stripe, btcpay, paypal, revolut — DONE
- Posrednik Service (Moj-eRacun.hr API) — DONE
- Auto-send e-Racun kroz posrednika — DONE
- fetch_posrednik_inbox Celery task — DONE

### i18n (FAZA 1 KOMPLET)
- Company.ui_language + middleware fallback — DONE
- 134 DE prijevoda — DONE
- LANG_PREFIXES fix (de dodano) — DONE
- AdminLangRedirectMiddleware — DONE

### POS Offline (KOMPLET)
- IndexedDB engine (pos-offline.js v2) — DONE
- Session caching (country, fiscal_system) — DONE
- Offline receipt print + country-aware footer — DONE
- Cash ops offline + Shift summary offline — DONE
- Bulk sync on reconnect — DONE
- beforeunload warning (B-02) — DONE

### FenixCamera (KOMPLET — 19 templatea)
- fenix-camera.js (8KB) u base.html — DONE
- AI Widget, arhiva_upload, arhiva_convert, prigovori — DONE
- ivan_cockpit, smart_import, helpdesk (x2) — DONE
- delivery, worker_camera, assessment (x2) — DONE
- marketplace, steuerberater_portal — DONE
- 4 udruge templatea (clan_form, donacija_form, knjiga, clan_detail) — DONE
- /ai/api/analyze-image/ endpoint (Claude Haiku Vision) — DONE

### Transport modul Faza 1 (KOMPLET — 21.03.)
- TransportOrder (35+ polja, verify_documents(), auto order_number) — DONE
- VehicleDocument (ATP, registration, insurance, community_licence, expiry alerts) — DONE
- DriverDocument (licence, CPC, ADR, posting_declaration, non-EU attestation) — DONE
- TachographEntry (driving/rest/break evidencija, violation detection) — DONE
- FuelEntry (liters, price, odometer, photo) — DONE
- posting_document FK na TransportOrder (Gemini sugestija) — DONE
- Migration: delivery/0009_transport_module + 0010_posting_document_fk — DONE
- Testovi: 35/36 PASS (T13 SQLite-specific bug, radi na PostgreSQL) — DONE
- verify_documents() fix: non-EU attestation za SVE međunarodne — DONE
- Views + URLs + 3 templates (order_list, order_detail, fleet_dashboard) — DONE

### Korpa Synesis Import (KOMPLET — 21.03.)
- import_korpa management command — DONE
- Korpaš: +885 faktura (1242 ukupno) — DONE
- Kruljac: +945 faktura (1032 ukupno) — DONE
- KUD/Furdi/Dubinsko: Journal nema fakture (samo config) — DONE
- Ukupno arhiva: 9.304 dokumenata — DONE
- Korpaš umbrella komuna (5 children) — DONE

### Knjiga boljitaka (12/21)
- B-02 beforeunload + smart_logout open receipts guard — DONE
- B-03 audit IP/UA, B-04 fiscal retry (48h + backoff + notify) — DONE
- B-07 QR cart, B-08 stock race condition (select_for_update) — DONE
- B-14 order_source, B-16 company switch audit — DONE

### Infrastruktura (KOMPLET)
- Git init (720K linija, 3395 fajlova) — DONE
- Daily backup (lc_backup.sh, 03:00) — DONE
- Self-heal (lc_self_heal.sh, */10 min) — DONE
- Health monitor + error monitor (*/5 min) — DONE
- DR skripta (lc_rebuild.sh) — DONE
- Synesis email baza (1272 unique, 2828 updatirano) — DONE

### Sales + Onboarding (KOMPLET)
- Sales Wizard HR + DE (5 koraka) — DONE
- SalesLead model (ref_code, commission_percent) — DONE
- Agent Dashboard (/hr/register/agent/) — DONE
- QR referral (?ref=REF-XXXXX) — DONE
- Audit trail (IP + SHA-256 + immutable PDF) — DONE
- Auto email/WhatsApp nakon potpisa — DONE
- AI validacija + duplikat provjera — DONE

### Dokumenti + PDF (KOMPLET)
- 3 PDF dizajna (modern, datev, viskovic) — DONE
- doc_integrity_badge (SHA-256) na 14+ templatea — DONE
- ISMS dokumentacija (Policy, Risk Assessment, BCP) — DONE
- Steuerberater portal (/hr/steuerberater/) — DONE
- Promo stranice HR + DE — DONE
- Arhiva upute + onboarding modal + A4 vodic — DONE

### Mobile (KOMPLET)
- Bottom nav bar (5 ikona, <768px) — DONE
- Table-to-card CSS (.mobile-cards) — DONE
- Touch targets 44px — DONE
- Input 16px (no iOS zoom) — DONE
- Single column grids — DONE
- PWA permissions (fenix-permissions.js) — DONE
- Worktime offline (worktime-offline.js) — DONE
- SW v6 (worktime/fitness/udruge/hr routes) — DONE

### MCP Server (KOMPLET)
- Fenix MCP Server (11 alata) — DONE
- Systemd service (fenix-mcp) — DONE
- Nginx proxy (/mcp/) + CORS za claude.ai — DONE
- Sonnet spojen — DONE

### WhatsApp (KOMPLET)
- send_text, send_document, send_document_link, send_image — DONE

### Tim Chat
- tim_chat_send endpoint + Okrugli stol (Ivan, Niksa, Dragan, Seki, Marija, CC, Sonnet) — DONE

### Country Registry (KOMPLET)
- Strategy Pattern za multi-country ERP — DONE
- HR + DE production, AT/SI/RS/BA/IT planned — DONE

### AI Tools v2 (KOMPLET — 26 alata ukupno)
- get_fund_opportunities, get_livestock_status, create_futures_listing — DONE
- get_compliance_warnings, get_intelligence_results — DONE
- Kontekstualni bridge user->company->tools (_build_contextual_system_prompt) — DONE

### Livestock modul (KOMPLET — V1+V2+V3)
- Livestock, HealthRecord, MilkRecord, Field, CropPlan modeli — DONE
- auto_listing_ready property — DONE
- Views: list, detail, create, field_list, crop_list — DONE
- Templates: 5 HTML — DONE
- Test podaci za OPG Kruljac (5 grla, 2 parcele, 2 CropPlana) — DONE
- Karencija POS guard (blokira prodaju mlijeka/mesa od grla pod antibiotikom) — DONE
- livestock_animal FK na InventoryItem — DONE
- Livestock offline PWA — DONE
- JRDŽ osnova — DONE
- FenixCamera barcode scan za grla — DONE

### Intelligence modul (KOMPLET)
- IntelligenceSource, IntelligenceJob, IntelligenceResult — DONE
- FundOpportunity, FundApplication — DONE
- intelligence_nightly_patrol Celery task (03:30) — DONE
- check_auto_listings Celery task (07:00) — DONE
- setup_intelligence_sources management command (6 izvora) — DONE
- IntelligenceJob kreiran za OPG Kruljac — DONE
- Views: dashboard, results_list, funds_list, fund_detail + 4 templates — DONE
- Burza: agro kategorije (kukuruz, stoka, mlijeko_sir, povrce, mehanizacija, eu_fond) — DONE

### VetIS + Vet Portal (KOMPLET — 21.03.)
- Vet Portal: public vet entry (WhatsApp link) — DONE
- Vet Dashboard — DONE
- Milking robot /api/identify/ (MILK/DIVERT decision) — DONE
- Karencija auto-notify farmer — DONE
- 3 razine: WhatsApp link (R1), Vet portal (R2), Robot API (R3) — DONE
- EU Reg 2019/6 compliance — DONE

### Institutional API (KOMPLET — 21.03. — HEAD)
- InstitutionalAccessToken model — DONE
- 4 read-only endpointa: HAPIH, JRDZ, Sanitarna, VetIS — DONE
- Token management + vet/accountant/inspector roles — DONE
- Audit log za svaki API poziv — DONE

---

## OTVORENO — treba raditi

### DE Compliance
- Fiskaly sandbox test (treba API kljuceve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO

### Knjiga boljitaka (preostalo — 9/21)
- B-01 Offline cross-device sync — DJELOMICNO
- B-05 WaiterShift heartbeat — OTVORENO
- B-06 Konobar race condition — DJELOMICNO
- B-09 QR error toast — DJELOMICNO
- B-10 Claim race condition — DJELOMICNO
- B-11 QR bez emaila loyalty — OTVORENO
- B-13 Kitchen API rate limit — OTVORENO
- B-17 OCR confidence — OTVORENO
- B-21 Print QR label — DJELOMICNO

### Transport Faza 2
- CMR automatski iz TransportOrder — OTVORENO
- Multi-country routing UI — OTVORENO
- Kabotaža counter (max 3/7 dana) — OTVORENO
- Tahograf UI za vozača — OTVORENO
- Driver PWA kompletni — OTVORENO
- Route cost calculator — OTVORENO
- Customer tracking page (real-time + temp) — OTVORENO

### Nice-to-have
- ZUGFeRD PDF/A-3 pravi format — OTVORENO
- Vollstandige DE Ubersetzung (~2300 praznih) — OTVORENO
- Public donation page / widget — OTVORENO
- Fitness modul audit (GEMINI task) — CEKA GEMINI

### LIMIT Connect AI — Master Plan (ODOBREN — 2026-03-21)
- LIMIT_CONNECT_AI_PLAN.md kreiran — kompletni roadmap
- CC_TASK_LIMIT_AI_FOUNDATION.md — spreman za CC Code (Faza 1)
- GEMINI_TASK_LIMIT_AI_COMPLIANCE.md — spreman za Gemini (Faza 2)
- Vizija: per-klijent AI asistent, EU fondovi, compliance watchdog, kampanje, WhatsApp/email report

## SLJEDEĆI TASKOVI (po prioritetu)
1. CC_TASK_LIMIT_AI_FOUNDATION.md — CC Code — limit_connect_ai app (Faza 1) — AKTIVAN
2. GEMINI_TASK_LIMIT_AI_COMPLIANCE.md — Gemini — ComplianceWatchdog (Faza 2) — CEKA FAZU 1
3. CC_TASK_LIMIT_AI_FUNDS.md — CC Code — EU fondovi workflow (Faza 2) — CEKA FAZU 1
4. GEMINI_TASK_LIMIT_AI_CAMPAIGNS.md — Gemini — CampaignPlanner (Faza 3) — CEKA FAZU 2
5. CC_TASK_LIMIT_AI_COCKPIT.md — CC Code — per-klijent cockpit (Faza 3) — CEKA FAZU 2
