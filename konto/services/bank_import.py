"""
konto/services/bank_import.py
camt.053 parser + bank statement import + auto-reconciliation.
"""
import re
import logging
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from django.utils import timezone

logger = logging.getLogger(__name__)

NS = {'camt': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02'}


def _text(el, xpath, ns=None, default=''):
    node = el.find(xpath, ns or NS)
    if node is None:
        # Try without namespace
        node = el.find(xpath.replace('camt:', ''))
    return (node.text or '').strip() if node is not None else default


def _dec(val, default=Decimal('0')):
    try:
        return Decimal(str(val).replace(',', '.')) if val else default
    except (InvalidOperation, ValueError):
        return default


def parse_camt053(xml_string):
    """
    Parse camt.053 XML (bank statement) into structured data.
    Returns: {'iban': str, 'balance': Decimal, 'transactions': [dict]}
    """
    # Try parsing with namespace, fallback without
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ValueError(f'Invalid XML: {e}')

    # Auto-detect namespace
    ns = {}
    tag = root.tag
    if '{' in tag:
        ns_uri = tag.split('{')[1].split('}')[0]
        ns = {'ns': ns_uri}
        prefix = 'ns:'
    else:
        prefix = ''

    # Find Statement
    stmt = root.find(f'.//{prefix}Stmt', ns)
    if stmt is None:
        stmt = root.find(f'.//{prefix}BkToCstmrStmt/{prefix}Stmt', ns)
    if stmt is None:
        # Try any Stmt element
        for elem in root.iter():
            if elem.tag.endswith('Stmt'):
                stmt = elem
                break
    if stmt is None:
        raise ValueError('No Stmt element found in camt.053')

    # IBAN
    iban = ''
    acct = stmt.find(f'.//{prefix}Acct/{prefix}Id/{prefix}IBAN', ns)
    if acct is not None:
        iban = acct.text.strip()

    # Balance
    balance = Decimal('0')
    for bal in stmt.findall(f'{prefix}Bal', ns):
        tp = bal.find(f'{prefix}Tp/{prefix}CdOrPrtry/{prefix}Cd', ns)
        if tp is not None and tp.text in ('CLBD', 'CLAV', 'OPBD'):
            amt = bal.find(f'{prefix}Amt', ns)
            if amt is not None:
                balance = _dec(amt.text)

    # Transactions
    transactions = []
    for ntry in stmt.findall(f'{prefix}Ntry', ns):
        amt_el = ntry.find(f'{prefix}Amt', ns)
        amount = _dec(amt_el.text if amt_el is not None else '0')
        currency = amt_el.get('Ccy', 'EUR') if amt_el is not None else 'EUR'

        # Direction
        cdi = ntry.find(f'{prefix}CdtDbtInd', ns)
        direction = 'inflow' if (cdi is not None and cdi.text == 'CRDT') else 'outflow'

        # Dates
        booking_date = ''
        bd = ntry.find(f'{prefix}BookgDt/{prefix}Dt', ns)
        if bd is not None:
            booking_date = bd.text.strip()

        value_date = ''
        vd = ntry.find(f'{prefix}ValDt/{prefix}Dt', ns)
        if vd is not None:
            value_date = vd.text.strip()

        # Transaction details
        txdtls = ntry.find(f'.//{prefix}TxDtls', ns)

        description = ''
        counterparty_name = ''
        counterparty_iban = ''
        reference = ''
        external_id = ''

        if txdtls is not None:
            # Remittance info
            ustrd = txdtls.find(f'.//{prefix}RmtInf/{prefix}Ustrd', ns)
            if ustrd is not None:
                description = ustrd.text.strip()

            # Structured reference
            strd = txdtls.find(f'.//{prefix}RmtInf/{prefix}Strd/{prefix}CdtrRefInf/{prefix}Ref', ns)
            if strd is not None:
                reference = strd.text.strip()

            # Counterparty
            for party_tag in ['Dbtr', 'Cdtr']:
                party = txdtls.find(f'.//{prefix}RltdPties/{prefix}{party_tag}', ns)
                if party is not None:
                    nm = party.find(f'{prefix}Nm', ns)
                    if nm is not None:
                        counterparty_name = nm.text.strip()
                    break

            # Counterparty IBAN
            for acct_tag in ['DbtrAcct', 'CdtrAcct']:
                acct = txdtls.find(f'.//{prefix}RltdPties/{prefix}{acct_tag}/{prefix}Id/{prefix}IBAN', ns)
                if acct is not None:
                    counterparty_iban = acct.text.strip()
                    break

            # External ID
            eid = txdtls.find(f'.//{prefix}Refs/{prefix}EndToEndId', ns)
            if eid is not None:
                external_id = eid.text.strip()

        # Fallback: description from entry level
        if not description:
            info = ntry.find(f'.//{prefix}AddtlNtryInf', ns)
            if info is not None:
                description = info.text.strip()

        # Extract reference from description if not found
        if not reference and description:
            ref_match = re.search(r'(?:HR\d{2})?\s*(\d{2}-\d+-\d+|\d{10,})', description)
            if ref_match:
                reference = ref_match.group(1)

        transactions.append({
            'amount': amount,
            'currency': currency,
            'direction': direction,
            'booking_date': booking_date,
            'value_date': value_date or booking_date,
            'counterparty_name': counterparty_name,
            'counterparty_iban': counterparty_iban,
            'description': description,
            'reference': reference,
            'external_id': external_id,
        })

    return {
        'iban': iban,
        'balance': balance,
        'currency': currency if transactions else 'EUR',
        'transactions': transactions,
    }


def import_bank_statement(company, bank_account, xml_string, batch_id=None):
    """
    Import camt.053 bank statement into BankTransaction records.
    Returns: {created: int, skipped: int, errors: int}
    """
    from konto.models import BankTransaction

    data = parse_camt053(xml_string)

    if not batch_id:
        batch_id = f'camt053_{timezone.now().strftime("%Y%m%d_%H%M%S")}'

    created = skipped = errors = 0
    from datetime import date as _date

    for tx in data['transactions']:
        try:
            # Dedup by external_id
            if tx['external_id']:
                if BankTransaction.objects.filter(company=company, external_id=tx['external_id']).exists():
                    skipped += 1
                    continue

            # Parse date
            booking = None
            for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%Y%m%d'):
                try:
                    booking = _date.fromisoformat(tx['booking_date']) if '-' in tx['booking_date'] else None
                    if not booking:
                        from datetime import datetime
                        booking = datetime.strptime(tx['booking_date'], fmt).date()
                    break
                except (ValueError, TypeError):
                    continue
            if not booking:
                booking = timezone.now().date()

            value = None
            if tx['value_date']:
                try:
                    value = _date.fromisoformat(tx['value_date'])
                except (ValueError, TypeError):
                    value = booking

            BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking,
                value_date=value,
                amount=tx['amount'],
                transaction_type=tx['direction'],
                counterparty_name=tx['counterparty_name'],
                counterparty_iban=tx['counterparty_iban'],
                description=tx['description'],
                reference_number=tx['reference'],
                external_id=tx['external_id'],
                import_batch=batch_id,
                status='unmatched',
            )
            created += 1

        except Exception as e:
            errors += 1
            logger.warning(f'Bank import error: {e}')

    # Update bank account balance
    if bank_account and data['balance']:
        bank_account.current_balance = data['balance']
        bank_account.save(update_fields=['current_balance', 'updated_at'])

    return {'created': created, 'skipped': skipped, 'errors': errors, 'batch_id': batch_id}


