# Dodaj na kraj core/views.py

@login_required
def ivan_cockpit(request):
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    import subprocess
    from django.contrib.auth.models import User
    from companies.models import Company
    from registration.models import CompanySubscription
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_start = today.replace(day=1)
    ctx = {}
    ctx['now'] = now
    ctx['today'] = today
    # Korisnici
    ctx['users_total'] = User.objects.count()
    ctx['users_week'] = User.objects.filter(last_login__gte=week_ago).count()
    ctx['users_never'] = User.objects.filter(last_login__isnull=True, is_active=True).count()
    # Kompanije
    ctx['companies'] = Company.objects.count()
    subs = list(CompanySubscription.objects.filter(is_active=True).select_related('company').order_by('-monthly_fee'))
    ctx['subs'] = subs
    ctx['mrr'] = sum(float(s.monthly_fee or 0) for s in subs)
    # POS
    try:
        from pos.models import POSReceipt, POSSession
        paid = POSReceipt.objects.filter(created_at__date=today, status='paid')
        ctx['pos_promet'] = float(paid.aggregate(t=Sum('total'))['t'] or 0)
        ctx['pos_bonovi'] = paid.count()
        ctx['pos_open'] = POSSession.objects.filter(status='open').count()
        ctx['pos_by_company'] = list(
            POSReceipt.objects.filter(created_at__date=today, status='paid')
            .values('session__terminal__company__name')
            .annotate(p=Sum('total'), b=Count('id')).order_by('-p')
        )
        ctx['pos_week'] = float(POSReceipt.objects.filter(
            created_at__gte=week_ago, status='paid'
        ).aggregate(t=Sum('total'))['t'] or 0)
    except Exception:
        ctx['pos_promet'] = ctx['pos_bonovi'] = ctx['pos_open'] = ctx['pos_week'] = 0
        ctx['pos_by_company'] = []
    # Fakture
    try:
        from invoicing.models import Invoice
        ctx['inv_month'] = float(Invoice.objects.filter(
            date_issued__date__gte=month_start
        ).aggregate(t=Sum('total'))['t'] or 0)
        ctx['inv_count'] = Invoice.objects.count()
    except Exception:
        ctx['inv_month'] = ctx['inv_count'] = 0
    # eRacun
    try:
        from eracun.models import ERacun
        ctx['eracun_total'] = ERacun.objects.count()
        ctx['eracun_sent'] = ERacun.objects.filter(status='sent').count()
    except Exception:
        ctx['eracun_total'] = ctx['eracun_sent'] = 0
    # Arhiva
    try:
        from documents.models import ArhivaEntry
        ctx['arhiva'] = ArhivaEntry.objects.count()
    except Exception:
        ctx['arhiva'] = 0
    # Server
    try:
        d = subprocess.check_output(['df','-h','/'],text=True).split('\n')[1].split()
        ctx['disk_used'] = d[4]; ctx['disk_free'] = d[3]
    except Exception:
        ctx['disk_used'] = ctx['disk_free'] = 'N/A'
    try:
        m = subprocess.check_output(['free','-h'],text=True).split('\n')[1].split()
        ctx['mem_used'] = m[2]; ctx['mem_total'] = m[1]
    except Exception:
        ctx['mem_used'] = ctx['mem_total'] = 'N/A'
    # Feedback
    try:
        from pos.models import ImprovementSuggestion
        ctx['feedback'] = list(ImprovementSuggestion.objects.filter(status='new').order_by('-created_at')[:5])
    except Exception:
        ctx['feedback'] = []
    # Logovi
    try:
        lines = subprocess.check_output(['tail','-30','/var/www/fina-connect/logs/django.log'],text=True).split('\n')
        ctx['logs'] = [l for l in lines if any(k in l for k in ['ERROR','WARNING','whatsapp','pos_checkout'])][-6:]
    except Exception:
        ctx['logs'] = []
    return render(request, 'dashboards/ivan_cockpit.html', ctx)
