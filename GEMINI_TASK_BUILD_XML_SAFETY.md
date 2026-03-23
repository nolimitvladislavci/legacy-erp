# GEMINI_TASK: _build_xml() implementacija + eIzvjestavanje safety
## Agent: Gemini Pro 2.5 | Prioritet: P0-HITNO | Datum: 2026-03-23

## Kontekst
Postoji servis koji ima `_build_xml()` s `raise NotImplementedError`.
Ovo blokira produkcijsko slanje eRačuna/eIzvješća.
Mora biti implementiran ili zaštićen PRIJE nego Marija počne slati u produkciji.

## Zadatak 1 — Lociranje problema
```bash
grep -rn "NotImplementedError\|_build_xml\|raise NotImpl" /var/www/fina-connect \
  --include="*.py" | grep -v venv | grep -v test
```
Identificiraj sve lokacije i kontekst.

## Zadatak 2 — Provjeri eIzvjestavanje servis
```bash
cat /var/www/fina-connect/eracun/services.py | grep -A 30 "_build_xml\|build_xml"
```
Čitaj stvarna polja iz modela:
```bash
grep -n "class.*Model\|XMLField\|xml_content\|report_type" \
  /var/www/fina-connect/eracun/models.py | head -40
```

## Zadatak 3 — Implementacija ili Safety Pin
Ako `_build_xml()` nije implementiran za određeni tip dokumenta:
**OPCIJA A** (ako format je poznat): Implementiraj prema CIUS-HR specifikaciji
**OPCIJA B** (ako format nije poznat): Postavi safety pin koji JASNO loggira i blokira:
```python
def _build_xml(self, ...):
    logger.error(
        f"_build_xml() nije implementiran za {self.__class__.__name__}. "
        f"Company: {self.company}. BLOKIRAN za produkciju."
    )
    raise NotImplementedError(
        f"XML builder za {self.__class__.__name__} nije implementiran. "
        f"Kontaktirajte support."
    )
```
Opcija B je bolja od tihog pada.

## Zadatak 4 — SupplierRiskAlert auto-trigger
```bash
grep -rn "SupplierRiskAlert\|supplier_risk" /var/www/fina-connect \
  --include="*.py" | grep -v venv | grep -v migration
```
Trenutno: 0 zapisa. FINA bonitet provjera nije triggerana.
Implementiraj signal koji se pokreće pri kreiranju nove fakture od dobavljača:
```python
# Na Invoice post_save signal, ako je invoice tip 'ulazna':
#   1. Provjeri postoji li SupplierRiskAlert za tog dobavljača iz zadnjih 30 dana
#   2. Ako ne — pokreni async Celery task koji provjerava FINA bonitet
#   3. Ako company nema T&C consent — preskoči (GDPR)
```

## Čitaj modele PRIJE pisanja ikakvog koda:
```bash
python manage.py shell -c "
from eracun.models import *
from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert
print([f.name for f in SupplierRiskAlert._meta.concrete_fields])
"
```

## Commit poruka
`eRacun: _build_xml safety pin + SupplierRiskAlert invoice trigger`