def auto_reconcile(company):
    """
    Auto-match unmatched bank transactions to open invoices.
    Matching strategy:
    1. Reference number contains invoice number
    2. Amount matches + counterparty OIB matches client OIB
    3. Amount matches + counterparty name fuzzy matches client name
    """
    from konto.models import BankTransaction
    from invoicing.models import Invoice

    unmatched = BankTransaction.objects.filter(
        company=company, status='unmatched', transaction_type='inflow'
    )
    open_invoices = Invoice.objects.filter(
        company=company, status__in=['SENT', 'CONFIRMED', 'FISCALIZED', 'UNPAID', 'OVERDUE']
    )

    matched = 0

    for tx in unmatched:
        invoice = None

        # Strategy 1: reference contains invoice number
        if tx.reference_number:
            invoice = open_invoices.filter(number__icontains=tx.reference_number).first()

        # Strategy 2: exact amount + description contains invoice number
        if not invoice and tx.description:
            for inv in open_invoices.filter(total=tx.amount):
                if inv.number in tx.description:
                    invoice = inv
                    break

        # Strategy 3: exact amount + counterparty name matches client
        if not invoice and tx.counterparty_name:
            cn = tx.counterparty_name.upper()[:20]
            for inv in open_invoices.filter(total=tx.amount):
                if inv.client_name and cn in inv.client_name.upper():
                    invoice = inv
                    break

        if invoice:
            tx.matched_invoice = invoice
            tx.status = 'matched'
            tx.save(update_fields=['matched_invoice', 'status'])

            invoice.status = 'PAID'
            invoice.save(update_fields=['status'])

            matched += 1

    return {'matched': matched, 'remaining': unmatched.filter(status='unmatched').count()}
