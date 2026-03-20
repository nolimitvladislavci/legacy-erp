import os, glob

BASE_DIR = '/var/www/fina-connect'

FILES = [
    'website/urls.py',
    'website/views.py'
]

# Pronađi sve HTML datoteke unutar website templates mape
html_files = glob.glob(os.path.join(BASE_DIR, 'website/templates/**/*.html'), recursive=True)
for f in html_files:
    FILES.append(f.replace(BASE_DIR + '/', ''))

print("\n" + "="*80)
for f_path in FILES:
    full_path = os.path.join(BASE_DIR, f_path)
    print(f"📄 POČETAK DATOTEKE: {f_path}")
    print("-" * 80)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            print(f.read().strip())
    else:
        print(f"⚠️ Datoteka nije pronađena.")
    print("-" * 80)
    print(f"🛑 KRAJ DATOTEKE: {f_path}")
    print("="*80 + "\n")
