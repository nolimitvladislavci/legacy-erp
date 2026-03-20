#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from pathlib import Path

# ==============================================================================
# 1. KONFIGURACIJA
# ==============================================================================
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

# ==============================================================================
# 2. DEFINICIJA SADRŽAJA - SVE KLASE SU TU (NEMA IMPORT ERRORA)
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
    created_at = models.DateTimeField(auto_now_add=True)
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
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
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
    method = models.CharField(max_length=20, default='invoice')
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
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
        with transaction.atomic():
            owner_company = Company.objects.first()
            if not owner_company: return JsonResponse({'error': 'No company found'}, status=400)

            client = Partner.objects.filter(email=data['email'], company=owner_company).first()
            if not client:
                try:
                    client = Partner.objects.create(
                        name=data['name'], email=data['email'], phone=data['phone'],
                        company=owner_company, partner_type='KUPAC'
                    )
                except:
                    client = Partner.objects.filter(company=owner_company).first()

            res = Resource.objects.get(id=data['resource_id'])
            start = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
            end = start + timedelta(days=res.min_duration)

            booking = Booking.objects.create(
                resource=res, guest_name=data['name'], guest_email=data['email'],
                guest_phone=data['phone'], start_time=start, end_time=end, total_price=res.base_price
            )

            # ERP SINKRONIZACIJA
            erp_res, _ = ERPResource.objects.get_or_create(name=res.name, defaults={'company': owner_company})
            Appointment.objects.create(
                title=f"PREMIUM: {res.name}", client=client, resource=erp_res,
                start_time=start, end_time=end, status='scheduled', color='#c9a84c', company=owner_company
            )
            Invoice.objects.create(partner=client, total_amount=booking.total_price, company=owner_company, status='DRAFT')

            return JsonResponse({'status': 'success', 'booking_number': booking.booking_number})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)
