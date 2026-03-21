## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — HITNO: Tim Chat endpoint fix (10 minuta)

## Problem
`/superadmin/ai/api/submit-request/` ima `@user_passes_test(is_superadmin)`
Šeki nije superadmin → 302 redirect → fetch pada → "Greška slanja"

## Fix — 3 koraka

### Korak 1: Dodaj view u core/views.py
```python
@login_required
@require_POST
def tim_chat_send(request):
    """Javni endpoint za Tim Chat — dostupan svim prijavljenim korisnicima."""
    from django.http import JsonResponse
    import json as json_lib
    try:
        data = json_lib.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Poruka je prazna'}, status=400)
    
    module = data.get('module', 'tim_chat')
    priority = int(data.get('priority', 2))
    
    # Spremi kao ImprovementSuggestion (dostupno svim korisnicima)
    from pos.models import ImprovementSuggestion
    from core.company_utils import get_user_company
    company = get_user_company(request)
    
    suggestion = ImprovementSuggestion.objects.create(
        company=company,
        author=request.user,
        source='user',
        title=f'Tim Chat: {description[:50]}',
        description=description,
        category=module,
        priority=priority,
        status='new',
    )
    return JsonResponse({
        'ok': True,
        'id': str(suggestion.id),
        'message': 'Poruka primljena ✅'
    })
```

### Korak 2: Dodaj URL u core/urls.py
Iza `path('tim-chat/', ...)` linije dodaj:
```python
path('tim-chat/send/', views.tim_chat_send, name='tim_chat_send'),
```

### Korak 3: Ažuriraj tim_chat.html — zamijeni endpoint URL
```bash
sed -i "s|/superadmin/ai/api/submit-request/|/hr/tim-chat/send/|g" \
  /var/www/fina-connect/templates/dashboards/tim_chat.html

# Provjeri zamjenu
grep -n "tim-chat/send\|submit-request" \
  /var/www/fina-connect/templates/dashboards/tim_chat.html
```

### Korak 4: Provjeri ImprovementSuggestion polja
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import ImprovementSuggestion
print([f.name for f in ImprovementSuggestion._meta.fields])
# Provjeri postoje li: author, company, title, description, category, priority, status, source
"
```
Ako koji field ne postoji — prilagodi view.

### Korak 5: Test
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/tim-chat/send/
# Mora biti 302 (redirect na login — endpoint postoji)
```

## PRAVILA
- require_POST dodaj: `from django.views.decorators.http import require_POST`
- Ako require_POST već importiran — ne dodavaj duplikat
- Django check 0 issues
- Javi HTTP status /hr/tim-chat/send/
