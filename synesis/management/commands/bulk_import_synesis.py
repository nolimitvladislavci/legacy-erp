"""
synesis/management/commands/bulk_import_synesis.py

Comprehensive bulk import from all 69 Synesis MDB client archives.

Imports:
  - Partners (existing)
  - Items (existing)
  - Chart of Accounts (ACCOUNTS -> konto.KontoAccount)
  - Journal Entries (ACCOUNTING + TACCOUNTING -> konto.JournalEntry + LedgerLine)
  - Issued Invoices (INVOICES + TINVOICES -> invoicing.Invoice)
  - Received Invoices (URAEU + TURAEU -> konto.JournalEntry as URA)
  - Employees (EMPLOYEES + WORKER -> worktime.EmployeeProfile)
  - Payroll (PAYROLL2 + TPAYROLL2 -> payroll.PayrollRun + konto.JournalEntry)
  - Bank Accounts (BANKACCOUNTS -> konto.BankAccount)
  - Retail/Primke (RETAIL + TRETAIL -> inventory.GoodsReceipt)

Usage:
    python manage.py bulk_import_synesis --dry-run
    python manage.py bulk_import_synesis --filter FAST
    python manage.py bulk_import_synesis --filter KONJIK --only accounts,temeljnice
    python manage.py bulk_import_synesis --per-client
    python manage.py bulk_import_synesis --company "Konjik d.o.o." --type all
    python manage.py bulk_import_synesis --analyze
"""

import csv
import io
import os
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime as _dt
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db import DatabaseError

ARCHIVE_PATH = "/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis/"

DATE_FORMATS = [
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%y",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
]

ALL_TYPES = [
    'partners', 'items', 'accounts', 'temeljnice', 'invoices',
    'ura', 'employees', 'payroll', 'bank', 'retail',
]


def safe_dec(v):
    if v is None:
        return Decimal('0')
    s = str(v).strip().replace(',', '.')
    if not s or s in ('', 'None', 'null'):
        return Decimal('0')
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def parse_date(s):
    if not s or str(s).strip() in ('', 'None', 'null'):
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return _dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime_aware(s):
    if not s or str(s).strip() in ('', 'None', 'null'):
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            dt = _dt.strptime(s, fmt)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            continue
    return None


def mdb_export(mdb_path, table_name):
    try:
        result = subprocess.run(
            ['mdb-export', mdb_path, table_name],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, 'MDB_ICONV': 'UTF-8'},
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = []
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                if isinstance(v, str):
                    v = v.strip()
                cleaned[k] = v
            rows.append(cleaned)
        return rows
    except subprocess.TimeoutExpired:
        return []
    except (ValueError, AttributeError):
        return []


