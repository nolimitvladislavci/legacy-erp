"""
Management command: retroactively archive all existing photos into ArhivaEntry.

Usage:
    python manage.py archive_existing_photos
    python manage.py archive_existing_photos --app stolarija
    python manage.py archive_existing_photos --dry-run
"""

from django.core.management.base import BaseCommand


# Registry of all ImageField locations across the codebase
PHOTO_REGISTRY = [
    # (app_label, model_name, field_name, source_type, tags)
    # Stolarija
    ("stolarija", "Measurement", "photo_before", "before_photo", ["mjerenje", "teren"]),
    ("stolarija", "InstallationOrder", "photo_before", "before_photo", ["ugradnja", "prije"]),
    ("stolarija", "InstallationOrder", "photo_after", "after_photo", ["ugradnja", "poslije"]),
    ("stolarija", "InstallationChecklist", "photo_result", "after_photo", ["ugradnja", "rezultat"]),
    ("stolarija", "WindowWarranty", "handover_photo", "site_photo", ["primopredaja"]),
    ("stolarija", "ServiceVisit", "photo", "site_photo", ["servis"]),
    ("stolarija", "ServiceMessage", "attachment", "complaint_photo", ["poruka"]),
    # Delivery
    ("delivery", "DeliveryStop", "delivery_photo", "delivery_proof", ["dostava"]),
    ("delivery", "ConsolidatedDelivery", "delivery_photo", "delivery_proof", ["dostava"]),
    ("delivery", "ConsolidatedDelivery", "recipient_signature", "delivery_proof", ["potpis"]),
    # Worktime
    ("worktime", "ProjectPhoto", "image", "site_photo", ["gradiliste"]),
    # Production
    ("production", "QualityCheck", "photo", "qc_photo", ["kvaliteta"]),
    # Assessment
    ("assessment", "AssessmentPhoto", "photo", "site_photo", ["inspekcija"]),
    # Livestock
    ("livestock", "Livestock", "photo", "animal_photo", ["zivotinja"]),
    ("livestock", "HealthRecord", "photo", "animal_photo", ["zdravlje"]),
    # Invoicing
    ("invoicing", "Invoice", "photo", "receipt_scan", ["racun"]),
    # Projects
    ("projects", "ProjectPhoto", "image", "site_photo", ["projekt"]),
    # Marketplace
    ("marketplace", "OrderComplaint", "photo", "complaint_photo", ["reklamacija"]),
    # Accounts
    ("accounts", "UserProfile", "profile_image", "profile_photo", ["profil"]),
    # Companies
    ("companies", "Company", "logo", "profile_photo", ["logo"]),
]


class Command(BaseCommand):
    help = "Archive all existing photos from domain apps into ArhivaEntry"

    def add_arguments(self, parser):
        parser.add_argument("--app", type=str, default="", help="Only process specific app (e.g. stolarija)")
        parser.add_argument("--dry-run", action="store_true", help="Count photos without archiving")

    def handle(self, *args, **options):
        from documents.photo_registry import retroactive_archive

        app_filter = options["app"]
        dry_run = options["dry_run"]
        total = 0
        errors = 0

        for app_label, model_name, field_name, source_type, tags in PHOTO_REGISTRY:
            if app_filter and app_label != app_filter:
                continue

            try:
                from django.apps import apps

                Model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stdout.write(self.style.WARNING(f"  SKIP: {app_label}.{model_name} — model not found"))
                continue

            # Count existing photos
            count = Model.objects.exclude(**{f"{field_name}": ""}).exclude(**{f"{field_name}__isnull": True}).count()

            if count == 0:
                self.stdout.write(f"  {app_label}.{model_name}.{field_name}: 0 photos")
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f"  {app_label}.{model_name}.{field_name}: {count} photos (dry-run)")
                )
                total += count
                continue

            try:
                archived = retroactive_archive(
                    app_label,
                    model_name,
                    field_name,
                    source_type=source_type,
                    content_category="photo",
                    tags=tags,
                )
                total += archived
                self.stdout.write(
                    self.style.SUCCESS(f"  {app_label}.{model_name}.{field_name}: {archived}/{count} archived")
                )
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f"  {app_label}.{model_name}.{field_name}: ERROR — {e}"))

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"DRY RUN: {total} photos found across all apps"))
        else:
            self.stdout.write(self.style.SUCCESS(f"DONE: {total} photos archived, {errors} errors"))
