#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
from pathlib import Path

# ==============================================================================
# 1. KONFIGURACIJA I PUTANJE
# ==============================================================================
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

print("🚀 POKRETANJE: Visković Group Unified Engine (Potpuna integracija ERP sustava)")

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

# ==============================================================================
# 2. DEFINICIJA SADRŽAJA - MODELS.PY
# ==============================================================================
models_content = '''import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Resource(models.Model):
    GROUP_CHOICES = [
        ('construction', 'Gradnja'),
        ('housing', 'Stanovanje'),
        ('business', 'Poslovni prostori'),
    ]
    UNIT_CHOICES = [('hour', 'Sat'), ('day', 'Dan'), ('month', 'Mjesec')]
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, verbose_name='Grupa')
    name = models.CharField(max_length=200, verbose_name='Naziv')
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='day')
    capacity = models.PositiveIntegerField(default=1)
    min_duration = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to='resources/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group', 'name']
        verbose_name = 'Premium Resurs'
    def __str__(self): return f"{self.name} ({self.get_group_display()})"

class Addon(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome ikona")
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Booking(models.Model):
    STATUS_CHOICES = [('pending', 'Čeka potvrdu'), ('confirmed', 'Potvrđeno'), ('cancelled', 'Otkazano')]
    PAYMENT_METHODS = [('invoice', 'Službena ponuda'), ('revolut', 'Revolut Pay')]
    booking_number = models.CharField(max_length=20, unique=True, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='invoice')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.booking_number:
            import uuid
            self.booking_number = f"VG-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

class BookingAddon(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='selected_addons')
    addon = models.ForeignKey(Addon, on_delete=models.CASCADE)
    price_at_booking = models.DecimalField(max_digits=8, decimal_places=2)

class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
'''

# ==============================================================================
# 3. DEFINICIJA SADRŽAJA - VIEWS.PY (LOGIKA UJEDINJENJA)
# ==============================================================================
views_content = '''import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Resource, Addon, Booking, BookingAddon, Payment
from appointments.models import Appointment, BookingResource as ERPResource
from partners.models import Partner
from invoicing.models import Invoice

def index(request):
    resources = Resource.objects.filter(is_active=True)
    return render(request, 'premium_booking/index.html', {'resources': resources})

def detail(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    addons = Addon.objects.filter(is_active=True)
    return render(request, 'premium_booking/detail.html', {'resource': resource, 'addons': addons})

@csrf_exempt
def api_submit(request):
    if request.method != 'POST': return JsonResponse({'error': 'Invalid'}, status=405)
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            # 1. Dohvat resursa i vremena
            resource = Resource.objects.get(id=data['resource_id'])
            start_time = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
            duration = resource.min_duration
            end_time = start_time + (timedelta(hours=duration) if resource.unit == 'hour' else timedelta(days=duration))

            # 2. Sinkronizacija Partnera (ERP)
            client, _ = Partner.objects.get_or_create(
                email=data['email'],
                defaults={'name': data['name'], 'phone': data['phone'], 'partner_type': 'KUPAC'}
            )

            # 3. Kreiranje Bookinga
            booking = Booking.objects.create(
                resource=resource, guest_name=data['name'], guest_email=data['email'],
                guest_phone=data['phone'], whatsapp_number=data.get('whatsapp', ''),
                start_time=start_time, end_time=end_time,
                total_price=resource.base_price, payment_method=data['payment_method']
            )

            for addon_id in data.get('addons', []):
                addon = Addon.objects.get(id=addon_id)
                BookingAddon.objects.create(booking=booking, addon=addon, price_at_booking=addon.price)
                booking.total_price += addon.price
            booking.save()

            # 4. Sinkronizacija u ERP Kalendar
            erp_res, _ = ERPResource.objects.get_or_create(name=resource.name)
            Appointment.objects.create(
                title=f"PREMIUM: {resource.name} - {client.name}",
                client=client, resource=erp_res, start_time=start_time, end_time=end_time,
                status='scheduled', color='#c9a84c'
            )

            # 5. Kreiranje fakture (ERP Invoicing)
            if booking.payment_method == 'invoice':
                Invoice.objects.create(partner=client, total_amount=booking.total_price, status='DRAFT', notes=f"Rezervacija: {booking.booking_number}")

            return JsonResponse({'status': 'success', 'booking_number': booking.booking_number, 'total_price': str(booking.total_price)})
    except Exception as e: return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

# ==============================================================================
# 4. DEFINICIJA SADRŽAJA - URLS.PY (POPRAVLJENO!)
# ==============================================================================
urls_content = '''from django.urls import path
from . import views

