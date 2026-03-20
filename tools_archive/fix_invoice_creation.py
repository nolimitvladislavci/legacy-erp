#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

VIEWS_FILE = Path('/var/www/fina-connect/premium_booking/views.py')

print("🛠️ KIRURŠKI ZAHVAT: Popravak generiranja fakture u Premium modulu...")

if VIEWS_FILE.exists():
    content = VIEWS_FILE.read_text(encoding='utf-8')
    
    # Prvo provjeravamo imamo li potreban import za InvoiceItem
    if "from invoicing.models import Invoice" in content and "InvoiceItem" not in content:
        content = content.replace(
            "from invoicing.models import Invoice",
            "from invoicing.models import Invoice, InvoiceItem"
        )
    
    # Lociramo problematičnu liniju Invoice.objects.create(...)
    pattern = r"Invoice\.objects\.create\([^)]*\)"
    
    # Nova, ispravna logika za fakturu prema tvom modelu
    new_invoice_logic = """
            # Generiranje jedinstvenog broja predračuna
            import time
            temp_number = f"PR-{int(time.time())}"
            
            # 1. Kreiranje zaglavlja fakture
            invoice = Invoice.objects.create(
                doctype='P',  # Predračun
                number=temp_number,
                client_name=client.name if client else data['name'],
                client_email=email,
                date_issued=timezone.now(),
                subtotal=booking.total_price,
                total=booking.total_price,
                status='DRAFT',
                note=f"Automatska rezervacija: {res.name}"
            )
            
            # 2. Kreiranje stavke računa (InvoiceItem)
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Najam: {res.name}",
                quantity=1,
                unit_price=booking.total_price,
                total_price=booking.total_price
            )
    """
    
    # Zamjena stare neispravne linije novom logikom
    new_content = re.sub(pattern, new_invoice_logic.strip(), content)
    
    if new_content != content:
        VIEWS_FILE.write_text(new_content, encoding='utf-8')
        print("✅ Logika za kreiranje fakture je uspješno usklađena s bazom podataka.")
    else:
        print("ℹ️ Nije bilo potrebe za zamjenom. Kod je možda već popravljen.")

else:
    print(f"❌ GREŠKA: Ne mogu pronaći datoteku {VIEWS_FILE}")

# Restart servera
print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")

print("✨ ZAVRŠENO! Sada bi Premium rezervacija trebala proći i automatski generirati ispravnu fakturu.")
