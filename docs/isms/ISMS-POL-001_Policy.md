# ISMS Policy — Information Security Management System
## LIMIT Connect ERP Platform

**Dokument:** ISMS-POL-001
**Verzija:** 1.0
**Datum:** 20.03.2026.
**Vlasnik:** Konjik d.o.o. (OIB: 37590751921)
**Odobrio:** Ivan Brtan, Direktor
**Klasifikacija:** Interno

---

## 1. Opseg (Scope)

Ovaj ISMS pokriva:
- **Platformu** LIMIT Connect ERP (limit-connect.com)
- **Infrastrukturu** — Hetzner Cloud server (37.27.248.86), PostgreSQL baza, Nginx, Gunicorn
- **Module** — POS, Fakturiranje, eRačun, Arhiva, Konto, Zalihe, Worktime, Payroll, Udruge
- **Integracije** — FINA CIS (HR fiskalizacija), Fiskaly Cloud TSE (DE KassenSichV), Stripe, Revolut, BTCPay, PayPal
- **Korisnike** — 78 tvrtki, ~300 korisnika, 33.268 partnera u bazi
- **Tržišta** — Hrvatska (HR) i Njemačka (DE)

Isključeno iz opsega: fizička sigurnost korisničkih uređaja, treći softver na korisničkim računalima.

---

## 2. Politika informacijske sigurnosti

### 2.1 Izjava uprave

Konjik d.o.o. se obvezuje na zaštitu informacijske imovine svojih klijenata i partnera. Svi zaposlenici, suradnici i sustavi moraju poštivati ovu politiku.

### 2.2 Ciljevi sigurnosti

1. **Povjerljivost** — Pristup podacima samo ovlaštenim osobama
2. **Integritet** — Zaštita podataka od neovlaštene izmjene
3. **Dostupnost** — Sustav dostupan 99.5% vremena (godišnje)

### 2.3 Zakonski okvir

- GDPR / Uredba (EU) 2016/679
- Zakon o zaštiti osobnih podataka (NN 42/18)
- Zakon o fiskalizaciji (NN 133/12)
- KassenSichV (DE) — §146a AO
- GoBD (DE) — Grundsätze ordnungsmäßiger Buchführung
- DSFinV-K v2.3

---

## 3. Organizacija informacijske sigurnosti

### 3.1 Uloge i odgovornosti

| Uloga | Osoba | Odgovornost |
|-------|-------|-------------|
| **Vlasnik ISMS-a** | Ivan Brtan | Ukupna odgovornost za sigurnost |
| **Tehnički direktor** | Nikša Višković | Infrastruktura i DE compliance |
| **Službenica za zaštitu podataka** | Marija Brtan | GDPR, revizija, izvještavanje |
| **Operativni sigurnosni tim** | Claude Code (AI) | Monitoring, patching, incident response |

### 3.2 Pregled politike

Politika se preispituje:
- Godišnje (redovni pregled)
- Nakon svakog sigurnosnog incidenta
- Kod značajnih promjena sustava ili zakonodavstva

---

## 4. Implementirane kontrole (Annex A mapping)

### A.5 Politike informacijske sigurnosti
- [x] Ovaj dokument (ISMS-POL-001)
- [x] Acceptable Use Policy (u planu)

### A.6 Organizacija
- [x] Definirane uloge (super_admin, company_admin, manager, accountant, employee)
- [x] Razdvajanje dužnosti (RBAC — 10 permission fajlova)
- [x] Kontakt s nadležnim tijelima (FINA, Porezna uprava, BSI)

### A.7 Sigurnost ljudskih resursa
- [x] ForcePasswordChangeMiddleware — obavezna promjena lozinke
- [x] Role-based pristup modulima (CompanyModuleConfig)
- [x] Audit trail za svaku korisničku akciju (ActivityEvent)

### A.8 Upravljanje imovinom
- [x] Inventar informacijske imovine (Company, InventoryItem, Partner modeli)
- [x] Klasifikacija podataka (company-level tenant isolation)
- [x] Multi-tenant izolacija (CompanyManager queryset filter)

### A.9 Kontrola pristupa
- [x] RBAC sustav (permissions/ modul — 10 fajlova)
- [x] IP filter middleware (IPFilterMiddleware)
- [x] Session management (Django session + CSRF)
- [x] Kompanijska izolacija (get_user_company() helper)
- [x] Umbrella pristup (parent-child company hierarchy)

