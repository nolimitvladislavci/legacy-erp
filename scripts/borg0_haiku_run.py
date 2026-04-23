#!/usr/bin/env python3
"""BORG-0 Haiku batch: classify remaining 'other' items."""
import json
import os
import time

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from dotenv import load_dotenv

load_dotenv('/var/www/fina-connect/.env')

from collections import Counter

import anthropic

from inventory.models import InventoryItem

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

VALID_CLASSES = {'tangible', 'service', 'intangible', 'asset', 'financial'}
VALID_FISCAL = {'standard', 'service_cash', 'exempt_pdv', 'no_fiscal', 'currency', 'pfand'}
VALID_CATS = {'material', 'tool', 'equipment', 'consumable', 'product', 'service',
              'food', 'drink', 'dessert', 'special', 'other'}

others = list(InventoryItem.objects.filter(
    category='other', item_class='tangible', fiscal_treatment='standard'
).values('id', 'name'))
total = len(others)
print(f'Total: {total}', flush=True)

stats = Counter()
classified = 0
errors = 0
batch_size = 50
all_results = []

for i in range(0, total, batch_size):
    batch = others[i:i+batch_size]
    bnum = i // batch_size + 1
    btotal = (total + batch_size - 1) // batch_size

    items_json = json.dumps(
        [{'id': it['id'], 'name': it['name']} for it in batch],
        ensure_ascii=False
    )

    prompt = (
        'Classify items. Return ONLY a JSON array, no text. '
        'Each: {id, item_class (tangible/service/asset), '
        'fiscal_treatment (standard/service_cash/exempt_pdv/no_fiscal), '
        'category (material/tool/equipment/product/service/food/drink/other)}. '
        'Rules: goods=tangible+standard, services=service+service_cash, '
        'vehicles=asset+no_fiscal+equipment, agrochemicals=material, '
        'eyewear=product, membership=exempt_pdv.\n'
        'Items: ' + items_json
    )

    try:
        resp = client.messages.create(
            model='claude-3-5-haiku-20241022',
            max_tokens=4000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = resp.content[0].text.strip()
        # Extract JSON
        if not raw.startswith('['):
            # Try to find JSON array
            start = raw.find('[')
            end = raw.rfind(']')
            if start >= 0 and end > start:
                raw = raw[start:end+1]

        results = json.loads(raw)
        rmap = {r['id']: r for r in results}

        for it in batch:
            r = rmap.get(it['id'])
            if not r:
                errors += 1
                continue
            ic = r.get('item_class', 'tangible')
            ft = r.get('fiscal_treatment', 'standard')
            cat = r.get('category', 'other')
            if ic not in VALID_CLASSES: ic = 'tangible'
            if ft not in VALID_FISCAL: ft = 'standard'
            if cat not in VALID_CATS: cat = 'other'

            InventoryItem.objects.filter(pk=it['id']).update(
                item_class=ic, fiscal_treatment=ft, category=cat
            )
            classified += 1
            stats[cat] += 1
            all_results.append({'id': it['id'], 'name': it['name'],
                                'item_class': ic, 'fiscal_treatment': ft, 'category': cat})

        print(f'  Batch {bnum}/{btotal}: {len(results)} OK', flush=True)
    except Exception as e:
        print(f'  Batch {bnum}/{btotal}: ERROR {e}', flush=True)
        errors += len(batch)

    time.sleep(0.3)

print(f'\nDone: {classified} classified, {errors} errors', flush=True)
for cat, c in stats.most_common():
    print(f'  {cat}: {c}', flush=True)

# Save report
with open('BORG0_HAIKU_REPORT.json', 'w') as f:
    json.dump({'classified': classified, 'errors': errors,
               'stats': dict(stats), 'results': all_results}, f, indent=2, ensure_ascii=False)
print('Report saved: BORG0_HAIKU_REPORT.json', flush=True)
