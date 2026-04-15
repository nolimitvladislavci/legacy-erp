"""
Europeana Sync — povlači items iz Europeana API u EuropeanaItem model.

Pokretanje:
  manage.py europeana_sync                          # sve kategorije, 20 po kategoriji
  manage.py europeana_sync --category alphabet      # samo slovarice
  manage.py europeana_sync --category bestiary --limit 50
  manage.py europeana_sync --country HR             # samo hrvatski sadržaj
  manage.py europeana_sync --dry-run                # bez pisanja u bazu
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("europeana")

DEFAULT_CATEGORIES = [
    "alphabet",
    "counting",
    "story",
    "song",
    "bestiary",
    "game",
    "illustration",
    "manuscript",
]


class Command(BaseCommand):
    help = "Sync Europeana items u EuropeanaItem model"

    def add_arguments(self, parser):
        parser.add_argument("--category", type=str, help="Samo ova kategorija")
        parser.add_argument("--limit", type=int, default=20, help="Max items po kategoriji")
        parser.add_argument("--country", type=str, default="", help="ISO zemlja filter")
        parser.add_argument("--dry-run", action="store_true", help="Bez pisanja u bazu")
        parser.add_argument("--curate", action="store_true", help="Oznaci sve kao is_curated=True")

    def handle(self, *args, **options):
        from memio_world.europeana_client import EuropeanaClient
        from memio_world.play_eu_models import EuropeanaItem

        client = EuropeanaClient()
        dry_run = options["dry_run"]
        limit = options["limit"]
        country = options["country"]
        curate = options["curate"]
        target_cat = options.get("category")

        categories = [target_cat] if target_cat else DEFAULT_CATEGORIES

        self.stdout.write(
            self.style.SUCCESS(
                f"Europeana Sync START — {len(categories)} kategorija, limit={limit}"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        total_new = 0
        total_skip = 0
        total_error = 0

        for cat in categories:
            self.stdout.write(f"\n  [{cat.upper()}]")
            items = client.search_children_content(cat, limit=limit, country=country)

            if not items:
                self.stdout.write(self.style.WARNING(f"    0 rezultata"))
                continue

            for item_data in items:
                eid = item_data["europeana_id"]

                # Dedup
                if EuropeanaItem.objects.using("memio_world").filter(europeana_id=eid).exists():
                    total_skip += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"    [NEW] {item_data['title'][:60]} "
                        f"({item_data['provider'][:30]}, {item_data['rights'][:40]})"
                    )
                    total_new += 1
                    continue

                try:
                    if curate:
                        item_data["is_curated"] = True
                    EuropeanaItem.objects.using("memio_world").create(**item_data)
                    total_new += 1
                    self.stdout.write(f"    [SAVED] {item_data['title'][:60]}")
                except Exception as e:
                    total_error += 1
                    logger.error("Europeana sync error for %s: %s", eid, e)
                    self.stdout.write(self.style.ERROR(f"    [ERROR] {eid}: {e}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"SYNC DONE: {total_new} novih, {total_skip} preskočenih, {total_error} grešaka")
        )
