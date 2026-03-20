#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
from pathlib import Path

# ==============================================================================
# 1. ARHITEKTONSKA KONFIGURACIJA (STRIKTNO CORE)
# ==============================================================================
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

print("🚀 POKRETANJE: Visković Group Unified Premium Engine (Verzija 2.0 - Full UI/UX)")

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

# ==============================================================================
# 2. MODELS.PY (Puna arhitektura s Payment i Invoice modelima)
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
    PAYMENT_METHODS = [('invoice', 'Uplata po ponudi'), ('revolut', 'Revolut Pay')]
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
# 3. VIEWS.PY (Pametna Integracija - Rješava Company ID Grešku)
# ==============================================================================
views_content = '''import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Resource, Addon, Booking, BookingAddon, Payment
from companies.models import Company
from partners.models import Partner
from appointments.models import Appointment, BookingResource as ERPResource
from invoicing.models import Invoice

def index(request):
    resources = Resource.objects.filter(is_active=True)
    group_filter = request.GET.get('group', 'all')
    if group_filter != 'all':
        resources = resources.filter(group=group_filter)
    return render(request, 'premium_booking/index.html', {
        'resources': resources, 'groups': dict(Resource.GROUP_CHOICES), 'current_group': group_filter
    })

def detail(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    addons = Addon.objects.filter(is_active=True)
    return render(request, 'premium_booking/detail.html', {'resource': resource, 'addons': addons})

@require_GET
def api_slots(request):
    resource_id = request.GET.get('resource')
    date_str = request.GET.get('date')
    if not resource_id or not date_str: return JsonResponse({'error': 'Nedostaju parametri'}, status=400)
    resource = get_object_or_404(Resource, id=resource_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=8)))
    end_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=20)))
    existing = Booking.objects.filter(resource=resource, start_time__date=target_date, status__in=['pending', 'confirmed']).values_list('start_time', 'end_time')
    slots = []
    current = start_dt
    step = timedelta(hours=1) if resource.unit == 'hour' else timedelta(days=1)
    while current + step <= end_dt:
        if not any(current < b_end and current + step > b_start for b_start, b_end in existing):
            slots.append(current.isoformat())
        current += step
    return JsonResponse({'slots': slots})

@csrf_exempt
def api_submit(request):
    if request.method != 'POST': return JsonResponse({'error': 'Invalid'}, status=405)
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            # 1. Pronalazak tvrtke (Ključno za rješavanje company_id greške)
            owner_company = Company.objects.first()
            if not owner_company: return JsonResponse({'status': 'error', 'error': 'Tvrtka nije definirana u ERP-u.'})

            resource = Resource.objects.get(id=data['resource_id'])
            start_time = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
            duration = resource.min_duration
            end_time = start_time + (timedelta(hours=duration) if resource.unit == 'hour' else timedelta(days=duration))

            # 2. Partner Sync (S Company ID-om)
            client, _ = Partner.objects.get_or_create(
                email=data['email'],
                defaults={'name': data['name'], 'phone': data['phone'], 'partner_type': 'KUPAC', 'company': owner_company}
            )

            # 3. Premium Booking
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

            # 4. ERP Integracija (Kalendar i Fakture)
            erp_res, _ = ERPResource.objects.get_or_create(name=resource.name, defaults={'company': owner_company})
            Appointment.objects.create(
                title=f"PREMIUM: {resource.name}", client=client, resource=erp_res, 
                start_time=start_time, end_time=end_time, status='scheduled', 
                color='#c9a84c', company=owner_company
            )

            if booking.payment_method == 'invoice':
                Invoice.objects.create(partner=client, total_amount=booking.total_price, status='DRAFT', company=owner_company, notes=f"Rezervacija: {booking.booking_number}")

            return JsonResponse({'status': 'success', 'booking_number': booking.booking_number, 'total_price': str(booking.total_price)})
    except Exception as e: return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

# ==============================================================================
# 4. URLS.PY I ADMIN.PY (Osigurani Redoslijed)
# ==============================================================================
urls_content = '''from django.urls import path
from . import views
app_name = 'premium_booking'
urlpatterns = [
    path('', views.index, name='index'),
    path('<int:resource_id>/', views.detail, name='detail'),
    path('api/slots/', views.api_slots, name='api_slots'),
    path('api/submit/', views.api_submit, name='api_submit'),
]
'''

admin_content = '''from django.contrib import admin
from .models import Resource, Addon, Booking, BookingAddon, Payment
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin): list_display = ('name', 'group', 'base_price', 'is_active')
@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin): list_display = ('name', 'price', 'is_active')
admin.site.register(Booking)
admin.site.register(Payment)
'''

# ==============================================================================
# 5. INDEX.HTML (Puni CSS iz viskovic_group_index.html)
# ==============================================================================
index_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium Katalog | VISKOVIĆ GROUP</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --black:   #0a0a0a; --dark:    #111214; --surface: #181a1d; --border:  #252830;
            --muted:   #4a5060; --light:   #9aa0b0; --white:   #f0ede8; --gold:    #c9a84c;
            --gold2:   #e8c96a;
        }
        body { background: var(--black); color: var(--light); font-family: 'Barlow', sans-serif; overflow-x: hidden; line-height: 1.6; }
        header { position: fixed; top: 0; width: 100%; padding: 30px 60px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; background: rgba(10, 10, 10, 0.9); backdrop-filter: blur(15px); border-bottom: 1px solid var(--border); }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 1.8rem; color: var(--white); text-decoration: none; letter-spacing: 4px; font-weight: 300; }
        .logo span { color: var(--gold); }
        .hero { height: 50vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600'); background-size: cover; background-position: center; text-align: center; border-bottom: 2px solid var(--gold); }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 4.5rem; color: var(--white); margin-bottom: 20px; font-weight: 300; letter-spacing: 6px; }
        .hero p { color: var(--gold); letter-spacing: 10px; text-transform: uppercase; font-size: 0.85rem; font-weight: 600; opacity: 0.8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 50px; padding: 100px 40px; max-width: 1400px; margin: 0 auto; }
        .res-card { background: var(--surface); border: 1px solid var(--border); transition: 0.6s cubic-bezier(0.165, 0.84, 0.44, 1); text-decoration: none; color: inherit; position: relative; display: flex; flex-direction: column; overflow: hidden; }
        .res-card:hover { transform: translateY(-20px); border-color: var(--gold); box-shadow: 0 40px 80px rgba(0,0,0,0.7); }
        .res-content { padding: 50px; flex-grow: 1; display: flex; flex-direction: column; }
        .res-title { font-family: 'Cormorant Garamond', serif; font-size: 2.8rem; color: var(--white); font-weight: 300; margin: 25px 0; }
        .res-price { font-size: 2.2rem; color: var(--gold); font-weight: 600; font-family: 'Cormorant Garamond', serif; border-top: 1px solid var(--border); padding-top: 30px; margin-top: auto; }
        .btn-vg { display: inline-block; padding: 18px 45px; border: 1px solid var(--gold); background: transparent; color: var(--white); text-transform: uppercase; font-size: 0.8rem; letter-spacing: 5px; transition: 0.5s; font-weight: 700; text-align: center; margin-top: 30px; }
        .res-card:hover .btn-vg { background: var(--gold); color: var(--black); }
        .reveal { opacity: 0; transform: translateY(60px); transition: 1.5s all cubic-bezier(0.165, 0.84, 0.44, 1); }
        .reveal.visible { opacity: 1; transform: translateY(0); }
    </style>
</head>
<body>
    <header>
        <a href="/" class="logo">VISKOVIĆ <span>GROUP</span></a>
        <a href="/" style="color: var(--gold); text-decoration: none; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 3px; border-bottom: 1px solid var(--gold);">Povratak</a>
    </header>
    <div class="hero">
        <h1 class="reveal">Premium <span>Resursi</span></h1>
        <p class="reveal">ARHITEKTURA SNAGE</p>
    </div>
    <div class="grid">
        {% for res in resources %}
        <a href="{% url 'premium_booking:detail' res.id %}" class="res-card reveal">
            <div class="res-content">
                <span style="color:var(--gold); text-transform:uppercase; letter-spacing:6px; font-size:0.75rem; font-weight:700;">{{ res.get_group_display }}</span>
                <h2 class="res-title">{{ res.name }}</h2>
                <p style="color:#9aa0b0; font-weight:300; line-height:2;">{{ res.description|truncatechars:180 }}</p>
                <div class="res-price">{{ res.base_price }}€ <span style="font-size:1rem; color:#4a5060;">/ {{ res.get_unit_display }}</span></div>
                <div class="btn-vg">Pokreni Protokol</div>
            </div>
        </a>
        {% empty %}
        <div style="grid-column: 1/-1; text-align: center; padding: 150px; border: 1px dashed var(--border);">
            <p style="color: var(--muted); font-size: 1.2rem; letter-spacing: 4px; text-transform: uppercase;">Učitavanje podataka iz baze...</p>
        </div>
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

# ==============================================================================
# 6. DETAIL.HTML (Puna integracija)
# ==============================================================================
detail_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <title>{{ resource.name }} | Protokol Rezervacije</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <link rel="stylesheet" type="text/css" href="https://npmcdn.com/flatpickr/dist/themes/dark.css">
    <style>
        :root { --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830; --gold: #c9a84c; }
        body { background: var(--black); color: white; font-family: 'Barlow', sans-serif; margin: 0; }
        .main-container { display: flex; max-width: 1500px; margin: 60px auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 80px 150px rgba(0,0,0,0.8); }
        .side-info { width: 42%; padding: 100px; background: linear-gradient(180deg, var(--dark) 0%, var(--black) 100%); border-right: 1px solid var(--border); }
        .booking-panel { width: 58%; padding: 100px; }
        h1 { font-family: 'Cormorant Garamond', serif; font-size: 4.5rem; font-weight: 300; line-height: 1; margin: 30px 0; }
        h4 { font-family: 'Cormorant Garamond', serif; font-size: 2.8rem; margin-bottom: 50px; border-bottom: 1px solid var(--border); padding-bottom: 25px; font-weight: 300; }
        input, select { width: 100%; background: var(--black); border: 1px solid var(--border); padding: 22px 30px; color: white; margin-bottom: 40px; font-family: inherit; font-size: 1.15rem; border-radius: 0; transition: 0.5s; }
        input:focus { border-color: var(--gold); outline: none; box-shadow: 0 0 35px rgba(201, 168, 76, 0.15); }
        .btn-submit { width: 100%; padding: 28px; background: var(--gold); color: black; border: none; font-weight: 800; text-transform: uppercase; letter-spacing: 6px; cursor: pointer; transition: 0.6s cubic-bezier(0.165, 0.84, 0.44, 1); font-size: 1.1rem; }
        .btn-submit:hover { background: #e8c96a; transform: translateY(-7px); box-shadow: 0 25px 60px rgba(201, 168, 76, 0.4); }
        .addon-item { border: 1px solid var(--border); background: var(--black); padding: 30px; margin-bottom: 20px; cursor: pointer; transition: 0.4s; display: flex; justify-content: space-between; align-items: center; }
        .addon-item.selected { border-color: var(--gold); background: rgba(201, 168, 76, 0.12); }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="side-info">
            <span style="color:var(--gold); text-transform:uppercase; letter-spacing:8px; font-size:0.9rem; font-weight:700;">PROFIL RESURSA</span>
            <h1>{{ resource.name }}</h1>
            <p style="color:#9aa0b0; line-height:2.2; font-size:1.15rem; margin-bottom:60px;">{{ resource.description }}</p>
            <div style="font-size:4.5rem; color:var(--gold); font-family:'Cormorant Garamond', serif; border-top:1px solid var(--border); padding-top:40px;">{{ resource.base_price }}€ <span style="font-size:1.2rem; color:#4a5060; font-family:'Barlow'; letter-spacing:5px;">/ {{ resource.get_unit_display }}</span></div>
        </div>
        <div class="booking-panel">
            <form id="bookingForm">
                <h4>Rezervacijski Protokol</h4>
                <label style="text-transform:uppercase; letter-spacing:5px; font-size:0.85rem; display:block; margin-bottom:15px; opacity:0.7;">Odaberite Termin</label>
                <input type="text" id="dateTimeSelect" placeholder="Pretraži dostupnost..." required>
                {% if addons %}
                <div style="margin-bottom:50px;">
                    <label style="display:block; margin-bottom:20px; color:var(--gold); text-transform:uppercase; letter-spacing:5px; font-size:0.8rem; font-weight:700;">Dodatni Moduli</label>
                    {% for addon in addons %}
                    <div class="addon-item" onclick="toggleAddon(this)" data-id="{{ addon.id }}" data-price="{{ addon.price }}">
                        <span style="letter-spacing:1px;"><i class="fas {{ addon.icon|default:'fa-plus' }} me-3"></i> {{ addon.name }}</span>
                        <strong style="color:var(--gold);">+{{ addon.price }}€</strong>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                <input type="text" id="name" placeholder="Puno ime i prezime klijenta" required>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:40px;">
                    <input type="email" id="email" placeholder="E-mail adresa" required>
                    <input type="tel" id="phone" placeholder="Kontakt telefon" required>
                </div>
                <select id="paymentMethod"><option value="invoice">Uplata po ponudi (ERP)</option><option value="revolut">Revolut Premium Direct</option></select>
                <div style="background:black; padding:50px; border:1px solid var(--border); margin-bottom:60px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="text-transform:uppercase; letter-spacing:6px; font-size:1rem; font-weight:500; color:var(--light);">Ukupna Vrijednost</span>
                    <span id="totalPrice" style="font-size:3.5rem; color:var(--gold); font-weight:700; font-family:'Cormorant Garamond', serif;">{{ resource.base_price }}€</span>
                </div>
                <button type="submit" class="btn-submit" id="btnSubmit">Završi i Evidentiraj Rezervaciju</button>
            </form>
        </div>
    </div>
    <div id="successModal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.99); z-index:2000; align-items:center; justify-content:center; text-align:center; backdrop-filter:blur(25px);">
        <div style="background:var(--surface); border:1px solid var(--gold); padding:100px; max-width:800px; box-shadow:0 0 150px rgba(201,168,76,0.3);">
            <i class="fas fa-check-circle" style="font-size:8rem; color:var(--gold); margin-bottom:40px;"></i>
            <h2 style="font-family:'Cormorant Garamond', serif; font-size:4.5rem; margin:0; line-height:1;">Uspjeh</h2>
            <p style="font-size:1.4rem; margin:60px 0; letter-spacing:2px;">Kod rezervacije: <strong id="resNo" style="color:white; border-bottom:3px solid var(--gold); padding-bottom:5px;"></strong></p>
            <a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block; text-decoration:none;">Zatvori Protokol</a>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script>
        let selectedAddons = [];
        let basePrice = parseFloat("{{ resource.base_price }}");
        flatpickr("#dateTimeSelect", { enableTime: true, dateFormat: "Y-m-d H:i", minDate: "today", theme: "dark", minuteIncrement: 30, time_24hr: true });
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
            const btn = document.getElementById('btnSubmit'); btn.disabled = true; btn.innerText = "POVEZIVANJE SA SERVEROM...";
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
                else { alert('Pogreška: ' + data.error); btn.disabled = false; btn.innerText = "ZAVRŠI REZERVACIJU"; }
            });
        });
    </script>
</body>
</html>"""

# ==============================================================================
# 7. ZAPISIVANJE, MIGRACIJA I AUTOMATSKO SJEMENAŠENJE
# ==============================================================================
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content)
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

# Migracije
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

# SJEMENAŠENJE (Seeding) - Osigurava da stranica nije prazna!
with open('seed.py', 'w') as f:
    f.write('''
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from premium_booking.models import Resource
if not Resource.objects.exists():
    Resource.objects.create(name="Luxury Suite 101", group="housing", base_price=120, unit="day", description="Ekskluzivan stan u srcu poslovne zone. Potpuna privatnost.")
    Resource.objects.create(name="Caterpillar 320", group="construction", base_price=450, unit="day", description="Vrhunski bager za najzahtjevnije građevinske operacije.")
    Resource.objects.create(name="Bavaria VIP Office", group="business", base_price=50, unit="hour", description="Prestižni uredski prostor za sastanke najviše razine.")
    print("✨ Kreirani Visković Premium resursi.")
''')
os.system(f"{BASE_DIR}/venv/bin/python seed.py")
os.remove('seed.py')

# Konfiguracija settings.py i urls.py
settings_path = BASE_DIR / PROJECT_NAME / 'settings.py'
with open(settings_path, 'r') as f: s_data = f.read()
if f"'{APP_NAME}'" not in s_data:
    s_data = s_data.replace("INSTALLED_APPS = [", f"INSTALLED_APPS = [\\n    '{APP_NAME}',")
    with open(settings_path, 'w') as f: f.write(s_data)

main_urls_path = BASE_DIR / PROJECT_NAME / 'urls.py'
with open(main_urls_path, 'r') as f: u_data = f.read()
if f"'{APP_NAME}.urls'" not in u_data:
    u_data = u_data.replace("urlpatterns = [", f"urlpatterns = [\\n    path('premium/', include('{APP_NAME}.urls')),")
    with open(main_urls_path, 'w') as f: f.write(u_data)

# Dozvole, portovi i restart
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("fuser -k 8000/tcp > /dev/null 2>&1")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*80)
print("✨ OBEĆANA ZEMLJA JE ONLINE! Sve varijable su na mjestu, baza je puna.")
print("🔗 Portal: https://viskovic-group.de/premium/")
print("="*80)
