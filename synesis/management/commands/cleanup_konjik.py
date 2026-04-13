"""
synesis/management/commands/cleanup_konjik.py

Čisti pogrešno importirane podatke iz Konjik recorda.
Sve što NIJE iz KONJIK D.O.O. foldera → briše se.

Usage:
    python manage.py cleanup_konjik --dry-run    # preview
    python manage.py cleanup_konjik --execute    # stvarno brisanje
    python manage.py cleanup_konjik --validate   # validacija vs Excel
"""
import os
import time
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q, Sum

KONJIK_OIB = '37590751921'
KONJIK_SOURCES = {'KONJIK D.O.O. 2025', 'KONJIK D.O.O. 2025(Popravljeno 1)'}


class Command(BaseCommand):
    help = 'Cleanup wrong multi-client import from Konjik record'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without deleting')
        parser.add_argument('--execute', action='store_true', help='Actually delete foreign data')
        parser.add_argument('--validate', action='store_true', help='Validate vs Excel after cleanup')
        parser.add_argument('--excel', default='Konjik/Podaci-KONJIK D.O.O.-2025.xls', help='Path to validation Excel')

    def handle(self, *args, **options):
        from companies.models import Company
        from synesis.models import SynesisLog

        konjik = Company.objects.get(oib=KONJIK_OIB)
        self.stdout.write('Firma: %s (PK: %s)' % (konjik.name, konjik.pk))

        # Step 1: Identify foreign imports
        all_logs = SynesisLog.objects.filter(company=konjik)
        foreign_sources = set()
        konjik_sources = set()

        for log in all_logs:
            src = (log.error_detail or '').strip()
            if not src:
                continue
            # Extract source folder name
            src_clean = src.replace('Archive: ', '').strip()
            is_konjik = any(k in src_clean.upper() for k in ['KONJIK D.O.O.', 'KONJIK D.O.O'])
            if is_konjik:
                konjik_sources.add(src_clean)
            else:
                foreign_sources.add(src_clean)

        self.stdout.write('\nKonjik sources: %s' % konjik_sources)
        self.stdout.write('Foreign sources: %d' % len(foreign_sources))
        for s in sorted(foreign_sources)[:10]:
            self.stdout.write('  - %s' % s)
        if len(foreign_sources) > 10:
            self.stdout.write('  ... +%d more' % (len(foreign_sources) - 10))

        if options['validate']:
            self._validate(konjik, options['excel'])
            return

        # Step 2: Count what needs to be deleted
        from inventory.models import InventoryItem
        from invoicing.models import Invoice
        from konto.models import JournalEntry, LedgerLine
        from partners.models import Partner

        # JournalEntries from foreign imports have entry_numbers like SYN-2025-*
        # But we can't distinguish by entry_number alone.
        # Better: use SynesisLog to find which JEs were created per source folder.

        # Actually, the import script doesn't store source folder on JE.
        # The only way is: JEs created by Konjik's own import are from KONJIK folder.
        # But since we imported ALL folders into Konjik, they all have same company_id.

        # Strategy: Delete ALL, then reimport only KONJIK folder.
        # This is cleaner than trying to identify individual records.

        total_je = JournalEntry.objects.filter(company=konjik).count()
        total_ll = LedgerLine.objects.filter(journal_entry__company=konjik).count()
        total_partners = Partner.objects.filter(company=konjik).count()
        total_items = InventoryItem.objects.filter(company=konjik).count()
        total_invoices = Invoice.objects.filter(company=konjik).count()

        d_total = LedgerLine.objects.filter(
            journal_entry__company=konjik, side='debit'
        ).aggregate(s=Sum('amount'))['s'] or 0

        self.stdout.write('\n=== CURRENT STATE ===')
        self.stdout.write('JournalEntries:  %d' % total_je)
        self.stdout.write('LedgerLines:     %d' % total_ll)
        self.stdout.write('Partners:        %d' % total_partners)
        self.stdout.write('Items:           %d' % total_items)
        self.stdout.write('Invoices:        %d' % total_invoices)
        self.stdout.write('Total Debit:     %.2f EUR' % d_total)

        self.stdout.write('\n=== EXPECTED AFTER CLEANUP (from Excel) ===')
        self.stdout.write('Knjiženja:       ~23,755')
        self.stdout.write('Konata:          398')
        self.stdout.write('Partnera:        957')
        self.stdout.write('URA:             1,863')
        self.stdout.write('Duguje:          2,545,113.35 EUR')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDRY RUN — nothing deleted'))
            self.stdout.write('Would delete: %d JE, %d LL' % (total_je, total_ll))
            self.stdout.write('Then reimport with: --filter "KONJIK D.O.O." --per-client')
            return

        if not options['execute']:
            self.stdout.write(self.style.ERROR('\nUse --dry-run or --execute'))
            return

        # Step 3: Backup counts
        self.stdout.write(self.style.WARNING('\n=== EXECUTING CLEANUP ==='))

        # Delete temeljnice (JournalEntry + LedgerLine cascade)
        t0 = time.time()
        with transaction.atomic():
            # Delete all LedgerLines first (faster than cascade)
            ll_deleted = LedgerLine.objects.filter(journal_entry__company=konjik).delete()[0]
            je_deleted = JournalEntry.objects.filter(company=konjik).delete()[0]

        self.stdout.write('  Deleted: %d LedgerLines, %d JournalEntries (%.1fs)' % (
            ll_deleted, je_deleted, time.time() - t0))

        # Delete foreign partners (keep those referenced in invoices)
        # Actually: delete ALL partners, reimport will recreate Konjik's own
        # But invoices reference partners... so keep partners for now

        # Delete SynesisLogs for foreign sources
        foreign_logs = SynesisLog.objects.filter(company=konjik).exclude(
            error_detail__icontains='KONJIK D.O.O.'
        )
        fl_count = foreign_logs.count()
        foreign_logs.delete()
        self.stdout.write('  Deleted: %d foreign SynesisLog entries' % fl_count)

        self.stdout.write(self.style.SUCCESS('\nCLEANUP COMPLETE'))
        self.stdout.write('Next steps:')
        self.stdout.write('  1. python manage.py bulk_import_synesis --company "Konjik d.o.o." --filter "KONJIK D.O.O." --type accounts,temeljnice,ura')
        self.stdout.write('  2. python manage.py cleanup_konjik --validate')
        self.stdout.write('  3. python manage.py bulk_import_synesis --per-client --type all  (za ostale klijente)')

    def _validate(self, konjik, excel_path):
        """Validate LC data vs Synesis Excel export."""
        import warnings
        warnings.filterwarnings('ignore')

        full_path = os.path.join('/var/www/fina-connect', excel_path)
        if not os.path.exists(full_path):
            self.stderr.write('Excel not found: %s' % full_path)
            return

        import xlrd
        wb = xlrd.open_workbook(full_path)
        ws = wb.sheet_by_name('Dnevnik_knjiženja')

        # Synesis totals per konto
        xls_d = defaultdict(lambda: Decimal('0'))
        xls_p = defaultdict(lambda: Decimal('0'))
        for r in range(1, ws.nrows):
            k = str(ws.cell_value(r, 4)).strip()
            xls_d[k] += Decimal(str(round(ws.cell_value(r, 7) or 0, 2)))
            xls_p[k] += Decimal(str(round(ws.cell_value(r, 8) or 0, 2)))

        # LC totals per konto
        from konto.models import LedgerLine
        lc_data = LedgerLine.objects.filter(
            journal_entry__company=konjik,
        ).values('account__code').annotate(
            d=Sum('amount', filter=Q(side='debit')),
            p=Sum('amount', filter=Q(side='credit')),
            cnt=Count('id'),
        )
        lc_d = {r['account__code']: r['d'] or Decimal('0') for r in lc_data}
        lc_p = {r['account__code']: r['p'] or Decimal('0') for r in lc_data}

        # Compare
        all_kontos = sorted(set(xls_d.keys()) | set(lc_d.keys()))
        ok = diff = 0
        total_diff_d = Decimal('0')

        self.stdout.write('\n=== VALIDACIJA: Excel vs LC ===')
        diffs = []
        for k in all_kontos:
            sd, sp = xls_d.get(k, Decimal('0')), xls_p.get(k, Decimal('0'))
            ld, lp = lc_d.get(k, Decimal('0')), lc_p.get(k, Decimal('0'))
            dd, dp = ld - sd, lp - sp

            if abs(dd) <= Decimal('0.01') and abs(dp) <= Decimal('0.01'):
                ok += 1
            else:
                diff += 1
                total_diff_d += dd
                diffs.append((k, sd, ld, dd, dp))

        self.stdout.write('Konata identičnih: %d' % ok)
        self.stdout.write('Konata s razlikom: %d' % diff)
        self.stdout.write('Ukupna razlika D:  %.2f EUR' % total_diff_d)

        if diffs:
            self.stdout.write('\nRazlike:')
            self.stdout.write('%-8s %12s %12s %12s %12s' % ('Konto', 'XLS D', 'LC D', 'Diff D', 'Diff P'))
            for k, sd, ld, dd, dp in sorted(diffs, key=lambda x: -abs(x[3]))[:20]:
                self.stdout.write('%-8s %12.2f %12.2f %+12.2f %+12.2f' % (k, sd, ld, dd, dp))

        if diff == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ VALIDACIJA USPJEŠNA — SVE IDENTIČNO!'))
        else:
            self.stdout.write(self.style.ERROR('\n✗ VALIDACIJA NEUSPJEŠNA — %d konata s razlikom' % diff))
