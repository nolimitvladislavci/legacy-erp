# HAIKU TASK: Klasifikacija tipova udruga — AI auto-detect
## Agent: Claude Haiku 4.5 | Prioritet: SREDNJI | Datum: 2026-03-26

## MISIJA
Za svaku firmu s business_type='udruga' ili 'zadruga' — AI analizira naziv i automatski
predloži SEGMENT (dvd/kud/ribolov/pcelari/lov/branitelji/zadruga/opca).

## Pristup
```python
# Haiku Celery task — pokreni kao:
# from limit_connect_ai.tasks import haiku_classify_udruge_segments
# haiku_classify_udruge_segments.delay()

from companies.models import Company
from anthropic import Anthropic

client = Anthropic()

udruge = Company.objects.filter(
    business_type__in=['udruga','zadruga','ustanova']
).order_by('name')

results = []
for company in udruge:
    # Provjeri ima li vec segment
    if company.settings and company.settings.get('udruga_segment'):
        continue

    prompt = f"""Analiziraj naziv organizacije i klasificiraj segment.

Naziv: "{company.name}"

Segmenti (jedan odgovor):
- dvd = Dobrovoljno vatrogasno društvo
- kud = Kulturno-umjetničko društvo / tamburaši / folklorni ansambl
- ribolov = Ribolovno društvo / sportski ribolov
- lov = Lovačko društvo / lov divljači
- pcelari = Pčelarsko društvo
- branitelji = Udruga branitelja (HVIDRA, HDR, UHDDR, LD...)
- zadruga = Poljoprivredna zadruga / zadruga
- sport = Sportski klub (šport koji nije lov/ribolov)
- opca = Opća udruga (bez specifičnog segmenta)

Odgovori SAMO jednom riječju iz gornjeg popisa. Ništa drugo."""

    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=10,
        messages=[{'role':'user','content':prompt}]
    )
    segment = resp.content[0].text.strip().lower()
    
    # Validiraj
    valid = {'dvd','kud','ribolov','lov','pcelari','branitelji','zadruga','sport','opca'}
    if segment not in valid:
        segment = 'opca'
    
    # Spremi u company.settings
    settings = company.settings or {}
    settings['udruga_segment'] = segment
    settings['udruga_segment_ai_confidence'] = 'haiku_auto'
    company.settings = settings
    company.save(update_fields=['settings'])
    
    results.append({'company': company.name, 'segment': segment})

# Spremi report
import json
with open('/var/www/fina-connect/HAIKU_UDRUGE_SEGMENT_REPORT.md','w') as f:
    f.write("# Haiku — Auto-klasifikacija segmenata udruga\n\n")
    f.write(f"Klasificirano: {len(results)} udruga\n\n")
    f.write("| Naziv | Segment |\n|---|---|\n")
    for r in results:
        f.write(f"| {r['company']} | {r['segment']} |\n")
```

## Output
- `/var/www/fina-connect/HAIKU_UDRUGE_SEGMENT_REPORT.md`
- Company.settings['udruga_segment'] postavljen za sve udruge u sustavu
