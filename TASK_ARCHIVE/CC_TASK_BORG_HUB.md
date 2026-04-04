# CC_TASK_BORG_HUB.md
# Dodijeljen: CC Code (server + lokalno)
# Prioritet: VISOK — Krater #2
# Datum: 2026-03-28
# Procjena: 3h
# Preduvjet: CC_TASK_DESIGN_SYSTEM.md mora biti DONE (partialsi moraju postojati)
#
# KONTEKST: BORG nema "krov". Operations dashboard postoji ali nije command center.
# BORG Hub = jedan URL gdje BORG operater vidi SVE: work_orders, interventions,
# borg_ops dispatch, experiences bookings, burza, alerts — sve u jednom kanban/alert prikazu.
#
# URL: /borg/hub/  (novi view u borg_ops/views.py ili nova borg_hub app)
# Template: templates/borg_ops/hub.html

---

## KORAK 1 — Čitaj postojeće modele OBVEZNO

```bash
# Provjeri što postoji u borg_ops
grep -n "class.*Model" /var/www/fina-connect/borg_ops/models.py
grep -n "def " /var/www/fina-connect/borg_ops/views.py | head -30
cat /var/www/fina-connect/borg_ops/urls.py
```

```bash
# Provjeri work_orders modele
grep -n "class.*Model\|status.*=\|STATUS_CHOICES" /var/www/fina-connect/work_orders/models.py | head -30
```

```bash
# Provjeri experiences booking statuse
grep -n "STATUS_CHOICES\|status" /var/www/fina-connect/experiences/models.py | head -20
```

```bash
# Provjeri burza modele
grep -n "class.*Model\|status" /var/www/fina-connect/burza/models.py | head -20
```

## KORAK 2 — Novi view u borg_ops/views.py (ili dodaj novi fajl borg_hub_views.py)

```python
# Dodati na kraju borg_ops/views.py ili u borg_ops/hub_views.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

@login_required
def borg_hub(request):
    """
    BORG Hub — Cross-module command center.
    Jedan prikaz za sve module u real-time.
    Requires: login (svi autorizirani korisnici koji imaju BORG pristup)
    """
    from core.company_utils import get_user_company
    company = get_user_company(request)
    now = timezone.now()
    today = now.date()
    
    # ── WORK ORDERS ──────────────────────────────────────
    try:
        from work_orders.models import WorkOrder
        wo_qs = WorkOrder.objects.filter(company=company)
        work_orders = {
            'draft':       list(wo_qs.filter(status='draft').select_related('client')[:10]),
            'in_progress': list(wo_qs.filter(status='in_progress').select_related('client')[:10]),
            'completed':   list(wo_qs.filter(status='completed', date=today).select_related('client')[:5]),
        }
        wo_stats = {
            'open': wo_qs.filter(status__in=['draft','in_progress']).count(),
            'completed_today': wo_qs.filter(status='completed', date=today).count(),
        }
    except Exception:
        work_orders = {}
        wo_stats = {}
    
    # ── BORG OPS (CardActivity, SLA alerts) ───────────────
    try:
        from borg_ops.models import CardActivity
        recent_activity = CardActivity.objects.order_by('-created_at')[:20]
    except Exception:
        recent_activity = []
    
    # ── EXPERIENCES BOOKINGS ──────────────────────────────
    try:
        from experiences.models import ExperienceBooking, ExperienceSchedule
        # Termini danas i sutra
        upcoming_schedules = ExperienceSchedule.objects.filter(
            experience__company=company,
            date__gte=today,
            date__lte=today + timedelta(days=7),
            status='open'
        ).select_related('experience').order_by('date', 'time_from')[:10]
        
        pending_bookings = ExperienceBooking.objects.filter(
            schedule__experience__company=company,
            status='pending'
        ).select_related('schedule__experience')[:10]
        
        exp_stats = {
            'upcoming': upcoming_schedules.count(),
            'pending_payment': pending_bookings.count(),
        }
    except Exception:
        upcoming_schedules = []
        pending_bookings = []
        exp_stats = {}
    
    # ── BURZA ─────────────────────────────────────────────
    try:
        from burza.models import BurzaOglas  # provjeri stvarno ime modela!
        burza_active = BurzaOglas.objects.filter(company=company, status='active')[:5]
    except Exception:
        burza_active = []
    
    # ── ALERTS / FENIX SIGNALS ────────────────────────────
    try:
        from core.models import FenixSignal
        alerts = FenixSignal.objects.filter(
            company=company,
            resolved=False
        ).order_by('-priority', '-created_at')[:5]
    except Exception:
        alerts = []
    
    # ── INVOICING (neplaćeni) ─────────────────────────────
    try:
        from invoicing.models import Invoice
        unpaid_invoices = Invoice.objects.filter(
            company=company,
            status__in=['sent', 'overdue']
        ).order_by('due_date')[:8]
        overdue_count = Invoice.objects.filter(
            company=company,
            status='overdue'
        ).count()
    except Exception:
        unpaid_invoices = []
        overdue_count = 0
    
    # ── POS (danas) ───────────────────────────────────────
    try:
        from pos.models import POSReceipt  # provjeri stvarno ime
        pos_today_count = POSReceipt.objects.filter(
            company=company,
            created_at__date=today
        ).count()
    except Exception:
        pos_today_count = 0
    
    context = {
        'work_orders': work_orders,
        'wo_stats': wo_stats,
        'recent_activity': recent_activity,
        'upcoming_schedules': upcoming_schedules,
        'pending_bookings': pending_bookings,
        'exp_stats': exp_stats,
        'burza_active': burza_active,
        'alerts': alerts,
        'unpaid_invoices': unpaid_invoices,
        'overdue_count': overdue_count,
        'pos_today_count': pos_today_count,
        'now': now,
        'today': today,
    }
    return render(request, 'borg_ops/hub.html', context)
```

