from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext as _
from datetime import timedelta
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import SeasonalWorker, SeasonalContract, SeasonalPayment


def _company(request):
    from core.company_utils import get_user_company
    return get_user_company(request)


@login_required
def dashboard(request):
    company = _company(request)
    today   = timezone.localdate()

    active = SeasonalContract.objects.filter(
        company=company, status='active'
    ).select_related('worker').order_by('end_date')

    upcoming = SeasonalContract.objects.filter(
        company=company, status='pending',
        start_date__lte=today + timedelta(days=14)
    ).select_related('worker').order_by('start_date')

    # HZMO alarmi
    hzmo_alerts = []
    for c in SeasonalContract.objects.filter(
        company=company,
        contract_type='odredjeno',
        status__in=['active', 'pending', 'completed']
    ).select_related('worker'):
        if c.needs_hzmo_prijava:
            dl = (c.hzmo_prijava_deadline - today).days
            hzmo_alerts.append({'contract': c, 'type': 'M-1 prijava',
                                 'deadline': c.hzmo_prijava_deadline,
                                 'days_left': dl, 'urgent': dl <= 2})
        if c.contract_type == 'odredjeno' and c.status == 'completed' and not c.hzmo_odjava_sent:
            dl = (c.hzmo_odjava_deadline - today).days
            hzmo_alerts.append({'contract': c, 'type': 'M-2 odjava',
                                 'deadline': c.hzmo_odjava_deadline,
                                 'days_left': dl, 'urgent': dl <= 2})

    year = today.year
    paid_payments = SeasonalPayment.objects.filter(
        company=company, payment_date__year=year, status='paid')
    total_gross_year = sum(p.gross_amount for p in paid_payments)

    stats = {
        'total_workers':      SeasonalWorker.objects.filter(company=company).count(),
        'active_now':         active.count(),
        'contracts_year':     SeasonalContract.objects.filter(
                                  company=company, start_date__year=year).count(),
        'total_gross_year':   total_gross_year,
        'hzmo_alert_count':   len(hzmo_alerts),
    }

    return render(request, 'seasonal/dashboard.html', {
        'active_contracts':   active,
        'upcoming_contracts': upcoming,
        'hzmo_alerts':        hzmo_alerts,
        'stats':              stats,
        'today':              today,
    })


@login_required
def worker_list(request):
    company = _company(request)
    q = request.GET.get('q', '')
    qs = SeasonalWorker.objects.filter(company=company)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(oib__icontains=q))
    return render(request, 'seasonal/worker_list.html', {'workers': qs, 'q': q})


@login_required
def worker_create(request):
    company = _company(request)
    if request.method == 'POST':
        p = request.POST
        oib = p.get('oib', '').strip()
        from core.oib_validator import validate_oib_hr
        if not validate_oib_hr(oib):
            messages.error(request, _('OIB mora biti točno 11 znamenki.'))
            return render(request, 'seasonal/worker_form.html',
                          {'nationality_choices': SeasonalWorker.NATIONALITY_CHOICES,
                           'form_data': p})
        if SeasonalWorker.objects.filter(company=company, oib=oib).exists():
            messages.error(request, f'Radnik s OIB-om {oib} već postoji.')
            return render(request, 'seasonal/worker_form.html',
                          {'nationality_choices': SeasonalWorker.NATIONALITY_CHOICES,
                           'form_data': p})
        worker = SeasonalWorker.objects.create(
            company=company,
            first_name=p['first_name'].strip(),
            last_name=p['last_name'].strip(),
            oib=oib,
            nationality=p.get('nationality', 'HR'),
            phone=p.get('phone', '').strip(),
            email=p.get('email', '').strip(),
            iban=p.get('iban', '').strip(),
            address=p.get('address', '').strip(),
            notes=p.get('notes', '').strip(),
        )
        messages.success(request, f'{worker.full_name} dodan u bazu.')
        if p.get('create_contract'):
            return redirect('seasonal:contract_create', worker_pk=worker.pk)
        return redirect('seasonal:worker_detail', pk=worker.pk)
    return render(request, 'seasonal/worker_form.html',
                  {'nationality_choices': SeasonalWorker.NATIONALITY_CHOICES})


@login_required
def worker_detail(request, pk):
    company  = _company(request)
    worker   = get_object_or_404(SeasonalWorker, pk=pk, company=company)
    contracts = worker.contracts.filter(company=company).order_by('-start_date')
    return render(request, 'seasonal/worker_detail.html',
                  {'worker': worker, 'contracts': contracts})


@login_required
def contract_create(request, worker_pk):
    company = _company(request)
    worker  = get_object_or_404(SeasonalWorker, pk=worker_pk, company=company)
    if request.method == 'POST':
        p = request.POST
        try:
            from decimal import Decimal
            contract = SeasonalContract.objects.create(
                company=company, worker=worker,
                contract_type=p['contract_type'],
                start_date=p['start_date'],
                end_date=p['end_date'],
                gross_amount=Decimal(p['gross_amount']),
                payment_cycle=p.get('payment_cycle', 'lump_sum'),
                position=p.get('position', '').strip(),
                notes=p.get('notes', '').strip(),
                status='pending',
                created_by=request.user,
            )
            messages.success(request,
                f'Ugovor kreiran: {worker.full_name} '
                f'({contract.start_date} → {contract.end_date}, '
                f'{contract.gross_amount}€ bruto)')
            if contract.contract_type == 'odredjeno':
                messages.info(request,
                    f'⚠️ M-1 HZMO prijava: rok {contract.hzmo_prijava_deadline}')
            return redirect('seasonal:contract_detail', pk=contract.pk)
        except (ValueError, TypeError) as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    return render(request, 'seasonal/contract_form.html', {
        'worker': worker,
        'contract_type_choices': SeasonalContract.CONTRACT_TYPE_CHOICES,
        'payment_cycle_choices': SeasonalContract.PAYMENT_CYCLE_CHOICES,
        'today': timezone.localdate(),
    })


