# CC_TASK_FAZA3_AI_MOZAK — Heuristic Triage + Smart Dispatch + Closed Loop
## Agent: Claude Code | Prioritet: P1
## PREDUVJET: CC_TASK_FAZA1_ARMATURA must be DONE

---

## TASK 3.1 — Heuristic-First Triage (zamjena za Haiku pozive)

`limit_connect_ai/triage_heuristic.py` — novi file:

3-tier model:
  TIER 1 (regex, 0 cost): keyword matching → signal_type + priority
  TIER 2 (rules, 0 cost): source URL + user context → routing
  TIER 3 (Haiku, cost):   samo kad T1+T2 confidence < 0.7 ili P1

Procijenjeno: 80% signala bez AI troška.

---

## TASK 3.2 — Smart Dispatch za Intervencije

`udruge/services/dispatch.py` — novi file:

score = (1/(dist+0.1))*0.5 + (1/(open_count+1))*0.3 + skill_match*0.2

Haversine distance između intervencije i field_workera GPS.
Celery task: auto_dispatch.delay(pk) na signal NOVO → DODIJELJENO.
WhatsApp notifikacija field_workeru pri dodjeli.

---

## TASK 3.3 — WhatsApp Closed Loop

FSMMixin._on_transition() hooks po modelu:
  WorkOrder invoiced   → notify company admin
  Intervencija RIJESENO → notify klijent
  FenixSignal DONE     → notify originator

Koristi existing core/whatsapp.py + WAHA session.

---

## TASK 3.4 — AI Budget Estimator (nizak prioritet, zadnje)

Lead → INTERNA_PROCJENA → Haiku procjena budgeta.
Prikaz na kartici: "AI est: X-Y EUR · 85%"
Async Celery task, ne blokira korisnika.
