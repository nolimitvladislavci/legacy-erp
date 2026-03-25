# CC_TASK_UNSCOPED_AUDIT — Cross-Tenant Izolacija Fix
# Agent: CC Code
# Prioritet: KRITIČAN — GDPR kršenje, moguće zatvorske kazne
# Datum: 2026-03-25

---

## Problem

89 mjesta u kodu koriste querije bez `.filter(company=...)` ili `.for_company(...)`.
To znači da firma A može vidjeti podatke firme B.
Ovo je kršenje GDPR-a (Art. 32 — tehničke mjere zaštite podataka).
Kazna: do 4% godišnjeg prihoda ili 20M EUR. Ivan odgovara osobno kao data controller.

---

## Korak 1 — Pronađi sva mjesta

```bash
cd /var/www/fina-connect
grep -rn "\.objects\.filter\b" --include="*.py" | grep -v "company=" | grep -v "tenant=" | grep -v "for_company" | grep -v "test_" | grep -v "migrations/" | grep -v "#" | grep -v "select_for_update" > /tmp/unscoped_candidates.txt
wc -l /tmp/unscoped_candidates.txt
```

Drugi pass — pronađi `.objects.all()` bez scope:
```bash
grep -rn "\.objects\.all()" --include="*.py" | grep -v "test_" | grep -v "migrations/" | grep -v "admin.py" >> /tmp/unscoped_candidates.txt
```

---

## Korak 2 — Klasifikacija (CC Code radi ovo)

Za svaki unos iz liste, klasificiraj u jednu od kategorija:

| Kategorija | Opis | Akcija |
|------------|------|--------|
| A — Sigurno | Interne tablice bez company FK (Country, NKD, etc.) | Ignoriraj |
| B — Riziče | Ima company FK ali query ne filtrira | FIKSAJ ODMAH |
| C — Admin only | Koristi se samo u admin viewu, superuser | Dokumentiraj |
| D — Celery task | Background task koji procesira sve kompanije | Dokumentiraj |

---

## Korak 3 — Fix pattern za kategoriju B

**Svuda gdje model ima `company` FK:**
```python
# OPASNO:
invoices = Invoice.objects.filter(status='paid')

# ISPRAVNO:
invoices = Invoice.objects.filter(company=request.company, status='paid')
# ili ako postoji manager:
invoices = Invoice.objects.for_company(request.company).filter(status='paid')
```

**Za view funkcije — dodaj helper:**
```python
# core/utils.py (dodaj ako ne postoji)
def company_scope(model_class, request):
    """Shortcut za company-scoped queryset."""
    return model_class.objects.filter(company=request.company)
```

---

## Korak 4 — Prioritetni fajlovi za fix

Na temelju portala skena, ovo su najkritičnija mjesta:

1. `invoicing/views.py` — invoice liste
2. `pos/views.py` — POS podaci
3. `archival/views.py` — arhiva dokumenata  
4. `core/views.py` — dashboard queriji
5. `reporting/views.py` — izvještaji

---

## Korak 5 — Test za svaki fix

```python
def test_cross_tenant_isolation(self):
    """Firma A ne smije vidjeti podatke firme B."""
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    invoice_b = InvoiceFactory(company=company_b)
    
    self.client.force_login(UserFactory(company=company_a))
    response = self.client.get('/invoicing/')
    
    invoice_ids = [i['id'] for i in response.context['invoices']]
    self.assertNotIn(invoice_b.pk, invoice_ids)
```

---

## Output koji CC Code mora dostaviti

Nakon audita:
1. `/tmp/unscoped_report.md` — lista svih B kategorija s linijama
2. Commit s fixevima: `fix: cross-tenant isolation — N unscoped queries fixed`
3. Broj reduciranih unscoped querija: bio 89, sada X