class Command(BaseCommand):
    help = 'Comprehensive bulk import from Synesis MDB archives (69 clients)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archive-dir', default=ARCHIVE_PATH,
            help='Path to archive directory',
        )
        parser.add_argument('--company', default='', help='Import into specific company (name or OIB)')
        parser.add_argument('--per-client', action='store_true', help='Create one company per client folder')
        parser.add_argument('--filter', default='', help='Comma-separated client name prefixes to filter')
        parser.add_argument('--year', default='', help='Filter by year')
        parser.add_argument('--analyze', action='store_true', help='Analyze archive without importing')
        parser.add_argument('--dry-run', action='store_true', help='Preview what would be imported')
        parser.add_argument(
            '--type', default='all',
            choices=['all'] + ALL_TYPES,
            help='Import specific data type',
        )
        parser.add_argument(
            '--only', default='',
            help='Comma-separated types: ' + ','.join(ALL_TYPES),
        )

    def handle(self, *args, **options):
        archive_dir = options['archive_dir'].rstrip('/')
        if not os.path.isdir(archive_dir):
            raise CommandError('Directory not found: ' + archive_dir)

        folders = self._scan_folders(archive_dir, options.get('year'), options.get('filter'))
        self.stdout.write('Found %d client folders' % len(folders))

        if options['analyze']:
            self._analyze(folders)
            return

        if options['only']:
            import_types = [t.strip() for t in options['only'].split(',') if t.strip() in ALL_TYPES]
        elif options['type'] == 'all':
            import_types = ALL_TYPES
        else:
            import_types = [options['type']]

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - no data will be written'))

        if not options['company'] and not options['per_client']:
            raise CommandError('Specify --company "Name" or --per-client')

        company = None
        if options['company']:
            from companies.models import Company
            try:
                company = Company.objects.get(name__iexact=options['company'])
            except Company.DoesNotExist:
                try:
                    company = Company.objects.get(oib=options['company'])
                except Company.DoesNotExist:
                    raise CommandError('Company not found: ' + options['company'])

        total_stats = defaultdict(int)
        t_start = time.time()

        for fi in folders:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write('Client: %s (%s)' % (fi['client'], fi['year']))

            if not fi['has_storage']:
                self.stdout.write(self.style.WARNING('  SKIP: no Storage.mdb'))
                continue

            target = company
            if options['per_client']:
                if dry_run:
                    self.stdout.write('  [DRY] Would create/get company: ' + fi['client'])
                    continue
                target = self._get_or_create_company(fi)

            if not target and not dry_run:
                self.stderr.write(self.style.ERROR('  SKIP: no target company'))
                continue

            folder_stats = defaultdict(int)

            for itype in import_types:
                try:
                    method = getattr(self, '_import_' + itype, None)
                    if method:
                        result = method(target, fi, dry_run)
                        for k, v in result.items():
                            folder_stats[k] += v
                            total_stats[k] += v
                except (AttributeError, TypeError) as exc:
                    self.stderr.write(self.style.ERROR('  ERROR [%s]: %s' % (itype, exc)))
                    total_stats[itype + '_errors'] = total_stats.get(itype + '_errors', 0) + 1
                    import traceback
                    traceback.print_exc()

            if folder_stats:
                parts = ['%s=%s' % (k, v) for k, v in sorted(folder_stats.items()) if v > 0]
                if parts:
                    self.stdout.write('  Summary: ' + ', '.join(parts))

            total_stats['folders_processed'] += 1

        elapsed = round(time.time() - t_start, 1)
        self.stdout.write('\n' + '=' * 60)
        pfx = '(DRY RUN) ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS('BULK IMPORT COMPLETE %s[%ss]' % (pfx, elapsed)))
        for k, v in sorted(total_stats.items()):
            if v > 0:
                self.stdout.write('  %s: %s' % (k, v))

    # ---- Scanning & Analysis ----

    def _scan_folders(self, archive_dir, year_filter, name_filter):
        folders = []
        prefixes = [n.strip().upper() for n in (name_filter or '').split(',') if n.strip()]
        for entry in sorted(os.listdir(archive_dir)):
            fp = os.path.join(archive_dir, entry)
            if not os.path.isdir(fp):
                continue
            match = re.match(r'^(.+?)\s+(\d{4})(.*)$', entry)
            if match:
                client = match.group(1).strip()
                year = match.group(2)
                suffix = match.group(3).strip()
            else:
                client, year, suffix = entry, 'unknown', ''
            if year_filter and year != year_filter:
                continue
            if prefixes and not any(client.upper().startswith(p) for p in prefixes):
                continue
            storage = os.path.join(fp, 'Storage.mdb')
            journal = os.path.join(fp, 'Journal.mdb')
            folders.append({
                'path': fp, 'folder_name': entry, 'client': client,
                'year': year, 'suffix': suffix,
                'has_storage': os.path.exists(storage),
                'has_journal': os.path.exists(journal),
                'storage_path': storage if os.path.exists(storage) else None,
                'journal_path': journal if os.path.exists(journal) else None,
                'storage_size': os.path.getsize(storage) if os.path.exists(storage) else 0,
            })
        return folders

    def _analyze(self, folders):
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(' SYNESIS ARCHIVE ANALYSIS')
        self.stdout.write('=' * 70 + '\n')

        clients = defaultdict(list)
        for f in folders:
            clients[f['client']].append(f)

        self.stdout.write('Total folders: %d' % len(folders))
        self.stdout.write('Unique clients: %d\n' % len(clients))

        tables_to_check = [
            'ACCOUNTS', 'PARTNERS', 'ITEMS', 'INVOICES', 'URAEU',
            'ACCOUNTING', 'TACCOUNTING', 'EMPLOYEES', 'PAYROLL2',
            'BANKACCOUNTS', 'RETAIL', 'WORKER',
        ]

        hdr = '%-35s %5s %8s ' % ('Client', 'Year', 'Size')
        hdr += ' '.join('%6s' % t[:6] for t in tables_to_check)
        self.stdout.write(hdr)
        self.stdout.write('-' * len(hdr))

        grand_totals = defaultdict(int)

        for f in folders:
            smb = '%.1fM' % (f['storage_size'] / 1024 / 1024) if f['has_storage'] else '---'
            counts = {}
            if f['has_storage']:
                for table in tables_to_check:
                    try:
                        r = subprocess.run(
                            ['mdb-export', f['storage_path'], table],
                            capture_output=True, text=True, timeout=15,
                        )
                        if r.returncode == 0 and r.stdout.strip():
                            c = max(0, len(r.stdout.strip().split('\n')) - 1)
                            counts[table] = c
                            grand_totals[table] += c
                        else:
                            counts[table] = 0
                    except (ValueError, AttributeError):
                        counts[table] = 0

            count_strs = []
            for t in tables_to_check:
                c = counts.get(t, 0)
                count_strs.append('%6d' % c if c > 0 else '%6s' % '---')

            line = '%-35s %5s %8s ' % (f['client'][:35], f['year'], smb)
            line += ' '.join(count_strs)
            self.stdout.write(line)

        self.stdout.write('-' * len(hdr))
        total_strs = ['%6d' % grand_totals.get(t, 0) for t in tables_to_check]
        line = '%-35s %5s %8s ' % ('TOTAL', '', '')
        line += ' '.join(total_strs)
        self.stdout.write(line)

    # ---- Company creation ----

    def _get_or_create_company(self, fi):
        from companies.models import Company
        client_name = fi['client'].strip()
        try:
            return Company.objects.get(name__iexact=client_name)
        except Company.DoesNotExist:
            pass
        for suffix in [' d.o.o.', ' D.O.O.', ' j.d.o.o.']:
            try:
                return Company.objects.get(name__iexact=client_name + suffix)
            except Company.DoesNotExist:
                continue

        oib = ''
        if fi.get('storage_path'):
            settings_rows = mdb_export(fi['storage_path'], 'Settings')
            for row in settings_rows:
                key = (row.get('Key') or '').strip()
                if key in ('OIB', 'SE_OIB', 'USEROIB', 'USER_OIB'):
                    oib = (row.get('ValueString') or '').strip()
                    break
            if not oib:
                pr = mdb_export(fi['storage_path'], 'PAYROLL2')
                if pr:
                    oib = (pr[0].get('USEROIB') or '').strip()

        if oib and len(oib) >= 11:
            try:
                return Company.objects.get(oib=oib)
            except Company.DoesNotExist:
                pass

        display_name = client_name.title() if client_name.isupper() else client_name
        if not oib:
            oib = 'SYN-' + client_name[:20].upper().replace(' ', '')

        self.stdout.write('  Creating company: %s (OIB: %s)' % (display_name, oib))
        return Company.objects.create(name=display_name, oib=oib, country='HR')

    # ---- Log helper ----

    def _log_sync(self, company, sync_type, received, created, updated, errors, detail, duration):
        from synesis.models import SynesisLog
        SynesisLog.objects.create(
            company=company, sync_type=sync_type,
            records_received=received, records_created=created,
            records_updated=updated, errors=errors,
            error_detail=str(detail)[:2000],
            duration_seconds=round(duration, 2),
        )

    # =====================================================================
    # IMPORT METHODS
    # =====================================================================

    def _import_partners(self, company, fi, dry_run):
        from synesis.views import _import_partners
        t0 = time.time()
        rows = mdb_export(fi['storage_path'], 'PARTNERS')
        if not rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Partners: %d rows' % len(rows))
            return {'partners_would_import': len(rows)}
        res = _import_partners(company, rows)
        dur = time.time() - t0
        c, u, e = res.get('created', 0), res.get('updated', 0), res.get('errors', 0)
        self.stdout.write('  Partners: %d new, %d upd, %d err (%.1fs)' % (c, u, e, dur))
        self._log_sync(company, 'partners', len(rows), c, u, e, fi['folder_name'], dur)
        return {'partners_created': c, 'partners_updated': u, 'partners_errors': e}

    def _import_items(self, company, fi, dry_run):
        from synesis.views import _import_items
        t0 = time.time()
        rows = mdb_export(fi['storage_path'], 'ITEMS')
        if not rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Items: %d rows' % len(rows))
            return {'items_would_import': len(rows)}
        res = _import_items(company, rows)
        dur = time.time() - t0
        c, u, e = res.get('created', 0), res.get('updated', 0), res.get('errors', 0)
        self.stdout.write('  Items: %d new, %d upd, %d err (%.1fs)' % (c, u, e, dur))
        self._log_sync(company, 'items', len(rows), c, u, e, fi['folder_name'], dur)
        return {'items_created': c, 'items_updated': u, 'items_errors': e}

    def _import_accounts(self, company, fi, dry_run):
        from konto.models import KontoAccount, AccountType
        t0 = time.time()
        rows = mdb_export(fi['storage_path'], 'ACCOUNTS')
        if not rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Accounts: %d rows' % len(rows))
            return {'accounts_would_import': len(rows)}

        CLASS_MAP = {
            '0': AccountType.ASSET, '1': AccountType.ASSET,
            '2': AccountType.ASSET, '3': AccountType.ASSET,
            '4': AccountType.LIABILITY, '5': AccountType.EXPENSE,
            '6': AccountType.EXPENSE, '7': AccountType.INCOME,
            '8': AccountType.EXPENSE, '9': AccountType.EQUITY,
        }

        created = updated = errors = 0
        for row in rows:
            try:
                code = (row.get('ACC_NUMBER') or '').strip()
                name = (row.get('ACC_NAME') or '').strip()
                if not code or not name:
                    continue
                acc_class = (row.get('ACC_CLASS') or '').strip()
                account_type = CLASS_MAP.get(acc_class[:1], AccountType.ASSET) if acc_class else AccountType.ASSET
                obj, was_created = KontoAccount.objects.update_or_create(
                    company=company, code=code,
                    defaults={'name': name, 'account_type': account_type, 'is_active': True},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except DatabaseError:
                errors += 1

        dur = time.time() - t0
        self.stdout.write('  Accounts: %d new, %d upd, %d err (%.1fs)' % (created, updated, errors, dur))
        self._log_sync(company, 'accounts', len(rows), created, updated, errors, fi['folder_name'], dur)
        return {'accounts_created': created, 'accounts_updated': updated, 'accounts_errors': errors}

    def _import_temeljnice(self, company, fi, dry_run):
        from konto.models import JournalEntry, LedgerLine, KontoAccount
        t0 = time.time()

        headers = mdb_export(fi['storage_path'], 'ACCOUNTING')
        lines = mdb_export(fi['storage_path'], 'TACCOUNTING')

        if not headers:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Temeljnice: %d headers, %d lines' % (len(headers), len(lines)))
            return {'temeljnice_would_import': len(headers), 'stavke_would_import': len(lines)}

        lines_by_din = defaultdict(list)
        for line in lines:
            din = (line.get('DIN') or '').strip()
            if din:
                lines_by_din[din].append(line)

        account_cache = {}
        for acc in KontoAccount.objects.filter(company=company):
            account_cache[acc.code.strip()] = acc

        TYPE_MAP = {
            '0': 'asset', '1': 'asset', '2': 'asset', '3': 'asset',
            '4': 'liability', '5': 'expense', '6': 'expense',
            '7': 'income', '8': 'expense', '9': 'equity',
        }

        je_created = je_skipped = line_created = errors = 0
        year = fi.get('year', '')

        for hdr in headers:
            try:
                din = (hdr.get('DIN') or '').strip()
                trancode = (hdr.get('TRANCODE') or '').strip()
                date_str = (hdr.get('TRANDATE') or '').strip()
                remark = (hdr.get('REMARK') or '').strip()

                if not din or not trancode:
                    continue

                entry_date = parse_date(date_str)
                if not entry_date:
                    errors += 1
                    continue

                entry_number = 'SYN-%s-%s-%s' % (year, trancode, din)

                if JournalEntry.objects.filter(company=company, entry_number=entry_number).exists():
                    je_skipped += 1
                    continue

                hdr_lines = lines_by_din.get(din, [])
                if not hdr_lines:
                    continue

                parsed_lines = []
                total_debit = Decimal('0')
                total_credit = Decimal('0')

                for ln in hdr_lines:
                    acc_code = (ln.get('ACC_NUMBER') or '').strip()
                    debit = safe_dec(ln.get('ACC_DEBIT'))
                    credit = safe_dec(ln.get('ACC_CREDIT'))
                    desc = (ln.get('ACC_TEXT') or ln.get('ACC_TITLE') or '').strip()
                    partner_name = (ln.get('PARTNER_NAME') or '').strip()

                    if not acc_code:
                        continue
                    if debit == 0 and credit == 0:
                        continue

                    account = account_cache.get(acc_code)
                    if not account:
                        acc_name = (ln.get('ACC_NAME') or ('Konto ' + acc_code)).strip()
                        first_digit = acc_code[0] if acc_code else '0'
                        account = KontoAccount.objects.create(
                            company=company, code=acc_code, name=acc_name,
                            account_type=TYPE_MAP.get(first_digit, 'asset'), is_active=True,
                        )
                        account_cache[acc_code] = account

                    line_desc = desc
                    if partner_name:
                        line_desc = (desc + ' -- ' + partner_name)[:200]

                    # Handle negative amounts by flipping side
                    if debit < 0:
                        credit += abs(debit)
                        debit = Decimal('0')
                    if credit < 0:
                        debit += abs(credit)
                        credit = Decimal('0')

                    if debit > 0:
                        parsed_lines.append({'account': account, 'side': 'debit', 'amount': debit, 'description': line_desc[:200]})
                        total_debit += debit
                    if credit > 0:
                        parsed_lines.append({'account': account, 'side': 'credit', 'amount': credit, 'description': line_desc[:200]})
                        total_credit += credit

                if not parsed_lines:
                    continue

                tranid = (hdr.get('TRANID') or '').strip().upper()
                source_type = 'manual'
                if 'INVOICE' in tranid:
                    source_type = 'invoice'
                elif 'PAYROLL' in tranid or 'PAY' in tranid:
                    source_type = 'payroll'
                elif 'BANK' in tranid:
                    source_type = 'bank_statement'

                description = remark or ('Synesis temeljnica ' + trancode)

                diff = total_debit - total_credit
                if diff != Decimal('0'):
                    if abs(diff) <= Decimal('5.00'):
                        rounding_acc = account_cache.get('3999')
                        if not rounding_acc:
                            rounding_acc, _ = KontoAccount.objects.get_or_create(
                                company=company, code='3999',
                                defaults={'name': 'Zaokruzenja', 'account_type': 'expense', 'is_active': True},
                            )
                            account_cache['3999'] = rounding_acc
                        if diff > 0:
                            parsed_lines.append({'account': rounding_acc, 'side': 'credit', 'amount': diff, 'description': 'Zaokruzenje'})
                        else:
                            parsed_lines.append({'account': rounding_acc, 'side': 'debit', 'amount': abs(diff), 'description': 'Zaokruzenje'})
                    else:
                        self.stderr.write('    WARN: Temeljnica %s imbalanced D=%s P=%s diff=%s' % (entry_number, total_debit, total_credit, diff))
                        errors += 1
                        continue

                # Create with is_posted=False first, insert lines, then mark posted
                # (DB trigger check_journal_balance only fires when is_posted=True)
                with transaction.atomic():
                    je = JournalEntry.objects.create(
                        company=company, entry_number=entry_number,
                        date=entry_date, description=description[:300],
                        source_type=source_type, is_posted=False,
                    )
                    for pl in parsed_lines:
                        LedgerLine.objects.create(
                            journal_entry=je, account=pl['account'],
                            side=pl['side'], amount=pl['amount'],
                            description=pl['description'],
                        )
                        line_created += 1
                    je.is_posted = True
                    je.save(update_fields=['is_posted'])

                je_created += 1

            except (ValueError, TypeError):
                errors += 1

        dur = time.time() - t0
        self.stdout.write('  Temeljnice: %d new, %d exist, %d lines, %d err (%.1fs)' % (je_created, je_skipped, line_created, errors, dur))
        self._log_sync(company, 'temeljnice', len(headers), je_created, 0, errors, fi['folder_name'], dur)
        return {
            'temeljnice_created': je_created, 'temeljnice_skipped': je_skipped,
            'stavke_created': line_created, 'temeljnice_errors': errors,
        }

    def _import_invoices(self, company, fi, dry_run):
        t0 = time.time()
        inv_rows = mdb_export(fi['storage_path'], 'INVOICES')
        tinv_rows = mdb_export(fi['storage_path'], 'TINVOICES')

        if not inv_rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Invoices: %d headers, %d lines' % (len(inv_rows), len(tinv_rows)))
            return {'invoices_would_import': len(inv_rows)}

        lines_by_din = defaultdict(list)
        for lr in tinv_rows:
            din = (lr.get('DIN') or '').strip()
            if din:
                lines_by_din[din].append(lr)

        for inv_row in inv_rows:
            din = (inv_row.get('DIN') or '').strip()
            inv_row['_items'] = lines_by_din.get(din, [])
            inv_row['_synesis_year'] = fi.get('year', '')
            inv_row['TRANCODE'] = din
            inv_row['TRANDATE'] = inv_row.get('INVOICE_DATE', '')
            inv_row['INVOICE_TOTAL'] = inv_row.get('INVOICETOTAL', inv_row.get('VAT_INVOICEAMMOUNT', '0'))
            inv_row['INVOICE_TAX'] = inv_row.get('VAT_AMMOUNT', '0')

        from synesis.views import _import_invoices
        c, u, e = _import_invoices(None, company, inv_rows)
        dur = time.time() - t0
        self.stdout.write('  Invoices: %d new, %d upd, %d err (%.1fs) [%d lines]' % (c, u, e, dur, len(tinv_rows)))
        self._log_sync(company, 'invoices', len(inv_rows), c, u, e, fi['folder_name'], dur)
        return {'invoices_created': c, 'invoices_updated': u, 'invoices_errors': e}

    def _import_ura(self, company, fi, dry_run):
        from konto.models import JournalEntry, LedgerLine, KontoAccount
        t0 = time.time()

        headers = mdb_export(fi['storage_path'], 'URAEU')
        lines = mdb_export(fi['storage_path'], 'TURAEU')

        if not headers:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] URA: %d headers, %d lines' % (len(headers), len(lines)))
            return {'ura_would_import': len(headers)}

        lines_by_din = defaultdict(list)
        for ln in lines:
            din = (ln.get('DIN') or '').strip()
            if din:
                lines_by_din[din].append(ln)

        account_cache = {acc.code.strip(): acc for acc in KontoAccount.objects.filter(company=company)}

        TYPE_MAP = {
            '0': 'asset', '1': 'asset', '2': 'asset', '3': 'asset',
            '4': 'liability', '5': 'expense', '6': 'expense',
            '7': 'income', '8': 'expense', '9': 'equity',
        }

        created = skipped = line_count = errors = 0
        year = fi.get('year', '')

        for hdr in headers:
            try:
                din = (hdr.get('DIN') or '').strip()
                trancode = (hdr.get('TRANCODE') or '').strip()
                date_str = (hdr.get('TRANDATE') or '').strip()
                vendor_name = (hdr.get('VENDOR_NAME') or '').strip()
                invoice_num = (hdr.get('VAT_INVOICENUMBER') or '').strip()
                total_amount = safe_dec(hdr.get('VAT_INVOICEAMMOUNT'))

                if not din or not trancode:
                    continue

                entry_date = parse_date(date_str)
                if not entry_date:
                    errors += 1
                    continue

                entry_number = 'URA-%s-%s' % (year, trancode)

                if JournalEntry.objects.filter(company=company, entry_number=entry_number).exists():
                    skipped += 1
                    continue

                hdr_lines = lines_by_din.get(din, [])
                description = ('URA %s -- %s' % (invoice_num, vendor_name))[:300]

                parsed_lines = []
                total_debit = Decimal('0')
                total_credit = Decimal('0')

                for ln in hdr_lines:
                    acc_code = (ln.get('ACC_NUMBER') or '').strip()
                    debit = safe_dec(ln.get('ACC_DEBIT'))
                    credit = safe_dec(ln.get('ACC_CREDIT'))
                    desc = (ln.get('ACC_TEXT') or ln.get('ACC_TITLE') or '').strip()

                    if not acc_code:
                        continue

                    # Handle negative amounts by flipping side
                    if debit < 0:
                        credit += abs(debit)
                        debit = Decimal('0')
                    if credit < 0:
                        debit += abs(credit)
                        credit = Decimal('0')

                    if debit == 0 and credit == 0:
                        continue

                    account = account_cache.get(acc_code)
                    if not account:
                        acc_name = (ln.get('ACC_NAME') or ('Konto ' + acc_code)).strip()
                        first_digit = acc_code[0] if acc_code else '2'
                        account = KontoAccount.objects.create(
                            company=company, code=acc_code, name=acc_name,
                            account_type=TYPE_MAP.get(first_digit, 'liability'), is_active=True,
                        )
                        account_cache[acc_code] = account

                    if debit > 0:
                        parsed_lines.append({'account': account, 'side': 'debit', 'amount': debit, 'description': desc[:200]})
                        total_debit += debit
                    if credit > 0:
                        parsed_lines.append({'account': account, 'side': 'credit', 'amount': credit, 'description': desc[:200]})
                        total_credit += credit

                if not parsed_lines:
                    if total_amount <= 0:
                        continue

                    vat_deductable = safe_dec(hdr.get('VAT_DEDUCTABLE', hdr.get('VAT_PREPAID', '0')))
                    net_amount = total_amount - vat_deductable

                    def _get_acc(code, name, atype):
                        acc = account_cache.get(code)
                        if not acc:
                            acc, _ = KontoAccount.objects.get_or_create(
                                company=company, code=code,
                                defaults={'name': name, 'account_type': atype, 'is_active': True},
                            )
                            account_cache[code] = acc
                        return acc

                    vendor_acc_code = (hdr.get('SE_VENDORACCOUNT') or '220').strip()
                    vendor_acc = _get_acc(vendor_acc_code, 'Dobavljaci', 'liability')
                    vat_acc_code = (hdr.get('SE_VATPREPAIDR1ACCOUNT') or '1405').strip()
                    vat_acc = _get_acc(vat_acc_code, 'Pretporez', 'asset')
                    expense_acc = _get_acc('4000', 'Troskovi materijala', 'expense')

                    parsed_lines = [
                        {'account': expense_acc, 'side': 'debit', 'amount': net_amount, 'description': description[:200]},
                    ]
                    total_debit = net_amount
                    total_credit = Decimal('0')

                    if vat_deductable > 0:
                        parsed_lines.append({'account': vat_acc, 'side': 'debit', 'amount': vat_deductable, 'description': 'Pretporez ' + invoice_num})
                        total_debit += vat_deductable

                    parsed_lines.append({'account': vendor_acc, 'side': 'credit', 'amount': total_amount, 'description': '%s %s' % (vendor_name, invoice_num)})
                    total_credit = total_amount

                diff = total_debit - total_credit
                if diff != Decimal('0'):
                    if abs(diff) <= Decimal('5.00'):
                        rounding_acc = account_cache.get('3999')
                        if not rounding_acc:
                            rounding_acc, _ = KontoAccount.objects.get_or_create(
                                company=company, code='3999',
                                defaults={'name': 'Zaokruzenja', 'account_type': 'expense', 'is_active': True},
                            )
                            account_cache['3999'] = rounding_acc
                        if diff > 0:
                            parsed_lines.append({'account': rounding_acc, 'side': 'credit', 'amount': diff, 'description': 'Zaokruzenje URA'})
                        else:
                            parsed_lines.append({'account': rounding_acc, 'side': 'debit', 'amount': abs(diff), 'description': 'Zaokruzenje URA'})
                    else:
                        errors += 1
                        continue

                with transaction.atomic():
                    je = JournalEntry.objects.create(
                        company=company, entry_number=entry_number,
                        date=entry_date, description=description,
                        source_type='invoice', is_posted=False,
                    )
                    for pl in parsed_lines:
                        LedgerLine.objects.create(
                            journal_entry=je, account=pl['account'],
                            side=pl['side'], amount=pl['amount'],
                            description=pl['description'],
                        )
                        line_count += 1
                    je.is_posted = True
                    je.save(update_fields=['is_posted'])
                    created += 1

            except (ValueError, TypeError):
                errors += 1

        dur = time.time() - t0
        self.stdout.write('  URA: %d new, %d exist, %d lines, %d err (%.1fs)' % (created, skipped, line_count, errors, dur))
        self._log_sync(company, 'ura', len(headers), created, 0, errors, fi['folder_name'], dur)
        return {'ura_created': created, 'ura_skipped': skipped, 'ura_lines': line_count, 'ura_errors': errors}

    def _import_employees(self, company, fi, dry_run):
        t0 = time.time()
        emp_rows = mdb_export(fi['storage_path'], 'EMPLOYEES')
        worker_rows = mdb_export(fi['storage_path'], 'WORKER')

        if not emp_rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Employees: %d emps, %d workers' % (len(emp_rows), len(worker_rows)))
            return {'employees_would_import': len(emp_rows)}

        worker_by_id = {}
        for w in worker_rows:
            wid = (w.get('WORKER_ID') or '').strip()
            if wid:
                worker_by_id[wid] = w

        for row in emp_rows:
            stuff_id = (row.get('STUFF_ID') or '').strip()
            worker = worker_by_id.get(stuff_id, {})
            if not row.get('STUFF_DATEOFBIRTH') and worker.get('STUFF_DATEOFBIRTH'):
                row['STUFF_DATEOFBIRTH'] = worker['STUFF_DATEOFBIRTH']
            if not row.get('STUFF_CITY') and worker.get('STUFF_CITY'):
                row['STUFF_CITY'] = worker['STUFF_CITY']

        from synesis.views import _import_employees
        res = _import_employees(company, emp_rows)
        dur = time.time() - t0
        c, u, e = res.get('created', 0), res.get('updated', 0), res.get('errors', 0)
        self.stdout.write('  Employees: %d new, %d upd, %d err (%.1fs)' % (c, u, e, dur))
        self._log_sync(company, 'employees', len(emp_rows), c, u, e, fi['folder_name'], dur)
        return {'employees_created': c, 'employees_updated': u, 'employees_errors': e}

    def _import_payroll(self, company, fi, dry_run):
        from konto.models import JournalEntry, LedgerLine, KontoAccount
        from payroll.models import PayrollRun
        t0 = time.time()

        headers = mdb_export(fi['storage_path'], 'PAYROLL2')
        lines = mdb_export(fi['storage_path'], 'TPAYROLL2')

        if not headers:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Payroll: %d headers, %d lines' % (len(headers), len(lines)))
            return {'payroll_would_import': len(headers)}

        payroll_by_period = defaultdict(list)
        for hdr in headers:
            try:
                y = int((hdr.get('PAYROLL_YEAR') or '0').strip())
                m = int((hdr.get('PAYROLL_MONTH') or '0').strip())
                if y > 0 and 1 <= m <= 12:
                    payroll_by_period[(y, m)].append(hdr)
            except (ValueError, TypeError):
                continue

        account_cache = {acc.code.strip(): acc for acc in KontoAccount.objects.filter(company=company)}
        runs_created = runs_skipped = je_created = errors = 0
        year = fi.get('year', '')

        def _get_acc(code, name, atype):
            acc = account_cache.get(code)
            if not acc:
                acc, _ = KontoAccount.objects.get_or_create(
                    company=company, code=code,
                    defaults={'name': name, 'account_type': atype, 'is_active': True},
                )
                account_cache[code] = acc
            return acc

        for (pay_year, pay_month), pay_rows in payroll_by_period.items():
            try:
                run, was_new = PayrollRun.objects.get_or_create(
                    company=company, year=pay_year, month=pay_month,
                    defaults={'status': 'FINALIZED'},
                )
                if not was_new:
                    runs_skipped += 1
                    continue

                runs_created += 1

                total_gross = Decimal('0')
                total_net = Decimal('0')
                total_tax = Decimal('0')

                for pr in pay_rows:
                    total_gross += safe_dec(pr.get('PAYROLL_BRUTTOAMMOUNT', pr.get('PAYROLL_TOTALAMMOUNT', '0')))
                    total_net += safe_dec(pr.get('PAYROLL_FINALAMMOUNT', '0'))
                    total_tax += safe_dec(pr.get('PAYROLL_TAXTOTAL', pr.get('PAYROLL_TAXAMMOUNT', '0')))

                run.total_gross = total_gross
                run.total_net = total_net
                run.total_tax = total_tax
                run.save(update_fields=['total_gross', 'total_net', 'total_tax'])

                entry_number = 'PLACA-%s-%02d' % (year, pay_month)
                if JournalEntry.objects.filter(company=company, entry_number=entry_number).exists():
                    continue

                if total_gross <= 0:
                    continue

                contributions = total_gross - total_net - total_tax
                if contributions < 0:
                    contributions = Decimal('0')

                acc_bruto = _get_acc('4200', 'Bruto place', 'expense')
                acc_neto = _get_acc('2400', 'Obveze za neto place', 'liability')
                acc_porez = _get_acc('2401', 'Obveze za porez iz place', 'liability')
                acc_doprinosi = _get_acc('2402', 'Obveze za doprinose iz place', 'liability')

                entry_date = parse_date(pay_rows[0].get('TRANDATE', ''))
                if not entry_date:
                    from datetime import date
                    entry_date = date(pay_year, pay_month, 28)

                parsed_lines = [
                    {'account': acc_bruto, 'side': 'debit', 'amount': total_gross, 'description': 'Bruto place %02d/%d' % (pay_month, pay_year)},
                ]
                credit_total = Decimal('0')

                if total_net > 0:
                    parsed_lines.append({'account': acc_neto, 'side': 'credit', 'amount': total_net, 'description': 'Neto place %02d/%d' % (pay_month, pay_year)})
                    credit_total += total_net
                if total_tax > 0:
                    parsed_lines.append({'account': acc_porez, 'side': 'credit', 'amount': total_tax, 'description': 'Porez iz place %02d/%d' % (pay_month, pay_year)})
                    credit_total += total_tax
                if contributions > 0:
                    parsed_lines.append({'account': acc_doprinosi, 'side': 'credit', 'amount': contributions, 'description': 'Doprinosi %02d/%d' % (pay_month, pay_year)})
                    credit_total += contributions

                # For payroll, don't force contributions to be 0 if negative
                # Instead, recalculate: credit_total must equal total_gross
                diff = total_gross - credit_total
                if diff != Decimal('0'):
                    # Add rounding/adjustment line to balance
                    adj_acc = _get_acc('3999', 'Zaokruzenja', 'expense')
                    if diff > 0:
                        parsed_lines.append({'account': adj_acc, 'side': 'credit', 'amount': diff, 'description': 'Razlika obracun placa %02d/%d' % (pay_month, pay_year)})
                    else:
                        parsed_lines.append({'account': adj_acc, 'side': 'debit', 'amount': abs(diff), 'description': 'Razlika obracun placa %02d/%d' % (pay_month, pay_year)})

                with transaction.atomic():
                    je = JournalEntry.objects.create(
                        company=company, entry_number=entry_number,
                        date=entry_date,
                        description='Obracun placa %02d/%d (Synesis)' % (pay_month, pay_year),
                        source_type='payroll', is_posted=False,
                    )
                    for pl in parsed_lines:
                        LedgerLine.objects.create(
                            journal_entry=je, account=pl['account'],
                            side=pl['side'], amount=pl['amount'],
                            description=pl['description'],
                        )
                    je.is_posted = True
                    je.save(update_fields=['is_posted'])
                    je_created += 1

            except (ValueError, TypeError):
                errors += 1

        dur = time.time() - t0
        self.stdout.write('  Payroll: %d runs, %d exist, %d JE, %d err (%.1fs)' % (runs_created, runs_skipped, je_created, errors, dur))
        self._log_sync(company, 'payroll', len(headers), runs_created, 0, errors, fi['folder_name'], dur)
        return {
            'payroll_runs_created': runs_created, 'payroll_runs_skipped': runs_skipped,
            'payroll_je_created': je_created, 'payroll_errors': errors,
        }

    def _import_bank(self, company, fi, dry_run):
        from konto.models import BankAccount, KontoAccount
        t0 = time.time()

        rows = mdb_export(fi['storage_path'], 'BANKACCOUNTS')
        bank_rows = mdb_export(fi['storage_path'], 'BANK')

        if not rows and not bank_rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Bank: %d accounts, %d bank records' % (len(rows), len(bank_rows)))
            return {'bank_would_import': len(rows) + len(bank_rows)}

        created = updated = errors = 0

        for row in rows:
            try:
                iban = (row.get('BANK_IBAN') or '').strip()
                name = (row.get('BANK_NAME') or row.get('BANKNAME') or '').strip()
                book_acc = (row.get('BANK_BOOKACCOUNT') or '').strip()

                if not iban or len(iban) < 10:
                    continue

                konto_acc = None
                if book_acc:
                    konto_acc = KontoAccount.objects.filter(company=company, code=book_acc).first()

                obj, was_created = BankAccount.objects.update_or_create(
                    company=company, iban=iban,
                    defaults={
                        'name': name or ('Racun ' + iban[-8:]),
                        'bank_name': name.split('-')[0].strip() if '-' in name else name,
                        'konto_account': konto_acc,
                        'currency': 'EUR',
                        'is_active': True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except DatabaseError:
                errors += 1

        for row in bank_rows:
            try:
                iban = (row.get('BANKIBAN') or '').strip()
                name = (row.get('BANKNAME') or '').strip()
                swift = (row.get('BANK_SWIFT') or '').strip()

                if not iban or len(iban) < 10:
                    continue

                obj, was_created = BankAccount.objects.get_or_create(
                    company=company, iban=iban,
                    defaults={
                        'name': name or ('Racun ' + iban[-8:]),
                        'bank_name': name.split('-')[0].strip() if '-' in name else name,
                        'swift': swift,
                        'currency': 'EUR',
                        'is_active': True,
                    },
                )
                if was_created:
                    created += 1
            except DatabaseError:
                pass

        dur = time.time() - t0
        self.stdout.write('  Bank: %d new, %d upd, %d err (%.1fs)' % (created, updated, errors, dur))
        self._log_sync(company, 'bank', len(rows) + len(bank_rows), created, updated, errors, fi['folder_name'], dur)
        return {'bank_created': created, 'bank_updated': updated, 'bank_errors': errors}

    def _import_retail(self, company, fi, dry_run):
        t0 = time.time()
        retail_rows = mdb_export(fi['storage_path'], 'RETAIL')
        tretail_rows = mdb_export(fi['storage_path'], 'TRETAIL')

        if not retail_rows:
            return {}
        if dry_run:
            self.stdout.write('  [DRY] Retail: %d headers, %d lines' % (len(retail_rows), len(tretail_rows)))
            return {'retail_would_import': len(retail_rows)}

        try:
            from synesis.views import _import_retail
            res = _import_retail(company, retail_rows, tretail_rows)
            dur = time.time() - t0
            c = res.get('created', 0)
            u = res.get('updated', 0)
            e = res.get('errors', 0)
            self.stdout.write('  Retail: %d new, %d exist, %d err (%.1fs) [%d lines]' % (c, u, e, dur, len(tretail_rows)))
            self._log_sync(company, 'retail', len(retail_rows), c, u, e, fi['folder_name'], dur)
            return {'retail_created': c, 'retail_updated': u, 'retail_errors': e}
        except ImportError as exc:
            dur = time.time() - t0
            self.stderr.write(self.style.ERROR('  Retail error: %s' % exc))
            return {'retail_errors': 1}
