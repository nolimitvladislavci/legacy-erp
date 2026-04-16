# CC TASK: evalidator.eu — MVP Deploy

**Prioritet:** HIGH  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Odobrio:** Sonnet (koordinator)  
**Domena:** evalidator.eu (registrirana, DNS još ne pointe na server)

---

## ARHITEKTURA (ne mijenjaj bez odobrenja)

```
evalidator.eu → nginx (novi config) → 127.0.0.1:8000 (isti gunicorn)
                                    → nova Django app: evalidator/
```

**NEMA:** Vue.js, blockchain, kripto, FastAPI, novi server, novi gunicorn.  
**IMA:** Django templates + HTMX + vanilla JS + core/oib_validator.py

---

## KORAK 1 — Pročitaj postojeći kod PRIJE pisanja

```bash
cat /var/www/fina-connect/core/oib_validator.py
cat /var/www/fina-connect/zeleni_otok/views.py | grep -A 40 "oib_validate"
cat /var/www/fina-connect/templates/zeleni_otok/tools/oib_lookup.html
cat /var/www/fina-connect/permissions/route_registry.py | head -60
cat /etc/nginx/sites-enabled/no-limit-world  # Uzmi kao template za nginx
```

Razumij što već postoji. eValidator WRAPA core/oib_validator.py — ne duplicira.

---

## KORAK 2 — Nova Django app

```bash
cd /var/www/fina-connect
. venv/bin/activate
python manage.py startapp evalidator
```

Dodaj u `settings.py` INSTALLED_APPS: `'evalidator'`

---

## KORAK 3 — Models (`evalidator/models.py`)

```python
from django.db import models

class ValidationLog(models.Model):
    """
    Anonimni log validacija — bez osobnih podataka.
    Čuvamo samo: tip, rezultat, timestamp, hash inputa.
    GDPR: NE čuvamo sirovi OIB/IBAN — samo SHA-256 hash.
    """
    VALIDATION_TYPES = [
        ('oib_hr', 'OIB (Hrvatska)'),
        ('vat_eu', 'VAT ID (EU)'),
        ('iban', 'IBAN'),
        ('mbs', 'MBS'),
        ('cross', 'Unakrsna provjera'),
        ('batch', 'Batch provjera'),
    ]
    
    validation_type = models.CharField(max_length=20, choices=VALIDATION_TYPES)
    input_hash = models.CharField(max_length=64)  # SHA-256, ne sirovi podatak
    is_valid = models.BooleanField()
    country_code = models.CharField(max_length=5, blank=True)
    
    # API usage
    is_api_call = models.BooleanField(default=False)
    api_key_hash = models.CharField(max_length=64, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    response_ms = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'evalidator_log'
        indexes = [
            models.Index(fields=['validation_type', 'created_at']),
            models.Index(fields=['is_api_call', 'created_at']),
        ]


class APIKey(models.Model):
    """API ključevi za enterprise korisnike."""
    
    PLAN_CHOICES = [
        ('free', 'Free (100/dan)'),
        ('starter', 'Starter (1,000/dan)'),
        ('pro', 'Pro (10,000/dan)'),
        ('enterprise', 'Enterprise (unlimited)'),
    ]
    
    name = models.CharField(max_length=200)
    email = models.EmailField()
    key_hash = models.CharField(max_length=64, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    
    daily_limit = models.IntegerField(default=100)
    daily_used = models.IntegerField(default=0)
    last_reset = models.DateField(auto_now_add=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'evalidator_apikey'
    
    def reset_if_new_day(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.last_reset < today:
            self.daily_used = 0
            self.last_reset = today
            self.save(update_fields=['daily_used', 'last_reset'])
    
    def can_use(self) -> bool:
        self.reset_if_new_day()
        return self.is_active and self.daily_used < self.daily_limit
```

Napravi migraciju.

---

## KORAK 4 — URL routing

