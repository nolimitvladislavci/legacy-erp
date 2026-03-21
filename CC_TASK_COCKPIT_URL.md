## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — HITNO: Ivan Cockpit URL + View (5 minuta)

## Problem
Template postoji: `/var/www/fina-connect/templates/dashboards/ivan_cockpit.html`
Ali view i URL ne postoje → 404

## Zadatak — 2 stvari

### 1. Dodaj view na kraj core/views.py
```bash
cat >> /var/www/fina-connect/core/views.py << 'PYEOF'


@login_required
def ivan_cockpit(request):
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    import subprocess
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_start = today.replace(day=1)
    from django.contrib.auth.models import User
    from companies.models import Company
    from registration.models import CompanySubscription
    from pos.models import POSReceipt, POSSession, POSTerminal, ImprovementSuggestion
    from invoicing.models import Invoice
    from documents.models import ArhivaEntry
    from eracun.models import ERacun
    subs = list(CompanySubscription.objects.filter(is_active=True).select_related('company').order_by('-monthly_fee'))
    mrr = sum(float(s.monthly_fee or 0) for s in subs)
    pos_today_qs = POSReceipt.objects.filter(created_at__date=today, status='paid')
    pos_by_company = list(POSReceipt.objects.filter(created_at__date=today, status='paid').values('session__terminal__company__name').annotate(promet=Sum('total'), bonovi=Count('id')).order_by('-promet'))
    try:
        disk = subprocess.check_output(['df','-h','/'], text=True).split('\n')[1].split()
        disk_info = f"{disk[4]} ({disk[3]} slobodno)"
    except: disk_info = 'N/A'
    try:
        mem = subprocess.check_output(['free','-h'], text=True).split('\n')[1].split()
        mem_info = f"{mem[2]} / {mem[1]}"
    except: mem_info = 'N/A'
    try:
        logs_raw = subprocess.check_output(['tail','-30','/var/www/fina-connect/logs/django.log'], text=True).strip().split('\n')
        recent_logs = [l for l in logs_raw if any(k in l for k in ['ERROR','WARNING','INFO whatsapp'])][-8:]
    except: recent_logs = []
    context = {
        'now': now, 'today': today,
        'users_total': User.objects.count(),
        'users_active_week': User.objects.filter(last_login__gte=week_ago).count(),
        'users_never': User.objects.filter(last_login__isnull=True, is_active=True).count(),
        'companies': Company.objects.count(),
        'subs': subs, 'mrr': mrr,
        'pos_promet_danas': pos_today_qs.aggregate(t=Sum('total'))['t'] or 0,
        'pos_bonovi_danas': pos_today_qs.count(),
        'pos_open_sessions': POSSession.objects.filter(status='open').count(),
        'pos_terminal_count': POSTerminal.objects.filter(is_active=True).count(),
        'pos_by_company': pos_by_company,
        'invoices_month': Invoice.objects.filter(date_issued__date__gte=month_start).count(),
        'invoices_promet': Invoice.objects.filter(date_issued__date__gte=month_start).aggregate(t=Sum('total'))['t'] or 0,
        'eracun_total': ERacun.objects.count(),
        'eracun_sent': ERacun.objects.filter(status='sent').count(),
        'arhiva_total': ArhivaEntry.objects.count(),
        'disk_info': disk_info, 'mem_info': mem_info,
        'recent_logs': recent_logs,
        'feedback': ImprovementSuggestion.objects.filter(status='new').order_by('-created_at')[:5],
    }
    return render(request, 'dashboards/ivan_cockpit.html', context)
PYEOF
```

### 2. Dodaj URL u core/urls.py
Pronađi hr_patterns listu i dodaj PRIJE zadnjeg `]`:
```python
path('superadmin/ivan/', __import__('core.views', fromlist=['ivan_cockpit']).ivan_cockpit, name='ivan_cockpit'),
```

### 3. Provjeri i restartaj
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/superadmin/ivan/
# Mora biti 302
```

### 4. Javi rezultat
- HTTP status
- Django check output
