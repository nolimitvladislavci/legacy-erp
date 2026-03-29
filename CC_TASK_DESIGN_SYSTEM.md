# CC_TASK_DESIGN_SYSTEM.md
# Dodijeljen: CC Code (server + lokalno)
# Prioritet: VISOK — Krater #3
# Datum: 2026-03-28
# Procjena: 2h
# Napomena: Gradi KROZ experiences — ne u vakuumu. Svaki partial odmah se koristi.
#
# FILOZOFIJA: Ne radimo novi CSS framework.
# Radimo 6 Django template partialsa koji enkapsuliraju ponavljajuće UI patterne.
# Svaki dashboard koji ih koristi dobiva konzistentnost gratis.

---

## PARTIAL 1: templates/partials/_stat_card.html

Najkorišteniji element u cijelom sustavu. Svaki dashboard ima 3-4 stat karte.

```html
{# Poziv: {% include "partials/_stat_card.html" with icon="fas fa-users" color="text-primary" label="Ukupno klijenata" value=stats.total sub="firmi u sustavu" %} #}
<div class="col">
  <div class="card bg-dark border-secondary h-100">
    <div class="card-body d-flex align-items-center gap-3 py-3">
      <div class="rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
           style="width:48px;height:48px;background:rgba(255,255,255,.05)">
        <i class="{{ icon|default:'fas fa-chart-bar' }} {{ color|default:'text-primary' }} fs-5"></i>
      </div>
      <div class="flex-grow-1 min-w-0">
        <div class="text-muted small">{{ label }}</div>
        <div class="fs-4 fw-bold text-white lh-1 mt-1">{{ value|default:"—" }}</div>
        {% if sub %}<div class="text-muted" style="font-size:.75rem">{{ sub }}</div>{% endif %}
      </div>
    </div>
  </div>
</div>
```

Parametri: icon (FA klasa), color (text-* klasa), label (string), value (broj/string), sub (podnaslov, opcionalno)

---

## PARTIAL 2: templates/partials/_stat_grid.html

Wraps 3-4 _stat_card-a u Bootstrap grid row.

```html
{# Poziv: {% include "partials/_stat_grid.html" with cards=stat_cards_list %} #}
{# cards = lista dicta: [{icon, color, label, value, sub}, ...] #}
<div class="row row-cols-1 row-cols-sm-2 row-cols-lg-{{ cards|length|default:4 }} g-3 mb-4">
  {% for card in cards %}
    {% include "partials/_stat_card.html" with icon=card.icon color=card.color label=card.label value=card.value sub=card.sub %}
  {% endfor %}
</div>
```

Alternativni poziv (inline, za module koji sami definiraju karte):
```html
<div class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3 mb-4">
  {% include "partials/_stat_card.html" with icon="fas fa-mountain" color="text-warning" label="Iskustva" value=stats.ukupno %}
  {% include "partials/_stat_card.html" with icon="fas fa-calendar-check" color="text-success" label="Aktivnih" value=stats.aktivnih %}
  {% include "partials/_stat_card.html" with icon="fas fa-star" color="text-warning" label="Prosj. ocjena" value=stats.avg_rating|floatformat:1 sub="od 5.0" %}
</div>
```

---

## PARTIAL 3: templates/partials/_kanban_column.html

Za Kanban prikaz statusa — BORG Hub, work_orders, borg_ops.

```html
{# Poziv: {% include "partials/_kanban_column.html" with col_title="U tijeku" col_color="#f59e0b" col_icon="fas fa-spinner" items=in_progress_items card_template="work_orders/_kanban_card.html" %} #}
<div class="kanban-col flex-shrink-0" style="width:280px">
  <div class="kanban-col-header d-flex align-items-center gap-2 px-3 py-2 rounded-top"
       style="background:{{ col_color|default:'#3b82f6' }}22; border-top:3px solid {{ col_color|default:'#3b82f6' }}">
    <i class="{{ col_icon|default:'fas fa-circle' }}" style="color:{{ col_color }}"></i>
    <span class="fw-semibold small text-white">{{ col_title }}</span>
    <span class="badge ms-auto rounded-pill" style="background:{{ col_color }}">{{ items|length }}</span>
  </div>
  <div class="kanban-col-body p-2 d-flex flex-column gap-2 bg-dark border border-secondary border-top-0 rounded-bottom"
       style="min-height:200px;max-height:70vh;overflow-y:auto">
    {% for item in items %}
      {% include card_template with item=item %}
    {% empty %}
      <div class="text-center text-muted py-4" style="font-size:.8rem">
        <i class="fas fa-inbox mb-2 d-block fs-4"></i>Prazno
      </div>
    {% endfor %}
  </div>
</div>
```

CSS koji mora biti u base.html (ili dodan u static):
```css
.kanban-board { display:flex; gap:16px; overflow-x:auto; padding-bottom:16px; }
.kanban-board::-webkit-scrollbar { height:6px; }
.kanban-board::-webkit-scrollbar-track { background:#1e293b; }
.kanban-board::-webkit-scrollbar-thumb { background:#475569; border-radius:3px; }
```

---

## PARTIAL 4: templates/partials/_timeline.html

Za prikaz CardActivity / audit trail na detail stranicama.

