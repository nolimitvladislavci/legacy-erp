"""
Konto (Accounting) Views
- Dashboard with stats
- Chart of accounts (CRUD)
- Bank accounts (CRUD)
- Bank transactions (list, import, matching)
- Journal entries (list, create manual)
- Reports (P&L, Balance Sheet)
- API endpoints for AJAX
"""
import json
import datetime
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils.translation import gettext_lazy as _
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    KontoAccount, BankAccount, BankTransaction,
    JournalEntry, LedgerLine, AccountType,
)
from . import services
from core.audit_access import audit_sensitive_access, audit_bulk_access


def _get_company(request):
    """Get active company for current user."""
    company = getattr(request, 'impersonated_company', None)
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass
    # No fallback to Company.objects.first() — prevents cross-company data leakage
    return company  # May be None; callers must guard


# ═══════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════
@login_required
def dashboard(request):
    """Konto dashboard with key financial stats."""
    company = _get_company(request)
    if not company:
        from django.contrib import messages
        messages.warning(request, 'Nema aktivne tvrtke. Obratite se administratoru.')
        return redirect('dashboard')
    today = timezone.now().date()
    year_start = datetime.date(today.year, 1, 1)

    # Bank balances
    bank_accounts = BankAccount.objects.filter(company=company, is_active=True)
    total_bank = bank_accounts.aggregate(t=Sum('current_balance'))['t'] or Decimal('0')

    # Transaction stats this month
    month_start = today.replace(day=1)
    month_txns = BankTransaction.objects.filter(
        company=company, transaction_date__gte=month_start)
    month_inflow = month_txns.filter(
        transaction_type='inflow').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    month_outflow = month_txns.filter(
        transaction_type='outflow').aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Unmatched transactions
    unmatched_count = BankTransaction.objects.filter(
        company=company, status='unmatched').count()

    # P&L summary YTD
    pnl = services.get_profit_loss(company, year_start, today)

    # Open receivables/payables
    receivables = services.get_open_receivables(company)
    total_receivable = sum(r['remaining'] for r in receivables)
    overdue_receivables = [r for r in receivables if r['days_overdue'] > 0]

    # Recent journal entries
    recent_entries = JournalEntry.objects.filter(
        company=company).select_related('source_invoice')[:10]

    # Fiscal stats
    from invoicing.models import Invoice as Inv
    try:
        from invoicing.fiscal_models import FiscalCertificate
        cert = FiscalCertificate.objects.filter(company=company, is_active=True).first()
    except Exception:
        cert = None

    country = getattr(company, 'country', 'HR') or 'HR'
    unfiscalized_count = 0
    if country == 'HR':
        unfiscalized_count = Inv.objects.filter(
            company=company, jir__isnull=True,
            status__in=['SENT', 'PAID', 'UNPAID']
        ).count()

    gobd_report = None
    if country == 'DE':
        try:
            from invoicing.gobd_compliance import get_gobd_report
            gobd_report = get_gobd_report(company, year=today.year)
        except Exception:
            gobd_report = None

    fiscal_stats = {
        'unfiscalized_count':  unfiscalized_count,
        'cert_valid':          getattr(cert, 'is_valid', False) if cert else False,
        'cert_expiring_soon':  getattr(cert, 'is_expiring_soon', False) if cert else False,
        'days_until_expiry':   getattr(cert, 'days_until_expiry', None) if cert else None,
        'country':             country,
    }

    ctx = {
        'company': company,
        'bank_accounts': bank_accounts,
        'total_bank': total_bank,
        'month_inflow': month_inflow,
        'month_outflow': month_outflow,
        'unmatched_count': unmatched_count,
        'pnl': pnl,
        'total_receivable': total_receivable,
        'overdue_count': len(overdue_receivables),
        'recent_entries': recent_entries,
        'fiscal_stats': fiscal_stats,
        'gobd_report': gobd_report,
# Audit hash chain status    from konto.integrity import verify_chain    from konto.models import LedgerLine as LL    _hashed = LL.objects.filter(journal_entry__company=company, integrity_hash__gt='').count()    _valid, _ = verify_chain(company) if _hashed > 0 else (True, None)    ctx['audit_hashed'] = _hashed    ctx['audit_valid'] = _valid
    }
    return render(request, 'konto/dashboard.html', ctx)


# ═══════════════════════════════════════════════════
#  KONTNI PLAN (Chart of Accounts)
# ═══════════════════════════════════════════════════
@login_required
def chart_of_accounts(request):
    """List all accounts in the chart."""
    company = _get_company(request)
    acct_type = request.GET.get('type', '')
    q = request.GET.get('q', '')

    accounts = KontoAccount.objects.filter(company=company)
    if acct_type:
        accounts = accounts.filter(account_type=acct_type)
    if q:
        accounts = accounts.filter(Q(code__icontains=q) | Q(name__icontains=q))

    # Calculate balances
    account_list = []
    for acct in accounts:
        account_list.append({
            'obj': acct,
            'balance': acct.balance,
        })

    ctx = {
        'accounts': account_list,
        'account_types': AccountType.choices,
        'current_type': acct_type,
        'search_q': q,
    }
    return render(request, 'konto/chart_of_accounts.html', ctx)


