import os
import sys

import django

sys.path.append("/var/www/fina-connect")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q

from invoicing.models import Invoice


def purge():
    print("🚀 Pokrećem završno čišćenje neispravnih računa...")

    # Hvatanje svih rubnih slučajeva: NULL klijent, prazan klijent ili nula iznos
    bad_invoices = Invoice.objects.filter(Q(partner__isnull=True) | Q(total=0))

    count = bad_invoices.count()
    if count > 0:
        for inv in bad_invoices:
            print(f"  - Brišem neispravan račun: {inv.number} (Iznos: {inv.total})")
        bad_invoices.delete()
        print(f"✅ Uspješno uklonjeno {count} neispravnih zapisa.")
    else:
        print("ℹ️ Nisu pronađeni neispravni računi.")


if __name__ == "__main__":
    purge()
