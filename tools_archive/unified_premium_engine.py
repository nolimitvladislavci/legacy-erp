#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta

# 1. POSTAVKE OKRUŽENJA
PROJECT_NAME = 'core'
APP_NAME = 'premium_booking'
BASE_DIR = Path('/var/www/fina-connect')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'{PROJECT_NAME}.settings')
sys.path.append(str(BASE_DIR))

import django
django.setup()

from django.utils import timezone
from django.db import transaction
from premium_booking.models import Resource, Booking, Addon, BookingAddon
from appointments.models import Appointment, BookingResource as ERPResource
from partners.models import Partner
from invoicing.models import Invoice

print("🏗️  UJEDINJENJE: Spajanje Premium Portala s ERP sustavom...")

# ==========================================
# 2. NADOGRADNJA LOGIKE (VIEWS.PY)
# ==========================================
# Pišemo potpuno novi, povezani engine
views_content = '''import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Resource, Addon, Booking, BookingAddon
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
    if request.method != 'POST': return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            # 1. Dohvat Premium Resursa
            p_resource = Resource.objects.get(id=data['resource_id'])
            start_time = timezone.make_aware(datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M'))
            
            # Izračun trajanja
            duration = p_resource.min_duration
            if p_resource.unit == 'hour': end_time = start_time + timedelta(hours=duration)
            else: end_time = start_time + timedelta(days=duration)

            # 2. Sinkronizacija s Partnerima
            client, created = Partner.objects.get_or_create(
                email=data['email'],
                defaults={'name': data['name'], 'phone': data['phone'], 'partner_type': 'KUPAC'}
            )

            # 3. Kreiranje Premium Bookinga
            booking = Booking.objects.create(
                resource=p_resource, guest_name=data['name'], guest_email=data['email'],
                guest_phone=data['phone'], whatsapp_number=data.get('whatsapp', ''),
                start_time=start_time, end_time=end_time,
                total_price=p_resource.base_price, payment_method=data['payment_method']
            )

            # 4. DODACI I OBRAČUN
            for addon_id in data.get('addons', []):
                addon = Addon.objects.get(id=addon_id)
                BookingAddon.objects.create(booking=booking, addon=addon, price_at_booking=addon.price)
                booking.total_price += addon.price
            booking.save()

            # 5. KLJUČNI KORAK: Upis u centralni ERP Kalendar
            # Tražimo ili kreiramo ekvivalentni resurs u centralnom sustavu
            erp_res, _ = ERPResource.objects.get_or_create(name=p_resource.name, defaults={'resource_type': 'other'})
            
            Appointment.objects.create(
                title=f"PREMIUM: {p_resource.name} - {client.name}",
                client=client,
                resource=erp_res,
                start_time=start_time,
                end_time=end_time,
                status='scheduled',
                color='#c9a84c', # Visković Gold u kalendaru
                appointment_type='service'
            )

            # 6. Kreiranje PRAVE fakture u sustavu
            if booking.payment_method == 'invoice':
                Invoice.objects.create(
                    partner=client,
                    total_amount=booking.total_price,
                    status='DRAFT',
                    notes=f"Rezervacija {booking.booking_number} putem Premium Portala"
                )

        return JsonResponse({
            'status': 'success', 
            'booking_number': booking.booking_number,
            'total_price': str(booking.total_price)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
'''

# Zapisujemo views.py s novom logikom ujedinjenja
with open(APP_DIR / 'views.py', 'w', encoding='utf-8') as f:
    f.write(views_content)

# ==========================================
# 3. POPRAVAK SPAWN ERROR-A (ENGINE RECOVERY)
# ==========================================
print("🧹 Čišćenje blokada i popravak dozvola...")

# Ubijamo stare procese koji drže port 8000
os.system("fuser -k 8000/tcp > /dev/null 2>&1")

# Provjeravamo i primjenjujemo migracije
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py makemigrations {APP_NAME}")
os.system(f"{BASE_DIR}/venv/bin/python {BASE_DIR}/manage.py migrate")

# Postavljanje dozvola za www-data nad cijelim projektom
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system(f"chmod -R 755 {BASE_DIR}")

# Restart servisa
print("⚡ Ponovno pokretanje Visković Premium Engine-a...")
os.system("supervisorctl reread")
os.system("supervisorctl update")
os.system("supervisorctl restart fina-connect")

# Provjera statusa
status = os.popen("supervisorctl status fina-connect").read()
print(f"📊 Status servera: {status}")

if "RUNNING" in status:
    print("\n" + "="*80)
    print("✨ OBEĆANA ZEMLJA JE STIGLA! Sustav je ujedinjen.")
    print(f"🔗 Portal: https://viskovic-group.de/premium/")
    print(f"📅 ERP Kalendar: https://limit-connect.com/appointments/")
    print("="*80)
else:
    print("\n❌ Server i dalje javlja grešku. Provjeravam logove...")
    os.system("tail -n 20 /var/log/fina-connect.err.log")
