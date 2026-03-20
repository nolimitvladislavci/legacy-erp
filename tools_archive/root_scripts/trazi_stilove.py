import os, glob

BASE_DIR = '/var/www/fina-connect'

# Tražimo CSS datoteke
css_files = glob.glob(os.path.join(BASE_DIR, 'static/**/*.css'), recursive=True)
# Tražimo i unutar glavnih template-a ako su stilovi tamo ubačeni
html_files = glob.glob(os.path.join(BASE_DIR, 'templates/**/*.html'), recursive=True)

all_files = css_files + html_files

print("\n" + "="*80)
print("🔍 TRAŽIM GLOBALNE STILOVE I TEME...")
print("="*80)

pronadeno = False

for f_path in all_files:
    try:
        with open(f_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Tražimo definicije root varijabli ili theme atribute
            if ':root' in content and '--' in content:
                pronadeno = True
                relative_path = f_path.replace(BASE_DIR + '/', '')
                print(f"\n📄 PRONAĐENE VARIJABLE U: {relative_path}")
                print("-" * 80)
                # Ispisujemo samo blokove gdje se definiraju teme
                lines = content.split('\n')
                is_printing = False
                for line in lines:
                    if ':root' in line or '[data-theme' in line:
                        is_printing = True
                    if is_printing:
                        print(line)
                    if '}' in line and is_printing:
                        is_printing = False
                        print("/* ... */")
                print("-" * 80)
    except Exception:
        pass

if not pronadeno:
    print("⚠️ Nisam pronašao standardne :root CSS varijable u static ni templates mapama.")
    print("Moguće je da su teme spremljene u bazi (dinamički) ili u specifičnoj datoteci koju nismo skenirali.")
print("="*80 + "\n")