### A.10 Kriptografija
- [x] TLS 1.3 (HTTPS, HSTS preload)
- [x] Fernet enkripcija certifikata (FiscalConfig._cert_password)
- [x] SHA-256 hash chain (audit_certificate — blockchain princip)
- [x] SHA-256 document integrity (doc_integrity.py)
- [x] TSE kriptografski potpis (Fiskaly Cloud TSE)

### A.11 Fizička sigurnost
- [x] Hetzner Cloud — ISO 27001 certificirani podatkovni centri
- [x] Lokacija: Helsinki, Finska (EU)
- [x] Redundantno napajanje i hlađenje (Hetzner SLA)

### A.12 Operativna sigurnost
- [x] Automatski backup (lc_backup.sh — svaki dan 03:00)
- [x] 14-dana retencija backupa
- [x] Self-healing (lc_self_heal.sh — svakih 10 min)
- [x] Health monitoring (lc_health_monitor.sh — svakih 5 min)
- [x] Error monitoring (lc_error_monitor.sh — svakih 5 min)
- [x] Logging (gunicorn, celery, nginx — rotacija)
- [x] Git verzioniranje koda (initial commit + snapshots)

### A.13 Komunikacijska sigurnost
- [x] HSTS (max-age=31536000, includeSubDomains, preload)
- [x] Content-Security-Policy (script-src, style-src, img-src ograničeni)
- [x] X-Frame-Options: SAMEORIGIN
- [x] X-XSS-Protection: 1; mode=block
- [x] X-Content-Type-Options: nosniff

### A.14 Nabava i razvoj sustava
- [x] Git verzioniranje (3.395 fajlova, 720K linija)
- [x] Test suite (50 POS testova, 2618 ukupno)
- [x] Code review proces (Claude Code + Sonnet + Gemini)
- [x] Staging prije produkcije (is_demo flag)

### A.15 Odnosi s dobavljačima
- [x] Fiskaly GmbH — BSI-K-TR-0493-2021 (Cloud TSE)
- [x] Hetzner Cloud — ISO 27001 certificiran
- [x] Stripe — PCI DSS Level 1
- [x] Let's Encrypt — automatski SSL certifikati

### A.16 Upravljanje incidentima
- [x] AnomalyReport model (AI detekcija anomalija)
- [x] Email alerti na sustav pad (health_monitor)
- [x] WhatsApp notifikacije za kritične događaje
- [x] AML Guard (pranje novca detekcija — 10k EUR prag)
- [x] VolunteerTaxGuard (neoporezivi limit provjera)

### A.17 Kontinuitet poslovanja
- [x] Disaster Recovery skripta (lc_rebuild.sh)
- [x] Dnevni DB backup (24MB gzip)
- [x] Git snapshot koda
- [x] Offline POS rad (IndexedDB)
- [ ] Formalni BCP dokument (vidi ISMS-BCP-001)

### A.18 Sukladnost
- [x] GDPR — minimalizacija podataka, pravo na brisanje
- [x] HR fiskalizacija — FINA CIS, ZKI/JIR
- [x] DE KassenSichV — Fiskaly TSE, DSFinV-K export
- [x] GoBD — unveränderbarkeit, hash chain
- [x] AML/ZSPNFT — donacija monitoring

---

## 5. Metrički ciljevi

| Metrika | Cilj | Mjerenje |
|---------|------|---------|
| Uptime | ≥ 99.5% | health_monitor log |
| Backup uspješnost | 100% | lc_backup.log |
| Incident response | < 30 min | email alert → fix |
| Password policy compliance | 100% | ForcePasswordChange |
| Patch time (kritični) | < 24h | Git commit history |

---

## 6. Potpis

| Uloga | Ime | Datum | Potpis |
|-------|-----|-------|--------|
| Direktor | Ivan Brtan | 20.03.2026. | _________________ |
| Tehnički direktor | Nikša Višković | __.__.2026. | _________________ |
| DPO | Marija Brtan | __.__.2026. | _________________ |

---

*Ovaj dokument je klasificiran kao INTERNO i ne smije se distribuirati izvan organizacije bez odobrenja vlasnika ISMS-a.*
