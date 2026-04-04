# BORG-0 TASK: AI Klasifikacija "Other" artikala
## Agent: Haiku (brzo, jeftino) | Prioritet: KRITIČAN — MORA biti prije W1A
## Datum: 2026-03-27 | Naređuje: Sonnet

---

## ZAŠTO OVO MORA BITI PRVO

11.057 od 12.259 artikala (90.2%) su u kategoriji "other".
Price Engine, fiscal_treatment, PDV logika — SVE je beskorisno bez čiste baze.
Ako pustimo W1A bez čišćenja, sustav će krivo obračunati porez na 90% artikala.

Gemini analiza (2026-03-27): "Sustav će se pri svakom pokušaju prodaje
srušiti ili će krivo obračunati porez jer neće znati je li taj 'Other'
artikl zapravo usluga, imovina ili roba."

---

## ZADATAK

Proći kroz svih 11.057 "other" artikala, poslati naziv Haiku-u,
dobiti klasifikaciju, i ažurirati bazu.

**NE mijenjamo:** category polje (staro)
**DODAJEMO:** item_class + fiscal_treatment (nova polja iz W1A)

Ali W1A JOŠ NIJE NAPRAVLJEN — zato koristimo privremenu tablicu.

---

## IMPLEMENTACIJA

### Korak 1: Provjeri može li se odmah pokrenuti

```bash
# Provjeri koja nova polja postoje
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.models import InventoryItem
fields = [f.name for f in InventoryItem._meta.concrete_fields]
print('item_class postoji:', 'item_class' in fields)
print('fiscal_treatment postoji:', 'fiscal_treatment' in fields)
"
```

**Ako W1A JOŠ NIJE NAPRAVLJEN** (item_class ne postoji):
→ Spremi klasifikacije u JSON fajl, primijeni kad W1A dođe.

**Ako W1A JE NAPRAVLJEN** (item_class postoji):
→ Direktno ažuriraj bazu.

### Korak 2: Klasifikacijska logika

