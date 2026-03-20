import os
import django
import re
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from worktime.models import Project, TimeEntry

def sync_all_hours():
    print(">>> SINKRONIZIRAM SVE RADNE SATE ZA SVE RADNIKE...")
    
    user_map = {u.username: u for u in User.objects.all()}
    project_map = {p.name: p for p in Project.objects.all()}
    
    # Proširena mapa ID-ova iz dumpa za sve radnike
    id_to_username = {
        3: 'ivan.brtan', 6: 'antonio.brtan', 8: 'dragan.jakovljevic',
        12: 'marko.brtan', 17: 'petar.brtan', 18: 'ive.kovacevic',
        20: 'marko.vilic', 21: 'edin.cehic', 22: 'abdulach.cehic',
        23: 'mahmoud.shihadehs', 24: 'ilija.sosic', 25: 'dorijan.mrkonjic',
        26: 'david.simic', 27: 'seki.temaj', 28: 'damir.vilic'
    }

    id_to_project = {
        1: 'Nufringen', 2: 'Waldenbuch', 3: 'Dagersheim',
        4: 'Dettenhausen', 5: 'Sindelfingen', 6: 'Ostalo / Razno'
    }

    with open('db_dump.sql', 'r', encoding='utf8') as f:
        content = f.read()
        
    pattern = re.compile(r'(\d+)\t(\d{4}-\d{2}-\d{2})\t.*?\t.*?\t(\d+\.\d+)\t(.*?)\t.*?\t.*?\t.*?\t.*?\t.*?\t.*?\t.*?\t(\d+\.\d+)\t.*?\t.*?\t.*?\t.*?\t(\d+)\t(\d+)')
    
    added = 0
    for match in pattern.finditer(content):
        _, date_str, duration, desc, billing, proj_id, user_id = match.groups()
        
        username = id_to_username.get(int(user_id))
        proj_name = id_to_project.get(int(proj_id))
        
        if username in user_map and proj_name in project_map:
            obj, created = TimeEntry.objects.get_or_create(
                date=date_str,
                user=user_map[username],
                project=project_map[proj_name],
                duration=Decimal(duration),
                defaults={
                    'description': desc,
                    'status': 'approved',
                    'billing_amount': Decimal(billing)
                }
            )
            if created:
                added += 1

    print(f"==================================================")
    print(f" SINKRONIZACIJA GOTOVA.")
    print(f" Dodano novih {added} unosa koji su nedostajali.")
    print(f" Ukupno radnih sati u sustavu: {TimeEntry.objects.count()}")
    print(f"==================================================")

if __name__ == '__main__':
    sync_all_hours()
