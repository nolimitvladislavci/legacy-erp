"""
Bulk aktivacija artikala za kiosk/webshop prikaz.
Aktivira sve food/dessert/drink artikle za zadanu firmu.

Korištenje:
  python manage.py activate_kiosk_items --company "UVIJEK FRIŠKO"
  python manage.py activate_kiosk_items --company-id <uuid> --categories food,dessert,drink
  python manage.py activate_kiosk_items --all  # sve firme
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Aktiviraj artikle za kiosk/webshop prikaz (webshop_visible=True)"

    def add_arguments(self, parser):
        parser.add_argument("--company", type=str, help="Naziv firme (parcijalni match)")
        parser.add_argument("--company-id", type=str, help="Company UUID")
        parser.add_argument(
            "--categories",
            type=str,
            default="food,dessert,drink",
            help="Kategorije za aktivaciju (default: food,dessert,drink)",
        )
        parser.add_argument("--all", action="store_true", help="Sve firme")
        parser.add_argument("--dry-run", action="store_true", help="Samo prikaži, ne mijenjaj")

    def handle(self, *args, **options):
        from companies.models import Company
        from inventory.models import InventoryItem

        categories = [c.strip() for c in options["categories"].split(",")]

        if options["company_id"]:
            companies = Company.objects.filter(pk=options["company_id"])
        elif options["company"]:
            companies = Company.objects.filter(name__icontains=options["company"])
        elif options["all"]:
            companies = Company.objects.all()
        else:
            self.stderr.write("Navedi --company, --company-id ili --all")
            return

        for company in companies:
            qs = InventoryItem.objects.filter(
                company=company,
                is_active=True,
                category__in=categories,
                webshop_visible=False,
            )
            count = qs.count()
            if options["dry_run"]:
                self.stdout.write(f"  {company.name}: {count} artikala bi bilo aktivirano")
            else:
                updated = qs.update(webshop_visible=True)
                self.stdout.write(self.style.SUCCESS(f"  {company.name}: {updated} artikala aktivirano"))
