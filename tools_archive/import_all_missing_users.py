import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import Company

def run_total_user_import():
    print(">>> KREĆEM U POTRAGU ZA SVIM RADNICIMA IZ DUMPA...")
    
    main_company = Company.objects.first()
    new_password = "s5Jtkn66!"
    
    # Čitamo cijeli dump
    with open('db_dump.sql', 'r', encoding='utf8') as f:
        content = f.read()

    # Tražimo auth_user COPY blok (id, password, last_login, is_superuser, username, first_name, last_name, email...)
    # Regex hvata username, email, first_name i last_name
    pattern = re.compile(r'\d+\t[^\t]+\t[^\t]*\t(?:f|t)\t([^\t]+)\t([^\t]*)\t([^\t]*)\t([^\t]*)')
    
    found_count = 0
    for match in pattern.finditer(content):
        username, first_name, last_name, email = match.groups()
        
        # Preskačemo sistemske i već postojeće
        if username in ['admin', 'Ivan'] or User.objects.filter(username=username).exists():
            continue
            
        # Kreiramo korisnika
        user = User.objects.create_user(
            username=username,
            email=email if '@' in email else f"{username}@fina-connect.com",
            password=new_password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Postavljamo ulogu worker
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'company': main_company, 'role': 'worker'}
        )
        found_count += 1
        print(f"✓ Pronuđen i dodan: {username} ({first_name} {last_name})")

    print(f"==================================================")
    print(f" USPJEH: Dodano novih {found_count} radnika.")
    print(f" Ukupno radnika u bazi: {User.objects.count()}")
    print(f"==================================================")

if __name__ == '__main__':
    run_total_user_import()
