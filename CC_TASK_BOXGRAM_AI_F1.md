# CC_TASK_BOXGRAM_AI_F1.md
# Boxgram AI Faza 1 — Haiku auto-opisi
# Agent: CC Code | Prioritet: KRITIČNO | Datum: 05.04.2026.
# Čitaj: BOXGRAM_10_10_PLAN.md → TASK A

## KONTEKST
Svaki LifeEvent koji se kreira u Boxgramu mora automatski dobiti
AI-generiran opis na hrvatskom. Model: claude-haiku-4-5-20251001.
Ovo je razlika između suhoparne evidencije i žive priče.

## IMPLEMENTACIJA

### 1. Kreirati fajl:
/var/www/fina-connect/boxgram/services/ai_enrichment.py
→ Sadržaj: vidi BOXGRAM_10_10_PLAN.md sekcija A1

### 2. U boxgram/tasks.py dodati:
→ enrich_life_event_ai Celery task
→ Sadržaj: vidi BOXGRAM_10_10_PLAN.md sekcija A2

### 3. U boxgram/signals.py dodati:
→ auto_enrich_life_event signal (post_save na LifeEvent)
→ Sadržaj: vidi BOXGRAM_10_10_PLAN.md sekcija A3

### 4. Provjeri da ANTHROPIC_API_KEY postoji u .env:
```bash
grep ANTHROPIC_API_KEY /var/www/fina-connect/.env | head -1
```

### 5. Test:
```python
# venv/bin/python manage.py shell
from boxgram.models import PetProfile, LifeEvent
from boxgram.services.ai_enrichment import enrich_life_event
import datetime

# Uzmi prvi PetProfile
pet = PetProfile.objects.first()
if pet:
    event = LifeEvent(
        pet=pet,
        event_type='rodenje',
        title=f'{pet.name} je na svijetu!',
        date=datetime.date.today(),
    )
    result = enrich_life_event(event)
    print('AI OPIS:', result)
else:
    print('Nema PetProfile-a — kreiraj jedan prvo')
```

### 6. Integracijski test — full flow:
```python
# Kreiraj LifeEvent → signal → Celery task → AI opis
from boxgram.models import PetProfile, LifeEvent
import datetime, time

pet = PetProfile.objects.first()
event = LifeEvent.objects.create(
    pet=pet,
    event_type='milestone',
    title='Rudi je naučio sjediti!',
    date=datetime.date.today(),
    is_public=True,
)
print('Kreiran event, čekam AI (5 sek)...')
time.sleep(5)
event.refresh_from_db()
print('AI opis:', event.description[:100] if event.description else 'NEMA — provjeri Celery')
```

## DONE KRITERIJ
- [ ] ai_enrichment.py kreiran i testiran
- [ ] Celery task enrich_life_event_ai radi
- [ ] Signal auto_enrich_life_event registriran
- [ ] Full flow test: kreiraj event → AI opis se pojavi automatski
- [ ] Commit: "feat(boxgram): AI Faza 1 — Haiku auto-opisi za LifeEvent"
