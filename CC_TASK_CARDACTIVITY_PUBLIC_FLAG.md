# CC_TASK_CARDACTIVITY_PUBLIC_FLAG.md
# Dodijeljen: CC Code
# Prioritet: KRITIČNO — sigurnosna rupa, mora biti DONE prije QR traceability
# Procjena: 1.5h
# Ref: MASTER_PLAN_2026.md → P0.2

## KONTEKST

CardActivity.note je slobodan tekst koji upisuju ljudi.
QR traceability (H2.2) povlačit će CardActivity zapise prema kupcu/javnosti.
Ako ne filtriramo, interne napomene idu van.

Primjer što NE SMIJE izaći:
  "Petar rekao da je ova šarža možda kontaminirana, ali šef rekao šalji"
  "Klijent kasni s plaćanjem, ne raditi za njega"
  "GPS kaže da je dostava bila u 3h ujutro, pitaj vozača"

## KORAK 1 — Migracija

```python
# OBAVEZNO: pročitaj stvarna polja PRIJE pisanja migracije
cat /var/www/fina-connect/borg_ops/models.py
```

Dodati na CardActivity model:
```python
is_public_facing   = models.BooleanField(default=False, db_index=True,
    verbose_name='Javno vidljivo',
    help_text='Ako True, ovaj zapis se prikazuje na javnom QR traceability linka.')
is_system_generated = models.BooleanField(default=True, db_index=True,
    verbose_name='Generirano od sustava',
    help_text='Ako False, zapis je ručno unio korisnik i ne smije biti javno vidljiv.')
```

Generirati migraciju:
```bash
cd /var/www/fina-connect && source venv/bin/activate
python manage.py makemigrations borg_ops --name cardactivity_public_flag
python manage.py migrate
```

## KORAK 2 — FSMMixin update

U borg_ops/mixins.py, metoda _log_transition():
```python
def _log_transition(self, old_status, new_status, user, note):
    try:
        from borg_ops.models import CardActivity
        from django.contrib.contenttypes.models import ContentType
        return CardActivity.objects.create(
            content_type=ContentType.objects.get_for_model(self),
            object_id=str(self.pk),
            action='status_change',
            old_value=old_status,
            new_value=new_status,
            note=note or '',
            user=user,
            is_system_generated=True,   # ← DODATI
            is_public_facing=False,     # ← DODATI (default False, eksplicitno)
        )
    except Exception as e:
        logger.error('CardActivity create failed: %s', e)
        return None
```

## KORAK 3 — Sterilne sistemske poruke koje SMIJU biti javne

Dodati helper metodu u FSMMixin:

```python
def _log_public_event(self, message, user=None):
    """
    Kreira CardActivity zapis koji JE javan.
    SAMO sustav smije zvati ovu metodu — NE korisnici direktno.
    Koristi za: "Berba završena", "QC: Prošao", "Pakiranje završeno"
    """
    try:
        from borg_ops.models import CardActivity
        from django.contrib.contenttypes.models import ContentType
        return CardActivity.objects.create(
            content_type=ContentType.objects.get_for_model(self),
            object_id=str(self.pk),
            action='public_milestone',
            old_value='',
            new_value=message,
            note='',
            user=user,
            is_system_generated=True,
            is_public_facing=True,  # ← Jedino ovdje True
        )
    except Exception as e:
        logger.error('Public CardActivity create failed: %s', e)
        return None
```

## KORAK 4 — QR API endpoint (stub, ne buildati još)

Kreirati SAMO placeholder view u borg_ops/views.py:

```python
from django.http import JsonResponse
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # cache 5 min
def public_trace_api(request, qr_token):
    """
    Javni API za QR traceability.
    ČITA SAMO: is_public_facing=True AND is_system_generated=True
    """
    from django.contrib.contenttypes.models import ContentType
    from .models import CardActivity
    
    # TODO H2.2: implementirati QR token lookup
    # Trenutno: samo potvrdi da filtar radi
    public_activities = CardActivity.objects.filter(
        is_public_facing=True,
        is_system_generated=True,
    ).count()
    
    return JsonResponse({
        'status': 'stub',
        'public_records': public_activities,
        'note': 'Full QR traceability implementira se u H2.2',
    })
```

Dodati URL u borg_ops/urls.py:
```python
path('trace/<str:qr_token>/', views.public_trace_api, name='public_trace'),
```

## KORAK 5 — Test

```python
# U simulate_borg.py dodati u _sim_borg_ops():
try:
    from borg_ops.models import CardActivity
    # Provjeri da je_public_facing polje postoji
    assert hasattr(CardActivity, 'is_public_facing'), "is_public_facing polje ne postoji!"
    assert hasattr(CardActivity, 'is_system_generated'), "is_system_generated polje ne postoji!"
    
    # Provjeri da nema starih zapisa označenih kao public (default=False)
    public_count = CardActivity.objects.filter(is_public_facing=True).count()
    r.success(f"CardActivity.is_public_facing: OK. Javnih zapisa: {public_count}")
    r.success(f"CardActivity.is_system_generated: OK")
except AssertionError as e:
    r.error(str(e))
except Exception as e:
    r.error("CardActivity sigurnosna provjera greška", e)
```

## VERIFIKACIJA

```bash
cd /var/www/fina-connect && source venv/bin/activate

# Test migracije
python manage.py shell -c "
from borg_ops.models import CardActivity
print('Fields:', [f.name for f in CardActivity._meta.fields])
print('is_public_facing default:', CardActivity._meta.get_field('is_public_facing').default)
print('is_system_generated default:', CardActivity._meta.get_field('is_system_generated').default)
print('OK: Sigurnosna zaštita implementirana')
"

# Simulate borg
python manage.py simulate_borg --modules borg_ops

# Commit
git add borg_ops/models.py borg_ops/mixins.py borg_ops/views.py borg_ops/urls.py borg_ops/migrations/
git commit -m "security(borg-ops): CardActivity.is_public_facing + is_system_generated — QR leak protection

Zaštita od curenja internih napomena na javni QR traceability endpoint.
Sve sistemske tranzicije: is_system_generated=True, is_public_facing=False (default).
Samo _log_public_event() smije postaviti is_public_facing=True.
Javni API čita SAMO is_public_facing=True AND is_system_generated=True."
git log --oneline -3
```

## AŽURIRAJ FENIX_STATUS.md

Dodati u "DEPLOYAN DANAS":
| CardActivity security | (hash) | is_public_facing + is_system_generated — QR leak protection |

---
# STATUS: READY_FOR_CC_CODE
# Sljedeći task: P0.3 simulate_borg URL fix (30 min)
