# CC_TASK_BORG_CARDS_10_10 — Slaganje otvorenih karata
## Agent: Claude Code | Prioritet: P0
## Datum: 2026-03-28
## Izvor: Analiza CC#1 + Gemini integracija

**Status:** AKTIVAN — fazna implementacija
**Preduvjet:** FenixSignal model postoji, Celery beat radi, SW v8 aktivan

---

## FILOZOFIJA

```
SADA (6.2/10):  Skup tablica koje Ivan ručno dirigira
CILJ (10/10):   Autonomni operativni sustav sa središnjim živčanim sustavom
```

Tri stupa:
1. **Logička armatura** — state machine + SLA + audit trail
2. **UI fluidnost** — HTMX + Sortable.js + unified dashboard
3. **AI mozak** — heuristic-first triage, smart dispatch, closed loop

---

## FAZA 1: LOGIČKA ARMATURA (Temelj — bez ove faze ništa)
### Prioritet: P0 — radi se ODMAH

---

### TASK 1.1: FSM Mixin — Workflow State Machine

**Problem:** Burza/WO/Intervencije nemaju validaciju tranzicija. Korisnik može skočiti s NOVI_UPIT na RIJESENO.

**Rješenje:** Lightweight FSM mixin (NE django-fsm — pattern već postoji u invoice_service.py)

**Fajl:** `core/mixins/fsm.py` — NOVI

```python
class FSMMixin:
    STATUS_FIELD = 'status'
    TRANSITIONS = {}  # override in subclass

    def can_transition_to(self, new_status):
        current = getattr(self, self.STATUS_FIELD)
        allowed = self.TRANSITIONS.get(current, [])
        return new_status in allowed

    def transition_to(self, new_status, user=None):
        if not self.can_transition_to(new_status):
            current = getattr(self, self.STATUS_FIELD)
            raise ValueError(
                f'Nedozvoljena tranzicija: {current} → {new_status}. '
                f'Dozvoljeno: {self.TRANSITIONS.get(current, [])}'
            )
        old_status = getattr(self, self.STATUS_FIELD)
        setattr(self, self.STATUS_FIELD, new_status)
        self._on_transition(old_status, new_status, user)
        return old_status

    def _on_transition(self, old_status, new_status, user=None):
        """Override za custom logic (SLA, audit, notifications)."""
        pass
```

**Tranzicije po sustavu:**

```python
# ProjectLead
TRANSITIONS = {
    'NOVI_UPIT':        ['INTERNA_PROCJENA', 'NA_BURZI'],
    'INTERNA_PROCJENA': ['NA_BURZI', 'NOVI_UPIT'],
    'NA_BURZI':         ['PREUZETO'],
    'PREUZETO':         ['RIJESENO', 'NA_BURZI'],
    'RIJESENO':         [],  # terminal
}

# HitnaIntervencija
TRANSITIONS = {
    'NOVO':        ['DODIJELJENO'],
    'DODIJELJENO': ['NA_PUTU', 'NOVO'],      # NOVO = reassign
    'NA_PUTU':     ['NA_LOKACIJI'],
    'NA_LOKACIJI': ['RIJESENO', 'ESKALIRANO'],
    'RIJESENO':    ['FAKTURIRANO'],
    'ESKALIRANO':  ['RIJESENO'],
    'FAKTURIRANO': [],  # terminal
}

# WorkOrder
TRANSITIONS = {
    'draft':       ['in_progress', 'cancelled'],
    'in_progress': ['completed', 'cancelled', 'draft'],
    'completed':   ['invoiced', 'in_progress'],
    'invoiced':    [],  # terminal
    'cancelled':   ['draft'],  # reopen
}
```

---

### TASK 1.2: SLA Engine — Timestamp po statusu + Eskalacija

**Problem:** Nemoguće znati koliko karta stoji u nekom statusu.

**Fajl:** `core/models.py` — dodati

```python
class StatusTimestamp(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    status = models.CharField(max_length=30)
    entered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = 'sla_status_timestamp'
        ordering = ['-entered_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', '-entered_at']),
        ]
```

**SLA pravila (Celery task — svakih 5 min):**

```python
SLA_RULES = {
    'HitnaIntervencija': {
        'NOVO':        {'max_minutes': 15,   'escalate': 'sms_to_dispatcher'},
        'DODIJELJENO': {'max_minutes': 30,   'escalate': 'reassign_to_next'},
        'NA_PUTU':     {'max_minutes': 60,   'escalate': 'notify_ivan'},
    },
    'ProjectLead': {
        'NOVI_UPIT':        {'max_minutes': 1440, 'escalate': 'notify_ivan'},   # 24h
        'INTERNA_PROCJENA': {'max_minutes': 4320, 'escalate': 'auto_na_burzu'}, # 72h
    },
    'WorkOrder': {
        'in_progress': {'max_minutes': 480, 'escalate': 'notify_assigned'},     # 8h
    },
}
```

**Integracija:** FSMMixin._on_transition() automatski kreira StatusTimestamp + zatvara prethodni.

---

### TASK 1.3: CardActivity — Univerzalni Audit Trail

**Problem:** Intervencije i WO nemaju nikakav history. LeadActivity postoji samo za Burzu.

**Fajl:** `core/models.py` — dodati

```python
class CardActivity(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=200)
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'card_activity'
        ordering = ['-created_at']
```

**Template:** `templates/includes/card_timeline.html` — reusable za sve kartice

---

## FAZA 2: UI FLUIDNOST
### Prioritet: P1 — nakon Faze 1

---

### TASK 2.1: HTMX Integration

**base.html:** `<script src="https://unpkg.com/htmx.org@2.0.4"></script>`

