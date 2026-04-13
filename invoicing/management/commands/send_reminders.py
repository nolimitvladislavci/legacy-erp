"""Management command: mark overdue invoices, create reminder tasks."""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from invoicing.models import Invoice
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Mark overdue invoices and create reminder notes'

    def handle(self, *args, **options):
        today = timezone.now().date()
        # 15+ days unpaid → OVERDUE
        overdue_threshold = today - datetime.timedelta(days=15)
        n1 = Invoice.objects.filter(
            status__in=['SENT', 'UNPAID'],
            date_due__lt=overdue_threshold
        ).update(status='OVERDUE')
        self.stdout.write(f'Marked {n1} invoices as OVERDUE (15+ days)')

        # 30+ days overdue → log warning
        warn_threshold = today - datetime.timedelta(days=30)
        n2 = Invoice.objects.filter(
            status='OVERDUE',
            date_due__lt=warn_threshold
        )
        for inv in n2:
            self.stdout.write(
                self.style.WARNING(
                    f'URGENT: {inv.number} – {inv.client_name} – '
                    f'{inv.total} {inv.currency} – due {inv.date_due}'
                )
            )
        self.stdout.write(self.style.SUCCESS(
            f'Done. {n1} overdue, {n2.count()} need urgent follow-up.'
        ))
