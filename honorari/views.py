"""
Honorari Views — ugovori o djelu, autorski honorari, obračuni.
"""
import datetime
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _

from .models import (
    HonorarContract, HonorarCalculation,
    HonorarJOPPD, HonorarPayment,
)
from partners.models import Partner
from django.core.exceptions import ObjectDoesNotExist


def _get_company(request):
    """Get active company for current user."""
    company = getattr(request, 'impersonated_company', None)
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass
    return company


# ═══════════════════════════════════════════════════
#  LISTA UGOVORA
# ═══════════════════════════════════════════════════
@login_required
def contract_list(request):
    """Lista svih ugovora o honorarima."""
    company = _get_company(request)
    if not company:
        messages.warning(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    status = request.GET.get('status', '')
    ctype = request.GET.get('type', '')
    q = request.GET.get('q', '')

    qs = HonorarContract.objects.filter(company=company).select_related('contractor')

    if status:
        qs = qs.filter(status=status)
    if ctype:
        qs = qs.filter(contract_type=ctype)
    if q:
        qs = qs.filter(
            Q(contract_number__icontains=q) |
            Q(description__icontains=q) |
            Q(contractor__name__icontains=q)
        )

    # Statistike
    total_gross = qs.aggregate(t=Sum('gross_amount'))['t'] or Decimal('0')
    active_count = qs.filter(status='active').count()

    ctx = {
        'contracts': qs[:200],
        'total_gross': total_gross,
        'active_count': active_count,
        'total_count': qs.count(),
        'current_status': status,
        'current_type': ctype,
        'search_q': q,
        'status_choices': HonorarContract.STATUS_CHOICES,
        'type_choices': HonorarContract.CONTRACT_TYPES,
    }
    return render(request, 'honorari/contract_list.html', ctx)


# ═══════════════════════════════════════════════════
#  DETALJ UGOVORA
# ═══════════════════════════════════════════════════
@login_required
def contract_detail(request, pk):
    """Detalj ugovora s obračunima i isplatama."""
    company = _get_company(request)
    contract = get_object_or_404(HonorarContract, pk=pk, company=company)
    calculations = contract.calculations.all().order_by('-calculation_date')

    total_net = calculations.aggregate(t=Sum('net_amount'))['t'] or Decimal('0')
    total_paid = Decimal('0')
    for calc in calculations:
        paid = calc.payments.filter(is_paid=True).aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        total_paid += paid

    ctx = {
        'contract': contract,
        'calculations': calculations,
        'total_net': total_net,
        'total_paid': total_paid,
        'remaining': total_net - total_paid,
    }
    return render(request, 'honorari/contract_detail.html', ctx)


# ═══════════════════════════════════════════════════
#  KREIRANJE UGOVORA
# ═══════════════════════════════════════════════════
@login_required
def contract_create(request):
    """Kreiranje novog ugovora o honoraru."""
    company = _get_company(request)
    if not company:
        messages.warning(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    if request.method == 'GET':
        partners = Partner.objects.filter(company=company).order_by('name')
        ctx = {
            'partners': partners,
            'type_choices': HonorarContract.CONTRACT_TYPES,
        }
        return render(request, 'honorari/contract_form.html', ctx)

    # POST
    try:
        contract = HonorarContract(
            company=company,
            created_by=request.user,
            contract_type=request.POST.get('contract_type', 'ugovor_djelo'),
            contract_number=request.POST.get('contract_number', '').strip(),
            description=request.POST.get('description', '').strip(),
            gross_amount=Decimal(request.POST.get('gross_amount', '0').replace(',', '.')),
            start_date=request.POST.get('start_date', ''),
            end_date=request.POST.get('end_date', ''),
            status=request.POST.get('status', 'draft'),
        )
        contractor_id = request.POST.get('contractor')
        if contractor_id:
            contract.contractor = Partner.objects.get(pk=contractor_id, company=company)
        contract.save()
        messages.success(request, f'Ugovor {contract.contract_number} kreiran.')
        return redirect('honorari:contract_detail', pk=contract.pk)
    except ObjectDoesNotExist as e:
        partners = Partner.objects.filter(company=company).order_by('name')
        ctx = {
            'partners': partners,
            'type_choices': HonorarContract.CONTRACT_TYPES,
            'error': str(e),
            'form_data': request.POST,
        }
        return render(request, 'honorari/contract_form.html', ctx)


@login_required
def contract_edit(request, pk):
    """Uređivanje postojećeg ugovora."""
    company = _get_company(request)
    contract = get_object_or_404(HonorarContract, pk=pk, company=company)

    if request.method == 'GET':
        partners = Partner.objects.filter(company=company).order_by('name')
        ctx = {
            'contract': contract,
            'partners': partners,
            'type_choices': HonorarContract.CONTRACT_TYPES,
            'edit_mode': True,
        }
        return render(request, 'honorari/contract_form.html', ctx)

    # POST
    try:
        contract.contract_type = request.POST.get('contract_type', contract.contract_type)
        contract.contract_number = request.POST.get('contract_number', '').strip()
        contract.description = request.POST.get('description', '').strip()
        contract.gross_amount = Decimal(request.POST.get('gross_amount', '0').replace(',', '.'))
        contract.start_date = request.POST.get('start_date', '')
        contract.end_date = request.POST.get('end_date', '')
        contract.status = request.POST.get('status', contract.status)

        contractor_id = request.POST.get('contractor')
        if contractor_id:
            contract.contractor = Partner.objects.get(pk=contractor_id, company=company)
        else:
            contract.contractor = None

        contract.save()
        messages.success(request, f'Ugovor {contract.contract_number} ažuriran.')
        return redirect('honorari:contract_detail', pk=contract.pk)
    except ObjectDoesNotExist as e:
        partners = Partner.objects.filter(company=company).order_by('name')
        ctx = {
            'contract': contract,
            'partners': partners,
            'type_choices': HonorarContract.CONTRACT_TYPES,
            'edit_mode': True,
            'error': str(e),
        }
        return render(request, 'honorari/contract_form.html', ctx)


# ═══════════════════════════════════════════════════
#  KREIRANJE OBRAČUNA
# ═══════════════════════════════════════════════════
@login_required
def calculation_create(request, pk):
    """Kreiraj obračun za ugovor i automatski izračunaj."""
    company = _get_company(request)
    contract = get_object_or_404(HonorarContract, pk=pk, company=company)

    if request.method != 'POST':
        return redirect('honorari:contract_detail', pk=pk)

    try:
        gross = Decimal(request.POST.get('gross_amount', str(contract.gross_amount)).replace(',', '.'))
        surtax_rate = Decimal(request.POST.get('surtax_rate', '0').replace(',', '.'))

        calc = HonorarCalculation(
            contract=contract,
            calculation_date=request.POST.get('calculation_date', str(timezone.now().date())),
            gross_amount=gross,
            surtax_rate=surtax_rate,
        )
        calc.calculate()
        calc.save()

        # Automatski kreiraj JOPPD stavku
        joppd_oznaka_map = {
            'ugovor_djelo': '4002',
            'autorski': '4080',
            'studentski': '4091',
            'clanarina_uprave': '4002',
        }
        oib = ''
        if contract.contractor:
            oib = getattr(contract.contractor, 'oib', '') or ''

        HonorarJOPPD.objects.create(
            calculation=calc,
            joppd_date=calc.calculation_date,
            joppd_oznaka=joppd_oznaka_map.get(contract.contract_type, '4002'),
            oib_primatelja=oib,
            bruto=calc.gross_amount,
            porez=calc.income_tax,
            prirez=calc.surtax_amount,
            mio1=calc.pension_mio1,
            zo=calc.health_insurance,
            neto=calc.net_amount,
        )

        messages.success(request, f'Obračun kreiran. Neto: {calc.net_amount} EUR')
    except Exception as e:
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    return redirect('honorari:contract_detail', pk=pk)


# ═══════════════════════════════════════════════════
#  PROKNJIŽAVANJE OBRAČUNA
# ═══════════════════════════════════════════════════
@login_required
def calculation_post(request, calc_id):
    """Proknjiži obračun u konto — kreira JournalEntry."""
    company = _get_company(request)

    calc = get_object_or_404(HonorarCalculation, pk=calc_id)
    contract = calc.contract
    if contract.company != company:
        messages.error(request, _('Nemate pristup ovom obračunu.'))
        return redirect('honorari:contract_list')

    if calc.is_posted:
        messages.warning(request, _('Obračun je već proknjižen.'))
        return redirect('honorari:contract_detail', pk=contract.pk)

    if request.method != 'POST':
        return redirect('honorari:contract_detail', pk=contract.pk)

    try:
        from konto.models import JournalEntry, LedgerLine, KontoAccount
        from konto import services

        with transaction.atomic():
            je = JournalEntry.objects.create(
                company=company,
                entry_number=services._next_entry_number(company, 'HON'),
                date=calc.calculation_date,
                description=f'Honorar: {contract.contract_number} — {contract.get_contract_type_display()}',
                source_type='manual',
                is_posted=True,
                created_by=request.user,
            )

            # Trošak honorara (duguje) — konto 4291 ili slično
            expense_account = KontoAccount.objects.filter(
                company=company, code__startswith='429', is_active=True
            ).first()
            if not expense_account:
                expense_account = KontoAccount.objects.filter(
                    company=company, account_type='expense', is_active=True
                ).first()

            if expense_account:
                LedgerLine.objects.create(
                    journal_entry=je,
                    account=expense_account,
                    side='debit',
                    amount=calc.gross_amount,
                    description=f'Bruto honorar — {contract.contract_number}',
                )

            # Obveza za neto isplatu (potražuje) — konto 2490
            payable_account = KontoAccount.objects.filter(
                company=company, code__startswith='249', is_active=True
            ).first()
            if not payable_account:
                payable_account = KontoAccount.objects.filter(
                    company=company, account_type='liability', is_active=True
                ).first()

            if payable_account and calc.net_amount > 0:
                LedgerLine.objects.create(
                    journal_entry=je,
                    account=payable_account,
                    side='credit',
                    amount=calc.net_amount,
                    description=f'Neto honorar — {contract.contract_number}',
                )

            # Porez na dohodak (potražuje) — konto 2400
            if calc.income_tax > 0:
                tax_account = KontoAccount.objects.filter(
                    company=company, code__startswith='240', is_active=True
                ).first()
                if tax_account:
                    LedgerLine.objects.create(
                        journal_entry=je,
                        account=tax_account,
                        side='credit',
                        amount=calc.income_tax,
                        description='Porez na dohodak — honorar',
                    )

            # Prirez (potražuje)
            if calc.surtax_amount > 0:
                surtax_account = KontoAccount.objects.filter(
                    company=company, code__startswith='241', is_active=True
                ).first()
                if surtax_account:
                    LedgerLine.objects.create(
                        journal_entry=je,
                        account=surtax_account,
                        side='credit',
                        amount=calc.surtax_amount,
                        description='Prirez — honorar',
                    )

            # ZO doprinos (potražuje)
            if calc.health_insurance > 0:
                zo_account = KontoAccount.objects.filter(
                    company=company, code__startswith='242', is_active=True
                ).first()
                if zo_account:
                    LedgerLine.objects.create(
                        journal_entry=je,
                        account=zo_account,
                        side='credit',
                        amount=calc.health_insurance,
                        description='ZO doprinos — honorar',
                    )

            # MIO I. stup (potražuje)
            if calc.pension_mio1 > 0:
                mio_account = KontoAccount.objects.filter(
                    company=company, code__startswith='243', is_active=True
                ).first()
                if mio_account:
                    LedgerLine.objects.create(
                        journal_entry=je,
                        account=mio_account,
                        side='credit',
                        amount=calc.pension_mio1,
                        description='MIO I. stup — honorar',
                    )

            calc.journal_entry = je
            calc.is_posted = True
            calc.save(update_fields=['journal_entry', 'is_posted'])

        messages.success(request, f'Obračun proknjižen — temeljnica {je.entry_number}')
    except Exception as e:
        messages.error(request, _('Knjiženje nije uspjelo. Provjerite konto i iznos.'))

    return redirect('honorari:contract_detail', pk=contract.pk)


# ═══════════════════════════════════════════════════
#  JOPPD PREGLED
# ═══════════════════════════════════════════════════
@login_required
def joppd_preview(request):
    """Pregled JOPPD stavki za mjesec — za slanje Poreznoj."""
    company = _get_company(request)
    if not company:
        messages.warning(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # Dohvati JOPPD stavke za odabrani mjesec
    from django.db.models.functions import ExtractYear, ExtractMonth
    items = HonorarJOPPD.objects.filter(
        calculation__contract__company=company,
        joppd_date__year=year,
        joppd_date__month=month,
    ).select_related('calculation__contract__contractor').order_by('joppd_date')

    totals = items.aggregate(
        total_bruto=Sum('bruto'),
        total_porez=Sum('porez'),
        total_prirez=Sum('prirez'),
        total_mio1=Sum('mio1'),
        total_zo=Sum('zo'),
        total_neto=Sum('neto'),
    )

    import calendar
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = list(range(today.year - 3, today.year + 1))

    ctx = {
        'items': items,
        'totals': totals,
        'year': year,
        'month': month,
        'months': months,
        'years': years,
    }
    return render(request, 'honorari/joppd_preview.html', ctx)