Kanban kolone dobivaju HTMX polling:
```html
<div class="kanban-cards"
     hx-get="/burza/kanban/column/NOVI_UPIT/"
     hx-trigger="every 10s"
     hx-swap="innerHTML">
```

**Novi endpoint:** Partial HTML response za svaku kolonu.

---

### TASK 2.2: Drag & Drop — Sortable.js

**CDN:** `<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>`

```javascript
document.querySelectorAll('.kanban-cards').forEach(col => {
    new Sortable(col, {
        group: 'kanban',
        animation: 150,
        ghostClass: 'kanban-ghost',
        onEnd(evt) {
            const cardId = evt.item.dataset.cardId;
            const newStatus = evt.to.dataset.status;
            fetch(`/api/card/${cardId}/move/`, {
                method: 'POST',
                headers: {'X-CSRFToken': CSRF, 'Content-Type': 'application/json'},
                body: JSON.stringify({status: newStatus})
            }).then(r => r.json()).then(d => {
                if (!d.ok) {
                    // FSM rejected — animiraj karticu nazad
                    evt.from.insertBefore(evt.item, evt.from.children[evt.oldIndex]);
                    toast(d.error, 'error');
                }
            });
        }
    });
});
```

**Ključno:** Ako FSM odbije tranziciju → kartica se animira nazad u originalnu kolonu. Zero data corruption.

---

### TASK 2.3: Work Orders Kanban Board

**URL:** `/work-orders/board/`
**Template:** Isti pattern kao Burza — 5 kolona (draft, in_progress, completed, invoiced, cancelled)

---

### TASK 2.4: Unified Master Dashboard

**URL:** `/dashboard/operations/`

Jedna ploča, tri boje:
- Intervencije (aktivne, po SLA urgency) — crvene
- Work Orders (in_progress, po deadline) — plave
- Burza (NA_BURZI + NOVI_UPIT) — zelene

**Widgeti:**
1. SLA Alert bar — kartice koje probijaju SLA
2. Mini kanban za svaki sustav — top 5
3. AI Digest — signal summary 24h
4. Quick actions

---

## FAZA 3: AI MOZAK
### Prioritet: P1 — paralelno s Fazom 2

---

### TASK 3.1: Heuristic-First Triage (AI Cost Control)

**3-tier model:**
```
TIER 1 — Regex/Keyword (0 cost):
  "ne radi"/"error"/"500" → bug, P2
  "kako"/"gdje" → pitanje, P3
  "predlažem" → prijedlog, P4
  "hitno"/"SOS" → urgent, P1

TIER 2 — Rules (0 cost):
  POS source + "kasa" → cc_code, P2
  eRačun source → marija, P2
  page_url /pos/ → POS team
  repeated signal 1h → duplicate

TIER 3 — Haiku AI (cost):
  Samo kad T1+T2 confidence < 0.7
  Ili P1/P2 (critical path)
```

---

### TASK 3.2: Smart Dispatch za Intervencije

**Score = w1 * distance + w2 * workload + w3 * skill**

```python
def smart_dispatch(intervention):
    workers = available_field_workers(intervention.company)
    scored = []
    for w in workers:
        dist = gps_distance(intervention, w)  # Haversine
        open_count = w.open_interventions_count
        skill_match = category_match(intervention.category, w)
        score = (1/(dist+0.1))*0.5 + (1/(open_count+1))*0.3 + skill_match*0.2
        scored.append((w, score))
    scored.sort(key=lambda x: -x[1])
    return scored[0][0] if scored else None
```

**Celery:** auto_dispatch.delay(pk) kad Intervencija = NOVO

---

### TASK 3.3: WhatsApp Closed Loop

FSMMixin._on_transition() kad terminal status:
- FenixSignal → in-app notifikacija korisniku
- Intervencija → WhatsApp klijentu
- WO → notifikacija assigned useru

---

### TASK 3.4: AI Budget Estimator za Burzu

Kad Lead → INTERNA_PROCJENA:
- Haiku procjenjuje budget iz kategorije + lokacije + opisa
- Prikazuje na kartici: "AI: X-Y EUR (85%)"

---

## FAZA 4: OFFLINE + POLISH
### Prioritet: P2

---

### TASK 4.1: Offline Intervencije

SW v8 proširenje: `pending_status_updates` IDB store za Intervencije field view.

### TASK 4.2: Keyboard Shortcuts

N=nova, 1-5=kolona, J/K=navigacija, Enter=detalji, Esc=zatvori

---

## GEMINIJEVA KOREKCIJA — INTEGRIRANA

| Gemini rekao | Naš odgovor |
|---|---|
| django-fsm | Vlastiti FSMMixin — lakši, bez dependency |
| HTMX + Alpine.js | Samo HTMX — Alpine nepotreban |
| Full WebSocket | HTMX polling 10s za Burzu/WO, WS samo za GPS |
| Offline-first | SW v8 proširenje — infrastruktura postoji |
| Local LLM | Heuristic T1+T2 pokriva 70-80% besplatno |
| Audit trail | CardActivity + ContentType — generički |

---

## DEFINICIJA 10/10

- [ ] Nijedan status se ne može preskočiti — FSM brani
- [ ] SLA alarm za kartice koje predugo stoje
- [ ] Svaka promjena = neizbrisiv CardActivity trag
- [ ] Drag-and-drop na sve 3 kanban ploče
- [ ] HTMX polling — promjene bez refresha
- [ ] Work Orders kanban ploča
- [ ] Unified operations dashboard
- [ ] Heuristic-first triage (90% besplatno)
- [ ] Smart dispatch za intervencije (GPS + workload)
- [ ] WhatsApp closed loop
- [ ] Offline intervencije
- [ ] AI budget estimator za Burzu
