from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company

from .models import Asset, MaintenanceLog, MaintenanceSchedule


def _get_company(request):
    return get_user_company(request)


@login_required
def maintenance_dashboard(request):
    company = _get_company(request)
    now = timezone.now().date()
    assets = Asset.objects.filter(company=company)
    schedules = MaintenanceSchedule.objects.filter(asset__company=company, is_active=True)
    overdue = schedules.filter(next_due__lt=now)
    upcoming = schedules.filter(next_due__gte=now, next_due__lte=now + timedelta(days=30))
    expiring_insurance = assets.filter(insurance_until__isnull=False, insurance_until__lte=now + timedelta(days=90))
    expiring_registration = assets.filter(registration_until__isnull=False, registration_until__lte=now + timedelta(days=90))
    expiring_warranty = assets.filter(warranty_until__isnull=False, warranty_until__lte=now + timedelta(days=90))
    logs_month = MaintenanceLog.objects.filter(asset__company=company, date_performed__month=now.month, date_performed__year=now.year)
    cost_stats = logs_month.aggregate(
        total_cost=Sum('total_cost'),
        labor=Sum('labor_cost'),
        parts=Sum('parts_cost'),
    )
    return render(request, 'maintenance/dashboard.html', {
        'asset_count': assets.count(),
        'active_count': assets.filter(status='active').count(),
        'on_service': assets.filter(status='maintenance').count(),
        'overdue': overdue,
        'upcoming': upcoming,
        'expiring_insurance': expiring_insurance,
        'expiring_registration': expiring_registration,
        'expiring_warranty': expiring_warranty,
        'cost_stats': cost_stats,
    })


@login_required
def asset_list(request):
    company = _get_company(request)
    qs = Asset.objects.filter(company=company)
    category = request.GET.get('category')
    status = request.GET.get('status')
    search = request.GET.get('q')
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(asset_code__icontains=search) | Q(serial_number__icontains=search))
    return render(request, 'maintenance/asset_list.html', {
        'assets': qs, 'current_category': category, 'current_status': status, 'q': search or '',
        'categories': Asset.CATEGORY_CHOICES, 'statuses': Asset.STATUS_CHOICES,
    })


@login_required
def asset_create(request):
    company = _get_company(request)
    if request.method == 'POST':
        asset = Asset(company=company, created_by=request.user)
        asset.name = request.POST.get('name', '')
        asset.category = request.POST.get('category', 'equipment')
        asset.asset_code = asset.generate_asset_code()
        asset.make = request.POST.get('make', '')
        asset.model_name = request.POST.get('model_name', '')
        asset.serial_number = request.POST.get('serial_number', '')
        asset.description = request.POST.get('description', '')
        asset.location = request.POST.get('location', '')
        asset.registration_plate = request.POST.get('registration_plate', '')
        asset.vin = request.POST.get('vin', '')
        asset.fuel_type = request.POST.get('fuel_type', '')
        asset.insurance_policy = request.POST.get('insurance_policy', '')
        for df in ['purchase_date', 'warranty_until', 'insurance_until', 'registration_until', 'leasing_until']:
            val = request.POST.get(df)
            if val:
                setattr(asset, df, val)
        for nf in ['purchase_price', 'current_value', 'depreciation_rate']:
            val = request.POST.get(nf)
            if val:
                setattr(asset, nf, Decimal(val))
        mileage = request.POST.get('mileage')
        if mileage:
            asset.mileage = int(mileage)
        if 'photo' in request.FILES:
            asset.photo = request.FILES['photo']
        assigned = request.POST.get('assigned_to')
        if assigned:
            from django.contrib.auth.models import User
            asset.assigned_to = User.objects.filter(id=assigned).first()
        asset.save()
        messages.success(request, f'Imovina {asset.asset_code} kreirana.')
        return redirect('maintenance:asset_detail', pk=asset.pk)
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True)
    return render(request, 'maintenance/asset_form.html', {'edit': False, 'users': users, 'categories': Asset.CATEGORY_CHOICES})


