# CC Task — Provjera i audit okruglog stola

## Tvoj zadatak
Provjeri tim_chat modul i okrugli stol. Pronađi probleme.
Preporuči poboljšanja. Ovo je pravi test funkcionira li sustav.

## Korak 1 — Provjeri pristupna prava
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
from superadmin_ai.models import PendingAIAction

# Tko može pristupiti tim-chat?
print('=== Korisnici i prava ===')
for u in User.objects.filter(is_active=True).select_related('profile'):
    try:
        role = u.profile.role
        is_super = u.is_superuser
        print(f'{u.username:20} | superuser:{is_super} | role:{role}')
    except: pass

# Koliko PendingAIAction ima?
print('=== PendingAIAction ===')
print('Total:', PendingAIAction.objects.count())
print('Pending:', PendingAIAction.objects.filter(status=\"pending\").count())
for a in PendingAIAction.objects.order_by('-created_at')[:5]:
    print(f'  {a.created_at:%d.%m %H:%M} | {a.module} | {a.description[:50]}')
"
```

## Korak 2 — Testiraj submit-request endpoint
```bash
# Kao www-data korisnik (simulacija regularnog korisnika)
curl -s -X POST https://limit-connect.com/hr/superadmin/ai/api/submit-request/ \
  -H "Content-Type: application/json" \
  -H "Cookie: $(cat /tmp/test_cookie 2>/dev/null || echo '')" \
  -d '{"description": "TEST: CC provjerava okrugli stol", "module": "tim_chat", "priority": 1}'
# Očekivano: {"ok": true, "id": "..."}
```

## Korak 3 — Provjeri tim_chat view
```bash
grep -n "def tim_chat\|user_messages\|ImprovementSuggestion" \
  /var/www/fina-connect/core/views.py | head -10

# Provjeri model - koji fields postoje
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import ImprovementSuggestion
print([f.name for f in ImprovementSuggestion._meta.fields])
"
```

## Korak 4 — Provjeri cockpit okrugli stol
```bash
# Je li okrugli stol u cockpit templateu isti kao u tim_chat?
grep -c "seat-ivan\|seat-seki\|seat-marija" \
  /var/www/fina-connect/templates/dashboards/ivan_cockpit.html
grep -c "seat-ivan\|seat-seki\|seat-marija" \
  /var/www/fina-connect/templates/dashboards/tim_chat.html
```

## Korak 5 — Lista problema i preporuka

Nakon provjere, napiši u /var/www/fina-connect/OKRUGLI_STOL_AUDIT.md:

```markdown
# Okrugli Stol — Audit izvješće
Datum: [danas]

## Funkcionira
- [što radi]

## Problemi
- [što ne radi]

## Preporuke poboljšanja
- [prijedlozi]

## Prava pristupa
- [tko vidi što]
```

## NAPOMENA
Ovo je test funkcionira li sustav — koordinator (Sonnet) čita izvješće
i odlučuje što se popravlja. Ti samo provjeri i dokumentiraj.
