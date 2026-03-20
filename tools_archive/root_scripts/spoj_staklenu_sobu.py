import os
import shutil

VIEWS_FILE = '/var/www/fina-connect/core/views.py'
TPL_FILE = '/var/www/fina-connect/templates/dashboards/partner.html'

# 1. BACKUP
if os.path.exists(VIEWS_FILE):
    shutil.copy2(VIEWS_FILE, VIEWS_FILE + '.bak_partner')
if os.path.exists(TPL_FILE):
    shutil.copy2(TPL_FILE, TPL_FILE + '.bak_partner')

# 2. AŽURIRANJE BACKENDA (core/views.py)
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

stari_partner_view = """def partner_dashboard(request):
    from django.utils import timezone
    today = timezone.now().date()
    try:
        from invoicing.models import Invoice
        my_invoices = Invoice.objects.unscoped().filter(client_email=request.user.email).order_by('-date_issued')[:10]
        unpaid_count = my_invoices.filter(status__in=('UNPAID','OVERDUE')).count()
    except Exception:
        my_invoices = []; unpaid_count = 0

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

    try:
        from documents.models import Document
        my_docs = Document.objects.unscoped().filter(client_email=request.user.email).order_by('-created_at')[:5]
    except Exception:
        my_docs = []

    return render(request, 'dashboards/partner.html', {"""

novi_partner_view = """def partner_dashboard(request):
    from django.utils import timezone
    from django.db.models import Sum
    from decimal import Decimal
    
    today = timezone.now().date()
    
    # 1. Osnovni dokumenti i fakture
    try:
        from invoicing.models import Invoice
        my_invoices = Invoice.objects.unscoped().filter(client_email=request.user.email).order_by('-date_issued')[:10]
        unpaid_count = my_invoices.filter(status__in=('UNPAID','OVERDUE')).count()
    except Exception:
        my_invoices = []; unpaid_count = 0

    try:
        from documents.models import Document
        my_docs = Document.objects.unscoped().filter(client_email=request.user.email).order_by('-created_at')[:5]
    except Exception:
        my_docs = []
        
    # 2. Magija praćenja uživo (Worktime & Burza)
    total_budget = Decimal('0')
    total_cost = Decimal('0')
    used_percentage = 0
    time_entries = []

    try:
        # Pronalazimo projekt na burzi po emailu klijenta
        from burza.models import ProjectLead
        from worktime.models import TimeEntry
        
        my_leads = ProjectLead.objects.filter(contact_email=request.user.email)
        
        # Zbrajamo budžete (gornju granicu) sa svih aktivnih upita
        for lead in my_leads:
            if lead.budget_to:
                total_budget += lead.budget_to
                
        # Povlačimo sve stvarne sate (TimeEntries) vezane uz te projekte
        time_entries = TimeEntry.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-date', '-start_time')[:15]
        
        # Zbrajamo troškove svih sati
        total_cost = TimeEntry.objects.filter(project_lead__in=my_leads).aggregate(total=Sum('billing_amount'))['total'] or Decimal('0')
        
        if total_budget > 0:
            used_percentage = int((total_cost / total_budget) * 100)
            if used_percentage > 100: used_percentage = 100
            
    except Exception as e:
        print(f"Greška pri dohvatu radnih sati: {e}")

    return render(request, 'dashboards/partner.html', {
        'my_invoices': my_invoices,
        'unpaid_count': unpaid_count,
        'my_docs': my_docs,
        'total_budget': total_budget,
        'total_cost': total_cost,
        'used_percentage': used_percentage,
        'time_entries': time_entries,"""

# Zamjenjujemo stari blok koda
views_code = views_code.replace(stari_partner_view, novi_partner_view)

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(views_code)


# 3. AŽURIRANJE FRONTENDA (partner.html) - Micanje hardkodiranog i ubacivanje dinamičkog Django koda
with open(TPL_FILE, 'r', encoding='utf-8') as f:
    tpl_html = f.read()

# Ubacivanje živih KPI podataka
tpl_html = tpl_html.replace(
    '<div class="kpi-value">€ 14.500</div>',
    '<div class="kpi-value">€ {{ total_budget|default:"0,00" }}</div>'
)
tpl_html = tpl_html.replace(
    '<div class="kpi-value gold">€ 6.240</div>',
    '<div class="kpi-value gold">€ {{ total_cost|default:"0,00" }}</div>'
)
tpl_html = tpl_html.replace(
    '<div class="progress-bar-fill" style="width: 43%;"></div>',
    '<div class="progress-bar-fill" style="width: {{ used_percentage|default:\'0\' }}%;"></div>'
)
tpl_html = tpl_html.replace(
    '<span>43%</span>',
    '<span>{{ used_percentage|default:"0" }}%</span>'
)

# Zamjena hardkodirane tablice sa stvarnom petljom iz baze
stara_tablica = """<tbody>
                        <tr>
                            <td>
                                <div class="worker-name">
                                    <div class="worker-avatar">IF</div>
                                    Ivan F.
                                </div>
                            </td>
                            <td><span class="task-tag">Trockenbau / Rigips</span></td>
                            <td>Heute, 15:30</td>
                            <td class="hours-val">8.0 h</td>
                            <td class="cost-val">€ 280,00</td>
                        </tr>
                        <tr>
                            <td>
                                <div class="worker-name">
                                    <div class="worker-avatar">MS</div>
                                    Mario S.
                                </div>
                            </td>
                            <td><span class="task-tag">Fliesenlegen</span></td>
                            <td>Gestern, 16:00</td>
                            <td class="hours-val">7.5 h</td>
                            <td class="cost-val">€ 262,50</td>
                        </tr>
                        <tr>
                            <td>
                                <div class="worker-name">
                                    <div class="worker-avatar">DR</div>
                                    Dragan R.
                                </div>
                            </td>
                            <td><span class="task-tag">Sanitärinstallation</span></td>
                            <td>23.02.2026</td>
                            <td class="hours-val">4.0 h</td>
                            <td class="cost-val">€ 140,00</td>
                        </tr>
                    </tbody>"""

nova_tablica = """<tbody>
                        {% if time_entries %}
                            {% for entry in time_entries %}
                            <tr>
                                <td>
                                    <div class="worker-name">
                                        <div class="worker-avatar">{{ entry.user.first_name|make_list|first|default:entry.user.username|make_list|first|upper }}{{ entry.user.last_name|make_list|first|default:""|upper }}</div>
                                        {{ entry.user.first_name|default:entry.user.username }} {{ entry.user.last_name|make_list|first|default:"" }}.
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
                    </tbody>"""

tpl_html = tpl_html.replace(stara_tablica, nova_tablica)

with open(TPL_FILE, 'w', encoding='utf-8') as f:
    f.write(tpl_html)

# 4. RESTART
os.system("supervisorctl restart fina-connect")
print("✅ STAKLENA SOBA JE SPOJENA NA ŽIVU BAZU! (Radni sati i Kalkulacije budžeta)")
