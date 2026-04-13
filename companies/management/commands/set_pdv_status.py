"""
companies/management/commands/set_pdv_status.py
PDV status auto-classification for all companies.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Auto-classify pdv_status for companies based on invoices and business_type'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Process all companies')
        parser.add_argument('--company-id', type=int, help='Process single company')
        parser.add_argument('--dry-run', action='store_true', help='Show changes without saving')

    def handle(self, *args, **options):
        from django.utils import timezone

        from companies.models import Company
        from invoicing.models import Invoice
        from konto.models import JournalEntry

        if options['company_id']:
            companies = Company.objects.filter(id=options['company_id'])
        elif options['all']:
            companies = Company.objects.all()
        else:
            self.stderr.write('Specify --all or --company-id')
            return

        dry_run = options['dry_run']
        updated = 0
        current_year = timezone.now().year

        for c in companies:
            old_status = c.pdv_status
            # Count outgoing invoices
            ira_count = Invoice.objects.filter(
                company=c,
                doctype__in=['R', 'IRA', 'A', 'GS', 'FA']
            ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO']).count()

            new_status = 'none'
            reason = ''

            if c.business_type in ('doo', 'jdoo', 'dd', 'gmbh'):
                if ira_count > 0:
                    new_status = 'obveznik'
                    reason = f'{ira_count} IRA, {c.business_type}'
                else:
                    je_count = JournalEntry.objects.filter(company=c).count()
                    if je_count > 0:
                        new_status = 'obveznik'
                        reason = f'{je_count} knjizenja, {c.business_type} (pretpostavka)'
                    else:
                        new_status = 'none'
                        reason = 'nema aktivnosti'

            elif c.business_type == 'obrt':
                revenue = Invoice.objects.filter(
                    company=c,
                    doctype__in=['R', 'IRA', 'A', 'GS'],
                    date_issued__year=current_year,
                ).exclude(
                    status__in=['DRAFT', 'CANCELLED', 'STORNO']
                ).aggregate(t=Sum('subtotal'))['t'] or Decimal('0')

                if revenue > Decimal('39816'):
                    new_status = 'obveznik'
                    reason = f'obrt, promet {revenue:.2f} EUR > 39.816'
                else:
                    new_status = 'pausalic'
                    reason = f'obrt, promet {revenue:.2f} EUR < 39.816'

            elif c.business_type == 'udruga':
                if ira_count > 0:
                    new_status = 'obveznik'
                    reason = f'udruga s {ira_count} izdanih racuna'
                else:
                    new_status = 'none'
                    reason = 'udruga bez gospodarske djelatnosti'

            else:
                if ira_count > 0:
                    new_status = 'obveznik'
                    reason = f'{ira_count} IRA, {c.business_type}'

            if new_status != old_status or (new_status == 'obveznik' and not c.is_vat_registered):
                icon = '🔍' if dry_run else '✅'
                self.stdout.write(f'{icon} {c.name} -> {new_status} (razlog: {reason})')

                if not dry_run:
                    c.pdv_status = new_status
                    if new_status in ('obveznik', 'pausalic'):
                        c.is_vat_registered = True
                        if c.country == 'HR' and c.oib and (not c.vat_id or c.vat_id == ''):
                            c.vat_id = f'HR{c.oib}'
                    c.save(update_fields=['pdv_status', 'is_vat_registered', 'vat_id'])
                    updated += 1
            else:
                self.stdout.write(f'  {c.name} -- bez promjene ({old_status})')

        self.stdout.write(self.style.SUCCESS(
            f'\nGotovo: {updated} firmi azurirano' + (' (DRY RUN)' if dry_run else '')
        ))
