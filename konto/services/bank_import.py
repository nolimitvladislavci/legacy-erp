"""
konto/services/bank_import.py
camt.053 parser + bank statement import + auto-reconciliation.
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from django.db import DatabaseError, IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)

NS = {"camt": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"}


def _text(el, xpath, ns=None, default=""):
    node = el.find(xpath, ns or NS)
    if node is None:
        # Try without namespace
        node = el.find(xpath.replace("camt:", ""))
    return (node.text or "").strip() if node is not None else default


def _dec(val, default=Decimal("0")):
    try:
        return Decimal(str(val).replace(",", ".")) if val else default
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
        raise ValueError(f"Invalid XML: {e}")

    # Auto-detect namespace
    ns = {}
    tag = root.tag
    if "{" in tag:
        ns_uri = tag.split("{")[1].split("}")[0]
        ns = {"ns": ns_uri}
        prefix = "ns:"
    else:
        prefix = ""

    # Find Statement
    stmt = root.find(f".//{prefix}Stmt", ns)
    if stmt is None:
        stmt = root.find(f".//{prefix}BkToCstmrStmt/{prefix}Stmt", ns)
    if stmt is None:
        # Try any Stmt element
        for elem in root.iter():
            if elem.tag.endswith("Stmt"):
                stmt = elem
                break
    if stmt is None:
        raise ValueError("No Stmt element found in camt.053")

    # IBAN
    iban = ""
    acct = stmt.find(f".//{prefix}Acct/{prefix}Id/{prefix}IBAN", ns)
    if acct is not None:
        iban = acct.text.strip()

    # Balance
    balance = Decimal("0")
    for bal in stmt.findall(f"{prefix}Bal", ns):
        tp = bal.find(f"{prefix}Tp/{prefix}CdOrPrtry/{prefix}Cd", ns)
        if tp is not None and tp.text in ("CLBD", "CLAV", "OPBD"):
            amt = bal.find(f"{prefix}Amt", ns)
            if amt is not None:
                balance = _dec(amt.text)

    # Transactions
    transactions = []
    for ntry in stmt.findall(f"{prefix}Ntry", ns):
        amt_el = ntry.find(f"{prefix}Amt", ns)
        amount = _dec(amt_el.text if amt_el is not None else "0")
        currency = amt_el.get("Ccy", "EUR") if amt_el is not None else "EUR"

        # Direction
        cdi = ntry.find(f"{prefix}CdtDbtInd", ns)
        direction = "inflow" if (cdi is not None and cdi.text == "CRDT") else "outflow"

        # Dates
        booking_date = ""
        bd = ntry.find(f"{prefix}BookgDt/{prefix}Dt", ns)
        if bd is not None:
            booking_date = bd.text.strip()

        value_date = ""
        vd = ntry.find(f"{prefix}ValDt/{prefix}Dt", ns)
        if vd is not None:
            value_date = vd.text.strip()

        # Transaction details
        txdtls = ntry.find(f".//{prefix}TxDtls", ns)

        description = ""
        counterparty_name = ""
        counterparty_iban = ""
        reference = ""
        external_id = ""

        if txdtls is not None:
            # Remittance info
            ustrd = txdtls.find(f".//{prefix}RmtInf/{prefix}Ustrd", ns)
            if ustrd is not None:
                description = ustrd.text.strip()

            # Structured reference
            strd = txdtls.find(f".//{prefix}RmtInf/{prefix}Strd/{prefix}CdtrRefInf/{prefix}Ref", ns)
            if strd is not None:
                reference = strd.text.strip()

            # Counterparty
            for party_tag in ["Dbtr", "Cdtr"]:
                party = txdtls.find(f".//{prefix}RltdPties/{prefix}{party_tag}", ns)
                if party is not None:
                    nm = party.find(f"{prefix}Nm", ns)
                    if nm is not None:
                        counterparty_name = nm.text.strip()
                    break

            # Counterparty IBAN
            for acct_tag in ["DbtrAcct", "CdtrAcct"]:
                acct = txdtls.find(f".//{prefix}RltdPties/{prefix}{acct_tag}/{prefix}Id/{prefix}IBAN", ns)
                if acct is not None:
                    counterparty_iban = acct.text.strip()
                    break

            # External ID
            eid = txdtls.find(f".//{prefix}Refs/{prefix}EndToEndId", ns)
            if eid is not None:
                external_id = eid.text.strip()

        # Fallback: description from entry level
        if not description:
            info = ntry.find(f".//{prefix}AddtlNtryInf", ns)
            if info is not None:
                description = info.text.strip()

        # Extract reference from description if not found
        if not reference and description:
            ref_match = re.search(r"(?:HR\d{2})?\s*(\d{2}-\d+-\d+|\d{10,})", description)
            if ref_match:
                reference = ref_match.group(1)

        transactions.append(
            {
                "amount": amount,
                "currency": currency,
                "direction": direction,
                "booking_date": booking_date,
                "value_date": value_date or booking_date,
                "counterparty_name": counterparty_name,
                "counterparty_iban": counterparty_iban,
                "description": description,
                "reference": reference,
                "external_id": external_id,
            }
        )

    return {
        "iban": iban,
        "balance": balance,
        "currency": currency if transactions else "EUR",
        "transactions": transactions,
    }


def import_bank_statement(company, bank_account, xml_string, batch_id=None):
    """
    Import camt.053 bank statement into BankTransaction records.
    Returns: {created: int, skipped: int, errors: int}
    """
    from konto.models import BankTransaction

    data = parse_camt053(xml_string)

    if not batch_id:
        batch_id = f"camt053_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

    created = skipped = errors = 0
    from datetime import date as _date

    for tx in data["transactions"]:
        try:
            # Dedup by external_id
            if tx["external_id"]:
                if BankTransaction.objects.filter(company=company, external_id=tx["external_id"]).exists():
                    skipped += 1
                    continue

            # Parse date
            booking = None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"):
                try:
                    booking = _date.fromisoformat(tx["booking_date"]) if "-" in tx["booking_date"] else None
                    if not booking:
                        from datetime import datetime

                        booking = datetime.strptime(tx["booking_date"], fmt).date()
                    break
                except (ValueError, TypeError):
                    continue
            if not booking:
                booking = timezone.now().date()

            value = None
            if tx["value_date"]:
                try:
                    value = _date.fromisoformat(tx["value_date"])
                except (ValueError, TypeError):
                    value = booking

            BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking,
                value_date=value,
                amount=tx["amount"],
                transaction_type=tx["direction"],
                counterparty_name=tx["counterparty_name"],
                counterparty_iban=tx["counterparty_iban"],
                description=tx["description"],
                reference_number=tx["reference"],
                external_id=tx["external_id"],
                import_batch=batch_id,
                status="unmatched",
            )
            created += 1

        except ValueError as e:
            errors += 1
            logger.warning(f"Bank import error: {e}")

    # Update bank account balance
    if bank_account and data["balance"]:
        bank_account.current_balance = data["balance"]
        bank_account.save(update_fields=["current_balance", "updated_at"])

    return {"created": created, "skipped": skipped, "errors": errors, "batch_id": batch_id}


def auto_reconcile(company):
    """
    Auto-match unmatched bank transactions to open invoices.
    Matching strategy:
    1. Reference number contains invoice number
    2. Amount matches + counterparty OIB matches client OIB
    3. Amount matches + counterparty name fuzzy matches client name
    """
    from invoicing.models import Invoice
    from konto.models import BankTransaction

    unmatched = BankTransaction.objects.filter(company=company, status="unmatched", transaction_type="inflow")
    open_invoices = Invoice.objects.filter(
        company=company, status__in=["SENT", "CONFIRMED", "FISCALIZED", "UNPAID", "OVERDUE"]
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
            tx.status = "matched"
            tx.save(update_fields=["matched_invoice", "status"])

            invoice.status = "PAID"
            invoice.save(update_fields=["status"])

            matched += 1

    return {"matched": matched, "remaining": unmatched.filter(status="unmatched").count()}


# ═══════════════════════════════════════════════════
#  MT940 (SWIFT) PARSER
# ═══════════════════════════════════════════════════


def parse_mt940(content):
    """
    Parse MT940 (SWIFT) bank statement format.
    Returns same structure as parse_camt053: {'iban': str, 'balance': Decimal, 'transactions': [dict]}

    MT940 structure:
    :20: Transaction reference
    :25: Account (IBAN or account number)
    :60F: Opening balance
    :61: Transaction line
    :86: Transaction details
    :62F: Closing balance
    """
    iban = ""
    balance = Decimal("0")
    transactions = []

    lines = content.replace("\r\n", "\n").split("\n")
    i = 0
    current_tx = None

    while i < len(lines):
        line = lines[i].strip()

        # Account identification :25:
        if line.startswith(":25:"):
            acct = line[4:]
            # May be IBAN or BLZ/account
            if re.match(r"[A-Z]{2}\d{2}", acct):
                iban = acct.replace("/", "").strip()
            else:
                iban = acct.strip()

        # Closing balance :62F: or :62M:
        elif line.startswith(":62F:") or line.startswith(":62M:"):
            bal_str = line[5:]
            # Format: C/D YYMMDD EUR amount
            direction = bal_str[0]  # C=credit, D=debit
            amt_str = bal_str[10:].replace(",", ".")  # After date+currency
            try:
                balance = Decimal(amt_str)
                if direction == "D":
                    balance = -balance
            except (InvalidOperation, ValueError):
                pass

        # Transaction line :61:
        elif line.startswith(":61:"):
            if current_tx:
                transactions.append(current_tx)

            tx_line = line[4:]
            # Format: YYMMDD[YYMMDD]RC amount N... //reference
            booking_date = ""
            value_date = ""
            amount = Decimal("0")
            direction = "inflow"

            try:
                # Date: YYMMDD
                yy = tx_line[:2]
                year = int(yy) + 2000
                month = int(tx_line[2:4])
                day = int(tx_line[4:6])
                booking_date = f"{year}-{month:02d}-{day:02d}"

                # Value date may follow
                offset = 6
                if tx_line[6:10].isdigit():
                    vy = int(tx_line[6:8]) + 2000
                    vm = int(tx_line[8:10])
                    vd = int(tx_line[10:12])
                    value_date = f"{vy}-{vm:02d}-{vd:02d}"
                    offset = 12

                # C/D indicator + optional RC code
                cd = tx_line[offset]
                if cd in ("C", "c"):
                    direction = "inflow"
                elif cd in ("D", "d"):
                    direction = "outflow"
                elif cd == "R":
                    cd2 = tx_line[offset + 1]
                    direction = "outflow" if cd2 in ("C", "c") else "inflow"  # Reversal
                    offset += 1
                offset += 1

                # Amount: digits and comma until N or F
                amt_match = re.search(r"([\d,]+)", tx_line[offset:])
                if amt_match:
                    amount = Decimal(amt_match.group(1).replace(",", "."))

                # Reference after //
                reference = ""
                if "//" in tx_line:
                    reference = tx_line.split("//")[1].strip()

            except (ValueError, IndexError):
                pass

            current_tx = {
                "amount": amount,
                "currency": "EUR",
                "direction": direction,
                "booking_date": booking_date or "",
                "value_date": value_date or booking_date,
                "counterparty_name": "",
                "counterparty_iban": "",
                "description": "",
                "reference": reference if "reference" in dir() else "",
                "external_id": f"mt940_{booking_date}_{amount}_{len(transactions)}",
            }

        # Transaction details :86:
        elif line.startswith(":86:") and current_tx:
            detail = line[4:]
            # Continuation lines (no tag)
            while i + 1 < len(lines) and not lines[i + 1].strip().startswith(":"):
                i += 1
                detail += " " + lines[i].strip()

            # Parse structured :86: fields (?20= description, ?32= counterparty)
            if "?" in detail:
                fields = {}
                for match in re.finditer(r"\?(\d{2})([^?]*)", detail):
                    fields[match.group(1)] = match.group(2).strip()

                current_tx["description"] = " ".join(
                    fields.get(f"{i:02d}", "") for i in range(20, 30) if fields.get(f"{i:02d}")
                ).strip()
                current_tx["counterparty_name"] = fields.get("32", "") or fields.get("33", "")
                current_tx["counterparty_iban"] = fields.get("38", "")
                if not current_tx["reference"]:
                    current_tx["reference"] = fields.get("21", "") or fields.get("20", "")
            else:
                current_tx["description"] = detail

        i += 1

    if current_tx:
        transactions.append(current_tx)

    return {
        "iban": iban,
        "balance": balance,
        "currency": "EUR",
        "transactions": transactions,
    }


# ═══════════════════════════════════════════════════
#  CSV PARSER (generic bank export)
# ═══════════════════════════════════════════════════


def parse_csv_statement(content, delimiter=";"):
    """
    Parse CSV bank statement.
    Auto-detects columns by header names (HR/DE/EN).

    Expected: Date, Amount, Description/Purpose, Counterparty, Reference
    """
    import csv
    import io

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no headers")

    # Column mapping — auto-detect by common names
    col_map = {}
    for col in reader.fieldnames:
        cl = col.lower().strip()
        if any(k in cl for k in ("datum", "date", "buchungstag", "dt. knjiženja")):
            col_map["date"] = col
        elif any(k in cl for k in ("iznos", "amount", "betrag", "suma")):
            col_map["amount"] = col
        elif any(k in cl for k in ("opis", "description", "verwendungszweck", "purpose", "namjena")):
            col_map["description"] = col
        elif any(k in cl for k in ("platitelj", "counterparty", "auftraggeber", "primatelj", "empfänger", "name")):
            col_map["counterparty"] = col
        elif any(k in cl for k in ("referenc", "reference", "poziv", "kundenreferenz")):
            col_map["reference"] = col
        elif any(k in cl for k in ("iban",)):
            col_map["iban"] = col

    if "date" not in col_map or "amount" not in col_map:
        raise ValueError(f"Cannot detect date/amount columns. Headers: {reader.fieldnames}")

    transactions = []
    for row in reader:
        try:
            amt_str = row.get(col_map["amount"], "0").replace(".", "").replace(",", ".").strip()
            amount = Decimal(amt_str)
            direction = "inflow" if amount >= 0 else "outflow"
            amount = abs(amount)

            # Parse date
            date_str = row.get(col_map["date"], "").strip()
            booking_date = ""
            from datetime import datetime

            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    booking_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

            if not booking_date or amount == 0:
                continue

            transactions.append(
                {
                    "amount": amount,
                    "currency": "EUR",
                    "direction": direction,
                    "booking_date": booking_date,
                    "value_date": booking_date,
                    "counterparty_name": row.get(col_map.get("counterparty", ""), "")[:300],
                    "counterparty_iban": row.get(col_map.get("iban", ""), "")[:34],
                    "description": row.get(col_map.get("description", ""), "")[:500],
                    "reference": row.get(col_map.get("reference", ""), "")[:100],
                    "external_id": f"csv_{booking_date}_{amount}_{len(transactions)}",
                }
            )
        except (ValueError, InvalidOperation):
            continue

    return {
        "iban": "",
        "balance": Decimal("0"),
        "currency": "EUR",
        "transactions": transactions,
    }


def import_any_statement(company, bank_account, file_content, filename=""):
    """
    Auto-detect format (camt.053 XML, MT940, CSV) and import.
    """
    content = file_content.strip()
    filename_lower = filename.lower()

    if content.startswith("<?xml") or content.startswith("<"):
        data = parse_camt053(content)
    elif ":20:" in content[:200] and ":61:" in content:
        data = parse_mt940(content)
    elif filename_lower.endswith(".csv") or "\t" in content[:200] or ";" in content[:200]:
        delimiter = "\t" if "\t" in content[:200] else ";"
        if "," in content[:200] and ";" not in content[:200]:
            delimiter = ","
        data = parse_csv_statement(content, delimiter)
    else:
        raise ValueError("Nepoznat format. Podržano: camt.053 XML, MT940, CSV")

    # Find/create bank account from IBAN
    if not bank_account and data["iban"]:
        from konto.models import BankAccount, KontoAccount

        bank_account = BankAccount.objects.filter(company=company, iban=data["iban"]).first()
        if not bank_account:
            konto, _ = KontoAccount.objects.get_or_create(
                company=company, code="1000", defaults={"name": "Žiro račun", "account_type": "asset"}
            )
            bank_account = BankAccount.objects.create(
                company=company,
                name=f"Račun {data['iban'][-8:]}",
                iban=data["iban"],
                bank_name="",
                konto_account=konto,
                current_balance=data.get("balance", 0),
            )

    # Import transactions
    return import_bank_statement_from_parsed(company, bank_account, data)


def import_bank_statement_from_parsed(company, bank_account, data):
    """Import pre-parsed statement data into BankTransaction records."""
    from datetime import date as _date

    from konto.models import BankTransaction

    batch_id = f"import_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    created = skipped = errors = 0

    for tx in data["transactions"]:
        try:
            if (
                tx.get("external_id")
                and BankTransaction.objects.filter(company=company, external_id=tx["external_id"]).exists()
            ):
                skipped += 1
                continue

            booking = None
            try:
                booking = _date.fromisoformat(tx["booking_date"])
            except (ValueError, TypeError):
                booking = timezone.now().date()

            value = None
            try:
                value = _date.fromisoformat(tx["value_date"])
            except (ValueError, TypeError):
                value = booking

            BankTransaction.objects.create(
                bank_account=bank_account,
                company=company,
                transaction_date=booking,
                value_date=value,
                amount=tx["amount"],
                transaction_type=tx["direction"],
                counterparty_name=tx.get("counterparty_name", "")[:300],
                counterparty_iban=tx.get("counterparty_iban", "")[:34],
                description=tx.get("description", ""),
                reference_number=tx.get("reference", "")[:100],
                external_id=tx.get("external_id", "")[:200],
                import_batch=batch_id,
                status="unmatched",
            )
            created += 1
        except (IntegrityError, DatabaseError) as e:
            errors += 1
            logger.warning(f"Import error: {e}")

    if bank_account and data.get("balance"):
        bank_account.current_balance = data["balance"]
        bank_account.save(update_fields=["current_balance", "updated_at"])

    return {"created": created, "skipped": skipped, "errors": errors, "batch_id": batch_id}
