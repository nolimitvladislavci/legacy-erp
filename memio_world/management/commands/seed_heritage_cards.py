"""
Seed Heritage Cards — HR slovarica + bestiarij kartice.

Pokretanje:
  manage.py seed_heritage_cards                # sve setove
  manage.py seed_heritage_cards --set hr_alphabet
  manage.py seed_heritage_cards --set bestiary
  manage.py seed_heritage_cards --dry-run
"""

import logging

from django.core.management.base import BaseCommand
from django.utils.text import slugify

logger = logging.getLogger("play_eu")

HR_ALPHABET = [
    (
        "A",
        "A kao Avion",
        "Avion leti visoko iznad oblaka!",
        "airplane",
        "Jesi li znao da prvi avion braće Wright letio je samo 12 sekundi?",
    ),
    (
        "B",
        "B kao Balun",
        "Balun je okrugao i veseo!",
        "ball",
        "U Hrvatskoj se balun kaže i lopta, a u Dalmaciji — balun!",
    ),
    ("C", "C kao Cvijet", "Cvjetovi čine svijet ljepšim.", "flower", "Suncokret se okreće za suncem!"),
    (
        "Č",
        "Č kao Čokolada",
        "Čokolada je nastala u Meksiku prije 3000 godina!",
        "chocolate",
        "Azteci su pili čokoladu s čilijem — ljuto!",
    ),
    (
        "Ć",
        "Ć kao Ćup",
        "Ćup je stara posuda za vodu.",
        "jug",
        "U starim hrvatskim kućama ćup je bio kao današnji frižider!",
    ),
    ("D", "D kao Drvo", "Drvo nam daje kisik za disanje.", "tree", "Najstarije drvo na svijetu ima preko 5000 godina!"),
    ("Đ", "Đ kao Đak", "Đak je učenik koji ide u školu.", "student", "U Hrvatskoj se kaže đak, a u Njemačkoj Schüler!"),
    (
        "DŽ",
        "DŽ kao Džep",
        "U džepu se skrivaju male tajne.",
        "pocket",
        "Džepovi na odjeći izumljeni su tek u 17. stoljeću!",
    ),
    (
        "E",
        "E kao Europa",
        "Europa je kontinent na kojem živimo.",
        "europe",
        "Europa ima 27 zemalja u EU — i mi smo jedna od njih!",
    ),
    (
        "F",
        "F kao Flauta",
        "Flauta svira najljepše melodije.",
        "flute",
        "Najstarija flauta pronađena je u Njemačkoj — stara 40.000 godina!",
    ),
    (
        "G",
        "G kao Gljiva",
        "Neke gljive su ukusne, a neke opasne!",
        "mushroom",
        "Gljive nisu ni biljke ni životinje — one su posebno carstvo!",
    ),
    (
        "H",
        "H kao Hrast",
        "Hrast je kralj šume.",
        "oak",
        "Slavonski hrast je poznat u cijelom svijetu po svojoj tvrdoći!",
    ),
    (
        "I",
        "I kao Igra",
        "Igra je najbolji način učenja!",
        "game",
        "Djeca se igraju u svakoj kulturi na svijetu — to je univerzalno!",
    ),
    ("J", "J kao Jež", "Jež ima bodlje za zaštitu.", "hedgehog", "Jež ima oko 5000 bodlji — i svaka raste posebno!"),
    ("K", "K kao Krava", "Krava nam daje mlijeko.", "cow", "Jedna krava daje 25 litara mlijeka dnevno!"),
    ("L", "L kao Lav", "Lav je kralj životinja.", "lion", "Lavovi spavaju do 20 sati dnevno!"),
    (
        "LJ",
        "LJ kao Ljuljačka",
        "Na ljuljački možeš dodirnuti nebo!",
        "swing",
        "Ljuljačke su stare preko 5000 godina — pronađene su na Kreti!",
    ),
    ("M", "M kao More", "More je plavo i beskrajno.", "sea", "Jadransko more ima preko 1000 otoka!"),
    ("N", "N kao Noć", "Noću svijetle zvijezde.", "night", "Golim okom možeš vidjeti oko 2500 zvijezda!"),
    ("NJ", "NJ kao Njuška", "Njuška je nos kod životinja.", "snout", "Pas njuškom može otkriti bolest kod čovjeka!"),
    (
        "O",
        "O kao Oblak",
        "Oblaci su napravljeni od sitnih kapljica vode.",
        "cloud",
        "Prosječni oblak teži oko 500 tona — koliko 100 slonova!",
    ),
    ("P", "P kao Ptica", "Ptice pjevaju najljepše pjesme.", "bird", "Selice putuju i do 70.000 km godišnje!"),
    ("R", "R kao Riba", "Ribe žive u moru i rijekama.", "fish", "U Jadranskom moru živi preko 400 vrsta riba!"),
    (
        "S",
        "S kao Sunce",
        "Sunce nam daje svjetlo i toplinu.",
        "sun",
        "Sunce je toliko veliko da u njega stane milijun Zemalja!",
    ),
    (
        "Š",
        "Š kao Škola",
        "U školi učimo i rastemo.",
        "school",
        "Najstarija škola na svijetu je u Maroku — osnovana 859. godine!",
    ),
    ("T", "T kao Torta", "Torta je za slavlje!", "cake", "Tradicija rođendanske torte potječe iz stare Grčke!"),
    ("U", "U kao Uho", "Ušima čujemo glazbu i priče.", "ear", "Tvoje uho raste cijeli život — nikad ne prestane!"),
    ("V", "V kao Vjetar", "Vjetar pokreće vjetrenjače.", "wind", "Bura na Kvarneru može puhati i do 250 km/h!"),
    (
        "Z",
        "Z kao Zvijezda",
        "Zvijezde su daleka sunca.",
        "star",
        "Najbliža zvijezda (osim Sunca) udaljena je 4 godine svjetlosti!",
    ),
    (
        "Ž",
        "Ž kao Žirafa",
        "Žirafa je najviša životinja na svijetu.",
        "giraffe",
        "Žirafin jezik je dug 45 cm — i plav je!",
    ),
]


