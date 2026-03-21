## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Ivan Cockpit: sidebar + klikabilni sjedači

## Problem
1. ivan_cockpit.html je standalone HTML — nema sidebara, nema navigacije
2. SVG sjedači imaju onclick ali ne reagiraju (pointer-events blokiran u SVG)
3. Info kartice nisu klikabilne (MRR, POS, pretplate)

## Rješenje

### Korak 1 — Pretvori u Django template koji extenda base.html

Otvori `/var/www/fina-connect/templates/dashboards/ivan_cockpit.html`

Zamijeni prvih ~30 linija (DOCTYPE, html, head, style blok, body) s:
```html
{% extends "base.html" %}
{% load i18n %}

{% block title %}🔥 Fenix Cockpit{% endblock %}

{% block extra_css %}
<style>
.gold{color:#c9a84c}
.green{color:#22c55e}
.blue{color:#3b82f6}
.amber{color:#f59e0b}
.red{color:#ef4444}
.muted{color:#64748b}
.sub{font-size:.7rem;color:#64748b;letter-spacing:1px;text-transform:uppercase}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:.75rem 0}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem;margin:.75rem 0}
@media(max-width:600px){.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
.card{background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;transition:border-color .2s}
.card-link{cursor:pointer;text-decoration:none;display:block}
.card-link:hover{border-color:#c9a84c !important}
.card-gold{border-left:3px solid #c9a84c}
.card-green{border-left:3px solid #22c55e}
.card-blue{border-left:3px solid #3b82f6}
.card-red{border-left:3px solid #ef4444}
.stat-num{font-size:1.8rem;font-weight:800;line-height:1}
.stat-lbl{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-top:.25rem}
.section-title{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#64748b;margin:1.25rem 0 .5rem;border-bottom:1px solid #1e293b;padding-bottom:.4rem}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{text-align:left;color:#64748b;font-weight:600;padding:.3rem .5rem;border-bottom:1px solid #1e293b}
td{padding:.4rem .5rem;border-bottom:1px solid #0f172a}
tr:hover td{background:#0f172a}

/* Sjedači — lista umjesto SVG */
.seat-list{display:flex;flex-direction:column;gap:8px}
.seat-item{display:flex;align-items:center;gap:12px;padding:.75rem 1rem;background:#111827;border:1px solid #1e293b;border-radius:10px;cursor:pointer;transition:all .2s;text-decoration:none}
.seat-item:hover,.seat-item.active{border-color:var(--seat-color,#c9a84c);background:#0d1117}
.seat-dot{width:10px;height:10px;border-radius:50%;background:var(--seat-color,#c9a84c);flex-shrink:0}
.seat-name{font-size:.85rem;font-weight:700;color:#e2e8f0}
.seat-role{font-size:.7rem;color:#64748b;margin-top:1px}
.seat-badge{margin-left:auto;font-size:.65rem;padding:2px 8px;border-radius:99px;background:#1e293b;color:#64748b;flex-shrink:0}

/* Chat panel */
.chat-panel{display:none;background:#0d1117;border:1px solid #1e293b;border-radius:10px;padding:1rem;margin-top:.5rem}
.chat-panel.open{display:block}
textarea{width:100%;background:#111;color:#e2e8f0;border:1px solid #1e293b;border-radius:8px;padding:.6rem;font-size:.83rem;resize:vertical;font-family:inherit;min-height:80px}
textarea:focus{outline:none;border-color:#c9a84c}
.btn-gold{background:#c9a84c;color:#000;border:none;border-radius:8px;padding:.5rem 1.25rem;font-weight:700;cursor:pointer;font-size:.83rem}
.btn-gold:hover{background:#d4a843}
.btn-ghost{background:none;border:1px solid #1e293b;border-radius:8px;padding:.4rem .9rem;font-size:.78rem;color:#64748b;cursor:pointer}
.btn-ghost:hover{border-color:#c9a84c;color:#c9a84c}
#send-status{font-size:.72rem;color:#64748b;margin-top:.3rem}

/* Feed */
.feed-item{display:flex;gap:8px;padding:.4rem 0;border-bottom:1px solid #0f172a;font-size:.75rem}
.feed-item:last-child{border-bottom:none}
.feed-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:4px}
.feed-time{color:#64748b;flex-shrink:0;min-width:35px}
.feed-module{color:#c9a84c;flex-shrink:0;min-width:60px}
.feed-desc{color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
{% endblock %}

{% block content %}
<div style="max-width:900px;margin:0 auto;padding:1rem">
```

