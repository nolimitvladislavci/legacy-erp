"""
konto/parsers.py
Unified bank statement parsers — camt.053 XML (SEPA), CSV (FINA/HR banke), MT940 (SWIFT).

Thin facade over konto.services.bank_import parsers with dedup + BankTransaction creation.
"""
import logging
import uuid
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


def parse_camt053(xml_content, bank_account, company):
    """
    Parse ISO 20022 camt.053 XML and create BankTransaction records.
    Supports namespace versions .001.02 and .001.08.
    Dedup: skips entries where external_id already exists.
    Returns: list of created BankTransaction objects.
    """
    from konto.services.bank_import import parse_camt053 as _parse, import_bank_statement_from_parsed
    from konto.models import BankTransaction, BankAccount, KontoAccount

    data = _parse(xml_content)

    # Auto-resolve bank account from IBAN if not provided
    if not bank_account and data.get('iban'):
        bank_account = BankAccount.objects.filter(
            company=company, iban=data['iban']
        ).first()
        if not bank_account:
            konto, _ = KontoAccount.objects.get_or_create(
                company=company, code='1000',
                defaults={'name': 'Žiro račun u banci', 'account_type': 'asset'})
            bank_account = BankAccount.objects.create(
                company=company,
                name=f'Račun {data["iban"][-8:]}',
                iban=data['iban'],
                bank_name='',
                konto_account=konto,
                current_balance=data.get('balance', Decimal('0')),
            )

    batch_id = f'camt053_{uuid.uuid4().hex[:12]}'
    created = []
    skipped = 0

    from datetime import date as _date

    for tx in data['transactions']:
        # Dedup by external_id
        ext_id = tx.get('external_id', '')
        if ext_id and BankTransaction.objects.filter(company=company, external_id=ext_id).exists():
            skipped += 1
            continue

        # Dedup fallback: date + amount + reference combo
        if not ext_id:
            ext_id = f'camt_{tx["booking_date"]}_{tx["amount"]}_{tx.get("reference", "")}'
            if BankTransaction.objects.filter(company=company, external_id=ext_id).exists():
                skipped += 1
                continue

        try:
            booking = _date.fromisoformat(tx['booking_date']) if tx['booking_date'] else timezone.now().date()
        except (ValueError, TypeError):
            booking = timezone.now().date()

        try:
            value = _date.fromisoformat(tx['value_date']) if tx.get('value_date') else booking
        except (ValueError, TypeError):
            value = booking

        try:
            obj = BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking,
                value_date=value,
                amount=Decimal(str(tx['amount'])).quantize(Decimal('0.01')),
                transaction_type=tx['direction'],
                counterparty_name=tx.get('counterparty_name', '')[:300],
                counterparty_iban=tx.get('counterparty_iban', '')[:34],
                description=tx.get('description', ''),
                reference_number=tx.get('reference', '')[:100],
                external_id=ext_id[:200],
                import_batch=batch_id,
                status='unmatched',
            )
            created.append(obj)
        except Exception as e:
            logger.warning(f'camt053 import error: {e}')

    # Update balance
    if bank_account:
        bank_account.recalculate_balance()

    logger.info(f'camt053 import: {len(created)} created, {skipped} skipped, batch={batch_id}')
    return created