### `evalidator/urls.py`
```python
from django.urls import path
from evalidator import views

app_name = 'evalidator'

urlpatterns = [
    # Landing
    path('', views.landing, name='home'),
    
    # Validacija (HTMX endpointi)
    path('validate/oib/', views.validate_oib, name='validate_oib'),
    path('validate/iban/', views.validate_iban, name='validate_iban'),
    path('validate/vat/', views.validate_vat, name='validate_vat'),
    path('validate/mbs/', views.validate_mbs, name='validate_mbs'),
    path('validate/cross/', views.validate_cross, name='validate_cross'),
    
    # Batch (faza 2 placeholder - vraća 501 za sada)
    path('api/v1/batch/', views.api_batch, name='api_batch'),
    
    # REST API (JSON)
    path('api/v1/oib/', views.api_oib, name='api_oib'),
    path('api/v1/iban/', views.api_iban, name='api_iban'),
    path('api/v1/vat/', views.api_vat, name='api_vat'),
    
    # Info stranice
    path('docs/', views.api_docs, name='api_docs'),
    path('about/', views.about, name='about'),
    path('pricing/', views.pricing, name='pricing'),
]
```

### U `config/urls.py` ili glavnom `urls.py` dodaj:
```python
# evalidator.eu routing — samo ako je hostname evalidator.eu
# Implementirano kroz middleware (vidi KORAK 5)
path('evalidator/', include('evalidator.urls', namespace='evalidator')),
```

---

## KORAK 5 — Hostname middleware

evalidator.eu i limit-connect.com dijele isti gunicorn.  
Trebamo middleware koji prepoznaje hostname i preusmjerava.

Kreiraj `evalidator/middleware.py`:
```python
class EValidatorHostMiddleware:
    """
    Ako request dolazi s evalidator.eu →
    preusmjeri na evalidator/ URL namespace.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        host = request.get_host().lower().split(':')[0]
        
        if host in ('evalidator.eu', 'www.evalidator.eu'):
            # Rewrite path: / → /evalidator/
            if not request.path.startswith('/evalidator/'):
                request.path = '/evalidator' + request.path
                request.path_info = request.path
        
        return self.get_response(request)
```

Dodaj u `settings.py` MIDDLEWARE (na vrh, ispred auth middlewarea):
```python
'evalidator.middleware.EValidatorHostMiddleware',
```

---

## KORAK 6 — Views (`evalidator/views.py`)

### Ključni principi:
- Wrapa `core/oib_validator.py` — ne duplicira logiku
- HTMX endpointi vraćaju HTML partial (ne JSON)
- API endpointi vraćaju JSON
- Svaka validacija logira u `ValidationLog` (hash, ne sirovi podatak)
- Rate limiting: 30 req/min bez API ključa, po APIKey limitu s ključem

