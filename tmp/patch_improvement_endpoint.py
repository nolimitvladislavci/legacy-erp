#!/usr/bin/env python3
"""
Patch: Dodaj system_improvement_api endpoint u cockpit_views.py
i registriraj URL u core/urls.py.
Također ažuriraj fenix-ui.js da koristi novi endpoint.
"""
import re

# ══════════════════════════════════════════════════════════════════
# 1. DODAJ ENDPOINT U cockpit_views.py
# ══════════════════════════════════════════════════════════════════
COCKPIT_PATH = '/var/www/fina-connect/core/cockpit_views.py'

NEW_ENDPOINT = '''

# ─── SYSTEM IMPROVEMENT API (bez login-a) ─────────────────────────────────────

@require_POST
def system_improvement_api(request):
    """
    Interni API za kreiranje ImprovementSuggestion s source='system'.
    Koristi se iz fenixNetworkError (JS auto-error-logging) i Celery taskova.
    Auth: X-System-Token header (HMAC od SECRET_KEY).
    Ako je korisnik ulogiran, koristi session auth kao fallback.
    """
    import hashlib
    from django.conf import settings

    # Auth: ulogiran korisnik ILI validan system token
    is_authenticated = request.user.is_authenticated if hasattr(request, 'user') else False
    system_token = request.META.get('HTTP_X_SYSTEM_TOKEN', '')
    expected_token = hashlib.sha256(
        ('fenix-system:' + settings.SECRET_KEY[:20]).encode()
    ).hexdigest()[:48]

    if not is_authenticated and system_token != expected_token:
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    title = (data.get('title') or '')[:200].strip()
    desc = (data.get('description') or '').strip()
    if not desc:
        return JsonResponse({'ok': False, 'error': 'description obavezan'}, status=400)
    if not title:
        title = 'System: ' + desc[:50]

    # Određivanje company
    company = None
    company_id = data.get('company_id', '')
    if company_id:
        from companies.models import Company
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
        company = Company.objects.filter(pk=company_id).first()
    elif is_authenticated:
        from core.company_utils import get_user_company
        company = get_user_company(request)

    if not company:
        # Fallback: prva aktivna kompanija (system-level log)
        from companies.models import Company
        company = Company.objects.first()
        if not company:
            return JsonResponse({'ok': False, 'error': 'Nema kompanije'}, status=400)

    from pos.models import ImprovementSuggestion
    source = data.get('source', 'system')
    if source not in ('system', 'anonymous'):
        source = 'system'

    s = ImprovementSuggestion.objects.create(
        company=company,
        author=request.user if is_authenticated else None,
        source=source,
        title=title,
        description=desc,
        category=(data.get('category') or 'auto')[:50],
        priority=min(max(int(data.get('priority', 3) or 3), 1), 5),
        status='new',
    )
    return JsonResponse({'ok': True, 'id': s.pk})
'''

with open(COCKPIT_PATH, 'r') as f:
    content = f.read()

# Dodaj prije partner_signup_api sekcije
content = content.replace(
    '# ─── PARTNER SIGNUP API',
    NEW_ENDPOINT + '\n# ─── PARTNER SIGNUP API'
)

with open(COCKPIT_PATH, 'w') as f:
    f.write(content)
print('[OK] cockpit_views.py — dodan system_improvement_api')

# ══════════════════════════════════════════════════════════════════
# 2. REGISTRIRAJ URL u core/urls.py
# ══════════════════════════════════════════════════════════════════
URLS_PATH = '/var/www/fina-connect/core/urls.py'

with open(URLS_PATH, 'r') as f:
    urls_content = f.read()

# Dodaj URL — u urlpatterns (izvan i18n jer je API)
URL_LINE = "    path('api/system/improvement/', __import__('core.cockpit_views', fromlist=['system_improvement_api']).system_improvement_api, name='system_improvement_api'),\n"

# Dodaj nakon health check linije
urls_content = urls_content.replace(
    "    path('health/', views.health_check, name='health_check'),",
    "    path('health/', views.health_check, name='health_check'),\n" + URL_LINE,
)

with open(URLS_PATH, 'w') as f:
    f.write(urls_content)
print('[OK] urls.py — registriran /api/system/improvement/')

# ══════════════════════════════════════════════════════════════════
# 3. AŽURIRAJ fenix-ui.js — fenixNetworkError da koristi novi endpoint
# ══════════════════════════════════════════════════════════════════
FENIX_UI_PATH = '/var/www/fina-connect/static/js/fenix-ui.js'

with open(FENIX_UI_PATH, 'r') as f:
    js_content = f.read()

# Zamijeni stari broken POST blok s novim
OLD_JS = """  // Auto-log greška u ImprovementSuggestion
  try {
    var payload = {
      title: 'Automatski log: ' + msg,
      description: 'URL: ' + window.location.href + '\\nError: ' + (err ? err.toString() : 'network') + '\\nUA: ' + navigator.userAgent,
      category: 'network',
      priority: 2,
      source: 'system'
    };
    var csrf = document.cookie.match(/csrftoken=([^;]+)/);
    if (csrf) {
      fetch('/pos/improvements/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf[1]},
        body: JSON.stringify(payload)
      }).catch(function(){});  // silent — ne prikazuj error od error handlera
    }
  } catch(e) {}"""

NEW_JS = """  // Auto-log greška u ImprovementSuggestion (system endpoint, bez login-a)
  try {
    var payload = {
      title: 'Automatski log: ' + msg,
      description: 'URL: ' + window.location.href + '\\nError: ' + (err ? err.toString() : 'network') + '\\nUA: ' + navigator.userAgent,
      category: 'network',
      priority: 2,
      source: 'system'
    };
    fetch('/api/system/improvement/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    }).catch(function(){});
  } catch(e) {}"""

js_content = js_content.replace(OLD_JS, NEW_JS)

with open(FENIX_UI_PATH, 'w') as f:
    f.write(js_content)
print('[OK] fenix-ui.js — fenixNetworkError koristi /api/system/improvement/')

print('\n✅ ImprovementSuggestion system endpoint spreman.')
print('   POST /api/system/improvement/')
print('   Auth: session (ulogiran) ILI X-System-Token header')
print('   Body: {title, description, category, priority, source, company_id}')
