"""
Seed Comfort Engine — snovi, tješenje, šale.
Sadržaj koji drži dijete sigurnim i nasmijanim.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed DreamGuard, ComfortCards, JokeBox"

    def add_arguments(self, parser):
        parser.add_argument("--only", type=str, help="dreams|comfort|jokes")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        only = options.get("only")
        dry = options["dry_run"]
        if not only or only == "dreams":
            self._seed_dreams(dry)
        if not only or only == "comfort":
            self._seed_comfort(dry)
        if not only or only == "jokes":
            self._seed_jokes(dry)

    def _seed_dreams(self, dry):
        from memio_world.comfort_models import DreamGuard

        self.stdout.write(self.style.SUCCESS("\n=== DREAM GUARD ==="))
        dreams = [
            {
                "type": "nightmare",
                "title": "Imao/la sam ružan san",
                "grandma": "Dođi k baki, zlato. Snovi su kao oblaci — izgledaju strašno, ali kad im priđeš, samo su para i ništa više. Tvoj ružan san je već gotov. Ti si tu, sigurno, u svom krevetu. Baka je s tobom.",
                "mama": "Hej, tu sam. Zagrli me. Snovi nisu stvarni — tvoj mozak samo slaže slike kao puzzle, i ponekad složi nešto čudno. To je potpuno normalno. Svi ljudi sanjaju, i svi ponekad sanjaju ružno.",
                "explain": "Tvoj mozak je kao mali filmski režiser koji radi cijelu noć. Ponekad snimi veseli film, a ponekad strašni. Ali znaš što? TI BIRAŠ što ćeš gledati kad se probudiš. Zatvori oči i zamisli svoje najdraže mjesto.",
                "technique": "TEHNIKA SIGURNOG MJESTA:\n1. Zatvori oči.\n2. Zamisli svoje najdraže mjesto (more, bakina kuća, park).\n3. Duboko udahni — 1, 2, 3, 4.\n4. Polako izdahni — 1, 2, 3, 4, 5, 6.\n5. Ponovi 3 puta.\n6. Sad si na svom sigurnom mjestu. Ništa te ne može dohvatiti.",
                "escalation": "Ako se noćne more ponavljaju svaku noć duže od 2 tjedna, razgovarajte s pedijatrom. To je potpuno normalan korak — kao kad odete zubaru za zub.",
            },
            {
                "type": "monster",
                "title": "Čudovište u sobi",
                "grandma": "Znаš li što čudovišta ne podnose? SMIJEH. Čim se nasmiješ — oni pobjegnu. Jer čudovišta žive od straha, a kad se smiješ — nema straha. Probaj: zamisli to čudovište u ružičastim čarapama. Vidiš? Već nije strašno!",
                "mama": "Hajde da zajedno pogledamo — pod krevetom? Iza ormara? Vidiš — ništa! Tvoja soba je sigurna. A znaš što? Možemo ostaviti malo svjetla da ti pravi društvo.",
                "explain": "Kad je mrak, tvoje oči ne vide dobro, pa tvoj mozak IZMIŠLJA što bi moglo biti u mraku. To se zove mašta. Ista mašta koja ti pomaže crtati prekrasne crteže — ponekad nacrta i čudovište. Ali to čudovište postoji samo u tvojoj glavi.",
                "technique": "TEHNIKA ČUDOVIŠTA U ČARAPAMA:\n1. Zamisli čudovište.\n2. Sad mu stavi RUŽIČASTE ČARAPE.\n3. Dodaj mu SMIJEŠAN ŠEŠIR.\n4. Napravi da PLEŠE.\n5. Vidiš — sad je smiješno, ne strašno!\n6. Ti si jači/jača od mašte.",
                "escalation": "",
            },
            {
                "type": "falling",
                "title": "Sanjao/la sam da padam",
                "grandma": "I baka je to sanjala kad je bila mala! Cijeli svijet to sanja. Znaš što to znači? Tvoje tijelo se opušta za spavanje, i mozak misli da padaš. Ali ne padaš — ležiš sigurno u krevetu.",
                "mama": "To je jedna od najčešćih vrsta snova. Čak i odrasli to sanjaju! Tvoje tijelo je sigurno u krevetu. Probaj se okrenuti na drugu stranu i zamisliti da LETIŠ umjesto da padaš.",
                "explain": "Kad zaspiš, tvoji mišići se opuste. Ponekad se opuste tako brzo da tvoj mozak pomisli: 'Padamo!' i ti osjetiš trzaj. To se zove hipnički trzaj i potpuno je normalno. Čak i astronauti to osjećaju!",
                "technique": "TEHNIKA LETENJA:\n1. Ako u snu padaš — raširi ruke.\n2. Zamisli da imaš krila.\n3. Sad NE padaš — LETIŠ!\n4. Letiš iznad oblaka, iznad grada, iznad svega.\n5. Ti kontroliraš svoj san.",
                "escalation": "",
            },
            {
                "type": "lost",
                "title": "Izgubio/la sam se u snu",
                "grandma": "Zlato, nikad se ne možeš zaista izgubiti. Jer kamo god odeš — tamo si TI. A dok si ti tu — sve je u redu. A kad se probudiš — tu je tvoj krevet, tvoja soba, tvoja mama, tata, i baka.",
                "mama": "U snu si se izgubio/la, ali pogledaj — ovdje si! U svom krevetu. Tata je u susjednoj sobi. Sve je na svom mjestu. San je kao film koji se završio — sad je tvoja stvarnost, i ona je sigurna.",
                "explain": "San o gubitku je način na koji tvoj mozak vježba snalažljivost. Kao trening! Čak je i korisno — jer tvoj mozak uči kako pronaći put. Sljedeći put kad se izgubiš u snu, probaj potražiti baku — ona je uvijek negdje blizu.",
                "technique": "TEHNIKA KOMPASA:\n1. U snu se zaustavi.\n2. Pogledaj lijevo — tamo je kuća.\n3. Pogledaj desno — tamo je škola.\n4. Pogledaj gore — tamo je sunce.\n5. Idi prema suncu — uvijek te vodi kući.",
                "escalation": "",
            },
            {
                "type": "dark",
                "title": "Bojim se mraka",
                "grandma": "Baka ti ima tajnu: mrak nije prazan. Mrak je pun zvijezda. Samo ih ne možeš vidjeti iz sobe. Ali one su tamo — sjaje za tebe. Mrak je prijatelj koji čuva zvijezde dok spavaš.",
                "mama": "Hajde da napravimo mali ritual: prije spavanja upalimo noćnu lampicu, zagrlimo se, i kažemo 'Laku noć, mračiću — hvala što čuvaš zvijezde.' Vidiš? Mrak nije neprijatelj.",
                "explain": "Tvoje oči su navikle na svjetlo. Kad je mrak, mozak se boji jer ne vidi. Ali zapravo — u mraku tvoje oči POSTAJU JAČE. Nakon 10 minuta, počneš vidjeti obrise. Tvoje oči se treniraju. Ti postaneš JAČI u mraku, ne slabiji.",
                "technique": "RITUAL ZA MRAK:\n1. Upalite noćnu lampicu (topla žuta boja).\n2. Zajedno recite: 'Laku noć, sobe. Laku noć, igračke. Laku noć, mračiću.'\n3. Duboko udahni — zamisli da udišeš zlatnu toplinu.\n4. Izdahni — sav strah izlazi van.\n5. Sada si dio noći. Noć te čuva.",
                "escalation": "Ako strah od mraka sprječava spavanje dulje od mjesec dana, razgovarajte s pedijatrom ili dječjim psihologom. To je normalno i rješivo.",
            },
        ]
        for d in dreams:
            if dry:
                self.stdout.write(f"  [{d['type']}] {d['title']}")
                continue
            obj, new = DreamGuard.objects.using("memio_world").get_or_create(
                title=d["title"],
                defaults={
                    "dream_type": d["type"],
                    "grandma_comfort": d["grandma"],
                    "mama_comfort": d.get("mama", ""),
                    "explanation_for_child": d["explain"],
                    "calming_technique": d["technique"],
                    "escalation_note": d.get("escalation", ""),
                    "age_min": 3,
                    "age_max": 10,
                    "is_published": True,
                },
            )
            self.stdout.write(f"  [{'NEW' if new else 'EXISTS'}] {d['title']}")

    def _seed_comfort(self, dry):
        from memio_world.comfort_models import ComfortCard

        self.stdout.write(self.style.SUCCESS("\n=== KARTICE UTJEHE ==="))
        cards = [
            {
                "sit": "hurt_knee",
                "title": "Udario/la sam se!",
                "grandma": "Ajme, zlato! Daj baka puhne. Evo — fuuuu. Bolje? Znaš, baka je jednom pala s bicikla i imala ogrebotinu veću od dlana. I znaš što je napravila? Oprala vodom, stavila flaster, i nastavila voziti. Jer si hrabar/a!",
                "mama": "Pokaži mi gdje boli. Sad ćemo oprati vodom, staviti malo kreme i flaster s tvojim najdražim likom. Za 3 dana neće se ni vidjeti. Znaš li da se koža obnavlja svake 3 tjedna? Tvoje tijelo je čarobno!",
                "grandpa": "E, to je tvoj prvi ratni ožiljak! Ja imam tri. Ovaj od drveta. Ovaj od bicikla. I ovaj od bake kad me udarila kuhačom jer sam jeo tijesto prije ručka. Ožiljci su priče na koži.",
                "do": "1. Operi vodom (mlaka, ne hladna).\n2. Stavi flaster ili zavoj.\n3. Ako jako boli — reci mami ili tati.\n4. Ako krvari i ne prestaje — odmah kod odraslog!",
                "dont": "Ne liži ranu (bakterije iz usta!). Ne diraj prljavu ranu prljavim rukama.",
            },
            {
                "sit": "sad",
                "title": "Tužan/na sam i ne znam zašto",
                "grandma": "Ponekad smo tužni bez razloga. I to je u redu. Tuga je kao kiša — dođe, padne, i prođe. A nakon kiše? Duga! Hajde, sjedni k baki. Ne moraš govoriti. Samo ćemo sjediti zajedno. To je dovoljno.",
                "mama": "Hej, tu sam. Ne moraš mi objasniti. Ponekad se osjećamo tužno i ne znamo zašto — to se događa svima, i djeci i odraslima. Hoćeš zagrljaj? Hoćeš da sjednemo i gledamo u oblake?",
                "grandpa": "Znaš li da se i lav ponekad sjedi sam u savani i gleda u daljinu? Čak se i lavovi osjećaju tužno. I to ih čini JAČIMA, ne slabijima. Jer tko zna što je tuga — zna i što je sreća.",
                "do": "1. Reci nekome kako se osjećaš (mama, tata, baka, prijatelj).\n2. Zagrli nekoga.\n3. Nacrtaj kako se osjećaš — ponekad crtanje pomaže.\n4. Izađi van — sunce i svjež zrak su čarobni.",
                "dont": "Nemoj se zatvoriti u sobu i šutjeti danima. Nemoj misliti da si 'plačljivko' — osjećati tugu je HRABROST.",
                "story": "Mala Lana je jednog dana došla kući i rekla: 'Tužna sam.' Mama ju je pitala zašto. 'Ne znam,' rekla je Lana. Mama je rekla: 'Hajde da budemo tužne zajedno.' Sjele su na kauč, zagrile se, i nakon 10 minuta Lana je rekla: 'Mislim da mi je bolje.' Ponekad je sve što trebaš — netko tko sjedi s tobom.",
            },
            {
                "sit": "fight_friend",
                "title": "Posvađao/la sam se s najboljim prijateljem",
                "grandma": "Ah, baka se jednom posvađala s najboljom prijateljicom Ružom. Nisu pričale 2 tjedna. A onda je Ruža došla s kolačima i rekla: 'Glupe smo.' I obje su se nasmijale. 60 godina kasnije — još se družimo. Prave prijatelje ne gubiš zbog svađe.",
                "mama": "Svađe se događaju — čak se i mama i tata ponekad ne slažu. Važno je KAKO reagiraš poslije svađe. Napiši prijatelju poruku: 'Žao mi je. Možemo li se igrati?' To nije slabost — to je snaga.",
                "grandpa": "Dva pravila: 1) Nikad ne idi spavati ljut na prijatelja. 2) Ako si ti kriv/a — reci 'oprosti' prvi/a. Tko prvi kaže oprosti — pobijedio je.",
                "do": "1. Pričekaj da se smiriš (1 sat, ne 1 minuta).\n2. Razmisli: jesam li JA napravio/la nešto krivo?\n3. Napiši ili reci: 'Žao mi je za [ono što si napravio]. Možemo li opet biti prijatelji?'\n4. SLUŠAJ što drugi ima za reći.",
                "dont": "Nemoj ogovarati prijatelja iza leđa. Nemoj pisati ružne poruke u grupi. Nemoj umjesto razgovora — blokirati.",
            },
            {
                "sit": "lost_pet",
                "title": "Moj ljubimac je umro",
                "grandma": "Oh, zlato moje. Baka zna koliko boli. Kad je moj Floki otišao, plakala sam 3 dana. I to je u redu. Plakati za nekim koga voliš nije slabost — to je dokaz da si volio/la svim srcem. Floki je sad na livadi punoj sunca. I pamti te.",
                "mama": "Znam da boli. Tvoj ljubimac je bio dio obitelji. Imaš pravo biti tužan/na koliko god trebaš. Možemo napraviti nešto lijepo u sjećanje — nacrtati ga, napisati mu pismo, posaditi cvijet na njegovom mjestu.",
                "grandpa": "Moj prvi pas se zvao Žućo. Umro je kad sam imao 10 godina. 60 godina kasnije — još ga se sjećam. Znaš zašto? Jer ljubav ne umire. Ljubav ostaje. Tvoj ljubimac živi u tvojim sjećanjima zauvijek.",
                "do": "1. Plači ako trebaš — to je normalno i zdravo.\n2. Pričaj o svom ljubimcu — sjećanja su najljepši dar.\n3. Napravi memorial: crtež, foto album, ili posadi cvijet.\n4. Kad budeš spreman/na — možda jednog dana imaš novog prijatelja. Ne zamjenu — novog.",
                "dont": "Nemoj se sramiti suza. Nemoj govoriti 'pa samo je životinja' — za tebe je bio/la OBITELJ.",
                "story": "",
            },
            {
                "sit": "cant_sleep",
                "title": "Ne mogu zaspati",
                "grandma": "Baka ti ima trik: zamisli da brojis ovčice. Ali ne obične ovčice — svaka ima ime. Prva se zove Mila, druga Cvjetko, treća Oblačak... Dok dođeš do desete — već spavaš. Jer tvoj mozak ne može istovremeno smišljati imena I brinuti se.",
                "mama": "Hajde da napravimo rutinu: 1) Toplo mlijeko. 2) Priča (kratka!). 3) Zagrljaj. 4) Duboki udah, polako izdah. 5) Laku noć. Isto svake večeri — tvoje tijelo će naučiti da je to ZNAK za spavanje.",
                "grandpa": "",
                "do": "1. Ugasi ekrane 30 min prije kreveta (mozak treba tamu).\n2. Popij toplo mlijeko ili čaj od kamilice.\n3. Čitaj ili slušaj priču (ne gledaj video!).\n4. Tehnika 4-7-8: udahni 4 sekunde, zadrži 7, izdahni 8.",
                "dont": "Ne gledaj u ekran u krevetu. Ne jedi čokoladu navečer. Ne igraj uzbudljive igre pred spavanje.",
            },
        ]
        for c in cards:
            if dry:
                self.stdout.write(f"  [{c['sit']}] {c['title']}")
                continue
            obj, new = ComfortCard.objects.using("memio_world").get_or_create(
                title=c["title"],
                defaults={
                    "situation": c["sit"],
                    "grandma_says": c["grandma"],
                    "mama_says": c.get("mama", ""),
                    "grandpa_says": c.get("grandpa", ""),
                    "what_to_do": c["do"],
                    "what_not_to_do": c.get("dont", ""),
                    "healing_story": c.get("story", ""),
                    "age_min": 3,
                    "age_max": 12,
                    "is_published": True,
                },
            )
            self.stdout.write(f"  [{'NEW' if new else 'EXISTS'}] {c['title']}")

    def _seed_jokes(self, dry):
        from memio_world.comfort_models import JokeEntry

        self.stdout.write(self.style.SUCCESS("\n=== JOKE BOX ==="))
        jokes = [
            ("joke", "Zašto patka nosi kišobran?", "Zato što nema ruke da ga drži!", ["životinje"], 3, 10),
            ("joke", "Kako se zove pas koji zna matematiku?", "Kalkulabrador!", ["životinje", "škola"], 4, 10),
            ("joke", "Što kaže nula osmici?", "Lijepi ti pojas!", ["matematika"], 5, 10),
            (
                "joke",
                "Zašto je učitelj nosio naočale za sunce?",
                "Jer su mu učenici bili presvijetli!",
                ["škola"],
                5,
                12,
            ),
            ("joke", "Što radi mačka kad završi školu?", "Postane MAČKatorka!", ["životinje", "škola"], 4, 10),
            ("riddle", "Što ima glavu a nema tijelo?", "Čavao!", ["predmeti"], 5, 12),
            ("riddle", "Što raste a nikad se ne smanjuje?", "Dob!", ["mudrost"], 6, 12),
            (
                "riddle",
                "Imam gradove ali nema kuća, imam šume ali nema drveća, imam vode ali nema riba. Što sam?",
                "Karta (zemljovid)!",
                ["zemljopis"],
                6,
                12,
            ),
            ("riddle", "Što možeš uhvatiti ali ne baciti?", "Prehladu!", ["zdravlje"], 5, 12),
            ("riddle", "Koje slovo pije čaj?", "Slovo T!", ["škola", "jezici"], 4, 10),
            ("wordplay", "Kako se zove riba koja pjeva?", "Tuna Turner!", ["životinje", "glazba"], 6, 12),
            ("wordplay", "Što kaže more obali?", "Ništa — samo maše!", ["priroda"], 4, 10),
            ("wordplay", "Kako se zove medvjed bez uha?", "Medvjd!", ["životinje", "jezici"], 5, 10),
            (
                "knock_knock",
                "Tko je? — Banana.\nBanana tko?",
                "Tko je? — Naranča.\nNaranča tko?\nNaranča te što nisi otvorio/la Banani!",
                ["hrana"],
                3,
                8,
            ),
            ("knock_knock", "Tko je? — Baka.\nBaka tko?", "Baka ti nosi kolače — otvori vrata!", ["obitelj"], 3, 8),
            (
                "grandma_joke",
                "Djed kaže: 'Kad sam bio mali, hodao sam 10 km do škole.'",
                "Baka dodaje: 'Uzbrdo. U oba smjera. Po snijegu. Bosonog. I još sam nosio brata na leđima!'",
                ["obitelj", "škola"],
                4,
                12,
            ),
            (
                "grandma_joke",
                "Baka: 'Jesi pojeo/la sve?'\nDijete: 'Da, bako!'",
                "Baka: 'Onda ti stavljam još.' (Bakina matematika: prazni tanjur = trebas jesti jos)",
                ["obitelj", "hrana"],
                3,
                12,
            ),
            (
                "grandma_joke",
                "Djed: 'Znaš li koliko je sat?'",
                "Dijete: 'Pola pet.' Djed: 'Krivo! Vrijeme je za sladoled!'",
                ["obitelj"],
                3,
                10,
            ),
            (
                "fun_fact",
                "Puževi mogu spavati i do 3 godine.",
                "Ponedjelji su valjda i za njih teški.",
                ["životinje"],
                5,
                12,
            ),
            (
                "fun_fact",
                "Flamingosi su ružičasti jer jedu škampe.",
                "Zamislite da MI poružičavimo od pizze!",
                ["životinje", "hrana"],
                4,
                12,
            ),
            (
                "fun_fact",
                "Skupina flamingosa zove se — flamboyance!",
                "Zamislite da se skupina učenika zove — učenikovanje!",
                ["životinje", "jezici"],
                6,
                12,
            ),
            (
                "fun_fact",
                "Krava daje 200.000 čaša mlijeka u životu.",
                "To je kao da napuniš mali bazen!",
                ["životinje", "matematika"],
                5,
                12,
            ),
            (
                "tongue_twister",
                "Riba ribi grize rep.",
                "Brzo 3 puta! Riba ribi grize rep, riba ribi grize rep, riba ribi grize rep!",
                ["jezici"],
                4,
                10,
            ),
            (
                "tongue_twister",
                "Petar Petru plete petlju.",
                "Sad brže! Petarpetrupletepeeeee... gotovo!",
                ["jezici"],
                5,
                10,
            ),
            (
                "tongue_twister",
                "Četiri čavčića na čunčiću čučeći cijuču.",
                "Ako si ovo izgovorio/la bez greške — čestitamo, ti si PRVAK brzalica!",
                ["jezici"],
                6,
                12,
            ),
        ]
        for jtype, setup, punch, tags, age_min, age_max in jokes:
            if dry:
                self.stdout.write(f"  [{jtype}] {setup[:40]}")
                continue
            obj, new = JokeEntry.objects.using("memio_world").get_or_create(
                setup=setup,
                defaults={
                    "joke_type": jtype,
                    "punchline": punch,
                    "tags": tags,
                    "age_min": age_min,
                    "age_max": age_max,
                    "is_published": True,
                },
            )
            self.stdout.write(f"  [{'NEW' if new else 'EXISTS'}] {setup[:50]}")
        self.stdout.write(self.style.SUCCESS(f"  {len(jokes)} sala"))
