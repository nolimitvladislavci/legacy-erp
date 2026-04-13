"""
payroll/views.py — Payroll views

Rute:
  /payroll/                → lista svih PayrollRun-ova
  /payroll/new/            → kreiraj novi run
  /payroll/<pk>/           → detalji (payslipovi, akcije)
  /payroll/<pk>/run/       → pokretanje obračuna
  /payroll/<pk>/book/      → knjiženje u konto
  /payroll/<pk>/pain001/   → download pain.001 XML
  /payroll/<pk>/datev/     → download DATEV Bewegungsdaten CSV
  /payroll/<pk>/pdf/<uid>/ → listić za radnika (legacy, bez JS)
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from core.audit_access import audit_sensitive_access, audit_bulk_access
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponse
from django.utils import timezone

from .models import PayrollRun, Payslip
from core.company_utils import get_user_company
from . import services





@login_required
def payroll_list(request):
    company = get_user_company(request)
    if not company:
        messages.warning(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    runs = PayrollRun.objects.filter(company=company).order_by('-year', '-month')
    return render(request, 'payroll/payroll_list.html', {
        'runs': runs, 'company': company})


@login_required
def payroll_new(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if request.method == 'POST':
        year  = int(request.POST.get('year', timezone.now().year))
        month = int(request.POST.get('month', timezone.now().month))
        try:
            run, created = PayrollRun.objects.get_or_create(
                company=company, year=year, month=month,
                defaults={'created_by': request.user}
            )
            if not created:
                messages.warning(request, f'Obračun za {month:02d}/{year} već postoji.')
            else:
                messages.success(request, f'Kreiran obračun za {month:02d}/{year}.')
            return redirect('payroll:detail', pk=run.pk)
        except DatabaseError as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    import datetime
    today = datetime.date.today()
    return render(request, 'payroll/payroll_new.html', {
        'default_year': today.year,
        'default_month': today.month,
        'months': range(1, 13),
        'years': range(today.year - 1, today.year + 2),
    })


@login_required
def payroll_detail(request, pk):
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    payslips = run.payslips.select_related('user').order_by(
        'user__last_name', 'user__first_name')

    from konto.models import BankAccount
    banks = BankAccount.objects.filter(company=company, is_active=True)

    return render(request, 'payroll/payroll_detail.html', {
        'run': run, 'payslips': payslips, 'banks': banks,
        'can_run': run.status == 'DRAFT',
        'can_book': run.status == 'FINALIZED',
        'can_pay': run.status == 'FINALIZED',
        'is_de': getattr(company, 'country', 'HR') == 'DE',
    })


@login_required
def payroll_run_action(request, pk):
    """Pokretanje obračuna (POST)."""
    if request.method != 'POST':
        return redirect('payroll:detail', pk=pk)
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    try:
        payslips = services.run_payroll(run)
        run.refresh_from_db()
        messages.success(
            request,
            f'Obračun završen: {len(payslips)} radnika | '
            f'Bruto: {run.total_gross}€ | Neto: {run.total_net}€'
        )
    except TypeError as e:
        messages.error(request, _('Obračun nije uspio. Provjerite podatke i pokušajte ponovo.'))
    return redirect('payroll:detail', pk=pk)


@login_required
def payroll_book_action(request, pk):
    """Knjiženje u konto (POST)."""
    if request.method != 'POST':
        return redirect('payroll:detail', pk=pk)
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    try:
        entry = services.book_payroll_to_ledger(run, user=request.user)
        messages.success(request,
            f'Proknjiženo: {entry.entry_number} | '
            f'Konto 4000 ← {run.total_gross}€')
    except Exception as e:
        messages.error(request, _('Knjiženje nije uspjelo. Provjerite konto i iznos.'))
    return redirect('payroll:detail', pk=pk)


@login_required
def payroll_pain001(request, pk):
    """Download pain.001 XML za isplatu neto plaća."""
    if request.method != 'POST':
        return redirect('payroll:detail', pk=pk)
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    bank_id = request.POST.get('bank_account')

    from konto.models import BankAccount
    try:
        bank = BankAccount.objects.get(pk=bank_id, company=company)
        xml_bytes, batch_id = services.generate_pain001_from_run(run, bank)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('payroll:detail', pk=pk)
    except ObjectDoesNotExist as e:
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
        return redirect('payroll:detail', pk=pk)

    filename = f"pain001_placa_{run.month:02d}{run.year}_{batch_id}.xml"
    resp = HttpResponse(xml_bytes, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def payroll_datev_export(request, pk):
    """Download DATEV Bewegungsdaten CSV (DE kompanije)."""
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    if getattr(company, 'country', 'HR') != 'DE':
        messages.warning(request, _('DATEV export samo za DE kompanije.'))
        return redirect('payroll:detail', pk=pk)
    csv_content = services.generate_datev_bewegungsdaten(run)
    filename = f"datev_bewegung_{run.month:02d}{run.year}.csv"
    resp = HttpResponse(csv_content.encode('utf-8-sig'), content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def payslip_pdf(request, pk, user_id):
    """
    Listić za radnika — legacy HTML+PDF bez JS.
    "Koverta na ekranu" — čisti HTML za iglični pisač.
    """
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    payslip = get_object_or_404(Payslip, payroll_run=run, user_id=user_id)

    # Provjera: radnik smije vidjeti samo svoj listić
    if not request.user.is_staff and request.user.pk != payslip.user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    return render(request, 'payroll/payslip_pdf.html', {
        'run': run, 'payslip': payslip, 'company': company,
        'is_hr': getattr(company, 'country', 'HR') == 'HR',
    })


@login_required
def payroll_joppd_export(request, pk):
    """Download JOPPD XML za Poreznu upravu."""
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    payslips = run.payslips.select_related('user').all()
    if not payslips.exists():
        messages.error(request, _('Nema obracunatih placa za ovaj period.'))
        return redirect('payroll:detail', pk=pk)
    from payroll.joppd_generator import generate_joppd_xml
    xml_str = generate_joppd_xml(company, run, payslips)
    filename = f"JOPPD_{company.oib}_{run.month:02d}{run.year}.xml"
    resp = HttpResponse(xml_str, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def payroll_sepa_hr(request, pk):
    """Download SEPA pain.001.001.03 za isplatu neto placa (HR)."""
    company = get_user_company(request)
    run = get_object_or_404(PayrollRun, pk=pk, company=company)
    payslips = run.payslips.select_related('user').all()
    if not payslips.exists():
        messages.error(request, _('Nema obracunatih placa za ovaj period.'))
        return redirect('payroll:detail', pk=pk)
    if not getattr(company, 'iban', None):
        messages.error(request, _('IBAN firme nije postavljen.'))
        return redirect('payroll:detail', pk=pk)
    from payroll.sepa_generator import generate_sepa_from_payroll_run
    xml_str = generate_sepa_from_payroll_run(company, run, payslips)
    filename = f"SEPA_placa_{run.month:02d}{run.year}.xml"
    resp = HttpResponse(xml_str, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
