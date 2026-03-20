#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

MODELS_FILE = Path('/var/www/fina-connect/appointments/models.py')
VIEWS_FILE = Path('/var/www/fina-connect/premium_booking/views.py')

print("🛠️ KIRURŠKI ZAHVAT: Dodavanje polja 'company' i migracija baze...")

# 1. AŽURIRANJE MODELA
models_content = MODELS_FILE.read_text(encoding='utf-8')
changed_models = False

if "company = models.ForeignKey('companies.Company'" not in models_content:
    # Dodavanje u Appointment
    models_content = re.sub(
        r"(class Appointment\(models\.Model\):)", 
        r"\1\n    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Tvrtka')",
        models_content
    )
    # Dodavanje u BookingResource
    models_content = re.sub(
        r"(class BookingResource\(models\.Model\):)", 
        r"\1\n    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Tvrtka')",
        models_content
    )
    MODELS_FILE.write_text(models_content, encoding='utf-8')
    changed_models = True
    print("✅ Polje 'company' uspješno upisano u models.py.")

# 2. OSIGURANJE LOGIKE U VIEWS (Ako je prethodno obrisana)
views_content = VIEWS_FILE.read_text(encoding='utf-8')
changed_views = False

if "defaults={'company': owner_company}" not in views_content and "defaults={" in views_content:
    # Ako defaults postoji, ali nema company
    views_content = re.sub(
        r"defaults=\{([^}]*)\}",
        r"defaults={\1, 'company': owner_company}",
        views_content
    )
    changed_views = True
elif "defaults=" not in views_content and "ERPResource.objects.get_or_create(name=res.name)" in views_content:
    # Ako uopće nema defaults bloka
    views_content = views_content.replace(
        "ERPResource.objects.get_or_create(name=res.name)",
        "ERPResource.objects.get_or_create(name=res.name, defaults={'company': owner_company})"
    )
    changed_views = True

if "company=owner_company" not in views_content and "status='scheduled'" in views_content:
    views_content = views_content.replace(
        "status='scheduled', color='#c9a84c'",
        "status='scheduled', color='#c9a84c', company=owner_company"
    )
    changed_views = True

if changed_views:
    VIEWS_FILE.write_text(views_content, encoding='utf-8')
    print("✅ Logika u views.py usklađena s novom bazom.")

# 3. MIGRACIJE BAZE PODATAKA
if changed_models:
    print("⚙️ Generiram migracije (makemigrations)...")
    os.system("bash -c 'source /var/www/fina-connect/venv/bin/activate && cd /var/www/fina-connect && python manage.py makemigrations appointments'")
    
    print("⚙️ Zapisujem u bazu (migrate)...")
    os.system("bash -c 'source /var/www/fina-connect/venv/bin/activate && cd /var/www/fina-connect && python manage.py migrate appointments'")

print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ ZAVRŠENO! Baza podataka je sada spremna za Premium rezervacije.")
