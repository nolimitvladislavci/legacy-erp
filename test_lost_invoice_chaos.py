import inspect
import os
import sys
from importlib import import_module

sys.path.append("/var/www/fina-connect")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.db import DatabaseError, IntegrityError

print("=" * 70)
print(" FINA-CONNECT CHAOS MONKEY - DIAGNOSTIČKI TEST POUZDANOSTI (FAZA 1)")
print("=" * 70)

# 1. TEST: Celery Smrtna Zona
print("\n[1] TESTIRANJE CELERY KONFIGURACIJE (Gubitak zadatka pri OOM-u)")
acks_late = getattr(settings, "CELERY_TASK_ACKS_LATE", False)
reject_on_worker_lost = getattr(settings, "CELERY_TASK_REJECT_ON_WORKER_LOST", False)

if not acks_late:
    print(" ❌ KRITIČNO: CELERY_TASK_ACKS_LATE nije postavljen na True!")
    print("    -> Ako Linux ubije worker proces (zbog RAM-a), račun koji se obrađuje je TRAJNO IZGUBLJEN.")
else:
    print(" ✅ CELERY_TASK_ACKS_LATE je aktivan.")

if not reject_on_worker_lost:
    print(" ❌ UPOZORENJE: CELERY_TASK_REJECT_ON_WORKER_LOST je isključen.")
    print("    -> Zadaci iz mrtvih workera se neće automatski vratiti u red čekanja.")

# 2. EKSTRAKCIJA MODELA (Pravilo: Nema nagađanja polja)
print("\n[2] DINAMIČKA ANALIZA MODELA (Priprema za sintetičku injekciju)")
target_models = [("konto", "JournalEntry"), ("konto", "LedgerLine"), ("smart_import", "ImportBatch")]

for app_label, model_name in target_models:
    try:
        model = apps.get_model(app_label, model_name)
        fields = [f.name for f in model._meta.get_fields() if not f.is_relation or f.many_to_one]
        print(f" ✅ Model lociran: {app_label}.{model_name}")
        print(f"    Polja za injekciju: {', '.join(fields)}")
    except (ValueError, TypeError) as e:
        print(f" ❌ Greška pri učitavanju modela {app_label}.{model_name}: {e}")

# 3. TEST: Logika baze i IMAP Taska
print("\n[3] ANALIZA KODA ZA TRANSACTION.ATOMIC (Sprječavanje 'Limbo' stanja)")
try:
    task_module = import_module("smart_import.tasks")
    if hasattr(task_module, "fetch_invoices_from_email"):
        source_code = inspect.getsource(task_module.fetch_invoices_from_email)
        if "transaction.atomic" not in source_code:
            print(" ❌ KRITIČNO: fetch_invoices_from_email ne koristi @transaction.atomic!")
            print("    -> Ako API padne nakon čitanja maila, račun ostaje 'Pročitan' na IMAP-u, a u bazi ga NEMA.")
        else:
            print(" ✅ Pronađen transaction.atomic unutar IMAP taska.")
    else:
        print(" ⚠️ Funkcija fetch_invoices_from_email nije pronađena u smart_import.tasks.")
except (IntegrityError, DatabaseError) as e:
    print(f" ⚠️ Nije moguće analizirati kod IMAP taska: {e}")

print("=" * 70)
print(" ZAVRŠETAK TESTA. ČEKAM ISPIS ZA KREIRANJE SKRIPTE ZA INJEKCIJU (FAZA 2).")
print("=" * 70)
