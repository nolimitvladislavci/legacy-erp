# CC TASK: Bug Fix Sprint — Čiste gaće za Mariju
# Agent: CC Code | Prioritet: 🔴 KRITIČNO | Datum: 2026-03-26
# Cilj: Nula 500 grešaka, nula pravnih rupa, sve zeleno za 15.4.

## OBAVEZNO PROČITAJ PRVO
```bash
cat FENIX_STATUS.md | head -30
git log --oneline -5
python manage.py check
```

---

## BUG-01: T&C Consent — 77/90 firmi bez potpisa (🔴 PRAVNI RIZIK)
**Problem:** has_signed_tc_consent=False za 77 aktivnih firmi. Bez ovoga nema
pravne osnove za obradu podataka (GDPR čl.6).

**Rješenje:**
1. Provjeri postoji li onboarding flow koji prikazuje T&C
2. Dodaj middleware ili login redirect: ako firma nema T&C → redirect na /legal/tc-accept/
3. View `/legal/tc-accept/` → POST sprema has_signed_tc_consent=True + tc_consent_signed_at + tc_consent_version
4. Exempt: superadmin, API requests, ajax

```python
# Provjeri fields
from companies.models import Company
c = Company.objects.first()
print([f.name for f in c._meta.fields if 'tc' in f.name.lower()])
```

**Test:** test_tc_redirect_unsigned() + test_tc_accept_saves()
**Commit:** `fix: T&C consent middleware — redirect unsigned firms to accept page`

---

## BUG-02: Worktime PDF export ne postoji (🟠)
**Problem:** `worktime_pdf_export` ne postoji u worktime/views.py

**Provjeri što postoji:**
```bash
grep -n "def.*pdf\|def.*export\|def.*print" worktime/views.py | head -20
grep -n "worktime.*pdf\|pdf.*worktime" worktime/urls.py
```

**Rješenje:** Kreiraj `worktime_pdf_export(request)` view koji:
- Filtrira TimeEntry za tekući user ili company (user_only=1 param → samo vlastite)
- Generira PDF s WeasyPrint (koristi postojeći worktime_report template)
- Vraća FileResponse

**Commit:** `fix: worktime PDF export view — user_only param, WeasyPrint`

---

## BUG-03: Tax Wizard sidebar link nedostaje (🟡)
**Problem:** Link na /hr/porezni-savjetnik/ nije u glavnom sidebaru

**Provjeri:**
```bash
grep -n "porezni\|tax_wizard\|savjetnik" templates/base.html | head -10
grep -rn "sidebar" templates/ --include="base*.html" -l
```

**Rješenje:** Dodaj u sidebar (uz ostale module):
```html
<li class="nav-item">
  <a href="{% url 'tax_wizard:dashboard' %}" class="nav-link {% active 'tax_wizard' %}">
    <i class="bi bi-calculator"></i> Porezni savjetnik
  </a>
</li>
```
Samo ako ima modul aktivan: `{% if request.company.module_config.tax_wizard_enabled %}`

**Commit:** `fix: tax wizard link u sidebaru`

---

## BUG-04: buyer_type — 19.385 partnera defaultno b2c (🟡)
**Problem:** Svi partneri bez buyer_type su b2c — PDV obračun može biti kriv za B2B.

**NE diraj postojeće podatke masovno.** Umjesto toga:
1. Dodaj u Partner create/edit formu: buyer_type polje obvezno (ne smije biti prazno)
2. U API importu (Synesis): auto-detect iz VAT broja (ako ima VAT ID → b2b)
3. Notification adminu: "X partnera bez točnog buyer_type — provjeri"

**Commit:** `fix: buyer_type validation — obavezno polje u formi, VAT auto-detect`

---

## BUG-05: POS receipt_number race condition (🟠)
**Problem:** Dva paralelna bona mogu dobiti isti receipt_number ako se kreiraju
istovremeno (last = session.receipts.order_by('-receipt_number').first() nije atomarno).

**Provjeri:**
```bash
grep -n "receipt_number\|select_for_update\|atomic" pos/views.py | head -20
```

**Rješenje:** Zaokruži dodjelu broja s `select_for_update`:
```python
from django.db import transaction

with transaction.atomic():
    last = session.receipts.select_for_update().order_by('-receipt_number').first()
    next_num = (last.receipt_number + 1) if last else 1
    receipt = POSReceipt.objects.create(session=session, receipt_number=next_num, ...)
```

**Test:** test_concurrent_receipt_number() — 2 threada istovremeno
**Commit:** `fix: POS receipt_number race condition — select_for_update`

---

## BUG-06: FINA eRačun namespace (🟠)
**Provjeri:**
```bash
python manage.py shell -c "
from eracun.services.posrednik_service import PosrednikService
s = PosrednikService()
print(dir(s))
"
grep -n "namespace\|xmlns\|urn:oasis" eracun/services/posrednik_service.py | head -10
```

Ako postoji namespace mismatch → ispravi xmlns string na korektni UBL 2.1 namespace.
**Commit:** `fix: FINA eRačun UBL namespace`

---

## KRAJ SPRINTA
1. `python manage.py test invoicing pos worktime --keepdb` — svi zeleni
2. `python manage.py run_system_test --quick` — 0 kritičnih
3. git commit po svakom bugu zasebno
4. Ažuriraj FENIX_STATUS.md — označi bugove kao DONE
