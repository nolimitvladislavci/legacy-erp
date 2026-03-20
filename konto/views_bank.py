"""
konto/views_bank.py
Bank dashboard — account management, statement upload, reconciliation.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from core.company_utils import get_user_company


@login_required
def bank_dashboard(request):
    """Bank accounts + recent transactions + reconciliation status."""
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from konto.models import BankAccount, BankTransaction

    accounts = BankAccount.objects.filter(company=company)
    transactions = BankTransaction.objects.filter(company=company).order_by('-transaction_date')[:50]

    stats = {
        'accounts': accounts.count(),
        'total_balance': sum(a.current_balance for a in accounts),
        'unmatched': BankTransaction.objects.filter(company=company, status='unmatched').count(),
        'matched': BankTransaction.objects.filter(company=company, status='matched').count(),
    }

    return render(request, 'konto/bank_dashboard.html', {
        'accounts': accounts,
        'transactions': transactions,
        'stats': stats,
    })


@login_required
def bank_account_create(request):
    """Create/edit bank account."""
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if request.method == 'POST':
        from konto.models import BankAccount, KontoAccount

        iban = request.POST.get('iban', '').strip().upper().replace(' ', '')
        name = request.POST.get('name', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        swift = request.POST.get('swift', '').strip().upper()
        opening = request.POST.get('opening_balance', '0').replace(',', '.')
        is_primary = request.POST.get('is_primary') == 'on'

        if not iban or not name:
            messages.error(request, 'IBAN i naziv su obavezni.')
            return redirect('konto:bank_dashboard')

        # Link to konto 1000
        konto_1000, _ = KontoAccount.objects.get_or_create(
            company=company, code='1000',
            defaults={'name': 'Ziro racun u banci', 'account_type': 'asset'}
        )

        from decimal import Decimal
        BankAccount.objects.create(
            company=company,
            name=name,
            iban=iban,
            bank_name=bank_name,
            swift=swift,
            opening_balance=Decimal(opening or '0'),
            current_balance=Decimal(opening or '0'),
            is_primary=is_primary,
            konto_account=konto_1000,
        )
        messages.success(request, f'Racun {name} ({iban[-8:]}) dodan.')
        return redirect('konto:bank_dashboard')

    return render(request, 'konto/bank_account_form.html')


@login_required
def bank_upload(request):
    """Upload camt.053 XML bank statement."""
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from konto.models import BankAccount

    if request.method == 'POST':
        xml_file = request.FILES.get('xml_file')
        account_id = request.POST.get('account_id')

        if not xml_file:
            messages.error(request, 'Odaberite XML datoteku.')
            return redirect('konto:bank_upload')

        account = None
        if account_id:
            account = BankAccount.objects.filter(pk=account_id, company=company).first()

        try:
            xml_string = xml_file.read().decode('utf-8')
        except UnicodeDecodeError:
            xml_string = xml_file.read().decode('utf-8-sig', errors='replace')

        from konto.services.bank_import import import_bank_statement, parse_camt053

        try:
            # If no account selected, try to find by IBAN in XML
            if not account:
                data = parse_camt053(xml_string)
                if data['iban']:
                    account = BankAccount.objects.filter(
                        company=company, iban=data['iban']
                    ).first()
                    if not account:
                        # Auto-create account from XML
                        from konto.models import KontoAccount
                        konto, _ = KontoAccount.objects.get_or_create(
                            company=company, code='1000',
                            defaults={'name': 'Ziro racun', 'account_type': 'asset'}
                        )
                        account = BankAccount.objects.create(
                            company=company,
                            name=f'Racun {data["iban"][-8:]}',
                            iban=data['iban'],
                            bank_name='',
                            konto_account=konto,
                            current_balance=data.get('balance', 0),
                        )
                        messages.info(request, f'Automatski kreiran racun: {data["iban"]}')

            result = import_bank_statement(company, account, xml_string)
            messages.success(request,
                f'Uvezeno {result["created"]} transakcija, {result["skipped"]} preskoceno.')

            # Auto-reconcile
            from konto.services.bank_import import auto_reconcile
            recon = auto_reconcile(company)
            if recon['matched'] > 0:
                messages.success(request, f'Automatski parirano: {recon["matched"]} transakcija!')

        except ValueError as e:
            messages.error(request, f'Greska u XML-u: {e}')
        except Exception as e:
            messages.error(request, f'Greska: {e}')

        return redirect('konto:bank_dashboard')

    accounts = BankAccount.objects.filter(company=company)
    return render(request, 'konto/bank_upload.html', {'accounts': accounts})


@login_required
def bank_reconcile(request, pk):
    """Manual reconciliation — match transaction to invoice."""
    company = get_user_company(request)
    from konto.models import BankTransaction
    from invoicing.models import Invoice

    tx = get_object_or_404(BankTransaction, pk=pk, company=company)

    if request.method == 'POST':
        invoice_id = request.POST.get('invoice_id')
        action = request.POST.get('action', 'match')

        if action == 'match' and invoice_id:
            invoice = get_object_or_404(Invoice, pk=invoice_id, company=company)
            tx.matched_invoice = invoice
            tx.status = 'matched'
            tx.save(update_fields=['matched_invoice', 'status'])
            invoice.status = 'PAID'
            invoice.save(update_fields=['status'])
            messages.success(request, f'Transakcija parirana s {invoice.number}')
        elif action == 'ignore':
            tx.status = 'ignored'
            tx.save(update_fields=['status'])
            messages.info(request, 'Transakcija ignorirana.')

        return redirect('konto:bank_dashboard')

    # Suggest matches
    suggestions = []
    if tx.transaction_type == 'inflow':
        open_inv = Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'CONFIRMED', 'FISCALIZED', 'UNPAID', 'OVERDUE'],
        ).order_by('-date_issued')[:20]

        for inv in open_inv:
            score = 0
            if inv.total == tx.amount:
                score += 50
            if tx.reference_number and tx.reference_number in (inv.number or ''):
                score += 40
            if tx.counterparty_name and inv.client_name:
                if tx.counterparty_name.upper()[:10] in inv.client_name.upper():
                    score += 30
            if score > 0:
                suggestions.append({'invoice': inv, 'score': score})

        suggestions.sort(key=lambda x: -x['score'])

    return render(request, 'konto/bank_reconcile.html', {
        'tx': tx,
        'suggestions': suggestions[:10],
    })


@login_required
def bank_auto_reconcile(request):
    """Run auto-reconciliation."""
    company = get_user_company(request)
    from konto.services.bank_import import auto_reconcile
    result = auto_reconcile(company)
    messages.success(request,
        f'Parirano: {result["matched"]}, preostalo: {result["remaining"]}')
    return redirect('konto:bank_dashboard')
