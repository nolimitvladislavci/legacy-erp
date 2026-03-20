import os
import subprocess

def run_fix():
    config_path = '/etc/nginx/sites-enabled/fina-connect'
    backup_path = config_path + '.bak'
    static_path = '/var/www/fina-connect/static/'

    print("🚀 Pokrećem All-in-One popravak Nginxa i dozvola...")

    # 1. Backup i modifikacija Nginx konfiguracije [cite: 2026-02-17]
    if os.path.exists(config_path):
        os.system(f"cp {config_path} {backup_path}")
        with open(config_path, 'r') as f:
            content = f.read()
        
        if 'location /static/' not in content:
            # Ubacujemo static blok unutar server sekcije
            static_block = "\n    location /static/ {\n        alias " + static_path + ";\n        expires 30d;\n    }\n"
            # Tražimo prvu 'location /' i ubacujemo ispred nje
            updated_content = content.replace("location / {", static_block + "    location / {")
            with open(config_path, 'w') as f:
                f.write(updated_content)
            print("✓ Nginx konfiguracija ažurirana i backupirana.")
        else:
            print("- Nginx već ima definiranu /static/ lokaciju.")

    # 2. Popravak dozvola za statiku i aplikaciju [cite: 2026-02-17]
    os.system(f"chown -R www-data:www-data /var/www/fina-connect/invoicing/")
    os.system(f"chown -R www-data:www-data {static_path}")
    os.system(f"chmod -R 755 {static_path}")
    print("✓ Dozvole za www-data (chown) su osigurane.")

    # 3. Validacija i restart [cite: 2026-02-17]
    test = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if test.returncode == 0:
        os.system("systemctl restart nginx")
        os.system("supervisorctl restart fina-connect")
        print("✅ Sustav je uspješno restartan. Lokot i statika bi trebali raditi.")
    else:
        print("❌ Greška u Nginx sintaksi. Vraćam backup...")
        os.system(f"cp {backup_path} {config_path}")
        print(test.stderr)

if __name__ == "__main__":
    run_fix()
