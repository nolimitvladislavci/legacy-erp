import os
import sys

import django

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db.models import Q

from invoicing.models import Invoice
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def purge():
    print("🚀 Pokrećem završno čišćenje koristeći ISPRAVNA polja...")

    # Filtriramo prema poljima koja tvoj model stvarno ima: client_name i total [cite: 2026-02-17]
    bad_invoices = Invoice.objects.filter(
        Q(client_name__isnull=True) |
        Q(client_name='') |
        Q(total=0)
    )

    count = bad_invoices.count()
    if count > 0:
        for inv in bad_invoices:
            print(f"  - Brišem neispravan račun: {inv.number} (Klijent: {inv.client_name}, Iznos: {inv.total})")
        bad_invoices.delete()
        print(f"✅ Uspješno uklonjeno {count} neispravnih zapisa.")
    else:
        print("ℹ️ Nisu pronađeni neispravni računi.")

if __name__ == "__main__":
    purge()
