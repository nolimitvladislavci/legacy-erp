# BUGLIST.md — Inventura rušenja
**Datum: 14.04.2026. | KORAK 1 ZLATNI KOD plana**

---

## STATUS LEGENDA
- ✅ FIKSIRANO — u ovoj sesiji
- 🔄 U TIJEKU
- ⏳ NA REDU
- ❌ POZNATO, NIJE KRITIČNO

---

## KRITIČNI BUGOVI (5xx / daily crash)

| # | Bug | Modul | Pojavnost | Status |
|---|-----|-------|-----------|--------|
| B-01 | `Company.is_active` ne postoji → FieldError svaki dan 06:30 | `inventory/prediction_tasks.py` | Svaki dan | ✅ |
| B-02 | `User.objects.filter(company=...)` → User nema company FK | `inventory/prediction_tasks.py` | Svaki dan | ✅ |
| B-03 | `AnonymousUser.profile` → 18x ERROR log, `logger.exception` za expected case | `core/company_utils.py` | Stalno | ✅ |
| B-04 | WeasyPrint `base_url=None` → Relative URI bez baze (logo, potpis) | `invoicing/services/pdf_service.py` | Celery PDF | ✅ |
| B-05 | `notification_api` datetime nije ISO string → potencijalni 502 | `notifications/views.py` | 5x 502 | ✅ |
| B-06 | 58.174 notifikacija → RAM/DB pressure na polling | `notifications/` | Stalno | ✅ |
| B-07 | `fiscal_status_api` bez `@login_required` → 223x 302 redirect | `pos/views.py` | 223x | ✅ |

---

## FIELD NAME MISMATCH (KORAK 2 — sljedeće)

| # | Bug | Ispravan field | Gdje greška | Status |
|---|-----|---------------|-------------|--------|
| F-01 | `invoice.invoice_number` → `invoice.number` | `Invoice.number` | `client_portal`, `portal_ai_agent`, `portal_accept_trail` | ✅ |
| F-02 | `invoice.valid_until` → `invoice.validity_date` | `Invoice.validity_date` | `client_portal` view + template | ✅ |
| F-03 | `POSReceipt.total_amount` → `POSReceipt.total` | `POSReceipt.total` | `core/views.py:1261` | ✅ |
| F-04 | `Company.is_active` ne postoji | nema — filter po subscriptions | `inventory/prediction_tasks.py` | ✅ |
| F-05 | `switch_company` — `Company` conditional import u try/except | mora biti na vrhu funkcije | `accounts/views.py` | ✅ |
| F-?? | Preostali mismatchi u 89 app-ova | — | KORAK 2 | ⏳ |

---

## ROUTEREGISTRY MISSES (KORAK 3 — sljedeće)

| # | Ruta | Problem | Status |
|---|------|---------|--------|
| R-01 | `customer_room` (/hr/ponuda/) | Nije bila PUBLIC → 302 za sve | ✅ |
| R-02 | `qr_code` (/qr/) | Nije bila PUBLIC | ✅ |
| R-03 | `public_pdf` | Nije bila PUBLIC | ✅ |
| R-04 | `portal_ai`, `portal_accept_trail` | Nisu bile PUBLIC | ✅ |
| R-05 | `fiscal_status_api` | Nije bila registrirana | ✅ |
| R-06 | `notification_api` | Nije bila registrirana | ✅ |
| R-07 | `pricing` | Nije bila PUBLIC | ✅ |
| R-?? | Sve ostale javne/AJAX rute | KORAK 3 — sistemski prolaz | ⏳ |

---

## 302 REDIRECTI (tiha blokiranja)

| # | Putanja | Pojavnost | Uzrok | Status |
|---|---------|-----------|-------|--------|
| D-01 | `/hr/pos/fiscal/status-api/` | 223x | Bez @login_required, RouteRegistry miss | ✅ |
| D-02 | `/hr/dashboard/company/` | 126x | `total_amount` field bug (rješen) | ✅ |
| D-03 | `/push/vapid-public-key/` | 58x | RouteRegistry miss | ✅ |
| D-04 | `/hr/ponuda/UUID/` | 6x | RouteRegistry + validity_date bug | ✅ |
| D-05 | `/hr/livestock/` | 32x | DomainGate za memio.farm → legitimno | ❌ |
| D-06 | `/hr/umbrella/` | 28x | Provjeri — možda RouteRegistry | ⏳ |
| D-07 | `/hub/` | 2x | Provjeri URL prefix | ⏳ |

---

## CELERY TASKOVI (dnevni)

| # | Task | Problem | Status |
|---|------|---------|--------|
| C-01 | `inventory.prediction_tasks.check_predictive_stockouts` | Company.is_active | ✅ |
| C-02 | `pos.trojstvo_task` | KORAK 1 MEMO | ⏳ |
| C-03 | Anthropic Advisor integracija | `core/anthropic_advisor.py` | ⏳ |

---

## INFRASTRUKTURA

| # | Problem | Status |
|---|---------|--------|
| I-01 | `--preload` na gunicorn → template cache locked | ✅ |
| I-02 | `cached.Loader` explicit u settings | ✅ |
| I-03 | `systemctl reload` umjesto `restart` u CI/CD | ✅ |
| I-04 | 58k notifikacija → memory pressure | ✅ 30k obrisano |
| I-05 | HMAC na QR endpoint | ✅ |

---

## PREOSTALO ZA KORAK 2

```bash
# Sistemski prolaz field mismatch — pokrenuti:
grep -rn "\.invoice_number\|\.valid_until\|\.is_active" \
  /var/www/fina-connect/ --include="*.py" --include="*.html" \
  | grep -v "venv\|backup\|migration" | grep -v "User\.is_active\|InvoiceItem\|CompanyBranch"
```

