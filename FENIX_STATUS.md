# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-21 06:30 — CC Code (Opus) — Transport modul + status sync

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
- Migration: delivery/0009_transport_module — DONE

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
- send_text — DONE
- send_document (WAHA Plus only) — DONE
- send_document_link (fallback, sve verzije) — DONE
- send_image — DONE

### Tim Chat
- tim_chat_send endpoint (@login_required, ne superadmin) — DONE
- Okrugli stol: Ivan, Niksa, Dragan, Seki, Marija, CC, Sonnet — DONE

---

## OTVORENO — treba raditi

### DE Compliance
- Fiskaly sandbox test (treba API kljuceve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO

### Knjiga boljitaka (preostalo)
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
- Fleet dashboard (sva vozila, statusi, istekli dokumenti) — OTVORENO
- Automatski CMR iz TransportOrder — OTVORENO
- Multi-country routing UI — OTVORENO
- Kabotaža counter (max 3/7 dana) — OTVORENO
- Tahograf UI za vozača — OTVORENO
- Driver PWA kompletni — OTVORENO
- Route cost calculator — OTVORENO
- Customer tracking page (real-time + temp) — OTVORENO

### Nice-to-have
- ZUGFeRD PDF/A-3 pravi format (trenutno basic embed) — OTVORENO
- Vollstandige DE Ubersetzung (~2300 praznih) — OTVORENO
- Public donation page / widget — OTVORENO
- Fitness modul audit (GEMINI task) — CEKA GEMINI
