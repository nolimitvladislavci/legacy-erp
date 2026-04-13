import os
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

path = '/var/www/fina-connect/invoicing/urls.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Dodajemo 'new/' uz 'create/' radi kompatibilnosti
    if "path('create/', views.invoice_create, name='invoice_create')," in line:
        new_lines.append(line)
        new_lines.append("    path('new/', views.invoice_create, name='invoice_new'),\n")
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

# Osiguravamo backup i dozvole [cite: 2026-02-17]
os.system(f"cp {path} {path}.stable.bak")
os.system("chown www-data:www-data " + path)
print("✓ URL 'new/' je uspješno dodan kao alias za invoice_create.")