@login_required
def asset_edit(request, pk):
    company = _get_company(request)
    asset = get_object_or_404(Asset, pk=pk, company=company)
    if request.method == 'POST':
        asset.name = request.POST.get('name', asset.name)
        asset.category = request.POST.get('category', asset.category)
        asset.status = request.POST.get('status', asset.status)
        asset.make = request.POST.get('make', '')
        asset.model_name = request.POST.get('model_name', '')
        asset.serial_number = request.POST.get('serial_number', '')
        asset.description = request.POST.get('description', '')
        asset.location = request.POST.get('location', '')
        asset.registration_plate = request.POST.get('registration_plate', '')
        asset.vin = request.POST.get('vin', '')
        asset.fuel_type = request.POST.get('fuel_type', '')
        asset.insurance_policy = request.POST.get('insurance_policy', '')
        for df in ['purchase_date', 'warranty_until', 'insurance_until', 'registration_until', 'leasing_until']:
            val = request.POST.get(df)
            if val:
                setattr(asset, df, val)
            else:
                setattr(asset, df, None)
        for nf in ['purchase_price', 'current_value', 'depreciation_rate']:
            val = request.POST.get(nf)
            if val:
                setattr(asset, nf, Decimal(val))
        mileage = request.POST.get('mileage')
        if mileage:
            asset.mileage = int(mileage)
        if 'photo' in request.FILES:
            asset.photo = request.FILES['photo']
        assigned = request.POST.get('assigned_to')
        if assigned:
            from django.contrib.auth.models import User
            asset.assigned_to = User.objects.filter(id=assigned).first()
        else:
            asset.assigned_to = None
        asset.save()
        messages.success(request, _('Imovina azurirana.'))
        return redirect('maintenance:asset_detail', pk=asset.pk)
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True)
    return render(request, 'maintenance/asset_form.html', {
        'asset': asset, 'edit': True, 'users': users,
        'categories': Asset.CATEGORY_CHOICES, 'statuses': Asset.STATUS_CHOICES,
    })


@login_required
def asset_detail(request, pk):
    company = _get_company(request)
    asset = get_object_or_404(Asset, pk=pk, company=company)
    schedules = asset.schedules.filter(is_active=True)
    logs = asset.logs.all()[:20]
    now = timezone.now().date()
    alerts = []
    if asset.insurance_until and asset.insurance_until <= now + timedelta(days=30):
        alerts.append({'type': 'warning', 'msg': f'Osiguranje istice {asset.insurance_until}'})
    if asset.registration_until and asset.registration_until <= now + timedelta(days=30):
        alerts.append({'type': 'danger', 'msg': f'Registracija istice {asset.registration_until}'})
    if asset.warranty_until and asset.warranty_until <= now + timedelta(days=30):
        alerts.append({'type': 'info', 'msg': f'Garancija istice {asset.warranty_until}'})
    for s in schedules:
        if s.is_overdue:
            alerts.append({'type': 'danger', 'msg': f'Zakasnjelo: {s.task_name} (rok: {s.next_due})'})
    return render(request, 'maintenance/asset_detail.html', {
        'asset': asset, 'schedules': schedules, 'logs': logs, 'alerts': alerts,
    })


@login_required
def add_maintenance_log(request, pk):
    company = _get_company(request)
    asset = get_object_or_404(Asset, pk=pk, company=company)
    if request.method == 'POST':
        log = MaintenanceLog(asset=asset, created_by=request.user)
        log.title = request.POST.get('title', '')
        log.maintenance_type = request.POST.get('maintenance_type', 'preventive')
        log.description = request.POST.get('description', '')
        log.service_provider = request.POST.get('service_provider', '')
        log.invoice_number = request.POST.get('invoice_number', '')
        date = request.POST.get('date_performed')
        if date:
            log.date_performed = date
        for nf in ['labor_cost', 'parts_cost']:
            val = request.POST.get(nf)
            if val:
                setattr(log, nf, Decimal(val))
        mileage = request.POST.get('mileage_at_service')
        if mileage:
            log.mileage_at_service = int(mileage)
        schedule_id = request.POST.get('schedule')
        if schedule_id:
            log.schedule = MaintenanceSchedule.objects.filter(id=schedule_id, asset=asset).first()
        log.save()
        messages.success(request, _('Servisni zapis dodan.'))
        return redirect('maintenance:asset_detail', pk=asset.pk)
    schedules = asset.schedules.filter(is_active=True)
    return render(request, 'maintenance/add_log.html', {
        'asset': asset, 'schedules': schedules, 'types': MaintenanceLog.TYPE_CHOICES,
    })