BESTIARY_CARDS = [
    (
        "Zmaj",
        "Dragon",
        "Drache",
        "Zmaj čuva blago u dubokoj pećini.",
        "U hrvatskim legendama zmaj živi na Medvednici!",
        "medieval",
    ),
    (
        "Jednorog",
        "Unicorn",
        "Einhorn",
        "Jednorog je bijeli konj s čarobnim rogom na čelu.",
        "Srednjovjekovni ljudi vjerovali su da jednorogov rog liječi bolesti!",
        "medieval",
    ),
    (
        "Feniks",
        "Phoenix",
        "Phönix",
        "Feniks je ptica koja se rađa iz vlastita pepela.",
        "Feniks simbolizira novi početak — uvijek se može početi ispočetka!",
        "medieval",
    ),
    (
        "Grifon",
        "Griffin",
        "Greif",
        "Grifon ima tijelo lava i krila orla.",
        "Grifoni su čuvali zlato u legendarnoj Skitiji!",
        "medieval",
    ),
    (
        "Bazilisk",
        "Basilisk",
        "Basilisk",
        "Bazilisk je kralj zmija — ubija pogledom!",
        "Jedini lijek protiv baziliska je zrcalo — jer se prestraši vlastitog odraza!",
        "medieval",
    ),
    (
        "Salamander",
        "Salamander",
        "Salamander",
        "Ljudi su vjerovali da salamander živi u vatri.",
        "Zapravo, salamanderi vole vlagu — mit dolazi jer se skrivaju u mokrom drvu!",
        "medieval",
    ),
    (
        "Pelikan",
        "Pelican",
        "Pelikan",
        "Pelikan u legendama hrani mlade vlastitom krvlju.",
        "Pravi pelikani imaju vrećastu kljun u koji stane 11 litara vode!",
        "medieval",
    ),
    (
        "Morska sirena",
        "Mermaid",
        "Meerjungfrau",
        "Sirene žive u dubokom moru i pjevaju prekrasne pjesme.",
        "U Dubrovniku postoji legenda o sireni koja čuva grad!",
        "medieval",
    ),
    (
        "Kentaur",
        "Centaur",
        "Zentaur",
        "Kentaur je pola čovjek, pola konj.",
        "Kentaur Hiron iz grčkih legendi bio je mudri učitelj junaka!",
        "ancient",
    ),
    (
        "Pegaz",
        "Pegasus",
        "Pegasus",
        "Pegaz je krilatokoni konj koji leti iznad oblaka.",
        "Kad je Pegaz udario kopitom o tlo, nastao je izvor vode!",
        "ancient",
    ),
]


