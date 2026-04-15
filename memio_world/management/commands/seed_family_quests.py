"""
Seed Family Quests — tjedni izazovi za cijelu obitelj.
MOST iz digitalnog u stvarni život.
"""

from django.core.management.base import BaseCommand

QUESTS = [
    # KUHANJE
    {
        "title": "Bakini uštipci — kuhajte zajedno",
        "type": "cooking",
        "season": "any",
        "desc": "1. Nazovite baku i pitajte za recept (ili koristite ovaj: brašno, jaje, mlijeko, šećer, ulje).\n2. DIJETE miješa tijesto. RODITELJ prži.\n3. Posipajte šećerom u prahu.\n4. Fotografirajte gotove uštipke.\n5. BONUS: snimite baku kako objašnjava recept (VoiceLegacy!).",
        "need": "Brašno, jaje, mlijeko, šećer, ulje za prženje, šećer u prahu",
        "time": "45 min",
        "points": 60,
        "grandma": "Uštipci se prave s ljubavlju. Ako su okrugli — naučili ste. Ako nisu — naučili ste da oblik nije važan!",
        "age_min": 4,
        "age_max": 14,
    },
    # AKTIVNOST VANI
    {
        "title": "Lov na prometne znakove — tko će naći više?",
        "type": "outdoor",
        "season": "any",
        "desc": "1. Prošećite kvartom 30 minuta.\n2. Dijete fotografira SVAKI prometni znak koji vidi.\n3. Kod kuće: sortirajte po bojama (crveni = zabrana, plavi = obaveza).\n4. Kviz: roditelj pokazuje znak, dijete govori što znači.\n5. BONUS: nacrtajte vlastiti prometni znak za svoju sobu.",
        "need": "Telefon za fotografiranje, papir i boje za crtanje",
        "time": "1 sat",
        "points": 50,
        "grandma": "U moje vrijeme znakova je bilo 5. Danas ih ima 500. Ali pravilo je isto: crveno znači stani.",
        "age_min": 4,
        "age_max": 10,
    },
    # RAZGOVOR S BAKAMA/DJEDOVIMA
    {
        "title": "Intervju s bakom/djedom — kako je bilo kad si bio/la mali/a?",
        "type": "interview",
        "season": "any",
        "desc": "1. Pripremite 5 pitanja: Što si jeo/la za doručak? Kako si išao/la u školu? Koja ti je bila najdraža igra? Jesi li imao/la ljubimca? Što bi poručio/la djeci danas?\n2. SNIMITE razgovor (mobitel, diktafon).\n3. Dijete nacrta jednu scenu iz bakine/djedove priče.\n4. BONUS: uploadajte snimku u VoiceLegacy — čuvate glas za generacije.",
        "need": "Mobitel za snimanje, papir i boje",
        "time": "30 min + crtanje",
        "points": 80,
        "grandma": "Svaka priča koju zaboravimo je izgubljena zauvijek. Snimite me dok još mogu pričati.",
        "age_min": 5,
        "age_max": 14,
    },
    # RUKOTVORINA
    {
        "title": "Ptičja kućica od kutije za cipele",
        "type": "craft",
        "season": "spring",
        "desc": "1. Uzmite kutiju za cipele.\n2. Izrežite okrugli otvor (roditelj reže!).\n3. Dijete boja kutiju — boje po želji.\n4. Stavite sjemenke ili krušne mrvice unutra.\n5. Objesite na drvo ili balkon.\n6. Svaki dan promatrajte dolaze li ptice — vodite dnevnik!",
        "need": "Kutija za cipele, boje, škare (roditelj!), špaga, sjemenke",
        "time": "1 sat + svakodnevno promatranje",
        "points": 70,
        "grandma": "Ptice pamte tko ih hrani. Ako stavite kućicu — imat ćete prijatelje za cijelu godinu.",
        "age_min": 4,
        "age_max": 10,
    },
    # PRIRODA
    {
        "title": "Posadi sjemenku — dnevnik rasta 14 dana",
        "type": "nature",
        "season": "spring",
        "desc": "1. Uzmite sjemenku (grah, suncokret, ili rajčica).\n2. Posadite u čašu s zemljom.\n3. Svaki dan: zalijte, fotografirajte, izmjerite visinu.\n4. Napravite dnevnik rasta (tablica: dan, visina, crtež).\n5. Nakon 14 dana: presadite u veći lonac ili vrt.",
        "need": "Sjemenke, zemlja, plastična čaša, voda, ravnalo",
        "time": "14 dana × 5 min/dan",
        "points": 100,
        "grandma": "Strpljenje je kao sjemenka. Zaliješ je, čekaš, i jednog dana — cvijet.",
        "age_min": 3,
        "age_max": 10,
    },
    # ČITANJE
    {
        "title": "Čitaj mi — 7 večeri, 7 bajki",
        "type": "reading",
        "season": "any",
        "desc": "1. Odaberite 7 bajki s PLAY.EU platforme (jedna za svaku večer).\n2. Svaku večer roditelj čita JEDNU bajku djetetu.\n3. Dijete bira na kojem jeziku (HR, DE, EN!).\n4. Nakon bajke: dijete prepriča pouku svojim riječima.\n5. Na kraju tjedna: koja bajka je bila najdraža i ZAŠTO?",
        "need": "PLAY.EU aplikacija, mir i mrak, toplina kreveta",
        "time": "7 × 15 min",
        "points": 70,
        "grandma": "Ja sam svaku večer pričala priču. Bez knjige. Iz glave. Ponekad sam izmišljala — i to je bilo najbolje.",
        "age_min": 3,
        "age_max": 8,
    },
    # SPORT
    {
        "title": "Obiteljska olimpijada — 5 disciplina u parku",
        "type": "sport",
        "season": "any",
        "desc": "1. Trčanje na 50m (svi trče — i mama i tata!).\n2. Skok u dalj (s mjesta).\n3. Bacanje loptice u dalj.\n4. Stoj na jednoj nozi — tko duže izdrži?\n5. Trka u vrećama (ili s kašikom i jajem).\nSvi dobivaju medalju (nacrtajte ih od kartona!).",
        "need": "Loptica, vrećica, kašika, jaje (tvrdo kuhano!), karton za medalje",
        "time": "1-2 sata",
        "points": 60,
        "grandma": "Nije važno tko pobijedi. Važno je da ste ZAJEDNO trčali, smijali se, i pali u travu.",
        "age_min": 4,
        "age_max": 14,
    },
    # BRIGA O LJUBIMCU
    {
        "title": "Tjedan odgovornosti — ja brinem o ljubimcu!",
        "type": "pet_care",
        "season": "any",
        "desc": "1. Dijete preuzima brigu o ljubimcu na 7 dana (uz nadzor roditelja).\n2. Svaki dan: hrana, voda, šetnja/čišćenje, igra.\n3. Vodite dnevnik: što je ljubimac radio, kako se osjećao.\n4. Fotografirajte najslađi trenutak svakog dana.\n5. Podijelite na Pet Bridge — pokažite svima kako brinete!",
        "need": "Ljubimac (!), hrana, voda, dnevnik, telefon za fotografije",
        "time": "7 dana × 30 min/dan",
        "points": 100,
        "grandma": "Životinja te ne može nazvati kad je gladna. Ti MORAŠ zapamtiti. To se zove odgovornost.",
        "age_min": 5,
        "age_max": 14,
    },
    # KULTURNI IZLET
    {
        "title": "Istraži svoj grad — 5 mjesta koja nisi znao/la",
        "type": "culture",
        "season": "any",
        "desc": "1. Pronađite 5 mjesta u svom gradu koja nikad niste posjetili.\n2. Idite na svako — fotografirajte.\n3. Dijete zapisuje: Što sam naučio/la? Što mi se svidjelo?\n4. Nacrtajte kartu svog grada s 5 zvjezdica.\n5. BONUS: napravite istu mapu na PLAY.EU i podijelite s drugom djecom!",
        "need": "Udobne cipele, telefon, papir i boje",
        "time": "Pola dana",
        "points": 80,
        "grandma": "Mi smo poznavali svaki kamen u svom selu. Danas djeca ne znaju ime ulice u kojoj žive. Istražite!",
        "age_min": 5,
        "age_max": 14,
    },
    # POMAGANJE
    {
        "title": "Učini nešto lijepo za susjeda",
        "type": "helping",
        "season": "any",
        "desc": "1. Razmislite zajedno: tko u susjedstvu treba pomoć?\n2. Starija gospođa kojoj treba donijeti kruh? Susjed koji ne može pokositi travu?\n3. Napravite nešto KONKRETNO — ne samo razmišljajte.\n4. Dijete piše kratko pismo susjedi/susjedu.\n5. Ne tražite ništa zauzvrat.",
        "need": "Samo dobru volju i malo vremena",
        "time": "30-60 min",
        "points": 100,
        "grandma": "Kad pomogneš nekome, pomogneš i sebi. To je čarolija koju ne možeš kupiti.",
        "age_min": 5,
        "age_max": 14,
    },
]


class Command(BaseCommand):
    help = "Seed Family Quests"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from memio_world.growth_models import FamilyQuest

        dry = options["dry_run"]
        created = 0

        self.stdout.write(self.style.SUCCESS("\n=== OBITELJSKI IZAZOVI ==="))
        for q in QUESTS:
            if dry:
                self.stdout.write(f"  [{q['type']}] {q['title']}")
                created += 1
                continue
            obj, is_new = FamilyQuest.objects.using("memio_world").get_or_create(
                title=q["title"],
                defaults={
                    "quest_type": q["type"],
                    "season": q["season"],
                    "description": q["desc"],
                    "what_you_need": q.get("need", ""),
                    "estimated_time": q.get("time", ""),
                    "grandma_tip": q.get("grandma", ""),
                    "family_points": q["points"],
                    "requires_photo": True,
                    "age_min": q["age_min"],
                    "age_max": q["age_max"],
                    "is_published": True,
                },
            )
            created += 1 if is_new else 0
            self.stdout.write(f"  [{'NEW' if is_new else 'EXISTS'}] {q['title']}")

        self.stdout.write(self.style.SUCCESS(f"\nDONE: {created} izazova"))