@login_required
def add_schedule(request, pk):
    company = _get_company(request)
    asset = get_object_or_404(Asset, pk=pk, company=company)
    if request.method == 'POST':
        sched = MaintenanceSchedule(asset=asset)
        sched.task_name = request.POST.get('task_name', '')
        sched.description = request.POST.get('description', '')
        sched.frequency = request.POST.get('frequency', 'monthly')
        sched.next_due = request.POST.get('next_due')
        sched.service_provider = request.POST.get('service_provider', '')
        cost = request.POST.get('estimated_cost')
        if cost:
            sched.estimated_cost = Decimal(cost)
        interval = request.POST.get('mileage_interval')
        if interval:
            sched.mileage_interval = int(interval)
        notify = request.POST.get('notify_days_before')
        if notify:
            sched.notify_days_before = int(notify)
        sched.save()
        messages.success(request, _('Raspored odrzavanja dodan.'))
        return redirect('maintenance:asset_detail', pk=asset.pk)
    return render(request, 'maintenance/add_schedule.html', {
        'asset': asset, 'frequencies': MaintenanceSchedule.FREQUENCY_CHOICES,
    })


@login_required
def maintenance_calendar(request):
    company = _get_company(request)
    now = timezone.now().date()
    schedules = MaintenanceSchedule.objects.filter(
        asset__company=company, is_active=True,
        next_due__gte=now, next_due__lte=now + timedelta(days=90)
    ).select_related('asset').order_by('next_due')
    return render(request, 'maintenance/calendar.html', {'schedules': schedules, 'today': now})


@login_required
def expiring_list(request):
    company = _get_company(request)
    now = timezone.now().date()
    threshold = now + timedelta(days=90)
    assets = Asset.objects.filter(company=company)
    expiring = []
    for asset in assets:
        items = []
        if asset.insurance_until and asset.insurance_until <= threshold:
            items.append({'doc': 'Osiguranje', 'date': asset.insurance_until, 'expired': asset.insurance_until < now})
        if asset.registration_until and asset.registration_until <= threshold:
            items.append({'doc': 'Registracija', 'date': asset.registration_until, 'expired': asset.registration_until < now})
        if asset.warranty_until and asset.warranty_until <= threshold:
            items.append({'doc': 'Garancija', 'date': asset.warranty_until, 'expired': asset.warranty_until < now})
        if asset.leasing_until and asset.leasing_until <= threshold:
            items.append({'doc': 'Leasing', 'date': asset.leasing_until, 'expired': asset.leasing_until < now})
        if items:
            expiring.append({'asset': asset, 'items': items})
    return render(request, 'maintenance/expiring.html', {'expiring': expiring})


@login_required
def alerts_api(request):
    company = _get_company(request)
    now = timezone.now().date()
    overdue = MaintenanceSchedule.objects.filter(
        asset__company=company, is_active=True, next_due__lt=now
    ).count()
    expiring = Asset.objects.filter(
        company=company
    ).filter(
        Q(insurance_until__lte=now + timedelta(days=30)) |
        Q(registration_until__lte=now + timedelta(days=30))
    ).count()
    return JsonResponse({
        'overdue_maintenance': overdue,
        'expiring_docs': expiring,
        'total_alerts': overdue + expiring,
    })


@login_required
def asset_register(request):
    company = _get_company(request)
    assets = Asset.objects.filter(company=company).order_by('asset_code')
    totals = {
        'purchase': sum(a.purchase_price for a in assets),
        'accumulated': sum(a.accumulated_depreciation for a in assets),
        'current': sum(a.current_value for a in assets),
    }
    from maintenance.services import calculate_monthly_depreciation
    asset_data = []
    for asset in assets:
        monthly = calculate_monthly_depreciation(asset)
        asset_data.append({'asset': asset, 'monthly_depreciation': monthly,
            'fully_depreciated': asset.accumulated_depreciation >= (asset.purchase_price - asset.salvage_value) if asset.purchase_price > 0 else False})
    return render(request, 'maintenance/asset_register.html', {'asset_data': asset_data, 'totals': totals})


@login_required
def run_depreciation(request):
    if request.method != 'POST':
        return redirect('maintenance:asset_register')
    company = _get_company(request)
    now = timezone.now()
    from maintenance.services import run_monthly_depreciation
    entries = run_monthly_depreciation(company, now.year, now.month)
    if entries:
        messages.success(request, f'Amortizacija provedena za {len(entries)} sredstava.')
    else:
        messages.info(request, _('Nema sredstava za amortizaciju ili vec provedena.'))
    return redirect('maintenance:asset_register')
