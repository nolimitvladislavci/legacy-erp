# CC_TASK_PROD_MASTER.md
# PRODUCTION MODULE — MASTER KOORDINACIJA
# Supervisor: Sonnet (Ivan)
# Datum: 04.04.2026. — večernji sprint

---

## POSTROJAVANJE — 6 AGENATA

| Agent | Task fajl | Čeka | Može početi odmah? |
|-------|-----------|------|--------------------|
| **CC #1** | CC_TASK_PROD_1_MODELS.md | — | ✅ DA — KRENE ODMAH |
| **CC #2** | CC_TASK_PROD_2_VIEWS.md | Task 1 DONE | ⏳ Čeka migrate |
| **CC #3** | CC_TASK_PROD_3_TEMPLATES.md | Task 1 DONE | ⏳ Čeka models |
| **Gemini** | CC_TASK_PROD_4_INTEGRATION.md | Task 1 DONE | ⏳ Čeka models |
| **Haiku** | CC_TASK_PROD_5_TESTS.md | Task 1+4 DONE | ⏳ Čeka services |
| **CC #6** | CC_TASK_PROD_6_KONTO_MENU.md | Task 1+2 DONE | ⏳ Čeka urls |

---

## REDOSLIJED UNLOCK-A

```
[START]
  │
  ▼
TASK 1 — Models + Migrations (CC #1)
  │ migrate prolazi → echo TASK1_DONE
  │
  ├──────────────────────────────────────┐
  ▼                                      ▼
TASK 2 — Views + URLs (CC #2)      TASK 3 — Templates (CC #3)
TASK 4 — Integration (Gemini)       [paralelno s 2 i 4]
  │
  ▼
TASK 5 — Tests (Haiku)
TASK 6 — Konto + Menu (CC #6)
  │
  ▼
[Sonnet QA — Ivan potvrdi]
  │
  ▼
git commit "feat: production MRP modul — 10/10"
```

---

## STATUS TRACKER

Svaki agent po završetku piše:
```bash
echo "TASKX_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt
```

Provjeri status:
```bash
cat /var/www/fina-connect/PROD_BUILD_STATUS.txt
```

---

## SCOPE — ŠTO ULAZI U VEČERNJI SPRINT

### ✅ ULAZI (10/10 cilj)
- `production/` Django app s 7 modela
- BOM CRUD (sastavnice + linije)
- Proizvodni nalog CRUD + FSM (7 stanja)
- Radna mjesta
- Inventory integracija (dedukcija sirovina + dodavanje gotovog)
- Troškovnik (materijal, rad, režija, po komadu)
- QC evidencija
- Konto knjiženje (automatsko pri completion)
- PDF print naloga (WeasyPrint)
- Sidebar link + RouteRegistry
- 40+ testova zeleno
- MRP planer (simulacija potreba — ne automatsko kreiranje naloga)
- Demo seed command

### ❌ NE ULAZI (Q3 2026, sljedeći sprint)
- Automatsko kreiranje naloga iz prodajnih narudžbi
- Višerazinski MRP (MRP II — kapacitetno planiranje)
- Autoservis-specifičan modul (generički work_orders pokriva)
- Intrastat export
- Integracija s vanjskim IoT senzorima (buduća Pupilla razlika)
- Mobile app za radnike na liniji

---

## ARHITEKTURNA PRAVILA ZA SVE AGENTE

1. **models.py** — FSMMixin za ProductionOrder, CompanyManager na svim modelima
2. **Decimal** — sve kalkulacije quantize(Decimal('0.01')) ili '0.0001' za per-unit
3. **select_related / prefetch_related** — NA SVIM listama (N+1 = fail)
4. **transaction.atomic** — NA SVIM operacijama koje diraju inventory
5. **logging** — `logger = logging.getLogger('production')` u svakom fajlu
6. **NULA hardkodiranih boja** u templates — samo var(--gold), var(--card) itd.
7. **Test isolation** — svaki test kreira vlastite podatke, nema global fixtures
8. **Greške** — nikad ne baci Exception u user-facing view — messages.error() + redirect

---

## QA CHECKLIST (Sonnet prolazi na kraju)

```bash
cd /var/www/fina-connect

# 1. Django sistem check
venv/bin/python manage.py check production

# 2. Migracije
venv/bin/python manage.py migrate --check

# 3. Testovi
venv/bin/python manage.py test production --verbosity=2 2>&1 | tail -5

# 4. URL smoke test
venv/bin/python -c "
import django; django.setup()
from django.urls import reverse
urls = [
    'production:dashboard', 'production:bom_list',
    'production:order_list', 'production:wc_list',
    'production:report_costs',
]
for u in urls:
    print(f'OK {reverse(u)}')" 2>/dev/null

# 5. Model import
venv/bin/python -c "
import django; django.setup()
from production.models import (
    BillOfMaterials, BOMLine, WorkCenter,
    ProductionOrder, ProductionOrderLine,
    ProductionCost, ProductionQualityCheck
)
from production.services import BOMCostEngine, ProductionInventoryService, MRPPlanner
print('ALL IMPORTS OK')" 2>/dev/null

# 6. HTTP audit (kad gunicorn radi)
for path in "/hr/production/" "/hr/production/bom/" "/hr/production/nalozi/" "/hr/production/radna-mjesta/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -b "sessionid=x" "https://limit-connect.com$path")
  echo "[$code] $path"
done

# 7. Status tracker
cat PROD_BUILD_STATUS.txt
```

Sve mora biti zeleno → `git commit`

---

## COMMIT MESSAGE (na kraju)

```
feat: Modul Proizvodnje (MRP) — v1.0

- 7 modela: BOM, BOMLine, WorkCenter, ProductionOrder,
  ProductionOrderLine, ProductionCost, ProductionQualityCheck
- FSM: 7 stanja (draft→planned→in_progress→paused→completed→invoiced)
- BOMCostEngine: kalkulacija troška s škartom
- ProductionInventoryService: automatska dedukcija sirovina (atomic)
- MRPPlanner: simulacija potreba materijala
- Konto: automatsko knjiženje pri completion (6000/6100/6200/1300)
- PDF print (WeasyPrint)
- 40+ testova zeleno
- Sidebar + RouteRegistry
- Pupilla rupa zatvorena — LIMIT Connect ima MRP

Closes: CC_TASK_PROD_1-6
```
