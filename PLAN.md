# FENIX MASTER PLAN — 2026-04-10
# Ažurirano: 2026-04-10 22:15 (Opus + Seki)
# Server: 0 errors, 0 pending migrations, gunicorn ✅

═══════════════════════════════════════════════════════════════
  SVE PREOSTALO — podijeljeno na 2 DIJELA
═══════════════════════════════════════════════════════════════

## STANJE DANAS (checkpoint)

  ✅ CSS redesign 9.5/10 (25k+ fixes, fenix-tokens.css)
  ✅ Global Shell deployed (3 faze, 4 modula s desnim panelom)
  ✅ Workspace model (5 desk + 31 premise, BookingSignature audit)
  ✅ Stolarija backend (12 modela, 22 viewova, 3 migracije)
  ✅ Audit 11 bugova popravljeno
  ✅ manage.py check = 0 issues
  ✅ KonjikStol removed (model + views + migration + template)
  ✅ Stolarija servis views LIVE (4 views, 4 templates, 2 Celery tasks)

═══════════════════════════════════════════════════════════════

## DIO 1 — OPUS (stavke 1-7)
## Redoslijed: zakonski rizik → integracije → UX polish

═══════════════════════════════════════════════════════════════

### 1. POS: 10 tvrtki bez POSSettings — ZAKONSKI RIZIK 🔴
  Prioritet: CRITICAL
  Procjena: 1-2h

  Problem: 10 firmi ima POS terminale ali NEMA POSSettings (fiskalni config).
  Konjik ima fiscal_active=True ali nema certifikat → lažna fiskalizacija.

  Koraci:
  - [ ] Identificiraj svih 10 firmi bez POSSettings
  - [ ] Kreiraj POSSettings za svaku (fiscal_active=False, default config)
  - [ ] Konjik: fiscal_active=False dok nema certifikat
  - [ ] Dodaj validaciju: POSTerminal ne može otvoriti smjenu bez POSSettings
  - [ ] manage.py check + git commit

---

### 2. POS ↔ Workspace integracija + BookingSignature
  Prioritet: HIGH
  Procjena: 3-4h
  Ovisi o: CC_TASK_POS_WORKSPACE.md (detaljni plan postoji)

  Koraci:
  - [ ] POSTerminal.workspace FK (nullable, SET_NULL)
  - [ ] Migracija + auto-mapping (branch → workspace)
  - [ ] BookingSignature hook: pos_open, pos_close, pos_void
  - [ ] Z-report snapshot u changes JSON
  - [ ] Verifikacija: otvori/zatvori smjenu, provjeri BookingSignature
  - [ ] manage.py check + git commit

---

### 3. Archive Readonly — zakonska obaveza 11 godina
  Prioritet: HIGH (zakon)
  Procjena: 2-3h
  Ovisi o: CC_TASK_ARCHIVE_READONLY.md (detaljni plan postoji)

  Koraci:
  - [ ] PricingPlan slug='archive_readonly' (price=0)
  - [ ] Celery task: auto-downgrade isteklih pretplata
  - [ ] RouteRegistry: readonly pristup /arhiva/ + /konto/pregled/
  - [ ] Login redirect za archived korisnike
  - [ ] /arhiva-info/ stranica s porukama
  - [ ] Celery Beat registracija (01:00 svaki dan)
  - [ ] manage.py check + git commit

---

### 4. Arhiva AI pipeline — 20k zapisa dormantna
  Prioritet: MEDIUM
  Procjena: 2-3h

  Problem: 20.000 ArhivaEntry zapisa ima ai_status='none' — AI nikad nije
  procesirao. Pipeline postoji ali nikad pokrenuta na existingima.

  Koraci:
  - [ ] Audit: koliko zapisa po ai_status (none/pending/processing/done/error)
  - [ ] Celery task: batch process existing zapisa (100 po batchu, rate limit)
  - [ ] Graceful fallback za FenixScan OCR (poznati bug)
  - [ ] Test na 10 zapisa, provjeri rezultate
  - [ ] Pusti batch na sve 20k (background, nadzor)
  - [ ] manage.py check + git commit

---

### 5. Workspace WS#5 — nedostaje Silvija
  Prioritet: LOW (brz fix)
  Procjena: 15min

  Koraci:
  - [ ] Identificiraj WS#5 i Silvijin profil
  - [ ] Dodaj Silviju kao workera u WS#5
  - [ ] Verifikacija: Silvija vidi klijente u svom workspace-u

