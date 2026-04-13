"""
konto/views_bank.py
Bank dashboard — account management, multi-format statement upload, reconciliation.
Supported formats: camt.053 XML (SEPA), CSV (FINA/HR banke), MT940 (SWIFT).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from core.company_utils import get_user_company
from django.db import DatabaseError


@login_required
def bank_dashboard(request):
    """Bank accounts + recent transactions + reconciliation status."""
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from konto.models import BankAccount, BankTransaction

    accounts = BankAccount.objects.filter(company=company).select_related("company", "konto_account")
    transactions = BankTransaction.objects.filter(company=company).select_related("bank_account", "company", "matched_invoice").order_by('-transaction_date')[:50]

    stats = {
        'accounts': accounts.count(),
        'total_balance': sum(a.current_balance for a in accounts),
        'unmatched': BankTransaction.objects.filter(company=company, status='unmatched').select_related("bank_account", "company", "matched_invoice").count(),
        'matched': BankTransaction.objects.filter(company=company, status='matched').select_related("bank_account", "company", "matched_invoice").count(),
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
            messages.error(request, _('IBAN i naziv su obavezni.'))
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
    """
    Upload bank statement — auto-detect format:
      .xml  → camt.053 (SEPA ISO 20022)
      .csv  → FINA CSV (PBZ, ZABA, RBA)
      .sta / .mt940 / .s940 → MT940 (SWIFT)
    """
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from konto.models import BankAccount

    if request.method == 'POST':
        uploaded_file = request.FILES.get('statement_file') or request.FILES.get('xml_file')
        account_id = request.POST.get('account_id')

        if not uploaded_file:
            messages.error(request, _('Odaberite datoteku bankovnog izvoda.'))
            return redirect('konto:bank_upload')

        # Resolve bank account
        account = None
        if account_id:
            account = BankAccount.objects.filter(pk=account_id, company=company).select_related("company", "konto_account").first()

        # Read file content
        try:
            raw = uploaded_file.read()
            try:
                content = raw.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = raw.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = raw.decode('cp1250', errors='replace')
        except IOError as e:
            messages.error(request, _('Datoteka se ne može pročitati. Provjerite format i pokušajte ponovo.'))
            return redirect('konto:bank_upload')

        filename = uploaded_file.name.lower() if uploaded_file.name else ''

        # Detect format and parse
        try:
            from konto.parsers import parse_camt053, parse_csv_fina, parse_mt940

            fmt = _detect_format(filename, content)

            if fmt == 'camt053':
                created = parse_camt053(content, account, company)
                fmt_label = 'camt.053 XML'
            elif fmt == 'csv':
                created = parse_csv_fina(content, account, company)
                fmt_label = 'CSV'
            elif fmt == 'mt940':
                created = parse_mt940(content, account, company)
                fmt_label = 'MT940'
            else:
                messages.error(request, _('Nepoznat format datoteke. Podrzano: XML (camt.053), CSV, MT940.'))
                return redirect('konto:bank_upload')

            # Count results
            num_created = len(created)

            # Get skipped count from batch — total parsed minus created
            if num_created > 0:
                messages.success(request,
                    f'Uvezeno {num_created} transakcija iz {fmt_label} formata.')
            else:
                messages.info(request,
                    _('Nema novih transakcija za uvoz (sve vec postoje ili datoteka prazna).'))

            # Auto-reconcile after import
            try:
                from konto.services.bank_import import auto_reconcile
                recon = auto_reconcile(company)
                if recon['matched'] > 0:
                    messages.success(request,
                        f'Automatski parirano: {recon["matched"]} transakcija!')
            except ImportError as e:
                pass  # Non-critical

            # Recalculate all account balances
            for acct in BankAccount.objects.filter(company=company).select_related("company", "konto_account"):
                acct.recalculate_balance()

        except ValueError as e:
            messages.error(request, _('Neispravan format datoteke. Provjerite strukturu podataka.'))
        except DatabaseError as e:
            messages.error(request, _('Uvoz nije uspio. Provjerite format datoteke i pokušajte ponovo.'))

        return redirect('konto:bank_dashboard')

    # GET — show upload form
    accounts = BankAccount.objects.filter(company=company).select_related("company", "konto_account")
    return render(request, 'konto/bank_upload.html', {'accounts': accounts})


def _detect_format(filename, content):
    """Auto-detect bank statement format from filename extension and content."""
    content_start = content.strip()[:500]

    # By extension
    if filename.endswith('.xml'):
        return 'camt053'
    if filename.endswith('.csv'):
        return 'csv'
    if filename.endswith(('.sta', '.mt940', '.s940', '.940')):
        return 'mt940'

    # By content sniffing
    if content_start.startswith('<?xml') or content_start.startswith('<'):
        return 'camt053'
    if ':20:' in content_start and ':61:' in content_start:
        return 'mt940'
    if ';' in content_start or '\t' in content_start or ',' in content_start:
        # Heuristic: if it has recognizable date patterns, treat as CSV
        import re
        if re.search(r'\d{2}\.\d{2}\.\d{4}', content_start) or \
           re.search(r'\d{4}-\d{2}-\d{2}', content_start):
            return 'csv'

    return None


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
            messages.info(request, _('Transakcija ignorirana.'))

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
