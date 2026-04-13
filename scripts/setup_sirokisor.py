#!/usr/bin/env python3
"""
Setup Široki Šor — digitalni jelovnik + inventura + stolovi za Korpaš d.o.o.

Koristi se: cd /var/www/fina-connect && python manage.py shell < scripts/setup_sirokisor.py

Što radi:
1. Kreira CompanyBranch "Široki Šor" pod Korpaš d.o.o.
2. Kreira DigitalMenu
3. Kreira 6 MenuCategory + 66 MenuItem
4. Kreira InventoryItem za svaki artikl (drink/food)
5. Kreira MenuItemIngredient veze (jelovnik ↔ inventura)
6. Kreira 20 Table + 20 TableQR (Lokal 1-8, Šank 1-4, Terasa 1-8)
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.utils.text import slugify
from companies.models import Company, CompanyBranch
from gastro_menu.models import DigitalMenu, MenuCategory, MenuItem, MenuItemIngredient, TableQR
from inventory.models import InventoryItem
from pos.models import Table
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════

KORPAS_ID = '0240b7d9'  # Prefix za lookup

# Cijenik Široki Šor — 66 artikala
MENU_DATA = {
    'Žestoka pića': {
        'sort_order': 1,
        'items': [
            ('Vilijamovka', 2.50, 'drink'),
            ('Šljivovica', 2.50, 'drink'),
            ('Travarica', 2.50, 'drink'),
            ('Medica', 2.50, 'drink'),
            ('Pelinkovac', 2.50, 'drink'),
            ('Loza', 2.50, 'drink'),
            ('Vinjak', 2.50, 'drink'),
            ('Vodka', 2.50, 'drink'),
            ('Rum', 2.50, 'drink'),
            ('Gin', 2.50, 'drink'),
            ('Jack Daniels', 4.00, 'drink'),
            ('Jägermeister', 3.00, 'drink'),
            ('Ballantine\'s', 3.50, 'drink'),
            ('Tullamore Dew', 3.50, 'drink'),
            ('Stock 84', 2.50, 'drink'),
        ],
    },
    'Pivo': {
        'sort_order': 2,
        'items': [
            ('Karlovačko 0.5L', 3.00, 'drink'),
            ('Karlovačko 0.33L', 2.50, 'drink'),
            ('Heineken 0.5L', 3.50, 'drink'),
            ('Heineken 0.33L', 3.00, 'drink'),
            ('Ožujsko 0.5L', 3.00, 'drink'),
            ('Ožujsko 0.33L', 2.50, 'drink'),
            ('Pan 0.5L', 3.00, 'drink'),
            ('Staropramen 0.5L', 3.50, 'drink'),
            ('Točeno pivo 0.5L', 3.00, 'drink'),
            ('Točeno pivo 0.3L', 2.50, 'drink'),
            ('Radler 0.5L', 3.00, 'drink'),
            ('Nealko pivo 0.5L', 3.00, 'drink'),
        ],
    },
    'Vino': {
        'sort_order': 3,
        'items': [
            ('Graševina 0.2L', 2.50, 'drink'),
            ('Graševina 1L', 10.00, 'drink'),
            ('Frankovka 0.2L', 2.50, 'drink'),
            ('Frankovka 1L', 10.00, 'drink'),
            ('Rajnski rizling 0.2L', 3.00, 'drink'),
            ('Rajnski rizling 1L', 12.00, 'drink'),
            ('Gemišt 0.2L', 2.00, 'drink'),
            ('Bambus 0.2L', 2.00, 'drink'),
        ],
    },
    'Bezalkoholna pića': {
        'sort_order': 4,
        'items': [
            ('Coca-Cola 0.25L', 2.50, 'drink'),
            ('Coca-Cola 0.5L', 3.50, 'drink'),
            ('Fanta 0.25L', 2.50, 'drink'),
            ('Sprite 0.25L', 2.50, 'drink'),
            ('Schweppes Tonic 0.25L', 2.50, 'drink'),
            ('Cedevita 0.25L', 2.00, 'drink'),
            ('Sok naranča 0.2L', 2.50, 'drink'),
            ('Sok jabuka 0.2L', 2.50, 'drink'),
            ('Mineralna voda 0.25L', 2.00, 'drink'),
            ('Mineralna voda 0.75L', 3.50, 'drink'),
            ('Obična voda 0.25L', 1.50, 'drink'),
            ('Red Bull 0.25L', 4.00, 'drink'),
        ],
    },
    'Kava i topli napici': {
        'sort_order': 5,
        'items': [
            ('Espresso', 1.50, 'drink'),
            ('Kava s mlijekom', 1.80, 'drink'),
            ('Cappuccino', 2.00, 'drink'),
            ('Bijela kava', 2.00, 'drink'),
            ('Čaj', 1.50, 'drink'),
            ('Topla čokolada', 2.50, 'drink'),
            ('Kuhano vino', 2.50, 'drink'),
        ],
    },
    'Hrana': {
        'sort_order': 6,
        'items': [
            ('Ćevapi 10 kom', 8.00, 'food'),
            ('Pljeskavica', 7.00, 'food'),
            ('Ražnjići 2 kom', 8.00, 'food'),
            ('Kobasica s roštilja', 6.00, 'food'),
            ('Miješano meso za 2', 18.00, 'food'),
            ('Pommes frites', 3.00, 'food'),
            ('Salata sezonska', 3.00, 'food'),
            ('Ajvar', 1.50, 'food'),
            ('Kajmak', 2.00, 'food'),
            ('Lepinja', 1.00, 'food'),
            ('Sir domaći', 4.00, 'food'),
            ('Kulen narezak', 5.00, 'food'),
        ],
    },
}

# Stolovi
TABLES = [
    # (name, table_type, capacity, floor/zone)
    ('Lokal 1', 'table', 4, 'Lokal'),
    ('Lokal 2', 'table', 4, 'Lokal'),
    ('Lokal 3', 'table', 4, 'Lokal'),
    ('Lokal 4', 'table', 4, 'Lokal'),
    ('Lokal 5', 'table', 6, 'Lokal'),
    ('Lokal 6', 'table', 6, 'Lokal'),
    ('Lokal 7', 'table', 4, 'Lokal'),
    ('Lokal 8', 'table', 4, 'Lokal'),
    ('Šank 1', 'bar', 2, 'Šank'),
    ('Šank 2', 'bar', 2, 'Šank'),
    ('Šank 3', 'bar', 2, 'Šank'),
    ('Šank 4', 'bar', 2, 'Šank'),
    ('Terasa 1', 'terrace', 4, 'Terasa'),
    ('Terasa 2', 'terrace', 4, 'Terasa'),
    ('Terasa 3', 'terrace', 4, 'Terasa'),
    ('Terasa 4', 'terrace', 6, 'Terasa'),
    ('Terasa 5', 'terrace', 6, 'Terasa'),
    ('Terasa 6', 'terrace', 4, 'Terasa'),
    ('Terasa 7', 'terrace', 4, 'Terasa'),
    ('Terasa 8', 'terrace', 4, 'Terasa'),
]


# ═══════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════

def run():
    print('=' * 60)
    print('SETUP ŠIROKI ŠOR — Korpaš d.o.o.')
    print('=' * 60)

    # 1. Find Korpaš company
    company = Company.objects.filter(id__startswith=KORPAS_ID).first()
    if not company:
        company = Company.objects.filter(name__icontains='Korpa').first()
    if not company:
        print('ERROR: Korpaš d.o.o. nije pronađen u bazi!')
        print('Dostupne firme:')
        for c in Company.objects.all()[:10]:
            print(f'  {c.id} — {c.name}')
        return
    print(f'✓ Company: {company.name} (ID: {company.id})')

    # 2. Create Branch
    branch, created = CompanyBranch.objects.get_or_create(
        parent_company=company,
        name='Široki Šor',
        defaults={
            'branch_type': 'restaurant',
            'is_active': True,
        },
    )
    print(f'{"✓ Created" if created else "· Exists"} Branch: {branch.name}')

    # 3. Create DigitalMenu
    menu_slug = slugify(f'{company.name}-siroki-sor')
    menu, created = DigitalMenu.objects.get_or_create(
        company=company,
        slug=menu_slug,
        defaults={
            'name': 'Široki Šor — Jelovnik',
            'is_active': True,
            'primary_color': '#8B4513',
        },
    )
    print(f'{"✓ Created" if created else "· Exists"} Menu: {menu.name} (slug: {menu.slug})')

    # 4. Create Categories + MenuItems + InventoryItems
    total_items = 0
    total_inventory = 0

    for cat_name, cat_data in MENU_DATA.items():
        category, created = MenuCategory.objects.get_or_create(
            menu=menu,
            name=cat_name,
            defaults={
                'sort_order': cat_data['sort_order'],
                'is_active': True,
            },
        )

        for idx, (item_name, price, inv_category) in enumerate(cat_data['items']):
            # MenuItem
            menu_item, mi_created = MenuItem.objects.get_or_create(
                category=category,
                name=item_name,
                defaults={
                    'price': Decimal(str(price)),
                    'is_available': True,
                    'sort_order': idx,
                },
            )
            if mi_created:
                total_items += 1

            # InventoryItem
            sku = slugify(item_name)[:40]
            inv_item, inv_created = InventoryItem.objects.get_or_create(
                company=company,
                sku=sku,
                defaults={
                    'name': item_name,
                    'category': inv_category,
                    'unit': 'kom' if inv_category == 'drink' else 'por',
                    'quantity': Decimal('50'),
                    'min_quantity': Decimal('10'),
                    'purchase_price': Decimal(str(round(price * 0.4, 2))),
                    'unit_price': Decimal(str(price)),
                    'is_active': True,
                },
            )
            if inv_created:
                total_inventory += 1

            # MenuItemIngredient — link menu ↔ inventory
            MenuItemIngredient.objects.get_or_create(
                menu_item=menu_item,
                name=item_name,
                defaults={
                    'is_highlighted': False,
                },
            )

    print(f'✓ MenuItems: {total_items} created')
    print(f'✓ InventoryItems: {total_inventory} created')

    # 5. Create Tables + TableQR
    total_tables = 0
    total_qr = 0

    for table_name, table_type, capacity, zone in TABLES:
        # POS Table
        table, t_created = Table.objects.get_or_create(
            company=company,
            name=table_name,
            defaults={
                'branch': branch,
                'table_type': table_type,
                'capacity': capacity,
                'floor': zone,
                'is_active': True,
            },
        )
        if t_created:
            total_tables += 1

        # TableQR (gastro_menu)
        tqr, qr_created = TableQR.objects.get_or_create(
            company=company,
            table_number=table_name,
            defaults={
                'menu': menu,
                'table_zone': zone,
                'ordering_enabled': True,
            },
        )
        if qr_created:
            total_qr += 1

    print(f'✓ Tables: {total_tables} created')
    print(f'✓ TableQR: {total_qr} created')

    # 6. Summary
    print()
    print('=' * 60)
    print('SETUP COMPLETE')
    print('=' * 60)
    print(f'Company:     {company.name}')
    print(f'Branch:      {branch.name} (type: {branch.branch_type})')
    print(f'Menu:        {menu.name} (slug: {menu.slug})')
    print(f'Categories:  {MenuCategory.objects.filter(menu=menu).count()}')
    print(f'MenuItems:   {MenuItem.objects.filter(category__menu=menu).count()}')
    print(f'Inventory:   {InventoryItem.objects.filter(company=company, category__in=["food", "drink"]).count()} (food+drink)')
    print(f'Tables:      {Table.objects.filter(company=company, branch=branch).count()}')
    print(f'QR Codes:    {TableQR.objects.filter(company=company, menu=menu).count()}')
    print()
    print(f'Digital menu URL: /gastro/menu/{menu.slug}/')
    print(f'Admin panel:      /gastro/admin/')


run()