```python
#!/usr/bin/env python3
"""
scripts/borg0_classify_items.py
Haiku AI klasifikacija svih 'other' artikala.

Pokretanje:
  venv/bin/python scripts/borg0_classify_items.py --dry-run
  venv/bin/python scripts/borg0_classify_items.py --execute --batch-size=100
"""
import django, os, sys, json, time
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import anthropic
from inventory.models import InventoryItem
from django.db import transaction

client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

# ─── KLASIFIKACIJSKA MAPA ────────────────────────────────────────────
# Format: keyword_lista → (item_class, fiscal_treatment, suggested_category)
KEYWORD_RULES = [
    # Usluge — po ključnim riječima u nazivu
    (['uslug', 'servis', 'montaž', 'instalac', 'popravak', 'remont', 'adaptac',
      'naknada', 'provizij', 'konzultac', 'savjet', 'prijevoz', 'transport',
      'dostava', 'najam', 'zakup', 'service', 'labour', 'work', 'rad'],
     'service', 'service_cash', 'service'),

    # Hrana/piće
    (['kruh', 'peciv', 'kolač', 'torta', 'pizza', 'meso', 'riba', 'voće',
      'povrće', 'mlijeko', 'sir', 'jaje', 'ulje', 'brašno', 'šećer', 'kava',
      'čaj', 'sok', 'pivo', 'vino', 'žestok', 'brot', 'fleisch', 'bier'],
     'tangible', 'standard', 'food'),

    # Građevinski materijal
    (['beton', 'cement', 'cigla', 'blok', 'ploča', 'šljunak', 'pijesak',
      'kamen', 'gravel', 'sand', 'armatur', 'čelik', 'željez', 'čavl',
      'vijak', 'matica', 'profil', 'cijev', 'lim', 'drvo', 'peleta',
      'drva', 'piljevina', 'daska', 'greda', 'foli', 'izolac'],
     'tangible', 'standard', 'material'),

    # Alati / oprema
    (['alat', 'bušilica', 'brusilica', 'pila', 'čekić', 'odvijač',
      'kliješta', 'ključ', 'stroj', 'pumpa', 'motor', 'kompresor',
      'agregat', 'generator', 'werkzeug', 'maschine', 'gerät'],
     'tangible', 'standard', 'tool'),

    # Elektronika / IT
    (['računalo', 'laptop', 'tablet', 'mobitel', 'printer', 'monitor',
      'tipkovnica', 'miš', 'kabel', 'punjač', 'adapter', 'router',
      'switch', 'server', 'hard disk', 'ssd', 'ram', 'procesor',
      'computer', 'phone', 'software', 'licenc'],
     'tangible', 'standard', 'equipment'),

    # Uredski materijal
    (['papir', 'uredski', 'olovka', 'rokovnik', 'fascikl', 'registrat',
      'tonер', 'tinta', 'briefpapier', 'büro'],
     'tangible', 'standard', 'consumable'),

    # Vozila / imovina
    (['vozilo', 'auto', 'kamion', 'kombi', 'traktor', 'prikolica',
      'excavator', 'bager', 'dizalica', 'utovarivač', 'fahrzeug'],
     'asset', 'no_fiscal', 'asset_vehicle'),

    # Životinje / stočarstvo
    (['krava', 'svinja', 'junad', 'ovca', 'perad', 'riba_uzgoj',
      'rind', 'schwein', 'schaf'],
     'tangible', 'standard', 'livestock'),

    # Ambalaža / Pfand
    (['ambalaža', 'povratna', 'boca', 'palete', 'kontejner', 'pfand',
      'depot', 'leergut'],
     'tangible', 'pfand', 'other'),
]

def rule_based_classify(name: str) -> tuple:
    """Brza klasifikacija po ključnim riječima — bez AI, besplatno."""
    name_lower = name.lower()
    for keywords, item_class, fiscal, category in KEYWORD_RULES:
        if any(kw in name_lower for kw in keywords):
            return item_class, fiscal, category, 'rule_based', 95.0
    return None, None, None, 'unknown', 0.0


def ai_classify_batch(items: list) -> list:
    """
    Haiku klasifikacija za batch artikala.
    Šalje max 50 artikala odjednom — efikasno.
    """
    if not items:
        return []

    items_json = json.dumps([
        {'id': i['id'], 'name': i['name'], 'price': str(i['unit_price'])}
        for i in items
    ], ensure_ascii=False)

    prompt = f"""Klasificiraj poslovne artikle u JSON formatu.

Za svaki artikl vrati:
- id: isti kao ulaz
- item_class: "tangible" | "service" | "intangible" | "asset" | "financial"
- fiscal_treatment: "standard" | "service_cash" | "exempt_pdv" | "no_fiscal" | "pfand"
- category: "food" | "drink" | "material" | "tool" | "equipment" | "service" | "asset_fixed" | "consumable" | "product" | "other"
- confidence: 0-100

Pravila:
- Usluge (servis, montaža, prijevoz, konzultacije) → service + service_cash
- Hrana/piće → tangible + standard + food/drink
- Materijali, alati, oprema, roba → tangible + standard + odgovarajuća cat.
- Osnovna sredstva (vozila, strojevi > 3500 EUR) → asset + no_fiscal
- Softver, licence → intangible + no_fiscal
- Ako nisi siguran → tangible + standard + confidence < 70

Vrati SAMO JSON array, bez ikakvog teksta.

Artikli:
{items_json}"""

    try:
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=4000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        return json.loads(raw)
    except Exception as e:
        print(f'  ⚠️ AI batch failed: {e}')
        return []


def classify_all_others(dry_run=True, batch_size=50, max_items=None):
    """
    Glavni runner klasifikacije.
    dry_run=True → samo prikaži, ne mijenjaj bazu.
    """
    others = InventoryItem.objects.filter(category='other')
    if max_items:
        others = others[:max_items]

    total = others.count()
    print(f'Artikala za klasifikaciju: {total}')
    print(f'Batch size: {batch_size} | Dry run: {dry_run}')
    print()

    stats = {'rule': 0, 'ai': 0, 'unknown': 0, 'errors': 0}
    results = []

    # ── Prolaz 1: Klasifikacija po pravilima (besplatno) ──────────
    for_ai = []
    for item in others.values('id', 'name', 'unit_price', 'company_id'):
        item_class, fiscal, category, method, conf = rule_based_classify(item['name'])
        if item_class:
            results.append({
                'id': item['id'],
                'item_class': item_class,
                'fiscal_treatment': fiscal,
                'category': category,
                'method': method,
                'confidence': conf,
            })
            stats['rule'] += 1
        else:
            for_ai.append(item)

    print(f'Klasificirano pravilima: {stats["rule"]}')
    print(f'Ostaje za AI: {len(for_ai)}')

    # ── Prolaz 2: AI za sve što pravila nisu uhvatila ─────────────
    for i in range(0, len(for_ai), batch_size):
        batch = for_ai[i:i + batch_size]
        print(f'  AI batch {i//batch_size + 1} ({len(batch)} artikala)...', end=' ')

        ai_results = ai_classify_batch(batch)
        if ai_results:
            results.extend(ai_results)
            stats['ai'] += len(ai_results)
            print(f'✅ {len(ai_results)} klasificirano')
        else:
            # Fallback: tangible/standard za sve neprepoznate
            for item in batch:
                results.append({
                    'id': item['id'],
                    'item_class': 'tangible',
                    'fiscal_treatment': 'standard',
                    'category': 'other',
                    'method': 'fallback',
                    'confidence': 40.0,
                })
            stats['unknown'] += len(batch)
            print(f'⚠️ fallback na tangible/standard')

        time.sleep(0.3)  # Rate limiting

    # ── Spremi JSON izvještaj ──────────────────────────────────────
    report_path = Path('BORG0_CLASSIFICATION_REPORT.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total': total,
            'stats': stats,
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    print(f'\nReport spreman: {report_path} ({len(results)} zapisa)')

    # ── Ažuriraj bazu (ako nije dry_run) ─────────────────────────
    if not dry_run:
        # Provjeri postoje li nova polja
        item_fields = [f.name for f in InventoryItem._meta.concrete_fields]
        has_item_class = 'item_class' in item_fields
        has_fiscal = 'fiscal_treatment' in item_fields

        if not has_item_class:
            print('\n⚠️ W1A migracija nije napravljena!')
            print('Klasifikacije su spremljene u BORG0_CLASSIFICATION_REPORT.json')
            print('Primijeni ih nakon W1A migracije s apply_borg0_results.py')
            return stats

        updated = 0
        low_confidence = 0

        with transaction.atomic():
            for result in results:
                if result.get('confidence', 0) < 50:
                    low_confidence += 1
                    continue  # Ne diramo niskopouzdane

                update_fields = {}
                if has_item_class and result.get('item_class'):
                    update_fields['item_class'] = result['item_class']
                if has_fiscal and result.get('fiscal_treatment'):
                    update_fields['fiscal_treatment'] = result['fiscal_treatment']

                if update_fields:
                    InventoryItem.objects.filter(pk=result['id']).update(**update_fields)
                    updated += 1

        print(f'\n✅ Ažurirano: {updated} artikala')
        print(f'⚠️ Preskočeno (niska pouzdanost): {low_confidence}')
        print(f'📋 Ručna provjera potrebna za niskopouzdane!')

    return stats


# ── Aplikacija BORG-0 rezultata (nakon W1A migracije) ─────────────
def apply_borg0_results(report_path='BORG0_CLASSIFICATION_REPORT.json'):
    """
    Primijeni prethodno spremljeni BORG-0 report na bazu.
    Poziva se NAKON W1A migracije kada nova polja postoje.
    """
    with open(report_path) as f:
        data = json.load(f)

    item_fields = [f.name for f in InventoryItem._meta.concrete_fields]
    if 'item_class' not in item_fields:
        print('❌ W1A migracija još nije napravljena!')
        return

    updated = low_conf = 0
    with transaction.atomic():
        for result in data['results']:
            if result.get('confidence', 0) < 50:
                low_conf += 1
                continue
            InventoryItem.objects.filter(pk=result['id']).update(
                item_class=result.get('item_class', 'tangible'),
                fiscal_treatment=result.get('fiscal_treatment', 'standard'),
            )
            updated += 1

    print(f'✅ Primijenjeno {updated} klasifikacija (preskočeno {low_conf} niskopouzdanih)')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--apply-report', action='store_true')
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--max-items', type=int, default=None)
    args = parser.parse_args()

    if args.apply_report:
        apply_borg0_results()
    else:
        dry = not args.execute
        classify_all_others(
            dry_run=dry,
            batch_size=args.batch_size,
            max_items=args.max_items,
        )
```

