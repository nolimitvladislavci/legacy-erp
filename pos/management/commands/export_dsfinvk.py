"""
DSFinV-K Export Management Command.

Usage:
    python manage.py export_dsfinvk <company_uuid> --from 2026-01-01 --to 2026-03-31
    python manage.py export_dsfinvk <company_uuid>  (default: letzter Monat)
"""
from datetime import date, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Exportiert DSFinV-K konformen ZIP fuer das Finanzamt.'

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=str, help='Company UUID oder OIB')
        parser.add_argument('--from', dest='date_from', type=str, default='', help='Start (YYYY-MM-DD)')
        parser.add_argument('--to', dest='date_to', type=str, default='', help='Ende (YYYY-MM-DD)')
        parser.add_argument('--output', type=str, default='', help='Output Pfad (default: dsfinvk_DATE.zip)')

    def handle(self, *args, **options):
        from companies.models import Company
        from pos.dsfinvk_export import generate_dsfinvk_export

        # Find company
        cid = options['company_id']
        try:
            company = Company.objects.get(pk=cid)
        except ObjectDoesNotExist:
            try:
                company = Company.objects.get(oib=cid)
            except Company.DoesNotExist:
                self.stderr.write('Firma nicht gefunden: %s' % cid)
                return

        # Date range
        if options['date_from']:
            date_from = date.fromisoformat(options['date_from'])
        else:
            today = date.today()
            date_from = today.replace(day=1) - timedelta(days=1)
            date_from = date_from.replace(day=1)

        if options['date_to']:
            date_to = date.fromisoformat(options['date_to'])
        else:
            date_to = date.today()

        self.stdout.write('Firma: %s (%s)' % (company.name, company.oib))
        self.stdout.write('Zeitraum: %s bis %s' % (date_from, date_to))

        zip_bytes = generate_dsfinvk_export(company, date_from, date_to)

        output_path = options['output'] or 'dsfinvk_%s_%s_%s.zip' % (
            company.oib, date_from.isoformat(), date_to.isoformat()
        )
        with open(output_path, 'wb') as f:
            f.write(zip_bytes)

        self.stdout.write(self.style.SUCCESS(
            'DSFinV-K Export: %s (%d bytes)' % (output_path, len(zip_bytes))
        ))
