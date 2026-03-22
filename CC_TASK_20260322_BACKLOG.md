# KONSOLIDIRANI BACKLOG — 22.03.2026
# Sve neriješeno iz 60 starih task fajlova, filtrirano na ono što ima smisla.
# Prioritet: VISOK → SREDNJI → NIZAK

---

## VISOK PRIORITET

### 1. POS Redesign "3 klika" (iz CC_TASK_POS_REDESIGN_3KLIKA.md)
- Auto-seed TaxRate pri registraciji (HR/DE/AT/SI)
- TaxRate management stranica
- POSCashier.oib migracija (zakonski obavezno)
- Novi 3-step wizard: Porezne stope → Blagajnik+OIB → Tip = OTVORI POS
- Fix artikl unos 404
- OIB operatera u fiskalizaciju

### 2. Robot Prodavač — Šeki pilot (iz CC_TASK_ROBOT_PRODAVAC_KOMPLET.md)
- Webshop artikli za Uvijek Friško (617 artikala vidljivo)
- Kiosk template (QR → naruči → plati → pokupi)
- PDF QR plakati za Vladislavce/Ivanovac

### 3. AI Assistant ne reagira (bug iz testiranja 21.03.)
- AI cockpit fixan (3 broken queries), ali AI chat/pomoćnik ne radi
- Dijagnosticirati: koji endpoint, koji error

### 4. Predkomora testovi (iz CC_TASK_TESTS_PREDKOMORA.md)
- 15 testova za StagingFileHeader, auto_match, Predkomora review
- Hash chain testovi (GEMINI_TASK_TESTS_HASHCHAIN.md — 13 testova)

---

## SREDNJI PRIORITET

### 5. Korpaš import (iz CC_TASK_KORPA_IMPORT.md)
- Uvoz ~60 klijenata iz Synesis MDB u ERP
- Fizički pristup KS LIMIT serveru ili BAT remote sync

### 6. Transport modul deploy (iz CC_TASK_TRANSPORT_DEPLOY.md)
- Migracije + views + fleet dashboard
- CMR dokument, rute, utovar

### 7. Livestock V3 (iz CC_TASK_LIVESTOCK_V3.md)
- Karenca → POS blokada (djelomično implementirano)
- Offline PWA za teren
- JRDŽ osnova (institucijski pristup)

### 8. AI Compliance watchdog (iz GEMINI_TASK_LIMIT_AI_COMPLIANCE.md)
- Automatsko praćenje zakonskih promjena
- Alert na nove propise koji utječu na klijente

### 9. Newsletter / Faza 3 outreach (iz CC_TASK_FAZA3_NEWSLETTER.md)
- Email kampanje za akviziciju
- Bulk invite flow

---

## NIZAK PRIORITET (može čekati)

### 10. Fitness modul za Mislava (CC_TASK_FITNESS_SIM_TEST.md)
### 11. DE Markt promo stranica (GEMINI_TASK_DE_MARKT.md)
### 12. Okrugli stol audit (CC_TASK_OKRUGLI_STOL_AUDIT.md)
### 13. TimChat fix (CC_TASK_TIMCHAT_FIX.md)

---

## VEĆ NAPRAVLJENO (za brisanje)
- CC_TASK_GTM_FOUNDATION.md ✅
- CC_TASK_PREDARHIVA_BULK_OCR.md ✅
- CC_TASK_POS_QR_INSTANT_OPEN.md ✅
- CC_TASK_LIMIT_AI_FOUNDATION.md ✅
- CC_TASK_OFFLINE_ENGINE.md ✅
- CC_TASK_FENIX_INTELLIGENCE.md ✅
- CC_TASK_FENIX_INTELLIGENCE_V2.md ✅
- CC_TASK_FENIX_CAMERA.md ✅
- CC_TASK_FENIX_CAMERA_INTEGRACIJA.md ✅
- CC_TASK_MCP_SERVER.md ✅
- CC_TASK_PRICING_RESTRUKTURA.md ✅
- CC_TASK_INSTITUTIONAL_ACCESS.md ✅
- CC_TASK_IVAN_COCKPIT.md ✅
- CC_TASK_COCKPIT_*.md (4 fajla) ✅
- CC_TASK_OKRUGLI_STOL.md ✅
- CC_TASK_POS_BRUTAL.md ✅
- CC_TASK_MEGA_SIMULACIJA.md ✅
- CC_TASK_ERACUN_UNIQUE.md ✅
- CC_TASK_NOTIFICATIONS.md ✅
- CC_TASK_NOTIFY.md ✅
- CC_TASK_WIDGET_FIX.md ✅
- CC_TASK_LIVE_METRICS_FIX.md ✅
- CC_TASK_WHATSAPP_SEND_DOCUMENT.md ✅
- CC_TASK_SUPERADMIN_AI_FEEDBACK.md ✅
- CC_TASK_SEKI_POS_CHECK.md ✅
- CC_TASK_DE_PROMO.md ✅
- CC_TASK_POLISH_MARIJA.md ✅
- CC_TASK_ARHIVA_*.md (3 fajla) ✅
- CC_TASK_BULK_INVITE.md ✅
- CC_TASK_VET_INTEGRATION.md ✅
- CC_TASK_UDRUGE_SIMULACIJA.md ✅
- GEMINI_TASK_BULK_INVITE.md ✅
- GEMINI_TASK_OKRUGLI_STOL.md ✅
- GEMINI_TASK_VIKEND_PLAN.md ✅
- GEMINI_TASK_ERACUN_PRAVO.md ✅
- GEMINI_TASK_FITNESS_*.md (2 fajla) ✅
- GEMINI_TASK_DE_MARKT.md ✅
- CC_TASK_TRANSPORT_TESTS.md ✅

## UPUTA ZA BRISANJE
Kad korisnik odobri, obriši sve iz "VEĆ NAPRAVLJENO" sekcije:
```bash
cd /var/www/fina-connect
# listaj pa potvrdi
ls CC_TASK_GTM_FOUNDATION.md CC_TASK_PREDARHIVA_BULK_OCR.md ...
# brisanje
rm CC_TASK_GTM_FOUNDATION.md CC_TASK_PREDARHIVA_BULK_OCR.md ...
```
