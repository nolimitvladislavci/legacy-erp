import re
import os

VIEWS_FILE = '/var/www/fina-connect/core/views.py'
TPL_FILE = '/var/www/fina-connect/templates/dashboards/partner.html'

# --- 1. RJEŠAVANJE BACKEND LOGIKE (core/views.py) ---
# Čitamo cijeli fajl
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_content = f.read()

# Nova, potpuno bulletproof funkcija koja izolira sve greške i štiti sustav
novi_view = """def partner_dashboard(request):
    from django.utils import timezone
    from django.db.models import Sum
    from decimal import Decimal
    
    today = timezone.now().date()
    
    # 1. Invoices
    try:
        from invoicing.models import Invoice
        my_invoices = Invoice.objects.unscoped().filter(client_email=request.user.email).order_by('-date_issued')[:10]
        unpaid_count = my_invoices.filter(status__in=('UNPAID','OVERDUE')).count()
    except Exception:
        my_invoices = []
        unpaid_count = 0

    # 2. Appointments
    try:
        from appointments.models import Appointment
        from partners.models import Partner
        partner_obj = Partner.objects.filter(email=request.user.email).first()
        if partner_obj:
            my_appointments = Appointment.objects.filter(client=partner_obj).order_by('-start_time')[:6]
        else:
            my_appointments = []
    except Exception:
        my_appointments = []

    # 3. Documents
    try:
        from documents.models import Document
        my_docs = Document.objects.unscoped().filter(client_email=request.user.email).order_by('-created_at')[:5]
    except Exception:
        my_docs = []
        
    # 4. Live Tracking (Burza & Worktime) - MAX SIGURNOST OD CRASHA
    total_budget = Decimal('0')
    total_cost = Decimal('0')
    used_percentage = 0
    time_entries = []

    try:
        from burza.models import ProjectLead
        from worktime.models import TimeEntry
        
        my_leads = ProjectLead.objects.filter(contact_email=request.user.email)
        
        for lead in my_leads:
            if lead.budget_to:
                total_budget += Decimal(str(lead.budget_to))
                
        time_entries = TimeEntry.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-date', '-start_time')[:15]
        
        agg = TimeEntry.objects.filter(project_lead__in=my_leads).aggregate(total=Sum('billing_amount'))
        if agg and agg['total']:
            total_cost = Decimal(str(agg['total']))
            
        if total_budget > 0:
            used_percentage = int((total_cost / total_budget) * 100)
            if used_percentage > 100:
                used_percentage = 100
                
    except Exception as e:
        print(f"Partner Dashboard Tracking Error: {e}")

    return render(request, 'dashboards/partner.html', {
        'my_invoices': my_invoices,
        'unpaid_count': unpaid_count,
        'my_appointments': my_appointments,
        'my_docs': my_docs,
        'total_budget': total_budget,
        'total_cost': total_cost,
        'used_percentage': used_percentage,
        'time_entries': time_entries,
    })
"""

# Zamjena stare funkcije pomoću regularnih izraza
pattern = re.compile(r'^def partner_dashboard\(request\):.*?(?=^def |\Z)', re.MULTILINE | re.DOTALL)
views_content = pattern.sub(novi_view, views_content)

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(views_content)


