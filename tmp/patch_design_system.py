"""
Design System — 5 reusable partials + AI Assist pravila za nove module
"""
import os
BASE = '/var/www/fina-connect/templates'

# ══════════════════════════════════════════════════════════════════════
# 1. _stat_grid.html — reusable stats row
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(BASE, 'components/_stat_grid.html'), 'w') as f:
    f.write("""{% comment %}
Reusable Stat Grid — koristi na svakom dashboardu.
Usage:
  {% include "components/_stat_grid.html" with stats=my_stats %}
  
  stats = [
    {"value": "42", "label": "Artikala", "color": "var(--gold)", "icon": "fas fa-box"},
    {"value": "3", "label": "Upozorenja", "color": "#ef4444"},
  ]
{% endcomment %}
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.75rem;margin-bottom:1.5rem">
{% for s in stats %}
  <div style="background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center">
    {% if s.icon %}<div style="font-size:.9rem;color:{{ s.color|default:'var(--text)' }};margin-bottom:4px"><i class="{{ s.icon }}"></i></div>{% endif %}
    <div style="font-size:1.6rem;font-weight:800;color:{{ s.color|default:'var(--text)' }}">{{ s.value }}</div>
    <div style="font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.3px;color:var(--text-dim,var(--text-muted));margin-top:2px">{{ s.label }}</div>
  </div>
{% endfor %}
</div>
""")
print("  OK _stat_grid.html")

# ══════════════════════════════════════════════════════════════════════
# 2. _page_header.html — standardized page header
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(BASE, 'components/_page_header.html'), 'w') as f:
    f.write("""{% comment %}
Reusable Page Header — naslov, podnaslov, CTA gumb.
Usage:
  {% include "components/_page_header.html" with title="Skladište" subtitle="42 artikala" icon="fas fa-boxes" cta_text="Novi artikl" cta_url="/inventory/create/" %}
{% endcomment %}
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap;gap:.75rem">
  <div>
    {% if back_url %}<a href="{{ back_url }}" style="color:var(--text-dim,var(--text-muted));font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>{{ back_text|default:"Natrag" }}</a>{% endif %}
    <h2 style="font-size:1.5rem;font-weight:800;margin:{% if back_url %}.5rem{% else %}0{% endif %} 0 0;color:var(--text)">
      {% if icon %}<i class="{{ icon }} me-2" style="color:var(--gold,#c9a84c)"></i>{% endif %}{{ title }}
    </h2>
    {% if subtitle %}<small style="color:var(--text-dim,var(--text-muted))">{{ subtitle }}</small>{% endif %}
  </div>
  {% if cta_url %}
  <a href="{{ cta_url }}" style="background:linear-gradient(135deg,var(--gold,#c9a84c),#a78b3d);color:#0a0a0a;font-weight:700;border-radius:10px;padding:.5rem 1.5rem;font-size:.85rem;text-decoration:none;border:none">
    {% if cta_icon %}<i class="{{ cta_icon }} me-1"></i>{% endif %}{{ cta_text }}
  </a>
  {% endif %}
</div>
""")
print("  OK _page_header.html")

# ══════════════════════════════════════════════════════════════════════
# 3. _filter_bar.html — standardized search + filter
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(BASE, 'components/_filter_bar.html'), 'w') as f:
    f.write("""{% comment %}
Reusable Filter Bar — search + dropdown filter.
Usage:
  {% include "components/_filter_bar.html" with search_name="q" search_value=q filter_name="status" filter_value=status_f filter_choices=status_choices reset_url="/list/" %}
{% endcomment %}
<div style="background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:12px;padding:.75rem 1rem;margin-bottom:1.25rem">
  <form method="get" class="d-flex gap-2 flex-wrap align-items-center">
    {% if search_name %}
    <input type="text" name="{{ search_name }}" value="{{ search_value|default:'' }}" 
           class="form-control form-control-sm" placeholder="{{ search_placeholder|default:'Pretraži...' }}"
           style="max-width:250px;background:var(--dark,var(--bg));border-color:var(--border);color:var(--text);border-radius:8px">
    {% endif %}
    {% if filter_name %}
    <select name="{{ filter_name }}" class="form-select form-select-sm" 
            style="max-width:180px;background:var(--dark,var(--bg));border-color:var(--border);color:var(--text);border-radius:8px">
      <option value="">{{ filter_placeholder|default:'Sve' }}</option>
      {% for code, label in filter_choices %}<option value="{{ code }}" {% if filter_value == code %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select>
    {% endif %}
    <button type="submit" class="btn btn-sm" style="background:var(--gold-dim,rgba(201,168,76,.1));border:1px solid var(--gold-border,rgba(201,168,76,.3));color:var(--gold,#c9a84c);border-radius:8px;font-weight:600">
      <i class="fas fa-search me-1"></i>{{ submit_text|default:'Traži' }}
    </button>
    {% if reset_url %}<a href="{{ reset_url }}" class="btn btn-sm btn-outline-secondary" style="border-radius:8px">✕</a>{% endif %}
  </form>
</div>
""")
print("  OK _filter_bar.html")

