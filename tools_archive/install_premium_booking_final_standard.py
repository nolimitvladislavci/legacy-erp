#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import uuid
from pathlib import Path

# 1. OSIGURAVANJE DJANGO OKRUŽENJA (PRVO I OSNOVNO)
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'{PROJECT_NAME}.settings')
sys.path.append(str(BASE_DIR))

# Definiranje varijabli prije bilo kakvog zapisivanja
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

print("🚀 POKRETANJE: Visković Group Premium Booking System (Punokrvni UX + Backend)")

# ==========================================
# 2. MODELS.PY (Kompletna Arhitektura)
# ==========================================
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
    name = models.CharField(max_length=200, verbose_name='Naziv resursa')
    description = models.TextField(blank=True, verbose_name='Opis')
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Osnovna cijena (€)')
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='day', verbose_name='Jedinica naplate')
    capacity = models.PositiveIntegerField(default=1, verbose_name='Kapacitet (osobe)')
    min_duration = models.PositiveIntegerField(default=1, verbose_name='Minimalno trajanje')
    image = models.ImageField(upload_to='resources/', blank=True, null=True, verbose_name='Premium Slika')
    is_active = models.BooleanField(default=True, verbose_name='Vidljivo klijentima')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group', 'name']
        verbose_name = 'Resurs'
        verbose_name_plural = 'Resursi'
        
    def __str__(self):
        return f"{self.name} ({self.get_group_display()})"

class Addon(models.Model):
    name = models.CharField(max_length=100, verbose_name='Naziv dodatka')
    description = models.TextField(blank=True, verbose_name='Opis')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Cijena (€)')
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome klasa (npr. 'fa-wifi')")
    applicable_groups = models.CharField(max_length=50, blank=True, help_text="Odvojite zarezom: housing,business")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Dodatna usluga'
        verbose_name_plural = 'Dodatne usluge'
        
    def __str__(self):
        return f"{self.name} (+{self.price}€)"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Čeka potvrdu'),
        ('confirmed', 'Potvrđeno / Plaćeno'),
        ('cancelled', 'Otkazano'),
    ]
    PAYMENT_METHODS = [
        ('invoice', 'Uplata po ponudi'),
        ('revolut', 'Revolut Pay'),
    ]
    booking_number = models.CharField(max_length=20, unique=True, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    guest_name = models.CharField(max_length=200, verbose_name='Ime i prezime')
    guest_email = models.EmailField(verbose_name='Email')
    guest_phone = models.CharField(max_length=20, verbose_name='Telefon')
    whatsapp_number = models.CharField(max_length=20, blank=True, verbose_name='WhatsApp')
    start_time = models.DateTimeField(verbose_name='Početak')
    end_time = models.DateTimeField(verbose_name='Kraj')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Ukupni iznos (€)')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='invoice')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rezervacija'
        verbose_name_plural = 'Rezervacije'

    def save(self, *args, **kwargs):
        if not self.booking_number:
            import uuid
            self.booking_number = f"VG-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_number} - {self.guest_name}"

class BookingAddon(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='selected_addons')
    addon = models.ForeignKey(Addon, on_delete=models.CASCADE)
    price_at_booking = models.DecimalField(max_digits=8, decimal_places=2)

class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='invoice')
    invoice_number = models.CharField(max_length=50, unique=True)
    issued_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
'''

# ==========================================
# 3. VIEWS.PY (Pametna Logika)
# ==========================================
views_content = '''import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
from decimal import Decimal
from .models import Resource, Addon, Booking, BookingAddon, Invoice, Payment

def index(request):
    resources = Resource.objects.filter(is_active=True)
    group_filter = request.GET.get('group', 'all')
    if group_filter != 'all':
        resources = resources.filter(group=group_filter)
    return render(request, 'premium_booking/index.html', {
        'resources': resources, 
        'groups': dict(Resource.GROUP_CHOICES),
        'current_group': group_filter
    })

