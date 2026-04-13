"""
BORG Hub — nadogradnja operations_dashboard u pravi command center
+ Experiences, Inventory, Financije, HTMX auto-refresh
+ Sidebar link
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# 1. VIEW — dodaj experiences, inventory, financije u kontekst
# ══════════════════════════════════════════════════════════════════════
path = os.path.join(BASE, 'borg_ops/views.py')
with open(path) as f:
    c = f.read()

old_return = """    return render(request, 'borg_ops/operations_dashboard.html', {
        'sla_alerts': sorted(sla_alerts, key=lambda x: -x['minutes']),
        'interventions': interventions_active,
        'work_orders': wo_active,
        'leads': leads_open,
        'signal_stats': signal_stats,
        'now': now,
    })"""

new_return = """    # ── Experiences — danas ──
    exp_today = {'schedules': 0, 'bookings': 0, 'no_shows': 0, 'revenue': 0}
    try:
        from experiences.models import ExperienceSchedule, ExperienceBooking
        today = now.date()
        today_scheds = ExperienceSchedule.objects.filter(date=today)
        exp_today['schedules'] = today_scheds.count()
        today_bookings = ExperienceBooking.objects.filter(
            schedule__date=today
        )
        exp_today['bookings'] = today_bookings.count()
        exp_today['no_shows'] = today_bookings.filter(status='no_show').count()
        from django.db.models import Sum
        exp_today['revenue'] = today_bookings.filter(
            status__in=['completed', 'checked_in']
        ).aggregate(s=Sum('price_total'))['s'] or 0
    except DatabaseError:
        pass

    # ── Inventory alerts ──
    inv_alerts = {'low_stock': 0, 'karenca': 0, 'expiring': 0, 'items': []}
    try:
        from inventory.models import InventoryItem, StockBatch
        low = InventoryItem.objects.filter(
            is_active=True, quantity__lte=models.F('min_quantity'),
            min_quantity__gt=0,
        )[:5]
        inv_alerts['low_stock'] = low.count()
        inv_alerts['items'] = list(low.values_list('name', flat=True))

        # Karenca
        karenca_items = InventoryItem.objects.filter(
            source_flock__isnull=False, is_active=True,
        )
        karenca_count = 0
        for item in karenca_items:
            if item.source_flock and item.source_flock.has_active_karenca:
                karenca_count += 1
        inv_alerts['karenca'] = karenca_count

        # Expiring batches (7 days)
        from datetime import timedelta
        week = today + timedelta(days=7)
        inv_alerts['expiring'] = StockBatch.objects.filter(
            expiry_date__lte=week, expiry_date__gte=today,
            quarantine_status='active',
        ).count()
    except DatabaseError:
        pass

    # ── Financijski pulse ──
    fin_pulse = {'today_revenue': 0, 'unpaid': 0, 'overdue': 0}
    try:
        from invoicing.models import Invoice
        today_invoices = Invoice.objects.filter(
            date_issued=today, status__in=['CONFIRMED', 'FISCALIZED', 'SENT'],
        )
        fin_pulse['today_revenue'] = today_invoices.aggregate(
            s=Sum('total'))['s'] or 0
        fin_pulse['unpaid'] = Invoice.objects.filter(
            status__in=['CONFIRMED', 'FISCALIZED', 'SENT'],
        ).exclude(total=0).count()
    except DatabaseError:
        pass

    return render(request, 'borg_ops/operations_dashboard.html', {
        'sla_alerts': sorted(sla_alerts, key=lambda x: -x['minutes']),
        'interventions': interventions_active,
        'work_orders': wo_active,
        'leads': leads_open,
        'signal_stats': signal_stats,
        'exp_today': exp_today,
        'inv_alerts': inv_alerts,
        'fin_pulse': fin_pulse,
        'now': now,
    })"""

c = c.replace(old_return, new_return)

# Dodaj models import ako fali
if 'from django.db import models' not in c:
    c = c.replace('from django.utils import timezone', 
                  'from django.db import models\nfrom django.utils import timezone')

with open(path, 'w') as f:
    f.write(c)
print("[OK] borg_ops/views.py — dodane Experiences, Inventory, Financije sekcije")


# ══════════════════════════════════════════════════════════════════════
# 2. TEMPLATE — dodaj nove sekcije + HTMX auto-refresh
# ══════════════════════════════════════════════════════════════════════
path = os.path.join(BASE, 'borg_ops/templates/borg_ops/operations_dashboard.html')
with open(path) as f:
    c = f.read()

# Zamijeni stats-row da uključuje nove metrike
old_stats = """<!-- Stats -->
<div class="stats-row">
    <div class="stat-mini {% if sla_alerts %}red{% endif %}">
        <div class="val">{{ sla_alerts|length }}</div>
        <div class="lbl">{% trans "SLA kršenja" %}</div>
    </div>
    <div class="stat-mini">
        <div class="val">{{ interventions|length }}</div>
        <div class="lbl">{% trans "Aktivne intervencije" %}</div>
    </div>
    <div class="stat-mini">
        <div class="val">{{ work_orders|length }}</div>
        <div class="lbl">{% trans "Otvoreni nalozi" %}</div>
    </div>
    <div class="stat-mini gold">
        <div class="val">{{ signal_stats.total }}</div>
        <div class="lbl">{% trans "Signali 24h" %}</div>
    </div>
