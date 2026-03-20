"""
konto/booking_engine.py
Automatic double-entry bookkeeping from matched bank transactions.

Rules:
  - Inflow + matched invoice → Debit 1000 (Ziro), Credit 1200 (Kupci)
  - Outflow + matched invoice → Debit 2200 (Dobavljaci), Credit 1000 (Ziro)
  - Unmatched → skip (manual booking required)

Uses KontoAccount FK lookup, not hardcoded account codes.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default account codes (HR RRiF standard kontni plan)
DEFAULT_ACCOUNTS = {
    'ziro': '1000',       # Ziro racun
    'kupci': '1200',      # Potrazivanja od kupaca
    'dobavljaci': '2200', # Obveze prema dobavljacima
}


def book_bank_transaction(bank_txn):
    """
    Creates a JournalEntry with double-entry lines for a matched BankTransaction.

    Returns the JournalEntry or None if booking was skipped.
    Raises nothing — logs errors instead.
    """
    from konto.models import KontoAccount, JournalEntry, LedgerLine

    # Guard: already booked
    if bank_txn.is_booked:
        return None

    # Guard: must be matched
    if bank_txn.status != 'matched':
        return None

    # Guard: must have a matched invoice for auto-booking
    if not bank_txn.matched_invoice:
        return None

    company = bank_txn.company
    if not company:
        logger.warning(f"BankTransaction {bank_txn.pk} has no company — skipping booking")
        return None

    try:
        with transaction.atomic():
            # Resolve accounts
            ziro_acct = _get_account(company, DEFAULT_ACCOUNTS['ziro'], 'Ziro racun')
            if bank_txn.transaction_type == 'inflow':
                contra_code = DEFAULT_ACCOUNTS['kupci']
                contra_name = 'Potrazivanja od kupaca'
            else:
                contra_code = DEFAULT_ACCOUNTS['dobavljaci']
                contra_name = 'Obveze prema dobavljacima'

            contra_acct = _get_account(company, contra_code, contra_name)

            if not ziro_acct or not contra_acct:
                logger.error(
                    f"Missing konto accounts for company {company.pk}. "
                    f"Need: {DEFAULT_ACCOUNTS['ziro']} and {contra_code}. "
                    f"Run kontni plan setup first."
                )
                return None

            # Generate entry number
            today = timezone.now().date()
            count = JournalEntry.objects.filter(
                company=company,
                date=today,
                source_type='bank_statement',
            ).count()
            entry_number = f"BK-{today.strftime('%Y%m%d')}-{count + 1:04d}"

            inv = bank_txn.matched_invoice
            inv_label = getattr(inv, 'number', str(inv.pk)) if inv else ''

            # Create journal entry
            entry = JournalEntry.objects.create(
                company=company,
                entry_number=entry_number,
                date=bank_txn.transaction_date,
                description=f"Izvod: {bank_txn.counterparty_name[:80]} / {inv_label}",
                source_type='bank_statement',
                source_invoice=inv,
                source_transaction=bank_txn,
                is_posted=True,
            )

            amount = bank_txn.amount  # Always positive

            if bank_txn.transaction_type == 'inflow':
                # Inflow: Debit Ziro, Credit Kupci
                LedgerLine.objects.create(
                    journal_entry=entry,
                    account=ziro_acct,
                    side='debit',
                    amount=amount,
                    description=f"Uplata: {bank_txn.counterparty_name[:100]}",
                )
                LedgerLine.objects.create(
                    journal_entry=entry,
                    account=contra_acct,
                    side='credit',
                    amount=amount,
                    description=f"Zatvaranje: {inv_label}",
                )
            else:
                # Outflow: Debit Dobavljaci, Credit Ziro
                LedgerLine.objects.create(
                    journal_entry=entry,
                    account=contra_acct,
                    side='debit',
                    amount=amount,
                    description=f"Placanje: {inv_label}",
                )
                LedgerLine.objects.create(
                    journal_entry=entry,
                    account=ziro_acct,
                    side='credit',
                    amount=amount,
                    description=f"Isplata: {bank_txn.counterparty_name[:100]}",
                )

            # Mark as booked
            bank_txn.is_booked = True
            bank_txn.save(update_fields=['is_booked'])

            logger.info(
                f"Auto-booked BankTransaction {bank_txn.pk} → "
                f"JournalEntry {entry.entry_number} "
                f"({amount} EUR, {bank_txn.transaction_type})"
            )
            return entry

    except Exception:
        logger.exception(f"Failed to book BankTransaction {bank_txn.pk}")
        return None


def _get_account(company, code, fallback_name):
    """Get or auto-create a KontoAccount by code for the company."""
    from konto.models import KontoAccount

    try:
        return KontoAccount.objects.get(company=company, code=code)
    except KontoAccount.DoesNotExist:
        # Auto-create with sensible defaults
        account_type = 'asset'
        if code.startswith('2'):
            account_type = 'liability'
        elif code.startswith(('4', '5', '6')):
            account_type = 'expense'
        elif code.startswith('7'):
            account_type = 'income'

        acct = KontoAccount.objects.create(
            company=company,
            code=code,
            name=fallback_name,
            account_type=account_type,
            is_active=True,
        )
        logger.info(f"Auto-created KontoAccount {code} - {fallback_name} for company {company.pk}")
        return acct