@login_required
def account_detail(request, pk):
    """View account ledger (all entries)."""
    company = _get_company(request)
    account = get_object_or_404(KontoAccount, pk=pk, company=company)
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    entries = LedgerLine.objects.filter(
        account=account
    ).select_related('journal_entry').order_by('-journal_entry__date', '-id')

    if date_from:
        try:
            entries = entries.filter(journal_entry__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            entries = entries.filter(journal_entry__date__lte=date_to)
        except Exception:
            pass

    ctx = {
        'account': account,
        'entries': entries[:200],
        'balance': account.balance,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'konto/account_detail.html', ctx)


@login_required
def account_save(request):
    """Create or update a konto account."""
    if request.method != 'POST':
        return redirect('konto:chart_of_accounts')

    company = _get_company(request)
    if not company:
        return redirect('dashboard')
    pk = request.POST.get('pk')

    if pk:
        acct = get_object_or_404(KontoAccount, pk=pk, company=company)
    else:
        acct = KontoAccount(company=company)

    acct.code = request.POST.get('code', '').strip()
    acct.name = request.POST.get('name', '').strip()
    acct.account_type = request.POST.get('account_type', 'asset')
    acct.description = request.POST.get('description', '')
    acct.is_active = request.POST.get('is_active') == 'on'

    parent_id = request.POST.get('parent')
    if parent_id:
        try:
            acct.parent = KontoAccount.objects.get(pk=parent_id, company=company)
        except KontoAccount.DoesNotExist:
            acct.parent = None
    else:
        acct.parent = None

    acct.save()
    return redirect('konto:chart_of_accounts')


# ═══════════════════════════════════════════════════
#  ŽIRO RAČUNI (Bank Accounts)
# ═══════════════════════════════════════════════════
@login_required
def bank_accounts(request):
    """List bank accounts."""
    company = _get_company(request)
    accounts = BankAccount.objects.filter(company=company)
    for ba in accounts:
        ba.recalculate_balance()
    ctx = {'bank_accounts': accounts}
    return render(request, 'konto/bank_accounts.html', ctx)


@login_required
def bank_account_save(request):
    """Create or update bank account."""
    if request.method != 'POST':
        return redirect('konto:bank_accounts')

    company = _get_company(request)
    if not company:
        return redirect('dashboard')
    pk = request.POST.get('pk')

    if pk:
        ba = get_object_or_404(BankAccount, pk=pk, company=company)
    else:
        ba = BankAccount(company=company)

    ba.name = request.POST.get('name', '').strip()
    ba.iban = request.POST.get('iban', '').strip().upper()
    ba.bank_name = request.POST.get('bank_name', '').strip()
    ba.swift = request.POST.get('swift', '').strip()
    ba.currency = request.POST.get('currency', 'EUR')
    ba.is_primary = request.POST.get('is_primary') == 'on'

    try:
        ba.opening_balance = Decimal(request.POST.get('opening_balance', '0').replace(',', '.'))
    except (InvalidOperation, ValueError):
        ba.opening_balance = Decimal('0')

    konto_id = request.POST.get('konto_account')
    if konto_id:
        try:
            ba.konto_account = KontoAccount.objects.get(pk=konto_id, company=company)
        except KontoAccount.DoesNotExist:
            pass
    else:
        ba.konto_account = None

    ba.save()
    ba.recalculate_balance()
    return redirect('konto:bank_accounts')


# ═══════════════════════════════════════════════════
#  BANKOVNE TRANSAKCIJE
# ═══════════════════════════════════════════════════
@login_required
def transactions(request):
    """List bank transactions with filters."""
    company = _get_company(request)
    bank_id = request.GET.get('bank', '')
    status = request.GET.get('status', '')
    txn_type = request.GET.get('type', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    q = request.GET.get('q', '')

    qs = BankTransaction.objects.filter(company=company).select_related(
        'bank_account', 'matched_invoice')

    if bank_id:
        qs = qs.filter(bank_account_id=bank_id)
    if status:
        qs = qs.filter(status=status)
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)
    if date_from:
        try:
            qs = qs.filter(transaction_date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            qs = qs.filter(transaction_date__lte=date_to)
        except Exception:
            pass
    if q:
        qs = qs.filter(
            Q(counterparty_name__icontains=q) |
            Q(description__icontains=q) |
            Q(reference_number__icontains=q))

    # Stats
    total_in = qs.filter(transaction_type='inflow').aggregate(t=Sum('amount'))['t'] or 0
    total_out = qs.filter(transaction_type='outflow').aggregate(t=Sum('amount'))['t'] or 0

    banks = BankAccount.objects.filter(company=company, is_active=True)

    ctx = {
        'transactions': qs[:500],
        'banks': banks,
        'total_in': total_in,
        'total_out': total_out,
        'current_bank': bank_id,
        'current_status': status,
        'current_type': txn_type,
        'date_from': date_from,
        'date_to': date_to,
        'search_q': q,
    }
    return render(request, 'konto/transactions.html', ctx)


# ═══════════════════════════════════════════════════
#  TEMELJNICE (Journal Entries)
# ═══════════════════════════════════════════════════
@login_required
def journal_entries(request):
    """List journal entries."""
    company = _get_company(request)
    source = request.GET.get('source', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    qs = JournalEntry.objects.filter(company=company).select_related(
        'source_invoice', 'created_by')

    if source:
        qs = qs.filter(source_type=source)
    if date_from:
        try:
            qs = qs.filter(date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            qs = qs.filter(date__lte=date_to)
        except Exception:
            pass

    ctx = {
        'entries': qs[:500],
        'current_source': source,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'konto/journal_entries.html', ctx)


@login_required
def journal_entry_detail(request, pk):
    """View a single journal entry with all lines."""
    company = _get_company(request)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    lines = entry.lines.select_related('account').order_by('side', 'id')
    ctx = {
        'entry': entry,
        'lines': lines,
    }
    return render(request, 'konto/journal_entry_detail.html', ctx)


@login_required
def journal_entry_create(request):
    """Create a manual journal entry."""
    if request.method != 'POST':
        company = _get_company(request)
        if not company:
            return redirect('dashboard')
        accounts = KontoAccount.objects.filter(company=company, is_active=True)
        ctx = {'accounts': accounts}
        return render(request, 'konto/journal_entry_form.html', ctx)

    company = _get_company(request)
    if not company:
        return redirect('dashboard')
    description = request.POST.get('description', '').strip()
    date_str = request.POST.get('date', '')

    try:
        entry_date = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        entry_date = timezone.now().date()

    try:
        with transaction.atomic():
            je = JournalEntry.objects.create(
                company=company,
                entry_number=services._next_entry_number(company, 'MAN'),
                date=entry_date,
                description=description,
                source_type='manual',
                is_posted=True,
                created_by=request.user,
            )

            # Process lines
            accounts_list = request.POST.getlist('line_account[]')
            sides = request.POST.getlist('line_side[]')
            amounts = request.POST.getlist('line_amount[]')
            descs = request.POST.getlist('line_desc[]')

            for i, acct_id in enumerate(accounts_list):
                if not acct_id:
                    continue
                try:
                    acct = KontoAccount.objects.get(pk=acct_id, company=company)
                    amount = Decimal(amounts[i].replace(',', '.')) if i < len(amounts) else Decimal('0')
                    side = sides[i] if i < len(sides) else 'debit'
                    desc = descs[i] if i < len(descs) else ''
                    if amount > 0:
                        LedgerLine.objects.create(
                            journal_entry=je,
                            account=acct,
                            side=side,
                            amount=amount,
                            description=desc,
                        )
                except (KontoAccount.DoesNotExist, InvalidOperation, IndexError, ValueError):
                    continue

    except IntegrityError as e:
        from .services import parse_integrity_error
        error_msg = parse_integrity_error(e)
        accounts = KontoAccount.objects.filter(company=company, is_active=True)
        return render(request, 'konto/journal_entry_form.html', {
            'accounts': accounts,
            'error': error_msg,
            'form_data': request.POST,
        })

    return redirect('konto:journal_entry_detail', pk=je.pk)


# ═══════════════════════════════════════════════════
#  IZVJEŠTAJI (Reports)
# ═══════════════════════════════════════════════════
@login_required
def report_profit_loss(request):
    """Profit & Loss report."""
    company = _get_company(request)
    today = timezone.now().date()
    date_from = request.GET.get('from', str(datetime.date(today.year, 1, 1)))
    date_to = request.GET.get('to', str(today))

    try:
        df = datetime.date.fromisoformat(date_from)
        dt = datetime.date.fromisoformat(date_to)
    except ValueError:
        df = datetime.date(today.year, 1, 1)
        dt = today

    pnl = services.get_profit_loss(company, df, dt)
    ctx = {
        'report': pnl,
        'date_from': str(df),
        'date_to': str(dt),
    }
    return render(request, 'konto/report_pnl.html', ctx)


@login_required
def report_balance_sheet(request):
    """Balance sheet report."""
    company = _get_company(request)
    today = timezone.now().date()
    date_str = request.GET.get('date', str(today))

    try:
        report_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        report_date = today

    bs = services.get_balance_sheet(company, report_date)
    ctx = {
        'report': bs,
        'report_date': str(report_date),
    }
    return render(request, 'konto/report_balance_sheet.html', ctx)


@login_required
def report_receivables(request):
    """Open receivables (saldakonti kupaca)."""
    company = _get_company(request)
    receivables = services.get_open_receivables(company)
    total = sum(r['remaining'] for r in receivables)
    ctx = {
        'receivables': receivables,
        'total': total,
    }
    return render(request, 'konto/report_receivables.html', ctx)


# ═══════════════════════════════════════════════════
#  API ENDPOINTS (AJAX)
# ═══════════════════════════════════════════════════
@login_required
def api_auto_match(request):
    """POST: Auto-match unmatched transactions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    matched = services.auto_match_transactions(company)
    return JsonResponse({
        'success': True,
        'matched_count': len(matched),
        'matches': [
            {
                'transaction_id': txn.pk,
                'invoice_number': inv.number,
                'amount': float(txn.amount),
                'score': score,
            }
            for txn, inv, score in matched
        ],
    })


@login_required
def api_match_transaction(request, pk):
    """POST: Manually match a transaction to an invoice."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    txn = get_object_or_404(BankTransaction, pk=pk, company=company)
    data = json.loads(request.body)
    invoice_id = data.get('invoice_id')

    if not invoice_id:
        return JsonResponse({'error': 'invoice_id required'}, status=400)

    from invoicing.models import Invoice
    invoice = get_object_or_404(Invoice, pk=invoice_id, company=company)
    result = services.match_transaction_to_invoice(txn, invoice)

    return JsonResponse({'success': result})


@login_required
def api_book_invoice(request, pk):
    """POST: Book an invoice into the ledger."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    from invoicing.models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    try:
        je = services.book_invoice(invoice, request.user)
    except IntegrityError as e:
        return JsonResponse({
            'status': 'error',
            'message': services.parse_integrity_error(e),
        }, status=400)

    if je:
        return JsonResponse({
            'success': True,
            'journal_entry_id': je.pk,
            'entry_number': je.entry_number,
            'is_balanced': je.is_balanced,
        })
    return JsonResponse({'success': False, 'reason': 'Already booked or zero total'})


@login_required
def api_book_transactions(request):
    """POST: Book selected transactions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    data = json.loads(request.body)
    ids = data.get('transaction_ids', [])
    qs = BankTransaction.objects.filter(pk__in=ids, is_booked=False, company=company)
    try:
        entries = services.book_bank_transactions(qs, request.user)
    except IntegrityError as e:
        return JsonResponse({
            'status': 'error',
            'message': services.parse_integrity_error(e),
        }, status=400)

    return JsonResponse({
        'success': True,
        'booked_count': len(entries),
    })


@login_required
def api_ignore_transaction(request, pk):
    """POST: Mark transaction as ignored."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    txn = get_object_or_404(BankTransaction, pk=pk)
    txn.status = 'ignored'
    txn.save(update_fields=['status'])
    return JsonResponse({'success': True})


@login_required
def api_transaction_create(request):
    """POST: Manually create a bank transaction."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne firme'}, status=403)
    data = json.loads(request.body)

    bank_id = data.get('bank_account_id')
    ba = get_object_or_404(BankAccount, pk=bank_id, company=company)

    try:
        txn_date = datetime.date.fromisoformat(data.get('date', ''))
    except (ValueError, TypeError):
        txn_date = timezone.now().date()

    try:
        amount = Decimal(str(data.get('amount', 0)))
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'Invalid amount'}, status=400)

    txn = BankTransaction.objects.create(
        bank_account=ba,
        company=company,
        transaction_date=txn_date,
        value_date=txn_date,
        amount=abs(amount),
        transaction_type=data.get('type', 'inflow'),
        counterparty_name=data.get('counterparty', ''),
        counterparty_iban=data.get('counterparty_iban', ''),
        description=data.get('description', ''),
        reference_number=data.get('reference', ''),
    )

    ba.recalculate_balance()

    return JsonResponse({
        'success': True,
        'id': txn.pk,
    })


@login_required
def api_chart_data(request):
    """GET: Return chart of accounts with balances as JSON."""
    company = _get_company(request)
    acct_type = request.GET.get('type', '')

    accounts = KontoAccount.objects.filter(company=company, is_active=True)
    if acct_type:
        accounts = accounts.filter(account_type=acct_type)

    data = []
    for acct in accounts:
        data.append({
            'id': acct.pk,
            'code': acct.code,
            'name': acct.name,
            'type': acct.account_type,
            'balance': float(acct.balance),
        })

    return JsonResponse({'accounts': data})


@login_required
def api_unmatched_invoices(request):
    """GET: Return unpaid invoices for matching UI."""
    from invoicing.models import Invoice
    company = _get_company(request)
    invoices = Invoice.objects.filter(
        company=company, status__in=['SENT', 'UNPAID', 'OVERDUE']
    ).order_by('-date_issued')[:100]

    data = [{
        'id': inv.pk,
        'number': inv.number,
        'client': inv.client_name,
        'total': float(inv.total or 0),
        'date': str(inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued),
        'status': inv.status,
    } for inv in invoices]

    return JsonResponse({'invoices': data})


# ═══════════════════════════════════════════════════════════════════════
#  TAX / PDV REPORTS
# ═══════════════════════════════════════════════════════════════════════



@login_required
def tax_dashboard(request):
    """Batch tax dashboard — all companies at a glance (Marijin kokpit)."""
    from .models import TaxPeriod
    from companies.models import Company
    from limit_connect_ai.models_knowledge_graph import SupplierRiskAlert

    # Filters
    pdv_filter = request.GET.get('pdv_status', '')
    btype_filter = request.GET.get('business_type', '')

    companies = Company.objects.all().order_by('name')
    if pdv_filter:
        companies = companies.filter(pdv_status=pdv_filter)
    if btype_filter:
        companies = companies.filter(business_type=btype_filter)

    today = timezone.now().date()
    rows = []
    totals = {'obveza': Decimal('0'), 'prihod': Decimal('0'), 'alerts': 0}

    for c in companies:
        # Latest TaxPeriod
        latest = TaxPeriod.objects.filter(company=c).order_by('-year', '-month').first()

        # Risk alerts count
        alert_count = SupplierRiskAlert.objects.filter(
            company=c, risk_level__in=['HIGH', 'CRITICAL'], is_acknowledged=False
        ).count()

        row = {
            'company': c,
            'pdv_status': c.pdv_status,
            'business_type': c.get_business_type_display() if hasattr(c, 'get_business_type_display') else c.business_type,
            'latest_period': f"{latest.month:02d}/{latest.year}" if latest and latest.month else None,
            'is_filed': latest.is_filed if latest else None,
            'vat_payable': latest.vat_payable if latest else Decimal('0'),
            'total_revenue': latest.total_revenue if latest else Decimal('0'),
            'alert_count': alert_count,
        }
        rows.append(row)

        if latest:
            totals['obveza'] += latest.vat_payable or Decimal('0')
            totals['prihod'] += latest.total_revenue or Decimal('0')
        totals['alerts'] += alert_count

    ctx = {
        'rows': rows,
        'totals': totals,
        'pdv_filter': pdv_filter,
        'btype_filter': btype_filter,
        'pdv_choices': [('', 'Sve'), ('obveznik', 'Obveznik'), ('pausalic', 'Paušalac'), ('none', 'Nije u PDV-u')],
        'btype_choices': [('', 'Sve'), ('doo', 'd.o.o.'), ('obrt', 'Obrt'), ('udruga', 'Udruga'), ('jdoo', 'j.d.o.o.'), ('gmbh', 'GmbH')],
        'company_count': companies.count(),
    }
    return render(request, 'konto/tax_dashboard.html', ctx)


@login_required
def report_vat(request):
    """VAT/PDV period report — USt-Voranmeldung / PDV obrazac."""
    import calendar
    from .models import TaxPeriod
    company = _get_company(request)
    today = timezone.now().date()

    period_type = request.GET.get('period_type', 'monthly')
    year  = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month)) if period_type == 'monthly' else None
    quarter = int(request.GET.get('quarter', (today.month - 1) // 3 + 1)) if period_type == 'quarterly' else None

    period = None
    error  = None
    if request.method == 'POST' or request.GET.get('calc'):
        try:
            period = services.calculate_vat_period(company, period_type, year, month, quarter)
        except Exception as exc:
            error = str(exc)

    # History
    history = TaxPeriod.objects.filter(company=company).order_by('-year', '-month', '-quarter')[:24]

    months  = list(range(1, 13))
    years   = list(range(today.year - 3, today.year + 1))
    quarters = [1, 2, 3, 4]

    return render(request, 'konto/report_vat.html', {
        'period': period,
        'error': error,
        'period_type': period_type,
        'year': year,
        'month': month,
        'quarter': quarter,
        'history': history,
        'months': months,
        'years': years,
        'quarters': quarters,
        'month_choices': [(i, calendar.month_name[i]) for i in range(1, 13)],
    })


@login_required
def report_annual_tax(request):
    """Annual income tax summary (HR: dohodak, DE: Einkommensteuer)."""
    company = _get_company(request)
    today   = timezone.now().date()
    year    = int(request.GET.get('year', today.year))
    years   = list(range(today.year - 4, today.year + 1))

    summary = None
    error   = None
    if request.GET.get('calc'):
        try:
            summary = services.get_annual_tax_summary(company, year)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_annual_tax.html', {
        'summary': summary,
        'error': error,
        'year': year,
        'years': years,
        'company': company,
    })