---

### 6. Shell: Right panel za ostale module + HTMX
  Prioritet: MEDIUM
  Procjena: 3-4h

  Trenutno: konto, doktor, pos, arhiva imaju panel.
  Nedostaje: payroll, helpdesk, inventory, fitness, webshop.

  Koraci:
  - [ ] _panel_payroll.html — platne liste summary
  - [ ] _panel_helpdesk.html — otvoreni ticketi
  - [ ] _panel_inventory.html — low stock alerts
  - [ ] _panel_fitness.html — aktivni članovi + raspored
  - [ ] _panel_webshop.html — narudžbe danas
  - [ ] Django blokovi u svaki dashboard template
  - [ ] HTMX: klik na red u tablici → detalji u panelu (dynamic)
  - [ ] manage.py check + git commit

---

### 7. Dashboard redirect + auto shell_mode
  Prioritet: LOW
  Procjena: 1-2h

  Koraci:
  - [ ] Dashboard view: ako radnik ima workspace → redirect na workspace_home
  - [ ] Auto shell_mode za form templatee (focus mode)
  - [ ] Shell top restructure: kamera, skener, pretraga, notifikacije
  - [ ] Shell bottom: sync status, fiskalizacija indicator
  - [ ] manage.py check + git commit

═══════════════════════════════════════════════════════════════

## DIO 2 — SEKI (stavke 8-10)

═══════════════════════════════════════════════════════════════

### 8. Stolarija: production/installation frontend (faze 4-6)
  Prioritet: HIGH (Zdenko čeka)
  Procjena: 4-5h

  Backend POSTOJI (Opus): create_production_order, production_detail,
  create_installation, installation_detail, handover, handover_detail.

  Preostalo:
  - [ ] Templates za production dashboard (BOM pregled, status update)
  - [ ] Templates za installation checklist (mobile, foto prije/poslije)
  - [ ] Templates za handover (canvas potpis, garancija PDF)
  - [ ] PDF generiranje: ponuda + garancijski list (WeasyPrint)
  - [ ] WhatsApp slanje ponude (WAHA)
  - [ ] E-potpis kupca (canvas signature → base64)

---

### 9. Stolarija servis views ✅ DONE
  Prioritet: MEDIUM
  Zavrseno: 2026-04-10

  Realizirano:
  - [x] Kupac portal: /stolarija/garancija/<qr_token>/ — dark UI, no login
  - [x] Servisni nalog view (field mode za montera: complete + reschedule)
  - [x] Service dashboard s tabovima (upcoming/overdue/completed)
  - [x] Warranty list s statusom + next service
  - [x] Celery task: check_service_reminders (daily, 30d/7d/0d WhatsApp)
  - [x] Celery task: check_expired_warranties (weekly, auto-schedule annual)
  - [x] Auto-schedule next service (6mj) on completion
  - [x] Fixed duplicate handover() bug

---

### 10. KonjikStol ✅ DONE
  Prioritet: LOW (cleanup)
  Zavrseno: 2026-04-10

  Realizirano:
  - [x] Model removed from companies/models.py (93 lines)
  - [x] Views removed from companies/views.py (148 lines)
  - [x] Template stolovi.html removed
  - [x] Migration 0042_remove_konjikstol applied (table dropped)
  - [x] Docstring updated in moji_komitenti
  - [x] manage.py check = 0 issues

═══════════════════════════════════════════════════════════════

## TIMELINE

  10.04. (danas)  │ Opus: #1 POS fiscal + #5 Silvija (brzi fixevi)
                  │ Seki: #9 Servis views ✅ + #10 KonjikStol ✅
  11.04.          │ Opus: #2 POS↔Workspace + #3 Archive Readonly
  11-12.04.       │ Opus: #4 AI pipeline + #6 Shell paneli
  12.04.          │ Opus: #7 Dashboard redirect + Load test prep
  12.04. (CCX33)  │ Load test
  13-14.04.       │ Seki: #8 Stolarija frontend (templates + PDF + WhatsApp)
  15.04.          │ GO/NO-GO + PRODUKCIJA

═══════════════════════════════════════════════════════════════

## PRAVILA
  - manage.py check = 0 errors NAKON svakog commita
  - chown -R www-data:www-data logs/ NAKON svake sesije
  - Commit format: tip(modul): opis
  - FENIX_STATUS.md ažurirati na kraju svake sesije