</div>"""

new_stats = """<!-- Stats -->
<div class="stats-row" style="grid-template-columns:repeat(8,1fr)">
    <div class="stat-mini {% if sla_alerts %}red{% endif %}">
        <div class="val">{{ sla_alerts|length }}</div>
        <div class="lbl">{% trans "SLA" %}</div>
    </div>
    <div class="stat-mini">
        <div class="val">{{ interventions|length }}</div>
        <div class="lbl">{% trans "Intervencije" %}</div>
    </div>
    <div class="stat-mini">
        <div class="val">{{ work_orders|length }}</div>
        <div class="lbl">{% trans "Nalozi" %}</div>
    </div>
    <div class="stat-mini gold">
        <div class="val">{{ signal_stats.total }}</div>
        <div class="lbl">{% trans "Signali" %}</div>
    </div>
    <div class="stat-mini" style="border-color:#22c55e44">
        <div class="val" style="color:#22c55e">{{ exp_today.bookings }}</div>
        <div class="lbl">{% trans "Gosti danas" %}</div>
    </div>
    <div class="stat-mini {% if inv_alerts.low_stock %}red{% endif %}">
        <div class="val">{{ inv_alerts.low_stock }}</div>
        <div class="lbl">{% trans "Niska zaliha" %}</div>
    </div>
    <div class="stat-mini {% if inv_alerts.karenca %}red{% endif %}">
        <div class="val">{{ inv_alerts.karenca }}</div>
        <div class="lbl">{% trans "Karenca" %}</div>
    </div>
    <div class="stat-mini gold">
        <div class="val">{{ fin_pulse.today_revenue }}€</div>
        <div class="lbl">{% trans "Danas" %}</div>
    </div>
</div>"""

c = c.replace(old_stats, new_stats)

# Dodaj HTMX auto-refresh na header
old_header = """<div class="ops-header">
    <div class="ops-title">⚡ {% trans "Operations" %} <span>{% trans "Dashboard" %}</span></div>
    <div style="font-size:.75rem;color:var(--text-muted)">{{ now|date:"d.m.Y H:i" }}</div>
</div>"""

new_header = """<div class="ops-header" hx-get="{% url 'borg_ops:operations_dashboard' %}" hx-trigger="every 60s" hx-select=".stats-row,.ops-grid" hx-target="#borg-hub-content" hx-swap="innerHTML">
    <div class="ops-title">⚡ BORG <span>Hub</span></div>
    <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:.65rem;color:var(--text-muted);background:rgba(34,197,94,.1);padding:3px 10px;border-radius:20px;border:1px solid rgba(34,197,94,.2)">● LIVE</span>
        <span style="font-size:.75rem;color:var(--text-muted)">{{ now|date:"d.m.Y H:i" }}</span>
    </div>
</div>
<div id="borg-hub-content">"""

c = c.replace(old_header, new_header)

# Dodaj experiences + inventory + financije sekcije prije zatvaranja
old_signals_end = """</div>
{% endblock %}"""

new_sections = """<!-- Experiences — Danas -->
{% if exp_today.schedules > 0 or exp_today.bookings > 0 %}
<div class="ops-section">
    <div class="ops-section-header">
        <div class="ops-section-title">🎯 {% trans "Iskustva — danas" %}</div>
        <a href="{% url 'experiences:experience_list' %}" style="font-size:.72rem;color:var(--gold);text-decoration:none">{% trans "Sva iskustva →" %}</a>
    </div>
    <div class="ops-section-body" style="display:flex;gap:24px;font-size:.85rem;flex-wrap:wrap">
        <div>{% trans "Termini:" %} <strong>{{ exp_today.schedules }}</strong></div>
        <div>{% trans "Rezervacije:" %} <strong style="color:#22c55e">{{ exp_today.bookings }}</strong></div>
        {% if exp_today.no_shows %}<div>{% trans "No-show:" %} <strong style="color:#ef4444">{{ exp_today.no_shows }}</strong></div>{% endif %}
        {% if exp_today.revenue %}<div>{% trans "Prihod:" %} <strong style="color:var(--gold)">{{ exp_today.revenue }}€</strong></div>{% endif %}
    </div>
</div>
{% endif %}