```python
import hashlib
import json
import time
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from core.oib_validator import (
    validate_oib_hr, validate_iban, validate_hr_iban,
    validate_vat_id, validate_mbs, cross_validate_company
)
from evalidator.models import ValidationLog


def _log_validation(vtype, value, is_valid, is_api=False, ms=0):
    """Logiraj validaciju — bez sirovog podatka."""
    ValidationLog.objects.create(
        validation_type=vtype,
        input_hash=hashlib.sha256(value.encode()).hexdigest(),
        is_valid=is_valid,
        is_api_call=is_api,
        response_ms=ms,
    )


@require_GET
def landing(request):
    """Landing page evalidator.eu — "Dark Gold" tema."""
    # Statistike za landing (iz cache-a)
    from django.core.cache import cache
    stats = cache.get('evalidator_stats')
    if not stats:
        stats = {
            'total': ValidationLog.objects.count(),
            'today': ValidationLog.objects.filter(
                created_at__date=__import__('django.utils.timezone', 
                fromlist=['now']).now().date()
            ).count(),
        }
        cache.set('evalidator_stats', stats, 300)
    
    return render(request, 'evalidator/landing.html', {'stats': stats})


@require_POST
def validate_oib(request):
    """HTMX: Validacija OIB-a. Vraća HTML partial."""
    t0 = time.monotonic()
    oib = request.POST.get('oib', '').strip().replace(' ', '')
    
    result = {'oib': oib, 'valid': False, 'message': '', 'suggestion': ''}
    
    if len(oib) == 11 and oib.isdigit():
        if validate_oib_hr(oib):
            result['valid'] = True
            result['message'] = 'OIB je ispravan ✓'
        else:
            result['message'] = 'Kontrolna znamenka ne odgovara ISO 7064 MOD 11,10'
            # Predloži ispravak
            for i in range(10):
                candidate = oib[:10] + str(i)
                if validate_oib_hr(candidate):
                    result['suggestion'] = f'Mislio si možda na: {candidate}?'
                    break
    elif oib:
        result['message'] = f'OIB mora imati 11 znamenki (uneseno: {len(oib)})'
    
    ms = int((time.monotonic() - t0) * 1000)
    if oib:
        _log_validation('oib_hr', oib, result['valid'], ms=ms)
    
    return render(request, 'evalidator/partials/result.html', result)


@require_POST  
def validate_iban(request):
    """HTMX: IBAN validacija."""
    t0 = time.monotonic()
    iban = request.POST.get('iban', '').strip().replace(' ', '').upper()
    
    result = {'iban': iban, 'valid': False, 'message': ''}
    
    if iban:
        # Detektiraj zemlju
        country = iban[:2] if len(iban) >= 2 else 'HR'
        
        from core.oib_validator import validate_iban as _validate_iban
        if _validate_iban(iban):
            result['valid'] = True
            result['message'] = f'IBAN je ispravan ({country}) ✓'
        else:
            result['message'] = 'IBAN nije ispravan (MOD97 provjera nije prošla)'
            if len(iban) == 21 and iban.startswith('HR'):
                result['hint'] = 'HR IBAN mora imati točno 21 znak: HR + 2 kontrolne + 17 brojeva'
    
    ms = int((time.monotonic() - t0) * 1000)
    if iban:
        _log_validation('iban', iban, result['valid'], ms=ms)
    
    return render(request, 'evalidator/partials/result.html', result)


@require_POST
def validate_vat(request):
    """HTMX: VAT ID validacija za sve EU zemlje."""
    t0 = time.monotonic()
    vat = request.POST.get('vat', '').strip().upper()
    country = request.POST.get('country', '').strip().upper() or vat[:2]
    
    result = {'vat': vat, 'valid': False, 'message': '', 'country': country}
    
    if vat:
        if validate_vat_id(vat, country):
            result['valid'] = True
            result['message'] = f'VAT ID je ispravan ({country}) ✓'
        else:
            result['message'] = f'VAT ID nije ispravan za {country}'
    
    ms = int((time.monotonic() - t0) * 1000)
    if vat:
        _log_validation('vat_eu', vat, result['valid'], ms=ms)
    
    return render(request, 'evalidator/partials/result.html', result)


@csrf_exempt
def api_oib(request):
    """REST API: OIB validacija — JSON response."""
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Rate limit check
    if not _check_rate_limit(request):
        return JsonResponse({
            'error': 'Rate limit exceeded',
            'limit': '30 requests/minute (free tier)',
            'upgrade': 'https://evalidator.eu/pricing/'
        }, status=429)
    
    oib = (request.GET.get('oib') or 
           request.POST.get('oib') or 
           json.loads(request.body or '{}').get('oib', '')).strip()
    
    if not oib:
        return JsonResponse({'error': 'Missing oib parameter'}, status=400)
    
    is_valid = validate_oib_hr(oib)
    _log_validation('oib_hr', oib, is_valid, is_api=True)
    
    return JsonResponse({
        'oib': oib,
        'valid': is_valid,
        'algorithm': 'ISO 7064 MOD 11,10',
        'country': 'HR',
    })


def _check_rate_limit(request) -> bool:
    """Redis-based rate limiting: 30/min za anonimne."""
    from django.core.cache import cache
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f'evalidator_rate:{ip}'
    count = cache.get(key, 0)
    if count >= 30:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


def api_docs(request):
    return render(request, 'evalidator/docs.html')

def about(request):
    return render(request, 'evalidator/about.html')

def pricing(request):
    return render(request, 'evalidator/pricing.html')

@csrf_exempt
def api_batch(request):
    """Batch API — faza 2 placeholder."""
    return JsonResponse({
        'status': 'coming_soon',
        'message': 'Batch API dolazi u Q3 2026.',
        'notify': 'api@evalidator.eu'
    }, status=501)
```

---

## KORAK 7 — Templati

### `evalidator/templates/evalidator/landing.html`

**"Dark Gold" tema** — bez external CSS frameworka osim Tailwind koji je već u projektu.

Dizajn zahtjevi:
- Tamna pozadina (`#0a0a0a` ili `#111`)
- Zlatni akcenti (`#c9a84c` ili `#d4af37`)
- Monospace font za OIB/IBAN inpute
- Animirani loading indikator dok validacija teče
- Zeleni checkmark ✓ za ispravno, crveni ✗ za neispravno
- "Zlatni" za suggestion/hint

