#!/usr/bin/env python3
"""
BORG-0 Faza 2: Haiku AI klasifikacija preostalih 'other' artikala.
Batch po 50, ~$0.25 ukupno za ~3000 artikala.

Pokretanje:
  ./venv/bin/python scripts/borg0_haiku_classify.py --dry-run
  ./venv/bin/python scripts/borg0_haiku_classify.py --execute
"""
import json
import os
import sys
import time

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from collections import Counter

import anthropic
from django.db import DatabaseError

# Učitaj API key iz .env
from dotenv import load_dotenv

from inventory.models import InventoryItem

load_dotenv('/var/www/fina-connect/.env')

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

VALID_CLASSES = {'tangible', 'service', 'intangible', 'asset', 'financial'}
VALID_FISCAL = {'standard', 'service_cash', 'exempt_pdv', 'no_fiscal', 'currency', 'pfand'}
VALID_CATS = {'material', 'tool', 'equipment', 'consumable', 'product', 'service',
              'food', 'drink', 'dessert', 'special', 'other'}


def ai_classify_batch(items_data):
    """Pošalji batch od max 50 artikala Haiku-u."""
    items_json = json.dumps([
        {'id': i['id'], 'name': i['name']}
        for i in items_data
    ], ensure_ascii=False)

    prompt = f"""Klasificiraj poslovne artikle. Za svaki vrati JSON objekt.

Polja:
- id: isti kao ulaz
- item_class: "tangible" | "service" | "intangible" | "asset"
- fiscal_treatment: "standard" | "service_cash" | "exempt_pdv" | "no_fiscal" | "pfand"
- category: "material" | "tool" | "equipment" | "consumable" | "product" | "service" | "food" | "drink" | "other"

Pravila:
- Fizička roba (materijal, hrana, piće, alati, oprema) → tangible + standard
- Usluge (rad, montaža, servis, prijevoz) → service + service_cash
- Agrohemija, pesticidi, gnojiva → tangible + standard + material
- Vozila, strojevi > 3500 EUR → asset + no_fiscal + equipment
- Članarine, donacije → tangible + exempt_pdv + service
- Naočale, leće, okviri → tangible + standard + product
- Ako ne znaš → tangible + standard + other

Vrati SAMO JSON array. Bez teksta, bez markdown.

Artikli:
{items_json}"""

    try:
        resp = client.messages.create(
            model='claude-3-5-haiku-20241022',
            max_tokens=4000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        results = json.loads(raw)
        # Validiraj
        for r in results:
            if r.get('item_class') not in VALID_CLASSES:
                r['item_class'] = 'tangible'
            if r.get('fiscal_treatment') not in VALID_FISCAL:
                r['fiscal_treatment'] = 'standard'
            if r.get('category') not in VALID_CATS:
                r['category'] = 'other'
        return results
    except (json.JSONDecodeError, ValueError) as e:
        print(f'  AI error: {e}')
        return []


def run(dry_run=True, batch_size=50):
    others = InventoryItem.objects.filter(
        category='other', item_class='tangible', fiscal_treatment='standard'
    ).values('id', 'name')

    total = others.count()
    print(f'BORG-0 Haiku: {total} artikala za AI klasifikaciju')
    print(f'Batch: {batch_size}, Procijenjeni trošak: ~${total * 0.00008:.2f}')
    print()

    stats = Counter()
    classified = 0
    errors = 0
    all_results = []

    items_list = list(others)

    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(items_list) + batch_size - 1) // batch_size
        print(f'  Batch {batch_num}/{total_batches} ({len(batch)} artikala)...', end=' ', flush=True)

        results = ai_classify_batch(batch)
        if not results:
            print('FAIL')
            errors += len(batch)
            continue

        # Map results by ID
        result_map = {r['id']: r for r in results}

        for item_data in batch:
            r = result_map.get(item_data['id'])
            if not r:
                errors += 1
                continue

            classified += 1
            stats[r.get('category', 'other')] += 1
            all_results.append(r)

            if not dry_run:
                try:
                    InventoryItem.objects.filter(pk=item_data['id']).update(
                        item_class=r['item_class'],
                        fiscal_treatment=r['fiscal_treatment'],
                        category=r['category'],
                    )
                except DatabaseError as e:
                    errors += 1

        print(f'OK ({len(results)} classified)')
        time.sleep(0.5)  # Rate limiting

    print(f'\nKlasificirano: {classified}')
    print(f'Greške: {errors}')
    print('\nPo kategoriji:')
    for cat, count in stats.most_common():
        print(f'  {cat}: {count}')

    if dry_run:
        print('\n--- DRY RUN — baza NIJE promijenjena ---')

    # Spremi report
    with open('BORG0_HAIKU_REPORT.json', 'w') as f:
        json.dump({'classified': classified, 'errors': errors,
                   'stats': dict(stats), 'results': all_results}, f, indent=2)
    print('Report: BORG0_HAIKU_REPORT.json')

    return classified, errors


if __name__ == '__main__':
    dry = '--execute' not in sys.argv
    run(dry_run=dry)