'''

urls_content = "from django.urls import path\nfrom . import views\napp_name='premium_booking'\nurlpatterns=[path('', views.index, name='index'), path('<int:resource_id>/', views.detail, name='detail'), path('api/submit/', views.api_submit, name='api_submit'),]"

admin_content = "from django.contrib import admin\nfrom .models import Resource, Addon, Booking, BookingAddon, Payment\nadmin.site.register(Resource)\nadmin.site.register(Addon)\nadmin.site.register(Booking)\nadmin.site.register(BookingAddon)\nadmin.site.register(Payment)"

# --- LUKSUZNI TEMPLATES (PUNI KOD) ---
index_template = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Katalog | VISKOVIĆ GROUP</title><link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet"><style>:root{--gold:#c9a84c;--black:#0a0a0a;--surface:#181a1d;--border:#252830;}body{background:var(--black);color:white;font-family:'Barlow',sans-serif;margin:0;}header{padding:40px 60px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;background:rgba(10,10,10,0.9);}.hero{height:40vh;display:flex;flex-direction:column;justify-content:center;align-items:center;background:linear-gradient(rgba(0,0,0,0.8),rgba(0,0,0,0.8)),url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600');background-size:cover;border-bottom:2px solid var(--gold);}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:50px;padding:80px 60px;max-width:1400px;margin:0 auto;}.res-card{background:var(--surface);border:1px solid var(--border);transition:0.5s;text-decoration:none;color:inherit;padding:40px;}.res-card:hover{border-color:var(--gold);transform:translateY(-10px);}.btn-vg{display:inline-block;padding:15px 45px;border:1px solid var(--gold);color:white;text-transform:uppercase;letter-spacing:3px;margin-top:30px;transition:0.4s;font-weight:600;}.res-card:hover .btn-vg{background:var(--gold);color:black;}</style></head><body><header><div style="font-family:'Cormorant Garamond',serif;font-size:1.8rem;letter-spacing:4px;">VISKOVIĆ <span style="color:var(--gold)">GROUP</span></div><a href="/" style="color:var(--gold);text-decoration:none;text-transform:uppercase;font-size:0.8rem;letter-spacing:2px;">Povratak</a></header><div class="hero"><h1>Ekskluzivni <span style="color:var(--gold);font-style:italic;">Resursi</span></h1></div><div class="grid">{% for res in resources %}<a href="{% url 'premium_booking:detail' res.id %}" class="res-card"><div><span style="color:var(--gold);text-transform:uppercase;letter-spacing:4px;font-size:0.7rem;">{{ res.get_group_display }}</span><h2 style="font-family:'Cormorant Garamond',serif;font-size:2.5rem;margin:15px 0;">{{ res.name }}</h2><p style="color:#9aa0b0;">{{ res.description|truncatechars:150 }}</p><div style="font-size:2rem;color:var(--gold);border-top:1px solid var(--border);padding-top:20px;margin-top:20px;">{{ res.base_price }}€</div><div class="btn-vg">Rezerviraj</div></div></a>{% endfor %}</div></body></html>"""

detail_template = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Rezervacija | VISKOVIĆ GROUP</title><link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css"><link rel="stylesheet" type="text/css" href="https://npmcdn.com/flatpickr/dist/themes/dark.css"><style>:root{--gold:#c9a84c;--black:#0a0a0a;--surface:#181a1d;--border:#252830;}body{background:var(--black);color:white;font-family:'Barlow',sans-serif;margin:0;}.main-container{display:flex;max-width:1400px;margin:60px auto;background:var(--surface);border:1px solid var(--border);box-shadow:0 80px 150px rgba(0,0,0,0.8);}.side-info{width:40%;padding:100px;background:linear-gradient(180deg,#111214 0%,#0a0a0a 100%);border-right:1px solid var(--border);}.booking-panel{width:60%;padding:100px;}input,select{width:100%;background:var(--black);border:1px solid var(--border);padding:22px;color:white;margin-bottom:40px;font-size:1.1rem;}.btn-submit{width:100%;padding:25px;background:var(--gold);color:black;border:none;font-weight:800;text-transform:uppercase;letter-spacing:5px;cursor:pointer;transition:0.5s;}.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.98);z-index:2000;align-items:center;justify-content:center;text-align:center;}</style></head><body><div class="main-container"><div class="side-info"><h1>{{ resource.name }}</h1><p style="color:var(--gold);letter-spacing:5px;text-transform:uppercase;">{{ resource.get_group_display }}</p><div style="font-size:3.5rem;margin-top:60px;">{{ resource.base_price }}€</div></div><div class="booking-panel"><form id="bookingForm"><input type="text" id="dt" placeholder="Odaberite termin..." required><input type="text" id="name" placeholder="Puno ime" required><input type="email" id="email" placeholder="E-mail" required><input type="tel" id="phone" placeholder="Telefon" required><button type="submit" class="btn-submit" id="btn">Dovrši Rezervaciju</button></form></div></div><div class="modal" id="modal"><div style="background:var(--surface);border:1px solid var(--gold);padding:100px;"><h2>USPJEH</h2><p>Rezervacija: <strong id="resNo"></strong></p><a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block;text-decoration:none;margin-top:30px;">Zatvori</a></div></div><script src="https://cdn.jsdelivr.net/npm/flatpickr"></script><script>flatpickr("#dt",{enableTime:true,dateFormat:"Y-m-d H:i",minDate:"today",theme:"dark"});document.getElementById('bookingForm').addEventListener('submit',function(e){e.preventDefault();const b=document.getElementById('btn');b.disabled=true;b.innerText="OBRADA...";fetch('/premium/api/submit/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resource_id:"{{resource.id}}",date:document.getElementById('dt').value.split(' ')[0],time:document.getElementById('dt').value.split(' ')[1],name:document.getElementById('name').value,email:document.getElementById('email').value,phone:document.getElementById('phone').value})}).then(r=>r.json()).then(d=>{if(d.booking_number){document.getElementById('resNo').innerText=d.booking_number;document.getElementById('modal').style.display='flex';}else{alert(d.error);b.disabled=false;}});});</script></body></html>"""

# ==============================================================================
# 4. IZVRŠAVANJE
# ==============================================================================
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content)
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

# --- DJANGO INTEGRACIJA ---
print("🔄 Provođenje migracija...")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

# SEEDING
with open('seed.py', 'w') as f:
    f.write('''
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from premium_booking.models import Resource
if not Resource.objects.exists():
    Resource.objects.create(name="Bager Caterpillar 320", group="construction", base_price=450, unit="day", description="Vrhunski stroj.")
    Resource.objects.create(name="Luxury Suite 101", group="housing", base_price=120, unit="day", description="Ekskluzivno.")
    print("✨ Podaci učitani.")
''')
os.system(f"{BASE_DIR}/venv/bin/python seed.py && rm seed.py")

os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("fuser -k 8000/tcp > /dev/null 2>&1")
os.system("supervisorctl restart fina-connect")

print("\n✨ SUSTAV JE OPERATIVAN. Bager te čeka na linku.")
print("🔗 https://viskovic-group.de/premium/")
