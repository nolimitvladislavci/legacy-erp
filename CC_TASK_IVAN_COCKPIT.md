## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Ivan Dashboard (Superadmin osobni cockpit)

## Što gradimo
Jedna stranica dostupna SAMO superadminu na:
  `/hr/superadmin/ivan/`

Nije generički admin. Nije Control Tower. Ovo je **Ivan's cockpit** —
sve što treba znati u jednom pogledu, bez klikanja.

## Korak 0 — Provjeri što postoji
```bash
grep -n "ivan\|cockpit\|personal" /var/www/fina-connect/core/urls.py | head -5
cat /var/www/fina-connect/core/views.py | grep -n "def superadmin_dashboard" | head -3
# Provjeri što vraća control_tower_api — iskoristi iste podatke
sed -n "1981,2050p" /var/www/fina-connect/core/views.py
```

## Korak 1 — View u core/views.py

Dodaj na kraj `core/views.py`:

```python
@login_required
def ivan_cockpit(request):
    """Ivan's personal superadmin cockpit — sve na jednom mjestu."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    from django.contrib.auth.models import User
    from companies.models import Company
    from registration.models import CompanySubscription
    from pos.models import POSReceipt, POSSession, POSTerminal
    from invoicing.models import Invoice
    from documents.models import ArhivaEntry
    from eracun.models import ERacun
    import subprocess, os

    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_start = today.replace(day=1)

    # ── Korisnici ──
    users_total = User.objects.count()
    users_active_week = User.objects.filter(last_login__gte=week_ago).count()
    users_never = User.objects.filter(last_login__isnull=True, is_active=True).count()

    # ── Kompanije + pretplate ──
    companies = Company.objects.count()
    subs = CompanySubscription.objects.filter(is_active=True).select_related('company')
    mrr = sum(s.monthly_fee for s in subs if s.monthly_fee)

    # ── POS ──
    pos_today = POSReceipt.objects.filter(created_at__date=today, status='paid')
    pos_promet_danas = pos_today.aggregate(t=Sum('total'))['t'] or 0
    pos_bonovi_danas = pos_today.count()
    pos_open_sessions = POSSession.objects.filter(status='open').count()
    pos_terminal_count = POSTerminal.objects.filter(is_active=True).count()

    # ── POS po kompanijama danas ──
    pos_by_company = (POSReceipt.objects
        .filter(created_at__date=today, status='paid')
        .values('session__terminal__company__name')
        .annotate(promet=Sum('total'), bonovi=Count('id'))
        .order_by('-promet'))

    # ── Fakture ──
    invoices_month = Invoice.objects.filter(date_issued__date__gte=month_start)
    invoices_promet = invoices_month.aggregate(t=Sum('total'))['t'] or 0

    # ── eRačun ──
    eracun_total = ERacun.objects.count()
    eracun_sent = ERacun.objects.filter(status='sent').count()

    # ── Arhiva ──
    arhiva_total = ArhivaEntry.objects.count()

    # ── Server health ──
    try:
        disk = subprocess.check_output(['df', '-h', '/'], text=True).split('\n')[1].split()
        disk_used = disk[4]  # npr. "45%"
        disk_free = disk[3]
    except Exception:
        disk_used = disk_free = 'N/A'

    try:
        mem = subprocess.check_output(['free', '-h'], text=True).split('\n')[1].split()
        mem_used = mem[2]
        mem_total = mem[1]
    except Exception:
        mem_used = mem_total = 'N/A'

    # ── Zadnji log eventi ──
    try:
        log_lines = subprocess.check_output(
            ['tail', '-20', '/var/www/fina-connect/logs/django.log'],
            text=True
        ).strip().split('\n')
        recent_logs = [l for l in log_lines if any(k in l for k in ['ERROR','WARNING','INFO whatsapp','INFO pos'])][-8:]
    except Exception:
        recent_logs = []

    # ── Zadnji feedback od korisnika ──
    from pos.models import ImprovementSuggestion
    feedback = ImprovementSuggestion.objects.filter(
        status='new'
    ).order_by('-created_at')[:5]

    context = {
        'now': now,
        'today': today,
        # Korisnici
        'users_total': users_total,
        'users_active_week': users_active_week,
        'users_never': users_never,
        # Kompanije
        'companies': companies,
        'subs': subs,
        'mrr': mrr,
        # POS
        'pos_promet_danas': pos_promet_danas,
        'pos_bonovi_danas': pos_bonovi_danas,
        'pos_open_sessions': pos_open_sessions,
        'pos_terminal_count': pos_terminal_count,
        'pos_by_company': list(pos_by_company),
        # Fakture
        'invoices_promet': invoices_promet,
        # eRačun
        'eracun_total': eracun_total,
        'eracun_sent': eracun_sent,
        # Arhiva
        'arhiva_total': arhiva_total,
        # Server
        'disk_used': disk_used,
        'disk_free': disk_free,
        'mem_used': mem_used,
        'mem_total': mem_total,
        # Logovi
        'recent_logs': recent_logs,
        # Feedback
        'feedback': feedback,
    }
    return render(request, 'dashboards/ivan_cockpit.html', context)
```

## Korak 2 — URL u core/urls.py

U hr_patterns dodaj:
```python
path('superadmin/ivan/', ivan_cockpit_view, name='ivan_cockpit'),
```
Gdje je `ivan_cockpit_view = __import__('core.views', fromlist=['ivan_cockpit']).ivan_cockpit`

## Korak 3 — Template

Kreiraj `/var/www/fina-connect/templates/dashboards/ivan_cockpit.html`

Dark gold tema, mobilno-friendly. Struktura:

```
┌─────────────────────────────────────────────┐
│  🔥 FENIX COCKPIT        20.03.2026  02:30  │
│  Ivan Brtan — Superadmin                    │
├──────────┬──────────┬──────────┬────────────┤
│ 💶 MRR   │ 👤 Users │ 🏢 Subs  │ 🖥️ Server  │
│ 1.330€   │ 318      │ 11 akt.  │ disk/mem   │
├──────────┴──────────┴──────────┴────────────┤
│  POS DANAS                                  │
│  Promet: X EUR | Bonovi: X | Smjene: X      │
│  [Po kompanijama tablica]                   │
├─────────────────────────────────────────────┤
│  PRETPLATE (11 aktivnih)                    │
│  Konjik 298€ | Korpaš 298€ | ...           │
├─────────────────────────────────────────────┤
│  FEEDBACK (novi) | ZADNJI LOGOVI            │
└─────────────────────────────────────────────┘
```

CSS: dark (#0a0a0a bg), gold (#c9a84c akcent), karticice s border-left gold.
Font: monospace za logove, sans-serif za ostatak.
Auto-refresh: `<meta http-equiv="refresh" content="60">` — osvježi svaku minutu.
Mobile: grid 2 col na mobitelu, 4 col na desktopu.

## Korak 4 — Sidebar link

U `/var/www/fina-connect/templates/base.html`, unutar
`{% if user.is_superuser %}` bloka, dodaj:
```html
<a href="{% url 'ivan_cockpit' %}">🔥 Cockpit</a>
```

## Korak 5 — Test
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/superadmin/ivan/
# Mora biti 302 (redirect na login ako nisi prijavljen)
```

## PRAVILA
- Ne diraj postojeći superadmin_dashboard
- Sve u try/except — cockpit nikad ne smije baciti 500
- Auto-refresh 60s — Ivan vidi live podatke
- Mobile first — Šeki i Ivan gledaju na mobitelu
- Backup base.html prije dodavanja linka
