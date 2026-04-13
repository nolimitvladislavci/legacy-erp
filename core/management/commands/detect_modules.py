"""
Management command: python manage.py detect_modules

Scans all companies and auto-activates specialized modules based on:
  1. business_type (udruga, opg, zadruga, ustanova)
  2. NKD code match
  3. Company name keyword match

Usage:
  python manage.py detect_modules              # Dry run
  python manage.py detect_modules --apply      # Actually save
  python manage.py detect_modules --company-id UUID  # Single company
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Auto-detect and activate specialized modules for companies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually save changes (default is dry-run)",
        )
        parser.add_argument(
            "--company-id",
            type=str,
            default=None,
            help="Only process a specific company by UUID",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset existing modules before detecting (replace, not append)",
        )

    def handle(self, *args, **options):
        from companies.models import Company, CompanyModuleConfig
        from core.module_registry import MODULE_REGISTRY, auto_detect_modules

        apply = options["apply"]
        company_id = options.get("company_id")
        reset = options["reset"]

        if apply:
            self.stdout.write(self.style.WARNING("MODE: APPLY (changes will be saved)"))
        else:
            self.stdout.write(self.style.NOTICE("MODE: DRY RUN (no changes)"))

        # Get companies
        qs = Company.objects.all().select_related("nkd_code")
        if company_id:
            qs = qs.filter(pk=company_id)

        total = qs.count()
        activated_count = 0
        companies_affected = 0

        self.stdout.write(f"\nScanning {total} companies...\n")
        self.stdout.write("-" * 70)

        for company in qs.iterator():
            detected = auto_detect_modules(company)
            if not detected:
                continue

            # Get existing config
            config = CompanyModuleConfig.objects.filter(company=company).first()
            existing = set(config.enabled_modules) if config else set()

            # Filter to only specialized modules (from our registry)
            existing_spec = existing & set(MODULE_REGISTRY.keys())

            if reset:
                new_modules = set(detected)
            else:
                new_modules = existing_spec | set(detected)

            newly_added = new_modules - existing_spec

            if not newly_added and not reset:
                continue

            companies_affected += 1
            nkd_str = ""
            if company.nkd_code:
                nkd_str = f" [NKD: {company.nkd_code.code}]"

            self.stdout.write(f"\n  {company.name} ({company.business_type}){nkd_str}")

            if newly_added:
                for mod_key in sorted(newly_added):
                    mod_info = MODULE_REGISTRY.get(mod_key, {})
                    self.stdout.write(self.style.SUCCESS(f"    + {mod_key}: {mod_info.get('name', '?')}"))
                    activated_count += 1

            if existing_spec and not reset:
                for mod_key in sorted(existing_spec):
                    self.stdout.write(self.style.HTTP_INFO(f"    = {mod_key} (already active)"))

            if apply:
                with transaction.atomic():
                    if not config:
                        config = CompanyModuleConfig.objects.create(company=company, enabled_modules=[])

                    # Merge: keep non-spec modules from existing, add detected spec modules
                    non_spec = [m for m in config.enabled_modules if m not in MODULE_REGISTRY]
                    if reset:
                        config.enabled_modules = non_spec + sorted(new_modules)
                    else:
                        config.enabled_modules = non_spec + sorted(existing_spec | set(detected))
                    config.save(update_fields=["enabled_modules", "updated_at"])

        self.stdout.write("\n" + "-" * 70)
        self.stdout.write(f"\nDone! {companies_affected} companies affected, {activated_count} new module activations.")

        if not apply and activated_count > 0:
            self.stdout.write(self.style.WARNING("\nThis was a DRY RUN. Run with --apply to save changes."))
