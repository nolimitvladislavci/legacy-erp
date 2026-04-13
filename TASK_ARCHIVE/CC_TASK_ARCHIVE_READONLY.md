# CC_TASK: Archive Readonly Access — 11 godina zakonska obaveza
# Kreirao: Sonnet — 2026-04-10
# Prioritet: Visok — zakonska obaveza (ZOR čl. 10)
# Procjena: 2-3 sata

## PROBLEM
Kad firma otkaže pretplatu ili korisnik postane inactive:
- is_active=False → ne može ući u sustav
- valid_until prođe → nema pristupa podacima
- Zakon o računovodstvu zahtijeva pristup arhivi 11 GODINA

## RJEŠENJE: archive_readonly mode

### KORAK 1: Novi plan u PricingPlan
Kreiraj u Django shellu (jednom):
```python
from registration.models import PricingPlan
PricingPlan.objects.get_or_create(
    slug='archive_readonly',
    defaults={
        'name': 'Arhiva (read-only)',
        'price_monthly': 0,
        'max_users': 999,
        'included_modules': ['documents', 'konto', 'invoicing'],
        'is_active': True,
        'sort_order': 99,
    }
)
```

### KORAK 2: Celery task — auto-downgrade
U `registration/tasks.py`, dodaj:
```python
@shared_task
def downgrade_expired_subscriptions():
    """
    Svake noći u 01:00 — firme s isteklom pretplatom → archive_readonly.
    Korisnici OSTAJU aktivni, ali vide samo arhivu.
    """
    from registration.models import CompanySubscription, PricingPlan
    from django.utils import timezone
    
    archive_plan = PricingPlan.objects.get(slug='archive_readonly')
    today = timezone.now().date()
    
    expired = CompanySubscription.objects.filter(
        is_active=True,
        valid_until__lt=today,
        plan__in=['starter','professional','micro','enterprise'],
    ).exclude(plan='archive_readonly')
    
    for sub in expired:
        sub.plan = 'archive_readonly'
        sub.pricing_plan = archive_plan
        sub.save(update_fields=['plan', 'pricing_plan'])
        # Korisnici ostaju is_active=True — mogu se logirati
        # Ali RouteRegistry im daje samo /arhiva/ i /konto/pregled/
```

### KORAK 3: RouteRegistry — archive_readonly permissions
U `permissions/route_registry.py`, dodaj za archive_readonly plan:
- DOZVOLJENO: /dokumenti/arhiva/ (read), /konto/pregled/ (read), /izvjestaji/ (read)
- ZABRANJENO: sve ostalo (redirect na /arhiva-info/ s porukom)

### KORAK 4: Login poruka za archived korisnike
U `core/views.py`, u login_view, NAKON login():
```python
sub = user.profile.company.subscriptions.filter(plan='archive_readonly').first() if hasattr(user, 'profile') else None
if sub:
    messages.info(request, 'Vaša pretplata je istekla. Imate readonly pristup arhivi.')
    return redirect('/hr/dokumenti/arhiva/')
```

### KORAK 5: /arhiva-info/ stranica
Jednostavna stranica: "Vaša pretplata je istekla. Arhiva je dostupna do [datum]. Za obnovu kontaktirajte nas."

### KORAK 6: Celery Beat registracija
```python
'downgrade-expired-subs': {
    'task': 'registration.tasks.downgrade_expired_subscriptions',
    'schedule': crontab(hour=1, minute=0),
},
```

## NIJE U OVOM TASKU
- syn_ korisnici (Synesis import) → ostaju is_active=False, to je ispravno
- Kad admin želi aktivirati syn_ korisnika → ručno u admin panelu
- Budući fix: onboarding email syn_ korisnicima da postave lozinku

## VERIFIKACIJA
```bash
# Test: kreiraj test pretplatu s valid_until=jučer, pokreni task, provjeri plan
python manage.py shell -c "
from registration.tasks import downgrade_expired_subscriptions
downgrade_expired_subscriptions()
print('Done')
"
```