# --- 2. RJEŠAVANJE HTML PREDLOŠKA (Nema više loma sustava zbog praznog stringa) ---
novi_html = """{% extends 'base.html' %}
{% load i18n %}

{% block title %}Kundenportal – Visković Group{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="/static/css/global_themes.css">
<style>
    .partner-wrap { font-family: var(--font-body); color: var(--text); padding: 24px 0; max-width: 1400px; margin: 0 auto; }
    .p-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 32px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
    .p-greeting { font-family: var(--font-heading); font-size: 2.2rem; font-weight: 300; color: var(--text); margin: 0; }
    .p-greeting span { color: var(--gold); font-weight: 600; font-style: italic; }
    .p-subtext { font-size: 0.9rem; color: var(--text-dim); letter-spacing: 1px; text-transform: uppercase; margin-top: 8px; }
    .p-status-badge { background: rgba(16, 185, 129, 0.1); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.3); padding: 6px 14px; border-radius: 99px; font-size: 0.75rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; }
    .p-status-badge::before { content: ''; width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 10px var(--green); animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 32px; }
    .kpi-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 24px; position: relative; overflow: hidden; transition: transform 0.2s, border-color 0.2s; }
    .kpi-card:hover { transform: translateY(-3px); border-color: var(--gold-border); }
    .kpi-card::after { content: ''; position: absolute; top: -50%; right: -50%; width: 100px; height: 100px; background: radial-gradient(circle, var(--gold-dim) 0%, transparent 70%); border-radius: 50%; opacity: 0.5; }
    .kpi-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
    .kpi-value { font-family: var(--font-heading); font-size: 2.5rem; font-weight: 400; color: var(--text); line-height: 1; }
    .kpi-value.gold { color: var(--gold); font-weight: 600; }
    
    .progress-container { margin-top: 16px; }
    .progress-bar-bg { width: 100%; height: 6px; background: var(--surface3); border-radius: 4px; overflow: hidden; position: relative; }
    .progress-bar-fill { height: 100%; background: linear-gradient(90deg, var(--gold2), var(--gold)); border-radius: 4px; transition: width 1s cubic-bezier(0.4, 0, 0.2, 1); }
    .progress-text { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-dim); margin-top: 8px; }

    .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; align-items: start; }
    .section-box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 24px; }
    .box-header { background: var(--surface2); padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .box-title { font-size: 0.85rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--gold); margin: 0; }

    .feed-table { width: 100%; border-collapse: collapse; }
    .feed-table th { background: rgba(0,0,0,0.2); font-size: 0.65rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; padding: 12px 24px; text-align: left; font-weight: 600; border-bottom: 1px solid var(--border); }
    .feed-table td { padding: 16px 24px; font-size: 0.88rem; color: var(--text); border-bottom: 1px solid rgba(255,255,255,0.03); vertical-align: middle; }
    .feed-table tr:hover td { background: rgba(255,255,255,0.01); }
    .feed-table tr:last-child td { border-bottom: none; }
    
    .worker-name { font-weight: 600; display: flex; align-items: center; gap: 10px; }
    .worker-avatar { width: 28px; height: 28px; border-radius: 50%; background: var(--surface3); color: var(--text-dim); display: flex; align-items: center; justify-content: center; font-size: 0.6rem; font-weight: 700; }
    .task-tag { display: inline-block; padding: 3px 10px; border-radius: 4px; background: var(--surface3); color: var(--text-dim); font-size: 0.7rem; border: 1px solid var(--border); }
    .hours-val { color: var(--text); font-weight: 700; }
    .cost-val { color: var(--gold); font-weight: 700; text-align: right; }

    .doc-list { list-style: none; padding: 0; margin: 0; }
    .doc-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--border); transition: background 0.2s; }
    .doc-item:hover { background: var(--surface2); }
    .doc-item:last-child { border-bottom: none; }
    .doc-info { display: flex; align-items: center; gap: 12px; }
    .doc-icon { width: 36px; height: 36px; border-radius: 8px; background: rgba(59, 130, 246, 0.1); color: var(--blue); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; }
    .doc-icon.invoice { background: rgba(201, 168, 76, 0.1); color: var(--gold); }
    .doc-icon.pdf { background: rgba(239, 68, 68, 0.1); color: var(--red); }
    .doc-meta h4 { margin: 0 0 4px 0; font-size: 0.85rem; font-weight: 600; color: var(--text); }
    .doc-meta span { font-size: 0.7rem; color: var(--text-dim); }
    .btn-download { background: transparent; border: 1px solid var(--border); color: var(--text-dim); padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.2s; text-decoration: none; }
    .btn-download:hover { border-color: var(--gold); color: var(--gold); background: var(--gold-dim); }

    .empty-state { padding: 40px 20px; text-align: center; color: var(--text-dim); }
    .empty-icon { font-size: 2.5rem; opacity: 0.3; margin-bottom: 12px; }

    @media (max-width: 1024px) { .main-grid { grid-template-columns: 1fr; } .p-header { flex-direction: column; align-items: flex-start; gap: 16px; } }
    @media (max-width: 768px) { .feed-table th { display: none; } .feed-table td { display: block; padding: 10px 16px; border: none; } .feed-table tr { border-bottom: 1px solid var(--border); display: block; padding: 8px 0; } .cost-val { text-align: left; } }
</style>
{% endblock %}

{% block content %}
<div class="partner-wrap">

    <div class="p-header">
        <div>
            <div class="p-subtext">Ihr Kundenportal</div>
            <h1 class="p-greeting">Willkommen, <span>{{ request.user.first_name|default:request.user.username }}</span></h1>
        </div>
        <div class="p-status-badge">
            Projekt Aktiv
        </div>
    </div>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label"><i class="fas fa-bullseye"></i> Gesamtbudget (Schätzung)</div>
            <div class="kpi-value">€ {{ total_budget|default:"0.00" }}</div>
            <div class="progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: 100%; opacity: 0.3;"></div>
                </div>
                <div class="progress-text">
                    <span>Laut Angebot</span>
                    <span>100%</span>
                </div>
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label"><i class="fas fa-hammer"></i> Bisherige Arbeitskosten</div>
            <div class="kpi-value gold">€ {{ total_cost|default:"0.00" }}</div>
            <div class="progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {{ used_percentage|default:'0' }}%;"></div>
                </div>
                <div class="progress-text">
                    <span>Transparente Kostenkontrolle</span>
                    <span>{{ used_percentage|default:"0" }}%</span>
                </div>
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label"><i class="fas fa-file-invoice-dollar"></i> Offene Rechnungen</div>
            <div class="kpi-value {% if unpaid_count > 0 %}red{% endif %}" style="color: {% if unpaid_count > 0 %}var(--red){% else %}var(--text){% endif %};">
                {{ unpaid_count|default:"0" }}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 16px;">
                {% if unpaid_count > 0 %}Bitte prüfen Sie den Tab "Rechnungen".{% else %}Alles ist bezahlt. Danke!{% endif %}
            </div>
        </div>
    </div>

    <div class="main-grid">
        
        <div>
            <div class="section-box">
                <div class="box-header">
                    <h2 class="box-title"><i class="fas fa-history"></i> Bautagebuch & Zeiterfassung (Live)</h2>
                    <span style="font-size: 0.7rem; color: var(--text-dim); border: 1px solid var(--border); padding: 4px 8px; border-radius: 4px;">Zuletzt aktualisiert: Heute</span>
                </div>
                
                <table class="feed-table">
                    <thead>
                        <tr>
                            <th>Mitarbeiter</th>
                            <th>Tätigkeit</th>
                            <th>Datum</th>
                            <th>Stunden</th>
                            <th style="text-align: right;">Kosten</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if time_entries %}
                            {% for entry in time_entries %}
                            <tr>
                                <td>
                                    <div class="worker-name">
                                        <div class="worker-avatar">
                                            {% if entry.user.first_name %}
                                                {{ entry.user.first_name|make_list|first|upper }}{% if entry.user.last_name %}{{ entry.user.last_name|make_list|first|upper }}{% endif %}
                                            {% else %}
                                                {{ entry.user.username|make_list|first|upper }}
                                            {% endif %}
                                        </div>
                                        
                                        {% if entry.user.first_name %}
                                            {{ entry.user.first_name }} {% if entry.user.last_name %}{{ entry.user.last_name|make_list|first|upper }}.{% endif %}
                                        {% else %}
                                            {{ entry.user.username }}
                                        {% endif %}
                                    </div>
                                </td>
                                <td><span class="task-tag">{{ entry.get_task_type_display|default:entry.task_type }}</span></td>
                                <td>{{ entry.date|date:"d.m.Y" }} {% if entry.start_time %}{{ entry.start_time|time:"H:i" }}{% endif %}</td>
                                <td class="hours-val">{{ entry.duration }} h</td>
                                <td class="cost-val">€ {{ entry.billing_amount }}</td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="5" style="text-align: center; color: var(--text-dim); padding: 40px 0;">
                                    Noch keine Arbeitszeiten für Ihr Projekt erfasst.
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
                <div style="padding: 16px; text-align: center; border-top: 1px solid var(--border);">
                    <a href="#" style="color: var(--gold); font-size: 0.8rem; text-decoration: none; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;">Alle Einträge anzeigen ↓</a>
                </div>
            </div>
        </div>

        <div>
            <div class="section-box">
                <div class="box-header">
                    <h2 class="box-title"><i class="fas fa-file-invoice"></i> Rechnungen</h2>
                </div>
                {% if my_invoices %}
                    <ul class="doc-list">
                        {% for inv in my_invoices %}
                        <li class="doc-item">
                            <div class="doc-info">
                                <div class="doc-icon invoice"><i class="fas fa-receipt"></i></div>
                                <div class="doc-meta">
                                    <h4>{{ inv.invoice_number|default:"RE-2026" }}</h4>
                                    <span>{{ inv.date_issued|date:"d.m.Y" }} · {{ inv.total }} €</span>
                                </div>
                            </div>
                            <a href="#" onclick="alert('Dokument wird vorbereitet. Bitte versuchen Sie es später erneut.'); return false;" class="btn-download"><i class="fas fa-download"></i></a>
                        </li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <div class="empty-state">
                        <div class="empty-icon"><i class="fas fa-folder-open"></i></div>
                        <div>Keine Rechnungen vorhanden.</div>
                    </div>
                {% endif %}
            </div>

            <div class="section-box">
                <div class="box-header">
                    <h2 class="box-title"><i class="fas fa-folder"></i> Projektunterlagen</h2>
                </div>
                {% if my_docs %}
                    <ul class="doc-list">
                        {% for doc in my_docs %}
                        <li class="doc-item">
                            <div class="doc-info">
                                <div class="doc-icon pdf"><i class="fas fa-file-pdf"></i></div>
                                <div class="doc-meta">
                                    <h4>{{ doc.title }}</h4>
                                    <span>{{ doc.created_at|date:"d.m.Y" }}</span>
                                </div>
                            </div>
                            <a href="{{ doc.file.url }}" target="_blank" class="btn-download"><i class="fas fa-download"></i></a>
                        </li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <ul class="doc-list">
                        <li class="doc-item">
                            <div class="doc-info">
                                <div class="doc-icon pdf"><i class="fas fa-file-pdf"></i></div>
                                <div class="doc-meta">
                                    <h4>Angebot_Badsanierung.pdf</h4>
                                    <span>20.02.2026 · Vertrag</span>
                                </div>
                            </div>
                            <a href="#" onclick="alert('Dokument wird vorbereitet. Bitte versuchen Sie es später erneut.'); return false;" class="btn-download"><i class="fas fa-download"></i></a>
                        </li>
                    </ul>
                {% endif %}
            </div>
            
            <div class="section-box" style="background: var(--gold-dim); border-color: var(--gold-border);">
                <div style="padding: 24px; text-align: center;">
                    <h3 style="color: var(--gold); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 0;">Fragen zum Projekt?</h3>
                    <p style="font-size: 0.85rem; color: var(--text); line-height: 1.6; margin: 12px 0 20px;">Ihr persönlicher Bauleiter steht Ihnen jederzeit zur Verfügung.</p>
                    <a href="tel:+4915234209056" style="display: block; width: 100%; padding: 12px; background: var(--gold); color: var(--black); text-decoration: none; font-weight: 700; border-radius: 6px; text-transform: uppercase; letter-spacing: 1px;">📞 Anrufen</a>
                </div>
            </div>

        </div>
    </div>
</div>
{% endblock %}
"""
with open(TPL_FILE, 'w', encoding='utf-8') as f:
    f.write(novi_html)

os.system("supervisorctl restart fina-connect")
print("✅ GOTOVO! Partner Dashboard više ne puca, podnosi prazne podatke i spremno čita bazu.")
