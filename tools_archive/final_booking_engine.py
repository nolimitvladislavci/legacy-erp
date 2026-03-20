#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import re
from pathlib import Path

print("🚀 INICIJALIZACIJA: LIMIT CONNECT Univerzalni Booking Engine (Pro Verzija)...")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') # Prilagođeno tvom core modulu
BASE_DIR = Path('/var/www/fina-connect')
sys.path.append(str(BASE_DIR))

import django
django.setup()

from django.core.management import call_command
from django.apps import apps

APP_NAME = 'appointments'
MODELS_PATH = BASE_DIR / APP_NAME / 'models.py'
VIEWS_PATH = BASE_DIR / APP_NAME / 'views.py'
URLS_PATH = BASE_DIR / APP_NAME / 'urls.py'
ADMIN_PATH = BASE_DIR / APP_NAME / 'admin.py'
FORMS_PATH = BASE_DIR / APP_NAME / 'forms.py'
TEMPLATES_DIR = BASE_DIR / APP_NAME / 'templates' / APP_NAME

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# 1. SIGURNOSNI BACKUP
for path in [MODELS_PATH, VIEWS_PATH, URLS_PATH, ADMIN_PATH]:
    if path.exists():
        shutil.copy2(path, f"{path}.bak")
        print(f"📦 Backup kreiran: {path}.bak")

def model_exists(model_name):
    try:
        apps.get_model(APP_NAME, model_name)
        return True
    except LookupError:
        return False

def field_exists(model_name, field_name):
    try:
        model = apps.get_model(APP_NAME, model_name)
        return hasattr(model, field_name)
    except LookupError:
        return False

# 2. NADOGRADNJA MODELA
with open(MODELS_PATH, 'r', encoding='utf-8') as f:
    models_content = f.read()

if not model_exists('BookingResource'):
    resource_model = """
class BookingResource(models.Model):
    RESOURCE_TYPES = [
        ('ljudstvo', 'Ljudski resurs (Radnik, Majstor)'),
        ('nekretnina', 'Nekretnina (Soba, Garsonjera, Restoran)'),
        ('oprema', 'Oprema / Vozilo / Aparat'),
    ]
    name = models.CharField(max_length=100, verbose_name='Naziv resursa')
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES, default='nekretnina', verbose_name='Tip resursa')
    is_active = models.BooleanField(default=True, verbose_name='Aktivan')
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena po satu')
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena po danu')
    capacity = models.PositiveIntegerField(blank=True, null=True, verbose_name='Kapacitet (broj osoba)')
    description = models.TextField(blank=True, verbose_name='Opis')

    class Meta:
        verbose_name = 'Resurs za najam/rezervaciju'
        verbose_name_plural = 'Resursi'

    def __str__(self):
        return f"{self.name} ({self.get_resource_type_display()})"
"""
    models_content += resource_model
    print("✅ Dodan model BookingResource.")

fields_to_add = {
    'appointment_type': "models.CharField(max_length=20, choices=TYPE_CHOICES, default='meeting', verbose_name='Tip termina')",
    'resource': "models.ForeignKey('BookingResource', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Zauzeti resurs')",
    'is_all_day': "models.BooleanField(default=False, verbose_name='Cjelodnevni/Višednevni najam')",
    'color': "models.CharField(max_length=20, default='#3b82f6', verbose_name='Boja u kalendaru')",
}

if model_exists('Appointment'):
    missing_fields = [f for f in fields_to_add if not field_exists('Appointment', f)]
    if missing_fields:
        type_choices_code = """
    TYPE_CHOICES = [
        ('service', 'Kratka usluga (Frizer, Mehaničar, Optičar)'),
        ('rental', 'Dugoročni najam (Soba, Nekretnina, Radnik)'),
        ('event', 'Događaj (Fešta, Zakupljeni termin)'),
        ('meeting', 'Obični sastanak'),
    ]"""
        pattern = r'(class Appointment\(models\.Model\):.*?)(\s+class Meta:)'
        replacement = r'\1' + type_choices_code + '\n'
        for field_name, field_def in fields_to_add.items():
            if field_name in missing_fields:
                replacement += f'    {field_name} = {field_def}\n'
        replacement += r'\2'
        models_content = re.sub(pattern, replacement, models_content, flags=re.DOTALL)
        print(f"✅ Appointment proširen s poljima: {', '.join(missing_fields)}")

with open(MODELS_PATH, 'w', encoding='utf-8') as f:
    f.write(models_content)

# 3. KREIRANJE FORMS.PY (S VALIDACIJOM PREKLAPANJA)
forms_content = '''from django import forms
from .models import Appointment, BookingResource

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['title', 'client', 'start_time', 'end_time', 'appointment_type',
                  'resource', 'is_all_day', 'status', 'color', 'description']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        resource = cleaned_data.get('resource')
        
        if resource and start and end:
            overlapping = Appointment.objects.filter(
                resource=resource,
                start_time__lt=end,
                end_time__gt=start
            )
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise forms.ValidationError("Upozorenje: Ovaj resurs je već zauzet u odabranom terminu.")
        return cleaned_data
'''
with open(FORMS_PATH, 'w', encoding='utf-8') as f:
    f.write(forms_content)
