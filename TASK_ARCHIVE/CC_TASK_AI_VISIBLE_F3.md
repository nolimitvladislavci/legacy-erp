# CC_TASK_AI_VISIBLE_F3 — AI postaje vidljiv korisniku
**Dodjeljeno:** CC Code
**Prioritet:** 🟠 Prodajni argument — korisnik mora vidjeti AI
**Datum:** 02.04.2026

---

## KONTEKST — Stvarno stanje (izmjereno)

```
AI audit trail u templateima: 1 jedino mjesto
AI radi u pozadini (konto, signal, OCR) ali korisnik to ne vidi
Korisnik ne zna da BORG AI postoji dok ne pita
```

Gemini Dron #3 je točan: "Nevidljiva magija nije prodajni argument."

Cilj: Svaka AI akcija mora biti vidljiva, pregledna i povjerljiva.
Povjerenje = vidljivost + mogućnost revizije.

---

## ZADATAK F3a — Fenix AI Badge templatetag

### Kreiraj: `core/templatetags/fenix_ai.py`

```python
from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def ai_badge(action, confidence=None, model=None, review_url=None):
    """
    Prikazuje vizualnu značku da je AI napravio ovu akciju.
    
    Korištenje:
      {% load fenix_ai %}
      {% ai_badge "Proknjiženo" confidence=99 model="BORG AI" %}
      {% ai_badge "Klasificirano" review_url=request.path %}
    
    Rezultat:
      🤖 Proknjiženo od BORG AI (99%) [Revidiraj]
    """
    conf_html = ''
    if confidence:
        conf_html = format_html(
            '<span class="fenix-ai-confidence">({}%)</span>', confidence
        )
    
    review_html = ''
    if review_url:
        review_html = format_html(
            '<a href="{}" class="fenix-ai-review-link">Revidiraj</a>', review_url
        )
    
    model_name = model or 'BORG AI'
    
    return format_html(
        '<span class="fenix-ai-action">'
        '<span class="ai-icon">&#x1F916;</span>'
        '{} od {} {} {}'
        '</span>',
        action, model_name, conf_html, review_html
    )

@register.simple_tag
def ai_status_pill(status):
    """
    Status pill za AI akcije: pending, processing, done, failed.
    {% ai_status_pill "done" %}
    """
    icons = {'pending': '⏳', 'processing': '⚙️', 'done': '✓', 'failed': '✗'}
    colors = {
        'pending':    ('rgba(245,158,11,.1)', '#d97706'),
        'processing': ('rgba(59,130,246,.1)', '#2563eb'),
        'done':       ('rgba(34,197,94,.1)',  '#16a34a'),
        'failed':     ('rgba(239,68,68,.1)',  '#dc2626'),
    }
    bg, color = colors.get(status, colors['pending'])
    icon = icons.get(status, '?')
    return format_html(
        '<span style="background:{};color:{};padding:.15rem .5rem;'
        'border-radius:12px;font-size:.7rem;font-weight:600;">{} {}</span>',
        bg, color, icon, status
    )
```

---

## ZADATAK F3b — AI akcije u konto/ai_bookkeeper.py

`konto/ai_bookkeeper.py` je 497 linija. Kad AI proknjiži fakturu, treba
sačuvati zapis o akciji.

### Dodati model AIAction u konto/models.py (ili limit_connect_ai/models.py):

```python
class AIAction(models.Model):
    """Svaka automatska AI akcija vidljiva korisniku."""
    ACTION_TYPES = [
        ('booking',      'Automatsko knjiženje'),
        ('classification', 'Klasifikacija dokumenta'),
        ('ocr',          'OCR ekstrakcija'),
        ('signal',       'BORG signal trijage'),
        ('recommendation', 'AI preporuka'),
    ]
    company         = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    action_type     = models.CharField(max_length=30, choices=ACTION_TYPES)
    description     = models.CharField(max_length=200)
    confidence      = models.PositiveIntegerField(null=True, blank=True)  # 0-100
    ai_model        = models.CharField(max_length=50, default='BORG AI')
    source_object   = models.CharField(max_length=200, blank=True)  # "Invoice #123"
    result_object   = models.CharField(max_length=200, blank=True)  # "JournalEntry #456"
    is_reviewed     = models.BooleanField(default=False)
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL,
                        null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI akcija'
```

