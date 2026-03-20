import os
import django
import random
from datetime import date, timedelta, time
from decimal import Decimal

# Postavljanje Django okruženja
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from companies.models import Company
from accounts.models import UserProfile
from partners.models import Partner
from worktime.models import Project, TimeEntry, EmployeeProfile
from finance.models import Transaction

def run_seed():
    print("--- POČINJEM UVOZ PODATAKA IZ DUMPA ---")

    # 1. KREIRANJE GLAVNE TVRTKE
    main_company, created = Company.objects.get_or_create(
        oib="12345678901", # Testni OIB
        defaults={
            'name': "Visković Bau",
            'city': "Gärtringen",
            'is_vat_registered': True
        }
    )
    print(f"✓ Tvrtka: {main_company.name}")

    # 2. KREIRANJE RADNIKA (Iz dumpa auth_user)
    # Format: (username, first_name, last_name, email)
    users_data = [
        ('ivan.brtan', 'Ivan', 'Brtan', 'grosmarkt.online@gmail.com'),
        ('marko.vilic', 'Marko', 'Vilic', 'makivily@gmail.com'),
        ('dragan.jakovljevic', 'Dragan', 'Jakovljevic', 'jakovljevicdragan8@gmail.com'),
        ('petar.brtan', 'Petar', 'Brtan', 'petar.brtan@gmail.com'),
        ('edin.cehic', 'Edin', 'Cehic', 'edo.cehic@gmail.com'),
        ('antonio.brtan', 'Antonio', 'Brtan', 'antonio-brtan@hotmail.com'),
        ('seki.temaj', 'Šeki', 'Temaj', 'pekara.uvijekfrisko@gmail.com'),
        ('ive.kovacevic', 'Ive', 'Kovacevic', 'ive.kovacevic@gmail.com'),
        ('mahmoud.shihadehs', 'Mahmoud', 'Shihadehs', 'lktw44@gmail.com'),
        ('ilija.sosic', 'Ilija', 'Sosic', 'ilijasosic0401.1997@gmail.com'),
        ('david.simic', 'David', 'Simic', 'davsimic93@gmail.com'),
        ('dorijan.mrkonjic', 'Dorijan', 'Mrkonjić', 'dorijanm14@gmail.com'),
        ('damir.vilic', 'Damir', 'Vilic', 'vilicdamir84@gmail.com'),
    ]

    employees = []
    
    for username, first, last, email in users_data:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first,
                'last_name': last,
                'email': email,
                'is_staff': False
            }
        )
        if created:
            user.set_password('test1234') # Default šifra za sve
            user.save()
        
        # Povezivanje profila s tvrtkom
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.company = main_company
        profile.role = 'worker'
        profile.save()

        # Kreiranje EmployeeProfile (za satnice)
        emp_profile, _ = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={
                'hourly_rate': Decimal('20.00'), # Default satnica iz dumpa
                'position': 'Radnik'
            }
        )
        employees.append(user)
        print(f"✓ Radnik: {first} {last}")

    # 3. KREIRANJE PROJEKATA (Iz dumpa worktime_project)
    projects_data = [
        ('Nufringen', 'NUF'),
        ('Waldenbuch', 'WAL'),
        ('Dagersheim', 'DAG'),
        ('Dettenhausen', 'DET'),
        ('Sindelfingen', 'SIN'),
        ('Gartringen', 'GAR'),
        ('Ostalo / Razno', 'GEN'),
    ]

    project_objs = []
    for name, code in projects_data:
        proj, _ = Project.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'hourly_rate': Decimal('25.00'),
                'is_billable': True,
                'status': 'active'
            }
        )
        project_objs.append(proj)
        print(f"✓ Projekt: {name}")

    # 4. KREIRANJE PARTNERA (Iz dumpa partners_partner)
    partner_vodocomp, _ = Partner.objects.get_or_create(
        oib="700123456789",
        company=main_company,
        defaults={
            'name': "VODOCOMP d.o.o.",
            'email': "vodocomp@gmail.com",
            'city': "Novska",
            'partner_type': 'client'
        }
    )
    print(f"✓ Partner: {partner_vodocomp.name}")

    # 5. GENERIRANJE RADNIH SATI (Rekonstrukcija iz dumpa)
    # Generirat ćemo unose za zadnja 3 mjeseca da dashboard izgleda živo
    print(">>> Generiram radne sate (ovo može potrajati par sekundi)...")
    
    tasks = [
        "Priprema za betonazu",
        "Ljepljenje pločica",
        "Rigips konstrukcija",
        "Uvoz materijala",
        "Fugiranje",
        "Glazura",
        "Montaža vrata"
    ]

    today = date.today()
    entries_count = 0

    for i in range(150): # 150 nasumičnih unosa
        # Random datum u zadnjih 90 dana
        entry_date = today - timedelta(days=random.randint(0, 90))
        
        # Preskoči nedjelju (ponekad)
        if entry_date.weekday() == 6 and random.choice([True, False]):
            continue

        user = random.choice(employees)
        project = random.choice(project_objs)
        description = random.choice(tasks)
        hours = Decimal(random.choice(['8.00', '8.50', '9.00', '10.00', '4.00']))
        
        TimeEntry.objects.get_or_create(
            user=user,
            date=entry_date,
            project=project,
            defaults={
                'start_time': time(7, 0),
                'end_time': time(7 + int(hours), 0) if hours % 1 == 0 else time(7 + int(hours), 30),
                'duration': hours,
                'description': f"{description} - {project.name}",
                'status': 'approved' # Odmah odobreno da se vidi u izračunima
            }
        )
        entries_count += 1

    print(f"✓ Generirano {entries_count} unosa radnog vremena.")

    # 6. INICIJALNA FINANCIJSKA TRANSAKCIJA (Da partner nije na nuli)
    Transaction.objects.get_or_create(
        company=main_company,
        partner=partner_vodocomp,
        amount=Decimal('5000.00'),
        date=today,
        direction='income',
        description="Uplata po ponudi 2026-001"
    )
    # Okinuti update salda
    partner_vodocomp.update_balance()
    print("✓ Financije inicijalizirane.")

    print("--- IMPORT ZAVRŠEN USPJEŠNO ---")
    print(f"Svi radnici imaju šifru: test1234")

if __name__ == '__main__':
    run_seed()
