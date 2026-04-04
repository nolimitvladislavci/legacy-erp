# GEMINI TASK: Warehouse Compliance Analiza + Smart Import Wire
## Agent: Gemini 2.5 Flash | Prioritet: VISOK | Datum: 2026-03-27

---

## OBAVEZNO PROČITAJ PRVO
```bash
cat LEGAL_PARAMS_MASTER.md        # Zakonski parametri
cat AGENT_PARAMS_TESTNI_PODACI.md # Testni podaci filtar
```

---

## MISIJA

1. Analiziraj stanje inventory baze (SAMO produkcijski podaci)
2. Provjeri SmartImport (CompanyMailbox) je li konfiguriran
3. Provjeri traceability (ProductTrace) je li se koristi
4. Napiši compliance report za HR/DE zakonske obveze u skladištu
5. Identificiraj top 10 artikala kojima nedostaju podaci (barkod, kategorizacija)

---

## Korak 1: Inventory SQL analiza (samo produkcija)

```sql
-- Kategorije artikala
SELECT category, COUNT(*) as n, 
       COUNT(barcode) as s_barcodom,
       COUNT(NULLIF(location,'')) as s_lokacijom
FROM inventory_inventoryitem
WHERE company_id IN (
    SELECT id FROM companies_company WHERE is_deactivated = false
)
GROUP BY category ORDER BY n DESC;

-- Artikli bez barkoda (top problemi)
SELECT name, sku, category, quantity, unit_price
FROM inventory_inventoryitem
WHERE barcode = '' OR barcode IS NULL
AND company_id IN (SELECT id FROM companies_company WHERE is_deactivated=false)
ORDER BY quantity DESC LIMIT 20;

-- StockMovement po tipu
SELECT movement_type, COUNT(*) as n, SUM(quantity) as ukupno
FROM inventory_stockmovement
GROUP BY movement_type;

-- Warehouse pregled
SELECT w.name, w.warehouse_type, COUNT(DISTINCT i.id) as artikala
FROM inventory_warehouse w
LEFT JOIN inventory_inventoryitem i ON i.company_id = w.company_id
GROUP BY w.id, w.name, w.warehouse_type;
```

## Korak 2: SmartImport provjera

```python
from smart_import.models import CompanyMailbox, ImportBatch, StagingFile

# Koliko firmi ima konfiguriran mailbox
total_mailboxes = CompanyMailbox.objects.count()
active_mailboxes = CompanyMailbox.objects.filter(is_active=True).count() if hasattr(CompanyMailbox, 'is_active') else total_mailboxes

# Koliko je batcha prošlo kroz sustav
batches = ImportBatch.objects.count()
successful = ImportBatch.objects.filter(status='completed').count() if hasattr(ImportBatch, 'status') else 0

print(f'Mailboxovi: {total_mailboxes} ukupno, {active_mailboxes} aktivnih')
print(f'Import batches: {batches} ukupno, {successful} uspješnih')
```

## Korak 3: Zakonske obveze provjera

Provjeri:
1. Ima li firmi s prehrambenim artiklima (category='food') BEZ batch/expiry evidencije → HACCP rizik
2. Ima li artikala s vrijednosti > 1000 EUR bez inventory_number → osnovna sredstva problem
3. Ima li WarehouseTransfer koji nije potvrđen > 30 dana → HR ZoR rizik

## Korak 4: Napiši report

Spremi u: `/var/www/fina-connect/WAREHOUSE_COMPLIANCE_REPORT_20260327.md`

```markdown
# Warehouse Compliance Report — 2026-03-27

## Stanje baze
...

## HR zakonske obveze (Zakon o računovodstvu čl.11)
...

## DE zakonske obveze (HGB §240, GoBD)
...

## Top problemi
...

## Preporuke za CC Code Sprint W2
...
```

## Korak 5: Poprosti propter vezu

Provjeri imaju li sve firme s aktivnim BillingPeriod-om InventoryItem-e koji bi trebali generirati otpremnice:
```sql
SELECT bp.company_id, bp.year, bp.month, bp.otpremnica_count,
       COUNT(DISTINCT ii.id) as inventory_items
FROM propter_billingperiod bp
JOIN inventory_inventoryitem ii ON ii.company_id = bp.company_id
WHERE bp.status = 'open' AND bp.year = 2026
GROUP BY bp.id, bp.company_id, bp.year, bp.month, bp.otpremnica_count;
```
