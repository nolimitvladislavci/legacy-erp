# CC Task — HITNO: Tim Chat view + URL (10 minuta)

## Što trebaš dodati

### 1. Dodaj na kraj core/views.py:
```python

@login_required
def tim_chat(request):
    from pos.models import ImprovementSuggestion
    user_messages = ImprovementSuggestion.objects.filter(
        author=request.user, module='tim_chat'
    ).order_by('-created_at')[:10] if not request.user.is_superuser else []
    return render(request, 'dashboards/tim_chat.html', {
        'user_messages': user_messages,
    })
```

### 2. Dodaj URL u core/urls.py — iza superadmin/ivan/ linije:
```python
path('tim-chat/', views.tim_chat, name='tim_chat'),
```

### 3. Dodaj sidebar link u base.html — dostupan SVIM prijavljenima
Pronađi blok koji je vidljiv svim korisnicima (ne samo superadminu).
Npr. iza FAQ ili Kontakt linka, dodaj:
```html
<a href="/tim-chat/" onclick="closeSidebar()">
  <i class="fas fa-comments"></i> <span>💬 Tim Chat</span>
</a>
```

### 4. Provjeri
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/tim-chat/
# Mora biti 302
```

## NAPOMENA
- ImprovementSuggestion model ima polje `module` (CharField) i `author` (FK User)
- Provjeri pravo ime polja: grep -n "module\|author" /var/www/fina-connect/pos/models.py | grep -A2 "class ImprovementSuggestion"
- Ako polje se zove drugačije — prilagodi view
