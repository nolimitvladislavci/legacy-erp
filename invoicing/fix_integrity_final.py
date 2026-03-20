import os
import sys

import django

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from invoicing.models import Invoice


def fix_and_protect():
    # 1. Čišćenje preostalog smeća (onaj jedan sa slike)
    deleted = Invoice.objects.filter(client_name__isnull=True).delete()[0]
    deleted += Invoice.objects.filter(client_name='').delete()[0]
    print(f"✓ Obrisano {deleted} neispravnih računa bez klijenta.")

    # 2. Sigurna modifikacija views.py (Append umjesto Replace)
    # Dodajemo pomoćnu funkciju za validaciju na kraj datoteke
    views_path = '/var/www/fina-connect/invoicing/views.py'

    validation_logic = """
# --- Sigurnosna validacija dodana od strane Gemini ---
def validate_invoice_data(data):
    if not data.get('client_name') or data.get('client_name').strip() == '':
        return False
    return True
"""
    with open(views_path, 'a', encoding='utf-8') as f:
        f.write(validation_logic)
    print("✓ Sigurnosna logika dodana na kraj views.py.")

if __name__ == "__main__":
    fix_and_protect()