@login_required
def report_corporate_tax(request):
    """PD — Porez na dobit (Corporate tax) for d.o.o. companies."""
    company = _get_company(request)
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year - 1))  # Default: previous year
    years = list(range(today.year - 4, today.year + 1))

    report = None
    error = None
    if request.GET.get('calc'):
        try:
            report = services.calculate_corporate_tax(company, year)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_corporate_tax.html', {
        'report': report,
        'error': error,
        'year': year,
        'years': years,
        'company': company,
    })

@login_required
def report_euer(request):
    """EÜR — Einnahmenüberschussrechnung (DE) / Jednostavno knjigovodstvo (HR)."""
    company = _get_company(request)
    today   = timezone.now().date()
    year    = int(request.GET.get('year', today.year))
    years   = list(range(today.year - 4, today.year + 1))

    report  = None
    error   = None
    if request.GET.get('calc'):
        try:
            report = services.get_euer_report(company, year)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_euer.html', {
        'report': report,
        'error': error,
        'year': year,
        'years': years,
        'company': company,
    })



# Insert after report_euer view in views.py
@login_required
def report_po_sd(request):
    """PO-SD — Paušalni obrtnici (Izvješće o paušalnom dohotku)."""
    company = _get_company(request)
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year - 1))
    years = list(range(today.year - 4, today.year + 1))

    report = None
    error = None
    if request.GET.get('calc'):
        try:
            report = services.calculate_po_sd(company, year)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_po_sd.html', {
        'report': report,
        'error': error,
        'year': year,
        'years': years,
        'company': company,
    })

