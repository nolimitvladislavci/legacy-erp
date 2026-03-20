# FENIX STATUS — Koordinacijski fajl
# Svi agenti čitaju OVO prije svakog taska.
# Sonnet ažurira nakon svake sesije.
# CC Code i Gemini čitaju na početku svakog taska.
#
# PRAVILO: Ako nešto piše DONE ovdje — NE RADIŠ PONOVO.
# PRAVILO: Prije nego staviš task u plan — provjeri git log i ovaj fajl.

---

## Zadnje ažuriranje
2026-03-21 01:00 — Sonnet (koordinator)

## Aktivni klijenti
| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Šeki Temaj | Uvijek Friškom | POS (3 lokacije, 5 terminala) | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRačun, Invoicing | LIVE |
| Nikša Visković | Viskovic Bau | DE market, GoBD | ONBOARDING |

## Infrastruktura
- Server: 37.27.248.86 (limit-connect.com)
- MCP: https://limit-connect.com/mcp/sse — LIVE, 10 alata
- Gunicorn + Celery + Nginx — sve active
- SW: fina-v6

---

## ✅ DONE — NE RADITI PONOVO

### POS modul
- R1 račun: kupac OIB/naziv/adresa na termalnom i A4 ✅
- PDV tablica po stopama (kompaktna termalni, puna A4) ✅
- 50/50 testova PASS (R1, nonprofit, multi-terminal, fiscal, offline, Z-report, storno) ✅
- ZKI/JIR, FINA QR, M.P. klauzula HR+DE ✅
- POS Offline Engine v2 (IndexedDB, session cache, bulk sync) ✅
- DSFinV-K export (ZIP, CSV) ✅
- TSE KassenSichV, offline Klausel DE ✅
- TipTracker HR (3360 EUR limit), Voucher PDV ✅
- FINA Napojnica XML (HR NN 156/2023) ✅
- Kassenbuch/Blagajnički dnevnik HR+DE ✅
- ZUGFeRD 2.2 + XRechnung DE B2B ✅
- Nonprofit guard + member discount + audit trail ✅
- Knjiga prigovora (KnjigaPrigovora model) ✅

### eRačun / Invoicing
- eRačun auto iz POS R1, source_receipt FK ✅
- Posrednik Service (Moj-eRačun/FINA/Custom) ✅
- DE 250 EUR Kleinbetragsrechnung hard-stop ✅
- Legal compliance HR+DE ✅

### Dokumenti / Arhiva
- ArhivaEntry SHA-256 integrity_hash ✅
- Global doc_integrity: SHA-256 badge na 11 PDF templatea ✅
- core/doc_integrity.py + templatetag ✅
- Arhiva UX: filter 0-iznos, sort, delete, onboarding modal ✅

### PDF predlošci
- base_modern.html (HR klijenti, plavo-bijeli) ✅
- base_datev.html (DE Steuerberater, DATEV-like) ✅
- base_viskovic.html (gold/dark premium, HR+DE auto-switch) ✅
- Sva 3 imaju: doc_integrity_badge, čl.9 ZOR (HR), §147 AO (DE) ✅
- KOPIRANJE DATEV STILA: legalno — stil/layout nije zaštićen autorskim pravom ✅

### Sales / Registracija
- Sales Wizard HR+DE ✅
- SalesLead model (ref_code, commission) ✅
- QR referral tracking, Agent Dashboard ✅
- Auto email + WhatsApp nakon potpisa ✅
- AI validacija po koraku, duplicate check OIB+ime ✅
- Audit trail: IP + SHA-256 + timestamp ✅
- Verfahrensdokumentation (GoBD/KassenSichV) + online potpis ✅
- ISMS dokumentacija (ISO 27001 Annex A) ✅

### FenixCamera
- fenix-camera.js globalni modul (pick, preview, upload, AI analyze, quick) ✅
- 19 templatea integrirala FenixCamera ✅
- FAB (plutajuća ikona) SAMO na pos/prigovori.html ✅
- analyze_image AI endpoint ✅
- Kontekstualni gumbi: udruge (3), assessment (1+), marketplace, delivery, pos ✅

### PWA / Offline
- SW fina-v6: worktime/fitness/udruge rute u PAGE_CACHE ✅
- fenix-permissions.js: storage.persist(), Notification dozvola ✅
- worktime-offline.js: IndexedDB clock-in/out, auto-sync ✅
- offline.html: module grid (koje stranice rade offline) ✅

