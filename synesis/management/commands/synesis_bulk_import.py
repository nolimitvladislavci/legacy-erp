"""
synesis/management/commands/synesis_bulk_import.py
Bulk import from Synesis archive -- scans directory for client folders.
"""
import csv
import io
import os
import re
import subprocess
import time
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, IntegrityError


class Command(BaseCommand):
    help = 'Bulk import Synesis archive folders into ERP'

    def add_arguments(self, parser):
        parser.add_argument('--archive-dir', required=True)
        parser.add_argument('--company', default='')
        parser.add_argument('--per-client', action='store_true')
        parser.add_argument('--analyze', action='store_true')
        parser.add_argument('--filter', default='')
        parser.add_argument('--type', default='all', choices=['all', 'partners', 'items', 'invoices', 'retail', 'employees'])
        parser.add_argument('--year', default='')

    def handle(self, *args, **options):
        archive_dir = options['archive_dir'].rstrip('/')
        if not os.path.isdir(archive_dir):
            raise CommandError(f'Directory not found: {archive_dir}')
        folders = self._scan_folders(archive_dir, options.get('year'), options.get('filter'))
        if options['analyze']:
            self._analyze(folders)
            return
        if not options['company'] and not options['per_client']:
            raise CommandError('Specify --company or --per-client')
        company = None
        if options['company']:
            from companies.models import Company
            try:
                company = Company.objects.get(name=options['company'])
            except Company.DoesNotExist:
                try:
                    company = Company.objects.get(oib=options['company'])
                except Company.DoesNotExist:
                    raise CommandError(f'Company not found: {options["company"]}')
        sync_type = options['type']
        total_stats = defaultdict(int)
        for fi in folders:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Client: {fi["client"]} ({fi["year"]})')
            target = company
            if options['per_client']:
                target = self._get_or_create_company(fi['client'])
            try:
                stats = self._import_folder(target, fi, sync_type)
                for k, v in stats.items():
                    total_stats[k] += v
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  ERROR: {exc}'))
                total_stats['folder_errors'] += 1
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(self.style.SUCCESS('BULK IMPORT COMPLETE'))
        self.stdout.write(f'  Folders processed: {len(folders)}')
        for k, v in sorted(total_stats.items()):
            self.stdout.write(f'  {k}: {v}')

    def _scan_folders(self, archive_dir, year_filter, name_filter):
        folders = []
        prefixes = [n.strip().upper() for n in (name_filter or '').split(',') if n.strip()]
        for entry in sorted(os.listdir(archive_dir)):
            fp = os.path.join(archive_dir, entry)
            if not os.path.isdir(fp):
                continue
            match = re.match(r'^(.+?)\s+(\d{4})(.*)$', entry)
            if match:
                client, year, suffix = match.group(1).strip(), match.group(2), match.group(3).strip()
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
        self.stdout.write(f'\n{"="*70}')
        self.stdout.write(' SYNESIS ARCHIVE ANALYSIS')
        self.stdout.write(f'{"="*70}\n')
        clients = defaultdict(list)
        for f in folders:
            clients[f['client']].append(f)
        self.stdout.write(f'Total folders: {len(folders)}')
        self.stdout.write(f'Unique clients: {len(clients)}')
        years = defaultdict(int)
        for f in folders:
            years[f['year']] += 1
        self.stdout.write('\nBy year:')
        for y in sorted(years):
            self.stdout.write(f'  {y}: {years[y]} folders')
        self.stdout.write(f'\n{"-"*70}')
        self.stdout.write(f'{"Client":<40} {"Year":>5} {"Storage":>10} {"Journal":>8}')
        self.stdout.write(f'{"-"*70}')
        for f in folders:
            smb = f'{f["storage_size"]/1024/1024:.1f}MB' if f["has_storage"] else '---'
            jrn = 'Yes' if f['has_journal'] else '---'
            self.stdout.write(f'{f["client"]:<40} {f["year"]:>5} {smb:>10} {jrn:>8}')
            if f['has_storage']:
                counts = self._quick_counts(f['storage_path'])
                if counts:
                    parts = [f'{k}:{v}' for k, v in counts.items() if v > 0]
                    if parts:
                        self.stdout.write(f'    -> {", ".join(parts)}')
        self.stdout.write(f'{"-"*70}')

    def _quick_counts(self, storage_path):
        counts = {}
        for table in ['PARTNERS', 'ITEMS', 'INVOICES', 'EMPLOYEES']:
            try:
                r = subprocess.run(['mdb-export', storage_path, table],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    counts[table.lower()] = max(0, len(r.stdout.strip().split('\n')) - 1)
            except (ValueError, AttributeError):
                pass
        return counts

    def _read_mdb_table(self, mdb_path, table_name):
        r = subprocess.run(['mdb-export', mdb_path, table_name],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        return list(csv.DictReader(io.StringIO(r.stdout)))

    def _import_folder(self, company, fi, sync_type):
        from synesis.models import SynesisLog
        from synesis.views import _import_items, _import_partners
        stats = defaultdict(int)
        if not fi['has_storage']:
            self.stdout.write(self.style.WARNING('  No Storage.mdb -- skipping'))
            return stats
        storage = fi['storage_path']
        if sync_type in ('all', 'partners'):
            self.stdout.write('  Importing partners...')
            t0 = time.time()
            rows = self._read_mdb_table(storage, 'PARTNERS')
            if rows:
                res = _import_partners(company, rows)
                dur = round(time.time() - t0, 2)
                self.stdout.write(f'    {res.get("created",0)} new, {res.get("updated",0)} upd, {res.get("errors",0)} err ({dur}s)')
                stats['partners_created'] += res.get('created', 0)
                stats['partners_updated'] += res.get('updated', 0)
                SynesisLog.objects.create(company=company, sync_type='partners',
                    records_received=len(rows), records_created=res.get('created', 0),
                    records_updated=res.get('updated', 0), errors=res.get('errors', 0),
                    error_detail=f'Archive: {fi["folder_name"]}', duration_seconds=dur)
        if sync_type in ('all', 'items'):
            self.stdout.write('  Importing items...')
            t0 = time.time()
            rows = self._read_mdb_table(storage, 'ITEMS')
            if rows:
                res = _import_items(company, rows)
                dur = round(time.time() - t0, 2)
                self.stdout.write(f'    {res.get("created",0)} new, {res.get("updated",0)} upd, {res.get("errors",0)} err ({dur}s)')
                stats['items_created'] += res.get('created', 0)
                stats['items_updated'] += res.get('updated', 0)
                SynesisLog.objects.create(company=company, sync_type='items',
                    records_received=len(rows), records_created=res.get('created', 0),
                    records_updated=res.get('updated', 0), errors=res.get('errors', 0),
                    error_detail=f'Archive: {fi["folder_name"]}', duration_seconds=dur)
        if sync_type in ('all', 'invoices'):
            self.stdout.write('  Importing invoices...')
            t0 = time.time()
            inv_rows = self._read_mdb_table(storage, 'INVOICES')
            tinv_rows = self._read_mdb_table(storage, 'TINVOICES')
            if inv_rows:
                # Build line items lookup by DIN
                lines_by_din = defaultdict(list)
                for lr in tinv_rows:
                    din = lr.get('DIN', '').strip()
                    if din:
                        lines_by_din[din].append(lr)
                # Prepare data for _import_invoices: add _items and _synesis_year
                for inv_row in inv_rows:
                    din = inv_row.get('DIN', '').strip()
                    inv_row['_items'] = lines_by_din.get(din, [])
                    inv_row['_synesis_year'] = fi.get('year', '')
                    # Map field names expected by _import_invoices
                    inv_row['TRANCODE'] = din
                    inv_row['TRANDATE'] = inv_row.get('INVOICE_DATE', '')
                    inv_row['INVOICE_TOTAL'] = inv_row.get('INVOICETOTAL', inv_row.get('VAT_INVOICEAMMOUNT', '0'))
                    inv_row['INVOICE_TAX'] = inv_row.get('VAT_AMMOUNT', '0')
                    inv_row['INVOICE_DUEDATE'] = inv_row.get('INVOICE_DUEDATE', '') if 'INVOICE_DUEDATE' in inv_row else ''
                try:
                    from synesis.views import _import_invoices
                    # _import_invoices expects (request, company, data_list) but we pass None for request
                    c, u, e = _import_invoices(None, company, inv_rows)
                    dur = round(time.time() - t0, 2)
                    self.stdout.write(f'    {c} new, {u} upd, {e} err ({dur}s) [{len(tinv_rows)} line items]')
                    stats['invoices_created'] += c
                    stats['invoices_updated'] += u
                    stats['invoices_errors'] += e
                    SynesisLog.objects.create(company=company, sync_type='invoices',
                        records_received=len(inv_rows), records_created=c,
                        records_updated=u, errors=e,
                        error_detail=f'Archive: {fi["folder_name"]}', duration_seconds=dur)
                except (IntegrityError, DatabaseError) as exc:
                    dur = round(time.time() - t0, 2)
                    self.stderr.write(self.style.ERROR(f'    Invoice import error: {exc}'))
                    stats['invoices_errors'] += 1
        if sync_type in ('all', 'retail'):
            self.stdout.write('  Importing retail (primke)...')
            t0 = time.time()
            retail_rows = self._read_mdb_table(storage, 'RETAIL')
            tretail_rows = self._read_mdb_table(storage, 'TRETAIL')
            if retail_rows:
                try:
                    from synesis.views import _import_retail
                    res = _import_retail(company, retail_rows, tretail_rows)
                    dur = round(time.time() - t0, 2)
                    self.stdout.write(f'    {res.get("created",0)} new, {res.get("updated",0)} exist, {res.get("errors",0)} err ({dur}s) [{len(tretail_rows)} lines]')
                    stats['retail_created'] += res.get('created', 0)
                    stats['retail_updated'] += res.get('updated', 0)
                    SynesisLog.objects.create(company=company, sync_type='retail',
                        records_received=len(retail_rows), records_created=res.get('created', 0),
                        records_updated=res.get('updated', 0), errors=res.get('errors', 0),
                        error_detail=f'Archive: {fi["folder_name"]}', duration_seconds=dur)
                except (IntegrityError, DatabaseError) as exc:
                    self.stderr.write(self.style.ERROR(f'    Retail import error: {exc}'))
                    stats['retail_errors'] += 1
        if sync_type in ('all', 'employees'):
            self.stdout.write('  Importing employees...')
            t0 = time.time()
            rows = self._read_mdb_table(storage, 'EMPLOYEES')
            if rows:
                try:
                    from synesis.views import _import_employees
                    res = _import_employees(company, rows)
                    dur = round(time.time() - t0, 2)
                    self.stdout.write(f'    {res.get("created",0)} new, {res.get("updated",0)} upd, {res.get("errors",0)} err ({dur}s)')
                    stats['employees_created'] += res.get('created', 0)
                    stats['employees_updated'] += res.get('updated', 0)
                    SynesisLog.objects.create(company=company, sync_type='employees',
                        records_received=len(rows), records_created=res.get('created', 0),
                        records_updated=res.get('updated', 0), errors=res.get('errors', 0),
                        error_detail=f'Archive: {fi["folder_name"]}', duration_seconds=dur)
                except (IntegrityError, DatabaseError) as exc:
                    self.stderr.write(self.style.ERROR(f'    Employee import error: {exc}'))
                    stats['employees_errors'] += 1
        return stats

    def _get_or_create_company(self, client_name):
        from companies.models import Company
        name = client_name.strip().title()
        try:
            return Company.objects.get(name__iexact=name)
        except Company.DoesNotExist:
            self.stdout.write(f'  Creating company: {name}')
            return Company.objects.create(name=name, oib=f'SYN-{name[:8].upper()}')