@login_required
def report_vat_mark_filed(request, pk):
    """Mark a TaxPeriod as filed (POST)."""
    from .models import TaxPeriod
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    period = get_object_or_404(TaxPeriod, pk=pk, company=_get_company(request))
    period.is_filed = True
    period.filed_at = timezone.now()
    period.save(update_fields=['is_filed', 'filed_at'])
    return JsonResponse({'ok': True, 'filed_at': period.filed_at.isoformat()})


# ══════════════════════════════════════════════════════════════════════════════
# German Module: SKR 03 Seed + DATEV Export
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def datev_export(request):
    """
    GET /konto/datev-export/?start=YYYY-MM-DD&end=YYYY-MM-DD
    Returns DATEV EXTF/700 CSV file for download.
    """
    from django.http import HttpResponse
    from core.company_utils import get_user_company
    from konto.german_accounting import generate_datev_export
    import datetime

    company = get_user_company(request)
    if not company:
        return HttpResponse('Keine Firma zugeordnet.', status=400)

    if company.country != 'DE':
        return HttpResponse('DATEV-Export nur fuer deutsche Unternehmen.', status=400)

    # Date range from query params (default: current month)
    today = datetime.date.today()
    start_str = request.GET.get('start', today.replace(day=1).isoformat())
    end_str = request.GET.get('end', today.isoformat())

    try:
        start_date = datetime.date.fromisoformat(start_str)
        end_date = datetime.date.fromisoformat(end_str)
    except ValueError:
        return HttpResponse('Ungueltiges Datumsformat (YYYY-MM-DD).', status=400)

    berater_nr = request.GET.get('berater', '')
    mandanten_nr = request.GET.get('mandant', '')

    csv_content = generate_datev_export(
        company, start_date, end_date,
        berater_nr=berater_nr,
        mandanten_nr=mandanten_nr,
    )

    filename = f"EXTF_Buchungen_{company.name[:20]}_{start_date}_{end_date}.csv"
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def skr03_seed(request):
    """
    POST /konto/skr03-seed/
    Seeds SKR 03 accounts for the current company.
    """
    from django.http import JsonResponse, HttpResponse
    from core.company_utils import get_user_company
    from konto.german_accounting import seed_skr03

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Keine Firma'}, status=400)

    if company.country != 'DE':
        return JsonResponse({'error': 'SKR 03 nur fuer DE-Firmen'}, status=400)

    created, skipped = seed_skr03(company)
    return JsonResponse({
        'status': 'ok',
        'message': f'SKR 03: {created} Konten erstellt, {skipped} bereits vorhanden.',
        'created': created,
        'skipped': skipped,
    })




