# CC_TASK_PORTAL_BUGFIX_SPRINT.md
# Agent: CC Code | Prioritet: HITNO | Datum: 2026-03-25
# Sonnet sken sesija — 5 konkretnih fixeva, nema pretpostavljanja polja

---

## ✅ DONE — NE DIRAJ
- BUG-01: ai_hints.py direction='IN' → MessageDirection.INBOUND — POPRAVLJENO
- BUG-03: pos/signals.py item_name → description — VEĆ ISPRAVNO (koristi description__iregex)

---

## BUG-02 — pulse.py metadata__contains pada u testovima
**Fajl:** `pos/pulse.py` linija ~126
**Uzrok:** SQLite (test backend) ne podržava `metadata__contains` na JSONField
**Simptom:** `Pulse analyze failed: contains lookup is not supported on this database backend`

**Fix:**
```python
# Staro:
exists = company.pulse_events.filter(
    event_type='milestone_revenue',
    created_at__date=today,
    metadata__contains={'threshold': threshold},
).exists()

# Novo (radi na i PostgreSQL i SQLite):
exists = company.pulse_events.filter(
    event_type='milestone_revenue',
    created_at__date=today,
    metadata__threshold=threshold,
).exists()
```

---

## BUG-04 — website/views.py duplikat funkcije
**Fajl:** `website/views.py` — zadnje 2 linije fajla
**Problem:** `digitalni_posrednik` definirana DVAPUT. Django koristi samo drugu.
Prva definicija je tiho sakrivena — svi bugfixi na prvoj su nevidljivi.

**Fix:** Obriši prvu definiciju (linija ~490), ostavi samo zadnju.

---

## BUG-05 — SECURITY: Stari server IP u ALLOWED_HOSTS
**Fajl:** `core/settings.py` linija ~22
**Problem:** `'85.9.201.204'` — stari UpCloud server je ugašen i obrisan.
Ako netko drugi dobije tu IP adresu, može slati zahtjeve na produkciju bez ALLOWED_HOSTS blokade.

**Fix:** Ukloni `'85.9.201.204'` iz ALLOWED_HOSTS liste.

```python
# Staro:
ALLOWED_HOSTS = [
    "limit-connect.com", "www.limit-connect.com",
    "viskovic-group.de", "www.viskovic-group.de",
    "85.9.201.204",  # ← UKLONI OVO
    "37.27.248.86", ...
]
```

---

## BUG-06 — pricing_page ne koristi ?profile= parametar
**Fajl:** `website/views.py` — `pricing_page()` view
**Problem:** URL `/pricing/?profile=udruga` → view ignorira `profile` param, prikazuje SVE planove

**Fix:**
```python
def pricing_page(request):
    from registration.models import PricingPlan
    from registration.constants import PLAN_FEATURES, PROFILE_PLAN_MAP  # dodaj PROFILE_PLAN_MAP u constants

    plans = PricingPlan.objects.filter(is_active=True).order_by('sort_order')
    lang = request.GET.get('lang', 'hr')
    profile = request.GET.get('profile', '')

    # Filtriraj planove po profilu ako je naveden
    profile_plans = PROFILE_PLAN_MAP.get(profile, [])
    if profile_plans:
        plans = plans.filter(slug__in=profile_plans)

    return render(request, 'website/pricing.html', {
        'plans': plans,
        'plan_features': PLAN_FEATURES,
        'lang': lang,
        'active_profile': profile,
    })
```

**Dodaj u `registration/constants.py`:**
```python
PROFILE_PLAN_MAP = {
    'obrtnik':    ['pausalac'],
    'udruga':     ['udruga-starter'],
    'rental':     ['rental-starter'],
    'firma':      ['starter', 'professional', 'enterprise'],
    'racunovodja':['archive-ai', 'enterprise', 'distributor'],
    'gastro':     ['pos-starter', 'pos-archive', 'professional'],
}
```

---

## BUG-07 — pulse.py fiskalizacija fail streak — dvojni filter na jir
**Fajl:** `pos/pulse.py` linija ~155
**Problem:**
```python
fail_streak = POSReceipt.objects.filter(
    ...
    jir__isnull=True,
    jir='',          # ← OVO JE KONTRADIKCIJA: ne može biti NULL i '' istovremeno
    ...
)
```
Rezultat: `fail_streak` uvijek vraća 0, alarm se nikad ne trigera.

**Fix:**
```python
from django.db.models import Q
fail_streak = POSReceipt.objects.filter(
    session__terminal__company=company,
    status='paid',
    paid_at__date=today,
    is_training=False,
).filter(
    Q(jir__isnull=True) | Q(jir='')
).count()
```

---

## PROB-07 — public_pdf rate limiting
**Lokacija:** Pronađi view koji generira javni PDF (pretražiti: `public_pdf` ili `client_portal_pdf`)
**Problem:** Javni endpoint bez rate limitinga — WeasyPrint može biti zloupotrijebljen

**Fix:** Dodaj cache-based throttle:
```python
from django.core.cache import cache

def public_pdf(request, token):
    cache_key = f'pdf_gen:{token}'
    if cache.get(cache_key):
        return HttpResponse('Previše zahtjeva. Pokušajte za 60 sekundi.', status=429)
    cache.set(cache_key, True, 60)
    # ... ostatak view-a
```

---
## Commit message prijedlog:
`fix: BUG-02 pulse JSONField lookup, BUG-04 duplicate view, BUG-05 stale IP, BUG-06 pricing profile filter, BUG-07 jir Q filter`
