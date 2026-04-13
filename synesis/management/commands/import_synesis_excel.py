"""
synesis/management/commands/import_synesis_excel.py

Import dnevnika knjiženja iz Synesis Excel exporta.
Excel je JEDINI 100% kompletan izvor dnevnika — generiran internom
Synesis agreacijom svih tipova dokumenata.

Usage:
    python manage.py import_synesis_excel "Konjik/Podaci-KONJIK D.O.O.-2025.xls" --company "Konjik d.o.o."
    python manage.py import_synesis_excel path.xls --company OIB --dry-run
    python manage.py import_synesis_excel path.xls --company OIB --validate-only
"""
import os, time
from collections import defaultdict
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db import IntegrityError, DatabaseError


def safe_dec(v):
    try:
        return Decimal(str(round(float(v or 0), 2)))
    except (ValueError, TypeError):
        return Decimal('0')


class Command(BaseCommand):
    help = 'Import Synesis Excel export (Dnevnik knjiženja) into LC konto'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', help='Path to Synesis Excel .xls file')
        parser.add_argument('--company', required=True, help='Company name or OIB')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--validate-only', action='store_true', help='Only compare, no import')
        parser.add_argument('--clear-first', action='store_true', help='Delete existing JE before import')

    def handle(self, *args, **options):
        import xlrd, warnings
        warnings.filterwarnings('ignore')

        # Find company
        from companies.models import Company
        try:
            company = Company.objects.get(name__iexact=options['company'])
        except Company.DoesNotExist:
            try:
                company = Company.objects.get(oib=options['company'])
            except Company.DoesNotExist:
                raise CommandError('Company not found: %s' % options['company'])

        self.stdout.write('Company: %s (OIB: %s)' % (company.name, company.oib))

        # Open Excel
        xls_path = os.path.join('/var/www/fina-connect', options['excel_path'])
        if not os.path.exists(xls_path):
            raise CommandError('File not found: %s' % xls_path)

        wb = xlrd.open_workbook(xls_path)

        # ── KONTNI PLAN ──
        if 'Kontni_Plan' in wb.sheet_names():
            ws_k = wb.sheet_by_name('Kontni_Plan')
            self._import_kontni_plan(company, ws_k, options['dry_run'])

        # ── PARTNERI ──
        if 'Partneri' in wb.sheet_names():
            ws_p = wb.sheet_by_name('Partneri')
            self._import_partneri(company, ws_p, options['dry_run'])

        # ── DNEVNIK KNJIŽENJA ──
        ws = wb.sheet_by_name('Dnevnik_knjiženja')
        self.stdout.write('Dnevnik: %d redova' % (ws.nrows - 1))

        # Parse all rows
        entries = []  # [{datum, doc_name, doc_number, konto, partner_id, opis, duguje, potrazuje}]
        for r in range(1, ws.nrows):
            try:
                datum_serial = ws.cell_value(r, 0)
                datum = xlrd.xldate_as_datetime(datum_serial, wb.datemode).date()
            except Exception:
                continue

            entries.append({
                'datum': datum,
                'doc_name': str(ws.cell_value(r, 1)).strip(),
                'doc_number': int(float(ws.cell_value(r, 2) or 0)),
                'org_dio': str(ws.cell_value(r, 3)).strip(),
                'konto': str(ws.cell_value(r, 4)).strip(),
                'partner_id': str(int(float(ws.cell_value(r, 5) or 0))) if ws.cell_value(r, 5) else '',
                'opis': str(ws.cell_value(r, 6)).strip(),
                'duguje': safe_dec(ws.cell_value(r, 7)),
                'potrazuje': safe_dec(ws.cell_value(r, 8)),
            })

        total_d = sum(e['duguje'] for e in entries)
        total_p = sum(e['potrazuje'] for e in entries)
        self.stdout.write('Parsed: %d entries, D=%.2f, P=%.2f, diff=%.2f' % (
            len(entries), total_d, total_p, total_d - total_p))

        if options['validate_only']:
            self._validate(company, entries)
            return

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing imported'))
            return

        # ── CLEAR EXISTING ──
        if options['clear_first']:
            self._clear_existing(company)

        # ── IMPORT ──
        t0 = time.time()
        self._import_dnevnik(company, entries)
        dur = time.time() - t0
        self.stdout.write(self.style.SUCCESS('Import complete in %.1fs' % dur))

        # Auto-validate
        self._validate(company, entries)

    def _import_kontni_plan(self, company, ws, dry_run):
        from konto.models import KontoAccount
        CLASS_MAP = {
            '0': 'asset', '1': 'asset', '2': 'liability', '3': 'asset',
            '4': 'expense', '5': 'expense', '6': 'expense', '7': 'income',
            '8': 'expense', '9': 'equity',
        }
        created = updated = 0
        for r in range(1, ws.nrows):
            code = str(ws.cell_value(r, 0)).strip()
            name = str(ws.cell_value(r, 1)).strip()
            if not code or not name:
                continue
            if dry_run:
                continue
            acc_type = CLASS_MAP.get(code[0], 'asset')
            obj, was_new = KontoAccount.objects.update_or_create(
                company=company, code=code,
                defaults={'name': name, 'account_type': acc_type, 'is_active': True})
            if was_new:
                created += 1
            else:
                updated += 1
        self.stdout.write('Kontni plan: %d new, %d updated' % (created, updated))

    def _import_partneri(self, company, ws, dry_run):
        from partners.models import Partner
        created = skipped = 0
        for r in range(1, ws.nrows):
            name = str(ws.cell_value(r, 1)).strip()
            oib = str(ws.cell_value(r, 2)).strip()
            if not name:
                continue
            if dry_run:
                continue
            exists = False
            if oib and len(oib) >= 11:
                exists = Partner.objects.filter(company=company, oib=oib).exists()
            if not exists:
                exists = Partner.objects.filter(company=company, name=name).exists()
            if exists:
                skipped += 1
                continue
            Partner.objects.create(
                company=company, name=name, oib=oib,
                city=str(ws.cell_value(r, 3)).strip(),
                address=str(ws.cell_value(r, 4)).strip(),
                partner_type='both')
            created += 1
        self.stdout.write('Partneri: %d new, %d existing' % (created, skipped))

    def _clear_existing(self, company):
        from konto.models import JournalEntry, LedgerLine
        from django.db import connection

        with connection.cursor() as c:
            c.execute('ALTER TABLE konto_ledgerline DISABLE TRIGGER USER')
            c.execute('ALTER TABLE konto_journalentry DISABLE TRIGGER USER')

        je_ids = list(JournalEntry.objects.filter(company=company).values_list('id', flat=True))
        total = len(je_ids)
        for i in range(0, total, 500):
            batch = je_ids[i:i+500]
            with transaction.atomic():
                LedgerLine.objects.filter(journal_entry_id__in=batch).delete()
                JournalEntry.objects.filter(id__in=batch).delete()

        with connection.cursor() as c:
            c.execute('ALTER TABLE konto_ledgerline ENABLE TRIGGER USER')
            c.execute('ALTER TABLE konto_journalentry ENABLE TRIGGER USER')

        self.stdout.write('Cleared %d JournalEntries' % total)

    def _import_dnevnik(self, company, entries):
        """
        Group entries by (datum, doc_name, doc_number) → one JournalEntry per group.
        Each entry within the group → one LedgerLine.
        """
        from konto.models import JournalEntry, LedgerLine, KontoAccount

        # Build account cache
        account_cache = {acc.code.strip(): acc for acc in KontoAccount.objects.filter(company=company)}

        TYPE_MAP = {
            '0': 'asset', '1': 'asset', '2': 'liability', '3': 'asset',
            '4': 'expense', '5': 'expense', '6': 'expense', '7': 'income',
            '8': 'expense', '9': 'equity',
        }

        # Group entries
        groups = defaultdict(list)
        for e in entries:
            key = (e['datum'], e['doc_name'], e['doc_number'])
            groups[key].append(e)

        je_created = ll_created = errors = 0

        for (datum, doc_name, doc_number), lines in groups.items():
            entry_number = 'XLS-%s-%s-%d' % (datum.strftime('%Y%m%d'), doc_name[:10], doc_number)

            # Skip if exists
            if JournalEntry.objects.filter(company=company, entry_number=entry_number).exists():
                continue

            # Parse lines
            parsed = []
            total_d = Decimal('0')
            total_c = Decimal('0')

            for line in lines:
                konto = line['konto']
                d = line['duguje']
                c = line['potrazuje']

                if d == 0 and c == 0:
                    continue

                # Get or create account
                account = account_cache.get(konto)
                if not account:
                    acc_type = TYPE_MAP.get(konto[0] if konto else '0', 'asset')
                    account = KontoAccount.objects.create(
                        company=company, code=konto,
                        name='Konto %s' % konto, account_type=acc_type, is_active=True)
                    account_cache[konto] = account

                desc = line['opis'][:200]

                if d > 0:
                    parsed.append({'account': account, 'side': 'debit', 'amount': d, 'description': desc})
                    total_d += d
                if c > 0:
                    parsed.append({'account': account, 'side': 'credit', 'amount': c, 'description': desc})
                    total_c += c

            if not parsed:
                continue

            # Balance check
            diff = total_d - total_c
            if abs(diff) > Decimal('5.00'):
                errors += 1
                continue
            elif abs(diff) > Decimal('0'):
                # Auto-balance with rounding account
                rounding = account_cache.get('3999')
                if not rounding:
                    rounding, _ = KontoAccount.objects.get_or_create(
                        company=company, code='3999',
                        defaults={'name': 'Zaokruženja', 'account_type': 'expense', 'is_active': True})
                    account_cache['3999'] = rounding
                if diff > 0:
                    parsed.append({'account': rounding, 'side': 'credit', 'amount': diff, 'description': 'Zaokruženje'})
                else:
                    parsed.append({'account': rounding, 'side': 'debit', 'amount': abs(diff), 'description': 'Zaokruženje'})

            # Source type from doc_name
            source_map = {
                'PKV promet': 'manual', 'Izvod': 'bank_statement', 'URA': 'invoice',
                'PKV primka': 'manual', 'Račun': 'invoice', 'Promet usluga': 'invoice',
                'Temeljnica': 'manual', 'Prijenos artikala': 'manual',
                'Početno stanje': 'opening', 'Isplatnica': 'manual',
                'Knjiženje plaće': 'payroll', 'Kalo i lom': 'manual',
            }
            source_type = source_map.get(doc_name, 'manual')
            description = '%s br. %d' % (doc_name, doc_number)

            try:
                with transaction.atomic():
                    je = JournalEntry.objects.create(
                        company=company, entry_number=entry_number,
                        date=datum, description=description[:300],
                        source_type=source_type, is_posted=False)
                    for pl in parsed:
                        LedgerLine.objects.create(
                            journal_entry=je, account=pl['account'],
                            side=pl['side'], amount=pl['amount'],
                            description=pl['description'])
                        ll_created += 1
                    je.is_posted = True
                    je.save(update_fields=['is_posted'])
                    je_created += 1
            except (IntegrityError, DatabaseError) as e:
                errors += 1
                if errors <= 5:
                    self.stderr.write('Error on %s: %s' % (entry_number, e))

        self.stdout.write('Created: %d JE, %d LL, %d errors' % (je_created, ll_created, errors))

    def _validate(self, company, excel_entries):
        """Compare LC konto with Excel data per konto."""
        from konto.models import LedgerLine
        from django.db.models import Sum, Q

        # Excel per konto
        xls_d = defaultdict(lambda: Decimal('0'))
        xls_p = defaultdict(lambda: Decimal('0'))
        for e in excel_entries:
            xls_d[e['konto']] += e['duguje']
            xls_p[e['konto']] += e['potrazuje']

        # LC per konto
        lc_data = LedgerLine.objects.filter(
            journal_entry__company=company
        ).values('account__code').annotate(
            d=Sum('amount', filter=Q(side='debit')),
            p=Sum('amount', filter=Q(side='credit')))
        lc_d = {r['account__code']: r['d'] or Decimal('0') for r in lc_data}
        lc_p = {r['account__code']: r['p'] or Decimal('0') for r in lc_data}

        all_k = sorted(set(xls_d.keys()) | set(lc_d.keys()))
        ok = diff = 0
        total_abs_diff = Decimal('0')
        diffs = []

        for k in all_k:
            dd = lc_d.get(k, Decimal('0')) - xls_d.get(k, Decimal('0'))
            dp = lc_p.get(k, Decimal('0')) - xls_p.get(k, Decimal('0'))
            if abs(dd) <= Decimal('0.02') and abs(dp) <= Decimal('0.02'):
                ok += 1
            else:
                diff += 1
                total_abs_diff += abs(dd)
                diffs.append((k, xls_d.get(k, Decimal('0')), lc_d.get(k, Decimal('0')), dd, dp))

        self.stdout.write('\n=== VALIDACIJA ===')
        self.stdout.write('Identičnih konata: %d / %d (%.1f%%)' % (ok, len(all_k), ok/len(all_k)*100))
        self.stdout.write('S razlikom: %d' % diff)

        if diffs:
            self.stdout.write('\nTop razlike:')
            for k, sd, ld, dd, dp in sorted(diffs, key=lambda x: -abs(x[3]))[:10]:
                self.stdout.write('  %-8s XLS_D=%10.2f LC_D=%10.2f diff=%+10.2f' % (k, sd, ld, dd))

        if diff == 0:
            self.stdout.write(self.style.SUCCESS('VALIDACIJA USPJEŠNA — 100%% MATCH!'))
        elif diff <= 3 and total_abs_diff < Decimal('10'):
            self.stdout.write(self.style.SUCCESS('VALIDACIJA OK — razlike < 10 EUR (zaokruženja)'))
        else:
            self.stdout.write(self.style.ERROR('VALIDACIJA NEUSPJEŠNA — %d konata, %.2f EUR razlike' % (diff, total_abs_diff)))
