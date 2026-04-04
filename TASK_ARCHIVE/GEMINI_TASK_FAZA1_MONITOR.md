# GEMINI_TASK_FAZA1_MONITOR — Nadzor implementacije Faze 1
## Agent: Gemini | Datum: 2026-03-28

Dok CC Code implementira CC_TASK_FAZA1_ARMATURA.md, Gemini prati:

## TASK G1 — Provjera circular importa

Nakon što CC Code kreira card_ops app, provjeri:
```bash
cd /var/www/fina-connect
venv/bin/python -c "
from card_ops.mixins import FSMMixin
from card_ops.models import CardActivity, StatusTimestamp
from work_orders.models import WorkOrder
from burza.models import ProjectLead
print('Import OK — nema circular importa')
"
```

## TASK G2 — Provjera save() guard

```bash
venv/bin/python manage.py shell -c "
from work_orders.models import WorkOrder
wo = WorkOrder.objects.filter(status='draft').first()
if wo:
    wo.status = 'invoiced'
    try:
        wo.save()
        print('KRITIČNO: save() guard ne radi!')
    except ValueError as e:
        print('OK: save() guard radi —', str(e)[:60])
"
```

## TASK G3 — SLA timestamp provjera

Nakon prve tranzicije provjeri da se StatusTimestamp kreira:
```bash
venv/bin/python manage.py shell -c "
from card_ops.models import StatusTimestamp
print('StatusTimestamp count:', StatusTimestamp.objects.count())
if StatusTimestamp.objects.exists():
    ts = StatusTimestamp.objects.latest('entered_at')
    print('Zadnji:', ts.status, ts.entered_at, 'exit:', ts.exited_at)
"
```

## TASK G4 — Provjera injekcije (KRITIČNO)

Potvrdi da linija 90 i 182 u work_orders/views.py
VIŠE NEMA direktno `wo.status = request.POST.get(...)`:
```bash
grep -n "request.POST.get.*status\|wo\.status\s*=" work_orders/views.py
```
Rezultat smije sadržati samo `transition_to()` pozive, ne direktne assignmente.

## REPORT FORMAT
Po završetku svake provjere, upiši u FENIX_STATUS.md pod "Gemini validacija Faze 1".
