# CC_TASK_FAZA2_HTMX — UI Fluidnost: HTMX + Drag&Drop + WO Kanban
## Agent: Claude Code | Prioritet: P1
## PREDUVJET: CC_TASK_FAZA1_ARMATURA mora biti DONE

---

## TASK 2.1 — HTMX u base.html

Dodaj ISPRED </head>:
```html
<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" 
        integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>
```

---

## TASK 2.2 — HTMX partial endpointi za Burzu

Novi endpoint: GET `/burza/kanban/col/<str:status>/`
Vraća HTML fragment s karticama za jednu kolonu.
HTMX polling 10s na svakoj koloni.

Dodaj u burza/urls.py:
  `path('kanban/col/<str:status>/', views.kanban_col, name='kanban_col')`

Dodaj u burza/views.py:
```python
@login_required
def kanban_col(request, status):
    company = get_user_company(request)
    leads = ProjectLead.objects.filter(company=company, status=status).order_by('-created_at')[:20]
    return render(request, 'burza/partials/kanban_col.html', {'leads': leads, 'status': status})
```

Stvori `templates/burza/partials/kanban_col.html`:
  Samo kartice — bez wrapper diva koji HTMX zamjenjuje.

---

## TASK 2.3 — Drag & Drop + FSM API endpoint

Novi endpoint: POST `/api/card/move/`
Body: { "model": "WorkOrder|ProjectLead", "pk": 1, "new_status": "in_progress" }
Poziva model.transition_to() — ako FSM odbije, vraća error JSON.

Frontend `sortable_kanban.js`:
```javascript
new Sortable(col, {
  group: 'kanban', animation: 150,
  ghostClass: 'kanban-ghost',
  onEnd(evt) {
    const { cardId, model } = evt.item.dataset;
    const newStatus = evt.to.dataset.status;
    fetch('/api/card/move/', {
      method: 'POST',
      headers: {'X-CSRFToken': CSRF(), 'Content-Type': 'application/json'},
      body: JSON.stringify({ model, pk: cardId, new_status: newStatus })
    })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) {
        // Vrati karticu natrag — FSM je odbio
        evt.from.insertBefore(evt.item, evt.from.children[evt.oldIndex] || null);
        showToast(d.error, 'error');
      }
    });
  }
});
```

---

## TASK 2.4 — Work Orders Kanban

Nova URL: `/work-orders/board/`
5 kolona: draft | in_progress | completed | invoiced | cancelled
Isti pattern kao Burza.

---

## TASK 2.5 — Unified Operations Dashboard

Nova URL: `/dashboard/operations/`
Tri sekcije:
1. SLA Alert bar (kartice iz StatusTimestamp koje prekoračuju limit)
2. Mini kanban: top 5 po sekciji (Intervencije / WO / Burza)
3. AI Digest (FenixSignal zadnjih 24h — count po tipu)
