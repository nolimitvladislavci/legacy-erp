"""
synesis/full_import.py — Kompletni Synesis MDB → LIMIT Connect importer

Čita direktno iz Storage.mdb (mdbtools, bez lozinke na Linuxu):
  - ACCOUNTING (temeljnice/dokumenti header)
  - TACCOUNTING (stavke knjiženja — detalji)
  - ACCOUNTS (kontni plan)
  - PARTNERS (partneri)

Kreira JournalEntry + LedgerLine za svaki dokument.
Idempotent — ako se pokrene dva puta, ne duplicira.
"""
import csv
import io
import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

MDB_CHARSET = 'cp1250'


def _mdb_export(mdb_path, table_name):
    """Export table from MDB as list of dicts."""
    env = os.environ.copy()
    env['MDB_JET3_CHARSET'] = MDB_CHARSET
    try:
        result = subprocess.run(
            ['mdb-export', mdb_path, table_name],
            capture_output=True, text=True, timeout=120, env=env
        )
        if result.returncode != 0:
            logger.warning("mdb-export failed for %s/%s: %s", mdb_path, table_name, result.stderr)
            return []
        reader = csv.DictReader(io.StringIO(result.stdout))
        return list(reader)
    except Exception as e:
        logger.error("mdb-export error: %s", e)
        return []


def _parse_date(val):
    """Parse Synesis date (MM/DD/YY or Excel serial)."""
    if not val:
        return None
    val = val.strip().strip('"')
    for fmt in ('%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(val, fmt).date()
        except (ValueError, TypeError):
            continue
    # Excel serial
    try:
        serial = float(val)
        if 30000 < serial < 60000:
            from datetime import timedelta, date
            return date(1899, 12, 30) + timedelta(days=int(serial))
    except (ValueError, TypeError):
        pass
    return None


def _dec(val):
    """Parse decimal, handle empty/comma."""
    if not val:
        return Decimal('0')
    try:
        v = str(val).strip().replace(',', '.').replace('"', '')
        return Decimal(v).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def import_kontni_plan(company, mdb_path):
    """Import ACCOUNTS table → KontoAccount."""
    from konto.models import KontoAccount

    rows = _mdb_export(mdb_path, 'ACCOUNTS')
    created = 0
    for row in rows:
        code = (row.get('ACC_NUMBER') or '').strip().strip('"')
        name = (row.get('ACC_NAME') or '').strip().strip('"')
        if not code:
            continue

        # Determine type from class
        klasa = code[0] if code else '0'
        type_map = {
            '0': 'asset', '1': 'asset', '2': 'liability', '3': 'asset',
            '4': 'expense', '5': 'expense', '6': 'expense',
            '7': 'income', '8': 'income', '9': 'equity',
        }
        acct_type = type_map.get(klasa, 'asset')

        _, is_new = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={'name': name[:200], 'account_type': acct_type}
        )
        if is_new:
            created += 1

    return created


def import_partneri(company, mdb_path):
    """Import PARTNERS table → partners.Partner."""
    from partners.models import Partner

    rows = _mdb_export(mdb_path, 'PARTNERS')
    created = 0
    for row in rows:
        name = (row.get('PARTNER_NAME') or '').strip().strip('"').strip()
        oib = (row.get('PARTNER_VATNUMBER') or '').strip().strip('"').strip()
        city = (row.get('CITY_NAME') or '').strip().strip('"').strip()
        address = (row.get('PARTNER_STREET') or '').strip().strip('"').strip()
        phone = (row.get('PARTNER_PHONE') or '').strip().strip('"').strip()
        email = (row.get('PARTNER_EMAIL') or '').strip().strip('"').strip()

        if not name:
            continue

        # Dedup by OIB or name
        if oib and Partner.objects.filter(company=company, oib=oib).exists():
            continue
        if not oib and Partner.objects.filter(company=company, name=name).exists():
            continue

        Partner.objects.create(
            company=company, name=name[:200], oib=oib[:20],
            city=city[:100], address=address[:200],
            phone=phone[:50], email=email[:100],
        )
        created += 1

    return created


