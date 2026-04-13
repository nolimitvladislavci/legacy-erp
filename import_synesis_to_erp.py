# Import Synesis JSON export into ERP database
# Partners -> partners_partner, Items -> inventory_inventoryitem
import json
import os
import sys

import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from decimal import Decimal, InvalidOperation

from companies.models import Company
from inventory.models import InventoryItem
from partners.models import Partner

# Load JSON
print("Loading synesis_export.json...")
with open('/var/www/fina-connect/synesis_export.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Companies in export: {list(data.keys())}")

# Company name -> DB company mapping
COMPANY_MAP = {
    'Korpaš d.o.o.': Company.objects.filter(name__icontains='korpa', is_umbrella=True).first(),
    'O.P.G. Kruljac Slađana': Company.objects.filter(oib='41439993573').first(),
    'KUD Dukat Vladislavci': Company.objects.filter(name__icontains='KUD Dukat').first(),
    'Furdi, obrt': Company.objects.filter(name__icontains='Furdi').first(),
    'Dubinsko Čišćenje Čizo': Company.objects.filter(name__icontains='Dubinsko').first(),
    'Udruga Uniwerzum': Company.objects.filter(name__icontains='Uniwerzum').first(),
}

for name, co in COMPANY_MAP.items():
    if co:
        print(f"  {name} -> {co.name} (ID: {co.id})")
    else:
        print(f"  {name} -> NOT FOUND!")

def safe_decimal(val, default='0'):
    if val is None or val == '':
        return Decimal(default)
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(default)

def safe_str(val, max_len=255):
    if val is None:
        return ''
    return str(val).strip()[:max_len]

# ══════════════════════════════════════════════════
# Import strategy: use LATEST year for each company
# to get most current partners/items, but also
# collect unique entries from ALL years
# ══════════════════════════════════════════════════

total_partners = 0
total_items = 0

for company_name, years_data in data.items():
    co = COMPANY_MAP.get(company_name)
    if not co:
        print(f"\nSKIP: {company_name} (no matching company)")
        continue

    print(f"\n{'='*60}")
    print(f"IMPORTING: {company_name} -> {co.name}")
    print(f"{'='*60}")

    # Collect unique partners across all years (by name+oib combo)
    all_partners = {}
    all_items = {}

    sorted_years = sorted(years_data.keys(), key=lambda x: int(x))
    for year in sorted_years:
        yd = years_data[year]

        # Partners
        for p in yd.get('partners', []):
            name = safe_str(p.get('NAME', p.get('Name', '')))
            if not name:
                continue
            oib = safe_str(p.get('OIB', p.get('Oib', '')), 20)
            key = f"{name}|{oib}"
            all_partners[key] = {
                'name': name,
                'oib': oib,
                'city': safe_str(p.get('CITY', p.get('City', p.get('MJESTO', ''))), 100),
                'address': safe_str(p.get('ADDRESS', p.get('Address', p.get('ADRESA', ''))), 255),
                'phone': safe_str(p.get('PHONE', p.get('Phone', p.get('TEL', ''))), 50),
                'email': safe_str(p.get('EMAIL', p.get('Email', '')), 100),
                'zip_code': safe_str(p.get('ZIP', p.get('Zip', p.get('POSTBR', ''))), 20),
                'country': safe_str(p.get('COUNTRY', p.get('Country', p.get('DRZAVA', ''))), 50),
                'iban': safe_str(p.get('IBAN', p.get('Iban', p.get('ZIRO', ''))), 50),
                'year_first': int(year),
                'year_last': int(year),
            }
            # Update year range
            if key in all_partners and all_partners[key].get('year_first', 9999) > int(year):
                all_partners[key]['year_first'] = int(year)

        # Items
        for it in yd.get('items', []):
            name = safe_str(it.get('NAME', it.get('Name', '')))
            if not name:
                continue
            code = safe_str(it.get('CODE', it.get('Code', it.get('SIFRA', ''))), 50)
            key = f"{name}|{code}"
            all_items[key] = {
                'name': name,
                'code': code,
                'unit': safe_str(it.get('UNIT', it.get('Unit', it.get('JM', ''))), 20),
                'price': safe_decimal(it.get('PRICE', it.get('Price', it.get('CIJENA', 0)))),
                'purchase_price': safe_decimal(it.get('PURCHASEPRICE', it.get('PurchasePrice', it.get('NABCIJENA', 0)))),
                'tax_rate': safe_decimal(it.get('TAXRATE', it.get('TaxRate', it.get('PDV', 25)))),
                'barcode': safe_str(it.get('BARCODE', it.get('Barcode', it.get('BARKOD', ''))), 50),
                'group': safe_str(it.get('GROUP', it.get('Group', it.get('GRUPA', ''))), 100),
            }

    # Create partners in DB
    created_p = 0
    for key, pd in all_partners.items():
        if not pd['name']:
            continue
        existing = Partner.objects.filter(company=co, name=pd['name']).first()
        if not existing:
            Partner.objects.create(
                company=co,
                name=pd['name'],
                oib=pd['oib'],
                city=pd['city'],
                address=pd['address'],
                phone=pd.get('phone', ''),
                email=pd.get('email', ''),
            )
            created_p += 1

    # Create items in DB
    created_i = 0
    for key, itd in all_items.items():
        if not itd['name']:
            continue
        sku = itd['code'] if itd['code'] else f"SYN-{hash(itd['name']) % 100000:05d}"
        existing = InventoryItem.objects.filter(company=co, name=itd['name']).first()
        if not existing:
            InventoryItem.objects.create(
                company=co,
                name=itd['name'],
                sku=sku,
                unit=itd.get('unit', 'kom') or 'kom',
                selling_price=itd['price'],
                purchase_price=itd['purchase_price'],
                tax_rate=itd['tax_rate'],
                barcode=itd.get('barcode', ''),
            )
            created_i += 1

    print(f"  Partners: {len(all_partners)} unique -> {created_p} created")
    print(f"  Items: {len(all_items)} unique -> {created_i} created")
    total_partners += created_p
    total_items += created_i

# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════
print(f"\n{'='*60}")
print("IMPORT COMPLETE")
print(f"Total partners created: {total_partners}")
print(f"Total items created: {total_items}")
print(f"{'='*60}")

for co in Company.objects.all().order_by('name'):
    pc = Partner.objects.filter(company=co).count()
    ic = InventoryItem.objects.filter(company=co).count()
    if pc > 0 or ic > 0:
        print(f"  {co.name}: {pc} partners, {ic} items")