# ══════════════════════════════════════════════════════════════════════
# 4. _data_card.html — reusable card component  
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(BASE, 'components/_data_card.html'), 'w') as f:
    f.write("""{% comment %}
Reusable Data Card — za grid prikaz stavki.
Usage:
  {% include "components/_data_card.html" with title="Degustacija" badge="Aktivno" badge_color="var(--gold)" meta="60 min | 25€/os" url="/exp/1/" %}
{% endcomment %}
<div style="background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:14px;padding:1.25rem;transition:border-color .2s;cursor:{% if url %}pointer{% else %}default{% endif %}"
     {% if url %}onclick="window.location='{{ url }}'"{% endif %}
     onmouseover="this.style.borderColor='var(--gold-border,rgba(201,168,76,.3))'"
     onmouseout="this.style.borderColor='var(--border)'">
  <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:.5rem">
    <h6 style="font-weight:700;color:var(--text);margin:0;font-size:.95rem">{{ title }}</h6>
    {% if badge %}<span style="padding:3px 10px;border-radius:6px;font-size:.72rem;font-weight:700;background:{{ badge_bg|default:'var(--gold-dim,rgba(201,168,76,.1))' }};color:{{ badge_color|default:'var(--gold,#c9a84c)' }}">{{ badge }}</span>{% endif %}
  </div>
  {% if description %}<div style="font-size:.8rem;color:var(--text-dim,var(--text-muted));margin-bottom:.75rem">{{ description|truncatewords:20 }}</div>{% endif %}
  {% if meta %}<div style="font-size:.78rem;color:var(--text-dim,var(--text-muted))">{{ meta }}</div>{% endif %}
</div>
""")
print("  OK _data_card.html")

# ══════════════════════════════════════════════════════════════════════
# 5. _alert_banner.html — za upozorenja (karenca, SLA, etc.)
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(BASE, 'components/_alert_banner.html'), 'w') as f:
    f.write("""{% comment %}
Alert Banner — za kritična upozorenja na vrhu stranice.
Usage:
  {% include "components/_alert_banner.html" with level="danger" icon="fas fa-exclamation-triangle" title="KARENCA" text="Jato pod aktivnom karencom do 15.04.2026" %}
  level: danger (crveno), warning (žuto), info (plavo), success (zeleno)
{% endcomment %}
{% if level == "danger" %}
<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:10px;padding:12px 16px;margin-bottom:1rem;display:flex;align-items:center;gap:12px">
  <i class="{{ icon|default:'fas fa-exclamation-triangle' }}" style="color:#ef4444;font-size:1.1rem"></i>
  <div><strong style="color:#fca5a5">{{ title }}</strong> <span style="color:#fca5a5;font-size:.85rem">{{ text }}</span></div>
</div>
{% elif level == "warning" %}
<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:10px;padding:12px 16px;margin-bottom:1rem;display:flex;align-items:center;gap:12px">
  <i class="{{ icon|default:'fas fa-exclamation-circle' }}" style="color:#f59e0b;font-size:1.1rem"></i>
  <div><strong style="color:#fbbf24">{{ title }}</strong> <span style="color:#fbbf24;font-size:.85rem">{{ text }}</span></div>
</div>
{% elif level == "success" %}
<div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:10px;padding:12px 16px;margin-bottom:1rem;display:flex;align-items:center;gap:12px">
  <i class="{{ icon|default:'fas fa-check-circle' }}" style="color:#22c55e;font-size:1.1rem"></i>
  <div><strong style="color:#22c55e">{{ title }}</strong> <span style="color:#86efac;font-size:.85rem">{{ text }}</span></div>
</div>
{% else %}
<div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:10px;padding:12px 16px;margin-bottom:1rem;display:flex;align-items:center;gap:12px">
  <i class="{{ icon|default:'fas fa-info-circle' }}" style="color:#3b82f6;font-size:1.1rem"></i>
  <div><strong style="color:#93c5fd">{{ title }}</strong> <span style="color:#93c5fd;font-size:.85rem">{{ text }}</span></div>
</div>
{% endif %}
""")
print("  OK _alert_banner.html")


