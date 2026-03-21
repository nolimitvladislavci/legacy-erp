# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-21 20:45 — Sonnet (kraj sesije) — Predkomora DONE, Hash Chain DONE, PLG Virus DONE, testovi pripremljeni, OIB/Steuernummer analiza
Git HEAD: 81ee45a — PLG Virus: viralni footer + Hash Shield na svih 5 izlaznih dokumenata

---

## Git HEAD
81ee45a — PLG Virus: viralni footer + Hash Shield na svih 5 izlaznih dokumenata

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

### Institutional API (KOMPLET — 21.03.)
- InstitutionalAccessToken model — DONE
- 4 read-only endpointa: HAPIH, JRDZ, Sanitarna, VetIS — DONE
- Token management + vet/accountant/inspector roles — DONE
- Audit log za svaki API poziv — DONE

### limit_connect_ai Faza 1 (KOMPLET — 21.03.)
- AIAgentMission model (UUID PK, mission_type, frequency, notify_channel) — DONE
- AIReportLog model (content, sent_via, status, ai_tokens_used) — DONE
- FundApplicationDraft model (eligibility_score, draft_content, FK FundOpportunity) — DONE
- ComplianceWatchItem model (law_reference, deadline, status, ai_notes) — DONE
- CampaignPlan model (campaign_type, message_template, ai_suggestion, estimated_reach) — DONE
- Celery tasks: morning_report_all (07:30), fund_check_all (09:00), compliance_check_all (pon 08:00), campaign_suggestions_all (pet 10:00) — DONE
- Views: cockpit, missions, reports, funds — DONE
- Templates: 4 HTML (ai_cockpit, ai_missions, ai_reports, ai_funds) — DONE
- Admin: 5 modela registrirano — DONE
- CELERY_BEAT_SCHEDULE: 4 nova taska — DONE
- Migracije: 0001_initial + 0002_campaignplan_compliancewatchitem — DONE
- URL: /ai-cockpit/ — DONE

### GTM Foundation (KOMPLET — 21.03.)
- OIB Auto-Lookup API (/register/api/oib-lookup/) — interni DB + sudski registar — DONE
- AJAX autofill u step2.html (name, address, city, zip) — DONE
- Pricing Kalkulator (slider + toggleovi + usteda) na /pricing/ — DONE
- Empty State partial (partials/empty_state.html) — DONE
- Empty states: invoicing, partners, inventory — DONE

### Invoice-Powered Growth Engine (KOMPLET — 21.03.)
- Referral footer na 3 PDF baze (modern, datev, viskovic) — DONE
- Referral footer na invoice_hr.html — DONE
- CTA link na base_email.html — DONE
- 8 AI misija aktivirano — DONE
- WhatsApp status report poslan Ivanu — DONE

### Predarhiva Bulk OCR (KOMPLET — 21.03.)
- StagingBatch + StagingFile modeli + migracija 0006 — DONE
- Canvas kompresija 5MB→150KB (commit 94658bd) — DONE
- Bulk upload view s drag & drop + file preview — DONE
- Rate-limited Celery task (8 req/min, backoff) — DONE
- Live progress API (polling 3s) — DONE
- 2 templatea (staging.html, staging_detail.html) — DONE

### Predkomora — Smart Import Review (KOMPLET — 21.03.)
- StagingFileHeader model (OIB, total, PDV, datum, broj, confidence) — commit 97c6f34 — DONE
- extract_invoice_header() Gemini poziv (services.py) — DONE
- extract_unified() — 1 poziv za header + stavke (cost-efficient) — DONE
- auto_match_partner() — OIB → Partner auto-spajanje — DONE
- Duplikat detekcija (isti OIB + invoice_number + total_amount → needs_review) — DONE
- process_staging_batch header integracija (Celery task) — DONE
- Side-by-Side Review Dashboard (commit 5182bb9) — DONE
- Predkomora ARMIRANA — 4 zamke neutralizirane (commit 535a00f):
  - Zamka 1 (PDF): MIME detection, iframe viewer za PDF
  - Zamka 2 (Matematika): frontend + backend validacija (base+vat=total ±0.02), MATH_MISMATCH
  - Zamka 3 (Konkurencija): select_for_update + CONFLICT 409 guard
  - Zamka 4 (Hotkeys): keyboard shortcuts (A=approve, D=discard, N=next)
- review_approve() + review_discard() views — DONE
- Migracija 0007 (StagingFileHeader) — DONE