app_name = 'premium_booking'

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:resource_id>/', views.detail, name='detail'),
    path('api/submit/', views.api_submit, name='api_submit'),
]
'''

# ==============================================================================
# 5. ADMIN.PY
# ==============================================================================
admin_content = '''from django.contrib import admin
from .models import Resource, Addon, Booking, BookingAddon, Payment
admin.site.register(Resource)
admin.site.register(Addon)
admin.site.register(Booking)
admin.site.register(Payment)
'''

# ==============================================================================
# 6. PREMIUM TEMPLATES (VISKOVIĆ DIZAJN - 1000 LINIJA)
# ==============================================================================
index_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VISKOVIĆ PREMIUM | Katalog</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        :root { --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830; --gold: #c9a84c; --white: #f0ede8; }
        body { background: var(--black); color: var(--white); font-family: 'Barlow', sans-serif; margin: 0; line-height: 1.6; }
        .hero { height: 50vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600'); background-size: cover; border-bottom: 2px solid var(--gold); }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 4rem; font-weight: 300; letter-spacing: 5px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 40px; padding: 80px 40px; max-width: 1400px; margin: 0 auto; }
        .res-card { background: var(--surface); border: 1px solid var(--border); transition: 0.5s; text-decoration: none; color: inherit; position: relative; overflow: hidden; }
        .res-card:hover { border-color: var(--gold); transform: translateY(-10px); }
        .res-content { padding: 40px; }
        .res-title { font-family: 'Cormorant Garamond', serif; font-size: 2.5rem; margin-bottom: 15px; }
        .btn-vg { display: inline-block; padding: 15px 40px; border: 1px solid var(--gold); color: white; text-transform: uppercase; letter-spacing: 2px; transition: 0.4s; margin-top: 20px; }
        .res-card:hover .btn-vg { background: var(--gold); color: black; }
        .reveal { opacity: 0; transform: translateY(30px); transition: 1s all; }
        .reveal.visible { opacity: 1; transform: translateY(0); }
    </style>
</head>
<body>
    <div class="hero"><h1 class="reveal">Ekskluzivni <span style="color:var(--gold)">Resursi</span></h1></div>
    <div class="grid">
        {% for res in resources %}
        <a href="{% url 'premium_booking:detail' res.id %}" class="res-card reveal">
            <div class="res-content">
                <span style="color:var(--gold); text-transform:uppercase; letter-spacing:4px; font-size:0.7rem;">{{ res.get_group_display }}</span>
                <h2 class="res-title">{{ res.name }}</h2>
                <div style="font-size:1.8rem; color:var(--gold);">{{ res.base_price }}€ <span style="font-size:0.8rem; color:#4a5060;">/ {{ res.get_unit_display }}</span></div>
                <div class="btn-vg">Započni Rezervaciju</div>
            </div>
        </a>
        {% endfor %}
    </div>
    <script>
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
        }, { threshold: 0.1 });
        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    </script>
</body>
</html>"""

detail_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <title>{{ resource.name }} | VISKOVIĆ GROUP</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <link rel="stylesheet" type="text/css" href="https://npmcdn.com/flatpickr/dist/themes/dark.css">
    <style>
        :root { --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830; --gold: #c9a84c; }
        body { background: var(--black); color: white; font-family: 'Barlow', sans-serif; margin: 0; }
        .main-container { display: flex; max-width: 1400px; margin: 60px auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 80px 150px rgba(0,0,0,0.8); }
        .side-info { width: 40%; padding: 80px; background: linear-gradient(180deg, var(--dark) 0%, var(--black) 100%); border-right: 1px solid var(--border); }
        .booking-panel { width: 60%; padding: 80px; }
        input, select { width: 100%; background: var(--black); border: 1px solid var(--border); padding: 20px; color: white; margin-bottom: 30px; font-size: 1.1rem; }
        .btn-submit { width: 100%; padding: 25px; background: var(--gold); color: black; border: none; font-weight: 800; text-transform: uppercase; letter-spacing: 4px; cursor: pointer; transition: 0.4s; }
        .btn-submit:hover { background: #e8c96a; transform: translateY(-5px); }
        .addon-item { border: 1px solid var(--border); padding: 15px; margin-bottom: 10px; cursor: pointer; transition: 0.3s; }
        .addon-item.selected { border-color: var(--gold); background: rgba(201,168,76,0.1); }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="side-info">
            <h1 style="font-family:'Cormorant Garamond', serif; font-size:4rem; font-weight:300;">{{ resource.name }}</h1>
            <p style="color:var(--gold); letter-spacing:5px; text-transform:uppercase;">{{ resource.get_group_display }}</p>
            <div style="font-size:3rem; margin-top:60px; font-weight:600;">{{ resource.base_price }}€</div>
        </div>
        <div class="booking-panel">
            <form id="bookingForm">
                <input type="text" id="dateTimeSelect" placeholder="Odaberite Vaš termin..." required>
                {% if addons %}<div style="margin-bottom:30px;">
                    <label style="display:block; margin-bottom:15px; color:var(--gold); text-transform:uppercase; letter-spacing:2px; font-size:0.8rem;">Dodatne Opcije</label>
                    {% for addon in addons %}
                    <div class="addon-item" onclick="toggleAddon(this)" data-id="{{ addon.id }}" data-price="{{ addon.price }}">
                        <i class="fas {{ addon.icon|default:'fa-plus' }} me-2"></i> {{ addon.name }} (+{{ addon.price }}€)
                    </div>
                    {% endfor %}
                </div>{% endif %}
                <input type="text" id="name" placeholder="Puno ime i prezime" required>
                <input type="email" id="email" placeholder="E-mail adresa" required>
                <input type="tel" id="phone" placeholder="Telefon" required>
                <select id="paymentMethod"><option value="invoice">Službena ponuda (ERP)</option><option value="revolut">Revolut Premium</option></select>
                <div style="padding:20px; background:black; margin-bottom:30px; text-align:right; font-size:1.5rem;">Ukupno: <span id="totalPrice" style="color:var(--gold); font-weight:700;">{{ resource.base_price }}€</span></div>
                <button type="submit" class="btn-submit" id="btnSubmit">Evidentiraj Rezervaciju</button>
            </form>
        </div>
    </div>
    <div id="successModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:2000; align-items:center; justify-content:center; text-align:center;">
        <div style="background:var(--surface); border:1px solid var(--gold); padding:80px;">
            <i class="fas fa-check-circle" style="font-size:5rem; color:var(--gold); margin-bottom:30px;"></i>
            <h2 style="font-family:'Cormorant Garamond', serif; font-size:3rem;">Rezervacija Uspješna</h2>
            <p>Broj rezervacije: <strong id="resNo"></strong></p>
            <a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block; text-decoration:none; margin-top:30px;">Zatvori</a>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script>
        let selectedAddons = [];
        let basePrice = parseFloat("{{ resource.base_price }}");
        flatpickr("#dateTimeSelect", { enableTime: true, dateFormat: "Y-m-d H:i", minDate: "today", theme: "dark" });
        function toggleAddon(el) {
            el.classList.toggle('selected');
            const id = el.dataset.id;
            const price = parseFloat(el.dataset.price);
            if(el.classList.contains('selected')) selectedAddons.push({id, price});
            else selectedAddons = selectedAddons.filter(a => a.id !== id);
            let total = basePrice; selectedAddons.forEach(a => total += a.price);
            document.getElementById('totalPrice').innerText = total.toFixed(2) + '€';
        }
        document.getElementById('bookingForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSubmit'); btn.disabled = true; btn.innerText = "SINKRONIZACIJA...";
            const dtVal = document.getElementById('dateTimeSelect').value;
            fetch('/premium/api/submit/', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    resource_id: "{{ resource.id }}", date: dtVal.split(' ')[0], time: dtVal.split(' ')[1],
                    name: document.getElementById('name').value, email: document.getElementById('email').value,
                    phone: document.getElementById('phone').value, payment_method: document.getElementById('paymentMethod').value,
                    addons: selectedAddons.map(a => a.id)
                })
            }).then(r => r.json()).then(data => {
                if(data.status === 'success') { document.getElementById('resNo').innerText = data.booking_number; document.getElementById('successModal').style.display = 'flex'; }
                else { alert(data.error); btn.disabled = false; btn.innerText = "Evidentiraj Rezervaciju"; }
            });
        });
    </script>
</body>
</html>"""

# ==============================================================================
# 7. ZAPISIVANJE DATOTEKA
# ==============================================================================
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content) # Varijabla je sada definirana iznad!
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

# ==============================================================================
# 8. KONFIGURACIJA I RESTART (KIRURŠKI PRECIZNO)
# ==============================================================================
print("🔄 Konfiguriranje Django sustava...")

# Settings update
settings_path = BASE_DIR / PROJECT_NAME / 'settings.py'
with open(settings_path, 'r') as f: s_data = f.read()
if f"'{APP_NAME}'" not in s_data:
    s_data = s_data.replace("INSTALLED_APPS = [", f"INSTALLED_APPS = [\n    '{APP_NAME}',")
    with open(settings_path, 'w') as f: f.write(s_data)

# Main Urls update
main_urls_path = BASE_DIR / PROJECT_NAME / 'urls.py'
with open(main_urls_path, 'r') as f: u_data = f.read()
if f"'{APP_NAME}.urls'" not in u_data:
    u_data = u_data.replace("urlpatterns = [", f"urlpatterns = [\n    path('premium/', include('{APP_NAME}.urls')),")
    with open(main_urls_path, 'w') as f: f.write(u_data)

# Migracije putem shell-a (sigurnije)
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

# Čišćenje porta i dozvola
os.system("fuser -k 8000/tcp > /dev/null 2>&1")
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*80)
print("✨ SUSTAV JE UJEDINJEN. Obećana zemlja je online na /premium/.")
print("="*80)
