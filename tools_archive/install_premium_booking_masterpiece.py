#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from pathlib import Path

# ==============================================================================
# 1. KONFIGURACIJA SUSTAVA
# ==============================================================================
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')
APP_DIR = BASE_DIR / APP_NAME
TEMPLATES_DIR = APP_DIR / 'templates' / APP_NAME

print("🚀 POKRETANJE: Visković Group Premium Booking System (100% Cjeloviti Kod)")

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Zapisano: {path}")

# ==============================================================================
# 2. MODELS.PY - POTPUNA DJANGO ARHITEKTURA
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

# ==============================================================================
# 3. VIEWS.PY - LUKSUZNA POSLOVNA LOGIKA
# ==============================================================================
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
    """Premium katalog resursa Visković Grupe"""
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
    """Premium forma za rezervaciju specifičnog resursa"""
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    from django.db.models import Q
    addons = Addon.objects.filter(
        Q(applicable_groups='') | Q(applicable_groups__icontains=resource.group),
        is_active=True
    )
    return render(request, 'premium_booking/detail.html', {
        'resource': resource, 
        'addons': addons
    })

@require_GET
def api_slots(request):
    """Vraća slobodne termine za odabrani resurs i datum"""
    resource_id = request.GET.get('resource')
    date_str = request.GET.get('date')
    if not resource_id or not date_str:
        return JsonResponse({'error': 'Nedostaju parametri'}, status=400)
    
    resource = get_object_or_404(Resource, id=resource_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    if target_date < timezone.now().date():
        return JsonResponse({'slots': []})
    
    start_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=8)))
    end_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time().replace(hour=20)))
    
    existing = Booking.objects.filter(
        resource=resource, 
        start_time__date=target_date, 
        status__in=['pending', 'confirmed']
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
    """Glavni API za obradu rezervacije i plaćanja"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Metoda nije dozvoljena'}, status=405)
    
    try:
        data = json.loads(request.body)
        resource = get_object_or_404(Resource, id=data['resource_id'])
        start_time = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
        
        duration = resource.min_duration
        if resource.unit == 'hour':
            end_time = start_time + timedelta(hours=duration)
        elif resource.unit == 'day':
            end_time = start_time + timedelta(days=duration)
        else: # month
            end_time = start_time + timedelta(days=30*duration)
            
        if Booking.objects.filter(resource=resource, start_time__lt=end_time, end_time__gt=start_time, status__in=['pending', 'confirmed']).exists():
            return JsonResponse({'status': 'error', 'error': 'Termin je zauzet.'})
        
        total_price = resource.base_price * Decimal(str(duration))
        
        booking = Booking.objects.create(
            resource=resource,
            guest_name=data['name'],
            guest_email=data['email'],
            guest_phone=data['phone'],
            whatsapp_number=data.get('whatsapp', ''),
            start_time=start_time,
            end_time=end_time,
            total_price=total_price,
            payment_method=data['payment_method']
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
            'total_price': str(booking.total_price),
            'whatsapp': booking.whatsapp_number
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

# ==============================================================================
# 4. URLS.PY I ADMIN.PY
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
from .models import Resource, Addon, Booking, BookingAddon, Payment, Invoice

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'base_price', 'unit', 'is_active')
    list_filter = ('group', 'is_active')
    search_fields = ('name',)

@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active')

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
'''

# ==============================================================================
# 5. INDEX.HTML - PUNOKRVNI VISKOVIĆ GROUP DIZAJN (100% KOD)
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
        body { 
            background: var(--black); 
            color: var(--light); 
            font-family: 'Barlow', sans-serif; 
            overflow-x: hidden; 
            line-height: 1.6;
        }
        
        header { 
            position: fixed; top: 0; width: 100%; padding: 30px 60px; display: flex; 
            justify-content: space-between; align-items: center; z-index: 1000;
            background: rgba(10, 10, 10, 0.9); backdrop-filter: blur(15px); border-bottom: 1px solid var(--border);
        }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 1.8rem; color: var(--white); text-decoration: none; letter-spacing: 4px; font-weight: 300; }
        .logo span { color: var(--gold); }

        .hero { 
            height: 65vh; display: flex; flex-direction: column; justify-content: center; align-items: center;
            background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1600');
            background-size: cover; background-position: center; text-align: center; border-bottom: 2px solid var(--gold);
        }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 5rem; color: var(--white); margin-bottom: 20px; font-weight: 300; letter-spacing: 6px; }
        .hero h1 span { color: var(--gold); font-style: italic; }
        .hero p { color: var(--gold); letter-spacing: 10px; text-transform: uppercase; font-size: 0.9rem; font-weight: 600; opacity: 0.8; }

        .container { max-width: 1500px; margin: 0 auto; padding: 120px 40px; }
        
        .filter-nav { display: flex; justify-content: center; gap: 50px; margin-bottom: 100px; border-bottom: 1px solid var(--border); padding-bottom: 35px; }
        .filter-nav a { text-decoration: none; color: var(--muted); text-transform: uppercase; font-size: 0.85rem; letter-spacing: 4px; transition: 0.4s; position: relative; }
        .filter-nav a.active, .filter-nav a:hover { color: var(--gold); }
        .filter-nav a.active::after { content: ''; position: absolute; bottom: -37px; left: 0; width: 100%; height: 3px; background: var(--gold); }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 1fr)); gap: 60px; }
        
        .res-card { 
            background: var(--surface); border: 1px solid var(--border); transition: 0.7s cubic-bezier(0.165, 0.84, 0.44, 1); 
            text-decoration: none; color: inherit; position: relative; display: flex; flex-direction: column; overflow: hidden;
        }
        .res-card:hover { transform: translateY(-25px); border-color: var(--gold); box-shadow: 0 50px 100px rgba(0,0,0,0.7); }
        
        .res-img { height: 350px; background: var(--dark); overflow: hidden; position: relative; border-bottom: 1px solid var(--border); }
        .res-img img { width: 100%; height: 100%; object-fit: cover; opacity: 0.5; transition: 1.5s ease-out; }
        .res-card:hover .res-img img { opacity: 0.95; transform: scale(1.15); }
        .res-badge { position: absolute; top: 30px; right: 30px; padding: 10px 22px; background: rgba(0,0,0,0.85); border: 1px solid var(--gold); color: var(--gold); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 4px; font-weight: 700; z-index: 2; }

        .res-content { padding: 60px; flex-grow: 1; display: flex; flex-direction: column; background: linear-gradient(180deg, var(--surface) 0%, var(--black) 100%); }
        .res-category { font-size: 0.75rem; color: var(--gold); text-transform: uppercase; letter-spacing: 6px; margin-bottom: 25px; display: block; font-weight: 700; opacity: 0.9; }
        .res-title { font-family: 'Cormorant Garamond', serif; font-size: 3rem; color: var(--white); font-weight: 300; margin-bottom: 30px; line-height: 1.1; }
        .res-desc { font-size: 1.05rem; color: var(--light); margin-bottom: 45px; flex-grow: 1; opacity: 0.75; font-weight: 300; }
        
        .res-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 45px; margin-top: auto; }
        .res-price { font-size: 2.5rem; color: var(--gold); font-weight: 600; font-family: 'Cormorant Garamond', serif; }
        .res-price span { font-size: 1rem; color: var(--muted); font-weight: 300; margin-left: 10px; text-transform: uppercase; font-family: 'Barlow', sans-serif; letter-spacing: 4px; }
        
        .btn-reserve { 
            display: inline-block; padding: 18px 45px; border: 1px solid var(--gold); background: transparent; 
            color: var(--white); text-transform: uppercase; font-size: 0.8rem; letter-spacing: 5px; transition: 0.5s; font-weight: 700;
        }
        .res-card:hover .btn-reserve { background: var(--gold); color: var(--black); box-shadow: 0 0 50px rgba(201, 168, 76, 0.5); }

        footer { background: var(--dark); padding: 120px 60px; text-align: center; border-top: 1px solid var(--border); }
        .footer-logo { font-family: 'Cormorant Garamond', serif; font-size: 2.5rem; color: var(--white); letter-spacing: 8px; margin-bottom: 35px; font-weight: 300; }
        .footer-logo span { color: var(--gold); }
        .footer-tag { font-size: 0.85rem; color: var(--muted); letter-spacing: 5px; text-transform: uppercase; font-weight: 500; }

        .reveal { opacity: 0; transform: translateY(60px); transition: 1.5s all cubic-bezier(0.165, 0.84, 0.44, 1); }
        .reveal.visible { opacity: 1; transform: translateY(0); }
    </style>
</head>
<body>
    <header>
        <a href="/" class="logo">VISKOVIĆ <span>GROUP</span></a>
        <a href="/" style="color: var(--white); text-decoration: none; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 4px; border-bottom: 2px solid var(--gold); padding-bottom: 8px;">Povratak</a>
    </header>

    <div class="hero">
        <h1 class="reveal">Ekskluzivni <span>Najam</span></h1>
        <p class="reveal">PROFILIRANA SNAGA BUDUĆNOSTI</p>
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
                    <div class="res-badge">{{ res.get_group_display }}</div>
                    {% if res.image %}<img src="{{ res.image.url }}" alt="{{ res.name }}">{% else %}<div style="height:100%; background:#111; display:flex; align-items:center; justify-content:center;"><i class="fas fa-building fa-6x" style="color:var(--border);"></i></div>{% endif %}
                </div>
                <div class="res-content">
                    <span class="res-category">{{ res.get_unit_display }} PROTOKOL</span>
                    <h2 class="res-title">{{ res.name }}</h2>
                    <p class="res-desc">{{ res.description|truncatechars:220 }}</p>
                    <div class="res-footer">
                        <div class="res-price">{{ res.base_price }}€ <span>/ {{ res.get_unit_display }}</span></div>
                        <div class="btn-reserve">Pokreni Rezervaciju</div>
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>

    <footer>
        <div class="footer-logo">VISKOVIĆ <span>GROUP</span></div>
        <p class="footer-tag">Visković Group Premium Engineering · 2026</p>
    </footer>

    <script>
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
        }, { threshold: 0.1 });
        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    </script>
</body>
</html>"""

# ==============================================================================
# 6. DETAIL.HTML - LUKSUZNI USER EXPERIENCE (100% KOD)
# ==============================================================================
detail_template = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ resource.name }} | Rezervacija | VISKOVIĆ GROUP</title>
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
        
        .nav-top { padding: 40px 60px; background: var(--dark); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 1.8rem; color: var(--white); text-decoration: none; letter-spacing: 5px; font-weight: 300; }
        .logo span { color: var(--gold); }

        .main-container { display: flex; max-width: 1600px; margin: 60px auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 80px 150px rgba(0,0,0,0.8); }
        
        .side-info { width: 45%; padding: 100px; background: linear-gradient(180deg, var(--dark) 0%, var(--black) 100%); border-right: 1px solid var(--border); }
        .side-info h1 { font-family: 'Cormorant Garamond', serif; font-size: 4.5rem; color: var(--white); font-weight: 300; margin-bottom: 40px; line-height: 1; }
        .info-label { color: var(--gold); text-transform: uppercase; letter-spacing: 8px; font-size: 0.9rem; margin-bottom: 25px; display: block; font-weight: 700; }
        
        .booking-panel { width: 55%; padding: 100px; }
        h4 { font-family: 'Cormorant Garamond', serif; font-size: 2.8rem; color: var(--white); margin-bottom: 60px; border-bottom: 1px solid var(--border); padding-bottom: 25px; font-weight: 400; letter-spacing: 2px; }

        .form-group { margin-bottom: 45px; }
        label { display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 5px; color: var(--light); margin-bottom: 18px; opacity: 0.8; font-weight: 500; }
        input, select { width: 100%; background: var(--black); border: 1px solid var(--border); padding: 22px 35px; color: var(--white); outline: none; border-radius: 0; font-family: inherit; font-size: 1.15rem; transition: 0.5s; letter-spacing: 1px; }
        input:focus { border-color: var(--gold); box-shadow: 0 0 35px rgba(201, 168, 76, 0.2); }

        .addon-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 25px; margin-bottom: 60px; }
        .addon-item { border: 1px solid var(--border); background: var(--black); padding: 30px; text-align: center; cursor: pointer; transition: 0.5s; position: relative; }
        .addon-item:hover { border-color: var(--light); }
        .addon-item.selected { border-color: var(--gold); background: rgba(201, 168, 76, 0.12); }
        .addon-item i { display: block; font-size: 2.2rem; color: var(--gold); margin-bottom: 20px; transition: 0.4s; }
        .addon-item.selected i { transform: scale(1.1); }
        .addon-item span { display: block; font-size: 0.9rem; font-weight: 600; color: var(--white); letter-spacing: 1px; }

        .btn-submit { width: 100%; padding: 28px; background: var(--gold); color: var(--black); border: none; font-weight: 800; text-transform: uppercase; letter-spacing: 6px; cursor: pointer; transition: 0.6s cubic-bezier(0.165, 0.84, 0.44, 1); font-size: 1.1rem; }
        .btn-submit:hover { background: var(--gold2); transform: translateY(-7px); box-shadow: 0 25px 60px rgba(201, 168, 76, 0.45); }

        .summary-box { background: var(--black); padding: 50px; border: 1px solid var(--border); margin-top: 60px; display: flex; justify-content: space-between; align-items: center; position: relative; }
        .sum-label { text-transform: uppercase; letter-spacing: 6px; font-size: 1rem; color: var(--light); font-weight: 500; }
        .sum-val { font-size: 3.5rem; color: var(--gold); font-weight: 600; font-family: 'Cormorant Garamond', serif; }

        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.99); backdrop-filter: blur(25px); display: none; align-items: center; justify-content: center; z-index: 2000; }
        .modal-box { background: var(--surface); border: 1px solid var(--gold); padding: 100px; max-width: 800px; width: 90%; text-align: center; box-shadow: 0 0 150px rgba(201, 168, 76, 0.3); }
        .revolut-box { background: var(--black); border: 1px dashed var(--gold); padding: 45px; margin: 50px 0; text-align: left; }
        .whatsapp-btn { display: inline-block; width: 100%; padding: 25px; background: #25D366; color: white; text-decoration: none; font-weight: 800; text-transform: uppercase; letter-spacing: 4px; margin-top: 30px; transition: 0.4s; }
        .whatsapp-btn:hover { background: #128C7E; transform: scale(1.02); }

        @media (max-width: 1200px) { .main-container { flex-direction: column; } .side-info, .booking-panel { width: 100%; border-right: 0; } }
    </style>
</head>
<body>
    <nav class="nav-top">
        <a href="{% url 'premium_booking:index' %}" class="logo">VISKOVIĆ <span>GROUP</span></a>
        <a href="{% url 'premium_booking:index' %}" style="color: var(--gold); text-decoration: none; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 4px;"><i class="fas fa-arrow-left me-3"></i> Povratak</a>
    </nav>

    <div class="main-container">
        <div class="side-info">
            <span class="info-label">{{ resource.get_group_display }}</span>
            <h1>{{ resource.name }}</h1>
            <p style="color: var(--light); margin-bottom: 70px; line-height: 2.2; opacity: 0.85; font-size: 1.15rem;">{{ resource.description }}</p>
            
            <div style="margin-top: 60px; display: flex; flex-direction: column; gap: 40px; border-top: 1px solid var(--border); padding-top: 60px;">
                <div style="display: flex; align-items: center; gap: 25px;"><i class="far fa-clock" style="color: var(--gold); font-size: 1.8rem;"></i> <span style="letter-spacing: 3px; text-transform: uppercase; font-size: 1rem;">Min. Protokol: {{ resource.min_duration }} jedinica</span></div>
                <div style="display: flex; align-items: center; gap: 25px;"><i class="fas fa-users" style="color: var(--gold); font-size: 1.8rem;"></i> <span style="letter-spacing: 3px; text-transform: uppercase; font-size: 1rem;">Kapacitet: {{ resource.capacity }} osobe</span></div>
            </div>

            <div style="font-size: 4.5rem; color: var(--gold); font-weight: 600; margin-top: 80px; font-family: 'Cormorant Garamond', serif;">
                {{ resource.base_price }}€ <span style="font-size: 1.2rem; color: var(--muted); font-weight: 300; font-family: 'Barlow', sans-serif; letter-spacing: 5px; text-transform: uppercase;">/ {{ resource.get_unit_display }}</span>
            </div>
        </div>

        <div class="booking-panel">
            <form id="bookingForm">
                <h4>Rezervacijska Autentifikacija</h4>
                
                <div class="form-group">
                    <label>Protokol Vremena i Datuma</label>
                    <input type="text" id="dateTimeSelect" placeholder="Odaberite Vaš termin..." required>
                </div>

                {% if addons %}
                <label>Dodatni Premium Moduli</label>
                <div class="addon-grid">
                    {% for addon in addons %}
                    <div class="addon-item" onclick="toggleAddon(this)" data-id="{{ addon.id }}" data-price="{{ addon.price }}">
                        <i class="fas {{ addon.icon|default:'fa-plus' }}"></i>
                        <span>{{ addon.name }}</span>
                        <small style="color:var(--gold); margin-top:15px; display:block; font-weight:700;">+{{ addon.price }}€</small>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                <div class="form-group">
                    <label>Identitet Klijenta (Ime i Prezime)</label>
                    <input type="text" id="name" placeholder="Puno ime klijenta" required>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
                    <div class="form-group">
                        <label>E-mail adresa</label>
                        <input type="email" id="email" placeholder="vas@email.com" required>
                    </div>
                    <div class="form-group">
                        <label>Kontakt mobitel</label>
                        <input type="tel" id="phone" placeholder="+385..." required>
                    </div>
                </div>

                <div class="form-group">
                    <label>Metoda Likvidacije Troškova</label>
                    <select id="paymentMethod">
                        <option value="invoice">Uplata po službenoj ponudi</option>
                        <option value="revolut">Revolut Premium Direct</option>
                    </select>
                </div>

                <div class="summary-box">
                    <span class="sum-label">Ukupna vrijednost rezervacije</span>
                    <span class="sum-val" id="totalPrice">{{ resource.base_price }}€</span>
                </div>

                <button type="submit" class="btn-submit" id="btnSubmit">Završi i Evidentiraj Rezervaciju</button>
            </form>
        </div>
    </div>

    <div class="modal-overlay" id="successModal">
        <div class="modal-box">
            <i class="fas fa-check-circle" style="color: var(--gold); font-size: 8rem; margin-bottom: 50px;"></i>
            <h2 style="font-family: 'Cormorant Garamond', serif; color: white; font-size: 4.5rem; margin-bottom: 30px; line-height: 1;">Uspjeh</h2>
            <p style="color: var(--light); font-size: 1.4rem; margin-bottom: 60px; letter-spacing: 2px;">Kod rezervacije: <strong id="resNo" style="color:white; border-bottom: 3px solid var(--gold); padding-bottom: 5px;"></strong></p>
            
            <div id="revolutInfo" style="display: none;" class="revolut-box">
                <p style="color: var(--gold); text-transform: uppercase; letter-spacing: 5px; font-size: 0.9rem; margin-bottom: 25px;">Instrukcije za Direktnu Uplatu</p>
                <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                    <span>Iznos:</span><strong id="modalAmount" style="color:white; font-size: 1.5rem;"></strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>IBAN:</span><strong style="color:white; font-family: monospace; letter-spacing: 2px; font-size: 1.1rem;">HR12 1234 5678 9012 3456 7</strong>
                </div>
            </div>

            <div id="invoiceInfo" style="display: none; padding: 50px; border: 1px solid var(--border); margin-bottom: 50px;">
                <p style="letter-spacing: 2px; font-size: 1.1rem;">Službena dokumentacija za plaćanje poslana je na Vaš autorizirani email.</p>
            </div>

            <a href="#" target="_blank" class="whatsapp-btn" id="waLink"><i class="fab fa-whatsapp me-4"></i> Potvrdi putem WhatsApp-a</a>
            <a href="{% url 'premium_booking:index' %}" class="btn-submit" style="display:block; text-decoration:none; margin-top: 40px; background: transparent; border: 1px solid var(--border); color: white;">Zatvori</a>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script>
        let selectedAddons = [];
        let basePrice = parseFloat("{{ resource.base_price }}");

        flatpickr("#dateTimeSelect", { 
            enableTime: true, dateFormat: "Y-m-d H:i", minDate: "today", theme: "dark", minuteIncrement: 30, time_24hr: true
        });
        
        function toggleAddon(el) {
            el.classList.toggle('selected');
            const id = el.dataset.id;
            const price = parseFloat(el.dataset.price);
            if(el.classList.contains('selected')) selectedAddons.push({id, price});
            else selectedAddons = selectedAddons.filter(a => a.id !== id);
            updateTotal();
        }

        function updateTotal() {
            let total = basePrice;
            selectedAddons.forEach(a => total += a.price);
            document.getElementById('totalPrice').innerText = total.toFixed(2) + '€';
        }

        document.getElementById('bookingForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSubmit'); 
            btn.disabled = true; btn.innerText = "SINKRONIZACIJA SA SERVEROM...";
            
            const dtVal = document.getElementById('dateTimeSelect').value;
            fetch('/premium/api/submit/', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    resource_id: "{{ resource.id }}",
                    date: dtVal.split(' ')[0], time: dtVal.split(' ')[1],
                    name: document.getElementById('name').value,
                    email: document.getElementById('email').value,
                    phone: document.getElementById('phone').value,
                    payment_method: document.getElementById('paymentMethod').value,
                    addons: selectedAddons.map(a => a.id)
                })
            }).then(r => r.json()).then(data => {
                if(data.status === 'success') {
                    document.getElementById('resNo').innerText = data.booking_number;
                    document.getElementById('modalAmount').innerText = data.total_price + '€';
                    document.getElementById('waLink').href = `https://wa.me/385991234567?text=Pozdrav, želim potvrditi rezervaciju ${data.booking_number}.`;
                    if(document.getElementById('paymentMethod').value === 'revolut') document.getElementById('revolutInfo').style.display = 'block';
                    else document.getElementById('invoiceInfo').style.display = 'block';
                    document.getElementById('successModal').style.display = 'flex';
                } else { alert('Greška: ' + data.error); btn.disabled = false; btn.innerText = "POKRENI REZERVACIJU"; }
            });
        });
    </script>