# ═══════════════════════════════════════════════════
#  AUDIT HASH CHAIN VERIFICATION
# ═══════════════════════════════════════════════════
@login_required
def audit_verify(request):
    """Run hash chain verification and show results."""
    company = _get_company(request)
    if not company:
        return redirect('dashboard')

    from konto.integrity import verify_chain
    from konto.models import LedgerLine
    import time

    start = time.time()
    valid, broken_at = verify_chain(company)
    elapsed = round(time.time() - start, 3)

    total_hashed = LedgerLine.objects.filter(
        journal_entry__company=company, integrity_hash__gt=''
    ).count()

    broken_line = None
    if not valid and broken_at:
        broken_line = LedgerLine.objects.select_related(
            'account', 'journal_entry'
        ).filter(pk=broken_at).first()

    last = LedgerLine.objects.filter(
        journal_entry__company=company, integrity_hash__gt=''
    ).order_by('-id').first()

    ctx = {
        'company': company,
        'valid': valid,
        'total_hashed': total_hashed,
        'elapsed': elapsed,
        'broken_line': broken_line,
        'last_hash': last.integrity_hash if last else '',
        'last_entry': last.journal_entry if last else None,
    }
    return render(request, 'konto/audit_verify.html', ctx)


@login_required
def audit_certificate_pdf(request):
    """Generate PDF certificate of hash chain integrity."""
    company = _get_company(request)
    if not company:
        return redirect('dashboard')

    from konto.integrity import verify_chain
    from konto.models import LedgerLine
    from weasyprint import HTML
    from django.template.loader import render_to_string
    import time

    start = time.time()
    valid, broken_at = verify_chain(company)
    elapsed = round(time.time() - start, 3)

    total_hashed = LedgerLine.objects.filter(
        journal_entry__company=company, integrity_hash__gt=''
    ).count()

    first_line = LedgerLine.objects.filter(
        journal_entry__company=company, integrity_hash__gt=''
    ).order_by('id').select_related('journal_entry').first()

    last_line = LedgerLine.objects.filter(
        journal_entry__company=company, integrity_hash__gt=''
    ).order_by('-id').select_related('journal_entry').first()

    now = timezone.now()

    ctx = {
        'company': company,
        'valid': valid,
        'total_hashed': total_hashed,
        'elapsed': elapsed,
        'first_hash': first_line.integrity_hash if first_line else '',
        'last_hash': last_line.integrity_hash if last_line else '',
        'first_entry': first_line.journal_entry if first_line else None,
        'last_entry': last_line.journal_entry if last_line else None,
        'generated_at': now,
        'year': now.year,
    }

    html_string = render_to_string('konto/audit_certificate_pdf.html', ctx)
    pdf = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    fname = f'Audit_Certificate_{company.name}_{now.strftime("%Y%m%d_%H%M")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ═══════════════════════════════════════════════════
