# CC_TASK_3KLIK_REGISTRACIJA — Registracija bez frikcije
# Agent: CC Code  
# Prioritet: KRITIČAN — svaki dodatni klik gubi 30% korisnika
# Datum: 2026-03-25

---

## Cilj
Predsjednik DVD-a registrira firmu za < 3 minute, bez IT znanja.
Rezultat: ima pristup POS-u i putnim nalozima. Kartica nije potrebna.

## Trenutno stanje
- Registration step1-4 flow ✅ postoji i radi
- ServiceAgreement model ✅ postoji
- Trial period ✅ postoji (15 dana)
- Problem: step3 traži previše podataka odjednom, nema AI auto-fill

## Novi flow — 3 koraka

### Korak 1: Tko si? (30 sekundi)
```
Email + lozinka + profil (6 radio gumba, isti kao Joker Pricing)
→ Na temelju profila: pre-selecta pravi plan
→ [Nastavi →]
```

### Korak 2: Firma (60 sekundi)
```
OIB (11 znamenki) → AI auto-fill:
  - Ime firme (iz FINA registra)
  - Adresa
  - NKD kod (auto-detect)
  - PDV status
→ Korisnik samo provjeri i potvrdi
→ [Nastavi →]
```

OIB auto-fill endpoint (već postoji u `core/business_lookup.py`):
```python
# Provjeri postoji li:
from core.business_lookup import lookup_company_by_oib
# Ako radi — koristi ga u AJAX pozivu na /api/oib-lookup/?oib=12345678901
```

### Korak 3: Uvjeti + Start (30 sekundi)
```
Checkbox: "Prihvaćam uvjete korištenja" (link na PDF)
Checkbox: "Razumijem da su podaci zaštićeni (GDPR)"
→ [Pokreni besplatno →]
```

Redirect → onboarding dashboard s porukom:
"Dobrodošao/la! Imaš 15 dana svega. POS je aktivan odmah."

## ServiceProvider seed za Konjik d.o.o.

```python
# management command ili fixture:
from registration.models import ServiceProvider, ServiceAgreement
sp, _ = ServiceProvider.objects.get_or_create(
    name='Konjik d.o.o.',
    defaults={
        'oib': '...oib marije...',
        'is_default': True,
        'agreement_pdf': 'agreements/tc_v1.pdf',
    }
)
```

## OIB AJAX endpoint (ako ne postoji, napravi)

```python
# core/views.py ili companies/views.py
@require_GET
def oib_lookup(request):
    oib = request.GET.get('oib', '').strip()
    if len(oib) != 11 or not oib.isdigit():
        return JsonResponse({'error': 'OIB mora imati 11 znamenki'}, status=400)
    
    from core.business_lookup import lookup_company_by_oib
    try:
        data = lookup_company_by_oib(oib)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

URL: `path('api/oib-lookup/', views.oib_lookup, name='oib_lookup')`

## Definition of Done
- [ ] 3-koračni flow radi end-to-end
- [ ] OIB auto-fill radi (ili graceful fallback ako FINA ne odgovori)
- [ ] ServiceProvider seed za Konjik d.o.o. kreiran
- [ ] Trial 15 dana aktiviran automatski
- [ ] Redirect na dashboard s onboarding porukom
- [ ] Mobile first (375px test)
- [ ] Commit: `feat: 3-klik registracija — OIB auto-fill, ServiceProvider seed, trial`