<!-- Inventory Alerts -->
{% if inv_alerts.low_stock > 0 or inv_alerts.karenca > 0 or inv_alerts.expiring > 0 %}
<div class="ops-section">
    <div class="ops-section-header">
        <div class="ops-section-title">📦 {% trans "Zalihe — upozorenja" %}</div>
        <a href="{% url 'inventory:list' %}" style="font-size:.72rem;color:var(--gold);text-decoration:none">{% trans "Skladište →" %}</a>
    </div>
    <div class="ops-section-body">
        {% if inv_alerts.karenca > 0 %}
        <div class="sla-alert sla-critical"><span class="sla-model">KARENCA</span><span>{{ inv_alerts.karenca }} artikl(a) blokirano — aktivna karenca jata</span></div>
        {% endif %}
        {% if inv_alerts.low_stock > 0 %}
        <div class="sla-alert sla-warning"><span class="sla-model">ZALIHA</span><span>{{ inv_alerts.low_stock }} artikl(a) ispod minimuma: {{ inv_alerts.items|join:", " }}</span></div>
        {% endif %}
        {% if inv_alerts.expiring > 0 %}
        <div class="sla-alert sla-warning"><span class="sla-model">ROK</span><span>{{ inv_alerts.expiring }} šarži ističe u 7 dana</span></div>
        {% endif %}
    </div>
</div>
{% endif %}

<!-- Financijski pulse -->
<div class="ops-section">
    <div class="ops-section-header">
        <div class="ops-section-title">💰 {% trans "Financijski pulse" %}</div>
        <a href="{% url 'invoicing:list' %}" style="font-size:.72rem;color:var(--gold);text-decoration:none">{% trans "Fakture →" %}</a>
    </div>
    <div class="ops-section-body" style="display:flex;gap:24px;font-size:.85rem;flex-wrap:wrap">
        <div>{% trans "Danas:" %} <strong style="color:var(--gold)">{{ fin_pulse.today_revenue }}€</strong></div>
        <div>{% trans "Neplaćeno:" %} <strong style="color:#f59e0b">{{ fin_pulse.unpaid }}</strong> {% trans "računa" %}</div>
    </div>
</div>

</div>
</div><!-- /borg-hub-content -->
{% endblock %}"""

c = c.replace(old_signals_end, new_sections)

# Fix @media za 8 kolona
old_media = """@media(max-width:768px){
    .stats-row{grid-template-columns:repeat(2,1fr)}
}"""
new_media = """@media(max-width:992px){
    .stats-row{grid-template-columns:repeat(4,1fr)!important}
}
@media(max-width:576px){
    .stats-row{grid-template-columns:repeat(2,1fr)!important}
}"""
c = c.replace(old_media, new_media)

with open(path, 'w') as f:
    f.write(c)
print("[OK] borg_ops/operations_dashboard.html — BORG Hub s experiences, inventory, financije + HTMX live")


# ══════════════════════════════════════════════════════════════════════
# 3. SIDEBAR — dodaj BORG Hub link na vrh
# ══════════════════════════════════════════════════════════════════════
path = os.path.join(BASE, 'templates/base.html')
with open(path) as f:
    c = f.read()

# Nađi prvi sidebar nav-link i dodaj BORG Hub iznad
# Tražim pattern za sidebar sekciju
import re
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
# Nađi "Dashboard" link u sidebaru (obično prvi)
dashboard_pattern = re.search(r'(<a[^>]*href="{% url \'dashboard\' %}"[^>]*>.*?Dashboard.*?</a>)', c, re.DOTALL)
if dashboard_pattern:
    dashboard_link = dashboard_pattern.group(0)
    borg_link = """<a href="{% url 'borg_ops:operations_dashboard' %}" class="nav-link" style="background:linear-gradient(135deg,rgba(201,168,76,.1),rgba(201,168,76,.05));border:1px solid rgba(201,168,76,.2);border-radius:8px;margin:4px 8px;padding:8px 12px"><i class="fas fa-bolt me-2" style="color:var(--gold)"></i><span style="color:var(--gold);font-weight:700">BORG Hub</span></a>\n    """
    if 'BORG Hub' not in c:
        c = c.replace(dashboard_link, borg_link + dashboard_link)
        with open(path, 'w') as f:
            f.write(c)
        print("[OK] base.html — BORG Hub link dodan u sidebar (iznad Dashboard)")
    else:
        print("[SKIP] base.html — BORG Hub link već postoji")
else:
    # Fallback: traži bilo koji sidebar-menu ili nav element
    print("[WARN] Nisam našao Dashboard link u sidebaru — ručno dodaj BORG Hub link")

print("\n═══════════════════════════════════════════")
print("BORG HUB KOMPLETIRAN")
print("═══════════════════════════════════════════")