NAPOMENA: Za svaki import koji ne radi (model ne postoji pod tim imenom), zakomentirati blok i nastaviti.
Koristiti try/except za SVE externe module — Hub mora raditi čak i ako neki modul ima grešku.

## KORAK 3 — Dodaj URL u borg_ops/urls.py

```python
# U urlpatterns liste borg_ops/urls.py dodati:
path('hub/', views.borg_hub, name='borg_hub'),
# ili ako je odvojeni fajl:
from . import hub_views
path('hub/', hub_views.borg_hub, name='borg_hub'),
```

Provjeri kako je borg_ops uključen u main urls.py:
```bash
grep -n "borg_ops" /var/www/fina-connect/fina_connect/urls.py
```

## KORAK 4 — Template: templates/borg_ops/hub.html

```
LAYOUT BORG HUB:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HEADER: "⬡ BORG Hub — Command Center"  [datum/vrijeme, auto-refresh 60s]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP ALERT ROW (ako postoje alerts — crveni banner):
 "🚨 {N} aktivnih upozorenja"  [lista alerts, dismiss per alert]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUICK STATS (6 stat_card-a u row):
 Radni nalozi otvoreni | WO završeni danas | POS transakcija danas |
 Exp. termina ovaj tjedan | Čeka uplatu depozita | Faktura overdue
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAIN CONTENT (2 kolone):
 LIJEVO (col-lg-8):
   [Tab 1: Radni Nalozi Kanban]
     3 kolumne: Nacrt | U tijeku | Završeni danas
     Koristiti _kanban_column.html partial
     Card za WO: br. naloga, klijent, prioritet badge, link
   [Tab 2: Experiences]
     Nadolazeći termini (7 dana) — tablica
     Rezervacije čekaju uplatu — tablica s confirm gumbima
   [Tab 3: Financije]
     Neplaćene fakture sortirane po dospijeću
     Badge danger za overdue

 DESNO (col-lg-4):
   [Aktivnost — Live Feed]
     Koristiti _timeline.html partial
     CardActivity — zadnjih 20 akcija u sustavu
     Auto-refresh svakih 30s (meta refresh ili JS)
   [Brze akcije]
     Btn "Novi WO" | "Nova rezervacija" | "Novi račun" | "POS"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOOTER: "Zadnje osvježenje: {now}" [auto-refresh JS countdown]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Auto-refresh JS (na dnu template-a):
```javascript
// Osvježi stranicu svakih 60 sekundi
let countdown = 60;
const timer = setInterval(() => {
    countdown--;
    const el = document.getElementById('refresh-countdown');
    if (el) el.textContent = countdown + 's';
    if (countdown <= 0) { clearInterval(timer); location.reload(); }
}, 1000);
```

## KORAK 5 — Dodaj u Sidebar

```bash
grep -n "borg\|BORG\|hub" /var/www/fina-connect/templates/base.html | head -20
```

Naći sekciju sidebar-a gdje su BORG linkovi i dodati:
```html
<a href="{% url 'borg_ops:borg_hub' %}" class="{% if request.resolver_match.url_name == 'borg_hub' %}active{% endif %}">
  <i class="fas fa-globe"></i> BORG Hub
</a>
```
Staviti kao PRVI link u BORG sekciji sidebar-a.

## VERIFIKACIJA

```bash
cd /var/www/fina-connect && source venv/bin/activate

# Check URL resolves
python manage.py shell -c "
from django.urls import reverse
try:
    url = reverse('borg_ops:borg_hub')
    print(f'URL OK: {url}')
except Exception as e:
    print(f'URL ERROR: {e}')
"

# Restart i test
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/borg/hub/ 2>/dev/null || echo "needs auth (expected)"

git add .
git commit -m "feat(borg-hub): BORG command center — cross-module dashboard s kanban, timeline, alerts"
git log --oneline -3
```

---
# STATUS: READY_FOR_CC_CODE (after CC_TASK_DESIGN_SYSTEM is DONE)
# Sljedeći task: BORG_SIMULATION_MASTER.md