print("✅ forms.py kreiran (Smart Validation).")

# 4. NADOGRADNJA VIEWS (DODAN NEDOSTAJUĆI API ZA SPREMANJE)
with open(VIEWS_PATH, 'r', encoding='utf-8') as f:
    views_content = f.read()

new_views = """
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from .models import Appointment, BookingResource
from .forms import AppointmentForm
from partners.models import Partner

@login_required
def calendar_view(request):
    clients = Partner.objects.all()
    resources = BookingResource.objects.filter(is_active=True)
    return render(request, 'appointments/calendar.html', {'clients': clients, 'resources': resources})

@login_required
@require_GET
def api_events(request):
    appointments = Appointment.objects.all()
    events = []
    for app in appointments:
        client_name = app.client.name if app.client else 'Interno'
        events.append({
            'id': app.id,
            'title': f"{app.title} ({client_name})",
            'start': app.start_time.isoformat() if app.start_time else None,
            'end': app.end_time.isoformat() if app.end_time else None,
            'allDay': app.is_all_day,
            'backgroundColor': getattr(app, 'color', '#3b82f6'),
            'borderColor': getattr(app, 'color', '#3b82f6'),
            'extendedProps': {
                'type': app.get_appointment_type_display(),
                'status': app.get_status_display(),
                'resource_id': app.resource_id,
            }
        })
    return JsonResponse(events, safe=False)

@login_required
def api_appointments(request, pk=None):
    # API ENDPOINT ZA SPREMANJE I UREĐIVANJE (Ovo je nedostajalo)
    if request.method in ['POST', 'PUT']:
        if pk:
            appointment = get_object_or_404(Appointment, pk=pk)
            form = AppointmentForm(request.POST, instance=appointment)
        else:
            form = AppointmentForm(request.POST)

        if form.is_valid():
            appointment = form.save(commit=False)
            if not getattr(appointment, 'employee_id', None):
                appointment.employee = request.user
            appointment.save()
            return JsonResponse({'status': 'success', 'id': appointment.id})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
            
    elif request.method == 'DELETE' and pk:
        appointment = get_object_or_404(Appointment, pk=pk)
        appointment.delete()
        return JsonResponse({'status': 'success'})
        
    return JsonResponse({'status': 'invalid method'}, status=405)
"""
if "def calendar_view" not in views_content:
    views_content += new_views
    with open(VIEWS_PATH, 'w', encoding='utf-8') as f:
        f.write(views_content)
    print("✅ Views logika (calendar, GET api, POST/PUT api) uspješno ubačena.")

# 5. NADOGRADNJA URLS
with open(URLS_PATH, 'r', encoding='utf-8') as f:
    urls_content = f.read()

new_urls = """
    path('', views.calendar_view, name='calendar'),
    path('api/events/', views.api_events, name='api_events'),
    path('api/appointments/', views.api_appointments, name='api_appointments_create'),
    path('api/appointments/<int:pk>/', views.api_appointments, name='api_appointments_detail'),
"""
if "api_events" not in urls_content:
    if 'urlpatterns = [' in urls_content:
        urls_content = urls_content.replace('urlpatterns = [', 'urlpatterns = [' + new_urls)
        with open(URLS_PATH, 'w', encoding='utf-8') as f:
            f.write(urls_content)
    print("✅ URL rute prilagođene za novi API.")

