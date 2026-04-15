"""
split_story_pages — Dijeli priče u stranice slikovnice.

Za svaku published ParallelStory:
  1. Kreira naslovnicu (page 0, cover, full_bleed)
  2. Dijeli tekst u stranice (1 paragraf = 1 stranica)
  3. Kreira zadnju stranicu (pouka + CTA)
  4. Generira scene_description za AI ilustratora

Usage:
  manage.py split_story_pages                  # sve published priče
  manage.py split_story_pages --slug=rapunzel  # jedna priča
  manage.py split_story_pages --force          # prebriši postojeće
"""

from django.core.management.base import BaseCommand

from memio_world.book_models import StoryBookStyle, StoryPage
from memio_world.play_eu_models import ParallelStory

DB = "memio_world"

# ═══════════════════════════════════════════════════════════════
# SCENE DESCRIPTIONS — rucno za prvih 10 Grimm priča
# AI/agent ce generirati ostatak, ali ove moraju biti tocne
# ═══════════════════════════════════════════════════════════════

SCENE_BANK = {
    "rapunzel": {
        "cover": (
            "A tall stone tower rising above a misty enchanted forest, "
            "a girl with extremely long golden braids visible in the high window, "
            "wildflowers and ivy growing at the tower base, warm morning golden light, "
            "birds circling the tower"
        ),
        "scenes": [
            (
                "An evil old sorceress in a dark flowing cloak carrying a baby away from "
                "a weeping young couple standing at their cottage door, moonlit night, "
                "the couple reaching out helplessly"
            ),
            (
                "A beautiful young woman with impossibly long golden braids sitting by "
                "a round tower window, looking wistfully down at the vast forest below, "
                "songbirds perched on the windowsill, golden afternoon light"
            ),
            (
                "A handsome young prince on a white horse in a sun-dappled forest, "
                "looking up in wonder toward a tall tower, hearing beautiful singing, "
                "magical golden light streaming from the tower window"
            ),
            (
                "The golden-haired girl leaning from the tower window letting down her "
                "incredibly long braids like a rope, the prince climbing up, "
                "starlit night sky, fireflies glowing around them"
            ),
            (
                "The furious sorceress with wild eyes holding large scissors, cutting "
                "the golden braids, the girl crying in despair, cut hair falling like "
                "golden rain, dramatic stormy sky"
            ),
            (
                "A blind prince wandering alone through a barren desert landscape, "
                "tears streaming down his face, searching desperately, "
                "small wildflowers sprouting where his tears fall on dry ground"
            ),
            (
                "The prince and the golden-haired girl reunited in a meadow full of flowers, "
                "her healing tears falling on his closed eyes, golden radiant light "
                "surrounding them, a distant castle visible on the horizon, joy and love"
            ),
        ],
    },
    "cinderella": {
        "cover": (
            "A beautiful glass slipper sitting on a velvet cushion on palace steps, "
            "sparkling in moonlight, scattered rose petals, a grand palace ballroom "
            "glowing warmly in the background"
        ),
        "scenes": [
            (
                "A kind young girl in tattered clothes sweeping ashes by a large fireplace, "
                "her face gentle despite her worn dress, a cruel stepmother and two "
                "stepsisters in fine dresses laughing behind her"
            ),
            (
                "A magical fairy godmother appearing in a burst of sparkling light, "
                "waving a wand over a pumpkin in a garden, mice scurrying around, "
                "magical transformation beginning with golden sparkles"
            ),
            (
                "The girl transformed into a stunning princess in a shimmering ball gown, "
                "standing before a magnificent golden carriage pulled by white horses, "
                "the fairy godmother smiling, magical starlight"
            ),
            (
                "A grand palace ballroom with crystal chandeliers, the prince and the "
                "beautiful girl dancing alone in the center while everyone watches in awe, "
                "warm candlelight, swirling gown"
            ),
            (
                "The girl running down wide palace stairs at midnight, the clock striking "
                "twelve, one glass slipper left behind on the steps, her dress beginning "
                "to transform back, the prince reaching out from the top of the stairs"
            ),
            (
                "The prince kneeling before the girl in her simple dress, gently placing "
                "the glass slipper on her foot, a perfect fit, the stepsisters watching "
                "in shock, warm golden light of recognition and love"
            ),
        ],
    },
    "snow-white": {
        "cover": (
            "A beautiful girl with skin white as snow, lips red as blood, and hair "
            "black as ebony, standing in front of a tiny cottage in an enchanted forest, "
            "seven tiny doors visible, forest animals gathered around her"
        ),
        "scenes": [
            (
                "A vain evil queen standing before an ornate magic mirror in a dark "
                "castle chamber, the mirror glowing with an eerie face, the queen "
                "asking who is the fairest, jealousy in her eyes"
            ),
            (
                "A frightened young girl running through a dark scary forest at night, "
                "thorny branches reaching out, eyes of forest animals watching from "
                "shadows, but also friendly deer guiding her path"
            ),
            (
                "A charming tiny cottage with a red door, seven small chairs around "
                "a tiny table with seven tiny bowls, the girl peering inside with "
                "wonder, warm cozy firelight glowing from within"
            ),
            (
                "Seven friendly dwarfs with colorful hats and white beards standing "
                "in a line welcoming the girl at their cottage door, each with a "
                "different expression, pickaxes and lanterns, sunset behind mountains"
            ),
            (
                "The evil queen disguised as an old woman offering a beautiful "
                "red apple to the girl at the cottage window, the apple glistening "
                "ominously, a raven watching from a nearby tree"
            ),
            (
                "The girl lying peacefully in a glass coffin surrounded by flowers, "
                "seven weeping dwarfs standing guard, forest animals mourning, "
                "soft ethereal light, snow falling gently"
            ),
            (
                "A handsome prince on a white horse arriving at the glass coffin, "
                "leaning down to kiss the girl, magical golden light beginning to "
                "radiate, the dwarfs looking up with hope"
            ),
            (
                "The girl awakening from the coffin with a gentle smile, the prince "
                "helping her up, all seven dwarfs celebrating and dancing, flowers "
                "blooming everywhere, rainbow in the sky, happily ever after"
            ),
        ],
    },
    "sleeping-beauty": {
        "cover": (
            "A beautiful princess asleep on a canopy bed surrounded by climbing roses "
            "and thorny vines, a spinning wheel nearby, golden magical dust floating "
            "in the air, soft dreamy light"
        ),
        "scenes": [
            (
                "A grand christening ceremony in a palace, king and queen presenting "
                "a baby princess, twelve good fairies in colorful gowns bestowing gifts, "
                "golden light and celebration"
            ),
            (
                "A dark fairy in a black cloak appearing at the christening in a burst "
                "of green fire, pointing a bony finger at the baby, the court gasping "
                "in horror, the curse being spoken"
            ),
            (
                "A teenage princess in a tower room discovering an old spinning wheel, "
                "reaching out to touch the spindle with curiosity, golden dust swirling, "
                "an old woman sitting at the wheel smiling"
            ),
            (
                "The princess falling into a deep sleep on a bed of roses, the entire "
                "castle falling asleep around her — servants, guards, dogs, cats, even "
                "fire in the fireplace frozen, thick thorny roses growing over everything"
            ),
            (
                "A brave young prince on horseback arriving at a castle completely "
                "covered in thorny rose vines, cutting through the thorns with a sword, "
                "determined expression, sunlight breaking through clouds"
            ),
            (
                "The prince finding the sleeping princess and gently kissing her, "
                "roses blooming, thorns retreating, everyone in the castle beginning "
                "to wake up, golden magical light spreading through every room"
            ),
            (
                "The princess and prince walking together through the awakened castle "
                "garden, everyone celebrating, roses in full bloom, the kingdom alive "
                "again, warm sunset light, happily ever after"
            ),
        ],
    },
    "hansel-and-gretel": {
        "cover": (
            "A magical cottage made entirely of gingerbread, candy, and frosting "
            "in a dark enchanted forest, two children holding hands looking at it "
            "with wide eyes, candy cane fence, gumdrop bushes"
        ),
        "scenes": [
            (
                "A poor woodcutter's family — father, stepmother, and two children — "
                "sitting at a bare wooden table with almost no food, candlelight, "
                "the stepmother whispering to the reluctant father"
            ),
            (
                "Two small children walking hand in hand through a dark misty forest, "
                "dropping white pebbles behind them that glow like tiny moons on the "
                "forest floor, owls watching from branches"
            ),
            (
                "A magical house made of gingerbread and candy standing in a forest "
                "clearing, sugar windows, chocolate door, icing dripping from the roof, "
                "the two children reaching out to taste the walls in delight"
            ),
            (
                "A wicked old witch with a hooked nose and crooked smile welcoming "
                "the children inside, a dark kitchen with a large oven glowing red "
                "in the background, cages visible in the shadows"
            ),
            (
                "The brave girl pushing the wicked witch into the large glowing oven, "
                "the boy escaping from a cage in the background, dramatic firelight, "
                "the witch's hat flying off, a moment of courage"
            ),
            (
                "The two children running joyfully through the forest toward their "
                "father's cottage, carrying bags of jewels and gold from the witch's "
                "house, their father waiting with open arms at the door, morning light"
            ),
        ],
    },
    "little-red-riding-hood": {
        "cover": (
            "A little girl in a bright red hooded cape walking on a winding forest "
            "path carrying a basket, tall dark trees on both sides, wildflowers along "
            "the path, dappled sunlight, a shadowy wolf watching from behind a tree"
        ),
        "scenes": [
            (
                "A mother in a cozy kitchen giving a basket of bread and cake to a "
                "little girl wearing a red hooded cape, warning her to stay on the path, "
                "warm domestic light, flowers in the window"
            ),
            (
                "The little girl in the red cape meeting a large charming wolf on the "
                "forest path, the wolf standing upright with a sly smile, the girl "
                "looking up trustingly, forest wildflowers around them"
            ),
            (
                "The wolf running at full speed through the dark forest toward "
                "grandmother's cottage while the girl picks flowers in a sunny meadow "
                "in the background, split composition showing both scenes"
            ),
            (
                "The wolf in grandmother's nightcap and spectacles lying in bed, "
                "the little girl in red standing beside the bed looking puzzled, "
                "'What big eyes you have', cozy cottage interior"
            ),
            (
                "A brave woodsman with an axe bursting through the cottage door, "
                "the wolf leaping from the bed, the girl hiding behind a chair, "
                "dramatic action moment, warm cottage light"
            ),
            (
                "Grandmother, the girl in red, and the woodsman sitting together "
                "at a table eating cake, the wolf gone, warmth and safety, afternoon "
                "sunlight streaming through the window, a happy ending"
            ),
        ],
    },
    "the-frog-prince": {
        "cover": (
            "A golden ball splashing into a lily-covered pond, a small green frog "
            "with a tiny golden crown sitting on a lily pad looking up, a princess "
            "in a beautiful dress reaching toward the water, enchanted garden setting"
        ),
        "scenes": [
            (
                "A young princess playing alone in a castle garden, tossing a golden "
                "ball high in the air near a deep well surrounded by ferns, "
                "sunny day, butterflies, colorful flowers"
            ),
            (
                "The golden ball falling into the dark deep well, the princess kneeling "
                "and crying at the well's edge, a small friendly frog peeking up "
                "from the water surface with kind eyes"
            ),
            (
                "The frog sitting on the dining table at the royal palace, eating from "
                "a golden plate while the disgusted princess looks away, the king "
                "sternly pointing at her to keep her promise"
            ),
            (
                "The princess reluctantly placing the small frog on her silk pillow "
                "in her bedroom, moonlight through the window, the frog looking "
                "hopeful, magical sparkles beginning to appear"
            ),
            (
                "A magical burst of golden light as the frog transforms — mid-transformation "
                "showing the frog becoming a handsome prince, sparkles and swirling magic, "
                "the princess gasping in amazement"
            ),
            (
                "The prince and princess riding in a golden carriage toward a distant "
                "castle, a loyal servant on the back of the carriage with tears of joy, "
                "the iron bands around his heart breaking, sunset, celebration"
            ),
        ],
    },
    "the-star-money": {
        "cover": (
            "A small poor girl standing in a snowy field at night, golden stars "
            "falling from the dark sky and turning into coins as they land, "
            "the girl looking up in wonder with outstretched hands, magical glow"
        ),
        "scenes": [
            (
                "A small orphan girl with a piece of bread walking alone on a "
                "snowy winter road, wearing thin clothes, a cold wind blowing, "
                "bare trees, but her face showing kindness not sadness"
            ),
            (
                "The girl giving her bread to a hungry old man, her cap to a "
                "freezing child, her coat to another shivering child, each act "
                "of generosity shown in sequence, golden warmth despite the snow"
            ),
            (
                "The girl standing alone in a dark snowy forest wearing almost nothing, "
                "looking up at the night sky with faith, stars beginning to glow "
                "extra bright, a warm magical light starting to surround her"
            ),
            (
                "Golden stars falling from the sky like rain, transforming into "
                "shining gold coins as they touch the ground around the girl, "
                "she is wearing a beautiful new dress of starlight, magical wonder"
            ),
        ],
    },
    "the-town-musicians-of-bremen": {
        "cover": (
            "Four animals stacked on top of each other — a donkey, a dog, a cat, "
            "and a rooster on top — silhouetted against a full moon, "
            "a road leading to a distant town, musical notes in the air"
        ),
        "scenes": [
            (
                "An old tired donkey being chased away from a farm by an angry farmer, "
                "the donkey walking sadly down a country road, sunset, carrying nothing, "
                "looking back at the farm one last time"
            ),
            (
                "The donkey meeting a tired old dog, then a weary cat, then a rooster "
                "on the road, each animal looking old but hopeful, joining together "
                "as a group walking down the road toward Bremen"
            ),
            (
                "The four animals peering through a lit cottage window at night, "
                "seeing robbers eating at a table piled with food and gold, "
                "the animals' eyes wide with a plan forming"
            ),
            (
                "The four animals stacked — donkey, dog, cat, rooster on top — "
                "making a terrible noise together (braying, barking, meowing, crowing) "
                "crashing through the window, the robbers fleeing in terror"
            ),
            (
                "The four animal friends sitting comfortably in the cozy cottage, "
                "the donkey by the fire, the dog on a rug, the cat on a chair, "
                "the rooster on a beam, all happy and warm, the table set with food"
            ),
        ],
    },
    "the-wolf-and-the-seven-young-goats": {
        "cover": (
            "A mother goat in an apron standing at the door of a cozy cottage, "
            "seven small baby goats peeking from behind her, a shadowy wolf "
            "visible lurking behind a tree in the background"
        ),
        "scenes": [
            (
                "A loving mother goat in a bonnet and apron warning her seven baby "
                "goats at the cottage door before leaving, the little goats listening "
                "attentively, each one different and cute, cozy interior"
            ),
            (
                "A big bad wolf at the cottage door trying to imitate the mother's "
                "voice, one suspicious baby goat peering through the mail slot "
                "at the wolf's big dark paw, the others hiding behind furniture"
            ),
            (
                "The wolf with a paw whitened with flour and a voice sweetened with "
                "chalk, the cottage door opening, baby goats scattering in panic "
                "to hide — under the table, in the clock, under the bed, in the stove"
            ),
            (
                "The mother goat returning home to find the door open and cottage "
                "in disarray, one baby goat crying inside the grandfather clock, "
                "the mother's face showing horror and determination"
            ),
            (
                "The mother goat finding the wolf asleep under a tree with a huge "
                "belly, the one saved baby goat beside her, scissors and stones "
                "ready, a determined rescue about to begin"
            ),
            (
                "All seven baby goats freed and dancing around the sleeping wolf "
                "whose belly is now filled with heavy stones, the mother goat watching "
                "proudly, the wolf starting to wake up, a well by the river nearby"
            ),
            (
                "The whole goat family celebrating together in their cozy cottage, "
                "the mother hugging all seven babies, warm firelight, a feast on "
                "the table, safe and happy, the wolf gone forever"
            ),
        ],
    },
}


