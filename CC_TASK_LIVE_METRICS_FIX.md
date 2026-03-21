## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — HITNO: live_metrics endpoint proširenje (5 min)

## Problem
`/hr/superadmin/ai/api/live-metrics/` vraća samo 4 polja.
Ivan Cockpit čeka: `recent_actions`, `pending_actions`, `total_today`

## Fix u superadmin_ai/views.py

Nađi funkciju `live_metrics` i zamijeni return JsonResponse s:

```python
    from superadmin_ai.models import AICouncilVote
    today = timezone.now().date()
    
    # Recent actions (zadnjih 10)
    recent = AIActionLog.objects.select_related('company').order_by('-timestamp')[:10]
    recent_list = []
    for a in recent:
        recent_list.append({
            'status': a.outcome or 'unknown',
            'module': a.module or 'general',
            'description': (a.details or {}).get('description', a.action_type or '')[:60],
            'time': a.timestamp.strftime('%H:%M') if a.timestamp else '',
            'id': str(a.id),
        })
    
    # Pending actions (čekaju odobrenje)
    pending = PendingAIAction.objects.filter(status='pending').select_related('company').order_by('-created_at')[:5]
    pending_list = []
    for a in pending:
        pending_list.append({
            'id': str(a.id),
            'module': a.module or 'general',
            'description': a.description[:60] if a.description else '',
            'time': a.created_at.strftime('%H:%M') if a.created_at else '',
            'company': a.company.name if a.company else 'N/A',
        })
    
    total_today = AIActionLog.objects.filter(timestamp__date=today).count()
    
    return JsonResponse({
        'autonomous_today': AIActionLog.objects.filter(
            timestamp__date=today, access_level__gte=3, outcome='executed'
        ).count(),
        'pending_count': PendingAIAction.objects.filter(status='pending').count(),
        'blocked_today': AIActionLog.objects.filter(
            timestamp__date=today, outcome='blocked'
        ).count(),
        'council_votes': AICouncilVote.objects.filter(voted_at__date=today).count(),
        'total_today': total_today,
        'recent_actions': recent_list,
        'pending_actions': pending_list,
    })
```

## Provjera polja
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from superadmin_ai.models import AIActionLog, PendingAIAction
print('AIActionLog fields:', [f.name for f in AIActionLog._meta.fields])
print('PendingAIAction fields:', [f.name for f in PendingAIAction._meta.fields])
"
```
Prilagodi fieldove ako se zovu drugačije (npr. `timestamp` može biti `created_at`).

## Provjera
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl restart gunicorn-fina
```

## Javi
Output django check + potvrdu da je restart prošao.