### WhatsApp
- send_document (WAHA Plus, base64) ✅
- send_document_link (fallback za WAHA Basic) ✅
- send_image ✅
- Udruge: 4 PDF poslana na 385991908089 ✅

### Ivan Cockpit
- /hr/superadmin/ivan/ live ✅
- 6 control buttons (restart, daily report, arhiva, backup) ✅
- Live metrics: POS today, eRačun, pending AI actions ✅

### Udruge modul
- Clan, Clanarina, Donacija, KnjigaPrimitaka, MembershipPlan, MemberSubscription modeli ✅
- AML Guard (ZSPNFT) za donacije ✅
- OIB lookup + AI analiza člana ✅
- WhatsApp expiry reminders ✅
- FINA izvještaji (PR-RAS-NPF, G-PR-IZ-NPF, BIL-NPF) ✅
- EU Fondovi / volonterski izvještaji ✅
- Mobile responsive: 44px touch, bottom nav, card view ✅
- FenixCamera u 3 forme (clan, donacija, knjiga) ✅
- Testovi: 12/12 PASS ✅

### Fitness modul (Gemini — ova sesija)
- 8 modela: Member, MemberCheckIn, MembershipPlan, MemberSubscription,
  Payment, WorkoutClass, ClassBooking, Equipment ✅
- Migracije aplicirane ✅

### MCP Server
- fenix-mcp.service LIVE na :8765 ✅
- 10 alata: query_db, django_orm, read_file, write_file, list_files,
  exec_command, get_logs, system_status, pos_today, restart_service ✅
- CORS za claude.ai ✅
- Sonnet se spaja direktno iz chata ✅

### Ostalo
- Tim Chat (okrugli stol) ✅
- Bulk invite management command ✅
- Seki: uklonjen superuser, POS provjeren ✅
- AdminLangRedirectMiddleware (DE → German admin) ✅

---

## ⏳ ČEKA — otvoreni taskovi

### CC Code čeka (u redu, pokretati jedan po jedan):
1. CC_TASK_FITNESS_SIM_TEST.md — testovi + sim + 4 PDF na WhatsApp
2. CC_TASK_NOTIFICATIONS.md — push/WhatsApp notifikacije za expiry, invoice due, anomalije
3. CC_TASK_MEGA_SIMULACIJA.md — health check svih modula
4. CC_TASK_OKRUGLI_STOL_AUDIT.md — provjera PendingAIAction

### Gemini čeka:
1. GEMINI_TASK_FITNESS_IMPLEMENT.md — testovi i sim za fitness (modeli su napravljeni, testovi nisu)

### Nije ni u planu ali treba:
- Automatska naplata pretplate (Stripe ili SEPA reminder) — BLOCKER za pravi SaaS
- Payroll testovi (modul bez testova, dira plaće)
- Assessment testovi
- Konto godišnji obračun / GFI-POD automatizacija
- Onboarding wizard bez Ivana (self-service signup)

---

## 🚫 PRAVILA KOORDINACIJE

### Za CC Code:
- Uvijek čitaj FENIX_STATUS.md NA POČETKU svakog taska
- Uvijek čitaj models.py stvarnog modula PRIJE pisanja koda
- Nakon završetka — ažuriraj FENIX_STATUS.md (pomakni iz ČEKA u DONE)
- Git commit s jasnom porukom

### Za Gemini:
- Čitaj FENIX_STATUS.md na početku
- Ako piše DONE — ne opisuj to kao "sljedeći korak"
- Pišeš plan → odmah implementiraj (ne čekaj potvrdu za svaki korak)
- Nakon završetka — ažuriraj FENIX_STATUS.md

### Za Sonnet (koordinator):
- Prije pisanja taska: git log --oneline --since="danas" | grep tema
- Ako je u DONE — ne pišeš task
- Ažuriraj ovaj fajl nakon svake sesije
- Ivan je "moj enter" — finalna odluka je njegova

---

## 📊 Brojke (2026-03-21)
- Firme: 82 | Korisnici: 321 | Aktivne pretplate: 12 | MRR: 1.537 EUR
- POS bonovi: 76 | Fitness: 0 članova (testni) | Udruge: 10 članova (testni)
- Git commits danas: 49
- Python LOC: ~180.000 | Django apps: 47 | DB tables: 296

