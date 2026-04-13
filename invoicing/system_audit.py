import os
import sys

import django
from django.db.models import Sum

# Inicijalizacija okruženja
sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from invoicing.models import Invoice, InvoiceItem
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def run_audit():
    print("=== IZVJEŠTAJ O STANJU BAZE (INVOICING) ===")

    # 1. Ukupni brojevi
    total_invoices = Invoice.objects.count()
    total_amount = Invoice.objects.aggregate(Sum('total'))['total__sum'] or 0

    # 2. Provjera kritičnih polja (client_name)
    invalid_clients = Invoice.objects.filter(django.db.models.Q(client_name__isnull=True) | django.db.models.Q(client_name='')).count()

    # 3. Provjera računa bez stavki
    invoices_with_items = InvoiceItem.objects.values('invoice').distinct().count()
    invoices_without_items = total_invoices - invoices_with_items

    # 4. Statusi plaćanja
    paid_count = Invoice.objects.filter(status='Plaćeno').count() # Provjeri točan naziv statusa u tvom modelu
    draft_count = Invoice.objects.filter(status='Nacrt').count()

    print(f"Ukupno računa u bazi: {total_invoices}")
    print(f"Ukupna vrijednost: {total_amount:.2f} EUR")
    print("-" * 40)
    print(f"Računa bez imena klijenta: {invalid_clients}")
    print(f"Računa bez ijedne stavke: {invoices_without_items}")
    print("-" * 40)
    print(f"Broj plaćenih računa: {paid_count}")
    print(f"Broj računa u nacrtu: {draft_count}")

    if invalid_clients == 0 and invoices_without_items == 0:
        print("\n✅ STATUS: Baza je strukturno ispravna.")
    else:
        print("\n⚠ STATUS: Pronađene su nepravilnosti u integritetu podataka.")

if __name__ == "__main__":
    run_audit()
