"""Management command: backfill_arhiva_pdfs — generira PDF za sve invoice ArhivaEntry bez PDF-a."""

import gc
import logging
import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from documents.models import ArhivaEntry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill PDF za ArhivaEntry (invoice_out) koje nemaju PDF"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=50, help="Batch size (default: 50)")
        parser.add_argument("--limit", type=int, default=0, help="Max entries to process (0=all)")
        parser.add_argument("--dry-run", action="store_true", help="Samo provjeri, ne generiraj")

    def handle(self, *args, **options):
        batch_size = options["batch"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        qs = (
            ArhivaEntry.objects.filter(
                has_pdf=False,
                source_type="invoice_out",
                source_id__isnull=False,
            )
            .exclude(source_id="")
            .select_related("company")
        )

        total = qs.count()
        if limit:
            total = min(total, limit)

        self.stdout.write(f"PDF backfill: {total} entryja za obradu (batch={batch_size})")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nista nece biti generirano"))
            return

        from invoicing.models import Invoice
        from invoicing.services.pdf_service import generate_invoice_pdf

        ok = err = skip = 0
        processed = 0

        for entry in qs.iterator(chunk_size=batch_size):
            if limit and processed >= limit:
                break

            try:
                inv = Invoice.objects.get(pk=int(entry.source_id))
                result = generate_invoice_pdf(inv)
                pdf_bytes = result[0] if isinstance(result, tuple) else result

                if pdf_bytes and len(pdf_bytes) > 100:
                    rel_path = f"arhiva/{entry.company_id}/{entry.archive_number}.pdf"
                    full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "wb") as f:
                        f.write(pdf_bytes)
                    entry.file_path = rel_path
                    entry.has_pdf = True
                    entry.save(update_fields=["file_path", "has_pdf"])
                    ok += 1
                else:
                    skip += 1
            except Invoice.DoesNotExist:
                skip += 1
            except ObjectDoesNotExist as e:
                err += 1
                if err <= 5:
                    self.stderr.write(f"  Error #{entry.pk}: {e}")

            processed += 1

            if processed % batch_size == 0:
                gc.collect()
                self.stdout.write(f"  {processed}/{total} — OK:{ok} skip:{skip} err:{err}")

        self.stdout.write(self.style.SUCCESS(f"BACKFILL COMPLETE: {ok} OK, {skip} skip, {err} err (od {processed})"))
