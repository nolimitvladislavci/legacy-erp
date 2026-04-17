# CC_TASK — TROJSTVO TOP 5 IMMEDIATE FIXES
> Kreirao: Sonnet 2026-04-17 | Izvor: 1.281 Trojstvo analiza, agreed ≥85%
> Sve dijagnoze su Trojstvo konsenzus — implementacija direktna, bez analize

## TASK 1 — Payment model: 4 DB indeksa
**File:** `payments/models.py`
**Problem:** Nema indeksa na status, method, created_at. Composite za company+status+created_at.
**Fix:**
```python
class Meta:
    indexes = [
        models.Index(fields=['status']),
        models.Index(fields=['method']),
        models.Index(fields=['created_at']),
        models.Index(fields=['company', 'status', 'created_at']),
    ]
```
**Nakon:** `python manage.py makemigrations payments && migrate`

## TASK 2 — ERacun: indeks na status
**File:** `invoicing/models.py` → klasa `ERacun`
**Fix:** Dodati `db_index=True` na polje `status` ILI Index u Meta

## TASK 3 — RecallNotification admin N+1
**File:** tražiti `RecallNotificationAdmin` u admin.py fajlovima
**Fix:** Dodati `list_select_related = True` ili explicit `select_related`

## TASK 4 — payment_success/payment_cancel bez @login_required
**File:** `payments/views.py`
**Fix:** Dodati `@login_required` dekorator na obje funkcije

## TASK 5 — 9 radnika bez OIB-a: model validacija
**File:** `hrm/models.py` ili `employees/models.py` → Worker/Employee model
**Problem:** `oib` polje ima `blank=True, null=True`
**Fix:** 
```python
oib = models.CharField(
    max_length=11, 
    blank=False, 
    null=False,
    validators=[validate_oib]
)
```
**Pozornost:** Provjeri postoje li 9 radnika bez OIB-a PRIJE migracije — 
`Employee.objects.filter(oib__isnull=True).count()` — popuni ih ili obriši.

---
## UKUPNA PROCJENA: 2-3 sata CC Code rada
## POKRETANJE: claude → cd /var/www/fina-connect → pročitaj ovaj file → implementiraj redom
