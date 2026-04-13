"""
synesis/management/commands/synesis_server_sync.py
Server-side sync from MDB files directly (no Windows BAT needed).
Usage:
  python manage.py synesis_server_sync --company "Konjik d.o.o." --mdb-dir /var/www/fina-connect/synesis/KONJIK
  python manage.py synesis_server_sync --company "Konjik d.o.o." --type partners
  python manage.py synesis_server_sync --company "Konjik d.o.o." --type items
  python manage.py synesis_server_sync --company "Konjik d.o.o." --type all
"""
import csv
import io
import subprocess
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sync Synesis MDB data directly from server filesystem'

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True, help='Company name or OIB')
        parser.add_argument('--mdb-dir', default='/var/www/fina-connect/synesis/KONJIK',
                            help='Directory containing Storage.mdb, Journal.mdb')
        parser.add_argument('--type', default='all', choices=['all', 'partners', 'items', 'pos'],
                            help='What to sync')

    def handle(self, *args, **options):
        from companies.models import Company
        from synesis.models import SynesisConfig

        company_q = options['company']
        try:
            company = Company.objects.get(name=company_q)
        except Company.DoesNotExist:
            try:
                company = Company.objects.get(oib=company_q)
            except Company.DoesNotExist:
                raise CommandError(f'Company not found: {company_q}')

        cfg, _ = SynesisConfig.objects.get_or_create(company=company)
        mdb_dir = options['mdb_dir'].rstrip('/')
        sync_type = options['type']

        storage_path = f'{mdb_dir}/Storage.mdb'
        journal_path = f'{mdb_dir}/Journal.mdb'

        self.stdout.write(f'Company: {company.name} ({company.oib})')
        self.stdout.write(f'MDB dir: {mdb_dir}')
        self.stdout.write('')

        if sync_type in ('all', 'partners'):
            self._sync_partners(company, cfg, storage_path)

        if sync_type in ('all', 'items'):
            self._sync_items(company, cfg, storage_path)

        if sync_type in ('all', 'pos'):
            # Find POS MDB
            import glob
            pos_files = glob.glob(f'{mdb_dir}/Kasa*.mdb')
            if pos_files:
                self._sync_pos(company, cfg, pos_files[0])
            else:
                self.stdout.write(self.style.WARNING('No POS (Kasa*.mdb) file found, skipping'))

        self.stdout.write(self.style.SUCCESS('\nSync complete!'))

    def _read_mdb_table(self, mdb_path, table_name):
        """Read an MDB table using mdb-export and return list of dicts."""
        result = subprocess.run(
            ['mdb-export', mdb_path, table_name],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            self.stderr.write(f'mdb-export error: {result.stderr}')
            return []

        reader = csv.DictReader(io.StringIO(result.stdout))
        return list(reader)

    def _sync_partners(self, company, cfg, storage_path):
        from synesis.views import _import_partners
        from synesis.models import SynesisLog

        self.stdout.write('--- Syncing PARTNERS ---')
        t0 = time.time()

        rows = self._read_mdb_table(storage_path, 'PARTNERS')
        self.stdout.write(f'  Read {len(rows)} partners from MDB')

        if not rows:
            return

        # Pass raw MDB rows directly — _import_partners maps the fields
        result = _import_partners(company, rows)
        duration = round(time.time() - t0, 2)

        cfg.last_sync_partners = timezone.now()
        cfg.partners_total = result.get('total_in_db', 0)
        cfg.save(update_fields=['last_sync_partners', 'partners_total', 'updated_at'])

        SynesisLog.objects.create(
            company=company, sync_type='partners',
            records_received=len(rows),
            records_created=result.get('created', 0),
            records_updated=result.get('updated', 0),
            errors=result.get('errors', 0),
            error_detail=result.get('error_detail', ''),
            duration_seconds=duration,
        )

        self.stdout.write(self.style.SUCCESS(
            f'  Partners: {result.get("created",0)} created, '
            f'{result.get("updated",0)} updated, '
            f'{result.get("errors",0)} errors ({duration}s)'
        ))

    def _sync_items(self, company, cfg, storage_path):
        from synesis.views import _import_items
        from synesis.models import SynesisLog

        self.stdout.write('--- Syncing ITEMS ---')
        t0 = time.time()

        rows = self._read_mdb_table(storage_path, 'ITEMS')
        self.stdout.write(f'  Read {len(rows)} items from MDB')

        if not rows:
            return

        # Pass raw MDB rows directly — _import_items maps the fields
        result = _import_items(company, rows)
        duration = round(time.time() - t0, 2)

        cfg.last_sync_items = timezone.now()
        cfg.items_total = result.get('total_in_db', 0)
        cfg.save(update_fields=['last_sync_items', 'items_total', 'updated_at'])

        SynesisLog.objects.create(
            company=company, sync_type='items',
            records_received=len(rows),
            records_created=result.get('created', 0),
            records_updated=result.get('updated', 0),
            errors=result.get('errors', 0),
            error_detail=result.get('error_detail', ''),
            duration_seconds=duration,
        )

        self.stdout.write(self.style.SUCCESS(
            f'  Items: {result.get("created",0)} created, '
            f'{result.get("updated",0)} updated, '
            f'{result.get("errors",0)} errors ({duration}s)'
        ))

    def _sync_pos(self, company, cfg, pos_path):
        from synesis.views import _import_pos
        from synesis.models import SynesisLog

        self.stdout.write(f'--- Syncing POS from {pos_path} ---')
        t0 = time.time()

        # Read Receipts table
        rows = self._read_mdb_table(pos_path, 'Receipts')
        self.stdout.write(f'  Read {len(rows)} POS receipts from MDB')

        if not rows:
            self.stdout.write(self.style.WARNING('  No receipts found'))
            return

        # Map to expected format
        receipts = []
        for r in rows:
            receipts.append({
                'Receipt_Number': r.get('Receipt_Number') or r.get('RECEIPT_NUMBER', ''),
                'Receipt_Date': r.get('Receipt_Date') or r.get('RECEIPT_DATE', ''),
                'Receipt_Ammount': r.get('Receipt_Ammount') or r.get('RECEIPT_AMMOUNT', '0'),
                'Receipt_PayType': r.get('Receipt_PayType') or r.get('RECEIPT_PAYTYPE', ''),
            })

        data = {'receipts': receipts, 'pos_name': 'Kasa (server sync)'}
        result = _import_pos(company, data)
        duration = round(time.time() - t0, 2)

        SynesisLog.objects.create(
            company=company, sync_type='pos',
            records_received=len(receipts),
            records_created=result.get('created', 0),
            records_updated=result.get('updated', 0),
            errors=result.get('errors', 0),
            duration_seconds=duration,
        )

        self.stdout.write(self.style.SUCCESS(
            f'  POS: {len(receipts)} receipts processed ({duration}s)'
        ))
