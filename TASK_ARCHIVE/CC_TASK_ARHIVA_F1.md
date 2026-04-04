# CC_TASK_ARHIVA_F1 — Global Error Handler + arhiva_list.html
## Agent: Claude Code | Prioritet: P0 | Danas

**Čitaj:** ARHIVA_MASTER_PLAN.md  
**Preduvjet:** Ništa — počni odmah

---

## ZADATAK 1: Global Error Handler (30 minuta)

CC Code je već napravio handler u /tmp/. Deploy ga sada.

### 1a. Provjeri što je CC napravio

```bash
ls /tmp/global_error_handler.py /tmp/deploy_global_error_handler.sh
```

### 1b. Deploy

```bash
sudo bash /tmp/deploy_global_error_handler.sh
```

Ako /tmp fajlovi ne postoje, kreiraj middleware ručno:

**`core/graceful_error_middleware.py`:**
```python
"""
GracefulErrorMiddleware — Zero Friction error handling.

Umjesto golog 500 ekrana:
  → Toast poruka (Django messages)
  → Auto-redirect na referrer ili /
  → Async WhatsApp notifikacija timu
  → SystemAuditLog zapis

NE hvata: API pozivi (/api/*), AJAX, JSON Accept headersi
"""
import logging
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

logger = logging.getLogger('limit_connect.errors')

ERROR_CATEGORIES = {
    'OperationalError': ('database', 'Privremeni problem s bazom. Pokušajte za minutu.'),
    'ProgrammingError': ('database', 'Privremeni problem s bazom. Pokušajte za minutu.'),
    'PermissionDenied': ('permission', 'Nemate pristup ovom resursu.'),
    'Http404': ('not_found', 'Stranica nije pronađena.'),
    'TimeoutError': ('timeout', 'Zahtjev trajao predugo. Pokušajte ponovo.'),
    'ValidationError': ('validation', 'Podaci nisu ispravni. Provjerite unos.'),
}

def _is_api_or_ajax(request):
    if request.path.startswith('/api/'):
        return True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept and 'text/html' not in accept:
        return True
    return False

class GracefulErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Ne hvata API/AJAX/JSON — oni imaju svoje error handlere
        if _is_api_or_ajax(request):
            return None

        exc_name = type(exception).__name__
        category, user_msg = ERROR_CATEGORIES.get(exc_name, ('default', None))

        if user_msg is None:
            user_msg = 'Došlo je do greške. Tim je obaviješten i radi na tome.'

        # Log s traceback-om
        logger.error(
            'GracefulError [%s] %s %s: %s',
            category, request.method, request.path, exception,
            exc_info=True,
            extra={'user': getattr(request.user, 'username', 'anon')}
        )

        # Async notifikacija timu (ne blokira request)
        try:
            from documents.tasks import notify_error_to_team
            notify_error_to_team.delay(
                error_type=exc_name,
                path=request.path,
                user=getattr(request.user, 'username', 'anon'),
                message=str(exception)[:500],
            )
        except Exception:
            pass  # Notifikacija ne smije srušiti fallback

        # Toast + redirect
        try:
            messages.error(request, user_msg)
            referer = request.META.get('HTTP_REFERER', '/')
            # Izbjegni redirect loop
            if referer and request.path in referer:
                referer = '/'
            return HttpResponseRedirect(referer or '/')
        except Exception:
            return None  # Fallback na Django 500 handler
```

### 1c. Dodaj u MIDDLEWARE (core/settings.py)

Dodaj kao PRVI u listi:
```python
MIDDLEWARE = [
    'core.graceful_error_middleware.GracefulErrorMiddleware',  # ← OVDJE
    'django.middleware.security.SecurityMiddleware',
    ...
]
```

### 1d. notify_error_to_team Celery task

