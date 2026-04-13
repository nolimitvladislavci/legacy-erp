from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company

from .models import MeterReading, UtilityBill, UtilityContract


@login_required
def utilities_dashboard(request):
    """Glavni dashboard režija — trend, anomalije, ugovori, računi."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    today = timezone.now().date()
    year = today.year

    contracts = UtilityContract.objects.filter(company=company, is_active=True)
    bills = UtilityBill.objects.filter(company=company)
    bills_year = bills.filter(issue_date__year=year)

    # KPI
    total_year = bills_year.filter(status__in=('verified', 'booked', 'paid')).aggregate(s=Sum('total'))['s'] or 0
    pending_bills = bills.filter(status='pending').count()
    anomalies = bills.filter(is_anomaly=True, status__in=('pending', 'verified')).order_by('-issue_date')[:10]
    expiring = [c for c in contracts if c.is_expiring_soon]

    # Trend po mjesecima (zadnjih 12)
    from django.db.models.functions import TruncMonth
    monthly = (
        bills.filter(issue_date__gte=today.replace(year=year - 1))
        .annotate(month=TruncMonth('issue_date'))
        .values('month')
        .annotate(total=Sum('total'))
        .order_by('month')
    )
    trend_labels = [m['month'].strftime('%m/%y') for m in monthly]
    trend_data = [float(m['total'] or 0) for m in monthly]

    # Po vrsti
    by_type = (
        bills_year.values('contract__utility_type')
        .annotate(total=Sum('total'))
        .order_by('-total')
    )

    # Recent bills
    recent_bills = bills.order_by('-issue_date')[:15]

    # Recent readings
    recent_readings = MeterReading.objects.filter(
        contract__company=company
    ).order_by('-date')[:10]

    import json
    return render(request, 'utilities/dashboard.html', {
        'contracts': contracts,
        'total_year': total_year,
        'pending_bills': pending_bills,
        'anomalies': anomalies,
        'expiring': expiring,
        'trend_labels': json.dumps(trend_labels),
        'trend_data': json.dumps(trend_data),
        'by_type': by_type,
        'recent_bills': recent_bills,
        'recent_readings': recent_readings,
        'year': year,
        'page_title': 'Režije i komunalije',
    })


@login_required
def bill_book(request, bill_id):
    """Proknjiži račun režija."""
    bill = get_object_or_404(UtilityBill, pk=bill_id)
    company = get_user_company(request)
    if bill.company != company:
        messages.error(request, _('Nemate ovlasti za ovu radnju. Obratite se administratoru.'))
        return redirect('utilities:dashboard')

    je = bill.book(user=request.user)
    if je:
        messages.success(request, f'Proknjiženo: {je.entry_number}')

        # Detect anomaly after booking
        if bill.detect_anomaly():
            messages.warning(request, f'⚠️ Anomalija: {bill.anomaly_note}')
    else:
        messages.info(request, _('Već proknjiženo.'))

    return redirect('utilities:dashboard')
