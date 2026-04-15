"""
Seed Kurikulum 2.0 — životne lekcije, bakine mudrosti, sigurnosne teme.
Ovo je SRCE platforme — ono po čemu roditelji rado plate.

Pokretanje:
  manage.py seed_kurikulum              # sve
  manage.py seed_kurikulum --only paths
  manage.py seed_kurikulum --only wisdom
  manage.py seed_kurikulum --only safety
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed kurikulum: paths, wisdom, safety, lessons"

    def add_arguments(self, parser):
        parser.add_argument("--only", type=str, help="paths|wisdom|safety|lessons")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        only = options.get("only")
        dry = options["dry_run"]

        if not only or only == "paths":
            self._seed_paths(dry)
        if not only or only == "wisdom":
            self._seed_wisdom(dry)
        if not only or only == "safety":
            self._seed_safety(dry)
        if not only or only == "lessons":
            self._seed_lessons(dry)

    def _seed_paths(self, dry):
        from memio_world.kurikulum_models import LearningPath

        self.stdout.write(self.style.SUCCESS("\n=== PUTOVI UCENJA ==="))
        paths = [
            # Predškolski
            ("preschool", "traffic_safety", "Sigurno na ulici", 1),
            ("preschool", "grandma_wisdom", "Bakine priče i savjeti", 2),
            ("preschool", "emotional_iq", "Osjećaji i prijateljstvo", 3),
            ("preschool", "nature", "Životinje i biljke oko nas", 4),
            ("preschool", "cultural_heritage", "Bajke naroda Europe", 5),
            # 1.-2. razred
            ("grade_1_2", "traffic_safety", "Promet: pješak i bicikl", 1),
            ("grade_1_2", "internet_safety", "Moj prvi tablet — pravila", 2),
            ("grade_1_2", "croatian", "Čitanje i pisanje — igrom", 3),
            ("grade_1_2", "math", "Brojevi oko nas", 4),
            ("grade_1_2", "grandma_wisdom", "Poslovice i životne lekcije", 5),
            ("grade_1_2", "nature", "Godišnja doba i vrijeme", 6),
            # 3.-4. razred
            ("grade_3_4", "traffic_safety", "Romobil, bicikl, pravila", 1),
            ("grade_3_4", "internet_safety", "Društvene mreže — oprez!", 2),
            ("grade_3_4", "digital_citizenship", "Digitalni građanin", 3),
            ("grade_3_4", "first_aid", "Osnove prve pomoći", 4),
            ("grade_3_4", "money_basics", "Džeparac i štednja", 5),
            ("grade_3_4", "history", "Europa kroz priče", 6),
            ("grade_3_4", "ecology", "Naš planet — naša odgovornost", 7),
            # 5.-6. razred
            ("grade_5_6", "internet_safety", "Cyberbullying i lažni profili", 1),
            ("grade_5_6", "emotional_iq", "Emocije u pubertetu", 2),
            ("grade_5_6", "digital_citizenship", "Privatnost i digitalni otisak", 3),
            ("grade_5_6", "money_basics", "Novac, rad, vrijednost", 4),
            ("grade_5_6", "cooking_basics", "Kuhaj sam/a — bakini recepti", 5),
        ]
        for age, subject, title, pos in paths:
            if dry:
                self.stdout.write(f"  [{age}] {title}")
                continue
            obj, created = LearningPath.objects.using("memio_world").get_or_create(
                age_group=age,
                subject=subject,
                defaults={"title": title, "position": pos, "is_published": True},
            )
            status = "NEW" if created else "EXISTS"
            self.stdout.write(f"  [{status}] {title}")
        self.stdout.write(self.style.SUCCESS(f"  {len(paths)} putova"))

    def _seed_wisdom(self, dry):
        from memio_world.kurikulum_models import WisdomEntry

        self.stdout.write(self.style.SUCCESS("\n=== BAKINA MUDROST ==="))
        wisdoms = [
            {
                "category": "safety",
                "title": "Nikad ne idi s nepoznatima",
                "grandma": "Zlato moje, baka ti uvijek kaže — ako te netko nepoznat zove, ti okreni leđa i trči kući. Nije važno što ti nudi — čokoladu, igračku, psića. Ti znaš tko su tvoji ljudi. Ostali su — ostali.",
                "grandpa": "Slušaj, mali. U moje vrijeme smo trčali po polju cijeli dan. Ali jedno pravilo je bilo sveto: ne ideš nigdje s nekim koga ne poznaje ni mama ni tata. Točka.",
                "agree": True,
                "modern": "Danas ovo vrijedi i ONLINE. Ako ti netko nepoznat piše poruke, traži slike, ili te zove da se nađete — to je isti opasan stranac, samo u digitalnom ruhu.",
                "story": "Bakina susjeda Marija je kao djevojčica jednom krenula s nekim čovjekom koji joj je rekao da joj je tata bolestan. Srećom, poštarica ju je vidjela i zaustavila. Tata je bio zdrav kod kuće.",
                "age_min": 3,
                "age_max": 12,
            },
            {
                "category": "safety",
                "title": "STOP znači STANI — uvijek i svugdje",
                "grandma": "Kad vidiš crveno — stani. To je kao kad mama kaže 'dosta'. Crveno je boja koja te čuva.",
                "grandpa": "Ja sam se jednom zamalo nije zaletio na traktor jer nisam gledao znak. Od tog dana — svaki STOP je sveti. Gledaj, stani, pa tek onda idi.",
                "agree": True,
                "modern": "STOP ne vrijedi samo na cesti. STOP vrijedi i kad ti tijelo kaže da nešto nije u redu, kad ti se neka igra ne sviđa, kad ti netko čini nešto neugodno. Imaš pravo reći STOP.",
                "story": "",
                "age_min": 3,
                "age_max": 10,
            },
            {
                "category": "health",
                "title": "Jedi ono što raste iz zemlje",
                "grandma": "Moja mama mi je uvijek govorila: 'Ako ne možeš izgovoriti što piše na pakiranju — nemoj to jesti.' Jabuka, kruška, mrkva — to su prava jela. Čips i gumene bombone? To je za ponekad, ne za svaki dan.",
                "grandpa": "U moje vrijeme nije bilo fastfooda. Jeli smo kruh, sir, rajčicu, luk. I bili smo zdraviji nego današnja djeca. Ne kažem da ne smiješ čokoladu — ali prvo pojedi ručak!",
                "agree": True,
                "modern": "Danas znamo da pretjerano procesirana hrana može utjecati čak i na raspoloženje i koncentraciju. Baka je bila u pravu i bez laboratorija.",
                "story": "Djed je imao 92 godine i još je kopao vrt. Kad su ga pitali koja mu je tajna, rekao je: 'Nikad nisam jeo ništa što moja baka ne bi prepoznala kao hranu.'",
                "age_min": 4,
                "age_max": 14,
            },
            {
                "category": "manners",
                "title": "Dobar dan, hvala, molim — tri čarobne riječi",
                "grandma": "Tri najvažnije riječi na svijetu nisu 'volim te' — nego 'molim', 'hvala' i 'dobar dan'. S te tri riječi možeš otvoriti svaka vrata.",
                "grandpa": "Kad sam bio mali, nije me nitko pitao hoću li reći dobar dan. Ušao si u sobu — rekao si dobar dan. Dobio si nešto — rekao si hvala. Trebao si nešto — rekao si molim. Bez diskusije.",
                "agree": True,
                "modern": "I danas, u dobu emoji-ja i glasovnih poruka, ljudi koji kažu 'hvala' i 'molim' ostavljaju bolji dojam. To vrijedi i online — napišeš li 'hvala' u chatu, ljudi te bolje pamte.",
                "story": "",
                "age_min": 3,
                "age_max": 10,
            },
            {
                "category": "patience",
                "title": "Strpljenje je gorko, ali njegov plod je sladak",
                "grandma": "Kad sam sadila rajčice, morala sam čekati tri mjeseca da dozriju. Mogla sam ih ubrati zelene — ali ne bi bile slatke. Tako je i s tobom, zlato. Ne žuri. Dobre stvari dolaze onima koji čekaju.",
                "grandpa": "Ja nisam strpljiv čovjek. Ali naučio sam jedno: kad žuriš, griješiš. Kad sam žurio popraviti krov, pao sam s ljestvi. Da sam čekao pomoć — ne bi imao ožiljak na koljenu.",
                "agree": False,
                "modern": "U digitalnom svijetu sve je odmah: klik, like, stream. Ali prave vještine — sviranje, crtanje, sport, kuhanje — zahtijevaju tjedne i mjesece vježbe. Nema prečaca.",
                "story": "Baka i djed se ovdje NE slažu — baka kaže strpljenje uvijek, djed kaže ponekad moraš djelovati brzo. I OBOJE IMAJU PRAVO. To je lekcija sama za sebe.",
                "age_min": 5,
                "age_max": 14,
            },
            {
                "category": "friendship",
                "title": "Pravi prijatelj se vidi u nevolji",
                "grandma": "Kad ti je lijepo — svi su tu. Ali kad ti je teško, kad si bolestan, kad padneš na ispitu, kad te netko zadirkuje — pogledaj tko je ostao. To su tvoji pravi prijatelji.",
                "grandpa": "Ja imam jednog prijatelja iz djetinjstva. Jednog. Ali kad sam bio u bolnici, on je došao svaki dan. To vrijedi više od stotinu 'frendova' na internetu.",
                "agree": True,
                "modern": "500 followera na TikToku nije isto što i 1 prijatelj koji te nazove kad si tužan. Broji prijatelje po kvaliteti, ne po količini.",
                "story": "",
                "age_min": 5,
                "age_max": 14,
            },
            {
                "category": "digital",
                "title": "Ekran nije stvarni život",
                "grandma": "Ja ne razumijem te vaše telefone, ali znam jedno: ništa na tom ekranu te neće zagrliti kad ti je teško. Ostavi telefon i idi van — sunce, trava, vjetar — to je pravi život.",
                "grandpa": "Računala su korisna, neću lagati. Ali kad vidim dijete koje ne zna zavezati cipelu jer gleda u ekran — nešto nije u redu. Najprije nauči živjeti u stvarnom svijetu, pa tek onda u digitalnom.",
                "agree": True,
                "modern": "Istraživanja pokazuju da djeca koja provode manje od 2 sata dnevno na ekranima imaju bolji san, bolje ocjene i više prijatelja. Ekran je alat, ne život.",
                "story": "Jedan dječak je imao 10.000 followera, ali na svoj rođendan nitko nije došao. Sljedeće godine je pozvao samo 5 pravih prijatelja — i bio je najsretniji dan u životu.",
                "age_min": 5,
                "age_max": 14,
            },
            {
                "category": "money",
                "title": "Novac se ne raste na drveću",
                "grandma": "Svaki put kad mama ili tata kupe nešto — morali su za to raditi. Možda sat, možda dan, možda tjedan. Kad to razumiješ, nećeš tražiti igračku u svakom dućanu.",
                "grandpa": "Moj djed mi je dao prvu plaću za čišćenje štale — 5 kuna. Kupio sam sladoled i čokoladu. Do navečer je nestalo. Tada sam naučio: trošiti je lako, zaraditi je teško.",
                "agree": True,
                "modern": "In-app kupnje u igrama su dizajnirane da ti uzmu novac bez da osjećaš koliko trošiš. 'Samo 0.99€' × 50 puta = 50€. To je tjedan dana džeparca!",
                "story": "",
                "age_min": 6,
                "age_max": 14,
            },
            {
                "category": "proverb",
                "title": "Tko rano rani, dvije sreće grabi",
                "grandma": "Jutro je najljepši dio dana. Tiho je, ptice pjevaju, zrak je svjež. Kad ustaneš rano, imaš vremena za doručak, za igru, za sve. Kad kasniš — juriš, nervozan si, zaboravljaš stvari.",
                "grandpa": "U vojsci sam naučio: tko je prvi ustao, prvi je jeo. Tko je zadnji — jeo je hladnu kašu. Život je isti.",
                "agree": True,
                "modern": "Studije pokazuju da 'rani ptičevi' imaju bolje ocjene i manje stresa. Ali — svi smo različiti. Ako si noćna ptica, nađi svoj ritam. Bitno je imati rutinu.",
                "story": "",
                "age_min": 5,
                "age_max": 12,
            },
            {
                "category": "courage",
                "title": "Hrabrost nije kad te nije strah — hrabrost je kad te JE strah pa ipak učiniš pravu stvar",
                "grandma": "Meni su rekli da žene ne idu na fakultet. Bilo me strah. Ali sam otišla. I završila. I postala učiteljica. Strah je normalan — bježanje od straha nije.",
                "grandpa": "Jednom sam kao dijete vidio kako stariji dječak tuče mlađeg. Bio sam manji od obojice. Ali sam vikao tako glasno da je cijeli kvart čuo. Tukac je pobjegao. Nisam bio jak — bio sam glasan.",
                "agree": True,
                "modern": "Danas hrabrost znači i: prijaviti cyberbullying, reći učitelju kad netko vara, stati uz prijatelja kad ga ismijavaju. Ne moraš biti fizički jak — moraš biti moralno jak.",
                "story": "",
                "age_min": 5,
                "age_max": 14,
            },
        ]
        for w in wisdoms:
            if dry:
                self.stdout.write(f"  [{w['category']}] {w['title']}")
                continue
            obj, created = WisdomEntry.objects.using("memio_world").get_or_create(
                title=w["title"],
                defaults={
                    "category": w["category"],
                    "grandma_version": w["grandma"],
                    "grandpa_version": w["grandpa"],
                    "they_agree": w["agree"],
                    "modern_context": w["modern"],
                    "life_story": w.get("story", ""),
                    "age_min": w["age_min"],
                    "age_max": w["age_max"],
                    "is_published": True,
                },
            )
            self.stdout.write(f"  [{'NEW' if created else 'EXISTS'}] {w['title'][:60]}")
        self.stdout.write(self.style.SUCCESS(f"  {len(wisdoms)} mudrosti"))

    def _seed_safety(self, dry):
        from memio_world.kurikulum_models import SafetyTopic

        self.stdout.write(self.style.SUCCESS("\n=== SIGURNOSNE TEME ==="))
        topics = [
            # PROMET — PJEŠACI
            {
                "cat": "traffic_pedestrian",
                "sev": 3,
                "title": "Prelazak ceste — STANI, GLEDAJ, SLUŠAJ, IDI",
                "scenario": "Stojis na zebri. Semafor je zelen za pješake. Ali auto dolazi brzo s lijeve strane.",
                "correct": "STANI na rubu. GLEDAJ lijevo-desno-lijevo. SLUŠAJ dolazi li auto. Tek kad si SIGURAN — IDI. Čak i kad je zeleno!",
                "wrong": "Pretrčati jer je zeleno, gledati u mobitel dok prelaziš, istrčati za loptom na cestu.",
                "who": "Roditelj, policija (192), hitna (194)",
                "grandma": "Moja susjeda je izgubila mačku jer je istrčala na cestu. Životinje ne znaju pravila. Ali TI znaš. I zato si pametniji od mačke.",
                "grandpa": "Jedan pogled lijevo-desno traje 3 sekunde. Auto koji vozi 50 km/h u 3 sekunde prijeđe 42 metra. Te 3 sekunde ti mogu spasiti život.",
                "age_min": 3,
                "age_max": 10,
            },
            # PROMET — BICIKL
            {
                "cat": "traffic_bicycle",
                "sev": 3,
                "title": "Bicikl: kaciga UVIJEK, cestu NIKAD bez dozvole",
                "scenario": "Voziš bicikl s prijateljem. On ne nosi kacigu i vozi po cesti. Kaže ti: 'Ma ne treba kaciga, to je za male!'",
                "correct": "Kaciga UVIJEK — i za velike i za male. Na cestu s biciklom tek od 10. godine, i to s položenim ispitom. Do tada — nogostup i biciklističke staze.",
                "wrong": "Skinuti kacigu jer te prijatelj ismijavao. Voziti po cesti s 7 godina. Voziti u mraku bez svjetla.",
                "who": "Roditelj. Ako padneš: hitna 194.",
                "grandma": "Tvoj tata je jednom pao s bicikla bez kacige. Imao je 12 šavova na čelu. Od tada SVIH petero djece nosi kacigu. Čak i ja kad se vozim na triciklu!",
                "grandpa": "Kaciga košta 30 eura. Operacija glave košta 30.000. Matematika je jasna.",
                "age_min": 5,
                "age_max": 12,
            },
            # PROMET — ROMOBIL
            {
                "cat": "traffic_scooter",
                "sev": 2,
                "title": "Romobil: zabavno, ali OPASNO ako ne paziš",
                "scenario": "Dobiješ električni romobil za rođendan. Prijatelji voze po cesti i između auta.",
                "correct": "Električni romobil: kaciga obavezna, samo na biciklističkim stazama i pješačkim zonama. NIKAD na cesti s autima. Brzina max 25 km/h — to je brže nego misliš!",
                "wrong": "Voziti bez kacige jer 'nije daleko'. Voziti dva na jednom romobilu. Slušati muziku sa slušalicama dok voziš.",
                "who": "Roditelj. Policija (192) za prijavu nesreće.",
                "grandma": "U moje vrijeme smo se vozili na daski s kotačima. Pali smo, ogulili koljena, i naučili. Ali nismo se vozili 25 na sat!",
                "grandpa": "Električni romobil može ubrzati brže od auta u gradu. Mozak djeteta ne može reagirati tako brzo. KACIGA.",
                "age_min": 6,
                "age_max": 14,
            },
            # PROMETNI ZNAKOVI
            {
                "cat": "traffic_signs",
                "sev": 2,
                "title": "Prometni znakovi — crveni, žuti, plavi — što znače?",
                "scenario": "Ideš s roditeljima u šetnju. Posvuda su znakovi. Što znače?",
                "correct": "CRVENI krug = ZABRANA (ne smiješ). CRVENI trokut = OPREZ (pazi). PLAVI krug = OBAVEZA (moraš). PLAVI kvadrat = INFORMACIJA (tu je nešto korisno). Nauči barem 10 najvažnijih!",
                "wrong": "Ignorirati znakove jer 'to je za aute'. Znakovi su i za pješake i bicikliste!",
                "who": "",
                "grandma": "Znakovi su kao govor bez riječi. Kao kad mama podigne obrvu — znaš da si nešto krivo napravio. Cesta ima svoj 'pogled' — nauči ga čitati.",
                "grandpa": "U autoškoli sam pao ispit jer nisam znao razliku između trokuta i kruga. S 18 godina! Da sam naučio s 6 — ne bi pao.",
                "age_min": 4,
                "age_max": 12,
            },
            # INTERNET — NEPOZNATI
            {
                "cat": "internet_strangers",
                "sev": 3,
                "title": "Netko nepoznat mi piše online — što učiniti?",
                "scenario": "U igrici ti se javi netko tko kaže da ima 12 godina. Traži tvoju sliku, ime škole, i broj mobitela.",
                "correct": "NIKAD ne daj osobne podatke (ime, školu, adresu, broj) nikome online koga ne poznaješ IRL (in real life). Odmah reci roditelju. Blokiraj osobu. Napravi screenshot.",
                "wrong": "Dati podatke jer 'izgleda normalno'. Nastaviti razgovor jer 'zabavno je'. Ne reći roditelju jer 'nije ništa strašno'.",
                "who": "ODMAH roditelj. Policija (192) ako je prijetnja.",
                "grandma": "Kad je baka bila mala, nepoznati čovjek je mogao pokucati na vrata. Danas nepoznati ljudi kucaju na tvoj ekran. Ista opasnost — drugačija vrata.",
                "grandpa": "Nitko od 12 godina ne traži tvoju adresu. NITKO. Ako to radi — nije dijete.",
                "age_min": 6,
                "age_max": 14,
            },
            # INTERNET — CYBERBULLYING
            {
                "cat": "internet_cyberbully",
                "sev": 3,
                "title": "Netko me ismijava online — cyberbullying",
                "scenario": "Na grupnom chatu razreda netko objavi ružnu sliku tebe i svi se smiju. Osjećaš se užasno.",
                "correct": "1) Nije tvoja krivnja. 2) Napravi screenshot. 3) Reci roditelju ili učitelju ODMAH. 4) Nemoj odgovarati — to je ono što bully želi. 5) Blokiraj osobu.",
                "wrong": "Odgovarati istom mjerom (i ti ćeš biti bully). Šutjeti mjesecima jer 'ne želiš biti tužibaba'. Brisati dokaze.",
                "who": "Roditelj, učitelj, školski pedagog. Policija ako je prijetnja.",
                "grandma": "U moje vrijeme su zadirkivali na školskom dvorištu. Bilo je ružno, ali je trajalo do kraja škole. Danas to traje 24 sata — i to je GORE. Zato MORAŠ reći nekome.",
                "grandpa": "Tužibaba? Ne. Tražiti pomoć kad ti netko čini nažao je HRABROST, ne slabost. Slabost je šutjeti.",
                "age_min": 7,
                "age_max": 14,
            },
            # INTERNET — PRETJERANO KORISTENJE
            {
                "cat": "internet_screens",
                "sev": 2,
                "title": "Koliko je previše ekrana?",
                "scenario": "Svaki dan gledaš YouTube 3 sata. Roditelji kažu da je previše. Ti misliš da nije.",
                "correct": "Za djecu 6-12 god: max 1-2 sata ekrana dnevno (uključujući igre, YouTube, TikTok). ISKLJUČI: zadaću na kompjuteru — to se ne računa u zabavu. UKLJUČI: pauze svakih 30 min.",
                "wrong": "Gledati dok ne zaspiš. Gledati za vrijeme jela. Gledati umjesto igranja vani.",
                "who": "Roditelj (dogovorite pravila ZAJEDNO — ne samo zabrana).",
                "grandma": "Mi smo imali jedan TV u kući. Gledali smo ga sat dnevno. Ostatak dana smo trčali vani, čitali, pomagali u kuhinji. I bili smo — sretni.",
                "grandpa": "Ekran je alat. Čekić je koristan za zabijanje čavala. Ali ako cijeli dan držiš čekić — nećeš zabiti čavao, nego ćeš razbiti prst.",
                "age_min": 5,
                "age_max": 14,
            },
            # NEPOZNATI U STVARNOM SVIJETU
            {
                "cat": "stranger_danger",
                "sev": 3,
                "title": "Nepoznati čovjek ti nudi slatkiše — BJEŽI I VIČI",
                "scenario": "Na putu iz škole, nepoznati čovjek te zove iz auta i kaže da te mama poslala po tebe.",
                "correct": "1) NE prilazi autu. 2) BJEŽI u suprotnom smjeru od auta. 3) VIČI glasno 'POMOĆ!' 4) Uđi u najbliži dućan/kuću. 5) Reci odrasloj osobi. 6) MAMA NIKAD NE BI POSLALA NEPOZNATOG PO TEBE.",
                "wrong": "Ući u auto jer 'izgleda normalno'. Uzeti slatkiš jer 'ne mora ući u auto'. Šutjeti jer 'nije se ništa dogodilo'.",
                "who": "ODMAH: najbliži odrasli, policija 192, roditelj.",
                "grandma": "Mama i tata ti nikad neće poslati nepoznatog čovjeka. NIKAD. Ako ti netko to kaže — laže. Zapamti ovu rečenicu zauvijek.",
                "grandpa": "Kad sam bio mali, imali smo lozinku u obitelji. Ako je netko rekao 'mama me poslala' — morao je znati lozinku. Ako ne zna — bježi. Napravite i vi obiteljsku lozinku!",
                "age_min": 3,
                "age_max": 12,
            },
            # POŽAR
            {
                "cat": "fire_safety",
                "sev": 3,
                "title": "Požar! Što raditi — 3 koraka",
                "scenario": "U kuhinji nešto gori. Dima ima sve više.",
                "correct": "1) NE gasiš sam — IZLAZI van! 2) Pozovi 193 (vatrogasci). 3) Ako ima dima — spusti se nisko i puzi (dim ide gore, svjež zrak je dolje). Kad si vani — čekaj vatrogasce.",
                "wrong": "Pokušati sam gasiti vatru. Sakriti se u ormar (vatrogasci te neće naći!). Trčati po stubama kad ima dima.",
                "who": "Vatrogasci 193. Hitna 194. Policija 192. Ili europski 112.",
                "grandma": "Vatra je sluga, ali loš gospodar. U kući se ne igra s vatrom, šibicama, upaljačima. NIKAD.",
                "grandpa": "Zapamti 3 broja: 192, 193, 194. Policija, vatrogasci, hitna. Ili — 112 za sve.",
                "age_min": 4,
                "age_max": 14,
            },
        ]
        for t in topics:
            if dry:
                self.stdout.write(f"  [{t['cat']}] {t['title'][:60]}")
                continue
            obj, created = SafetyTopic.objects.using("memio_world").get_or_create(
                title=t["title"],
                defaults={
                    "danger_category": t["cat"],
                    "severity": t["sev"],
                    "scenario": t["scenario"],
                    "correct_action": t["correct"],
                    "wrong_action": t["wrong"],
                    "who_to_call": t.get("who", ""),
                    "grandma_advice": t.get("grandma", ""),
                    "grandpa_advice": t.get("grandpa", ""),
                    "age_min": t["age_min"],
                    "age_max": t["age_max"],
                    "is_published": True,
                },
            )
            self.stdout.write(f"  [{'NEW' if created else 'EXISTS'}] {t['title'][:60]}")
        self.stdout.write(self.style.SUCCESS(f"  {len(topics)} tema"))

    def _seed_lessons(self, dry):
        self.stdout.write(self.style.SUCCESS("\n=== LEKCIJE ==="))
        self.stdout.write("  Lekcije se generiraju iz wisdom + safety podataka (Faza D.2)")
