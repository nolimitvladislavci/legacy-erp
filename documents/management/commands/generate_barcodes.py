import random
import string
from datetime import date

from django.core.management.base import BaseCommand

from documents.models import ArhivaEntry


class Command(BaseCommand):
    help = "Generira barcodes za sve ArhivaEntry bez barcodea"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=100, help="Batch size (default: 100)")

    def handle(self, *args, **options):
        batch_size = options["batch"]
        entries = ArhivaEntry.objects.unscoped().filter(barcode="")
        total = entries.count()
        self.stdout.write(f"Generiram barcode za {total} zapisa (batch={batch_size})...")
        updated = 0
        for e in entries.iterator(chunk_size=batch_size):
            prefix = e.company.name[:4].upper().replace(" ", "") if e.company_id else "LCNK"
            rand = "".join(random.choices(string.digits, k=6))
            dt = e.archived_at.strftime("%Y%m%d") if e.archived_at else date.today().strftime("%Y%m%d")
            e.barcode = f"LC-{dt}-{prefix}-{rand}"
            ArhivaEntry.objects.unscoped().filter(pk=e.pk).update(barcode=e.barcode)
            updated += 1
            if updated % 500 == 0:
                self.stdout.write(f"  {updated}/{total}...")
        self.stdout.write(self.style.SUCCESS(f"Generirano: {updated} barcodes"))
