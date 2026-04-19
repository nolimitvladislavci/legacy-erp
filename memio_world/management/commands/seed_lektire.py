"""
Seed HR Lektire — obvezni i preporučeni naslovi za razrede 1-8.
Izvor: Ministarstvo znanosti, obrazovanja i sporta RH — Kurikulum HJ

Pokretanje:
  manage.py seed_lektire
  manage.py seed_lektire --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify


LEKTIRE = [
    # ─── 1. razred ────────────────────────────────────────────────
    {
        "grade": 1,
        "title": "Čudnovate zgode šegrta Hlapića",
        "author": "Ivana Brlić-Mažuranić",
        "published_year": 1913,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 140,
        "synopsis": (
            "Hlapić, mali šegrt postolar, bježi od zloga majstora i kreće u pustolovinu. "
            "Na putu susreće zlu vješticu Crnu Magu, prijatelja Gitu i doživljava mnoge avanture "
            "dok traži pravi dom i pravdu."
        ),
        "pedagogical_note": "Razvija empatiju, hrabrost i smisao za pravednost. Prva hrvatska dječja klasika.",
    },
    {
        "grade": 1,
        "title": "Priče iz davnine — Regoč",
        "author": "Ivana Brlić-Mažuranić",
        "published_year": 1916,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 20,
        "synopsis": (
            "Dušan je mali pastir koji se sprijatelji s divovskim Regočem. "
            "Priča o prijateljstvu između malog i velikog, moćnog i krhkog."
        ),
        "pedagogical_note": "Razvija fantaziju i razumijevanje razlika u veličini i snazi.",
    },
    {
        "grade": 1,
        "title": "Antuntun",
        "author": "Grigor Vitez",
        "published_year": 1957,
        "is_mandatory": True,
        "is_public_domain": False,
        "estimated_pages": 32,
        "synopsis": (
            "Zbirka dječjih pjesama o dječaku Antuntunu i njegovim pustolovinama. "
            "Vitezove pjesme pune su humora, igre riječima i radosti djetinjstva."
        ),
        "pedagogical_note": "Uvodi dijete u rimovanu poeziju, igru riječima i ritam govora.",
    },
    {
        "grade": 1,
        "title": "Ježeva kućica",
        "author": "Branko Ćopić",
        "published_year": 1949,
        "is_mandatory": True,
        "is_public_domain": False,
        "estimated_pages": 64,
        "synopsis": (
            "Jež Pinki gradi kućicu i otkriva što znači imati pravi dom. "
            "Vesela priča o šumskim životinjama i vrijednosti zajednice."
        ),
        "pedagogical_note": "Razvija razumijevanje zajedništva i pomaganja drugima.",
    },
    # ─── 2. razred ────────────────────────────────────────────────
    {
        "grade": 2,
        "title": "Vlak u snijegu",
        "author": "Mato Lovrak",
        "published_year": 1933,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 120,
        "synopsis": (
            "Đaci su ostali zaglavljeni u vlaku zbog snijega. Priča o tome kako djeca "
            "surađuju i pomažu jedni drugima, preuzimaju odgovornost i pokazuju hrabrost."
        ),
        "pedagogical_note": "Razvija timski duh, odgovornost i smisao za zajednicu.",
    },
    {
        "grade": 2,
        "title": "Pipi Duga Čarapa",
        "author": "Astrid Lindgren",
        "published_year": 1945,
        "is_mandatory": True,
        "is_public_domain": False,
        "estimated_pages": 160,
        "synopsis": (
            "Pipi je djevojčica koja živi sama s konjem i majmunom, bez roditelja. "
            "Najjača je djevojčica na svijetu i ima neograničenu maštu. "
            "Njezine avanture s prijateljima Tommijem i Annicom puni su humora i slobode."
        ),
        "pedagogical_note": "Razvija neovisnost mišljenja, hrabrost i maštu. Feminizam za djecu.",
    },
    {
        "grade": 2,
        "title": "Pčelica Maja",
        "author": "Waldemar Bonsels",
        "published_year": 1912,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 200,
        "synopsis": (
            "Pčelica Maja napušta košnicu i kreće istraživati svijet. "
            "Upoznaje razne kukce i životinje, uči o prijateljstvu i odgovornosti."
        ),
        "pedagogical_note": "Razvija radoznalost, prijateljstvo i razumijevanje prirode.",
    },
    # ─── 3. razred ────────────────────────────────────────────────
    {
        "grade": 3,
        "title": "Libro od Uskrsa",
        "author": "Silvije Strahimir Kranjčević",
        "published_year": 1900,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 20,
        "synopsis": "Čuvena Kranjčevićeva rodoljubna lirika. Odlomci pogodni za 3. razred.",
        "pedagogical_note": "Uvod u rodoljubnu poeziju i hrvatska kulturna baština.",
    },
    {
        "grade": 3,
        "title": "Šegrt Hlapić — strip",
        "author": "Ivana Brlić-Mažuranić / adaptacija",
        "published_year": 1968,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 64,
        "synopsis": "Strip adaptacija klasičnog romana. Vizualna naracija iste priče o hrabrom Hlapiću.",
        "pedagogical_note": "Razvija vizualnu pismenost i usporedbu medija (knjiga vs strip).",
    },
    {
        "grade": 3,
        "title": "Knjiga o džungli",
        "author": "Rudyard Kipling",
        "published_year": 1894,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 240,
        "synopsis": (
            "Mowgli je dječak odgojen u džungli od vukova. "
            "Uz učitelja medvjeda Balua i pantera Bagiru uči zakone džungle, "
            "suočava se sa zloćudnim tigrom Sherkhanom i traži svoje mjesto u svijetu."
        ),
        "pedagogical_note": "Razvija razumijevanje identiteta, zajednice i pravila. Ekološka osviještenost.",
    },
    {
        "grade": 3,
        "title": "Zlatna ptica — priče braće Grimm",
        "author": "Jacob i Wilhelm Grimm",
        "published_year": 1812,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 80,
        "synopsis": "Izbor bajki: Zlatna ptica, Ivica i Marica, Trnoružica, Pepeljuga. "
        "Klasične europske bajke s moralnim poukama.",
        "pedagogical_note": "Razvija razumijevanje simbolike, dobra i zla, moralne pouke.",
    },
    # ─── 4. razred ────────────────────────────────────────────────
    {
        "grade": 4,
        "title": "Mali princ",
        "author": "Antoine de Saint-Exupéry",
        "published_year": 1943,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 96,
        "synopsis": (
            "Pilot koji je prinudno sletio u pustinju upoznaje malog princa s asteroida B-612. "
            "Princ mu priča o svom putovanju po planetima, o ruži koju je volio i o tome "
            "što je zaista važno u životu: 'Dobro se vidi samo srcem — bitno je nevidljivo očima.'"
        ),
        "pedagogical_note": "Filozofija za djecu: prijateljstvo, ljubav, odgovornost, odrastanje.",
    },
    {
        "grade": 4,
        "title": "Divno putovanje Nilsa Holgerssona",
        "author": "Selma Lagerlöf",
        "published_year": 1906,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 320,
        "synopsis": (
            "Nils Holgersson, nestašni dječak, pretvoren je u palčića i odhvatio se "
            "na leđima divlje guske Martinom kroz cijelu Švedsku. "
            "Topografija, fauna i legende Skandinavije kroz dječje oči."
        ),
        "pedagogical_note": "Razvija geografsku pismenost, empatiju prema životinjama, odgovornost.",
    },
    {
        "grade": 4,
        "title": "Orašar i kralj miševa",
        "author": "E.T.A. Hoffmann",
        "published_year": 1816,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 80,
        "synopsis": (
            "Na Badnjak djevojčica Klara dobiva na dar Orašara. Noću igračke ožive, "
            "vodi se bitka između Orašara i kralja miševa, a Klara se nađe u čarobnoj zemlji."
        ),
        "pedagogical_note": "Mašta, granica između sna i jave, bajkovitost blagdanskog vremena.",
    },
    {
        "grade": 4,
        "title": "Winnie-Pooh",
        "author": "A. A. Milne",
        "published_year": 1926,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 160,
        "synopsis": (
            "Medvjedić Winnie Pooh i njegovi prijatelji — Prasić, Magarac Ijo, Kanga i Roo — "
            "žive u Šumi Stotinu jutara i doživljavaju smiješne avanture pune prijateljstva i mudrosti."
        ),
        "pedagogical_note": "Prijateljstvo, prihvaćanje razlika, humor i blaga filozofija djetinjstva.",
    },
    # ─── 5. razred ────────────────────────────────────────────────
    {
        "grade": 5,
        "title": "Priče iz davnine",
        "author": "Ivana Brlić-Mažuranić",
        "published_year": 1916,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 200,
        "synopsis": (
            "Zbirka mitoloških priča iz slavenskog folklora: Kako je Potjeh tražio istinu, "
            "Šuma Striborova, Bratac Jaglenac i sestrica Rutvica, Ribar Palunko i njegova žena. "
            "Hrvatski odgovor na Andersenove bajke."
        ),
        "pedagogical_note": "Slavenska mitologija, moralne dvojbe, žrtvovanje za dobro. Nacionalna baština.",
    },
    {
        "grade": 5,
        "title": "Oliver Twist",
        "author": "Charles Dickens",
        "published_year": 1837,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 400,
        "synopsis": (
            "Oliver Twist, siročić iz engleskog sirotišta, bježi u London gdje upada "
            "u gang malih kradljivaca. Dickensova kritika viktorijanskog siromaštva "
            "i socijalne nepravde."
        ),
        "pedagogical_note": "Socijalna pravda, empatija, razumijevanje siromaštva kroz književnost.",
    },
    {
        "grade": 5,
        "title": "Tom Sawyer",
        "author": "Mark Twain",
        "published_year": 1876,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 280,
        "synopsis": (
            "Tom Sawyer je nestašni dječak u malom gradu uz Mississippi. "
            "Zajedno s prijateljem Huckleberry Finnom svjedoči ubojstvu, "
            "luta ostrvom misleći da je mrtav i traži zakopano blago."
        ),
        "pedagogical_note": "Avantura, prijateljstvo, moralne odluke, odrastanje u 19. st. Americi.",
    },
    {
        "grade": 5,
        "title": "Alisa u zemlji čudesa",
        "author": "Lewis Carroll",
        "published_year": 1865,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 160,
        "synopsis": (
            "Alisa pada u zečju rupu i dospijeva u nevjerojatnu zemlju gdje ništa "
            "nije logično — gusjenica puši lulu, Mahar iz Cheshirea nestaje ostavljajući osmijeh, "
            "a Kraljica viče 'Glavu mu odrubite!' za svaku sitnicu."
        ),
        "pedagogical_note": "Logika, nonsens, identitet, kritičko mišljenje. Klasik apсurdne književnosti.",
    },
    # ─── 6. razred ────────────────────────────────────────────────
    {
        "grade": 6,
        "title": "Ilijada — odlomci",
        "author": "Homer",
        "published_year": -800,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 60,
        "synopsis": (
            "Odabrani odlomci iz Homerove epike o Trojanskom ratu: "
            "Ahilejeva srdžba, dvoboj Hektora i Ahileja, Prijamova tuga. "
            "Temelj europske književnosti."
        ),
        "pedagogical_note": "Uvod u antičku književnost, heroje, čast i sudbinu. Temelj europske kulture.",
    },
    {
        "grade": 6,
        "title": "San Ivanjske noći",
        "author": "William Shakespeare",
        "published_year": 1600,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 100,
        "synopsis": (
            "Tri isprepletene priče: atenska aristokratija, skupina obrtnika-amatera "
            "i vilinska kraljevina. Pukovo neprijazno čarolijom zavodi zaljubljenike "
            "u neočekivane parove."
        ),
        "pedagogical_note": "Drama, humor, ljubav, identitet. Uvod u Shakespearea.",
    },
    {
        "grade": 6,
        "title": "Dvadeset tisuća milja pod morem",
        "author": "Jules Verne",
        "published_year": 1870,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 400,
        "synopsis": (
            "Profesor Aronnax i njegovi pratioci zatvorenici su na podmornici Nautilus "
            "pod zapovjedništvom tajanstvenog kapetana Nema. "
            "Putuju podmorskim dubinama otkrivajući čuda oceanskih predjela."
        ),
        "pedagogical_note": "Znanstvena fantastika, ekologija oceana, tehnički optimizam 19. st.",
    },
    {
        "grade": 6,
        "title": "Heidi",
        "author": "Johanna Spyri",
        "published_year": 1881,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 280,
        "synopsis": (
            "Siroče Heidi živi s djedom na švicarskim Alpama. "
            "Odvučena u Frankfurt da posluži kao drugarica bolesnoj Klari, "
            "čezne za planinama i na kraju se vraća svom domu."
        ),
        "pedagogical_note": "Dom, priroda, prijateljstvo, bolest i iscjeljenje. Klasik djevojačke literature.",
    },
    # ─── 7. razred ────────────────────────────────────────────────
    {
        "grade": 7,
        "title": "Odiseja — odlomci",
        "author": "Homer",
        "published_year": -800,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 80,
        "synopsis": (
            "Odabrani odlomci Odisejeva povratka s Trojanskog rata: "
            "Kiklop Polifem, čarobnica Kirka, Sirene, Scila i Haribda, "
            "povratak Itaci i osveta prosjacima."
        ),
        "pedagogical_note": "Ep, junak, lutos i povratak — temelji narativne književnosti.",
    },
    {
        "grade": 7,
        "title": "Romeo i Julija",
        "author": "William Shakespeare",
        "published_year": 1597,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 120,
        "synopsis": (
            "Romeo Montague i Julija Capulet zaljube se na maškaranoj zabavi. "
            "Njihove obitelji su neprijatelji. Njihova ljubav, "
            "zabune i tragična sudbina postale su simbol zabranjene ljubavi za sva vremena."
        ),
        "pedagogical_note": "Ljubav, mržnja, sudbina, tragedija. Uvod u dramsku strukturu.",
    },
    {
        "grade": 7,
        "title": "Pustolovine Toma Sawyera / Huckleberry Finn",
        "author": "Mark Twain",
        "published_year": 1884,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 360,
        "synopsis": (
            "Huckleberry Finn bježi od okrutnog oca i pluta rijekom Mississippi "
            "zajedno s robom Jimom koji traži slobodu. "
            "Twainova kritika ropstva i američkog društva 19. st."
        ),
        "pedagogical_note": "Sloboda, ropstvo, moralne dileme — američka književna baština.",
    },
    {
        "grade": 7,
        "title": "Don Kihot — odlomci",
        "author": "Miguel de Cervantes",
        "published_year": 1605,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 80,
        "synopsis": (
            "Odabrani odlomci iz prvog modernog romana. Vitez tužnog lika Don Kihot "
            "i njegov vjerni štičenici Sancho Panza jure vjetrenjače misleći da su divovi, "
            "bore se za čast i ideale u prozi modernog doba."
        ),
        "pedagogical_note": "Idealizam vs. realizam, satira, identitet, prvi moderni roman.",
    },
    # ─── 8. razred ────────────────────────────────────────────────
    {
        "grade": 8,
        "title": "Jadnici — odlomci",
        "author": "Victor Hugo",
        "published_year": 1862,
        "is_mandatory": True,
        "is_public_domain": True,
        "estimated_pages": 100,
        "synopsis": (
            "Jean Valjean, osuđen na robiju zbog krađe kruha, pokušava se rehabilitirati "
            "u društvu koje mu ne daje šansu. Inspektor Javert ga progoni godinama. "
            "Odlomci: Jean Valjean i bishop, Fantine, Cosette, Pariška barikada."
        ),
        "pedagogical_note": "Socijalna pravda, milost, zakon vs. moral, revolucija. Victor Hugo na vrhuncu.",
    },
    {
        "grade": 8,
        "title": "Gospoda Glembajevi",
        "author": "Miroslav Krleža",
        "published_year": 1929,
        "is_mandatory": True,
        "is_public_domain": False,
        "estimated_pages": 120,
        "synopsis": (
            "Drama o raspadanju bogate građanske obitelji Glembay u Zagrebu. "
            "Leone Glembay suočava se s obiteljskim tajnama, "
            "lažima i propašću u međuratnoj Hrvatskoj."
        ),
        "pedagogical_note": "Hrvatska drama, dekadencija, obiteljske tajne, Krleža kao temelj HR književnosti.",
    },
    {
        "grade": 8,
        "title": "Zločin i kazna — odlomci",
        "author": "Fjodor Dostojevski",
        "published_year": 1866,
        "is_mandatory": False,
        "is_public_domain": True,
        "estimated_pages": 80,
        "synopsis": (
            "Student Raskoljnikov ubija kamatarku vjerujući da ima pravo ubiti zloga "
            "radi općeg dobra. Psihološka drama krivnje, kazne i otkupljenja."
        ),
        "pedagogical_note": "Psihološki realizam, moralne dileme, krivnja i otkupljenje. Uvod u rusku lit.",
    },
    {
        "grade": 8,
        "title": "Starac i more",
        "author": "Ernest Hemingway",
        "published_year": 1952,
        "is_mandatory": True,
        "is_public_domain": False,
        "estimated_pages": 128,
        "synopsis": (
            "Stari kubanski ribar Santiago bori se tri dana i noći s golemom ribom. "
            "Kratka alegorijska novela o ponos, ustrajnosti i čovjekovu dostojanstvu "
            "pred silama prirode."
        ),
        "pedagogical_note": "Hemingwayov princip ledenog brijega, alegorija, borba i dostojanstvo.",
    },
]


class Command(BaseCommand):
    help = "Seed HR OŠ Lektire — razredi 1-8, obvezne i preporučene knjige"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Ne upiši u bazu")
        parser.add_argument("--grade", type=int, help="Samo određeni razred")

    def handle(self, *args, **options):
        from memio_world.lektire_models import LektiraBook

        dry = options["dry_run"]
        grade_filter = options.get("grade")

        books = LEKTIRE
        if grade_filter:
            books = [b for b in books if b["grade"] == grade_filter]

        self.stdout.write(self.style.SUCCESS(f"Seeding {len(books)} lektira..."))
        created_count = updated_count = 0

        for data in books:
            slug_base = slugify(f"{data['grade']}-{data['title'][:50]}")
            if dry:
                self.stdout.write(f"  [{data['grade']}. razred] {data['title']} — {data['author']}")
                continue

            obj, created = LektiraBook.objects.using("memio_world").update_or_create(
                slug=slug_base,
                defaults={
                    "title": data["title"],
                    "author": data["author"],
                    "published_year": data.get("published_year"),
                    "grade": data["grade"],
                    "is_mandatory": data["is_mandatory"],
                    "is_public_domain": data["is_public_domain"],
                    "estimated_pages": data.get("estimated_pages", 0),
                    "synopsis": data["synopsis"],
                    "pedagogical_note": data.get("pedagogical_note", ""),
                    "is_published": True,
                    "language": "hr",
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
            symbol = "NEW" if created else "UPD"
            self.stdout.write(f"  [{symbol}] {data['grade']}. razred — {data['title']}")

        if not dry:
            self.stdout.write(self.style.SUCCESS(f"\nDone: {created_count} new, {updated_count} updated"))
        else:
            self.stdout.write(self.style.WARNING("\nDry run — ništa nije zapisano"))
