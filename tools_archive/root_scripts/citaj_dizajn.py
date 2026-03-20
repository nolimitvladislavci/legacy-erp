import os

BASE_DIR = '/var/www/fina-connect'

# Lokacije ključnih datoteka (core i templates)
FILES = [
    'templates/base.html',
    'templates/index.html',
    'core/urls.py',
    'core/views.py'
]

print("\n" + "="*80)
for f_path in FILES:
    full_path = os.path.join(BASE_DIR, f_path)
    print(f"📄 POČETAK DATOTEKE: {f_path}")
    print("-" * 80)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            print(f.read().strip())
    else:
        print(f"⚠️ Datoteka nije pronađena (vjerojatno se ne koristi ili je u drugoj mapi).")
    print("-" * 80)
    print(f"🛑 KRAJ DATOTEKE: {f_path}")
    print("="*80 + "\n")
