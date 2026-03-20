import os
import sys
import django

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def examine():
    print("\n--- ANALIZA ACCOUNTS MODULA ---")
    # Provjera modela
    from django.contrib.auth.models import User
    print(f"Ukupno korisnika u bazi: {User.objects.count()}")
    
    # Provjera datoteka
    paths = ['accounts/views.py', 'accounts/urls.py', 'accounts/models.py']
    for p in paths:
        full_p = os.path.join('/var/www/fina-connect', p)
        if os.path.exists(full_p):
            print(f"Datoteka {p} POSTOJI.")
        else:
            print(f"Datoteka {p} NEDOSTAJE.")

examine()
