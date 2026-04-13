# HAIKU_TASK_PUTNI_NALOG_CLASSIFIER — Auto-klasifikacija troškova
# Agent: Haiku (via Celery)
# Prioritet: SREDNJI — poboljšava UX, ne blokira launch
# Datum: 2026-03-25

---

## Zadatak

Kada korisnik upiše opis troška u TravelExpense.description,
Haiku automatski predlaže expense_type.

Primjeri:
- "INA benzinska Osijek" → `fuel`
- "Kotizacija smotre Đakovo" → `registration`
- "Restoran Slavonija večera" → `food`
- "Parkiranje Arena Zagreb" → `parking`
- "BusHrvatska karta Osijek-Zagreb" → `ticket`
- "Dozvola za ribolov Kopačko blato" → `licence`
- "Kostim za nastup KUD Dukat" → `costume`

---

## Implementacija

### Celery task: `worktime/tasks.py`

```python
@shared_task
def classify_travel_expense(expense_id: int) -> str:
    """
    Haiku klasificira tip troška na temelju opisa.
    Poziva se after_save signal na TravelExpense.
    """
    from .models import TravelExpense
    import anthropic
    
    expense = TravelExpense.objects.get(pk=expense_id)
    if expense.expense_type != 'other':
        return 'skipped'  # već klasificirano
    
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": (
                f"Klasificiraj ovaj trošak putnog naloga u jednu kategoriju.\n"
                f"Opis: '{expense.description}'\n"
                f"Kategorije: fuel, toll, parking, hotel, food, ticket, taxi, "
                f"registration, equipment, costume, licence, other\n"
                f"Odgovori SAMO jednom riječju — naziv kategorije."
            )
        }]
    )
    
    category = response.content[0].text.strip().lower()
    valid = [c[0] for c in TravelExpense.EXPENSE_TYPES]
    
    if category in valid and category != 'other':
        TravelExpense.objects.filter(pk=expense_id).update(
            expense_type=category,
            ai_classified=True  # dodaj ovo polje u model
        )
        return category
    return 'other'
```

### Signal: `worktime/signals.py` (kreiraj ako ne postoji)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TravelExpense

@receiver(post_save, sender=TravelExpense)
def auto_classify_expense(sender, instance, created, **kwargs):
    if created and instance.expense_type == 'other' and instance.description:
        from .tasks import classify_travel_expense
        classify_travel_expense.delay(instance.pk)
```

### Migracija — dodaj polje `ai_classified`

```python
# worktime/migrations/XXXX_add_ai_classified_to_travelexpense.py
ai_classified = models.BooleanField(default=False, help_text='Klasificirano AI-jem')
```

---

## UI feedback

Na detail stranici putnog naloga, uz svaki TravelExpense koji je ai_classified=True:
```html
<span class="badge bg-purple">🤖 AI</span>
```

Korisnik može kliknuti dropdown i ručno promijeniti ako Haiku pogriješi.

---

## Scope

- SAMO TravelExpense klasifikacija
- NE klasificira ostale modele u ovom tasku
- Ukupno: ~30 linija koda + signal + migracija

---

## Verifikacija

```bash
# Test:
venv/bin/python manage.py shell -c "
from worktime.tasks import classify_travel_expense
# Kreiraj test expense, provjeri klasifikaciju
"
```
