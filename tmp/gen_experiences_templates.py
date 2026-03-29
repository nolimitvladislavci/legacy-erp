"""Generate all 12 experiences templates — premium dark theme."""
import os
BASE = '/var/www/fina-connect/templates/experiences'
os.makedirs(BASE, exist_ok=True)

CSS = """<style>
.exp-container{max-width:1100px;margin:0 auto}
.exp-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin-bottom:1.5rem}
.exp-stat{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center}
.exp-stat-value{font-size:1.6rem;font-weight:800;color:var(--text)}
.exp-stat-label{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.3px;color:var(--text-dim);margin-top:2px}
.exp-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1.25rem;transition:border-color .2s}
.exp-card:hover{border-color:var(--gold-border)}
.exp-form{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1.5rem}
.exp-input{background:var(--dark)!important;border-color:var(--border)!important;color:var(--text)!important;border-radius:8px!important}
.exp-btn-gold{background:linear-gradient(135deg,var(--gold),#a78b3d);color:#0a0a0a;font-weight:700;border-radius:10px;padding:.5rem 1.5rem;font-size:.85rem;border:none}
.exp-btn-gold:hover{opacity:.9;color:#0a0a0a}
.exp-badge{padding:3px 10px;border-radius:6px;font-size:.72rem;font-weight:700}
.exp-empty{text-align:center;padding:4rem 2rem;color:var(--text-dim)}
.exp-empty i{font-size:3rem;opacity:.15;margin-bottom:.75rem;display:block}
.exp-section{margin-bottom:1.5rem}
.exp-section h5{font-size:.85rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-dim);margin-bottom:.75rem}
.severity-warning{background:#f59e0b22;color:#f59e0b;border:1px solid #f59e0b44}
.severity-recall{background:#ef444422;color:#ef4444;border:1px solid #ef444444}
.severity-critical{background:#dc262622;color:#dc2626;border:1px solid #dc262644}
</style>"""

HEADER = '{% extends "base.html" %}\n{% load i18n %}\n'

templates = {}