# 6. HTML PREDLOŽAK (Prilagođen za API komunikaciju)
calendar_template = """{% extends "base.html" %}
{% load i18n %}
{% block title %}Kalendar & Najam - LIMIT CONNECT{% endblock %}
{% block page_title %}UPRAVLJANJE TERMINIMA I NAJMOM{% endblock %}

{% block extra_css %}
<link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
<style>
    .fc-theme-standard td, .fc-theme-standard th { border-color: #e2e8f0; }
    .fc-col-header-cell { background: #f8fafc; padding: 10px 0; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; }
    .fc-event { border: none !important; border-radius: 6px; padding: 3px 5px; font-size: 0.75rem; font-weight: 500; cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.1); transition: transform 0.1s;}
    .fc-toolbar-title { font-size: 1.3rem !important; font-weight: 700; color: #0f172a; }
    .fc-button-primary { background-color: var(--sidebar-bg) !important; border-color: var(--sidebar-bg) !important; font-weight: 600 !important; text-transform: capitalize;}
    #calendar-container { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #f1f5f9; }
</style>
{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-md-3">
        <div class="stat-card" style="border-left: 4px solid var(--gold);">
            <div class="label">Novi Termin / Najam</div>
            <button class="btn btn-sm btn-dark w-100 mt-2" data-bs-toggle="modal" data-bs-target="#appointmentModal" onclick="clearForm()">
                <i class="fas fa-plus me-1"></i> Kreiraj unos
            </button>
        </div>
        <div class="stat-card mt-3">
            <div class="label">Legenda</div>
            <div class="mt-2" style="font-size:0.8rem; color:#475569;">
                <div class="d-flex align-items-center mb-1"><span class="badge me-2" style="background:#3b82f6; width:15px; height:15px;"></span> Kratke Usluge</div>
                <div class="d-flex align-items-center mb-1"><span class="badge me-2" style="background:#10b981; width:15px; height:15px;"></span> Dugoročni Najam</div>
                <div class="d-flex align-items-center mb-1"><span class="badge me-2" style="background:#f59e0b; width:15px; height:15px;"></span> Fešte / Događaji</div>
                <div class="d-flex align-items-center"><span class="badge me-2" style="background:#64748b; width:15px; height:15px;"></span> Sastanci</div>
            </div>
        </div>
    </div>
    <div class="col-md-9">
        <div id="calendar-container">
            <div id='calendar'></div>
        </div>
    </div>
</div>

<div class="modal fade" id="appointmentModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <form id="appointmentForm">
                <div class="modal-header">
                    <h5 class="modal-title" id="appointmentModalLabel">Novi termin / najam</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="formErrors" class="alert alert-danger d-none"></div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Naslov</label>
                            <input type="text" class="form-control" name="title" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Klijent</label>
                            <select class="form-select" name="client">
                                <option value="">--- Interni ---</option>
                                {% for client in clients %}
                                <option value="{{ client.id }}">{{ client.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Početak</label>
                            <input type="datetime-local" class="form-control" id="id_start_time" name="start_time" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Kraj</label>
                            <input type="datetime-local" class="form-control" id="id_end_time" name="end_time" required>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <label class="form-label">Tip termina</label>
                            <select class="form-select" name="appointment_type">
                                <option value="service">Kratka usluga</option>
                                <option value="rental">Dugoročni najam</option>
                                <option value="event">Događaj</option>
                                <option value="meeting" selected>Sastanak</option>
                            </select>
                        </div>
                        <div class="col-md-4 mb-3">
                            <label class="form-label">Resurs</label>
                            <select class="form-select" name="resource">
                                <option value="">--- Bez resursa ---</option>
                                {% for res in resources %}
                                <option value="{{ res.id }}">{{ res.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-md-4 mb-3">
                            <label class="form-label">Boja u kalendaru</label>
                            <input type="color" class="form-control form-control-color w-100" name="color" value="#3b82f6">
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Odustani</button>
                    <button type="submit" class="btn btn-primary">Spremi</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/@fullcalendar/core@6.1.10/locales-all.global.min.js'></script>
<script>
    let calendar;
    let currentEventId = null;

    function clearForm() {
        document.getElementById('appointmentForm').reset();
        currentEventId = null;
        document.getElementById('formErrors').classList.add('d-none');
        document.getElementById('appointmentModalLabel').innerText = 'Novi termin / najam';
    }

    document.addEventListener('DOMContentLoaded', function() {
        var calendarEl = document.getElementById('calendar');
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: '{{ CURRENT_LANG|default:"hr" }}',
            headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,timeGridDay' },
            navLinks: true, editable: true, selectable: true, dayMaxEvents: true,
            events: '/appointments/api/events/',
            select: function(info) {
                clearForm();
                document.getElementById('id_start_time').value = info.startStr.slice(0,16);
                if (info.endStr) { document.getElementById('id_end_time').value = info.endStr.slice(0,16); }
                var modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
                modal.show();
            }
        });
        calendar.render();
    });

    document.getElementById('appointmentForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const url = currentEventId ? `/appointments/api/appointments/${currentEventId}/` : '/appointments/api/appointments/';
        
        fetch(url, {
            method: 'POST', // Django forme najčešće traže klasični POST sa ID-jem
            body: formData,
            headers: { 'X-CSRFToken': '{{ csrf_token }}' }
        })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') {
                var modalInstance = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
                modalInstance.hide();
                calendar.refetchEvents();
            } else {
                let errDiv = document.getElementById('formErrors');
                errDiv.innerHTML = JSON.stringify(data.errors);
                errDiv.classList.remove('d-none');
            }
        });
    });
</script>
{% endblock %}
"""
with open(TEMPLATES_DIR / 'calendar.html', 'w', encoding='utf-8') as f:
    f.write(calendar_template)

# 7. MIGRACIJE, DOZVOLE I RESTART (KLJUČNO!)
print("🔄 Stvaranje i primjena migracija...")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations appointments")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

print("🔐 Usklađivanje Linux dozvola...")
os.system("chown -R www-data:www-data /var/www/fina-connect/appointments")

print("🔄 Restart servera...")
os.system("supervisorctl restart fina-connect")

print("✨ Arhitektura modula Termini uspješno prebačena na Universal Booking Engine!")