#  BANKOVNA REKONCILIJACIJA — Dashboard
# ═══════════════════════════════════════════════════
@login_required
def reconciliation_dashboard(request):
    """Bank reconciliation dashboard."""
    company = _get_company(request)
    if not company:
        return redirect('dashboard')

    from invoicing.models import Invoice

    unmatched = BankTransaction.objects.filter(
        company=company, status='unmatched', transaction_type='inflow'
    ).order_by('-transaction_date')

    unpaid_invoices = Invoice.objects.filter(
        status__in=['SENT', 'UNPAID', 'OVERDUE']
    ).order_by('-date_issued')

    # Build reconciliation suggestions
    reconciliation_data = []
    for txn in unmatched:
        match_quality = 'none'
        suggested_invoice = None
        best_score = 0

        for inv in unpaid_invoices:
            score = 0
            inv_total = Decimal(str(inv.total or 0))

            # Reference match
            if txn.reference_number and inv.number:
                ref_clean = txn.reference_number.replace('-', '').replace(' ', '').upper()
                inv_clean = inv.number.replace('-', '').replace(' ', '').upper()
                if ref_clean == inv_clean or inv_clean in ref_clean:
                    score += 50

            # Amount match
            if inv_total > 0 and txn.amount == inv_total:
                score += 30

            # Name match
            if txn.counterparty_name and inv.client_name:
                if inv.client_name.lower() in txn.counterparty_name.lower():
                    score += 20

            # OIB match
            if hasattr(inv, 'client_oib') and inv.client_oib and inv.client_oib in (txn.description or ''):
                score += 25

            if score > best_score:
                best_score = score
                suggested_invoice = inv
                if score >= 50:
                    match_quality = 'high'
                elif score >= 30:
                    match_quality = 'medium'

        reconciliation_data.append({
            'transaction': txn,
            'suggested_invoice': suggested_invoice,
            'match_quality': match_quality,
            'score': best_score,
        })

    total_unmatched = unmatched.count()
    total_amount = sum(item['transaction'].amount for item in reconciliation_data)
    high_matches = sum(1 for item in reconciliation_data if item['match_quality'] == 'high')

    return render(request, 'konto/reconciliation_dashboard.html', {
        'reconciliation_data': reconciliation_data,
        'unpaid_invoices': unpaid_invoices,
        'total_unmatched': total_unmatched,
        'total_amount': total_amount,
        'high_matches': high_matches,
    })