@login_required
def contract_detail(request, pk):
    company  = _company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    payments = contract.payments.all().order_by('-payment_date')
    return render(request, 'seasonal/contract_detail.html', {
        'contract':               contract,
        'payments':               payments,
        'net_estimate':           contract.net_estimate(),
        'days_worked':            contract.days_worked_so_far,
        'today':                  timezone.localdate(),
        'hzmo_prijava_deadline':  contract.hzmo_prijava_deadline,
        'hzmo_odjava_deadline':   contract.hzmo_odjava_deadline,
    })


@login_required
def contract_activate(request, pk):
    company  = _company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    if request.method == 'POST':
        contract.status = 'active'
        contract.save(update_fields=['status'])
        messages.success(request, f'{contract.worker.full_name} je aktivan.')
        if contract.needs_hzmo_prijava:
            messages.warning(request,
                f'⚠️ M-1 HZMO mora biti poslana do {contract.hzmo_prijava_deadline}!')
    return redirect('seasonal:contract_detail', pk=pk)


@login_required
def contract_complete(request, pk):
    company  = _company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    if request.method == 'POST':
        contract.status = 'completed'
        contract.save(update_fields=['status'])
        messages.success(request, f'Sezona završena: {contract.worker.full_name}.')
        if contract.contract_type == 'odredjeno' and not contract.hzmo_odjava_sent:
            messages.warning(request,
                f'⚠️ M-2 HZMO mora biti poslana do {contract.hzmo_odjava_deadline}!')
        # Auto-kreiraj finalnu isplatu za lump_sum
        if (contract.payment_cycle == 'lump_sum'
                and not contract.payments.filter(
                    status__in=['planned','approved','paid']).exists()):
            SeasonalPayment.objects.create(
                company=company, contract=contract,
                payment_date=contract.end_date,
                gross_amount=contract.gross_amount,
                payment_method='bank',
                notes='Auto-kreirana završna isplata',
                status='planned',
            )
            messages.info(request, _('Završna isplata automatski kreirana — provjeri i odobri.'))
    return redirect('seasonal:contract_detail', pk=pk)


@login_required
def payment_create(request, contract_pk):
    company  = _company(request)
    contract = get_object_or_404(SeasonalContract, pk=contract_pk, company=company)
    if request.method == 'POST':
        p = request.POST
        from decimal import Decimal
        payment = SeasonalPayment.objects.create(
            company=company, contract=contract,
            payment_date=p['payment_date'],
            gross_amount=Decimal(p['gross_amount']),
            payment_method=p.get('payment_method', 'bank'),
            notes=p.get('notes', '').strip(),
            status='planned',
        )
        if p.get('approve_now'):
            payment.calculate_and_approve(approved_by=request.user)
            messages.success(request,
                f'Isplata odobrena: {payment.net_amount}€ neto '
                f'za {contract.worker.full_name}.')
        else:
            messages.success(request, _('Isplata kreirana.'))
        return redirect('seasonal:contract_detail', pk=contract_pk)
    return render(request, 'seasonal/payment_form.html', {
        'contract':     contract,
        'today':        timezone.localdate(),
        'net_estimate': contract.net_estimate(),
    })


@login_required
def payment_approve(request, pk):
    company = _company(request)
    payment = get_object_or_404(SeasonalPayment, pk=pk, company=company)
    if request.method == 'POST':
        payment.calculate_and_approve(approved_by=request.user)
        messages.success(request,
            f'{payment.gross_amount}€ bruto → {payment.net_amount}€ neto '
            f'— {payment.contract.worker.full_name}')
    return redirect('seasonal:contract_detail', pk=payment.contract.pk)


@login_required
def hzmo_mark_sent(request, contract_pk, action):
    company  = _company(request)
    contract = get_object_or_404(SeasonalContract, pk=contract_pk, company=company)
    if request.method == 'POST':
        today = timezone.localdate()
        if action == 'm1':
            contract.hzmo_prijava_sent = True
            contract.hzmo_prijava_date = today
            contract.save(update_fields=['hzmo_prijava_sent', 'hzmo_prijava_date'])
            messages.success(request, f'M-1 zabilježena za {contract.worker.full_name}.')
        elif action == 'm2':
            contract.hzmo_odjava_sent = True
            contract.hzmo_odjava_date = today
            contract.save(update_fields=['hzmo_odjava_sent', 'hzmo_odjava_date'])
            messages.success(request, f'M-2 zabilježena za {contract.worker.full_name}.')
    return redirect('seasonal:contract_detail', pk=contract_pk)


@login_required
def cost_report(request):
    company = _company(request)
    year    = int(request.GET.get('year', timezone.localdate().year))
    contracts = SeasonalContract.objects.filter(
        company=company, start_date__year=year
    ).select_related('worker').prefetch_related('payments')
    total_gross  = sum(c.gross_amount for c in contracts)
    total_paid   = sum(
        p.net_amount for c in contracts
        for p in c.payments.filter(status='paid')
    )
    workers_count = contracts.values('worker').distinct().count()
    return render(request, 'seasonal/cost_report.html', {
        'contracts': contracts, 'total_gross': total_gross,
        'years_range': list(range(2024, timezone.localdate().year + 2)),
        'total_paid': total_paid, 'workers_count': workers_count, 'year': year,
    })
