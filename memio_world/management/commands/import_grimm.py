"""
Import Grimm bajki u ParallelStory model.
Izvor: public domain tekstovi (Brothers Grimm, umrli 1859/1863).

Pokretanje:
  manage.py import_grimm               # sve bajke
  manage.py import_grimm --limit 5     # prvih 5
  manage.py import_grimm --dry-run     # bez pisanja
"""

import logging

from django.core.management.base import BaseCommand
from django.utils.text import slugify

logger = logging.getLogger("play_eu")

# Public domain Grimm bajke — HR + DE + EN
# Izvor naslova: GrimmStories.com (13 jezika, public domain)
GRIMM_STORIES = [
    {
        "title_hr": "Crvenkapica",
        "title_de": "Rotkäppchen",
        "title_en": "Little Red Riding Hood",
        "title_fr": "Le Petit Chaperon rouge",
        "title_it": "Cappuccetto Rosso",
        "country": "Germany",
        "moral": "Ne razgovaraj sa strancima i slušaj roditelje.",
        "age_min": 4,
        "age_max": 8,
        "reading_time": 8,
        "difficulty": 2,
    },
    {
        "title_hr": "Pepeljuga",
        "title_de": "Aschenputtel",
        "title_en": "Cinderella",
        "title_fr": "Cendrillon",
        "title_it": "Cenerentola",
        "country": "Germany",
        "moral": "Dobrota i strpljivost uvijek pobijede.",
        "age_min": 4,
        "age_max": 10,
        "reading_time": 12,
        "difficulty": 2,
    },
    {
        "title_hr": "Snjeguljica",
        "title_de": "Schneewittchen",
        "title_en": "Snow White",
        "title_fr": "Blanche-Neige",
        "title_it": "Biancaneve",
        "country": "Germany",
        "moral": "Ljepota dolazi iznutra, ljubomora uništava.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 15,
        "difficulty": 3,
    },
    {
        "title_hr": "Ivica i Marica",
        "title_de": "Hänsel und Gretel",
        "title_en": "Hansel and Gretel",
        "title_fr": "Hansel et Gretel",
        "title_it": "Hänsel e Gretel",
        "country": "Germany",
        "moral": "Zajedno smo jači — brat i sestra se čuvaju.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 12,
        "difficulty": 3,
    },
    {
        "title_hr": "Trnoružica",
        "title_de": "Dornröschen",
        "title_en": "Sleeping Beauty",
        "title_fr": "La Belle au bois dormant",
        "title_it": "La bella addormentata",
        "country": "Germany",
        "moral": "Ljubav može probuditi i najdublji san.",
        "age_min": 4,
        "age_max": 8,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Vuk i sedam kozlića",
        "title_de": "Der Wolf und die sieben jungen Geißlein",
        "title_en": "The Wolf and the Seven Young Goats",
        "title_fr": "Le loup et les sept chevreaux",
        "title_it": "Il lupo e i sette capretti",
        "country": "Germany",
        "moral": "Ne otvaraj vrata strancima.",
        "age_min": 3,
        "age_max": 7,
        "reading_time": 8,
        "difficulty": 1,
    },
    {
        "title_hr": "Žabji kralj",
        "title_de": "Der Froschkönig",
        "title_en": "The Frog Prince",
        "title_fr": "Le roi grenouille",
        "title_it": "Il principe ranocchio",
        "country": "Germany",
        "moral": "Drži obećanje i ne sudi po vanjštini.",
        "age_min": 4,
        "age_max": 9,
        "reading_time": 8,
        "difficulty": 2,
    },
    {
        "title_hr": "Rapunzel",
        "title_de": "Rapunzel",
        "title_en": "Rapunzel",
        "title_fr": "Raiponce",
        "title_it": "Raperonzolo",
        "country": "Germany",
        "moral": "Sloboda je najvažnija.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Bremenski gradski muzikanti",
        "title_de": "Die Bremer Stadtmusikanten",
        "title_en": "The Town Musicians of Bremen",
        "title_fr": "Les musiciens de Brême",
        "title_it": "I musicanti di Brema",
        "country": "Germany",
        "moral": "Nikad nije kasno za novi početak — zajedno možemo sve.",
        "age_min": 4,
        "age_max": 9,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Rumpelstiltskin",
        "title_de": "Rumpelstilzchen",
        "title_en": "Rumpelstiltskin",
        "title_fr": "Nain Tracassin",
        "title_it": "Tremotino",
        "country": "Germany",
        "moral": "Laž ima kratke noge.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 10,
        "difficulty": 3,
    },
    {
        "title_hr": "Palčić",
        "title_de": "Daumesdick",
        "title_en": "Tom Thumb",
        "title_fr": "Tom Pouce",
        "title_it": "Pollicino",
        "country": "Germany",
        "moral": "I najmanji može biti najhrabriji.",
        "age_min": 4,
        "age_max": 8,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Hrabri krojač",
        "title_de": "Das tapfere Schneiderlein",
        "title_en": "The Brave Little Tailor",
        "title_fr": "Le vaillant petit tailleur",
        "title_it": "Il prode piccolo sarto",
        "country": "Germany",
        "moral": "Pametni pobjeđuju jače od sebe.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 15,
        "difficulty": 3,
    },
    {
        "title_hr": "Zlatna guska",
        "title_de": "Die goldene Gans",
        "title_en": "The Golden Goose",
        "title_fr": "L'oie d'or",
        "title_it": "L'oca d'oro",
        "country": "Germany",
        "moral": "Dobrota se nagrađuje.",
        "age_min": 4,
        "age_max": 9,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Zvjezdani taliri",
        "title_de": "Die Sterntaler",
        "title_en": "The Star Money",
        "title_fr": "Les étoiles d'or",
        "title_it": "Le stelle d'oro",
        "country": "Germany",
        "moral": "Darežljivost donosi čuda.",
        "age_min": 3,
        "age_max": 7,
        "reading_time": 5,
        "difficulty": 1,
    },
    {
        "title_hr": "Djed Mraz (Frau Holle)",
        "title_de": "Frau Holle",
        "title_en": "Mother Holle",
        "title_fr": "Dame Holle",
        "title_it": "Signora Holle",
        "country": "Germany",
        "moral": "Tko radi, taj i zaradi.",
        "age_min": 4,
        "age_max": 9,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Tri preslice",
        "title_de": "Die drei Spinnerinnen",
        "title_en": "The Three Spinners",
        "title_fr": "Les trois fileuses",
        "title_it": "Le tre filatrici",
        "country": "Germany",
        "moral": "Prijatelji pomažu u nevolji.",
        "age_min": 5,
        "age_max": 10,
        "reading_time": 8,
        "difficulty": 2,
    },
    {
        "title_hr": "Kralj Drozdobrad",
        "title_de": "König Drosselbart",
        "title_en": "King Thrushbeard",
        "title_fr": "Le roi Barbe d'Ours",
        "title_it": "Re Bazza di Tordo",
        "country": "Germany",
        "moral": "Poniznost je vrlina — oholost je slabost.",
        "age_min": 6,
        "age_max": 12,
        "reading_time": 12,
        "difficulty": 3,
    },
    {
        "title_hr": "Šest labudova",
        "title_de": "Die sechs Schwäne",
        "title_en": "The Six Swans",
        "title_fr": "Les six cygnes",
        "title_it": "I sei cigni",
        "country": "Germany",
        "moral": "Ljubav sestre je najjača čarolija.",
        "age_min": 6,
        "age_max": 12,
        "reading_time": 15,
        "difficulty": 3,
    },
    {
        "title_hr": "Čizmić mačak",
        "title_de": "Der gestiefelte Kater",
        "title_en": "Puss in Boots",
        "title_fr": "Le Chat botté",
        "title_it": "Il gatto con gli stivali",
        "country": "Germany/France",
        "moral": "Lukavost i vjerni prijatelj mogu promijeniti sudbinu.",
        "age_min": 4,
        "age_max": 10,
        "reading_time": 10,
        "difficulty": 2,
    },
    {
        "title_hr": "Ružno pače",
        "title_de": "Das hässliche Entlein",
        "title_en": "The Ugly Duckling",
        "title_fr": "Le vilain petit canard",
        "title_it": "Il brutto anatroccolo",
        "country": "Denmark",
        "moral": "Nikad ne odustaj — ono što misliš da je slabost može biti tvoja snaga.",
        "age_min": 3,
        "age_max": 8,
        "reading_time": 10,
        "difficulty": 1,
    },
]


