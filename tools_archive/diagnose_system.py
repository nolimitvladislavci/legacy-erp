import os
import sys
import django

# Inicijalizacija Django okruženja
sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.urls import get_resolver
from invoicing.models import Invoice

def check_zki_logic():
    print("\n--- ANALIZA FISKALNE LOGIKE ---")
    try:
        from invoicing import views
        import inspect
        source = inspect.getsource(views.generate_zki)
        print("Sadržaj generate_zki funkcije:\n")
        print(source)
    except Exception as e:
        print(f"Greška pri čitanju generate_zki: {e}")

def list_all_urls():
    print("\n--- REGISTRIRANI URL NAZIVI ---")
    resolver = get_resolver()
    for ns, (prefix, sub_resolver) in resolver.namespace_dict.items():
        print(f"Namespace: {ns} (Prefix: {prefix})")
        for url_name in sub_resolver.reverse_dict.keys():
            if isinstance(url_name, str):
                print(f"  - {ns}:{url_name}")

def check_certs():
    print("\n--- PROVJERA CERTIFIKATA ---")
    cert_dir = '/var/www/fina-connect/certs/'
    if os.path.exists(cert_dir):
        print(f"Datoteke u {cert_dir}: {os.listdir(cert_dir)}")
    else:
        print(f"Mapa {cert_dir} ne postoji.")

if __name__ == "__main__":
    check_zki_logic()
    list_all_urls()
    check_certs()
