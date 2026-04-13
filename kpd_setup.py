"""
KPD mapiranje — kreira KPDCode model, popunjava najcesce sifre,
i automatski mapira grupe artikala.
Run: cd /var/www/fina-connect && source venv/bin/activate && python3 kpd_setup.py
"""
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django; django.setup()

from django.db import connection, DatabaseError, IntegrityError

# 1. Kreiraj tablicu ako ne postoji
with connection.cursor() as c:
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory_kpdcode (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            name_hr VARCHAR(200) NOT NULL DEFAULT '',
            vat_rate DECIMAL(5,2) DEFAULT 25.00,
            category VARCHAR(50) DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory_itemgroupkpd (
            id SERIAL PRIMARY KEY,
            group_name VARCHAR(100) UNIQUE NOT NULL,
            kpd_code VARCHAR(20) NOT NULL DEFAULT '',
            item_count INTEGER DEFAULT 0
        )
    """)
    print('Tables created')

# 2. Popuni KPD sifre (najcesce za nase klijente)
kpd_data = [
    # Optika
    ('32.50.41', 'Spectacles and similar', 'Naocale, korektivne i zastitne', 25),
    ('32.50.42', 'Contact lenses', 'Kontaktne lece', 25),
    ('32.50.43', 'Spectacle lenses', 'Lece za naocale', 25),
    ('32.50.50', 'Optical instruments', 'Opticni instrumenti', 25),
    # Usluge
    ('69.20.10', 'Accounting services', 'Racunovodstvene usluge', 25),
    ('69.20.21', 'Book-keeping services', 'Knjigovodstvene usluge', 25),
    ('69.20.29', 'Other accounting services', 'Ostale racunovodstvene usluge', 25),
    ('86.90.19', 'Other health services', 'Ostale zdravstvene usluge', 25),
    # Gradevina
    ('43.39.19', 'Other completion work', 'Ostali zavrsni gradevinski radovi', 25),
    ('43.29.19', 'Other installation work', 'Ostali instalacijski radovi', 25),
    ('43.21.10', 'Electrical installation', 'Elektroinstalacijski radovi', 25),
    ('43.22.11', 'Plumbing work', 'Vodoinstalacijski radovi', 25),
    ('43.22.12', 'Heating installation', 'Instalacija grijanja', 25),
    # Trgovina
    ('47.00.10', 'Retail trade services', 'Usluge maloprodaje', 25),
    ('46.00.10', 'Wholesale trade services', 'Usluge veleprodaje', 25),
    # Hrana i pice
    ('56.10.11', 'Restaurant services', 'Usluge restorana', 13),
    ('56.10.19', 'Other food serving', 'Ostale usluge pripreme hrane', 13),
    ('56.30.10', 'Beverage serving', 'Usluge tocenja pica', 25),
    ('10.71.11', 'Bread and rolls', 'Kruh i peciva', 5),
    # Auto
    ('45.20.11', 'Maintenance of motor vehicles', 'Odrzavanje motornih vozila', 25),
    ('45.20.13', 'Repair of motor vehicles', 'Popravak motornih vozila', 25),
    ('45.31.10', 'Vehicle parts wholesale', 'Veleprodaja dijelova za vozila', 25),
    # IT
    ('62.01.11', 'IT consulting', 'IT savjetovanje', 25),
    ('62.01.12', 'Software development', 'Razvoj softvera', 25),
    # Energija
    ('27.51.21', 'Electric water heaters', 'Elektricni bojleri', 25),
    ('27.11.10', 'Electric motors', 'Elektromotori', 25),
    ('27.40.10', 'Electric lighting', 'Elektricna rasvjeta', 25),
    # Solar
    ('27.11.50', 'Solar cells', 'Solarne celije/paneli', 25),
    ('27.12.10', 'Power distribution', 'Oprema za distribuciju energije', 25),
]

with connection.cursor() as c:
    for code, name_en, name_hr, vat in kpd_data:
        c.execute("""
            INSERT INTO inventory_kpdcode (code, name, name_hr, vat_rate, category)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET name_hr = EXCLUDED.name_hr
        """, [code, name_en, name_hr, vat, code.split('.')[0]])
    print(f'Inserted {len(kpd_data)} KPD codes')

# 3. Auto-mapiranje grupa na KPD sifre
group_kpd_map = {
    'OKVIRI U OPTIKAMA': '32.50.41',
    'DJECJI OKVIRI': '32.50.41',
    'SUNCANI OKVIRI': '32.50.41',
    'LECE RECEPTURA': '32.50.43',
    'LECE LAGER': '32.50.43',
    'KONTAKTNE LECE': '32.50.42',
    'ROBA U OPTICI (TEKUCINE I SL.)': '32.50.50',
    'USLUGA': '69.20.29',
    'VLASTITE USLUGE': '69.20.29',
    'KNJIGOVODSTVENE USLUGE': '69.20.21',
    'BOJLERI I DR.': '27.51.21',
    'REZERVNI DIJELOVI': '45.31.10',
    'AUTO DIJELOVI': '45.31.10',
    'REZ. DIO.': '45.31.10',
    'CIJEVI': '43.22.11',
    'NOSAC': '43.29.19',
    'STEZALJKA': '43.29.19',
    'INVERTER': '27.12.10',
    'SOLARNI PANEL': '27.11.50',
    'TOPLI NAPICI': '56.30.10',
    'SOKOVI': '56.30.10',
    'ALKOHOL': '56.30.10',
    'PIVO': '56.30.10',
    'VODA': '56.30.10',
    'PIZZE': '56.10.11',
    'GRILL': '56.10.11',
    'CLANARINA': '94.99.10',
    'FOTOKOPIRANJE': '82.19.11',
    'OSTALI MATERIJAL': '47.00.10',
    'ROBA ZA KRAJNJU POTROSNJU': '47.00.10',
    'ROBA': '47.00.10',
}

from inventory.models import InventoryItem
from collections import Counter
from django.core.exceptions import ObjectDoesNotExist

# Get group counts
descriptions = InventoryItem.objects.values_list('description', flat=True)
group_counts = Counter()
for d in descriptions:
    if d and ' - ' in d:
        group_counts[d.split(' - ')[0].strip()] += 1
    elif d:
        group_counts[d.strip()[:40]] += 1

mapped = 0
unmapped = 0
with connection.cursor() as c:
    for group_name, count in group_counts.most_common():
        # Normalize for matching
        normalized = group_name.upper().replace('Č','C').replace('Ć','C').replace('Š','S').replace('Ž','Z').replace('Đ','D')
        kpd = group_kpd_map.get(normalized, '')
        if not kpd:
            # Try partial match
            for key, val in group_kpd_map.items():
                if key in normalized or normalized in key:
                    kpd = val
                    break
        c.execute("""
            INSERT INTO inventory_itemgroupkpd (group_name, kpd_code, item_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (group_name) DO UPDATE SET kpd_code = EXCLUDED.kpd_code, item_count = EXCLUDED.item_count
        """, [group_name, kpd, count])
        if kpd:
            mapped += 1
        else:
            unmapped += 1

print(f'\nGrupe mapirane: {mapped}')
print(f'Grupe BEZ KPD:  {unmapped}')
if unmapped:
    print('\nNemapirane grupe (trebaju rucno mapiranje):')
    for g, cnt in group_counts.most_common():
        norm = g.upper().replace('Č','C').replace('Ć','C').replace('Š','S').replace('Ž','Z').replace('Đ','D')
        if norm not in group_kpd_map and not any(k in norm or norm in k for k in group_kpd_map):
            print(f'  {cnt:>5}x  {g}')
