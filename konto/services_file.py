"""
Konto business logic - double-entry bookkeeping, bank reconciliation, reports.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q, F
from django.utils import timezone


def _get_or_fail(company, code):
    """Get a KontoAccount by code for a company, raise if not found."""
    from .models import KontoAccount
    try:
        return KontoAccount.objects.get(company=company, code=code)
    except KontoAccount.DoesNotExist:
        raise ValueError(f"Konto {code} ne postoji za firmu {company}")


def _next_entry_number(company, prefix='TEM'):
    """Generate next journal entry number: TEM-2026-0001"""
    from .models import JournalEntry
    year = timezone.now().year
    last = JournalEntry.objects.filter(
        company=company,
        entry_number__startswith=f"{prefix}-{year}-"
    ).order_by('-entry_number').first()
    if last:
        try:
            num = int(last.entry_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f"{prefix}-{year}-{num:04d}"


@transaction.atomic
def book_invoice(invoice, user=None):
    """Book an issued invoice into double-entry ledger.

    Izdani racun 1000€ + 250€ PDV = 1250€:
      Duguje: 1200 Potraživanja od kupaca  1250,00€
      Potražuje: 7000 Prihodi od prodaje   1000,00€
      Potražuje: 2400 Obveze za PDV         250,00€

    Primljeni racun 500€ + 95€ PDV = 595€:
      Duguje: 4000 Materijalni troškovi     500,00€
      Duguje: 1400 Pretporez                 95,00€
      Potražuje: 2200 Obveze prema dobavljačima 595,00€
    """
    from .models import KontoAccount, JournalEntry, LedgerLine

    company = invoice.invoice_profile.company if hasattr(invoice, 'invoice_profile') and invoice.invoice_profile else None
    if not company:
        # Try to find company from user or first available
        from companies.models import Company
        company = Company.objects.first()
    if not company:
        raise ValueError("Nije moguće odrediti firmu za knjiženje")

    # Check if already booked
    if JournalEntry.objects.filter(source_invoice=invoice, is_posted=True).exists():
        return None  # Already booked

    country = getattr(invoice, 'country', 'HR')
    is_storno = invoice.doctype == 'S'
    is_avansni = invoice.doctype == 'A'
    is_outgoing = invoice.doctype in ('R', 'P', 'A', 'FA', 'RN', 'GS')  # Izdani računi

    # Calculate totals
    subtotal = Decimal(str(invoice.subtotal or 0))
    tax_amount = Decimal(str(invoice.tax_amount or 0))
    total = Decimal(str(invoice.total or 0))

    if total <= 0:
        return None  # Nothing to book

    # FIX4: Validate total = subtotal + tax (tolerance 0.05 EUR)
    expected_total = subtotal + tax_amount
    if abs(total - expected_total) > Decimal('0.05'):
        import logging
        logging.getLogger('konto').warning(
            'Invoice %s total mismatch: total=%s but subtotal(%s)+tax(%s)=%s. Using calculated.',
            invoice.number, total, subtotal, tax_amount, expected_total
        )
        total = expected_total

    # Resolve konto accounts based on country
    if country == 'DE':
        receivable_code = '1200'   # Forderungen aus Lieferungen
        payable_code = '1600'      # Verbindlichkeiten
        revenue_code = '8000'      # Erlöse 19% USt
        expense_code = '4000'      # Materialaufwand
        vat_out_code = '1776'      # Umsatzsteuer 19%
        vat_in_code = '1576'       # Vorsteuer 19%
    else:  # HR
        receivable_code = '1200'   # Potraživanja od kupaca
        payable_code = '2200'      # Obveze prema dobavljačima
        revenue_code = '7000'      # Prihodi od prodaje
        expense_code = '4000'      # Materijalni troškovi
        vat_out_code = '2400'      # Obveze za PDV
        vat_in_code = '1400'       # Pretporez

    je = JournalEntry.objects.create(
        company=company,
        entry_number=_next_entry_number(company, 'INV'),
        date=invoice.date_issued.date() if hasattr(invoice.date_issued, 'date') else invoice.date_issued or timezone.now().date(),
        description=f"Račun {invoice.number} - {invoice.client_name}",
        source_type='invoice',
        source_invoice=invoice,
        is_posted=True,
        created_by=user,
    )

    if is_storno:
        # STORNO račun — reversal izdanog računa
        # D: Prihodi 7000 (storniramo prihod) + D: PDV 2400 (storniramo PDV)
        # P: Potraživanja 1200 (smanjujemo potraživanje)
        try:
            rev_acct = _get_or_fail(company, revenue_code)
        except ValueError:
            rev_acct = KontoAccount.objects.create(
                company=company, code=revenue_code,
                name='Prihodi od prodaje', account_type='income')
        LedgerLine.objects.create(
            journal_entry=je, account=rev_acct,
            side='debit', amount=subtotal,
            description=f"STORNO prihod {invoice.number}")

        if tax_amount > 0:
            try:
                vat_acct = _get_or_fail(company, vat_out_code)
            except ValueError:
                vat_acct = KontoAccount.objects.create(
                    company=company, code=vat_out_code,
                    name='Obveze za PDV', account_type='liability')
            LedgerLine.objects.create(
                journal_entry=je, account=vat_acct,
                side='debit', amount=tax_amount,
                description=f"STORNO PDV {invoice.number}")

        try:
            recv_acct = _get_or_fail(company, receivable_code)
        except ValueError:
            recv_acct = KontoAccount.objects.create(
                company=company, code=receivable_code,
                name='Potraživanja od kupaca', account_type='asset')
        LedgerLine.objects.create(
            journal_entry=je, account=recv_acct,
            side='credit', amount=total,
            description=f"STORNO potraživanje {invoice.number}")

    elif is_avansni:
        # AVANSNI RAČUN — D:1200 potraživanja / P:2900 primljeni avansi + P:2400 PDV
        # Zakon o PDV-u čl. 78, st. 3 — avansni PDV u momentu naplate
        try:
            recv_acct = _get_or_fail(company, receivable_code)
        except ValueError:
            recv_acct = KontoAccount.objects.create(
                company=company, code=receivable_code,
                name='Potraživanja od kupaca', account_type='asset')
        LedgerLine.objects.create(
            journal_entry=je, account=recv_acct,
            side='debit', amount=total,
            description=f"Avans kupac: {invoice.client_name}")

        # P: Primljeni avansi (konto 2900)
        avans_code = '2900' if country != 'DE' else '1718'
        avans_name = 'Primljeni avansi' if country != 'DE' else 'Erhaltene Anzahlungen'
        avans_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=avans_code,
            defaults={'name': avans_name, 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=avans_acct,
            side='credit', amount=subtotal,
            description=f"Avans {invoice.number}")

        # P: PDV na avans
        if tax_amount > 0:
            try:
                vat_acct = _get_or_fail(company, vat_out_code)
            except ValueError:
                vat_acct = KontoAccount.objects.create(
                    company=company, code=vat_out_code,
                    name='Obveze za PDV', account_type='liability')
            LedgerLine.objects.create(
                journal_entry=je, account=vat_acct,
                side='credit', amount=tax_amount,
                description=f"PDV avans {invoice.number}")

    elif is_outgoing:
        # Izdani račun
        # D: Potraživanja od kupaca (total with VAT)
        try:
            recv_acct = _get_or_fail(company, receivable_code)
        except ValueError:
            recv_acct = KontoAccount.objects.create(
                company=company, code=receivable_code,
                name='Potraživanja od kupaca', account_type='asset')
        LedgerLine.objects.create(
            journal_entry=je, account=recv_acct,
            side='debit', amount=total,
            description=f"Kupac: {invoice.client_name}")

        # P: Prihodi od prodaje (subtotal without VAT)
        try:
            rev_acct = _get_or_fail(company, revenue_code)
        except ValueError:
            rev_acct = KontoAccount.objects.create(
                company=company, code=revenue_code,
                name='Prihodi od prodaje', account_type='income')
        LedgerLine.objects.create(
            journal_entry=je, account=rev_acct,
            side='credit', amount=subtotal,
            description=f"Račun {invoice.number}")

        # P: PDV obveza (tax amount)
        if tax_amount > 0:
            try:
                vat_acct = _get_or_fail(company, vat_out_code)
            except ValueError:
                vat_acct = KontoAccount.objects.create(
                    company=company, code=vat_out_code,
                    name='Obveze za PDV', account_type='liability')
            LedgerLine.objects.create(
                journal_entry=je, account=vat_acct,
                side='credit', amount=tax_amount,
                description=f"PDV račun {invoice.number}")
    else:
        # Primljeni račun (ulazni) - doctype 'S' (storno) ili custom
        # D: Rashodi (subtotal)
        try:
            exp_acct = _get_or_fail(company, expense_code)
        except ValueError:
            exp_acct = KontoAccount.objects.create(
                company=company, code=expense_code,
                name='Materijalni troškovi', account_type='expense')
        LedgerLine.objects.create(
            journal_entry=je, account=exp_acct,
            side='debit', amount=subtotal,
            description=f"Trošak: {invoice.number}")

        # D: Pretporez
        if tax_amount > 0:
            try:
                vatin_acct = _get_or_fail(company, vat_in_code)
            except ValueError:
                vatin_acct = KontoAccount.objects.create(
                    company=company, code=vat_in_code,
                    name='Pretporez', account_type='asset')
            LedgerLine.objects.create(
                journal_entry=je, account=vatin_acct,
                side='debit', amount=tax_amount,
                description=f"Pretporez {invoice.number}")

        # P: Obveze prema dobavljačima (total)
        try:
            pay_acct = _get_or_fail(company, payable_code)
        except ValueError:
            pay_acct = KontoAccount.objects.create(
                company=company, code=payable_code,
                name='Obveze prema dobavljačima', account_type='liability')
        LedgerLine.objects.create(
            journal_entry=je, account=pay_acct,
            side='credit', amount=total,
            description=f"Dobavljač: {invoice.client_name}")

    return je


@transaction.atomic
def book_bank_transactions(transactions_qs, user=None):
    """Book bank statement transactions into the ledger.

    Uplata od kupca 1250€ (parirana s računom):
      Duguje: 1000 Žiro račun               1250,00€
      Potražuje: 1200 Potraživanja od kupaca 1250,00€

    Plaćanje dobavljaču 500€:
      Duguje: 2200 Obveze prema dobavljačima  500,00€
      Potražuje: 1000 Žiro račun              500,00€
    """
    from .models import KontoAccount, JournalEntry, LedgerLine

    booked = []
    for txn in transactions_qs:
        if txn.is_booked:
            continue

        company = txn.company
        bank_acct = txn.bank_account

        # Determine bank konto (from BankAccount or default 1000)
        if bank_acct.konto_account:
            bank_konto = bank_acct.konto_account
        else:
            bank_konto, _ = KontoAccount.objects.get_or_create(
                company=company, code='1000',
                defaults={'name': 'Žiro račun', 'account_type': 'asset'})

        je = JournalEntry.objects.create(
            company=company,
            entry_number=_next_entry_number(company, 'BNK'),
            date=txn.transaction_date,
            description=f"Izvod: {txn.counterparty_name[:50]} - {txn.amount}€",
            source_type='bank_statement',
            source_transaction=txn,
            is_posted=True,
            created_by=user,
        )

        if txn.transaction_type == 'inflow':
            # Uplata: D: Žiro račun, P: Potraživanja
            LedgerLine.objects.create(
                journal_entry=je, account=bank_konto,
                side='debit', amount=txn.amount,
                description=f"Uplata: {txn.counterparty_name[:80]}")

            if txn.matched_invoice:
                # Parirana s računom → potraživanja od kupaca
                recv_konto, _ = KontoAccount.objects.get_or_create(
                    company=company, code='1200',
                    defaults={'name': 'Potraživanja od kupaca', 'account_type': 'asset'})
                LedgerLine.objects.create(
                    journal_entry=je, account=recv_konto,
                    side='credit', amount=txn.amount,
                    description=f"Zatvaranje: {txn.matched_invoice.number}")
                # FIX3: Mark matched invoice as PAID
                inv = txn.matched_invoice
                if inv.status in ('SENT', 'UNPAID', 'OVERDUE', 'CONFIRMED', 'FISCALIZED'):
                    inv.status = 'PAID'
                    inv.save(update_fields=['status'])
            else:
                # Neparirana uplata → ostali prihodi
                other_konto, _ = KontoAccount.objects.get_or_create(
                    company=company, code='7600',
                    defaults={'name': 'Ostali prihodi', 'account_type': 'income'})
                LedgerLine.objects.create(
                    journal_entry=je, account=other_konto,
                    side='credit', amount=txn.amount,
                    description=f"Neparirana uplata: {txn.description[:80]}")
        else:
            # Isplata: D: Obveze, P: Žiro račun
            if txn.matched_invoice:
                pay_konto, _ = KontoAccount.objects.get_or_create(
                    company=company, code='2200',
                    defaults={'name': 'Obveze prema dobavljačima', 'account_type': 'liability'})
                LedgerLine.objects.create(
                    journal_entry=je, account=pay_konto,
                    side='debit', amount=txn.amount,
                    description=f"Plaćanje: {txn.matched_invoice.number}")
                # FIX3: Mark matched supplier invoice as PAID
                inv = txn.matched_invoice
                if inv.status in ('SENT', 'UNPAID', 'OVERDUE', 'CONFIRMED'):
                    inv.status = 'PAID'
                    inv.save(update_fields=['status'])
            else:
                exp_konto, _ = KontoAccount.objects.get_or_create(
                    company=company, code='4400',
                    defaults={'name': 'Ostali troškovi', 'account_type': 'expense'})
                LedgerLine.objects.create(
                    journal_entry=je, account=exp_konto,
                    side='debit', amount=txn.amount,
                    description=f"Isplata: {txn.counterparty_name[:80]}")

            LedgerLine.objects.create(
                journal_entry=je, account=bank_konto,
                side='credit', amount=txn.amount,
                description=f"Odljev: {txn.counterparty_name[:80]}")

        txn.is_booked = True
        txn.save(update_fields=['is_booked'])
        booked.append(je)

        # Recalculate bank balance
        bank_acct.recalculate_balance()

    return booked


@transaction.atomic
def match_transaction_to_invoice(transaction_obj, invoice):
    """Match a bank transaction to an invoice.

    1. Check amount (exact or partial)
    2. Link transaction.matched_invoice = invoice
    3. Update invoice status (PAID/partial)
    4. Auto-book the transaction
    5. Update bank_account.current_balance
    """
    from .models import BankTransaction

    if transaction_obj.status == 'matched':
        return False  # Already matched

    # Link
    transaction_obj.matched_invoice = invoice
    transaction_obj.status = 'matched'
    transaction_obj.save(update_fields=['matched_invoice', 'status'])

    # Check if invoice is fully paid
    total_paid = BankTransaction.objects.filter(
        matched_invoice=invoice, status='matched', transaction_type='inflow'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    invoice_total = Decimal(str(invoice.total or 0))

    if total_paid >= invoice_total:
        invoice.status = 'PAID'
    elif total_paid > 0:
        invoice.status = 'UNPAID'  # Partial payment
    invoice.save(update_fields=['status'])

    # Auto-book if not already booked
    if not transaction_obj.is_booked:
        book_bank_transactions(
            BankTransaction.objects.filter(pk=transaction_obj.pk))

    # Recalculate bank balance
    transaction_obj.bank_account.recalculate_balance()

    return True


def auto_match_transactions(company):
    """Auto-match unmatched transactions by reference number, counterparty, and amount.

    For each unmatched inflow transaction:
    1. Check reference_number -> search Invoice with that number
    2. Check counterparty_name -> search Client name
    3. Check amount -> search Invoice with exact amount
    4. If 100% match found -> link automatically
    5. Return list of matched pairs
    """
    from .models import BankTransaction
    from invoicing.models import Invoice

    unmatched = BankTransaction.objects.filter(
        company=company, status='unmatched', transaction_type='inflow'
    ).select_related('bank_account')

    unpaid_invoices = Invoice.objects.filter(
        status__in=['SENT', 'UNPAID', 'OVERDUE']
    ).order_by('-date_issued')

    matched_pairs = []

    for txn in unmatched:
        best_match = None
        best_score = 0

        for inv in unpaid_invoices:
            score = 0
            inv_total = Decimal(str(inv.total or 0))

            # 1. Reference number match (strongest signal)
            if txn.reference_number and inv.number:
                # Clean reference for comparison
                ref_clean = txn.reference_number.replace('-', '').replace(' ', '').upper()
                inv_num_clean = inv.number.replace('-', '').replace(' ', '').upper()
                if ref_clean == inv_num_clean or inv_num_clean in ref_clean:
                    score += 50

            # 2. Exact amount match
            if inv_total > 0 and txn.amount == inv_total:
                score += 30

            # 3. Counterparty name match
            if txn.counterparty_name and inv.client_name:
                cp_lower = txn.counterparty_name.lower()
                cl_lower = inv.client_name.lower()
                if cl_lower in cp_lower or cp_lower in cl_lower:
                    score += 20

            # 4. OIB match in description
            if inv.client_oib and inv.client_oib in (txn.description or ''):
                score += 25

            if score > best_score:
                best_score = score
                best_match = inv

        # Auto-match if score >= 50 (reference match or amount+name match)
        if best_match and best_score >= 50:
            match_transaction_to_invoice(txn, best_match)
            matched_pairs.append((txn, best_match, best_score))
            # Remove from available invoices to prevent double matching
            unpaid_invoices = unpaid_invoices.exclude(pk=best_match.pk)

    return matched_pairs


def get_open_receivables(company):
    """Saldakonti kupaca - tko nam koliko duguje.

    Returns list of: {client, invoice, date, due_date, total, paid, remaining, days_overdue}
    """
    from invoicing.models import Invoice
    from .models import BankTransaction
    from datetime import date as dt_date

    today = dt_date.today()
    invoices = Invoice.objects.filter(
        status__in=['SENT', 'UNPAID', 'OVERDUE'],
        doctype__in=['R', 'A'],  # Računi i avansni
    ).order_by('date_due', 'date_issued')

    receivables = []
    for inv in invoices:
        inv_total = Decimal(str(inv.total or 0))
        paid = BankTransaction.objects.filter(
            matched_invoice=inv, status='matched', transaction_type='inflow'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        remaining = inv_total - paid
        if remaining <= 0:
            continue

        due_date = inv.date_due
        days_overdue = (today - due_date).days if due_date and due_date < today else 0

        receivables.append({
            'client': inv.client_name,
            'client_oib': inv.client_oib or '',
            'invoice_number': inv.number,
            'invoice_id': inv.pk,
            'date': inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued,
            'due_date': due_date,
            'total': float(inv_total),
            'paid': float(paid),
            'remaining': float(remaining),
            'days_overdue': days_overdue,
        })

    return receivables


def get_open_payables(company):
    """Saldakonti dobavljača - kome mi koliko dugujemo.

    Returns list of: {supplier, invoice, date, due_date, total, paid, remaining, days_overdue}
    """
    from invoicing.models import Invoice
    from .models import BankTransaction
    from datetime import date as dt_date

    today = dt_date.today()
    # Incoming invoices (doctype 'S' for storno or custom incoming)
    # For now, look at invoices with source='import' or manually entered payables
    invoices = Invoice.objects.filter(
        status__in=['SENT', 'UNPAID', 'OVERDUE'],
        doctype='GS',  # Gotovinski račun or incoming
    ).order_by('date_due', 'date_issued')

    payables = []
    for inv in invoices:
        inv_total = Decimal(str(inv.total or 0))
        paid = BankTransaction.objects.filter(
            matched_invoice=inv, status='matched', transaction_type='outflow'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        remaining = inv_total - paid
        if remaining <= 0:
            continue

        due_date = inv.date_due
        days_overdue = (today - due_date).days if due_date and due_date < today else 0

        payables.append({
            'supplier': inv.client_name,
            'invoice_number': inv.number,
            'invoice_id': inv.pk,
            'date': inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued,
            'due_date': due_date,
            'total': float(inv_total),
            'paid': float(paid),
            'remaining': float(remaining),
            'days_overdue': days_overdue,
        })

    return payables


def get_profit_loss(company, date_from, date_to):
    """Račun dobiti i gubitka za period.

    PRIHODI (konta 7xxx): ukupno
    - RASHODI (konta 4xxx-6xxx): ukupno
    = DOBIT/GUBITAK
    """
    from .models import KontoAccount, LedgerLine

    # Income accounts (type='income', typically 7xxx)
    income_accounts = KontoAccount.objects.select_related("company").filter(
        company=company, account_type='income', is_active=True)
    income_lines = LedgerLine.objects.filter(
        account__in=income_accounts,
        journal_entry__date__gte=date_from,
        journal_entry__date__lte=date_to,
        journal_entry__is_posted=True,
    )
    income_credits = income_lines.filter(side='credit').aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    income_debits = income_lines.filter(side='debit').aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    total_income = income_credits - income_debits

    # Expense accounts (type='expense', typically 4xxx-6xxx)
    expense_accounts = KontoAccount.objects.select_related("company").filter(
        company=company, account_type='expense', is_active=True)
    expense_lines = LedgerLine.objects.filter(
        account__in=expense_accounts,
        journal_entry__date__gte=date_from,
        journal_entry__date__lte=date_to,
        journal_entry__is_posted=True,
    )
    expense_debits = expense_lines.filter(side='debit').aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    expense_credits = expense_lines.filter(side='credit').aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    total_expense = expense_debits - expense_credits

    # Breakdown by account
    income_detail = []
    for acct in income_accounts:
        cr = LedgerLine.objects.filter(
            account=acct, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        db = LedgerLine.objects.filter(
            account=acct, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        bal = cr - db
        if bal != 0:
            income_detail.append({
                'code': acct.code, 'name': acct.name, 'amount': float(bal)})

    expense_detail = []
    for acct in expense_accounts:
        db = LedgerLine.objects.filter(
            account=acct, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        cr = LedgerLine.objects.filter(
            account=acct, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        bal = db - cr
        if bal != 0:
            expense_detail.append({
                'code': acct.code, 'name': acct.name, 'amount': float(bal)})

    return {
        'period': {'from': str(date_from), 'to': str(date_to)},
        'income': {
            'total': float(total_income),
            'detail': income_detail,
        },
        'expenses': {
            'total': float(total_expense),
            'detail': expense_detail,
        },
        'profit_loss': float(total_income - total_expense),
    }


def get_balance_sheet(company, date):
    """Bilanca na datum.

    AKTIVA = PASIVA (mora biti u balansu!)
    Aktiva: imovina (asset accounts)
    Pasiva: obveze (liability) + kapital (equity) + zadržana dobit (income - expense)
    """
    from .models import KontoAccount, LedgerLine

    def _account_balance(acct, up_to_date):
        """Calculate account balance up to a given date."""
        lines = LedgerLine.objects.filter(
            account=acct,
            journal_entry__date__lte=up_to_date,
            journal_entry__is_posted=True,
        )
        debits = lines.filter(side='debit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        credits = lines.filter(side='credit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        if acct.account_type in ('asset', 'expense'):
            return debits - credits
        return credits - debits

    assets = []
    total_assets = Decimal('0')
    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='asset', is_active=True):
        bal = _account_balance(acct, date)
        if bal != 0:
            assets.append({'code': acct.code, 'name': acct.name, 'balance': float(bal)})
            total_assets += bal

    liabilities = []
    total_liabilities = Decimal('0')
    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='liability', is_active=True):
        bal = _account_balance(acct, date)
        if bal != 0:
            liabilities.append({'code': acct.code, 'name': acct.name, 'balance': float(bal)})
            total_liabilities += bal

    equity_items = []
    total_equity = Decimal('0')
    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='equity', is_active=True):
        bal = _account_balance(acct, date)
        if bal != 0:
            equity_items.append({'code': acct.code, 'name': acct.name, 'balance': float(bal)})
            total_equity += bal

    # Retained earnings = Income - Expense (up to date)
    income_total = Decimal('0')
    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='income', is_active=True):
        income_total += _account_balance(acct, date)

    expense_total = Decimal('0')
    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='expense', is_active=True):
        expense_total += _account_balance(acct, date)

    retained_earnings = income_total - expense_total
    if retained_earnings != 0:
        equity_items.append({
            'code': '9999', 'name': 'Zadržana dobit/gubitak',
            'balance': float(retained_earnings)})
        total_equity += retained_earnings

    total_pasiva = total_liabilities + total_equity

    return {
        'date': str(date),
        'assets': {
            'items': assets,
            'total': float(total_assets),
        },
        'liabilities': {
            'items': liabilities,
            'total': float(total_liabilities),
        },
        'equity': {
            'items': equity_items,
            'total': float(total_equity),
        },
        'total_pasiva': float(total_pasiva),
        'is_balanced': abs(total_assets - total_pasiva) < Decimal('0.01'),
    }


# ═══════════════════════════════════════════════════════════════════════
#  TAX / PDV REPORTING
# ═══════════════════════════════════════════════════════════════════════

def calculate_vat_period(company, period_type, year, month=None, quarter=None):
    """Calculate VAT (PDV/USt) for a given period.

    Output VAT: from issued invoices (doctype R/A/GS) in period
    Input VAT : from konto ledger (accounts 1400/1576)
    Returns   : TaxPeriod instance (created or updated)
    """
    import calendar
    import datetime
    from .models import TaxPeriod, TaxLineDetail, KontoAccount, LedgerLine
    from invoicing.models import Invoice, InvoiceItem
    from django.db.models import Sum as DSum

    # --- date range ---
    if period_type == 'monthly':
        if not month:
            raise ValueError("month required for monthly period")
        date_from = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        date_to = datetime.date(year, month, last_day)
        nm = month + 1 if month < 12 else 1
        ny = year if month < 12 else year + 1
        deadline_day = 20 if company.country == 'HR' else 10
        filing_deadline = datetime.date(ny, nm, deadline_day)

    elif period_type == 'quarterly':
        if not quarter:
            raise ValueError("quarter required for quarterly period")
        fm = (quarter - 1) * 3 + 1
        lm = fm + 2
        date_from = datetime.date(year, fm, 1)
        last_day = calendar.monthrange(year, lm)[1]
        date_to = datetime.date(year, lm, last_day)
        nm = lm + 1 if lm < 12 else 1
        ny = year if lm < 12 else year + 1
        deadline_day = 20 if company.country == 'HR' else 10
        filing_deadline = datetime.date(ny, nm, deadline_day)

    else:  # yearly
        date_from = datetime.date(year, 1, 1)
        date_to = datetime.date(year, 12, 31)
        filing_deadline = datetime.date(year + 1, 3, 31)

    # --- get or create TaxPeriod ---
    period, _ = TaxPeriod.objects.get_or_create(
        company=company,
        period_type=period_type,
        year=year,
        month=month,
        quarter=quarter,
        defaults={'filing_deadline': filing_deadline},
    )
    period.filing_deadline = filing_deadline

    # --- OUTPUT VAT: from outgoing invoices ---
    outgoing = Invoice.objects.filter(
        company=company,
        doctype__in=['R', 'A', 'GS'],
        status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
        date_issued__date__gte=date_from,
        date_issued__date__lte=date_to,
    )

    rate_data = {}   # {Decimal(rate): {'revenue_base': D, 'output_vat': D}}
    total_revenue = Decimal('0')
    total_output_vat = Decimal('0')

    for inv in outgoing:
        items_by_rate = (
            InvoiceItem.objects
            .filter(invoice=inv)
            .values('tax_rate')
            .annotate(net=DSum('total_price'), gross=DSum('gross_total'))
        )
        for row in items_by_rate:
            rate = Decimal(str(row['tax_rate'] or 0))
            net  = Decimal(str(row['net'] or 0))
            gross = Decimal(str(row['gross'] or 0))
            vat  = gross - net
            rd = rate_data.setdefault(rate, {'revenue_base': Decimal('0'), 'output_vat': Decimal('0')})
            rd['revenue_base'] += net
            rd['output_vat']   += vat
            total_revenue      += net
            total_output_vat   += vat

    # --- INPUT VAT: from konto ledger ---
    if company.country == 'DE':
        vat_in_codes = ['1576', '1571']
    else:
        vat_in_codes = ['1400', '1500']

    vat_in_accts = KontoAccount.objects.select_related("company").filter(company=company, code__in=vat_in_codes)
    total_input_vat = Decimal('0')
    if vat_in_accts.exists():
        total_input_vat = (
            LedgerLine.objects.filter(
                account__in=vat_in_accts,
                side='debit',
                journal_entry__date__gte=date_from,
                journal_entry__date__lte=date_to,
                journal_entry__is_posted=True,
            ).aggregate(t=DSum('amount'))['t'] or Decimal('0')
        )

    # --- EXPENSES: from konto expense accounts ---
    exp_accts = KontoAccount.objects.select_related("company").filter(company=company, account_type='expense')
    total_expenses = Decimal('0')
    if exp_accts.exists():
        exp_d = (LedgerLine.objects.filter(
            account__in=exp_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        exp_c = (LedgerLine.objects.filter(
            account__in=exp_accts, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        total_expenses = exp_d - exp_c

    # --- save period ---
    period.total_output_vat = total_output_vat
    period.total_input_vat  = total_input_vat
    period.vat_payable      = total_output_vat - total_input_vat
    period.total_revenue    = total_revenue
    period.total_expenses   = total_expenses
    period.save()

    # --- save line details ---
    TaxLineDetail.objects.filter(period=period).delete()
    for rate, data in rate_data.items():
        TaxLineDetail.objects.create(
            period=period,
            tax_rate=rate,
            revenue_base=data['revenue_base'],
            output_vat=data['output_vat'],
        )

    return period


def get_annual_tax_summary(company, year):
    """Annual income tax summary.

    HR: Porez na dohodak 20%/30% + prirez
    DE: Einkommensteuer (progressive) + Solidaritätszuschlag + Gewerbesteuer
    Returns a dict with all computed values.
    """
    import datetime
    from .models import KontoAccount, LedgerLine
    from django.db.models import Sum as DSum

    date_from = datetime.date(year, 1, 1)
    date_to   = datetime.date(year, 12, 31)

    # --- revenue from invoices ---
    from invoicing.models import Invoice
    gross_revenue = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).aggregate(t=DSum('subtotal'))['t'] or Decimal('0')
    )

    # --- expenses from konto ---
    exp_accts = KontoAccount.objects.select_related("company").filter(company=company, account_type='expense')
    total_expenses = Decimal('0')
    if exp_accts.exists():
        exp_d = (LedgerLine.objects.filter(
            account__in=exp_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        exp_c = (LedgerLine.objects.filter(
            account__in=exp_accts, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        total_expenses = exp_d - exp_c

    taxable_income = max(gross_revenue - total_expenses, Decimal('0'))
    tax_due        = Decimal('0')
    details        = {}

    if company.country == 'HR':
        # Porez na dohodak: 20% do 47.780 €, 30% iznad
        BAND1_LIMIT = Decimal('47780')
        RATE1 = Decimal('0.20')
        RATE2 = Decimal('0.30')
        PRIREZ_RATE = Decimal('0.18')  # Zagreb: 18%

        if taxable_income <= BAND1_LIMIT:
            income_tax = taxable_income * RATE1
        else:
            income_tax = BAND1_LIMIT * RATE1 + (taxable_income - BAND1_LIMIT) * RATE2

        prirez  = income_tax * PRIREZ_RATE
        tax_due = income_tax + prirez

        details = {
            'country': 'HR',
            'gross_revenue': float(gross_revenue),
            'total_expenses': float(total_expenses),
            'taxable_income': float(taxable_income),
            'income_tax_base': float(income_tax),
            'prirez': float(prirez),
            'prirez_rate_pct': float(PRIREZ_RATE * 100),
            'total_tax_due': float(tax_due),
            'effective_rate_pct': float((tax_due / taxable_income * 100) if taxable_income else 0),
        }

    else:  # DE — Einkommensteuer (vereinfacht, Einzelunternehmen)
        GRUNDFREIBETRAG = Decimal('11604')
        GEWERBESTEUER_MESSZAHL = Decimal('0.035')
        HEBESATZ = Decimal('3.80')  # 380% — mittlerer Satz
        SOLI_THRESHOLD = Decimal('18130')

        # Progressive ESt (simplified, Splittingtabelle not applied)
        taxable = max(taxable_income - GRUNDFREIBETRAG, Decimal('0'))
        if taxable <= 0:
            est = Decimal('0')
        elif taxable <= Decimal('15999'):
            y = (taxable - Decimal('11604')) / Decimal('10000')
            est = (Decimal('979.18') * y + Decimal('1400')) * y
        elif taxable <= Decimal('62809'):
            y = (taxable - Decimal('15999')) / Decimal('10000')
            est = (Decimal('192.59') * y + Decimal('2397')) * y + Decimal('966.53')
        elif taxable <= Decimal('277825'):
            est = taxable * Decimal('0.42') - Decimal('9972.98')
        else:
            est = taxable * Decimal('0.45') - Decimal('18307.73')

        est = max(est, Decimal('0'))

        # Solidaritätszuschlag (5.5% of ESt, only if ESt > threshold)
        soli = Decimal('0')
        if est > SOLI_THRESHOLD:
            soli = est * Decimal('0.055')

        # Gewerbesteuer (Messbetrag × Hebesatz)
        gewerbe_profit = max(taxable_income - Decimal('24500'), Decimal('0'))
        gewerbesteuer = gewerbe_profit * GEWERBESTEUER_MESSZAHL * HEBESATZ

        tax_due = est + soli + gewerbesteuer

        details = {
            'country': 'DE',
            'gross_revenue': float(gross_revenue),
            'total_expenses': float(total_expenses),
            'taxable_income': float(taxable_income),
            'grundfreibetrag': float(GRUNDFREIBETRAG),
            'einkommensteuer': float(est),
            'solidaritaetszuschlag': float(soli),
            'gewerbesteuer': float(gewerbesteuer),
            'hebesatz_pct': float(HEBESATZ * 100),
            'total_tax_due': float(tax_due),
            'effective_rate_pct': float((tax_due / taxable_income * 100) if taxable_income else 0),
        }

    details['year'] = year
    return details



def calculate_corporate_tax(company, year):
    """PD obrazac — Porez na dobit za d.o.o. (Čl.28 ZPD, NN 177/04, izmjena NN 114/23)."""
    import datetime
    from .models import KontoAccount, LedgerLine
    from invoicing.models import Invoice
    from django.db.models import Sum as DSum

    date_from = datetime.date(year, 1, 1)
    date_to = datetime.date(year, 12, 31)

    # Revenue from invoices
    gross_revenue = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS', 'IRA'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).aggregate(t=DSum('subtotal'))['t'] or Decimal('0')
    )

    # Expenses from konto
    exp_accts = KontoAccount.objects.filter(company=company, account_type='expense')
    total_expenses = Decimal('0')
    if exp_accts.exists():
        exp_d = (LedgerLine.objects.filter(
            account__in=exp_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        exp_c = (LedgerLine.objects.filter(
            account__in=exp_accts, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        total_expenses = exp_d - exp_c

    gross_profit = gross_revenue - total_expenses

    # Non-deductible expenses (Čl.5-7 ZPD) — representacija, 50% auto, kazne
    # Check konto accounts 4600 (repr), 4610 (auto 50%), 4620 (kazne)
    NON_DEDUCT_CODES = ['4600', '4610', '4620', '4630', '4640']
    non_deductible = Decimal('0')
    nd_accts = KontoAccount.objects.filter(company=company, code__in=NON_DEDUCT_CODES)
    if nd_accts.exists():
        nd_d = (LedgerLine.objects.filter(
            account__in=nd_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        non_deductible = nd_d * Decimal('0.50')  # 50% non-deductible

    # Exempt income (dividende, kapitalni dobici) — konto 7800-7899
    exempt_income = Decimal('0')
    ex_accts = KontoAccount.objects.filter(
        company=company, code__gte='7800', code__lte='7899'
    )
    if ex_accts.exists():
        ex_c = (LedgerLine.objects.filter(
            account__in=ex_accts, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        exempt_income = ex_c

    tax_base = max(gross_profit + non_deductible - exempt_income, Decimal('0'))

    # Tax rate (Čl.28 ZPD, NN 114/23)
    THRESHOLD = Decimal('1000000')  # 1M EUR
    RATE_LOW = Decimal('0.10')   # 10%
    RATE_HIGH = Decimal('0.18')  # 18%

    if tax_base <= THRESHOLD:
        corporate_tax = (tax_base * RATE_LOW).quantize(Decimal('0.01'))
        rate_label = '10%'
    else:
        corporate_tax = (
            THRESHOLD * RATE_LOW + (tax_base - THRESHOLD) * RATE_HIGH
        ).quantize(Decimal('0.01'))
        rate_label = '10% + 18%'

    # Legal reliefs from BORG FENIX
    reliefs = []
    relief_total = Decimal('0')
    try:
        from limit_connect_ai.models_knowledge_graph import ClientOpportunityMatch
        matches = ClientOpportunityMatch.objects.filter(
            company=company,
            status__in=['identified', 'applied', 'utilized'],
            opportunity__opportunity_type__in=['tax_relief', 'employment_subsidy'],
        ).select_related('opportunity')
        for m in matches:
            amt = Decimal(str(m.calculated_savings or 0))
            if amt > 0:
                reliefs.append({
                    'name': m.opportunity.name,
                    'amount': float(amt),
                    'type': m.opportunity.opportunity_type,
                })
                relief_total += amt
    except (ValueError, TypeError):
        pass

    net_tax = max(corporate_tax - relief_total, Decimal('0'))

    return {
        'year': year,
        'country': company.country,
        'company_name': company.name,
        'business_type': company.business_type,
        'gross_revenue': float(gross_revenue),
        'total_expenses': float(total_expenses),
        'gross_profit': float(gross_profit),
        'non_deductible': float(non_deductible),
        'exempt_income': float(exempt_income),
        'tax_base': float(tax_base),
        'tax_rate': rate_label,
        'corporate_tax': float(corporate_tax),
        'reliefs': reliefs,
        'relief_total': float(relief_total),
        'net_tax': float(net_tax),
        'effective_rate_pct': float((net_tax / gross_revenue * 100) if gross_revenue else 0),
    }

def get_euer_report(company, year):
    """Einnahmenüberschussrechnung (EÜR) — German simple income/expense report.

    Groups income accounts (7xxx/8xxx) and expense accounts (4xxx-6xxx)
    by ledger entries for the year.
    Returns dict: {income_items, expense_items, total_income, total_expenses, profit}
    """
    import datetime
    from .models import KontoAccount, LedgerLine
    from django.db.models import Sum as DSum

    date_from = datetime.date(year, 1, 1)
    date_to   = datetime.date(year, 12, 31)

    def _account_total(acct):
        lines = LedgerLine.objects.filter(
            account=acct,
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        )
        debits  = lines.filter(side='debit').aggregate(t=DSum('amount'))['t'] or Decimal('0')
        credits = lines.filter(side='credit').aggregate(t=DSum('amount'))['t'] or Decimal('0')
        if acct.account_type in ('asset', 'expense'):
            return debits - credits
        return credits - debits

    income_items   = []
    expense_items  = []
    total_income   = Decimal('0')
    total_expenses = Decimal('0')

    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='income', is_active=True).order_by('code'):
        bal = _account_total(acct)
        if bal != 0:
            income_items.append({'code': acct.code, 'name': acct.name, 'amount': float(bal)})
            total_income += bal

    for acct in KontoAccount.objects.select_related("company").filter(
            company=company, account_type='expense', is_active=True).order_by('code'):
        bal = _account_total(acct)
        if bal != 0:
            expense_items.append({'code': acct.code, 'name': acct.name, 'amount': float(bal)})
            total_expenses += bal

    # Also add invoice revenue (in case not all booked)
    from invoicing.models import Invoice
    invoice_revenue = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).aggregate(t=DSum('subtotal'))['t'] or Decimal('0')
    )

    return {
        'year': year,
        'income_items': income_items,
        'expense_items': expense_items,
        'total_income': float(total_income),
        'total_expenses': float(total_expenses),
        'invoice_revenue': float(invoice_revenue),
        'profit': float(total_income - total_expenses),
    }


# ═══════════════════════════════════════════════════
#  IntegrityError handler — PostgreSQL constraint zaštita
# ═══════════════════════════════════════════════════

def parse_integrity_error(e):
    """Parse PostgreSQL IntegrityError into user-friendly Croatian message."""
    msg = str(e).lower()
    if 'ledgerline_amount_positive' in msg:
        return 'Iznos stavke mora biti pozitivan (>0). Negativni iznosi nisu dozvoljeni.'
    if 'uravnotez' in msg or 'balance' in msg or 'duguje' in msg:
        return 'Temeljnica nije uravnotežena — ukupno duguje mora biti jednako ukupno potražuje.'
    if 'unique' in msg and 'entry_number' in msg:
        return 'Broj temeljnice već postoji za ovu firmu. Duplikati nisu dozvoljeni.'
    if 'unique' in msg:
        return 'Duplikat zapisa — ovaj unos već postoji u bazi.'
    return f'Baza podataka je odbila upis: {str(e)[:200]}'


# ═══════════════════════════════════════════════════
#  POS → KONTO: Auto-knjiženje zatvorene POS sesije
# ═══════════════════════════════════════════════════

@transaction.atomic
def book_pos_session(session, user=None):
    """Book a closed POS session into the ledger.

    Agregira sve plaćene račune u sesiji po načinu plaćanja i PDV stopi.
    Jedna temeljnica po sesiji:

    Gotovina 500€, Kartica 300€, Prihod neto 640€, PDV 160€:
      D: 1000 Blagajna               500,00€
      D: 1210 Potraživanja kartica   300,00€
      P: 7500 POS Prihodi            640,00€
      P: 2400 Obveze za PDV          160,00€

    Returns JournalEntry or None if already booked / no sales.
    """
    from .models import KontoAccount, JournalEntry, LedgerLine
    from pos.models import POSReceipt, POSPaymentLine

    company = session.terminal.company

    # Check period lock (N4 fix)
    from .models import AccountingPeriod
    session_date = (session.closed_at or session.opened_at)
    if hasattr(session_date, 'date'):
        session_date = session_date.date()
    if AccountingPeriod.is_period_locked(company, session_date.year, session_date.month):
        import logging
        logging.getLogger('konto').warning(
            'POS booking BLOCKED: period %d/%d is locked for %s (session #%s)',
            session_date.year, session_date.month, company.name, session.session_number
        )
        return None  # Period locked — cannot book

    # Check if already booked
    prefix = f"POS-{session.terminal.terminal_code}-{session.session_number}"
    if JournalEntry.objects.filter(company=company, entry_number__startswith=prefix).exists():
        return None  # Already booked

    # Get paid receipts (exclude training)
    receipts = session.receipts.filter(
        status=POSReceipt.Status.PAID,
        is_training=False,
    )
    if not receipts.exists():
        return None

    # Aggregate by payment method
    payment_totals = {}
    for receipt in receipts.prefetch_related('payment_lines'):
        for pl in receipt.payment_lines.all():
            method = pl.method
            payment_totals[method] = payment_totals.get(method, Decimal('0')) + pl.amount - pl.change_given

    # Aggregate tax breakdown
    total_subtotal = Decimal('0')
    total_tax = Decimal('0')
    tax_by_rate = {}
    for receipt in receipts.prefetch_related('items'):
        for item in receipt.items.all():
            net = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
            tax = net * item.tax_rate / 100
            total_subtotal += net
            total_tax += tax
            rate = item.tax_rate
            tax_by_rate[rate] = tax_by_rate.get(rate, Decimal('0')) + tax

    total_sales = total_subtotal + total_tax
    if total_sales <= 0:
        return None

    # Payment method → konto mapping
    PAYMENT_KONTO = {
        'CASH':    ('1000', 'Blagajna', 'asset'),
        'CARD':    ('1210', 'Potraživanja kartice', 'asset'),
        'MOBILE':  ('1215', 'Mobilno plaćanje', 'asset'),
        'VOUCHER': ('1290', 'Voucher potraživanja', 'asset'),
        'ACCOUNT': ('1200', 'Potraživanja od kupaca', 'asset'),
        'CRYPTO':  ('1280', 'Kripto potraživanja', 'asset'),
        'REVOLUT': ('1216', 'Revolut potraživanja', 'asset'),
        'AIRCASH': ('1217', 'Aircash potraživanja', 'asset'),
    }

    # Determine country
    country = getattr(company, 'country', 'HR')
    if country == 'DE':
        revenue_code, revenue_name = '8000', 'Erlöse POS'
        vat_code, vat_name = '1776', 'Umsatzsteuer'
    else:
        revenue_code, revenue_name = '7500', 'POS Prihodi od prodaje'
        vat_code, vat_name = '2400', 'Obveze za PDV'

    # Create journal entry
    entry_number = _next_entry_number(company, 'POS')
    session_date = (session.closed_at or session.opened_at).date() if hasattr(
        (session.closed_at or session.opened_at), 'date') else (session.closed_at or session.opened_at)

    je = JournalEntry.objects.create(
        company=company,
        entry_number=entry_number,
        date=session_date,
        description=f"POS {session.terminal.name} smjena #{session.session_number} — {receipts.count()} računa",
        source_type='pos',
        is_posted=True,
        created_by=user,
    )

    # DEBIT: Payment methods
    for method, amount in payment_totals.items():
        if amount <= 0:
            continue
        code, name, acct_type = PAYMENT_KONTO.get(method, ('1000', 'Blagajna', 'asset'))
        acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={'name': name, 'account_type': acct_type})
        LedgerLine.objects.create(
            journal_entry=je, account=acct,
            side='debit', amount=round(amount, 2),
            description=f"POS {method} smjena #{session.session_number}")

    # CREDIT: Revenue (subtotal without VAT)
    if total_subtotal > 0:
        rev_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=revenue_code,
            defaults={'name': revenue_name, 'account_type': 'income'})
        LedgerLine.objects.create(
            journal_entry=je, account=rev_acct,
            side='credit', amount=round(total_subtotal, 2),
            description=f"POS prihod smjena #{session.session_number}")

    # CREDIT: VAT
    if total_tax > 0:
        vat_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=vat_code,
            defaults={'name': vat_name, 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=vat_acct,
            side='credit', amount=round(total_tax, 2),
            description=f"PDV POS smjena #{session.session_number}")

    # CREDIT: Porez na potrošnju → konto 2390 (GAP1 fix)
    total_consumption_tax = sum(
        (r.consumption_tax_amount or Decimal('0')) for r in receipts
    )
    if total_consumption_tax > 0:
        ct_code = '2393' if country != 'DE' else '1776'
        ct_name = 'Obveza poreza na potrošnju (JLS)' if country != 'DE' else 'Verbrauchsteuer'
        ct_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code=ct_code,
            defaults={'name': ct_name, 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=ct_acct,
            side='credit', amount=round(total_consumption_tax, 2),
            description=f"Porez na potrošnju POS smjena #{session.session_number}")
        # Adjust revenue — consumption tax reduces net revenue
        # Revenue line already credited; add debit to consumption tax expense
        ct_exp_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code='4790',
            defaults={'name': 'Trošak poreza na potrošnju', 'account_type': 'expense'})
        LedgerLine.objects.create(
            journal_entry=je, account=ct_exp_acct,
            side='debit', amount=round(total_consumption_tax, 2),
            description=f"Porez na potrošnju POS smjena #{session.session_number}")

    # Verify balance
    if not je.is_balanced:
        import logging
        logging.getLogger(__name__).error(
            "POS booking NOT balanced! JE=%s debit=%s credit=%s",
            je.entry_number, je.total_debit, je.total_credit)
        # Fix rounding by adjusting revenue
        diff = je.total_debit - je.total_credit
        if abs(diff) < Decimal('0.10'):
            rev_line = je.lines.filter(side='credit', account__code=revenue_code).first()
            if rev_line:
                rev_line.amount += diff
                rev_line.save(update_fields=['amount'])

    return je


def calculate_po_sd(company, year):
    """
    PO-SD obrazac — Izvješće o paušalnom dohotku od samostalne djelatnosti.
    Za paušalne obrtnike (pdv_status='pausalic').

    Čl.82 Zakona o porezu na dohodak (NN 115/16)
    Primitci se razvrstavaju u razrede:
    - Razred 1: do 12.750 EUR godišnje → porez 1.530 EUR (12%)
    - Razred 2: 12.750-17.500 EUR → porez 2.100 EUR (12%)
    - Razred 3: 17.500-22.500 EUR → porez 2.700 EUR (12%)
    - Razred 4: 22.500-35.000 EUR → porez 4.200 EUR (12%)
    - Razred 5: 35.000-39.816,84 EUR → porez 4.778,02 EUR (12%)
    Prirez: ovisno o općini/gradu prebivališta (0-18%)
    """
    import datetime
    from invoicing.models import Invoice
    from django.db.models import Sum as DSum
    from konto.models import BankTransaction

    date_from = datetime.date(year, 1, 1)
    date_to = datetime.date(year, 12, 31)

    # Primitci iz izdanih računa
    invoice_primitci = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS', 'IRA'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).aggregate(t=DSum('total'))['t'] or Decimal('0')
    )

    # Primitci iz bankovnih uplata (backup ako nema faktura)
    bank_primitci = (
        BankTransaction.objects.filter(
            company=company,
            transaction_type='inflow',
            transaction_date__gte=date_from,
            transaction_date__lte=date_to,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0')
    )

    # Koristimo veći iznos (fakture ili banka)
    primitci = max(invoice_primitci, bank_primitci)

    # Razredi PO-SD (2024/2025 pragovi, NN 115/16 + izmjene)
    RAZREDI = [
        (Decimal('12750'), Decimal('1530.00'), '1'),
        (Decimal('17500'), Decimal('2100.00'), '2'),
        (Decimal('22500'), Decimal('2700.00'), '3'),
        (Decimal('35000'), Decimal('4200.00'), '4'),
        (Decimal('39816.84'), Decimal('4778.02'), '5'),
    ]

    razred = '0'
    pausal_porez = Decimal('0')
    gornja_granica = Decimal('0')

    for granica, porez, r in RAZREDI:
        if primitci <= granica:
            razred = r
            pausal_porez = porez
            gornja_granica = granica
            break
    else:
        # Prekoračen limit za paušalca!
        razred = 'PREKORAČEN'
        pausal_porez = Decimal('0')
        gornja_granica = RAZREDI[-1][0]

    # Prirez (default 0%, Marija može korigirati)
    prirez_rate = Decimal('0.10')  # 10% za Čepin (default)
    prirez = (pausal_porez * prirez_rate).quantize(Decimal('0.01'))
    ukupno = pausal_porez + prirez

    # Kvartalni pregled primitaka
    kvartali = []
    for q in range(1, 5):
        q_start = datetime.date(year, (q - 1) * 3 + 1, 1)
        if q < 4:
            q_end = datetime.date(year, q * 3 + 1, 1) - datetime.timedelta(days=1)
        else:
            q_end = date_to

        q_primitci = (
            Invoice.objects.filter(
                company=company,
                doctype__in=['R', 'A', 'GS', 'IRA'],
                status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
                date_issued__date__gte=q_start,
                date_issued__date__lte=q_end,
            ).aggregate(t=DSum('total'))['t'] or Decimal('0')
        )
        kvartali.append({
            'q': q,
            'start': q_start.strftime('%d.%m.'),
            'end': q_end.strftime('%d.%m.'),
            'primitci': float(q_primitci),
        })

    prekoracen = primitci > RAZREDI[-1][0]

    return {
        'year': year,
        'company_name': company.name,
        'oib': company.oib,
        'primitci_fakture': float(invoice_primitci),
        'primitci_banka': float(bank_primitci),
        'primitci': float(primitci),
        'razred': razred,
        'gornja_granica': float(gornja_granica),
        'pausal_porez': float(pausal_porez),
        'prirez_rate': float(prirez_rate * 100),
        'prirez': float(prirez),
        'ukupno_porez': float(ukupno),
        'kvartali': kvartali,
        'prekoracen': prekoracen,
        'napomena': 'UPOZORENJE: Primitci prelaze 39.816,84 EUR — obrtnik MORA prijeći u sustav PDV-a!' if prekoracen else '',
    }


def calculate_koerperschaftsteuer(company, year):
    """
    KSt — Körperschaftsteuer für GmbH/UG/AG.

    Steuersätze (2024/2025):
    - Körperschaftsteuer: 15% auf zu versteuerndes Einkommen
    - Solidaritätszuschlag: 5,5% auf KSt
    - Gewerbesteuer: Messbetrag (3,5%) × Hebesatz (Gemeinde)
    - Effektiver Steuersatz: ~30% (KSt + Soli + GewSt)

    Ref: KStG §23 Abs. 1, SolzG §4, GewStG §11
    """
    import datetime
    from .models import KontoAccount, LedgerLine
    from invoicing.models import Invoice
    from django.db.models import Sum as DSum

    date_from = datetime.date(year, 1, 1)
    date_to = datetime.date(year, 12, 31)

    # Revenue
    gross_revenue = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS', 'IRA'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).aggregate(t=DSum('subtotal'))['t'] or Decimal('0')
    )

    # Expenses
    exp_accts = KontoAccount.objects.filter(company=company, account_type='expense')
    total_expenses = Decimal('0')
    if exp_accts.exists():
        exp_d = (LedgerLine.objects.filter(
            account__in=exp_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        exp_c = (LedgerLine.objects.filter(
            account__in=exp_accts, side='credit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        total_expenses = exp_d - exp_c

    gewinn = max(gross_revenue - total_expenses, Decimal('0'))

    # Nicht abziehbare Aufwendungen (§10 KStG)
    # Bewirtung 30%, Geschenke >50 EUR, Geldbußen
    nicht_abziehbar = Decimal('0')
    na_codes = ['4650', '4600']  # Bewirtung, Werbekosten (Geschenke)
    na_accts = KontoAccount.objects.filter(company=company, code__in=na_codes)
    if na_accts.exists():
        na_d = (LedgerLine.objects.filter(
            account__in=na_accts, side='debit',
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            journal_entry__is_posted=True,
        ).aggregate(t=DSum('amount'))['t'] or Decimal('0'))
        nicht_abziehbar = (na_d * Decimal('0.30')).quantize(Decimal('0.01'))

    # Zu versteuerndes Einkommen
    zve = max(gewinn + nicht_abziehbar, Decimal('0'))

    # Körperschaftsteuer (15%)
    KST_RATE = Decimal('0.15')
    kst = (zve * KST_RATE).quantize(Decimal('0.01'))

    # Solidaritätszuschlag (5,5% auf KSt)
    SOLI_RATE = Decimal('0.055')
    soli = (kst * SOLI_RATE).quantize(Decimal('0.01'))

    # Gewerbesteuer
    MESSZAHL = Decimal('0.035')
    hebesatz = Decimal('4.00')  # 400% — Bundesdurchschnitt, anpassbar
    freibetrag = Decimal('24500')  # nur für Einzelunternehmen/PersGes, nicht GmbH

    # GmbH hat KEINEN Freibetrag bei GewSt
    is_kapitalgesellschaft = company.business_type in ('gmbh', 'ag', 'ug')
    if is_kapitalgesellschaft:
        gewerbe_gewinn = zve  # kein Freibetrag
    else:
        gewerbe_gewinn = max(zve - freibetrag, Decimal('0'))

    gewst_messbetrag = (gewerbe_gewinn * MESSZAHL).quantize(Decimal('0.01'))
    gewst = (gewst_messbetrag * hebesatz).quantize(Decimal('0.01'))

    total_tax = kst + soli + gewst
    effective_rate = float((total_tax / zve * 100) if zve else 0)

    return {
        'year': year,
        'country': 'DE',
        'company_name': company.name,
        'business_type': company.business_type,
        'gross_revenue': float(gross_revenue),
        'total_expenses': float(total_expenses),
        'gewinn': float(gewinn),
        'nicht_abziehbar': float(nicht_abziehbar),
        'zve': float(zve),
        'kst_rate': '15%',
        'kst': float(kst),
        'soli_rate': '5,5%',
        'soli': float(soli),
        'hebesatz': float(hebesatz * 100),
        'gewst_messbetrag': float(gewst_messbetrag),
        'gewst': float(gewst),
        'is_kapitalgesellschaft': is_kapitalgesellschaft,
        'total_tax': float(total_tax),
        'effective_rate': round(effective_rate, 1),
    }


def book_rental_booking(booking, user=None):
    """Book a rental booking into the ledger.

    Kratkoročni najam 500€ + PDV 65€ + boravišna pristojba 30€:
      D: 1200 Potraživanja od gostiju        595,00€
      P: 7100 Prihodi od najma               500,00€
      P: 2400 Obveze za PDV                   65,00€
      D: 2500 Obveze za boravišnu pristojbu   30,00€ (prolazna stavka)
      P: 1200 Potraživanja (pristojba)        30,00€
    """
    from .models import KontoAccount, JournalEntry, LedgerLine
    from decimal import Decimal

    company = booking.rental_property.company if hasattr(booking.rental_property, 'company') else None
    if not company:
        return None

    # Check if already booked
    prefix = f'RNT-{booking.pk}'
    if JournalEntry.objects.filter(company=company, entry_number__startswith=prefix).exists():
        return None

    subtotal = Decimal(str(booking.subtotal or 0))
    vat = Decimal(str(getattr(booking, 'vat_amount', 0) or 0))
    tourist_tax = Decimal(str(booking.tourist_tax_total or 0))
    total_guest = subtotal + vat  # What guest pays for accommodation

    if total_guest <= 0:
        return None

    je = JournalEntry.objects.create(
        company=company,
        entry_number=_next_entry_number(company, 'RNT'),
        date=booking.check_in,
        description=f'Najam {booking.rental_property.name} — {booking.guest_name} ({booking.check_in}–{booking.check_out})',
        source_type='manual',
        is_posted=True,
        created_by=user,
    )

    # D: Potraživanja od gostiju
    recv, _ = KontoAccount.objects.get_or_create(
        company=company, code='1200',
        defaults={'name': 'Potraživanja od kupaca', 'account_type': 'asset'})
    LedgerLine.objects.create(
        journal_entry=je, account=recv, side='debit',
        amount=total_guest + tourist_tax,
        description=f'Gost: {booking.guest_name}')

    # P: Prihodi od najma
    rev, _ = KontoAccount.objects.get_or_create(
        company=company, code='7100',
        defaults={'name': 'Prihodi od najma', 'account_type': 'income'})
    LedgerLine.objects.create(
        journal_entry=je, account=rev, side='credit',
        amount=subtotal,
        description=f'Najam {booking.check_in}–{booking.check_out}')

    # P: PDV
    if vat > 0:
        vat_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code='2400',
            defaults={'name': 'Obveze za PDV', 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=vat_acct, side='credit',
            amount=vat,
            description=f'PDV najam {booking.guest_name}')

    # Tourist tax: D:2500 / P:2500 (prolazna stavka — naplaćujemo za općinu)
    if tourist_tax > 0:
        tax_acct, _ = KontoAccount.objects.get_or_create(
            company=company, code='2500',
            defaults={'name': 'Obveze za boravišnu pristojbu', 'account_type': 'liability'})
        LedgerLine.objects.create(
            journal_entry=je, account=tax_acct, side='credit',
            amount=tourist_tax,
            description=f'Boravišna pristojba {booking.guest_name}')

    return je
