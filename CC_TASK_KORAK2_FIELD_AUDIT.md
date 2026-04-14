# CC TASK — KORAK 2: Field Name Audit
**Datum: 14.04.2026. | Prioritet: KRITIČNO**
**Executor: CC Code | Reviewer: Gemini | Koordinator: Sonnet**

---

## Cilj
Eliminirati sve AttributeError greške zbog krivog naziva polja.
Svaki `.field_name` u views.py i templates mora odgovarati stvarnom polju modela.

---

## Poznati mismatchi — FIKSAJ OVO ODMAH

### 1. `Company.is_active` — ne postoji na Company modelu
**Company nema `is_active` field. Jedini pravi filter za "aktivne" firme je provjera subscriptions.**

Datoteke s bugom:
```
konto/tasks_vat.py:39              Company.objects.filter(is_active=True)
pos/views.py:2056                  Company.objects.filter(is_active=True)
tax_wizard/tasks.py:225            Company.objects.filter(is_active=True)
limit_connect_ai/tasks.py:935      Company.objects.filter(is_active=True)[:100]
core/nudge_tasks.py:42             Company.objects.filter(is_active=True)
superadmin_ai/.../ai_ops.py:226    Company.objects.filter(is_active=True)
maintenance/tasks.py:13            Company.objects.filter(is_active=True)
```

**Fix pattern:**
```python
# STARO (puca):
Company.objects.filter(is_active=True)

# NOVO (ispravno):
Company.objects.all()
# ili ako hoćeš samo s aktivnom pretplatom:
Company.objects.filter(subscriptions__status="active").distinct()
```

Izaberi `Company.objects.all()` gdje je kontekst "sve firme u sustavu" — to je ispravno jer Company model nema is_active koncept, svaka firma koja postoji je aktivna.

---

### 2. `invoice.invoice_number` — ne postoji, pravo ime je `number`
**Provjeri koji su `invoice_number` referenci na `Invoice` modelu nasuprot `ERacun`/`AS4Message` modela koji GA IMAJU.**

```python
# Invoice model → Invoice.number
# ERacun model  → ERacun.invoice_number  (postoji!)
# AS4Message    → AS4Message.invoice_number (postoji!)
```

Datoteke koje trebaju provjeru (nisu sve bugovi — neke su OK jer su na ERacun):
```
propter/services/aggregate.py         → ERacun model, OK
propter/views.py                      → provjeri koji model
partners/client_portal_views.py:442   → provjeri koji model
einvoice/services/*                   → ERacun/AS4, vjerojatno OK
```

**Akcija:** Za svaki occurrence provjeri je li `.invoice_number` na `Invoice` ili `ERacun`/`AS4Message`. Samo `Invoice` je bug. ERacun i AS4 imaju to polje.

---

### 3. Sistemski scan — pronađi ostale

Pokreni ovo i fiksaj svaki rezultat:

```bash
cd /var/www/fina-connect

# Pronađi sve field pristupe koji pucaju
python manage.py shell -c "
from django.apps import apps
import re, os

# Modeli i njihova polja
model_fields = {}
for model in apps.get_models():
    label = f'{model._meta.app_label}.{model.__name__}'
    model_fields[model.__name__] = {f.name for f in model._meta.get_fields() if hasattr(f, 'name')}

# Provjeri Company specifično
from companies.models import Company
print('Company fields:', sorted(f for f in model_fields.get('Company', set()) if 'active' in f or 'status' in f))
print('Invoice fields:', sorted(f for f in model_fields.get('Invoice', set()) if 'number' in f or 'valid' in f or 'total' in f))
"
```

---

## Protokol rada

1. **Za svaki bug:** provjeri model u `models.py` PRIJE pisanja fixa
2. **Ne pretpostavljaj** — uvijek čitaj stvarni model
3. **Nakon svakih 5 fajlova:** `python manage.py check` mora proći
4. **Commit pattern:** `fix(field-audit): Company.is_active → all() u konto/tasks_vat.py`
5. **Po završetku:** ažuriraj BUGLIST.md i FENIX_STATUS.md

---

## Završni test

```bash
# Mora biti 0 rezultata:
grep -rn "Company\.objects\.filter(is_active=True)" \
  /var/www/fina-connect/ --include="*.py" | grep -v venv | grep -v backup

# Django check mora biti clean:
python manage.py check

# Commit:
git add -A
git commit -m "fix(korak2): field name audit — Company.is_active + ostali mismatchi"
```

---

## Nakon završetka

Upiši u FENIX_STATUS.md:
```
| 2 Field audit | ✅ GOTOVO | 100% |
| 3 RouteRegistry | 🔄 AKTIVAN | 0% |
```

I pošalji WhatsApp na 4915771998747:
```python
from core.whatsapp import send_text
send_text('4915771998747', 'KORAK 2 GOTOV — Field audit čist. Kreće KORAK 3 RouteRegistry.')
```