Zatim na kraju fajla, zatvori s:
```html
</div>
{% endblock %}

{% block extra_js %}
<script>
... (JS koji već postoji — openSeat, sendMsg, itd.)
</script>
{% endblock %}
```

### Korak 2 — Zamijeni SVG sjedače s listom

Pronađi SVG blok (između `<svg` i `</svg>`) i zamijeni cijeli card s okruglim stolom s:

```html
<div class="section-title">⬡ Tim — Okrugli stol</div>
<div class="seat-list">
  <div class="seat-item" style="--seat-color:#c9a84c" onclick="openSeat('ivan')">
    <div class="seat-dot"></div>
    <div>
      <div class="seat-name">Ivan Brtan</div>
      <div class="seat-role">Vlasnik — enter tipka, WhatsApp</div>
    </div>
    <div class="seat-badge">Superadmin</div>
  </div>
  <div class="seat-item" style="--seat-color:#22c55e" onclick="openSeat('cc')">
    <div class="seat-dot"></div>
    <div>
      <div class="seat-name">Claude Code</div>
      <div class="seat-role">Executor — server, kod, testovi</div>
    </div>
    <div class="seat-badge">Task</div>
  </div>
  <div class="seat-item" style="--seat-color:#3b82f6" onclick="openSeat('gemini')">
    <div class="seat-dot"></div>
    <div>
      <div class="seat-name">Gemini</div>
      <div class="seat-role">Autonomni agent — čita, piše, pokreće</div>
    </div>
    <div class="seat-badge">Agent</div>
  </div>
  <div class="seat-item" style="--seat-color:#f59e0b" onclick="openSeat('sonnet')">
    <div class="seat-dot"></div>
    <div>
      <div class="seat-name">Sonnet</div>
      <div class="seat-role">Koordinator — planira, pečati</div>
    </div>
    <div class="seat-badge">claude.ai</div>
  </div>
  <div class="seat-item" style="--seat-color:#ec4899" onclick="openSeat('marija')">
    <div class="seat-dot"></div>
    <div>
      <div class="seat-name">Marija Brtan</div>
      <div class="seat-role">Konjik d.o.o. — Tenant Admin</div>
    </div>
    <div class="seat-badge">WhatsApp</div>
  </div>
</div>

<!-- Chat panel ostaje isti -->
<div id="seat-panel" class="chat-panel">
  ... (postojeći seat-panel HTML)
</div>
```

### Korak 3 — Klikabilne info kartice

Dodaj `class="card-link"` i `onclick` na stat kartice:

```html
<!-- MRR → pretplate -->
<a href="/hr/superadmin/" class="card card-gold card-link" style="text-decoration:none">
  <div class="stat-num gold">€{{ mrr|floatformat:0 }}</div>
  <div class="stat-lbl">MRR → pretplate</div>
</a>

<!-- Aktivni korisnici → korisnici lista -->
<a href="/hr/superadmin/users/" class="card card-green card-link" style="text-decoration:none">
  <div class="stat-num green">{{ users_week }}</div>
  <div class="stat-lbl">Aktivni tjedan</div>
</a>

<!-- POS promet → POS lista -->
<a href="/hr/pos/" class="card card-green card-link" style="text-decoration:none">
  <div class="stat-num green">€{{ pos_promet|floatformat:2 }}</div>
  <div class="stat-lbl">POS danas → otvori</div>
</a>

<!-- Kompanije → lista -->
<a href="/hr/superadmin/companies/" class="card card-link" style="border-left:3px solid #8b5cf6;text-decoration:none">
  <div class="stat-num" style="color:#8b5cf6">{{ companies }}</div>
  <div class="stat-lbl">Kompanije → lista</div>
</a>
```

### Korak 4 — Provjera i restart

```bash
cd /var/www/fina-connect

# Provjeri extends
head -3 templates/dashboards/ivan_cockpit.html
# Mora biti: {% extends "base.html" %}

# Provjeri seat-list
grep -c "seat-item" templates/dashboards/ivan_cockpit.html
# Mora biti >= 5

# Django check
venv/bin/python manage.py check 2>&1 | tail -2

# Restart
systemctl restart gunicorn-fina

# Test
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/superadmin/ivan/
```

## Javi
- Je li `{% extends "base.html" %}` na vrhu
- Broj seat-item elemenata
- HTTP status cockpita