---

## ZADATAK F3c — AI Dashboard widget

### Kreirati: `templates/ai_assistant/partials/ai_activity_widget.html`

Koristiti ovaj widget na invoice detalju, konto dashboardu i BORG hubs:

```html
{% load fenix_ai %}
<div class="fenix-card" style="border-left: 3px solid rgba(139,92,246,.4);">
  <div class="fenix-card-header">
    <span class="fenix-label">🤖 BORG AI aktivnost</span>
    <span class="fenix-badge fenix-badge-ai">{{ actions|length }} akcija</span>
  </div>
  {% for action in actions %}
  <div style="display:flex;justify-content:space-between;align-items:center;
              padding:.5rem 0;border-bottom:1px solid var(--border-light);">
    <div>
      <div style="font-size:.82rem;color:var(--text);">{{ action.description }}</div>
      <div style="font-size:.72rem;color:var(--text-muted);">
        {{ action.created_at|timesince }} · {{ action.ai_model }}
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:.5rem;">
      {% if action.confidence %}
        <span class="fenix-badge fenix-badge-ai">{{ action.confidence }}%</span>
      {% endif %}
      {% ai_status_pill action.is_reviewed|yesno:"done,pending" %}
      {% if not action.is_reviewed %}
      <button hx-post="{% url 'ai:review_action' action.id %}"
              hx-target="closest div"
              hx-swap="outerHTML"
              class="fenix-btn fenix-btn-ghost fenix-btn-sm">
        Revidiraj
      </button>
      {% endif %}
    </div>
  </div>
  {% empty %}
  <div class="fenix-empty">
    <p>AI još nije poduzeo akciju. Kad proknjiži ili klasificira dokument, vidjet ćeš ovdje.</p>
  </div>
  {% endfor %}
</div>
```

---

## ZADATAK F3d — Ugradi widget na 3 ključna mjesta

### 1. Invoice detail page:
```html
{% with actions=invoice.company|ai_actions_for:"invoice" %}
  {% include "ai_assistant/partials/ai_activity_widget.html" %}
{% endwith %}
```

### 2. Konto dashboard (nakon journalEntry tablice)

### 3. BORG Hub / Cockpit

---

## ZADATAK F3e — AI Onboarding moment (WOW efekt)

Kad korisnik prvi put uploada dokument i AI ga automatski obradi:

```html
<!-- templates/smart_import/success.html -->
<div class="fenix-card" style="text-align:center;padding:2rem;">
  <div style="font-size:3rem;margin-bottom:1rem;">🤖</div>
  <h2 class="fenix-title">BORG AI je uvezao vaše podatke</h2>
  <p class="fenix-subtitle">{{ imported_count }} stavki automatski prepoznato i uvezeno</p>
  
  <div style="margin:1.5rem 0;padding:1rem;background:rgba(139,92,246,.08);
              border-radius:8px;border:1px solid rgba(139,92,246,.2);">
    <div class="fenix-label" style="color:#7c3aed;">Što je AI napravio</div>
    <div style="margin-top:.5rem;font-size:.85rem;color:var(--text);">
      Prepoznao {{ item_count }} artikala · Mapirao {{ partner_count }} partnera ·
      Predložio {{ category_count }} kategorija
    </div>
  </div>
  
  <a href="{{ review_url }}" class="fenix-btn fenix-btn-primary">
    Pregledaj i potvrdi →
  </a>
</div>
```

---

## MJERLJIVI CILJ:
```bash
# Prije: 1 AI badge u templateima
# Nakon F3: cilj > 20 mjesta gdje korisnik vidi AI akciju
grep -r "fenix-ai-action\|ai_badge\|BORG AI" /var/www/fina-connect/templates | wc -l
```

## GIT:
```bash
git add core/templatetags/fenix_ai.py konto/models.py \
        templates/ai_assistant/ limit_connect_ai/models.py
git commit -m "feat(ai-ux): AI postaje vidljiv — badge, audit trail, activity widget"
```
