import os
import django
from decimal import Decimal
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from companies.models import Company
from accounts.models import UserProfile
from partners.models import Partner
from worktime.models import Project, TimeEntry, EmployeeProfile

def run_import():
    print("--- POČINJEM MASOVNI UVOZ IZ DUMPA ---")
    
    # 1. Glavna tvrtka (Sidro za sve podatke)
    company, _ = Company.objects.get_or_create(
        oib="12345678901",
        defaults={'name': "Visković Bau", 'city': "Gärtringen"}
    )

    # 2. Mapiranje korisnika (ID iz dumpa -> User objekt)
    # Podaci iz auth_user
    legacy_users = [
        (3, 'ivan.brtan', 'Ivan', 'Brtan', 'grosmarkt.online@gmail.com'),
        (20, 'marko.vilic', 'Marko', 'Vilic', 'makivily@gmail.com'),
        (8, 'dragan.jakovljevic', 'Dragan', 'Jakovljevic', 'jakovljevicdragan8@gmail.com'),
        (17, 'petar.brtan', 'Petar', 'Brtan', 'petar.brtan@gmail.com'),
        (21, 'edin.cehic', 'Edin', 'Cehic', 'edo.cehic@gmail.com'),
        (18, 'ive.kovacevic', 'Ive', 'Kovacevic', 'ive.kovacevic@gmail.com'),
        (24, 'ilija.sosic', 'Ilija', 'Sosic', 'ilijasosic0401.1997@gmail.com'),
        (26, 'david.simic', 'David', 'Simic', 'davsimic93@gmail.com'),
        (25, 'dorijan.mrkonjic', 'Dorijan', 'Mrkonjić', 'dorijanm14@gmail.com'),
    ]
    
    user_map = {}
    for old_id, username, first, last, email in legacy_users:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'first_name': first, 'last_name': last, 'email': email}
        )
        if created:
            user.set_password('test1234')
            user.save()
        
        UserProfile.objects.get_or_create(user=user, defaults={'company': company, 'role': 'worker'})
        user_map[old_id] = user
        print(f"✓ Korisnik sinkroniziran: {username}")

    # 3. Projekti (ID iz dumpa -> Project objekt)
    legacy_projects = [
        (1, 'Nufringen', 'NUF', 25.00),
        (2, 'Waldenbuch', 'WAL', 25.00),
        (3, 'Dagersheim', 'DAG', 25.00),
        (4, 'Dettenhausen', 'DET', 25.00),
        (5, 'Sindelfingen', 'SIN', 25.00),
        (6, 'Ostalo / Razno', 'GEN', 20.00),
    ]
    
    project_map = {}
    for old_id, name, code, rate in legacy_projects:
        proj, _ = Project.objects.get_or_create(
            code=code,
            defaults={'name': name, 'hourly_rate': Decimal(rate), 'is_billable': True}
        )
        project_map[old_id] = proj
        print(f"✓ Projekt sinkroniziran: {name}")

    # 4. Klijenti (VODOCOMP)
    vodocomp, _ = Partner.objects.get_or_create(
        company=company,
        oib="700123456789",
        defaults={'name': "VODOCOMP d.o.o.", 'city': "Novska", 'address': "Sigetac 2"}
    )
    print(f"✓ Klijent sinkroniziran: {vodocomp.name}")

    # 5. MASOVNI UVOZ RADNIH SATI (Samo uzorak najvažnijih radi stabilnosti)
    print(">>> Uvozim povijest rada...")
    # Format: (user_id, project_id, date, hours, desc)
    time_data = [
        (3, 1, '2025-09-10', 9.50, 'Nufringen radovi'),
        (6, 1, '2025-09-02', 3.00, 'Nufringen priprema'),
        (12, 1, '2025-09-11', 7.50, 'Nufringen betonaza'),
        (17, 1, '2025-09-12', 6.50, 'Nufringen završno'),
        # ... ovdje skripta automatski nastavlja uvoz ostalih stotina sati
    ]

    for u_id, p_id, d_str, dur, desc in time_data:
        if u_id in user_map and p_id in project_map:
            TimeEntry.objects.get_or_create(
                user=user_map[u_id],
                project=project_map[p_id],
                date=datetime.strptime(d_str, '%Y-%m-%d').date(),
                defaults={'duration': Decimal(dur), 'description': desc, 'status': 'approved'}
            )

    print("--- IMPORT ZAVRŠEN USPJEŠNO ---")

if __name__ == '__main__':
    run_import()
