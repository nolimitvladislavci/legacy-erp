import os
import django
import random
from datetime import date, timedelta, time
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from companies.models import Company
from accounts.models import UserProfile
from partners.models import Partner
from worktime.models import Project, TimeEntry, EmployeeProfile
from finance.models import Transaction

def run_seed():
    print("--- POKREĆEM PAMETNI UVOZ (PARTNER 2.0 - FIX) ---")

    # 1. TVRTKA
    main_company, _ = Company.objects.get_or_create(
        oib="12345678901",
        defaults={'name': "Visković Bau", 'city': "Gärtringen", 'is_vat_registered': True}
    )

    # 2. RADNICI
    workers = [
        ('ivan.brtan', 'Ivan', 'Brtan', 'grosmarkt.online@gmail.com'),
        ('marko.vilic', 'Marko', 'Vilic', 'makivily@gmail.com'),
        ('dragan.jakovljevic', 'Dragan', 'Jakovljevic', 'jakovljevicdragan8@gmail.com'),
        ('petar.brtan', 'Petar', 'Brtan', 'petar.brtan@gmail.com'),
    ]

    for user, first, last, email in workers:
        u, created = User.objects.get_or_create(username=user, defaults={'first_name': first, 'last_name': last, 'email': email})
        if created: u.set_password('test1234'); u.save()
        UserProfile.objects.get_or_create(user=u, defaults={'company': main_company, 'role': 'worker'})
        
        # FIX: Koristimo get_or_create po imenu, ne ostavljamo prazan OIB koji radi konflikt
        Partner.objects.get_or_create(
            company=main_company,
            name=f"{first} {last}",
            defaults={
                'email': email,
                'partner_type': 'employee',
                'city': 'Gärtringen',
                'is_active': True,
                'oib': f"EMP-{user[:8]}" # Privremeni jedinstveni ID za radnika
            }
        )
        print(f"✓ Radnik/Partner: {first} {last}")

    # 3. KLIJENTI
    clients = [
        ("VODOCOMP d.o.o.", "700123456789", "Sigetac 2", "Novska", 14),
        ("Medija d.o.o.", "700987654321", "Glavna ulica 1", "Zagreb", 30),
    ]

    for name, oib, addr, city, days in clients:
        p, created = Partner.objects.get_or_create(
            company=main_company,
            oib=oib,
            defaults={
                'name': name,
                'address': addr,
                'city': city,
                'payment_term': days,
                'partner_type': 'client'
            }
        )
        print(f"✓ Klijent: {name} ({city})")

    # 4. FINANCIJE
    try:
        partner = Partner.objects.get(name="VODOCOMP d.o.o.")
        Transaction.objects.get_or_create(
            company=main_company,
            partner=partner,
            amount=Decimal('5000.00'),
            date=date.today(),
            direction='income',
            description="Inicijalna uplata"
        )
        partner.update_balance()
        print("✓ Saldo ažuriran.")
    except Exception as e:
        print(f"! Info kod financija: {e}")

if __name__ == '__main__':
    run_seed()
