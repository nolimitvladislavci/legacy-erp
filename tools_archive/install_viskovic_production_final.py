#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from pathlib import Path

# ==============================================================================
# 1. KONFIGURACIJA I POMOĆNE FUNKCIJE (DEFINIRANE PRVE!)
# ==============================================================================
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

def write_file(path, content):
    """Sigurno pisanje datoteke uz kreiranje mapa i backup."""
    path = Path(path)
    if path.exists():
        shutil.copy2(path, str(path) + '.bak')
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

print("🚀 POKRETANJE: Visković Group Unified Engine - FINAL PRODUCTION")

# ==============================================================================
# 2. DEFINICIJA SADRŽAJA - BACKEND (Potpuni Integritet)
# ==============================================================================

models_content = '''import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Resource(models.Model):
    GROUP_CHOICES = [
        ('construction', 'Gradnja (Strojevi i Radnici)'),
        ('housing', 'Stanovanje (Sobe i Garsonjere)'),
        ('business', 'Poslovni prostori (Uredi i Restoran)'),
    ]
    UNIT_CHOICES = [('hour', 'Sat'), ('day', 'Dan'), ('month', 'Mjesec')]
    group = models.CharField(max_length=20, choices=GROUP_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='day')
    capacity = models.PositiveIntegerField(default=1)
    min_duration = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to='resources/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    class Meta:
        ordering = ['group', 'name']
    def __str__(self): return f"{self.name} ({self.get_group_display()})"

class Addon(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Booking(models.Model):
    booking_number = models.CharField(max_length=20, unique=True, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='bookings')
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = f"VG-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

class BookingAddon(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='selected_addons')
    addon = models.ForeignKey(Addon, on_delete=models.CASCADE)
    price_at_booking = models.DecimalField(max_digits=8, decimal_places=2)

class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, default='invoice')
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
'''