def detail(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    addons = Addon.objects.filter(is_active=True)
    return render(request, 'premium_booking/detail.html', {'resource': resource, 'addons': addons})

@require_GET
def api_slots(request):
    resource_id = request.GET.get('resource')
    date_str = request.GET.get('date')
    if not resource_id or not date_str: return JsonResponse({'error': 'Fale parametri'}, status=400)
    
    resource = get_object_or_404(Resource, id=resource_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    start_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=8)))
    end_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=20)))
    
    existing = Booking.objects.filter(
        resource=resource, start_time__date=target_date, status__in=['pending', 'confirmed']
    ).values_list('start_time', 'end_time')
    
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
    if request.method != 'POST': return JsonResponse({'error': 'Metoda nije dozvoljena'}, status=405)
    try:
        data = json.loads(request.body)
        resource = get_object_or_404(Resource, id=data['resource_id'])
        start_time = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
        
        duration = resource.min_duration
        if resource.unit == 'hour': end_time = start_time + timedelta(hours=duration)
        elif resource.unit == 'day': end_time = start_time + timedelta(days=duration)
        else: end_time = start_time + timedelta(days=30*duration)
        
        total_price = resource.base_price * Decimal(str(duration))
        
        booking = Booking.objects.create(
            resource=resource, guest_name=data['name'], guest_email=data['email'],
            guest_phone=data['phone'], whatsapp_number=data.get('whatsapp', ''),
            start_time=start_time, end_time=end_time,
            total_price=total_price, payment_method=data['payment_method']
        )
        
        for addon_id in data.get('addons', []):
            addon = Addon.objects.get(id=addon_id)
            BookingAddon.objects.create(booking=booking, addon=addon, price_at_booking=addon.price)
            booking.total_price += addon.price
        
        booking.save()
        
        Payment.objects.create(booking=booking, amount=booking.total_price, method=data['payment_method'])
        
        if booking.payment_method == 'invoice':
            Invoice.objects.create(
                booking=booking, 
                invoice_number=f"INV-{booking.booking_number}", 
                due_date=timezone.now().date() + timedelta(days=7),
                total=booking.total_price
            )
            
        return JsonResponse({
            'status': 'success', 
            'booking_number': booking.booking_number,
            'total_price': str(booking.total_price)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

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
from .models import Resource, Addon, Booking, BookingAddon, Payment, Invoice

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'base_price', 'unit', 'is_active')
    list_filter = ('group', 'is_active')
    search_fields = ('name',)

@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active')
    list_filter = ('is_active',)

class BookingAddonInline(admin.TabularInline):
    model = BookingAddon
    extra = 0

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_number', 'resource', 'guest_name', 'start_time', 'total_price', 'status')
    list_filter = ('status', 'payment_method', 'resource__group')
    search_fields = ('booking_number', 'guest_name', 'guest_email')
    inlines = [BookingAddonInline]
    readonly_fields = ('booking_number', 'total_price')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'amount', 'method', 'status', 'created_at')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'booking', 'total', 'is_paid')
    list_filter = ('is_paid',)