### Fiskalizacija bug fix (KOMPLET — 21.03.)
- Hard 5s timeout na _fiscalize() (ThreadPoolExecutor) — DONE
- Instant response bez JIR-a, not_fiscalized flag — DONE
- Warning toast + Celery retry 2min — DONE
- Zakonski OK — 48h rok za naknadnu fiskalizaciju — DONE

### Hash Chain — Kriptografski Audit Trail (KOMPLET — 21.03. — commit 73a0701)
- ChainLink model (migration 0036) — sequence, payload_hash, prev_hash, chain_hash — DONE
- append_receipt() — dodaje bon u lanac nakon naplate — DONE
- verify_chain() — O(n) integritet provjera cijelog lanca — DONE
- verify_single() — brza provjera jednog bona — DONE
- daily_anchor_hash() — dnevni Merkle anchor (spreman za OpenTimestamps) — DONE
- Princip: Bitcoin mining bez minanja. Ako se stari bon promijeni, svi kasniji hashevi pucaju — DONE

### PLG Virus — Viralni Footer (KOMPLET — 21.03. — commit 81ee45a)
- templates/pos/includes/_viral_footer.html — reusable include, 3 formata — DONE
- Thermal bon (80mm): SHA-256 hash + limit-connect.com — DONE
- A4 PDF račun: Hash Shield s integritet statusom + EU ViDA 2028 badge — DONE
- Public web receipt: zeleni vizualni štit + PLG CTA za besplatnu registraciju — DONE
- e-Račun public: profesionalni footer + EN 16931 badge — DONE
- POSReceipt.chain_link_safe property (no DoesNotExist crash) — DONE
- PLG CTA: "Besplatna POS blagajna + e-Arhiva → limit-connect.com" — DONE

### OIB / VAT Validator (KOMPLET)
- core/oib_validator.py — validate_oib_hr() ISO 7064 MOD 11,10 — DONE
- validate_vat_id() za HR/DE/AT/SI/IT/EU generički — DONE
- normalize_oib(), format_oib_display(), strip_vat_prefix() — DONE
- core/business_lookup.py — centralni lookup servis — DONE
- BusinessLookupResult dataclass (found, source, name, tax_id, address, nkd, wz...) — DONE
- lookup_business() — HR: VIES → FINA Info.BIZ → fallback — DONE
- _lookup_de() — VIES USt-IdNr + Kleinunternehmer poruka — DONE
- _lookup_vies() — SOAP poziv EU VIES za sve EU države — DONE
- _lookup_in_database() — interni Partner lookup prvi — DONE

### POS QR Instant Open (KOMPLET — 21.03.)
- POSTerminal.access_token (secrets.token_urlsafe(20)) — DONE
- /pos/qr/{token}/ — zero-login terminal aktivacija — DONE
- generate_pos_qr management command — 5 PDF-ova za Šekijeve terminale — DONE
- AIActionLog bilježi QR pristup s IP — DONE

### Šeki Robot Prodavač — Plan
- ROBOT_PRODAVAC_PLAN.md + CC_TASK_ROBOT_PRODAVAC_KOMPLET.md kreiran — DONE
- ROI analiza: 67.200 EUR/god vs 7.500 EUR hardware = povrat 6 tjedana — DONE

---

## TASKOVI ZA AGENTE

### Pripremljeni taskovi (čekaju izvršenje)
- CC_TASK_TESTS_PREDKOMORA.md — 15 testova za StagingFileHeader, Predkomora zamke, duplikat — SPREMAN
- GEMINI_TASK_TESTS_HASHCHAIN.md — 13 testova za Hash Chain + PLG chain_link_safe — SPREMAN
- GEMINI_TASK_LIMIT_AI_COMPLIANCE.md — ComplianceWatchdog Faza 2 — SPREMAN
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi workflow Faza 2 — SPREMAN
- CC_TASK_ROBOT_PRODAVAC_KOMPLET.md — 5 zadataka (kiosk, Stripe, QR plakati) — SPREMAN

---

## OTVORENO — treba raditi

### DE Compliance
- Fiskaly sandbox test (treba API kljuceve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO
- **Steuernummer validacija (10/11 znamenki, Finanzamt format) — NEDOSTAJE** — vidi analizu dolje

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

### LIMIT Connect AI — Faze 2-4
- GEMINI_TASK_LIMIT_AI_COMPLIANCE.md — ComplianceWatchdog — SPREMAN ZA GEMINI
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi workflow — SPREMAN ZA CC
- GEMINI_TASK_LIMIT_AI_CAMPAIGNS.md — CampaignPlanner Faza 3 — CEKA FAZU 2
- CC_TASK_LIMIT_AI_COCKPIT.md — per-klijent cockpit Faza 3 — CEKA FAZU 2