Struktura landing-a:
```
[Hero] "eValidator — Infrastruktura Povjerenja"
       "Besplatna provjera OIB, IBAN i VAT ID za cijelu EU"

[Validator tabs] OIB | IBAN | VAT ID | MBS | Unakrsna

[Forma s HTMX] Input → real-time provjera (hx-trigger="keyup changed delay:300ms")

[Result partial] Prikazuje se ispod forme

[Statistike] X validacija danas | Y ukupno | 27 EU zemalja

[API sekcija] Kratki opis + link na /docs/

[Footer] © No-limit udruga | evalidator.eu | GDPR
```

### `evalidator/templates/evalidator/partials/result.html`

HTMX partial koji se mijenja bez reload-a:
```html
{% if valid %}
<div class="result-valid">
    <span class="checkmark">✓</span>
    <span>{{ message }}</span>
</div>
{% else %}
<div class="result-invalid">
    <span class="cross">✗</span>
    <span>{{ message }}</span>
    {% if suggestion %}
    <div class="suggestion">💡 {{ suggestion }}</div>
    {% endif %}
</div>
{% endif %}
```

---

## KORAK 8 — RouteRegistry

U `permissions/route_registry.py` dodaj:
```python
'evalidator': AccessLevel.PUBLIC,
```

eValidator je **javni servis** — nema auth, nema CompanyMiddleware.

---

## KORAK 9 — Nginx config

Kreiraj `/etc/nginx/sites-available/evalidator`:
```nginx
server {
    listen 80;
    server_name evalidator.eu www.evalidator.eu;
    return 301 https://evalidator.eu$request_uri;
}

server {
    listen 443 ssl http2;
    server_name www.evalidator.eu;
    ssl_certificate     /etc/letsencrypt/live/evalidator.eu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/evalidator.eu/privkey.pem;
    return 301 https://evalidator.eu$request_uri;
}

server {
    listen 443 ssl http2;
    server_name evalidator.eu;
    
    ssl_certificate     /etc/letsencrypt/live/evalidator.eu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/evalidator.eu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    location /static/ {
        alias /var/www/fina-connect/staticfiles/;
        expires 30d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}
```

**Ne aktiviraj** nginx config — samo kreiraj fajl.  
**Ne pokreći** certbot — DNS mora prvo pokazivati na server.

---

## KORAK 10 — Testovi

`evalidator/tests.py`:
```python
# 1. Validni OIB prolazi
# 2. Nevalidni OIB vraća grešku + suggestion  
# 3. Validni HR IBAN prolazi
# 4. API endpoint vraća JSON
# 5. Rate limiter blokira nakon 30 req
# 6. ValidationLog se kreira (hash, ne sirovi OIB)
# 7. RouteRegistry dopušta anonimni pristup
# 8. Middleware preusmjerava evalidator.eu host
```

---

## IZVJEŠTAJ

`/var/www/fina-connect/CC_REPORT_EVALIDATOR.md`:
- Kreirani fajlovi (lista)
- Test rezultati (X/8)
- Nginx config status (kreiran, ne aktiviran)
- DNS instrukcije za Ivana (koje A record unijeti)
- Što je ostalo za Fazu 2 (batch API, F7-F9 odbačeni)

---

## ODBAČENE FUNKCIJE (obrazloženje za commit)

- **F7 (Web3/Kripto):** EU tržište 2026 ne traži blockchain za OIB. GDPR komplikacije. Nema jasnog kupca.
- **F8 (Kripto payment):** Nema paying korisnika još. Uvesti kad APIKey plan bude imao >100 korisnika.
- **F9 (Blockchain Ledger):** QSeal (TrustPro) je bolji, EU-legalan, odvjetnici ga razumiju. Blockchain nema pravnu težinu HR sudovi 2026.
- **Vue.js:** HTMX + vanilla JS je dovoljno za formu + rezultat. Nula novih dependencija.

---

## DEFINICIJA DONE
- [ ] `evalidator/` app kreirana i registrirana u settings
- [ ] 3 modela (ValidationLog, APIKey) + migracije
- [ ] 7 URL-ova funkcionalni
- [ ] Middleware za hostname routing radi
- [ ] HTMX validacija radi za OIB, IBAN, VAT
- [ ] REST API radi (GET/POST JSON)
- [ ] Rate limiter aktivan (30/min)
- [ ] RouteRegistry ažuriran
- [ ] Nginx config kreiran (NE aktiviran)
- [ ] 8/8 testova prolazi
- [ ] CC_REPORT_EVALIDATOR.md napisan s DNS instrukcijama