def parse_csv_fina(csv_content, bank_account, company):
    """
    Parse FINA CSV bank statement (HR banke — PBZ, ZABA, RBA).
    Auto-detects delimiter (tab, semicolon, comma).
    Dedup: reference + date + amount combo.
    Returns: list of created BankTransaction objects.
    """
    import csv
    import io
    from decimal import InvalidOperation
    from datetime import datetime
    from konto.models import BankTransaction

    content = csv_content.strip()

    # Auto-detect delimiter
    first_line = content.split('\n')[0]
    if '\t' in first_line:
        delimiter = '\t'
    elif ';' in first_line:
        delimiter = ';'
    else:
        delimiter = ','

    # Try to detect encoding issues — BOM removal
    if content.startswith('\ufeff'):
        content = content[1:]

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError('CSV datoteka je prazna ili nema zaglavlje.')

    # Column auto-mapping for HR/DE/EN headers
    col_map = {}
    for col in reader.fieldnames:
        cl = col.lower().strip().replace('\ufeff', '')
        if any(k in cl for k in ('datum', 'date', 'buchungstag', 'dt. knjiženja', 'dt.knjizenja',
                                   'datum knjiženja', 'datum transakcije')):
            col_map['date'] = col
        elif any(k in cl for k in ('datum valute', 'value date', 'wertstellung', 'valuta')):
            col_map['value_date'] = col
        elif any(k in cl for k in ('iznos', 'amount', 'betrag', 'suma', 'promet')):
            col_map['amount'] = col
        elif any(k in cl for k in ('opis', 'description', 'verwendungszweck', 'purpose',
                                    'namjena', 'opis plaćanja', 'opis placanja')):
            col_map['description'] = col
        elif any(k in cl for k in ('platitelj', 'counterparty', 'auftraggeber', 'primatelj',
                                    'empfänger', 'name', 'naziv platitelja', 'naziv primatelja')):
            col_map['counterparty'] = col
        elif any(k in cl for k in ('referenc', 'reference', 'poziv na broj', 'poziv',
                                    'kundenreferenz', 'model i poziv')):
            col_map['reference'] = col
        elif any(k in cl for k in ('iban', 'račun platitelja', 'račun primatelja',
                                    'racun platitelja', 'racun primatelja')):
            col_map['iban'] = col
        elif any(k in cl for k in ('tip', 'vrsta', 'type', 'smjer')):
            col_map['type'] = col

    if 'date' not in col_map or 'amount' not in col_map:
        raise ValueError(
            f'Ne mogu detektirati stupce datum/iznos. Pronađeni stupci: {reader.fieldnames}'
        )

    batch_id = f'csv_{uuid.uuid4().hex[:12]}'
    created = []
    skipped = 0

    for row in reader:
        try:
            # Parse amount — HR format: 1.234,56 → 1234.56
            amt_str = row.get(col_map['amount'], '0').strip()
            # Remove thousands separator (. in HR, , in EN)
            if ',' in amt_str and '.' in amt_str:
                # HR format: 1.234,56
                if amt_str.rindex(',') > amt_str.rindex('.'):
                    amt_str = amt_str.replace('.', '').replace(',', '.')
                else:
                    # EN format: 1,234.56
                    amt_str = amt_str.replace(',', '')
            elif ',' in amt_str:
                amt_str = amt_str.replace(',', '.')

            amount = Decimal(amt_str)
            direction = 'inflow' if amount >= 0 else 'outflow'
            amount = abs(amount)

            if amount == 0:
                continue

            # Parse date
            date_str = row.get(col_map['date'], '').strip()
            booking_date = None
            for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y.', '%Y-%m-%dT%H:%M:%S'):
                try:
                    booking_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            if not booking_date:
                continue

            # Value date
            value_date = booking_date
            if 'value_date' in col_map:
                vd_str = row.get(col_map['value_date'], '').strip()
                if vd_str:
                    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            value_date = datetime.strptime(vd_str, fmt).date()
                            break
                        except ValueError:
                            continue

            # Inflow/outflow override from type column
            if 'type' in col_map:
                tip = row.get(col_map['type'], '').strip().lower()
                if tip in ('uplata', 'credit', 'priljev', 'cr', 'c'):
                    direction = 'inflow'
                elif tip in ('isplata', 'debit', 'odljev', 'db', 'd'):
                    direction = 'outflow'

            reference = row.get(col_map.get('reference', ''), '')[:100].strip()
            description = row.get(col_map.get('description', ''), '')[:500].strip()
            counterparty = row.get(col_map.get('counterparty', ''), '')[:300].strip()
            iban = row.get(col_map.get('iban', ''), '')[:34].strip()

            # Dedup: reference + date + amount combo
            dedup_key = f'csv_{booking_date}_{amount}_{reference}'
            if BankTransaction.objects.filter(company=company, external_id=dedup_key).exists():
                skipped += 1
                continue

            obj = BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking_date,
                value_date=value_date,
                amount=amount.quantize(Decimal('0.01')),
                transaction_type=direction,
                counterparty_name=counterparty,
                counterparty_iban=iban,
                description=description,
                reference_number=reference,
                external_id=dedup_key[:200],
                import_batch=batch_id,
                status='unmatched',
            )
            created.append(obj)

        except (ValueError, InvalidOperation) as e:
            logger.debug(f'CSV row skip: {e}')
            continue

    if bank_account:
        bank_account.recalculate_balance()

    logger.info(f'CSV FINA import: {len(created)} created, {skipped} skipped, batch={batch_id}')
    return created


def parse_mt940(content, bank_account, company):
    """
    Parse SWIFT MT940 bank statement format.
    Tag :61: for transactions, :86: for details.
    Returns: list of created BankTransaction objects.
    """
    from konto.services.bank_import import parse_mt940 as _parse
    from konto.models import BankTransaction, BankAccount, KontoAccount

    data = _parse(content)

    # Auto-resolve bank account
    if not bank_account and data.get('iban'):
        bank_account = BankAccount.objects.filter(
            company=company, iban=data['iban']
        ).first()
        if not bank_account:
            konto, _ = KontoAccount.objects.get_or_create(
                company=company, code='1000',
                defaults={'name': 'Žiro račun u banci', 'account_type': 'asset'})
            bank_account = BankAccount.objects.create(
                company=company,
                name=f'Račun MT940',
                iban=data.get('iban', ''),
                bank_name='',
                konto_account=konto,
                current_balance=data.get('balance', Decimal('0')),
            )

    batch_id = f'mt940_{uuid.uuid4().hex[:12]}'
    created = []
    skipped = 0

    from datetime import date as _date

    for tx in data['transactions']:
        ext_id = tx.get('external_id', '')
        if ext_id and BankTransaction.objects.filter(company=company, external_id=ext_id).exists():
            skipped += 1
            continue

        try:
            booking = _date.fromisoformat(tx['booking_date']) if tx['booking_date'] else timezone.now().date()
        except (ValueError, TypeError):
            booking = timezone.now().date()

        try:
            value = _date.fromisoformat(tx['value_date']) if tx.get('value_date') else booking
        except (ValueError, TypeError):
            value = booking

        try:
            obj = BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking,
                value_date=value,
                amount=Decimal(str(tx['amount'])).quantize(Decimal('0.01')),
                transaction_type=tx['direction'],
                counterparty_name=tx.get('counterparty_name', '')[:300],
                counterparty_iban=tx.get('counterparty_iban', '')[:34],
                description=tx.get('description', ''),
                reference_number=tx.get('reference', '')[:100],
                external_id=ext_id[:200],
                import_batch=batch_id,
                status='unmatched',
            )
            created.append(obj)
        except Exception as e:
            logger.warning(f'MT940 import error: {e}')

    if bank_account:
        bank_account.recalculate_balance()

    logger.info(f'MT940 import: {len(created)} created, {skipped} skipped, batch={batch_id}')
    return created