</body>
</html>"""

# ==============================================================================
# 7. ZAPISIVANJE I AKTIVACIJA (SIGURAN REDOSLIJED)
# ==============================================================================
# Prvo pišemo kod, pa onda radimo migracije
write_file(APP_DIR / 'models.py', models_content)
write_file(APP_DIR / 'views.py', views_content)
write_file(APP_DIR / 'urls.py', urls_content)
write_file(APP_DIR / 'admin.py', admin_content)
write_file(TEMPLATES_DIR / 'index.html', index_template)
write_file(TEMPLATES_DIR / 'detail.html', detail_template)

print("🔄 Konfiguriranje Django sustava...")

# Settings update
settings_path = BASE_DIR / PROJECT_NAME / 'settings.py'
with open(settings_path, 'r') as f: s_data = f.read()
if f"'{APP_NAME}'" not in s_data:
    s_data = s_data.replace("INSTALLED_APPS = [", f"INSTALLED_APPS = [\n    '{APP_NAME}',")
    with open(settings_path, 'w') as f: f.write(s_data)

# Urls update
main_urls_path = BASE_DIR / PROJECT_NAME / 'urls.py'
with open(main_urls_path, 'r') as f: u_data = f.read()
if f"'{APP_NAME}.urls'" not in u_data:
    u_data = u_data.replace("urlpatterns = [", f"urlpatterns = [\n    path('premium/', include('{APP_NAME}.urls')),")
    with open(main_urls_path, 'w') as f: f.write(u_data)

# Migracije i dozvole putem venv-a
print("🔄 Provođenje migracija baze...")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

print("🔐 Usklađivanje dozvola sustava...")
os.system(f"chown -R www-data:www-data {BASE_DIR}")

print("⚡ Provjera sintakse i pokretanje...")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py check")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*80)
print("✨ VISKOVIĆ PREMIUM BOOKING JE SPREMAN ZA PROMET!")
print(f"🔗 Link: https://viskovic-group.de/premium/")
print("="*80)
