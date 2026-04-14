# GEMINI TASK — KORAK 2 Verifikacija
**Datum: 14.04.2026.**
**Uloga: Neovisni reviewer — CC Code radi fix, Gemini verificira**

---

## Zadatak

Dok CC Code fiksira field name mismatch, Gemini paralelno:

1. **Scan svih modela** — napravi popis svih modela i njihovih field-a:
```bash
python manage.py shell -c "
from django.apps import apps
for model in sorted(apps.get_models(), key=lambda m: m.__name__):
    fields = [f.name for f in model._meta.get_fields() if hasattr(f,'name')]
    print(f'{model.__name__}: {fields[:10]}')
" > /var/www/fina-connect/MODEL_FIELDS_INVENTORY.txt
```

2. **Cross-reference scan** — za svaki `.field_name` u views koji NIJE u modelu:
```bash
# Pronađi sve .field pristupe u views
grep -rn "\.\(invoice_number\|valid_until\|is_active\|total_amount\|grand_total\)" \
  /var/www/fina-connect/ --include="*.py" \
  | grep -v "venv\|backup\|migration\|models\.py\|#" \
  | grep -v "CompanyMembership\|UserProfile\|FiscalCert\|Permission\|Mandate" \
  > /var/www/fina-connect/FIELD_MISMATCH_CANDIDATES.txt
cat /var/www/fina-connect/FIELD_MISMATCH_CANDIDATES.txt
```

3. **Po završetku CC Code-a** — provjeri da su SVI mismatchi fiksirani:
```bash
# Svaki od ovih mora biti 0:
grep -c "Company\.objects\.filter(is_active" /var/www/fina-connect/**/*.py 2>/dev/null
grep -c "Invoice.*invoice_number" /var/www/fina-connect/**/*.py 2>/dev/null
```

4. **Upiši nalaze** u `/var/www/fina-connect/GEMINI_KORAK2_REPORT.md`

5. **Ako nađeš novi bug koji CC nije pokrio** — odmah ga fiksaj i commiti.