class Command(BaseCommand):
    help = "Dijeli priče u stranice slikovnice (cover + inner + back)"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Slug jedne priče")
        parser.add_argument("--force", action="store_true", help="Prebriši postojeće stranice")
        parser.add_argument("--dry-run", action="store_true", help="Samo prikaži, ne kreiraj")

    def handle(self, *args, **options):
        slug = options.get("slug")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        # Osiguraj default stil
        style, _ = StoryBookStyle.objects.using(DB).get_or_create(
            slug="watercolor-parchment",
            defaults={
                "name": "PLAY.EU Watercolor Parchment",
                "prompt_prefix": (
                    "Children's storybook watercolor illustration on aged parchment paper, "
                    "warm golden light, soft watercolor edges, European folk art inspired, "
                    "Caldecott Medal quality, gentle and whimsical, safe for children, "
                    "muted earth tones with pops of color, no text in image, no logos, "
                    "wide aspect ratio, "
                ),
                "prompt_suffix": (
                    ", masterful watercolor technique, subtle paper texture visible, "
                    "storybook illustration, award-winning children's book art"
                ),
                "negative_prompt": (
                    "scary, violent, blood, weapons, nudity, photorealistic faces, "
                    "modern clothing, technology, text, watermark, signature, "
                    "dark themes, horror, anime style, cartoon style, 3D render"
                ),
                "dominant_palette": [
                    "#FDF6E3",
                    "#C9A84C",
                    "#8B4513",
                    "#2D5F2D",
                    "#1B4F72",
                    "#87CEEB",
                    "#DDA0DD",
                ],
                "font_family": "Cormorant Garamond",
                "page_texture": "parchment",
                "is_default": True,
            },
        )

        qs = ParallelStory.objects.using(DB).filter(is_published=True)
        if slug:
            qs = qs.filter(slug=slug)

        total_created = 0
        for story in qs:
            existing = StoryPage.objects.using(DB).filter(story=story).count()
            if existing and not force:
                self.stdout.write(f"  SKIP {story.slug} — već ima {existing} stranica (--force za prebrisati)")
                continue

            if force and existing:
                if not dry_run:
                    StoryPage.objects.using(DB).filter(story=story).delete()
                self.stdout.write(f"  DELETE {story.slug} — {existing} starih stranica")

            scenes = SCENE_BANK.get(story.slug, {})
            cover_scene = scenes.get("cover", f"Cover illustration for the fairy tale {story.title_hr}")
            inner_scenes = scenes.get("scenes", [])

            # Pokupi paragrafe
            paragraphs_hr = [p.strip() for p in story.text_hr.split("\n") if p.strip()]
            paragraphs_de = [p.strip() for p in (story.text_de or "").split("\n") if p.strip()]
            paragraphs_en = [p.strip() for p in (story.text_en or "").split("\n") if p.strip()]

            # Filtriraj "Titel:" prefix iz DE teksta
            paragraphs_de = [p for p in paragraphs_de if not p.startswith("Titel:")]

            pages_to_create = []

            # Stranica 0: Naslovnica
            pages_to_create.append(
                StoryPage(
                    story=story,
                    page_number=0,
                    page_type="cover",
                    layout="full_bleed",
                    scene_description=cover_scene,
                    text_hr=story.title_hr,
                    text_de=story.title_de or story.title_hr,
                    text_en=story.title_en or story.title_hr,
                    image_alt_text=f"Naslovnica: {story.title_hr}",
                    style=style,
                )
            )

            # Unutarnje stranice (1 paragraf = 1 stranica)
            layouts = [
                "top_image",
                "split_50_50",
                "top_image",
                "left_image",
                "top_image",
                "split_50_50",
                "top_image",
                "bottom_image",
                "top_image",
                "left_image",
            ]
            for i, para_hr in enumerate(paragraphs_hr):
                page_num = i + 1
                scene = (
                    inner_scenes[i]
                    if i < len(inner_scenes)
                    else f"Scene {page_num} of {story.title_hr}: {para_hr[:100]}"
                )
                para_de = paragraphs_de[i] if i < len(paragraphs_de) else ""
                para_en = paragraphs_en[i] if i < len(paragraphs_en) else ""
                layout = layouts[i % len(layouts)]

                pages_to_create.append(
                    StoryPage(
                        story=story,
                        page_number=page_num,
                        page_type="inner",
                        layout=layout,
                        scene_description=scene,
                        text_hr=para_hr,
                        text_de=para_de,
                        text_en=para_en,
                        image_alt_text=f"{story.title_hr}, stranica {page_num}",
                        style=style,
                    )
                )

            # Zadnja stranica
            back_page_num = len(paragraphs_hr) + 1
            pages_to_create.append(
                StoryPage(
                    story=story,
                    page_number=back_page_num,
                    page_type="back",
                    layout="full_bleed",
                    scene_description=f"Decorative endpage for {story.title_hr}, ornamental border, 'The End' feeling",
                    text_hr=story.moral_lesson or "Kraj.",
                    text_de="Ende.",
                    text_en="The End.",
                    image_alt_text=f"Zadnja stranica: {story.title_hr}",
                    style=style,
                )
            )

            if dry_run:
                self.stdout.write(f"  DRY-RUN {story.slug}: {len(pages_to_create)} stranica")
            else:
                StoryPage.objects.using(DB).bulk_create(pages_to_create)
                total_created += len(pages_to_create)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ {story.slug}: {len(pages_to_create)} stranica "
                        f"({len(paragraphs_hr)} inner + cover + back)"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"\nUkupno kreirano: {total_created} stranica"))
