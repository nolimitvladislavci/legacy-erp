import os, subprocess, sys

def run(cmd):
    try:
        # Koristimo shell=True jer nam trebaju pipe-ovi i redirekcije
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pass # Ignoriramo greške kod kill naredbi ako proces ne postoji

def rebuild():
    print("🚀 Čišćenje sustava i rekonstrukcija okruženja...")

    # 1. Brutalno čišćenje porta 8000 i gunicorna
    os.system("fuser -k 8000/tcp > /dev/null 2>&1")
    os.system("pkill -9 -f gunicorn > /dev/null 2>&1")
    os.system("pkill -9 -f manage.py > /dev/null 2>&1")

    # 2. Rekonstrukcija venv-a
    if os.path.exists("venv"):
        os.system("rm -rf venv")
    
    print("📦 Kreiranje novog virtualnog okruženja...")
    os.system("python3 -m venv venv")
    
    # 3. Instalacija paketa direktno preko venv python-a (najsigurnije)
    pip_path = "venv/bin/pip"
    packages = [
        "django==5.1.6",
        "django-rosetta",
        "django-modeltranslation",
        "django-import-export",
        "djangorestframework",
        "django-extensions",
        "gunicorn",
        "psycopg2-binary",
        "Pillow"
    ]
    
    print(f"📥 Instalacija ovisnosti (ovo može potrajati minutu)...")
    os.system(f"{pip_path} install --upgrade pip > /dev/null")
    os.system(f"{pip_path} install {' '.join(packages)} > /dev/null")

    # 4. Čišćenje i dozvole
    os.system("find . -type d -name '__pycache__' -exec rm -rf {} +")
    os.system("chown -R www-data:www-data /var/www/fina-connect/")
    
    print("✅ Sustav je spreman. Restartam servise...")
    os.system("supervisorctl restart fina-connect")
    print("✨ Gotovo! Provjeri portal.")

if __name__ == "__main__":
    rebuild()
