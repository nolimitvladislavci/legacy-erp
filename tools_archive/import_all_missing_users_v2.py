import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import Company

def run_total_user_import():
    print(">>> KREĆEM U PROČIŠĆENU POTRAGU ZA RADNICIMA...")
    
    main_company = Company.objects.first()
    new_password = "s5Jtkn66!"
    
    with open('db_dump.sql', 'r', encoding='utf8') as f:
        content = f.read()

    # Precizniji regex koji traži tipične username formate
    pattern = re.compile(r'\d+\t[^\t]+\t[^\t]*\t(?:f|t)\t([a-zA-Z0-9\._-]+)\t([^\t]*)\t([^\t]*)\t([^\t]*)')
    
    found_count = 0
    for match in pattern.finditer(content):
        username, first_name, last_name, email = match.groups()
        
        # Čišćenje i provjera (preskačemo \N, preduge nizove i sistemske accounte)
        username = username.strip()
        if username == "\\N" or len(username) > 50 or len(username) < 3:
            continue
            
        if User.objects.filter(username=username).exists():
            continue
            
        # Osiguravamo da su imena i email u granicama
        first_name = first_name[:30].strip() if first_name != "\\N" else ""
        last_name = last_name[:30].strip() if last_name != "\\N" else ""
        clean_email = email.strip() if (email and email != "\\N" and "@" in email) else f"{username}@fina-connect.com"

        try:
            user = User.objects.create_user(
                username=username,
                email=clean_email[:150],
                password=new_password,
                first_name=first_name,
                last_name=last_name
            )
            
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'company': main_company, 'role': 'worker'}
            )
            found_count += 1
            print(f"✓ Dodan: {username}")
        except Exception as e:
            print(f"! Preskočen {username} zbog greške: {e}")

    print(f"==================================================")
    print(f" USPJEH: Dodano novih {found_count} radnika.")
    print(f" Ukupno u bazi: {User.objects.count()} korisnika.")
    print(f"==================================================")

if __name__ == '__main__':
    run_total_user_import()
