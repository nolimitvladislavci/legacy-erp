import os, glob

burza_files = glob.glob('/var/www/fina-connect/**/burza/**/*.html', recursive=True)
print("\n=== TRAŽIM BURZA PREDLOŽAK ===")
for f in burza_files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
        # Tražimo datoteku koja sadrži riječi sa slike
        if 'NASLOV' in content or 'OPIS POSLA' in content or 'upit' in content.lower():
            print(f"📄 LOKACIJA: {f}")
            print("-" * 80)
            print(content)
            print("-" * 80)