Dodaj u `documents/tasks.py` (ili `core/tasks.py`):
```python
@shared_task(bind=True, soft_time_limit=30, name='core.notify_error_to_team')
def notify_error_to_team(self, error_type, path, user, message):
    """Šalje WhatsApp notifikaciju timu kad se dogodi 500 greška."""
    from notifications.whatsapp import send_whatsapp
    
    phones = getattr(settings, 'ERROR_NOTIFY_PHONES', '').split(',')
    phones = [p.strip() for p in phones if p.strip()]
    
    if not phones:
        return
    
    text = (
        f"🔴 *GREŠKA* na limit-connect.com\n"
        f"Tip: `{error_type}`\n"
        f"URL: `{path}`\n"
        f"User: `{user}`\n"
        f"Poruka: {message[:200]}"
    )
    
    for phone in phones[:3]:  # max 3 broja
        try:
            send_whatsapp(phone, text)
        except Exception:
            pass
```

### 1e. Dodaj u .env

```
ERROR_NOTIFY_PHONES=+385981234567,+385921234567
```

Koristi Ivanove i Draganove brojeve.

### 1f. Kreiraj 500.html i 404.html

`templates/500.html`:
```html
<!DOCTYPE html>
<html lang="hr">
<head><meta charset="UTF-8"><title>Greška — LIMIT Connect</title>
<meta http-equiv="refresh" content="4;url=/">
<style>
body{font-family:'Segoe UI',sans-serif;background:#f8fafc;display:flex;align-items:center;
  justify-content:center;min-height:100vh;margin:0}
.box{text-align:center;max-width:400px;padding:40px;background:white;
  border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.icon{font-size:48px;margin-bottom:16px}
h1{color:#1e3a5f;font-size:1.4rem;margin-bottom:8px}
p{color:#64748b;font-size:.9rem;line-height:1.6}
.btn{display:inline-block;margin-top:20px;padding:10px 24px;
  background:#1e3a5f;color:white;border-radius:8px;text-decoration:none;font-weight:600}
.countdown{color:#94a3b8;font-size:.8rem;margin-top:12px}
</style>
</head>
<body>
<div class="box">
  <div class="icon">⚡</div>
  <h1>Greška u sustavu</h1>
  <p>Nešto nije prošlo kako treba. Tim je automatski obaviješten i radi na tome.</p>
  <a href="/" class="btn">← Početna</a>
  <div class="countdown">Automatski preusmjerenje za 4 sekunde...</div>
</div>
</body>
</html>
```

---

## ZADATAK 2: arhiva_list.html template (2 sata)

Ovo je Marija's glavni ekran. Mora biti: brz, pregledan, mobilno.

**Zahtjevi:**
- Tablica dokumenata (datum, partner, iznos, tip, status)
- Filteri na vrhu: datum od/do, tip, partner search, valuta
- Stats traka: ukupno dokumenata, ukupan iznos, s fiskalnim kodom, s fajlom
- Svaki red: klik → detalji (modal ili slide-out panel)
- Integrity hash indikator (zeleni shield ✓)
- Bookmark (zvjezdica)
- Download PDF/XML inline
- Paginacija (50 po stranici)
- Export CSV/ZIP button
- **Scan dugme** (istaknuto, gore desno): "📷 Skeniraj račune"

**Kritično za Mariju:** Stats traka s ukupnim iznosom odmah vidljiva.  
Konjik ima 8.287 dokumenata i 1.682.152€ — to mora biti prvo što vidi.

**Template putanja:** `documents/templates/documents/arhiva_list.html`

Iskoristi postojeći `base.html` i Bootstrap koji je već u sustavu.

---

## ZADATAK 3: scan_batch.html skeleton (30 minuta)

Samo skeleton koji Sonnet može popuniti:
- `documents/templates/documents/scan_batch.html`
- Extends base.html
- Ima: `<div id="scan-app">` placeholder
- Ima: Django context varijable (`batch`, `images`)
- Ima: CSRF token i URLs za JS

---

## DONE kriterij

```bash
# Error middleware aktivan
curl -sI https://limit-connect.com/hr/documents/arhiva/ | grep "200 OK"

# Templates postoje
ls documents/templates/documents/arhiva_list.html
ls documents/templates/documents/scan_batch.html
ls templates/500.html

# Marija se može prijaviti i vidjeti arhivu
```

Ažuriraj FENIX_STATUS.md.