class Command(BaseCommand):
    help = "Seed Heritage Cards — HR slovarica + bestijarij"

    def add_arguments(self, parser):
        parser.add_argument("--set", type=str, help="Samo ovaj set (hr_alphabet, bestiary)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from memio_world.play_eu_models import HeritageCard

        dry_run = options["dry_run"]
        target_set = options.get("set")
        created = 0

        if not target_set or target_set == "hr_alphabet":
            self.stdout.write(self.style.SUCCESS("\n=== HR SLOVARICA ==="))
            for i, (letter, front, back, icon, fun_fact) in enumerate(HR_ALPHABET):
                slug = slugify(f"hr-alphabet-{letter}")
                if HeritageCard.objects.using("memio_world").filter(slug=slug).exists():
                    continue
                if dry_run:
                    self.stdout.write(f"  [{letter}] {front}")
                    created += 1
                    continue
                HeritageCard.objects.using("memio_world").create(
                    slug=slug,
                    title=f"Slovo {letter}",
                    title_hr=front,
                    title_de=f"{letter} wie...",
                    title_en=f"{letter} for...",
                    card_type="alphabet",
                    front_text=letter,
                    back_text=back,
                    fun_fact=fun_fact,
                    background_color="#F5E6CC",
                    country_of_origin="Croatia",
                    game_type="quiz",
                    difficulty=1,
                    points_value=10,
                    card_set="hr_alphabet",
                    position_in_set=i,
                    is_published=True,
                )
                created += 1
                self.stdout.write(f"  [SAVED] {letter} — {front}")

        if not target_set or target_set == "bestiary":
            self.stdout.write(self.style.SUCCESS("\n=== BESTIJARIJ ==="))
            for i, (hr, en, de, desc, fun_fact, period) in enumerate(BESTIARY_CARDS):
                slug = slugify(f"bestiary-{en}")
                if HeritageCard.objects.using("memio_world").filter(slug=slug).exists():
                    continue
                if dry_run:
                    self.stdout.write(f"  [{hr}] {desc[:50]}")
                    created += 1
                    continue
                HeritageCard.objects.using("memio_world").create(
                    slug=slug,
                    title=hr,
                    title_hr=hr,
                    title_de=de,
                    title_en=en,
                    card_type="animal",
                    front_text=hr,
                    back_text=desc,
                    fun_fact=fun_fact,
                    background_color="#2C1810",
                    historical_period=f"{period} era",
                    source_collection="European Bestiaries / Aberdeen Bestiary",
                    country_of_origin="Europe",
                    game_type="memory",
                    difficulty=2,
                    points_value=15,
                    card_set="eu_bestiary",
                    position_in_set=i,
                    is_published=True,
                )
                created += 1
                self.stdout.write(f"  [SAVED] {hr} ({en})")

        self.stdout.write(self.style.SUCCESS(f"\nDONE: {created} kartica kreirano"))