'''

# ==========================================
# 4. PREMIUM TEMPLATE: INDEX.HTML (Masivni CSS)
# ==========================================
index_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rezervacije | VISKOVIĆ GROUP</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --black:   #0a0a0a;
            --dark:    #111214;
            --surface: #181a1d;
            --border:  #252830;
            --muted:   #4a5060;
            --light:   #9aa0b0;
            --white:   #f0ede8;
            --gold:    #c9a84c;
            --gold2:   #e8c96a;
        }
        body { background: var(--black); color: var(--light); font-family: 'Barlow', sans-serif; overflow-x: hidden; line-height: 1.6; }
        
        .hero { 
            height: 60vh; display: flex; flex-direction: column; justify-content: center; align-items: center;
            background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600');
            background-size: cover; background-position: center; text-align: center; border-bottom: 2px solid var(--gold);
        }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 4rem; color: var(--white); font-weight: 300; letter-spacing: 2px; }
        .hero h1 span { color: var(--gold); font-style: italic; }

        .container { max-width: 1300px; margin: 0 auto; padding: 80px 20px; }
        
        .filter-nav { display: flex; justify-content: center; gap: 30px; margin-bottom: 50px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
        .filter-nav a { text-decoration: none; color: var(--muted); text-transform: uppercase; font-size: 0.8rem; letter-spacing: 2px; transition: 0.3s; position: relative; }
        .filter-nav a.active, .filter-nav a:hover { color: var(--gold); }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 40px; }
        
        .res-card { 
            background: var(--surface); border: 1px solid var(--border); transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1); 
            text-decoration: none; color: inherit; position: relative; display: flex; flex-direction: column;
        }
        .res-card:hover { transform: translateY(-15px); border-color: var(--gold); box-shadow: 0 30px 60px rgba(0,0,0,0.5); }
        
        .res-img { height: 260px; background: var(--dark); overflow: hidden; position: relative; border-bottom: 1px solid var(--border); }
        .res-img img { width: 100%; height: 100%; object-fit: cover; opacity: 0.6; transition: 0.8s; }
        .res-card:hover .res-img img { opacity: 0.9; transform: scale(1.1); }

        .res-content { padding: 40px; flex-grow: 1; display: flex; flex-direction: column; }
        .res-category { font-size: 0.65rem; color: var(--gold); text-transform: uppercase; letter-spacing: 5px; margin-bottom: 15px; display: block; font-weight: 600; }
        .res-title { font-family: 'Cormorant Garamond', serif; font-size: 2.2rem; color: var(--white); font-weight: 400; margin-bottom: 15px; line-height: 1.2; }
        .res-desc { font-size: 0.95rem; color: var(--light); margin-bottom: 30px; flex-grow: 1; }
        
        .res-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 25px; margin-top: auto; }
        .res-price { font-size: 1.8rem; color: var(--gold); font-weight: 600; }
        .res-price span { font-size: 0.8rem; color: var(--muted); font-weight: 300; margin-left: 5px; text-transform: uppercase; letter-spacing: 1px; }
        
        .btn-reserve { 
            display: inline-block; padding: 14px 35px; border: 1px solid var(--gold); background: transparent; 
            color: var(--white); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 2px; transition: 0.4s; 
        }
        .res-card:hover .btn-reserve { background: var(--gold); color: var(--black); box-shadow: 0 0 20px rgba(201, 168, 76, 0.3); }

        footer { background: var(--dark); padding: 80px 40px; text-align: center; border-top: 1px solid var(--border); }
        .footer-logo { font-family: 'Cormorant Garamond', serif; font-size: 1.8rem; color: var(--white); letter-spacing: 4px; margin-bottom: 20px; }
        .footer-logo span { color: var(--gold); }

        /* Reveal Animation */
        .reveal { opacity: 0; transform: translateY(30px); transition: 1s all ease; }
        .reveal.visible { opacity: 1; transform: translateY(0); }
    </style>
</head>
<body>
    <header style="padding: 30px 60px; position: absolute; width: 100%; display: flex; justify-content: space-between; z-index: 10;">
        <div style="font-family: 'Cormorant Garamond', serif; font-size: 1.5rem; color: var(--white); letter-spacing: 3px;">VISKOVIĆ <span>GROUP</span></div>
        <a href="/" style="color: var(--white); text-decoration: none; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 2px; border-bottom: 1px solid var(--gold);">Povratak na Home</a>
    </header>

    <div class="hero">
        <h1 class="reveal">Premium <span>Resursi</span> & Najam</h1>
        <p class="reveal" style="color: var(--gold); letter-spacing: 6px; text-transform: uppercase; margin-top: 15px; font-size: 0.9rem;">Visković Group Standard</p>
    </div>

    <div class="container">
        <div class="filter-nav reveal">
            <a href="?group=all" class="{% if current_group == 'all' %}active{% endif %}">Sve</a>
            <a href="?group=housing" class="{% if current_group == 'housing' %}active{% endif %}">Stanovanje</a>
            <a href="?group=construction" class="{% if current_group == 'construction' %}active{% endif %}">Gradnja</a>
            <a href="?group=business" class="{% if current_group == 'business' %}active{% endif %}">Poslovanje</a>
        </div>

        <div class="grid">
            {% for res in resources %}
            <a href="{% url 'premium_booking:detail' res.id %}" class="res-card reveal">
                <div class="res-img">
                    {% if res.image %}<img src="{{ res.image.url }}" alt="{{ res.name }}">{% else %}<div style="height:100%; background:#111;"></div>{% endif %}
                </div>
                <div class="res-content">
                    <span class="res-category">{{ res.get_group_display }}</span>
                    <h2 class="res-title">{{ res.name }}</h2>
                    <p class="res-desc">{{ res.description|truncatechars:120 }}</p>
                    <div class="res-footer">
                        <div class="res-price">{{ res.base_price }}€ <span>/ {{ res.get_unit_display }}</span></div>
                        <div class="btn-reserve">Rezerviraj</div>
                    </div>
                </div>
            </a>
            {% empty %}
            <div style="grid-column: 1/-1; text-align: center; padding: 100px;">
                <p style="color: var(--muted); font-size: 1.2rem;">Trenutno nema dostupnih resursa u ovoj kategoriji.</p>
            </div>
            {% endfor %}
        </div>
    </div>

    <footer>
        <div class="footer-logo">VISKOVIĆ <span>GROUP</span></div>
        <p style="font-size: 0.75rem; color: var(--muted); letter-spacing: 2px;">SNAGA KOJA GRADI BUDUĆNOST · 2026</p>
    </footer>

    <script>
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
        }, { threshold: 0.1 });
        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    </script>
</body>
</html>"""

# ==========================================
# 5. PREMIUM TEMPLATE: DETAIL.HTML (Full UX)
# ==========================================
detail_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ resource.name }} | Rezervacija</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <link rel="stylesheet" type="text/css" href="https://npmcdn.com/flatpickr/dist/themes/dark.css">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --black:   #0a0a0a; --dark:    #111214; --surface: #181a1d; --border:  #252830;
            --white:   #f0ede8; --gold:    #c9a84c; --gold2:   #e8c96a;
        }
        body { background: var(--black); color: var(--white); font-family: 'Barlow', sans-serif; min-height: 100vh; display: flex; flex-direction: column; }
        
        .nav-top { padding: 30px 60px; background: var(--dark); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 1.6rem; color: var(--white); text-decoration: none; letter-spacing: 3px; }
        .logo span { color: var(--gold); }

        .main-container { display: flex; max-width: 1400px; margin: 60px auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 50px 100px rgba(0,0,0,0.6); }
        
        .side-info { width: 40%; padding: 70px; background: linear-gradient(180deg, var(--dark) 0%, var(--black) 100%); border-right: 1px solid var(--border); }
        .side-info h1 { font-family: 'Cormorant Garamond', serif; font-size: 3.5rem; color: var(--white); font-weight: 300; margin-bottom: 30px; line-height: 1.1; }
        .info-label { color: var(--gold); text-transform: uppercase; letter-spacing: 5px; font-size: 0.75rem; margin-bottom: 15px; display: block; }
        
        .booking-panel { width: 60%; padding: 70px; }
        h4 { font-family: 'Cormorant Garamond', serif; font-size: 2rem; color: var(--white); margin-bottom: 40px; border-bottom: 1px solid var(--border); padding-bottom: 15px; font-weight: 400; }

        .form-group { margin-bottom: 30px; }
        label { display: block; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 3px; color: var(--light); margin-bottom: 12px; opacity: 0.6; }
        input, select { width: 100%; background: var(--black); border: 1px solid var(--border); padding: 18px 25px; color: var(--white); outline: none; border-radius: 0; font-family: inherit; font-size: 1rem; transition: 0.3s; }
        input:focus { border-color: var(--gold); box-shadow: 0 0 20px rgba(201, 168, 76, 0.1); }

        .btn-submit { width: 100%; padding: 22px; background: var(--gold); color: var(--black); border: none; font-weight: 700; text-transform: uppercase; letter-spacing: 4px; cursor: pointer; transition: 0.4s; font-size: 0.9rem; }
        .btn-submit:hover { background: var(--gold2); transform: translateY(-3px); box-shadow: 0 10px 30px rgba(201, 168, 76, 0.3); }

        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); backdrop-filter: blur(15px); display: none; align-items: center; justify-content: center; z-index: 1000; }
        .modal-box { background: var(--surface); border: 1px solid var(--gold); padding: 70px; max-width: 600px; width: 90%; text-align: center; box-shadow: 0 0 100px rgba(201, 168, 76, 0.2); }
    </style>
</head>
<body>
    <nav class="nav-top">
        <a href="{% url 'premium_booking:index' %}" class="logo">VISKOVIĆ <span>GROUP</span></a>
        <a href="{% url 'premium_booking:index' %}" style="color: var(--gold); text-decoration: none; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 2px;"><i class="fas fa-arrow-left me-2"></i> Natrag na katalog</a>
    </nav>

    <div class="main-container">
        <div class="side-info">
            <span class="info-label">{{ resource.get_group_display }}</span>
            <h1>{{ resource.name }}</h1>
            <p style="color: var(--light); margin-bottom: 50px; line-height: 1.8;">{{ resource.description }}</p>
            
            <div style="font-size: 2.8rem; color: var(--gold); font-weight: 600; border-top: 1px solid var(--border); padding-top: 40px; margin-top: 40px;">
                {{ resource.base_price }}€ <span style="font-size: 1rem; color: var(--muted); font-weight: 300;">/ {{ resource.get_unit_display }}</span>
            </div>
            
            <div style="margin-top: 50px; display: flex; flex-direction: column; gap: 20px;">
                <div style="display: flex; align-items: center; gap: 15px;"><i class="far fa-clock" style="color: var(--gold);"></i> <span>Min trajanje: {{ resource.min_duration }} jedinica</span></div>
                <div style="display: flex; align-items: center; gap: 15px;"><i class="fas fa-users" style="color: var(--gold);"></i> <span>Kapacitet: {{ resource.capacity }} osoba</span></div>
            </div>
        </div>

        <div class="booking-panel">
            <form id="bookingForm">
                <h4>Rezervacijski Portal</h4>
                <div class="form-group">
                    <label>Odaberite datum i vrijeme dolaska</label>
                    <input type="text" id="dateTimeSelect" placeholder="Kliknite za odabir..." required>
                </div>
                <div class="form-group">
                    <label>Puno ime i prezime</label>
                    <input type="text" id="name" required>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="form-group">
                        <label>Email adresa</label>
                        <input type="email" id="email" required>
                    </div>
                    <div class="form-group">
                        <label>Kontakt telefon</label>
                        <input type="tel" id="phone" required>
                    </div>
                </div>
                <div class="form-group">
                    <label>Odaberite način plaćanja</label>
                    <select id="paymentMethod">
                        <option value="invoice">Uplata po službenoj ponudi</option>
                        <option value="revolut">Revolut Premium Pay</option>
                    </select>
                </div>
                <button type="submit" class="btn-submit" id="btnSubmit">Završi i rezerviraj</button>
            </form>
        </div>
    </div>

    <div class="modal-overlay" id="successModal">
        <div class="modal-box">
            <i class="fas fa-check-circle" style="color: var(--gold); font-size: 5rem; margin-bottom: 30px;"></i>
            <h2 style="font-family: Cormorant Garamond, serif; color: white; font-size: 3rem; margin-bottom: 20px;">Rezervacija uspješna</h2>
            <p style="color: var(--light); font-size: 1.1rem; margin-bottom: 40px;">Vaš broj rezervacije je: <strong id="resNo" style="color:white; font-size: 1.5rem;"></strong></p>
            <p style="margin-bottom: 40px; color: var(--muted);">Potvrda i detaljne upute poslani su na Vaš email.</p>
            <a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block; text-decoration:none;">Povratak na naslovnicu</a>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script>
        flatpickr("#dateTimeSelect", { enableTime: true, dateFormat: "Y-m-d H:i", minDate: "today", theme: "dark" });
        
        document.getElementById('bookingForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSubmit'); btn.disabled = true; btn.innerText = "OBRADA U TIJEKU...";
            
            const dtVal = document.getElementById('dateTimeSelect').value;
            fetch('/premium/api/submit/', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    resource_id: {{ resource.id }},
                    date: dtVal.split(' ')[0], time: dtVal.split(' ')[1],
                    name: document.getElementById('name').value,
                    email: document.getElementById('email').value,
                    phone: document.getElementById('phone').value,
                    payment_method: document.getElementById('paymentMethod').value
                })
            }).then(r => r.json()).then(data => {
                if(data.status === 'success') {
                    document.getElementById('resNo').innerText = data.booking_number;
                    document.getElementById('successModal').style.display = 'flex';
                } else { alert('Greška: ' + data.error); btn.disabled = false; btn.innerText = "POTVRDI REZERVACIJU"; }
            });
        });
    </script>
</body>
</html>"""

# ==========================================
# 5. ZAPISIVANJE SVIH DATOTEKA
# ==========================================
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content)
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

# ==========================================
# 6. INICIJALIZACIJA DJANGA I MIGRACIJE
# ==========================================
print("🔄 Konfiguriranje Django sustava...")

# Ručno ubacivanje u settings.py ako već nije tamo
settings_path = BASE_DIR / PROJECT_NAME / 'settings.py'
with open(settings_path, 'r') as f: s_data = f.read()
if f"'{APP_NAME}'" not in s_data:
    s_data = s_data.replace("INSTALLED_APPS = [", f"INSTALLED_APPS = [\n    '{APP_NAME}',")
    with open(settings_path, 'w') as f: f.write(s_data)

# Ručno ubacivanje u glavni urls.py ako već nije tamo
main_urls_path = BASE_DIR / PROJECT_NAME / 'urls.py'
with open(main_urls_path, 'r') as f: u_data = f.read()
if f"'{APP_NAME}.urls'" not in u_data:
    u_data = u_data.replace("urlpatterns = [", f"urlpatterns = [\n    path('premium/', include('{APP_NAME}.urls')),")
    with open(main_urls_path, 'w') as f: f.write(u_data)

# Pokretanje migracija preko shell-a (sigurnije zbog okruženja)
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

# Dozvole i restart
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*50)
print("✨ VISKOVIĆ PREMIUM BOOKING JE USPJEŠNO INSTALIRAN!")
print(f"🔗 Link: https://viskovic-group.de/premium/")
print("="*50)
