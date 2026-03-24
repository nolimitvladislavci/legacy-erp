"""
konto/management/commands/seed_tax_periods.py
Seed TaxPeriod records by calling calculate_vat_period for all companies × all months.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


def _to_date(val):
    """Convert datetime or date to date."""
    if val is None:
        return None
    if hasattr(val, 'date'):
        return val.date()
    return val


class Command(BaseCommand):
    help = 'Seed TaxPeriod records for all companies with bookkeeping activity'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Process all companies')
        parser.add_argument('--company-id', type=int, help='Process single company')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be created')

    def handle(self, *args, **options):
        from companies.models import Company
        from konto.models import JournalEntry
        from invoicing.models import Invoice
        from konto.services import calculate_vat_period
        from django.db.models import Min
        import datetime

        if options['company_id']:
            companies = Company.objects.filter(id=options['company_id'])
        elif options['all']:
            companies = Company.objects.exclude(pdv_status='none')
        else:
            self.stderr.write('Specify --all or --company-id')
            return

        dry_run = options['dry_run']
        now = timezone.now().date()
        total_created = 0

        for c in companies:
            # Find earliest activity date — normalize to date
            earliest_je = _to_date(
                JournalEntry.objects.filter(company=c).aggregate(m=Min('date'))['m']
            )
            earliest_inv = _to_date(
                Invoice.objects.filter(company=c).exclude(
                    status__in=['DRAFT', 'CANCELLED']
                ).aggregate(m=Min('date_issued'))['m']
            )

            dates = [d for d in [earliest_je, earliest_inv] if d]
            if not dates:
                self.stdout.write(f'  {c.name} -- nema aktivnosti, preskacemo')
                continue

            start = min(dates)
            start_month = datetime.date(start.year, start.month, 1)
            end_month = datetime.date(now.year, now.month, 1)

            # Iterate months
            current = start_month
            periods_created = 0
            while current <= end_month:
                if dry_run:
                    periods_created += 1
                else:
                    try:
                        calculate_vat_period(c, 'monthly', current.year, current.month)
                        periods_created += 1
                    except Exception as e:
                        self.stderr.write(f'  GRESKA {c.name} {current.year}/{current.month:02d}: {e}')

                # Next month
                if current.month == 12:
                    current = datetime.date(current.year + 1, 1, 1)
                else:
                    current = datetime.date(current.year, current.month + 1, 1)

            total_created += periods_created
            self.stdout.write(
                f'{"🔍" if dry_run else "✅"} {c.name}: {periods_created} TaxPeriod-a '
                f'({start_month.strftime("%m/%Y")} - {end_month.strftime("%m/%Y")})'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nGotovo: {total_created} TaxPeriod-a ukupno'
            + (' (DRY RUN)' if dry_run else '')
        ))