def import_knjizenja(company, mdb_path, wipe_existing=False):
    """
    Import ACCOUNTING (headers) + TACCOUNTING (lines) → JournalEntry + LedgerLine.
    
    ACCOUNTING.DIN = unique document ID
    TACCOUNTING.DIN = FK to ACCOUNTING
    TACCOUNTING has: ACC_NUMBER (konto), ACC_DEBIT, ACC_CREDIT, ACC_TITLE, ACC_TEXT
    """
    from konto.models import KontoAccount, JournalEntry, LedgerLine
    from django.db import transaction

    if wipe_existing:
        deleted = LedgerLine.objects.filter(journal_entry__company=company).delete()
        JournalEntry.objects.filter(company=company).delete()
        logger.info("Wiped existing: %s", deleted)

    # Read headers
    headers = _mdb_export(mdb_path, 'ACCOUNTING')
    header_map = {}
    for h in headers:
        din = (h.get('DIN') or '').strip()
        if din:
            header_map[din] = {
                'date': _parse_date(h.get('TRANDATE')),
                'code': (h.get('TRANCODE') or '').strip(),
                'remark': (h.get('REMARK') or '').strip().strip('"').strip(),
                'conid': (h.get('CONID') or '').strip().strip('"').strip(),
            }

    # Read lines
    lines = _mdb_export(mdb_path, 'TACCOUNTING')
    
    # Group by DIN
    by_din = defaultdict(list)
    for line in lines:
        din = (line.get('DIN') or '').strip()
        if din:
            by_din[din].append(line)

    logger.info("Import: %d headers, %d lines, %d unique DINs", len(headers), len(lines), len(by_din))

    created_je = 0
    created_ll = 0
    errors = 0
    unbalanced = 0

    for din, din_lines in by_din.items():
        hdr = header_map.get(din, {})
        entry_date = hdr.get('date')
        if not entry_date:
            # Try from first line
            for ln in din_lines:
                entry_date = _parse_date(ln.get('ACC_INVDATE') or ln.get('TRANDATE'))
                if entry_date:
                    break
        if not entry_date:
            from datetime import date
            entry_date = date(2025, 1, 1)

        # Build description from lines
        descriptions = set()
        for ln in din_lines:
            t = (ln.get('ACC_TEXT') or '').strip().strip('"').strip()
            if t:
                descriptions.add(t[:80])
        desc = '; '.join(list(descriptions)[:3]) or hdr.get('remark', '') or f'Synesis DIN {din}'

        entry_number = f'SYN-{din}'

        # Skip if already exists
        if JournalEntry.objects.filter(company=company, entry_number=entry_number).exists():
            continue

        try:
            with transaction.atomic():
                je = JournalEntry.objects.create(
                    company=company,
                    entry_number=entry_number,
                    date=entry_date,
                    description=desc[:300],
                    source_type='manual',
                    is_posted=True,
                )

                total_d = Decimal('0')
                total_p = Decimal('0')

                for ln in din_lines:
                    konto_code = (ln.get('ACC_NUMBER') or '').strip().strip('"').strip()
                    debit = _dec(ln.get('ACC_DEBIT'))
                    credit = _dec(ln.get('ACC_CREDIT'))

                    if not konto_code or (debit == 0 and credit == 0):
                        continue

                    # Ensure konto exists
                    konto_name = (ln.get('ACC_NAME') or ln.get('ACC_TITLE') or '').strip().strip('"').strip()
                    klasa = konto_code[0] if konto_code else '0'
                    type_map = {'0':'asset','1':'asset','2':'liability','3':'asset',
                                '4':'expense','5':'expense','6':'expense',
                                '7':'income','8':'income','9':'equity'}
                    acct, _ = KontoAccount.objects.get_or_create(
                        company=company, code=konto_code,
                        defaults={'name': konto_name[:200] or konto_code, 'account_type': type_map.get(klasa, 'asset')}
                    )

                    desc_text = (ln.get('ACC_TEXT') or '')[:200].strip().strip('"')

                    if debit != 0:
                        # Negative debit = credit (Synesis storno convention)
                        side = 'debit' if debit > 0 else 'credit'
                        amt = abs(debit)
                        if amt > 0:
                            LedgerLine.objects.create(
                                journal_entry=je, account=acct,
                                side=side, amount=amt,
                                description=desc_text,
                            )
                            if side == 'debit':
                                total_d += amt
                            else:
                                total_p += amt
                            created_ll += 1

                    if credit != 0:
                        side = 'credit' if credit > 0 else 'debit'
                        amt = abs(credit)
                        if amt > 0:
                            LedgerLine.objects.create(
                                journal_entry=je, account=acct,
                                side=side, amount=amt,
                                description=desc_text,
                            )
                            if side == 'credit':
                                total_p += amt
                            else:
                                total_d += amt
                            created_ll += 1

                if abs(total_d - total_p) > Decimal('0.02'):
                    unbalanced += 1

                created_je += 1

        except Exception as e:
            errors += 1
            if errors < 5:
                logger.warning("Import error DIN %s: %s", din, e)

    return {
        'journal_entries': created_je,
        'ledger_lines': created_ll,
        'errors': errors,
        'unbalanced': unbalanced,
        'source_headers': len(headers),
        'source_lines': len(lines),
    }


def full_import(company, mdb_path, wipe=False):
    """Full import: kontni plan + partneri + knjiženja."""
    results = {}
    
    logger.info("=== FULL IMPORT: %s from %s ===", company.name, mdb_path)
    
    results['kontni_plan'] = import_kontni_plan(company, mdb_path)
    logger.info("Kontni plan: %d created", results['kontni_plan'])
    
    results['partneri'] = import_partneri(company, mdb_path)
    logger.info("Partneri: %d created", results['partneri'])
    
    results['knjizenja'] = import_knjizenja(company, mdb_path, wipe_existing=wipe)
    logger.info("Knjiženja: %s", results['knjizenja'])
    
    return results