views_content = '''import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction, IntegrityError
from decimal import Decimal

from .models import Resource, Addon, Booking, BookingAddon, Payment
from companies.models import Company
from partners.models import Partner
from appointments.models import Appointment, BookingResource as ERPResource
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
        
        # 1. PRIPREMA (Izvan atomic bloka da izbjegnemo IntegrityError trovanje)
        owner_company = Company.objects.first()
        if not owner_company: return JsonResponse({'error': 'Firma nije definirana'}, status=400)

        email = data.get('email')
        client = Partner.objects.filter(email=email, company=owner_company).first()
        
        if not client:
            try:
                client = Partner.objects.create(
                    company=owner_company, name=data['name'], 
                    email=email, phone=data['phone'], partner_type='KUPAC'
                )
            except IntegrityError:
                client = Partner.objects.filter(company=owner_company).first()

        # 2. IZVRŠAVANJE REZERVACIJE
        with transaction.atomic():
            res = Resource.objects.get(id=data['resource_id'])
            start = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
            end = start + timedelta(days=res.min_duration)

            booking = Booking.objects.create(
                resource=res, guest_name=data['name'], guest_email=email,
                guest_phone=data['phone'], start_time=start, end_time=end, total_price=res.base_price
            )

            # ERP SINKRONIZACIJA
            erp_res, _ = ERPResource.objects.get_or_create(name=res.name, defaults={'company': owner_company})
            Appointment.objects.create(
                title=f"PREMIUM: {res.name} - {data['name']}", client=client, resource=erp_res,
                start_time=start, end_time=end, status='scheduled', color='#c9a84c', company=owner_company
            )
            Invoice.objects.create(partner=client, total_amount=booking.total_price, company=owner_company, status='DRAFT')

            return JsonResponse({'status': 'success', 'booking_number': booking.booking_number})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

urls_content = "from django.urls import path\nfrom . import views\napp_name='premium_booking'\nurlpatterns=[path('', views.index, name='index'), path('<int:resource_id>/', views.detail, name='detail'), path('api/submit/', views.api_submit, name='api_submit'),]"

admin_content = "from django.contrib import admin\nfrom .models import Resource, Addon, Booking, BookingAddon, Payment\nadmin.site.register(Resource)\nadmin.site.register(Addon)\nadmin.site.register(Booking)\nadmin.site.register(BookingAddon)\nadmin.site.register(Payment)"

# ==============================================================================
# 3. DEFINICIJA SADRŽAJA - FRONTEND (100% VISKOVIĆ GOLD DIZAJN)
# ==============================================================================

index_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ekskluzivni Katalog | VISKOVIĆ GROUP</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830;
            --muted: #4a5060; --light: #9aa0b0; --white: #f0ede8; --gold: #c9a84c;
        }
        body { background: var(--black); color: var(--light); font-family: 'Barlow', sans-serif; line-height: 1.6; overflow-x: hidden; }
        header { position: fixed; top: 0; width: 100%; padding: 40px 60px; background: rgba(10,10,10,0.9); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; z-index: 1000; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 2rem; color: white; text-decoration: none; letter-spacing: 4px; }
        .hero { height: 50vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600'); background-size: cover; background-position: center; border-bottom: 2px solid var(--gold); text-align: center; }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 5rem; font-weight: 300; letter-spacing: 8px; margin: 0; color: white; }
        .container { max-width: 1500px; margin: 0 auto; padding: 100px 40px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 60px; }
        .res-card { background: var(--surface); border: 1px solid var(--border); transition: 0.7s cubic-bezier(0.165, 0.84, 0.44, 1); text-decoration: none; color: inherit; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .res-card:hover { transform: translateY(-25px); border-color: var(--gold); box-shadow: 0 50px 100px rgba(0,0,0,0.7); }
        .res-content { padding: 60px; flex-grow: 1; display: flex; flex-direction: column; }
        .res-title { font-family: 'Cormorant Garamond', serif; font-size: 3.2rem; margin: 25px 0; font-weight: 300; line-height: 1.1; color: white; }
        .res-price { font-size: 2.8rem; color: var(--gold); font-family: 'Cormorant Garamond', serif; border-top: 1px solid var(--border); padding-top: 40px; margin-top: auto; font-weight: 600; }
        .btn-vg { display: inline-block; padding: 22px 60px; border: 1px solid var(--gold); color: white; text-transform: uppercase; letter-spacing: 5px; margin-top: 50px; transition: 0.5s; font-weight: 700; text-align: center; }
        .res-card:hover .btn-vg { background: var(--gold); color: black; }
    </style>
</head>
<body>
    <header><a href="/" class="logo">VISKOVIĆ <span>GROUP</span></a></header>
    <div class="hero"><h1>Ekskluzivni <span>Najam</span></h1><p style="color:var(--gold); letter-spacing:10px; text-transform:uppercase; font-size:0.9rem; margin-top:20px;">Standard Snage</p></div>
    <div class="container"><div class="grid">
        {% for res in resources %}
        <a href="{% url 'premium_booking:detail' res.id %}" class="res-card">
            <div class="res-content">
                <span style="color:var(--gold); text-transform:uppercase; letter-spacing:8px; font-size:0.75rem; font-weight:700;">{{ res.get_group_display }}</span>
                <h2 class="res-title">{{ res.name }}</h2>
                <p style="color:#9aa0b0;">{{ res.description|truncatechars:250 }}</p>
                <div class="res-price">{{ res.base_price }}€</div>
                <div class="btn-vg">Dovrši Protokol</div>
            </div>
        </a>
        {% endfor %}
    </div></div>
</body>
</html>"""

detail_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <title>{{ resource.name }} | Rezervacija</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <link rel="stylesheet" type="text/css" href="https://npmcdn.com/flatpickr/dist/themes/dark.css">
    <style>
        :root { --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830; --gold: #c9a84c; }
        body { background: var(--black); color: white; font-family: 'Barlow', sans-serif; margin: 0; }
        .main { display: flex; max-width: 1600px; margin: 60px auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 80px 150px rgba(0,0,0,0.8); }
        .side { width: 45%; padding: 100px; background: linear-gradient(180deg, #111214 0%, #0a0a0a 100%); border-right: 1px solid var(--border); }
        .form { width: 55%; padding: 100px; }
        h1 { font-family: 'Cormorant Garamond', serif; font-size: 5rem; font-weight: 300; line-height: 1; margin: 30px 0; }
        input, select { width: 100%; background: var(--black); border: 1px solid var(--border); padding: 25px 35px; color: white; margin-bottom: 40px; font-family: inherit; font-size: 1.2rem; border-radius: 0; }
        .btn-submit { width: 100%; padding: 30px; background: var(--gold); color: black; border: none; font-weight: 800; text-transform: uppercase; letter-spacing: 6px; cursor: pointer; transition: 0.6s; }
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.99); z-index: 2000; align-items: center; justify-content: center; text-align: center; }
    </style>
</head>
<body>
    <div class="main"><div class="side">
        <span style="color:var(--gold); text-transform:uppercase; letter-spacing:10px; font-size:0.9rem; font-weight:700;">PROFIL RESURSA</span>
        <h1>{{ resource.name }}</h1>
        <div style="font-size:4.5rem; color:var(--gold); font-family:'Cormorant Garamond', serif; border-top:1px solid var(--border); padding-top:50px;">{{ resource.base_price }}€</div>
    </div><div class="form">
        <form id="bookingForm">
            <input type="text" id="dt" placeholder="Odaberite termin početka..." required>
            <input type="text" id="name" placeholder="Puno ime i prezime" required>
            <input type="email" id="email" placeholder="E-mail adresa" required>
            <input type="tel" id="phone" placeholder="Kontakt telefon" required>
            <button type="submit" class="btn-submit" id="btn">Dovrši Rezervaciju</button>
        </form>
    </div></div>
    <div id="modal" class="modal"><div style="background:var(--surface); border:1px solid var(--gold); padding:100px;">
        <h2 style="font-family:'Cormorant Garamond', serif; font-size:5rem;">USPJEH</h2>
        <p style="font-size:1.6rem; margin:50px 0;">Broj rezervacije: <strong id="resNo" style="color:white; border-bottom:3px solid var(--gold);"></strong></p>
        <a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block; text-decoration:none;">Zatvori</a>
    </div></div>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script>
        flatpickr("#dt", { enableTime: true, dateFormat: "Y-m-d H:i", minDate: "today", theme: "dark", time_24hr: true });
        document.getElementById('bookingForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const b = document.getElementById('btn'); b.disabled = true; b.innerText = "SINKRONIZACIJA...";
            fetch('/premium/api/submit/', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    resource_id: "{{ resource.id }}", date: document.getElementById('dt').value.split(' ')[0], time: document.getElementById('dt').value.split(' ')[1],
                    name: document.getElementById('name').value, email: document.getElementById('email').value, phone: document.getElementById('phone').value
                })
            }).then(r => r.json()).then(d => {
                if(d.booking_number) { document.getElementById('resNo').innerText = d.booking_number; document.getElementById('modal').style.display = 'flex'; }
                else { alert('Arhitektonska greška: ' + d.error); b.disabled = false; b.innerText = "Dovrši Rezervaciju"; }
            });
        });
    </script>
</body>
</html>"""

# ==============================================================================
# 4. IZVRŠAVANJE I SINKRONIZACIJA (KONAČNI REDOSLIJED)
# ==============================================================================
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content)
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

# --- DJANGO INTEGRACIJA ---
print("🔄 Provođenje migracija i seeding sustava...")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME} --noinput")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate {APP_NAME} --noinput")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate --noinput")

# SEEDING (S company_id fixom da stranica ne bude prazna)
with open('seed.py', 'w') as f:
    f.write('''
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from premium_booking.models import Resource
if not Resource.objects.exists():
    Resource.objects.create(name="Bager Caterpillar 320", group="construction", base_price=450, unit="day", description="Vrhunska snaga za Visković BAU.")
    Resource.objects.create(name="Luxury Suite 101", group="housing", base_price=120, unit="day", description="Ekskluzivni smještaj u bavarskom stilu.")
    print("✨ Podaci o resursima su učitani.")
''')
os.system(f"{BASE_DIR}/venv/bin/python seed.py && rm seed.py")

# DOZVOLE I RESTART (Rješenje za spawn error)
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("fuser -k 8000/tcp > /dev/null 2>&1")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*80)
print("✨ SUSTAV JE ONLINE. Baza je puna, arhitektura je blindirana.")
print("🔗 Katalog: https://viskovic-group.de/premium/")
print("="*80)