# ══════════════════════════════════════════════════════════════════════
# 6. AI ASSIST — dodaj pravila za nove module
# ══════════════════════════════════════════════════════════════════════
path = os.path.join(BASE, 'includes/_ai_assist.html')
with open(path) as f:
    c = f.read()

# Nađi kraj RULES array-a i dodaj nove
old_rules_end = """    // Anywhere: idle 2 min
    {
      page: /./,
      check: function(){ return true; },
      delay: 120000,
      id: 'global_idle',
      title: 'Nisi sam!',
      text: 'Što te muči? Klikni <b>🤖</b> i pitaj — tu sam za pomoć.',
    },
  ];"""

new_rules_end = """    // ── EXPERIENCES ──
    {
      page: /\\/experiences\\//,
      check: function(){ return true; },
      delay: 10000,
      id: 'exp_overview',
      title: 'Iskustva & Aktivnosti',
      text: 'Ovdje kreirate degustacije, radionice i ture za goste. <b>Normativi</b> (BOM) automatski skidaju zalihe pri check-inu.',
    },
    {
      page: /\\/experiences\\/novo/,
      check: function(){ return true; },
      delay: 15000,
      id: 'exp_create_help',
      title: 'Novo iskustvo',
      text: 'Unesite cijenu po osobi i postotak depozita. Gosti plaćaju depozit pri rezervaciji — ostatak na licu mjesta.',
    },
    // ── BORG HUB ──
    {
      page: /\\/dashboard\\/operations/,
      check: function(){ return true; },
      delay: 8000,
      id: 'borg_hub_intro',
      title: 'BORG Hub',
      text: 'Ovo je vaš operativni centar. SLA kršenja, intervencije, nalozi, gosti i zalihe — sve na jednom ekranu. <b>Osvježava se automatski</b> svake minute.',
    },
    // ── FLOCK / PERAD ──
    {
      page: /\\/perad\\//,
      check: function(){ return true; },
      delay: 10000,
      id: 'flock_intro',
      title: 'Jata peradi',
      text: 'Evidentirajte nesenje jaja, zdravstvene tretmane i uginuća. <b>Karenca</b> automatski blokira prodaju na POS-u dok traje.',
    },
    // ── MARKETPLACE ──
    {
      page: /\\/marketplace\\//,
      check: function(){ return true; },
      delay: 12000,
      id: 'marketplace_intro',
      title: 'OPG Tržnica',
      text: 'Objavite proizvode s automatskim rokom trajanja. Geofencing za kvarljivu robu (30km). LOT slijedivost ugrađena.',
    },
    // ── RECALL ──
    {
      page: /\\/experiences\\/recall/,
      check: function(){ return true; },
      delay: 8000,
      id: 'recall_intro',
      title: 'HACCP Recall',
      text: 'Povlačenje proizvoda u 3 sekunde: Gost → Jelo → Sastojak → Flock → Svi pogođeni. Kliknite <b>Trace</b> za pokretanje.',
    },
    // ── WORK ORDERS ──
    {
      page: /\\/work-orders\\//,
      check: function(){ return true; },
      delay: 10000,
      id: 'wo_intro',
      title: 'Radni nalozi',
      text: 'Drag & drop kanban ploča. SLA timer prati koliko dugo je nalog u svakom statusu. Crveno = prekoračen rok.',
    },
    // Anywhere: idle 2 min
    {
      page: /./,
      check: function(){ return true; },
      delay: 120000,
      id: 'global_idle',
      title: 'Nisi sam!',
      text: 'Što te muči? Klikni <b>🤖</b> i pitaj — tu sam za pomoć.',
    },
  ];"""

c = c.replace(old_rules_end, new_rules_end)

with open(path, 'w') as f:
    f.write(c)
print("  OK _ai_assist.html — 7 novih AI pravila")


print("\n═══════════════════════════════════════════")
print("DESIGN SYSTEM + AI PRAVILA KOMPLETIRANA")
print("  5 reusable partials")
print("  7 novih AI assist pravila")
print("═══════════════════════════════════════════")
