# PORTAL SKEN IZVJEŠTAJ — 2026-03-25
# Agent: Sonnet (koordinator) | Metoda: Automatski sken svih modula
# Distribuirati trojici: CC Code → bugfixi, Gemini → istraživanje, Sonnet → koordinacija

---

## 🔴 KRITIČNI BUGOVI (padaju u produkciji svaki dan)

### BUG-01: ai_hints.py — direction field na pogrešnom modelu
**Fajl:** `/var/www/fina-connect/core/services/ai_hints.py` linija ~119
**Greška:** `Cannot resolve keyword 'direction' into field`
**Učestalost:** SVAKI učitaj konto dashboarda (vidljivo u logovima 5+ puta/h)
**Uzrok:** `_check_eracun_status()` filtrira AS4Message po `direction='IN'`, ali iznimka
pokazuje polja koja su od *eRačun posrednik* modela — drugi model bez direction polja.
**Fix:** Zamijeniti `direction='IN'` s MessageDirection.INBOUND ili dodati try/except specifičniji

### BUG-02: pos/pulse.py — contains lookup PostgreSQL syntax
**Fajl:** `/var/www/fina-connect/pos/pulse.py` linija 126
**Greška:** `Pulse analyze failed: contains lookup is not supported on this database backend`
**Uzrok:** `metadata__contains={'threshold': threshold}` — ovo je SQLite sintaksa.
U PostgreSQL: `metadata__has_key='threshold'` ili `metadata__contains={'threshold': x}`
(JSONField na PostgreSQL podržava `contains` ali s drugačijom semantikom).
**Fix:** Zamijeniti s `metadata__threshold__gte=threshold` ili koristiti Python filter

### BUG-03: udruga signal — item_name field
**Fajl:** pos/signals.py (udruga hook na receipt)
**Greška iz loga:** `Cannot resolve keyword 'item_name' into field. Choices are: barcode, description...`
**Uzrok:** Signal filtrira ReceiptItem po `item_name` — polje se zove `description`
**Fix:** Jednolinijna zamjena field name-a

---

## 🟡 SREDNJI PROBLEMI

### PROB-04: Joker Pricing — ?profile= parameter nije implementiran
**Fajl:** `website/views.py` — `pricing_page()`
**Stanje:** View postoji, template postoji, ali nema routing po profilu
**Nedostaje:** `profile = request.GET.get('profile', '')` + filtriranje planova po profilu
**Utjecaj:** /pricing/?profile=udruga → ne prikazuje samo udruga plan (prikazuje sve)

### PROB-05: N+1 query problemi u 12 templatea
**Mjesta:** Svuda gdje se `.items.all()`, `.invoices.all()`, `.hives.all()` poziva u template loopu
**Utjecaj:** Svaki redak u listi = novi DB query. Na 200 redova = 200+ querija
**Fix:** `prefetch_related` u view-u

### PROB-06: ai_hints — eRacun posrednik model nema 'direction' polje
Vidjeti BUG-01 — sekundarni uzrok je da se `_check_eracun_status` može zvati i na
EInvoice/EDocumentArchive modelu koji nema `direction` — pokriveno try/except ali bučno

### PROB-07: public_pdf view — nema rate limiting
**Stanje:** Javni PDF endpoint bez autentifikacije ili rate limita
**Rizik:** Malicious crawler može generirati 1000 PDFova/minuti i opteretiti WeasyPrint
**Fix:** Cache per-token (24h) + max 10 req/h per token

---

## 🟢 PRILIKE (zarada, UX, akvizicija)

### OPP-01: Pricing page profili (BORG routing)
**Stanje:** pricing_ai_advisor endpoint postoji i ima industry routing
**Nedostaje:** URL routing + profil kartice + 4 kutna gumba
**Potencijal:** Svaka firma koja stigne na /pricing/?profile=pcela → direktno vidi APPRRR subvenciju

### OPP-02: CompanySubscription model POSTOJI u registration/models.py
**Stanje:** Model `CompanySubscription` je u registration/models.py — CC je već napravio!
**Nedostaje:** View za pregled subscriptiona, cockpit widget, trial tracking
**Napomena:** Sonnet CC_TASK_SUBSCRIPTION_TRACKING.md treba se updateati

### OPP-03: Worktime — sve template postoje
**Stanje:** analytics.html, approve_list.html, manager_timesheet.html — sve postoji
**Prilike:** Worktime modul je spreman ali nije prominentno u navigaciji

### OPP-04: Registration ServiceAgreement modeli — CC Code ih je napravio jutros
**Commit:** 293aae1 — ServiceAgreement + ServiceProvider + CompanyDocument
**Stanje:** Modeli postoje, ali nema views/templates za onboarding flow
**Ovo je dio 3-klik registracije:** ugovor o korištenju se treba prikazati i prihvatiti

---

## 📊 STATISTIKE SKENA

| Metrika | Vrijednost | Status |
|---------|-----------|--------|
| Aktivnih bugova u logovima | 3 ponavljajuća | 🔴 |
| Admin redirecti u invoicingu | 0 (popravljeno danas) | ✅ |
| N+1 queriji u templateima | 12 mjesta | 🟡 |
| unscoped() pozivi | 89 (audit potreban) | 🟡 |
| Views bez @login_required | 3 (generate_qr, generate_zki, public_pdf) | ⚠️ |
| Ukupno testova | 178 fajlova | ✅ |
| Commita danas | 9 | ✅ |
| Servisi aktivni | gunicorn, celery-worker, celery-beat | ✅ |

---

## DISTRIBUCIJA — TKO RADI ŠTO

### CC Code → CC_TASK_PORTAL_BUGFIX_SPRINT.md (HITNO)
- BUG-01: ai_hints direction fix (1 linija)
- BUG-02: pulse.py contains lookup fix (1 linija)
- BUG-03: udruga signal item_name→description (1 linija)
- PROB-04: pricing_page ?profile= parametar (30 linija)
- PROB-07: public_pdf rate limiting

### Gemini → GEMINI_TASK_PORTAL_SCAN_FINDINGS.md
- OPP-01: Istraži svaki pricing profile — koja su ključna prodajna mjesta?
- Provjeri pricing_ai_advisor logiku — je li BORG routing ispravno mapiran na PLAN_FEATURES?
- N+1 queriji — napiši prefetch_related preporuke za top 5 mjesta

### Sonnet (ovo) → ažuriranje FENIX_STATUS.md

---
Zadnje ažuriranje: 2026-03-25 — Sonnet sken