@login_required
def api_reconcile_batch(request):
    """POST: Batch reconcile multiple transactions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = _get_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)

    data = json.loads(request.body)
    mappings = data.get('mappings', [])

    if not mappings:
        return JsonResponse({'status': 'error', 'message': 'Nema odabranih transakcija.'}, status=400)

    reconciled = 0
    errors = []

    for mapping in mappings:
        try:
            txn = BankTransaction.objects.get(
                id=mapping['transaction_id'], company=company, status='unmatched')
            from invoicing.models import Invoice
            inv = Invoice.objects.get(id=mapping['invoice_id'])
            result = services.match_transaction_to_invoice(txn, inv)
            if result:
                reconciled += 1
            else:
                errors.append('Transakcija ' + str(txn.pk) + ' vec parirana.')
        except BankTransaction.DoesNotExist:
            errors.append('Transakcija ne postoji ili nije u vasoj firmi.')
        except IntegrityError as e:
            errors.append('DB error: ' + services.parse_integrity_error(e))
        except Exception as e:
            errors.append(str(e))

    msg = 'Sravnjeno ' + str(reconciled) + ' transakcija.'
    if errors:
        msg += ' Greske: ' + str(len(errors))

    return JsonResponse({
        'status': 'success' if reconciled > 0 else 'error',
        'message': msg,
        'reconciled_count': reconciled,
        'errors': errors,
    })


# ═══════════════════════════════════════════════════
#  PERIOD LOCK MANAGEMENT
# ═══════════════════════════════════════════════════
@login_required
def period_management(request):
    """Manage accounting period locks."""
    company = _get_company(request)
    if not company:
        return redirect('dashboard')

    from .models import AccountingPeriod
    import datetime

    if request.method == 'POST':
        action = request.POST.get('action')
        year = int(request.POST.get('year', 0))
        month = int(request.POST.get('month', 0))

        if year and month:
            period, created = AccountingPeriod.objects.get_or_create(
                company=company, year=year, month=month)
            if action == 'lock':
                period.lock(request.user)
            elif action == 'unlock':
                period.unlock(request.user)

        return redirect('konto:period_management')

    # Build period list for current and past 24 months
    today = datetime.date.today()
    periods_data = []
    for i in range(24):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        try:
            period = AccountingPeriod.objects.get(company=company, year=y, month=m)
            is_locked = period.is_locked
            locked_by = period.locked_by
            locked_at = period.locked_at
        except AccountingPeriod.DoesNotExist:
            is_locked = False
            locked_by = None
            locked_at = None

        # Count entries in this period
        entry_count = JournalEntry.objects.filter(
            company=company, date__year=y, date__month=m).count()

        periods_data.append({
            'year': y, 'month': m,
            'month_name': datetime.date(y, m, 1).strftime('%B %Y'),
            'is_locked': is_locked,
            'locked_by': locked_by,
            'locked_at': locked_at,
            'entry_count': entry_count,
        })

    return render(request, 'konto/periods.html', {
        'periods': periods_data,
    })


# ═══════════════════════════════════════════════════
#  OPZ-STAT-1 — Statisticki izvjestaj za FINA
# ═══════════════════════════════════════════════════
@login_required
def report_opz_stat(request):
    """OPZ-STAT-1 report — business transaction statistics."""
    company = _get_company(request)
    if not company:
        return redirect('dashboard')

    import datetime
    from invoicing.models import Invoice
    from django.db.models import Count, Sum

    year = int(request.GET.get('year', datetime.date.today().year))
    export_csv = request.GET.get('format') == 'csv'

    # Get all invoices for the year
    invoices = Invoice.objects.filter(
        date_issued__year=year
    ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO', 'REJECTED'])

    # Try to filter by company if possible
    if hasattr(Invoice, 'company'):
        invoices = invoices.filter(company=company)

    # Group by partner (client)
    partner_stats = {}
    for inv in invoices:
        client = inv.client_name or 'Nepoznato'
        oib = getattr(inv, 'client_oib', '') or ''
        key = oib if oib else client

        if key not in partner_stats:
            partner_stats[key] = {
                'name': client,
                'oib': oib,
                'is_domestic': (len(oib) == 11 and oib.isdigit()) or not oib,
                'invoice_count': 0,
                'total_amount': Decimal('0'),
                'total_vat': Decimal('0'),
            }
        partner_stats[key]['invoice_count'] += 1
        partner_stats[key]['total_amount'] += Decimal(str(inv.total or 0))
        partner_stats[key]['total_vat'] += Decimal(str(inv.tax_amount or 0))

    # ── Aging / overdue tracking ──
    today = datetime.date.today()
    for key, ps in partner_stats.items():
        ps['overdue_count'] = 0
        ps['overdue_amount'] = Decimal('0')
    for inv in invoices:
        if inv.status not in ('PAID',) and inv.date_due and inv.date_due < today:
            oib = getattr(inv, 'client_oib', '') or ''
            client = inv.client_name or 'Nepoznato'
            key = oib if oib else client
            if key in partner_stats:
                partner_stats[key]['overdue_count'] += 1
                partner_stats[key]['overdue_amount'] += Decimal(str(inv.total or 0))

    partners = sorted(partner_stats.values(), key=lambda x: x['total_amount'], reverse=True)
    domestic = [p for p in partners if p['is_domestic']]
    foreign = [p for p in partners if not p['is_domestic']]

    totals = {
        'domestic_count': sum(p['invoice_count'] for p in domestic),
        'domestic_amount': sum(p['total_amount'] for p in domestic),
        'domestic_vat': sum(p['total_vat'] for p in domestic),
        'foreign_count': sum(p['invoice_count'] for p in foreign),
        'foreign_amount': sum(p['total_amount'] for p in foreign),
        'foreign_vat': sum(p['total_vat'] for p in foreign),
    }
    totals['overdue_count'] = sum(p['overdue_count'] for p in partners)
    totals['overdue_amount'] = sum(p['overdue_amount'] for p in partners)
    totals['grand_count'] = totals['domestic_count'] + totals['foreign_count']
    totals['grand_amount'] = totals['domestic_amount'] + totals['foreign_amount']
    totals['grand_vat'] = totals['domestic_vat'] + totals['foreign_vat']

    if export_csv:
        import csv
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="OPZ-STAT-1_{year}.csv"'
        response.write('\xef\xbb\xbf')  # BOM for Excel
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Partner', 'OIB', 'Tip', 'Broj racuna', 'Ukupan iznos', 'Ukupan PDV'])
        for p in partners:
            writer.writerow([
                p['name'], p['oib'],
                'Domaci' if p['is_domestic'] else 'Inozemni',
                p['invoice_count'],
                f"{p['total_amount']:.2f}",
                f"{p['total_vat']:.2f}",
            ])
        writer.writerow([])
        writer.writerow(['UKUPNO DOMACI', '', '', totals['domestic_count'],
                         f"{totals['domestic_amount']:.2f}", f"{totals['domestic_vat']:.2f}"])
        writer.writerow(['UKUPNO INOZEMNI', '', '', totals['foreign_count'],
                         f"{totals['foreign_amount']:.2f}", f"{totals['foreign_vat']:.2f}"])
        writer.writerow(['SVEUKUPNO', '', '', totals['grand_count'],
                         f"{totals['grand_amount']:.2f}", f"{totals['grand_vat']:.2f}"])
        return response

    return render(request, 'konto/report_opz_stat.html', {
        'year': year,
        'years': range(datetime.date.today().year, 2024, -1),
        'domestic': domestic,
        'foreign': foreign,
        'totals': totals,
    })


# ═══════════════════════════════════════════════════
#  GFI-POD EXPORT
# ═══════════════════════════════════════════════════
@login_required
def gfi_pod_export(request):
    """Generate and download GFI-POD XML for a given year."""
    company = _get_company(request)
    if not company:
        from django.contrib import messages as msg
        msg.warning(request, "Nema aktivne tvrtke.")
        return redirect("dashboard")

    year = int(request.GET.get("year", timezone.now().year - 1))

    from konto.gfi_export import generate_gfi_pod
    result = generate_gfi_pod(company, year)

    fmt = request.GET.get("format", "xml")
    if fmt == "json":
        return JsonResponse(result, json_dumps_params={"ensure_ascii": False, "indent": 2})

    # Default: XML download
    xml_str = result.get("xml", "")
    response = HttpResponse(xml_str, content_type="application/xml")
    response["Content-Disposition"] = "attachment; filename=\"GFI-POD_%s_%s.xml\"" % (company.oib, year)
    return response


# ═══════════════════════════════════════════════════════════════════════
#  GERMAN TAX MODULE
# ═══════════════════════════════════════════════════════════════════════

@login_required
def report_ustva(request):
    """UStVA — Umsatzsteuervoranmeldung (German monthly VAT return)."""
    import calendar
    company = _get_company(request)
    today = timezone.now().date()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    years = list(range(today.year - 3, today.year + 1))

    report = None
    error = None
    if request.GET.get('calc'):
        try:
            from konto.ustva_export import generate_ustva
            report = generate_ustva(company, year, month)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_ustva.html', {
        'report': report,
        'error': error,
        'year': year,
        'month': month,
        'years': years,
        'month_choices': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'company': company,
    })


@login_required
def ustva_xml_export(request, year, month):
    """Download UStVA XML for ELSTER/DATEV import."""
    company = _get_company(request)
    from konto.ustva_export import generate_ustva, generate_ustva_xml

    kz_data = generate_ustva(company, year, month)
    xml_str = generate_ustva_xml(company, year, month, kz_data)

    steuernr = (company.oib or 'unknown').replace('/', '-')
    filename = f"UStVA_{steuernr}_{month:02d}{year}.xml"
    resp = HttpResponse(xml_str, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def report_koerperschaftsteuer(request):
    """KSt — Körperschaftsteuer (German corporate tax) for GmbH/UG."""
    company = _get_company(request)
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year - 1))
    years = list(range(today.year - 4, today.year + 1))

    report = None
    error = None
    if request.GET.get('calc'):
        try:
            report = services.calculate_koerperschaftsteuer(company, year)
        except Exception as exc:
            error = str(exc)

    return render(request, 'konto/report_kst.html', {
        'report': report,
        'error': error,
        'year': year,
        'years': years,
        'company': company,
    })



# ── SAF-T HR Export ────────────────────────────────────────────────────────

@login_required
def saft_export_view(request):
    """SAF-T HR export — form za period selection + trigger generacije."""
    from konto.saft_generator import SAFTGenerator
    from django.http import HttpResponse
    from datetime import date

    if request.method == 'POST':
        period_from = request.POST.get('period_from', '')
        period_to = request.POST.get('period_to', '')

        try:
            pf = date.fromisoformat(period_from)
            pt = date.fromisoformat(period_to)
        except (ValueError, TypeError):
            from django.contrib import messages
            messages.error(request, 'Neispravan format datuma.')
            return render(request, 'konto/saft_export.html')

        gen = SAFTGenerator(request.company, pf, pt)
        xml = gen.generate()

        response = HttpResponse(xml, content_type='application/xml')
        filename = f'SAFT_{request.company.oib}_{pf}_{pt}.xml'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # BorgAuditEntry
        try:
            from borg_ops.audit_helpers import log_borg_audit
            log_borg_audit(
                company=request.company,
                entry_type='EXPORT',
                summary=f'SAF-T HR download: {pf} do {pt}',
                user=request.user,
            )
        except Exception:
            pass

        return response

    return render(request, 'konto/saft_export.html')


# ═══════════════════════════════════════════════════
#  PROFITNI CENTRI (Cost Centers)
# ══════���════════════════════════════════════════════
@login_required
def cost_centers(request):
    """Lista profitnih centara s budžetom i troškovima."""
    company = _get_company(request)
    from .models import CostCenter
    centers = CostCenter.objects.filter(company=company)
    data = []
    for cc in centers:
        data.append({
            'obj': cc,
            'expenses': cc.total_expenses,
            'income': cc.total_income,
            'remaining': cc.budget_remaining,
            'pct': (float(cc.total_expenses) / float(cc.budget_annual) * 100) if cc.budget_annual else 0,
        })
    return render(request, 'konto/cost_centers.html', {
        'centers': data,
        'company': company,
    })


@login_required
def cost_center_detail(request, pk):
    """Detalj profitnog centra — knjiženja po centru."""
    company = _get_company(request)
    from .models import CostCenter
    cc = get_object_or_404(CostCenter, pk=pk, company=company)
    lines = cc.ledger_lines.select_related(
        'journal_entry', 'account'
    ).order_by('-journal_entry__date')[:200]
    return render(request, 'konto/cost_center_detail.html', {
        'cc': cc,
        'lines': lines,
        'expenses': cc.total_expenses,
        'income': cc.total_income,
        'remaining': cc.budget_remaining,
    })


@login_required
def cost_center_save(request):
    """Create or update cost center."""
    if request.method != 'POST':
        return redirect('konto:cost_centers')
    company = _get_company(request)
    if not company:
        return redirect('dashboard')
    from .models import CostCenter
    pk = request.POST.get('pk')
    if pk:
        cc = get_object_or_404(CostCenter, pk=pk, company=company)
    else:
        cc = CostCenter(company=company)
    cc.code = request.POST.get('code', '').strip()
    cc.name = request.POST.get('name', '').strip()
    cc.description = request.POST.get('description', '')
    cc.is_active = request.POST.get('is_active') == 'on'
    try:
        cc.budget_annual = Decimal(request.POST.get('budget_annual', '0').replace(',', '.'))
    except (InvalidOperation, ValueError):
        cc.budget_annual = Decimal('0')
    parent_id = request.POST.get('parent')
    cc.parent = CostCenter.objects.filter(pk=parent_id, company=company).first() if parent_id else None
    cc.save()
    return redirect('konto:cost_centers')