---

## POKRETANJE

### Korak 1 — DRY RUN (nikad ne mijenja bazu)
```bash
cd /var/www/fina-connect
venv/bin/python scripts/borg0_classify_items.py --dry-run --max-items=200
# Provjeri BORG0_CLASSIFICATION_REPORT.json
cat BORG0_CLASSIFICATION_REPORT.json | python3 -c "
import json,sys
data = json.load(sys.stdin)
from collections import Counter
c = Counter(r['item_class'] for r in data['results'])
print('Klase:', dict(c))
c2 = Counter(r['method'] for r in data['results'])
print('Metode:', dict(c2))
"
```

### Korak 2 — EXECUTE (samo nakon W1A migracije)
```bash
venv/bin/python scripts/borg0_classify_items.py --execute --batch-size=50
```

### Korak 3 — Ako W1A nije gotova, primijeni report kasnije
```bash
# Nakon W1A migracije:
venv/bin/python scripts/borg0_classify_items.py --apply-report
```

---

## DONE KRITERIJ

```bash
# 1. Report generiran
ls -la BORG0_CLASSIFICATION_REPORT.json

# 2. Distribucija klasa — ne smije biti > 20% "tangible/fallback"
cat BORG0_CLASSIFICATION_REPORT.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
from collections import Counter
print(Counter(r['item_class'] for r in d['results']))
print(Counter(r['method'] for r in d['results']))
"

# 3. Nema 'other' artikala s NULL item_class (ako je W1A gotova)
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from inventory.models import InventoryItem
null_class = InventoryItem.objects.filter(item_class='').count()
print('Bez item_class:', null_class, '(cilj: 0)')
"
```

---

## NAPOMENE

1. Haiku je jeftin (~$0.25 na 1000 artikala) — isplati se za čišćenje baze
2. Rule-based klasifikacija je besplatna i pokriva ~60-70% slučajeva
3. Confidence < 50% → NIKAD ne ažurirati automatski, ostaviti za ručni pregled
4. Artlike s low confidence → export u Excel za Mariju (ručna provjera)
5. 12.259 artikala / 50 po batchu = ~245 API poziva = ~5 min
6. UVIJEK pokrenuti dry-run prvo i pregledati report