```html
{# Poziv: {% include "partials/_timeline.html" with activities=card_activities %} #}
<div class="timeline">
  {% for act in activities %}
  <div class="timeline-item d-flex gap-3 mb-3">
    <div class="timeline-dot flex-shrink-0 d-flex align-items-start pt-1">
      <div class="rounded-circle bg-secondary d-flex align-items-center justify-content-center"
           style="width:28px;height:28px">
        <i class="fas fa-circle-dot text-primary" style="font-size:.6rem"></i>
      </div>
    </div>
    <div class="flex-grow-1">
      <div class="card bg-dark border-secondary p-2">
        <div class="d-flex justify-content-between align-items-start">
          <span class="small text-white">{{ act.action }}</span>
          <span class="text-muted" style="font-size:.7rem;white-space:nowrap">{{ act.created_at|timesince }} ago</span>
        </div>
        {% if act.old_value or act.new_value %}
        <div class="mt-1" style="font-size:.75rem">
          {% if act.old_value %}<span class="text-danger text-decoration-line-through">{{ act.old_value }}</span> → {% endif %}
          {% if act.new_value %}<span class="text-success">{{ act.new_value }}</span>{% endif %}
        </div>
        {% endif %}
        {% if act.note %}<div class="text-muted mt-1" style="font-size:.75rem">{{ act.note }}</div>{% endif %}
        {% if act.user %}<div class="text-muted mt-1" style="font-size:.7rem"><i class="fas fa-user me-1"></i>{{ act.user.get_full_name|default:act.user.username }}</div>{% endif %}
      </div>
    </div>
  </div>
  {% empty %}
  <div class="text-center text-muted py-3">
    <i class="fas fa-history mb-1 d-block"></i><small>Nema aktivnosti</small>
  </div>
  {% endfor %}
</div>
```

---

## PARTIAL 5: templates/partials/_empty_state.html

Poboljšana verzija postojećeg empty_state.html (standardizirana).

```html
{# Poziv: {% include "partials/_empty_state.html" with icon="fas fa-mountain" title="Nema iskustava" sub="Kreirajte prvu turističku aktivnost" cta_url=cta_url cta_label="Novo iskustvo" %} #}
<div class="text-center py-5 text-muted">
  <div class="mb-3">
    <i class="{{ icon|default:'fas fa-inbox' }}" style="font-size:3rem;opacity:.3"></i>
  </div>
  <h6 class="text-white-50 mb-1">{{ title|default:"Nema podataka" }}</h6>
  {% if sub %}<p class="small mb-3">{{ sub }}</p>{% endif %}
  {% if cta_url %}
  <a href="{{ cta_url }}" class="btn btn-sm btn-outline-primary">
    <i class="fas fa-plus me-1"></i>{{ cta_label|default:"Dodaj" }}
  </a>
  {% endif %}
</div>
```

---

## PARTIAL 6: templates/partials/_page_header.html

Standardizira header svake stranice (naslov + CTA gumb + breadcrumb).

```html
{# Poziv: {% include "partials/_page_header.html" with icon="fas fa-mountain" title="Iskustva" subtitle="Agro-Turizam 360" cta_url=cta_url cta_label="Novo iskustvo" cta_icon="fas fa-plus" %} #}
<div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
  <div>
    <h4 class="mb-0 text-white">
      {% if icon %}<i class="{{ icon }} me-2 {% if icon_color %}{{ icon_color }}{% else %}text-warning{% endif %}"></i>{% endif %}
      {{ title }}
    </h4>
    {% if subtitle %}<div class="text-muted small mt-1">{{ subtitle }}</div>{% endif %}
  </div>
  {% if cta_url %}
  <a href="{{ cta_url }}" class="btn btn-sm btn-warning">
    <i class="{{ cta_icon|default:'fas fa-plus' }} me-1"></i>{{ cta_label|default:"Novo" }}
  </a>
  {% endif %}
</div>
```

---

## PRIMJENA NA EXPERIENCES TEMPLATES

Nakon što su partialsi kreirani, refaktorirati svih 12 experiences templatea da ih koriste:

```html
{# U experience_list.html zamijeni inline header s: #}
{% include "partials/_page_header.html" with icon="fas fa-mountain" title="Iskustva / Aktivnosti" subtitle="Agro-Turizam 360" cta_url=experiences:experience_create|url cta_label="Novo iskustvo" %}

{# Stat karte: #}
<div class="row row-cols-1 row-cols-sm-3 g-3 mb-4">
  {% include "partials/_stat_card.html" with icon="fas fa-mountain" color="text-warning" label="Ukupno iskustava" value=stats.ukupno %}
  {% include "partials/_stat_card.html" with icon="fas fa-check-circle" color="text-success" label="Aktivnih" value=stats.aktivnih %}
  {% include "partials/_stat_card.html" with icon="fas fa-star" color="text-warning" label="Prosj. ocjena" value=stats.avg_rating|floatformat:1 sub="od 5.0" %}
</div>
```

---

## VERIFIKACIJA

```bash
ls /var/www/fina-connect/templates/partials/

# Provjeri da su partialsi valjani Django template (no syntax errors):
cd /var/www/fina-connect && source venv/bin/activate
python manage.py shell -c "
from django.template.loader import get_template
partials = ['_stat_card', '_stat_grid', '_kanban_column', '_timeline', '_empty_state', '_page_header']
for p in partials:
    try:
        t = get_template(f'partials/{p}.html')
        print(f'OK: {p}')
    except Exception as e:
        print(f'ERR {p}: {e}')
"

git add templates/partials/
git commit -m "feat(design-system): 6 reusable partials — stat_card, stat_grid, kanban_column, timeline, empty_state, page_header"
```

---
# STATUS: READY_FOR_CC_CODE
# Sljedeći task: CC_TASK_BORG_HUB.md
