import os
import django
import sys

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from invoicing.models import Invoice

def restore():
    # 1. Čišćenje preostalog računa bez klijenta (KNJ-2026-0010)
    # Koristimo client_name jer smo utvrdili da partner ne postoji u modelu
    bad_ones = Invoice.objects.filter(client_name__isnull=True) | Invoice.objects.filter(client_name='')
    count = bad_ones.count()
    bad_ones.delete()
    print(f"✓ Obrisan(o) {count} neispravnih računa bez klijenta.")

    # 2. Popravak views.py - vraćanje iz backupa ako postoji
    views_path = '/var/www/fina-connect/invoicing/views.py'
    backup_path = views_path + '.bak'
    if os.path.exists(backup_path):
        os.system(f"cp {backup_path} {views_path}")
        print("✓ Views.py vraćen iz backupa (sanacija 500 greške).")
    else:
        print("⚠ Backup nije pronađen, views.py ostaje nepromijenjen. Potrebna ručna provjera.")

if __name__ == "__main__":
    restore()