# ═══════════════════════════════════════════════════════════════════
# 1. EXPERIENCE LIST
# ═══════════════════════════════════════════════════════════════════
templates['experience_list.html'] = HEADER + """
{% block title %}Iskustva{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
  <div>
    <h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)"><i class="fas fa-hiking me-2" style="color:var(--gold)"></i>Iskustva & Aktivnosti</h2>
    <small style="color:var(--text-dim)">Degustacije, radionice, ture — sve na jednom mjestu</small>
  </div>
  <a href="{% url 'experiences:experience_create' %}" class="exp-btn-gold"><i class="fas fa-plus me-1"></i>Novo iskustvo</a>
</div>

<div class="exp-stats">
  <div class="exp-stat"><div class="exp-stat-value" style="color:var(--gold)">{{ stats.ukupno|default:0 }}</div><div class="exp-stat-label">Iskustava</div></div>
  <div class="exp-stat"><div class="exp-stat-value" style="color:#22c55e">{{ stats.aktivnih|default:0 }}</div><div class="exp-stat-label">Aktivnih</div></div>
  <div class="exp-stat"><div class="exp-stat-value">{{ stats.bookinga|default:0 }}</div><div class="exp-stat-label">Rezervacija</div></div>
</div>

<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:.75rem 1rem;margin-bottom:1.25rem">
  <form method="get" class="d-flex gap-2 flex-wrap align-items-center">
    <input type="text" name="q" value="{{ q }}" class="form-control form-control-sm exp-input" placeholder="Pretraži..." style="max-width:250px">
    <select name="type" class="form-select form-select-sm exp-input" style="max-width:180px">
      <option value="">Sve vrste</option>
      {% for code, label in type_choices %}<option value="{{ code }}" {% if exp_type == code %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select>
    <button type="submit" class="btn btn-sm" style="background:var(--gold-dim);border:1px solid var(--gold-border);color:var(--gold);border-radius:8px;font-weight:600"><i class="fas fa-search me-1"></i>Traži</button>
  </form>
</div>

{% if page %}
<div class="row g-3">
  {% for exp in page %}
  <div class="col-md-6 col-lg-4">
    <a href="{% url 'experiences:experience_detail' exp.pk %}" class="text-decoration-none">
    <div class="exp-card">
      <div class="d-flex justify-content-between align-items-start mb-2">
        <h6 style="font-weight:700;color:var(--text);margin:0">{{ exp.name }}</h6>
        <span class="exp-badge" style="background:var(--gold-dim);color:var(--gold)">{{ exp.get_experience_type_display }}</span>
      </div>
      <div style="font-size:.8rem;color:var(--text-dim);margin-bottom:.75rem">{{ exp.description|truncatewords:20 }}</div>
      <div class="d-flex justify-content-between align-items-center" style="font-size:.78rem">
        <span style="color:var(--text-dim)"><i class="fas fa-clock me-1"></i>{{ exp.duration_minutes }} min</span>
        <span style="color:var(--text-dim)"><i class="fas fa-users me-1"></i>max {{ exp.capacity }}</span>
        <span style="color:var(--gold);font-weight:700">{{ exp.price_per_person }} €/os</span>
      </div>
    </div>
    </a>
  </div>
  {% endfor %}
</div>
{% include "partials/pagination.html" with page_obj=page %}
{% else %}
<div class="exp-empty"><i class="fas fa-hiking"></i><h5>Nema iskustava</h5><p>Kreirajte prvu aktivnost za goste.</p><a href="{% url 'experiences:experience_create' %}" class="exp-btn-gold"><i class="fas fa-plus me-1"></i>Kreiraj</a></div>
{% endif %}
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 2. EXPERIENCE FORM (create + edit)
# ═══════════════════════════════════════════════════════════════════
templates['experience_form.html'] = HEADER + """
{% block title %}{% if edit %}Uredi{% else %}Novo{% endif %} iskustvo{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<div class="mb-4">
  <a href="{% url 'experiences:experience_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Natrag</a>
  <h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0 0;color:var(--text)">
    <i class="fas fa-{% if edit %}edit{% else %}plus-circle{% endif %} me-2" style="color:var(--gold)"></i>
    {% if edit %}Uredi: {{ exp.name }}{% else %}Novo iskustvo{% endif %}
  </h2>
</div>

<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-8"><label class="form-label small fw-bold" style="color:var(--text-dim)">Naziv</label><input type="text" name="name" value="{{ exp.name|default:'' }}" class="form-control exp-input" required></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Tip</label><select name="experience_type" class="form-select exp-input">{% for code,label in type_choices %}<option value="{{ code }}" {% if exp.experience_type == code %}selected{% endif %}>{{ label }}</option>{% endfor %}</select></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Opis</label><textarea name="description" rows="3" class="form-control exp-input">{{ exp.description|default:'' }}</textarea></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Trajanje (min)</label><input type="number" name="duration_minutes" value="{{ exp.duration_minutes|default:'60' }}" class="form-control exp-input" required></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Max gostiju</label><input type="number" name="capacity" value="{{ exp.capacity|default:'10' }}" class="form-control exp-input" required></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Cijena/osobi (EUR)</label><input type="number" step="0.01" name="price_per_person" value="{{ exp.price_per_person|default:'0' }}" class="form-control exp-input" required></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Depozit (%)</label><input type="number" name="deposit_pct" value="{{ exp.deposit_pct|default:'30' }}" class="form-control exp-input"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Težina</label><select name="difficulty" class="form-select exp-input">{% for code,label in difficulty_choices %}<option value="{{ code }}" {% if exp.difficulty == code %}selected{% endif %}>{{ label }}</option>{% endfor %}</select></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Popust djeca (%)</label><input type="number" name="child_discount_pct" value="{{ exp.child_discount_pct|default:'50' }}" class="form-control exp-input"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Otkazivanje (sati)</label><input type="number" name="cancellation_hours" value="{{ exp.cancellation_hours|default:'12' }}" class="form-control exp-input"></div>
    <div class="col-md-6"><label class="form-label small fw-bold" style="color:var(--text-dim)">Točka okupljanja</label><input type="text" name="meeting_point" value="{{ exp.meeting_point|default:'' }}" class="form-control exp-input"></div>
    <div class="col-md-6"><label class="form-label small fw-bold" style="color:var(--text-dim)">Što ponijeti</label><input type="text" name="what_to_bring" value="{{ exp.what_to_bring|default:'' }}" class="form-control exp-input"></div>
  </div>
  <div class="mt-4 d-flex gap-2">
    <button type="submit" class="exp-btn-gold"><i class="fas fa-save me-1"></i>{% if edit %}Spremi{% else %}Kreiraj{% endif %}</button>
    <a href="{% url 'experiences:experience_list' %}" class="btn btn-outline-secondary btn-sm" style="border-radius:10px">Odustani</a>
  </div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 3. EXPERIENCE DETAIL
# ═══════════════════════════════════════════════════════════════════
templates['experience_detail.html'] = HEADER + """
{% block title %}{{ exp.name }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<div class="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
  <div>
    <a href="{% url 'experiences:experience_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Iskustva</a>
    <h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0 0;color:var(--text)">{{ exp.name }}</h2>
    <div style="font-size:.82rem;color:var(--text-dim)">
      <span class="exp-badge" style="background:var(--gold-dim);color:var(--gold)">{{ exp.get_experience_type_display }}</span>
      <span class="ms-2"><i class="fas fa-clock me-1"></i>{{ exp.duration_minutes }} min</span>
      <span class="ms-2"><i class="fas fa-users me-1"></i>max {{ exp.capacity }}</span>
      <span class="ms-2"><i class="fas fa-star me-1" style="color:#f59e0b"></i>{{ avg_rating|floatformat:1|default:"-" }}</span>
    </div>
  </div>
  <div class="d-flex gap-2">
    <a href="{% url 'experiences:experience_edit' exp.pk %}" class="btn btn-sm btn-outline-light" style="border-radius:10px"><i class="fas fa-edit me-1"></i>Uredi</a>
    <a href="{% url 'experiences:schedule_create' exp.pk %}" class="exp-btn-gold"><i class="fas fa-calendar-plus me-1"></i>Novi termin</a>
  </div>
</div>

<div class="exp-stats">
  <div class="exp-stat"><div class="exp-stat-value" style="color:var(--gold)">{{ exp.price_per_person }} €</div><div class="exp-stat-label">Cijena/osobi</div></div>
  <div class="exp-stat"><div class="exp-stat-value" style="color:#22c55e">{{ total_bookings }}</div><div class="exp-stat-label">Ukupno rezervacija</div></div>
  <div class="exp-stat"><div class="exp-stat-value">{{ exp.deposit_pct }}%</div><div class="exp-stat-label">Depozit</div></div>
  <div class="exp-stat"><div class="exp-stat-value">{{ schedules|length }}</div><div class="exp-stat-label">Nadolazećih termina</div></div>
</div>

{% if exp.description %}<div class="exp-card mb-3"><p style="color:var(--text);margin:0">{{ exp.description }}</p></div>{% endif %}

<!-- Termini -->
<div class="exp-section">
  <h5><i class="fas fa-calendar me-2"></i>Nadolazeći termini</h5>
  {% if schedules %}
  <div class="table-responsive"><table class="table table-dark table-sm table-hover align-middle" style="border-radius:12px;overflow:hidden">
    <thead><tr><th>Datum</th><th>Vrijeme</th><th>Status</th><th>Gosti</th><th>Akcije</th></tr></thead>
    <tbody>
    {% for s in schedules %}
    <tr>
      <td style="font-weight:700">{{ s.date|date:"d.m.Y" }}</td>
      <td>{{ s.time_from|time:"H:i" }} — {{ s.time_to|time:"H:i" }}</td>
      <td><span class="exp-badge {% if s.status == 'full' %}severity-recall{% elif s.status == 'open' %}severity-warning{% else %}severity-critical{% endif %}">{{ s.get_status_display }}</span></td>
      <td>{{ s.booked_pax }}/{{ s.max_pax }}</td>
      <td><a href="{% url 'experiences:booking_create' s.pk %}" class="btn btn-sm btn-outline-success" style="border-radius:8px;font-size:.75rem"><i class="fas fa-plus me-1"></i>Rezerviraj</a></td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% else %}<div class="exp-card" style="text-align:center;color:var(--text-dim)"><i class="fas fa-calendar-times"></i> Nema termina — <a href="{% url 'experiences:schedule_create' exp.pk %}">dodaj termin</a></div>{% endif %}
</div>

<!-- Bookings za termine -->
{% for s in schedules %}
{% if s.bookings.all %}
<div class="exp-section">
  <h5><i class="fas fa-users me-2"></i>{{ s.date|date:"d.m." }} {{ s.time_from|time:"H:i" }} — Rezervacije</h5>
  <div class="table-responsive"><table class="table table-dark table-sm table-hover align-middle" style="border-radius:12px;overflow:hidden">
    <thead><tr><th>Gost</th><th>Osobe</th><th>Status</th><th>Depozit</th><th>Akcije</th></tr></thead>
    <tbody>
    {% for b in s.bookings.all %}
    <tr>
      <td style="font-weight:700">{{ b.guest_name }}<br><small style="color:var(--text-dim)">{{ b.guest_phone }}</small></td>
      <td>{{ b.pax_count }} {% if b.children_count %}({{ b.children_count }} dj.){% endif %}</td>
      <td><span class="exp-badge {% if b.status == 'confirmed' %}severity-warning{% elif b.status == 'checked_in' %}severity-warning{% elif b.status == 'completed' %}severity-warning{% elif b.status == 'no_show' %}severity-recall{% else %}severity-critical{% endif %}">{{ b.get_status_display }}</span></td>
      <td>{% if b.deposit_paid %}<span style="color:#22c55e"><i class="fas fa-check me-1"></i>{{ b.deposit_amount }} €</span>{% else %}<span style="color:#ef4444">Čeka</span>{% endif %}</td>
      <td class="d-flex gap-1 flex-wrap">
        {% if b.status == 'pending' %}<form method="POST" action="{% url 'experiences:booking_confirm_deposit' b.pk %}" class="d-inline">{% csrf_token %}<button class="btn btn-sm btn-outline-success" style="border-radius:6px;font-size:.7rem"><i class="fas fa-check"></i> Depozit</button></form>{% endif %}
        {% if b.status == 'confirmed' %}<form method="POST" action="{% url 'experiences:booking_check_in' b.pk %}" class="d-inline">{% csrf_token %}<button class="btn btn-sm btn-outline-info" style="border-radius:6px;font-size:.7rem"><i class="fas fa-sign-in-alt"></i> Check-in</button></form>{% endif %}
        {% if b.status == 'checked_in' %}<form method="POST" action="{% url 'experiences:booking_complete' b.pk %}" class="d-inline">{% csrf_token %}<button class="btn btn-sm btn-outline-success" style="border-radius:6px;font-size:.7rem"><i class="fas fa-flag-checkered"></i> Završi</button></form>{% endif %}
        {% if b.status == 'confirmed' %}<form method="POST" action="{% url 'experiences:booking_no_show' b.pk %}" class="d-inline">{% csrf_token %}<button class="btn btn-sm btn-outline-danger" style="border-radius:6px;font-size:.7rem"><i class="fas fa-user-slash"></i></button></form>{% endif %}
        {% if b.status == 'confirmed' or b.status == 'pending' %}<form method="POST" action="{% url 'experiences:booking_cancel' b.pk %}" class="d-inline">{% csrf_token %}<button class="btn btn-sm btn-outline-secondary" style="border-radius:6px;font-size:.7rem"><i class="fas fa-times"></i></button></form>{% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
</div>
{% endif %}
{% endfor %}

<!-- Normativi (BOM) -->
{% if inclusions %}
<div class="exp-section">
  <h5><i class="fas fa-boxes me-2"></i>Normativi (BOM) — Što je uključeno</h5>
  <div class="table-responsive"><table class="table table-dark table-sm align-middle" style="border-radius:12px;overflow:hidden">
    <thead><tr><th>Stavka</th><th>Po osobi</th><th>Artikl</th><th>Zaliha</th></tr></thead>
    <tbody>
    {% for inc in inclusions %}
    <tr>
      <td style="font-weight:700">{{ inc.description }}</td>
      <td>{{ inc.quantity_per_person }} {{ inc.unit }}</td>
      <td>{% if inc.inventory_item %}<span style="color:#22c55e">{{ inc.inventory_item.name }}</span>{% else %}<span style="color:var(--text-dim)">—</span>{% endif %}</td>
      <td>{% if inc.inventory_item %}{{ inc.inventory_item.quantity }} {{ inc.inventory_item.unit }}{% else %}—{% endif %}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
</div>
{% endif %}

<!-- Recenzije -->
{% if reviews %}
<div class="exp-section">
  <h5><i class="fas fa-star me-2" style="color:#f59e0b"></i>Recenzije</h5>
  {% for r in reviews %}
  <div class="exp-card mb-2">
    <div class="d-flex justify-content-between"><strong>{{ r.booking.guest_name }}</strong><span>{% for i in "12345" %}{% if forloop.counter <= r.rating %}<i class="fas fa-star" style="color:#f59e0b"></i>{% else %}<i class="far fa-star" style="color:var(--text-dim)"></i>{% endif %}{% endfor %}</span></div>
    {% if r.text %}<p style="margin:.5rem 0 0;font-size:.85rem;color:var(--text-dim)">{{ r.text }}</p>{% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 4. SCHEDULE FORM
# ═══════════════════════════════════════════════════════════════════
templates['schedule_form.html'] = HEADER + """
{% block title %}Novi termin — {{ exp.name }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:experience_detail' exp.pk %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>{{ exp.name }}</a>
<h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0 1.5rem;color:var(--text)"><i class="fas fa-calendar-plus me-2" style="color:var(--gold)"></i>Novi termin</h2>
<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Datum</label><input type="date" name="date" class="form-control exp-input" required></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Od</label><input type="time" name="time_from" class="form-control exp-input" required></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Do</label><input type="time" name="time_to" class="form-control exp-input" required></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Max gostiju</label><input type="number" name="max_pax" value="{{ exp.capacity }}" class="form-control exp-input"></div>
  </div>
  <div class="mt-4"><button type="submit" class="exp-btn-gold"><i class="fas fa-save me-1"></i>Dodaj termin</button></div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 5. BOOKING FORM
# ═══════════════════════════════════════════════════════════════════
templates['booking_form.html'] = HEADER + """
{% block title %}Rezervacija — {{ schedule.experience.name }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:experience_detail' schedule.experience.pk %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>{{ schedule.experience.name }}</a>
<h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0;color:var(--text)"><i class="fas fa-ticket-alt me-2" style="color:var(--gold)"></i>Nova rezervacija</h2>
<p style="color:var(--text-dim)">{{ schedule.date|date:"d.m.Y" }} {{ schedule.time_from|time:"H:i" }}—{{ schedule.time_to|time:"H:i" }} | {{ schedule.experience.price_per_person }} €/os | Depozit {{ schedule.experience.deposit_pct }}%</p>

<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-6"><label class="form-label small fw-bold" style="color:var(--text-dim)">Ime gosta</label><input type="text" name="guest_name" class="form-control exp-input" required></div>
    <div class="col-md-6"><label class="form-label small fw-bold" style="color:var(--text-dim)">Email</label><input type="email" name="guest_email" class="form-control exp-input"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Telefon</label><input type="text" name="guest_phone" class="form-control exp-input"></div>
    <div class="col-md-2"><label class="form-label small fw-bold" style="color:var(--text-dim)">Država</label><input type="text" name="guest_country" class="form-control exp-input" placeholder="HR" maxlength="3"></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Broj osoba</label><input type="number" name="pax_count" value="1" min="1" max="{{ schedule.available_spots }}" class="form-control exp-input" required></div>
    <div class="col-md-3"><label class="form-label small fw-bold" style="color:var(--text-dim)">Djece</label><input type="number" name="children_count" value="0" min="0" class="form-control exp-input"></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Napomena</label><textarea name="notes" rows="2" class="form-control exp-input"></textarea></div>
  </div>
  <div class="mt-4"><button type="submit" class="exp-btn-gold"><i class="fas fa-check me-1"></i>Rezerviraj</button></div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 6. REVIEW FORM
# ═══════════════════════════════════════════════════════════════════
templates['review_form.html'] = HEADER + """
{% block title %}Ocjena — {{ booking.schedule.experience.name }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<h2 style="font-size:1.5rem;font-weight:800;margin:0 0 1.5rem;color:var(--text)"><i class="fas fa-star me-2" style="color:#f59e0b"></i>Ocijeni: {{ booking.schedule.experience.name }}</h2>
<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Ocjena (1-5)</label><select name="rating" class="form-select exp-input" required><option value="5">⭐⭐⭐⭐⭐ Izvrsno</option><option value="4">⭐⭐⭐⭐ Vrlo dobro</option><option value="3">⭐⭐⭐ Dobro</option><option value="2">⭐⭐ Loše</option><option value="1">⭐ Užasno</option></select></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Komentar</label><textarea name="text" rows="3" class="form-control exp-input"></textarea></div>
  </div>
  <div class="mt-4"><button type="submit" class="exp-btn-gold"><i class="fas fa-paper-plane me-1"></i>Pošalji ocjenu</button></div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 7. PACKAGE LIST
# ═══════════════════════════════════════════════════════════════════
templates['package_list.html'] = HEADER + """
{% block title %}Agro Paketi{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<div class="d-flex justify-content-between align-items-center mb-4">
  <div><h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)"><i class="fas fa-box-open me-2" style="color:var(--gold)"></i>Agro Paketi</h2><small style="color:var(--text-dim)">Bundlevi iskustava s TaxSplitter-om</small></div>
  <a href="{% url 'experiences:package_create' %}" class="exp-btn-gold"><i class="fas fa-plus me-1"></i>Novi paket</a>
</div>
{% if packages %}
<div class="row g-3">
  {% for pkg in packages %}
  <div class="col-md-6 col-lg-4">
    <a href="{% url 'experiences:package_detail' pkg.pk %}" class="text-decoration-none">
    <div class="exp-card">
      <h6 style="font-weight:700;color:var(--text);margin:0 0 .5rem">{{ pkg.name }}</h6>
      <p style="font-size:.8rem;color:var(--text-dim);margin:0 0 .75rem">{{ pkg.description|truncatewords:15 }}</p>
      <div style="font-size:1.2rem;font-weight:800;color:var(--gold)">{{ pkg.advertised_price }} €</div>
    </div>
    </a>
  </div>
  {% endfor %}
</div>
{% else %}<div class="exp-empty"><i class="fas fa-box-open"></i><h5>Nema paketa</h5><p>Kreirajte bundle iskustava.</p></div>{% endif %}
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 8. PACKAGE FORM
# ═══════════════════════════════════════════════════════════════════
templates['package_form.html'] = HEADER + """
{% block title %}Novi paket{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:package_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Paketi</a>
<h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0 1.5rem;color:var(--text)"><i class="fas fa-box-open me-2" style="color:var(--gold)"></i>Novi Agro Paket</h2>
<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-8"><label class="form-label small fw-bold" style="color:var(--text-dim)">Naziv</label><input type="text" name="name" class="form-control exp-input" required></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Cijena (EUR)</label><input type="number" step="0.01" name="advertised_price" class="form-control exp-input" required></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Opis</label><textarea name="description" rows="3" class="form-control exp-input"></textarea></div>
  </div>
  <div class="mt-4"><button type="submit" class="exp-btn-gold"><i class="fas fa-save me-1"></i>Kreiraj paket</button></div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 9. PACKAGE DETAIL
# ═══════════════════════════════════════════════════════════════════
templates['package_detail.html'] = HEADER + """
{% block title %}{{ pkg.name }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:package_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Paketi</a>
<div class="d-flex justify-content-between align-items-start mb-4 mt-2">
  <div><h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)">{{ pkg.name }}</h2><p style="color:var(--text-dim);margin:.25rem 0 0">{{ pkg.description }}</p></div>
  <div style="font-size:1.5rem;font-weight:800;color:var(--gold)">{{ pkg.advertised_price }} €</div>
</div>

{% if components %}
<div class="exp-section">
  <h5><i class="fas fa-puzzle-piece me-2"></i>Komponente paketa</h5>
  <div class="table-responsive"><table class="table table-dark table-sm align-middle" style="border-radius:12px;overflow:hidden">
    <thead><tr><th>Stavka</th><th>Tip</th><th>PDV</th><th class="text-end">Cijena</th></tr></thead>
    <tbody>
    {% for c in components %}<tr><td style="font-weight:700">{{ c.name }}</td><td>{{ c.get_component_type_display }}</td><td>{{ c.tax_rate }}%</td><td class="text-end">{{ c.unit_price }} €</td></tr>{% endfor %}
    </tbody>
  </table></div>
</div>
{% endif %}

{% if tax_info %}
<div class="exp-section">
  <h5><i class="fas fa-calculator me-2"></i>TaxSplitter — Porezni raspored</h5>
  <div class="exp-card">
    {% for rate, info in tax_info.items %}<div class="d-flex justify-content-between mb-1"><span style="color:var(--text-dim)">PDV {{ rate }}%</span><span style="font-weight:700">{{ info.base }} € (porez: {{ info.tax }} €)</span></div>{% endfor %}
    <hr style="border-color:var(--border)"><div class="d-flex justify-content-between"><span style="font-weight:700">Ukupno</span><span style="font-weight:800;color:var(--gold)">{{ pkg.advertised_price }} €</span></div>
  </div>
</div>
{% endif %}

<a href="{% url 'experiences:package_tax_breakdown' pkg.pk %}" class="btn btn-sm btn-outline-info" style="border-radius:8px"><i class="fas fa-file-invoice me-1"></i>JSON Tax Breakdown</a>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 10. RECALL LIST
# ═══════════════════════════════════════════════════════════════════
templates['recall_list.html'] = HEADER + """
{% block title %}HACCP Recall{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<div class="d-flex justify-content-between align-items-center mb-4">
  <div><h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)"><i class="fas fa-exclamation-triangle me-2" style="color:#ef4444"></i>HACCP Recall</h2><small style="color:var(--text-dim)">Povlačenje proizvoda — obrnuta slijedivost</small></div>
  <a href="{% url 'experiences:recall_create' %}" class="btn btn-danger btn-sm" style="border-radius:10px;font-weight:700"><i class="fas fa-plus me-1"></i>Novi recall</a>
</div>
{% if recalls %}
<div class="row g-3">
  {% for r in recalls %}
  <div class="col-md-6">
    <a href="{% url 'experiences:recall_detail' r.pk %}" class="text-decoration-none">
    <div class="exp-card" style="border-left:4px solid {% if r.severity == 'critical' %}#dc2626{% elif r.severity == 'recall' %}#ef4444{% else %}#f59e0b{% endif %}">
      <div class="d-flex justify-content-between align-items-start">
        <h6 style="font-weight:700;color:var(--text);margin:0">{{ r.title }}</h6>
        <span class="exp-badge severity-{{ r.severity }}">{{ r.get_severity_display }}</span>
      </div>
      <p style="font-size:.8rem;color:var(--text-dim);margin:.5rem 0">LOT: {{ r.lot_number|default:"—" }} | {{ r.get_status_display }}</p>
      <div style="font-size:.75rem;color:var(--text-dim)">Gostiju: {{ r.affected_guests_count }} | Narudžbi: {{ r.affected_orders_count }} | {{ r.created_at|date:"d.m.Y H:i" }}</div>
    </div>
    </a>
  </div>
  {% endfor %}
</div>
{% else %}<div class="exp-empty"><i class="fas fa-shield-alt"></i><h5>Nema recall događaja</h5><p>Sve je pod kontrolom.</p></div>{% endif %}
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 11. RECALL FORM
# ═══════════════════════════════════════════════════════════════════
templates['recall_form.html'] = HEADER + """
{% block title %}Novi Recall{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:recall_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Recall</a>
<h2 style="font-size:1.5rem;font-weight:800;margin:.5rem 0 1.5rem;color:#ef4444"><i class="fas fa-exclamation-triangle me-2"></i>Novi HACCP Recall</h2>
<form method="POST" class="exp-form">
  {% csrf_token %}
  <div class="row g-3">
    <div class="col-md-8"><label class="form-label small fw-bold" style="color:var(--text-dim)">Naslov</label><input type="text" name="title" class="form-control exp-input" required placeholder="npr. Kontaminacija jaja — Salmonela"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Ozbiljnost</label><select name="severity" class="form-select exp-input">{% for code,label in severity_choices %}<option value="{{ code }}">{{ label }}</option>{% endfor %}</select></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">Izvorni model</label><input type="text" name="source_model" class="form-control exp-input" placeholder="EggRecord"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">ID izvora</label><input type="number" name="source_id" class="form-control exp-input"></div>
    <div class="col-md-4"><label class="form-label small fw-bold" style="color:var(--text-dim)">LOT / Šarža</label><input type="text" name="lot_number" class="form-control exp-input"></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Opis problema</label><textarea name="description" rows="3" class="form-control exp-input" required></textarea></div>
    <div class="col-12"><label class="form-label small fw-bold" style="color:var(--text-dim)">Simptomi</label><textarea name="reported_symptoms" rows="2" class="form-control exp-input"></textarea></div>
  </div>
  <div class="mt-4"><button type="submit" class="btn btn-danger" style="border-radius:10px;font-weight:700"><i class="fas fa-exclamation-circle me-1"></i>Pokreni Recall</button></div>
</form>
</div>
{% endblock %}
"""

# ═══════════════════════════════════════════════════════════════════
# 12. RECALL DETAIL
# ═══════════════════════════════════════════════════════════════════
templates['recall_detail.html'] = HEADER + """
{% block title %}Recall: {{ recall.title }}{% endblock %}
{% block extra_css %}""" + CSS + """{% endblock %}
{% block content %}
<div class="exp-container">
<a href="{% url 'experiences:recall_list' %}" style="color:var(--text-dim);font-size:.85rem"><i class="fas fa-arrow-left me-1"></i>Recall</a>
<div class="d-flex justify-content-between align-items-start mb-4 mt-2">
  <div>
    <h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)">{{ recall.title }}</h2>
    <div style="margin-top:.25rem">
      <span class="exp-badge severity-{{ recall.severity }}">{{ recall.get_severity_display }}</span>
      <span class="exp-badge ms-1" style="background:var(--surface);color:var(--text-dim);border:1px solid var(--border)">{{ recall.get_status_display }}</span>
    </div>
  </div>
  <div class="d-flex gap-2">
    <form method="POST" action="{% url 'experiences:recall_trace' recall.pk %}">{% csrf_token %}<button class="btn btn-sm btn-outline-warning" style="border-radius:8px"><i class="fas fa-search me-1"></i>Trace</button></form>
    <a href="{% url 'experiences:recall_notify' recall.pk %}" class="btn btn-sm btn-outline-danger" style="border-radius:8px"><i class="fas fa-bell me-1"></i>Obavijesti</a>
  </div>
</div>

<div class="exp-stats">
  <div class="exp-stat"><div class="exp-stat-value" style="color:#ef4444">{{ recall.affected_guests_count }}</div><div class="exp-stat-label">Pogođenih gostiju</div></div>
  <div class="exp-stat"><div class="exp-stat-value" style="color:#f59e0b">{{ recall.affected_orders_count }}</div><div class="exp-stat-label">Pogođenih narudžbi</div></div>
  <div class="exp-stat"><div class="exp-stat-value">{{ recall.lot_number|default:"—" }}</div><div class="exp-stat-label">LOT</div></div>
  <div class="exp-stat"><div class="exp-stat-value">{% if recall.health_authority_notified %}<i class="fas fa-check" style="color:#22c55e"></i>{% else %}<i class="fas fa-times" style="color:#ef4444"></i>{% endif %}</div><div class="exp-stat-label">Sanitarna</div></div>
</div>

<div class="exp-card mb-3">
  <h6 style="font-weight:700;color:var(--text)">Opis</h6>
  <p style="color:var(--text-dim);margin:0">{{ recall.description }}</p>
  {% if recall.reported_symptoms %}<h6 style="font-weight:700;color:var(--text);margin-top:1rem">Simptomi</h6><p style="color:var(--text-dim);margin:0">{{ recall.reported_symptoms }}</p>{% endif %}
</div>

{% if notifications %}
<div class="exp-section">
  <h5><i class="fas fa-bell me-2"></i>Obavijesti</h5>
  <div class="table-responsive"><table class="table table-dark table-sm align-middle" style="border-radius:12px;overflow:hidden">
    <thead><tr><th>Primatelj</th><th>Kanal</th><th>Status</th><th>Poslano</th></tr></thead>
    <tbody>
    {% for n in notifications %}
    <tr>
      <td>{{ n.recipient_name }}<br><small style="color:var(--text-dim)">{{ n.recipient_contact }}</small></td>
      <td>{{ n.channel }}</td>
      <td><span class="exp-badge {% if n.status == 'sent' %}severity-warning{% elif n.status == 'failed' %}severity-recall{% else %}severity-critical{% endif %}">{{ n.get_status_display }}</span></td>
      <td>{{ n.sent_at|date:"d.m. H:i"|default:"—" }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
</div>
{% endif %}
</div>
{% endblock %}
"""

# Write all templates
for name, content in templates.items():
    path = os.path.join(BASE, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✓ {name}")

print(f"\n[OK] {len(templates)} templates generated")