class Command(BaseCommand):
    help = "Import Grimm/Andersen bajki u ParallelStory model"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from memio_world.play_eu_models import ParallelStory

        dry_run = options["dry_run"]
        limit = options["limit"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Import Grimm START — {min(limit, len(GRIMM_STORIES))} bajki" + (" [DRY RUN]" if dry_run else "")
            )
        )

        created = 0
        skipped = 0

        for story_data in GRIMM_STORIES[:limit]:
            slug = slugify(story_data["title_en"])

            if ParallelStory.objects.using("memio_world").filter(slug=slug).exists():
                skipped += 1
                self.stdout.write(f"  [SKIP] {story_data['title_hr']} (već postoji)")
                continue

            if dry_run:
                self.stdout.write(f"  [NEW] {story_data['title_hr']} / {story_data['title_de']}")
                created += 1
                continue

            # Determine source
            source = "grimm"
            if story_data["country"] == "Denmark":
                source = "andersen"

            ParallelStory.objects.using("memio_world").create(
                slug=slug,
                title_hr=story_data["title_hr"],
                title_de=story_data["title_de"],
                title_en=story_data["title_en"],
                title_fr=story_data.get("title_fr", ""),
                title_it=story_data.get("title_it", ""),
                story_type="fairy_tale",
                source=source,
                license="public_domain",
                attribution=f"Brothers Grimm / H.C. Andersen — public domain (autor umro prije 1900)",
                age_min=story_data.get("age_min", 4),
                age_max=story_data.get("age_max", 10),
                reading_time_minutes=story_data.get("reading_time", 10),
                difficulty_level=story_data.get("difficulty", 2),
                country_of_origin=story_data.get("country", "Germany"),
                moral_lesson=story_data.get("moral", ""),
                # Tekstovi za sada prazni — popunit ćemo u Fazi C.2 sa scraperom
                text_hr="",
                text_de="",
                text_en="",
                is_published=False,  # Tek kad imaju tekst
            )
            created += 1
            self.stdout.write(f"  [SAVED] {story_data['title_hr']} ({story_data['title_de']})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"IMPORT DONE: {created} novih, {skipped} preskočenih"))
