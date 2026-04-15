"""Seed Rage Engine: 6 calming exercises + 3 anger stories + 3 conflict scenarios."""

from django.core.management.base import BaseCommand

DB = "memio_world"


class Command(BaseCommand):
    help = "Seed Rage Engine content"

    def handle(self, *args, **options):
        self._seed_exercises()
        self._seed_stories()
        self._seed_conflicts()

    def _seed_exercises(self):
        from memio_world.comfort_models import CalmingExercise

        exercises = [
            {
                "technique": "breathing",
                "title": "Duboko disanje",
                "title_de": "Tiefes Atmen",
                "title_en": "Deep Breathing",
                "instruction_text": "Stavi ruke na trbuh.\nUdahni duboko kroz nos — 1, 2, 3, 4.\nOsjeti kako ti se trbuh diže.\nZadrži dah — 1, 2.\nIzdahni polako kroz usta — 1, 2, 3, 4.\nOsjeti kako ti se trbuh spušta.\nPonovimo još jednom.",
                "instruction_text_de": "Lege deine Hände auf den Bauch.\nAtme tief durch die Nase ein — 1, 2, 3, 4.\nSpüre, wie sich dein Bauch hebt.\nHalte die Luft an — 1, 2.\nAtme langsam durch den Mund aus — 1, 2, 3, 4.\nSpüre, wie sich dein Bauch senkt.\nNoch einmal.",
                "instruction_text_en": "Put your hands on your belly.\nBreathe in deeply through your nose — 1, 2, 3, 4.\nFeel your belly rise.\nHold — 1, 2.\nBreathe out slowly through your mouth — 1, 2, 3, 4.\nFeel your belly fall.\nLet's do it again.",
                "grandma_voice": "Dušo, dišemo zajedno. Polako. Nema žurbe. Udahni... i sad lagano van. Vidiš, već je bolje. Bijes je kao oblak — dolazi i odlazi. Ti si jača od oblaka.",
                "grandma_voice_de": "Schatz, wir atmen zusammen. Langsam. Keine Eile. Einatmen... und jetzt langsam aus. Siehst du, es ist schon besser. Wut ist wie eine Wolke — sie kommt und geht.",
                "grandma_voice_en": "Sweetheart, let's breathe together. Slowly. No rush. Breathe in... and now gently out. See, it's already better. Anger is like a cloud — it comes and goes.",
                "duration_seconds": 60,
                "animation_data": {
                    "type": "balloon",
                    "inhale_sec": 4,
                    "exhale_sec": 4,
                    "hold_sec": 2,
                    "cycles": 5,
                    "color": "#87CEEB",
                },
                "emoji": "🎈",
                "age_min": 3,
                "sort_order": 1,
            },
            {
                "technique": "counting",
                "title": "Brojanje unatrag",
                "title_de": "Rückwärts zählen",
                "title_en": "Counting Backwards",
                "instruction_text": "Zatvori oči.\nBrojimo od 10 do 0.\nPolako. Svaki broj = jedan udah.\n10... 9... 8... 7... 6... 5... 4... 3... 2... 1... 0.\nOtvori oči. Kako se osjećaš?",
                "grandma_voice": "Kad sam ja bila mala, baka me naučila: kad te nešto ljuti, broji. Dok dođeš do nule, bijes se umanji. Uvijek se umanji.",
                "duration_seconds": 30,
                "animation_data": {"type": "countdown", "from": 10, "interval_sec": 3},
                "emoji": "🔢",
                "age_min": 4,
                "sort_order": 2,
            },
            {
                "technique": "volcano",
                "title": "Vulkan vježba",
                "title_de": "Vulkan-Übung",
                "title_en": "Volcano Exercise",
                "instruction_text": "Zamisli vulkan u svom trbuhu.\nLava se diže — to je tvoj bijes.\nAli ti MOŽEŠ ohladiti lavu!\nStavi ruke na trbuh.\nUdahni hladan zrak — lava se hladi.\nIzdahni toplo — para izlazi.\nSvaki put kad udahneš, lava je sve hladnija.\nDok na kraju nestane.",
                "grandma_voice": "Bijes je kao vatra. Nije loš — vatra grije, ali može i spaliti. Ti odlučuješ. Hladi ga polako. Ti si gazda.",
                "duration_seconds": 45,
                "animation_data": {"type": "volcano", "cool_steps": 5, "step_sec": 3},
                "emoji": "🌋",
                "age_min": 5,
                "sort_order": 3,
            },
            {
                "technique": "jellyfish",
                "title": "Meduza plutanje",
                "title_de": "Quallen-Schweben",
                "title_en": "Jellyfish Float",
                "instruction_text": "Zamisli da si meduza u toplom moru.\nTvoje ruke su mekane. Pusti ih da vise.\nTvoje noge su mekane. Opusti ih.\nTvoja glava je lagana. Nagne se malo.\nPlutaš. Nema ničeg što te drži.\nVal te nosi lijevo... desno...\nDišeš s morem. Unutra... van...",
                "grandma_voice": "Kad plutaš, sve teško potone na dno. Pusti da potone. Ti ostani gore. Lako. Nježno.",
                "duration_seconds": 60,
                "animation_data": {"type": "breathing", "inhale_sec": 5, "exhale_sec": 5, "cycles": 4},
                "emoji": "🪼",
                "age_min": 4,
                "sort_order": 4,
            },
            {
                "technique": "turtle",
                "title": "Kornjačina ljuska",
                "title_de": "Schildkrötenpanzer",
                "title_en": "Turtle Shell",
                "instruction_text": "Kad si ljut, budi kao kornjača.\nUvuci se u svoju ljusku:\nPodigni ramena do ušiju.\nSpusti bradu na prsa.\nZagrli se rukama.\nSad si siguran u ljusci.\nDiši polako.\nKad budeš spreman, polako izađi.\nSporije nego što misliš. Još sporije.",
                "grandma_voice": "Kornjača nije kukavica. Kornjača je MUDRA. Zna kad treba stati i odahnuti. Ti si moja mudra kornjačica.",
                "duration_seconds": 40,
                "animation_data": {"type": "steps", "step_sec": 4},
                "emoji": "🐢",
                "age_min": 3,
                "sort_order": 5,
            },
            {
                "technique": "traffic_light",
                "title": "Semafor",
                "title_de": "Ampel",
                "title_en": "Traffic Light",
                "instruction_text": "🔴 CRVENO — STOJ! Ne radi ništa. Stani.\n🟡 ŽUTO — DIŠI! Tri duboka udaha.\n🟢 ZELENO — RAZMISLI! Što mogu napraviti? Kažem, ne vičem.",
                "grandma_voice": "Znaš semafor na cesti? Isti vrijedi i za osjećaje. Kad je crveno — stanemo. Samo stanemo. Onda dišemo. I onda razmislimo. Uvijek tim redom.",
                "duration_seconds": 30,
                "animation_data": {"type": "steps", "step_sec": 5},
                "emoji": "🚦",
                "age_min": 3,
                "sort_order": 6,
            },
        ]

        created = 0
        for ex_data in exercises:
            _, was_created = CalmingExercise.objects.using(DB).update_or_create(
                technique=ex_data.pop("technique"),
                defaults={**ex_data, "is_published": True},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"CalmingExercise: {created} created"))

    def _seed_stories(self):
        from memio_world.play_eu_models import ParallelStory

        stories = [
            {
                "slug": "zmaj-koji-je-naucio-disati",
                "title_hr": "Zmaj koji je naučio disati",
                "title_de": "Der Drache, der atmen lernte",
                "title_en": "The Dragon Who Learned to Breathe",
                "story_type": "fairy_tale",
                "source": "original",
                "license": "CC-BY-4.0 PLAY.EU",
                "country_of_origin": "Hrvatska",
                "age_min": 3,
                "age_max": 7,
                "reading_time_minutes": 5,
                "moral_lesson": "Bijes je vatra — ali ti biraš kad ćeš je pustiti. Disanje je tvoja super-moć.",
                "text_hr": """Visoko na planini živio je mali zmaj po imenu Žar.

Žar je bio lijep zmaj — zelene ljuske, zlatni rogovi, i oči boje meda. Ali Žar je imao jedan problem.

Svaki put kad bi se naljutio — a ljutio se ČESTO — iz njegovih usta bi izletjela vatra.

Jednog jutra, dok je Žar čekao u redu za voće, mala vjeverica mu je ukrala lješnjak. "HEJ!" — viknuo je Žar, i iz njegovih usta izletio je plamen.

Plamen je spalio vjeveričin rep. Vjeverica je plakala. Žar je plakao još jače. Nije htio nikoga povrijediti. Ali vatra je bila brža od njegovih misli.

Sutradan je Žar otišao do Mudre Sove koja je živjela u šupljini starog hrasta.

"Sovo, ja ne mogu prestati bljuvati vatru kad sam ljut. Što da radim?"

Sova ga je pogledala dugim, mudrim pogledom i rekla: "Žare, vatru ne možeš ugasiti. Ali možeš naučiti DISATI prije nego je pustiš."

"Disati? Ali ja uvijek dišem!"

"Ne TAKO disati," rekla je Sova. "Ovako: kad osjetiš da ti vatra raste u trbuhu — STANI. Stavi šape na trbuh. I diši polako. Unutra... 1, 2, 3, 4. Van... 1, 2, 3, 4."

Žar je probao. Udahnuo je hladan planinski zrak. Osjetio je kako se vatra u trbuhu smanjuje. Polako, polako, vatra se pretvorila u toplinu. Ugodnu toplinu.

"Vidiš?" rekla je Sova. "Vatra ne nestaje. Ali postaje TOPLINA. A toplina je dobra. Toplina grije, ne pali."

Od tog dana, Žar je vježbao svaki dan. Kad bi se naljutio — a ljutio se i dalje, jer to je normalno — stavio bi šape na trbuh i disao.

Ponekad mu je trebao jedan udah. Ponekad pet. Jednom mu je trebalo deset. Ali UVIJEK je pomoglo.

I znate što? Žarovi prijatelji su primijetili promjenu. Više ih nije bilo strah. Počeli su se opet igrati s njim.

A vjeverici? Vjeverici je rep opet narastao. I sad se smije kad vidi Žara kako diše s zatvorenim očima.

"Opet vježba," kaže vjeverica. "Moj mali zmaj koji diše umjesto da pali."

I živjeli su sretno. Ne savršeno — jer savršeno ne postoji. Ali sretno. A to je sasvim dovoljno.""",
                "text_de": """Hoch oben auf einem Berg lebte ein kleiner Drache namens Glut.

Glut war ein schöner Drache — grüne Schuppen, goldene Hörner und honigfarbene Augen. Aber Glut hatte ein Problem.

Jedes Mal, wenn er wütend wurde — und das geschah OFT — schoss Feuer aus seinem Mund.

Eines Morgens, als Glut in der Schlange für Obst wartete, stahl ihm ein kleines Eichhörnchen eine Haselnuss. "HEY!" — schrie Glut, und Flammen schossen aus seinem Mund.

Die Flamme versengte den Schwanz des Eichhörnchens. Das Eichhörnchen weinte. Glut weinte noch mehr. Er wollte niemandem wehtun. Aber das Feuer war schneller als seine Gedanken.

Am nächsten Tag ging Glut zur Weisen Eule, die in der Höhle einer alten Eiche lebte.

"Eule, ich kann nicht aufhören, Feuer zu spucken, wenn ich wütend bin. Was soll ich tun?"

Die Eule sah ihn mit einem langen, weisen Blick an und sagte: "Glut, du kannst das Feuer nicht löschen. Aber du kannst lernen zu ATMEN, bevor du es loslässt."

"Atmen? Aber ich atme doch immer!"

"Nicht SO atmen," sagte die Eule. "So: Wenn du spürst, dass das Feuer in deinem Bauch wächst — STOPP. Lege deine Pfoten auf den Bauch. Und atme langsam. Ein... 1, 2, 3, 4. Aus... 1, 2, 3, 4."

Glut probierte es. Er atmete kühle Bergluft ein. Er spürte, wie das Feuer in seinem Bauch kleiner wurde. Langsam, langsam verwandelte sich das Feuer in Wärme. Angenehme Wärme.

"Siehst du?" sagte die Eule. "Das Feuer verschwindet nicht. Aber es wird zu WÄRME. Und Wärme ist gut. Wärme wärmt, sie verbrennt nicht."

Von diesem Tag an übte Glut jeden Tag. Wenn er wütend wurde — und das wurde er immer noch, denn das ist normal — legte er seine Pfoten auf den Bauch und atmete.

Manchmal brauchte er einen Atemzug. Manchmal fünf. Einmal brauchte er zehn. Aber es half IMMER.

Und wisst ihr was? Gluts Freunde bemerkten die Veränderung. Sie hatten keine Angst mehr. Sie fingen wieder an, mit ihm zu spielen.

Und das Eichhörnchen? Dem Eichhörnchen wuchs der Schwanz wieder nach. Und jetzt lacht es, wenn es Glut mit geschlossenen Augen atmen sieht.

"Er übt wieder," sagt das Eichhörnchen. "Mein kleiner Drache, der atmet statt zu brennen."

Und sie lebten glücklich. Nicht perfekt — denn perfekt gibt es nicht. Aber glücklich. Und das ist genug.""",
                "text_en": """High on a mountain, there lived a small dragon named Ember.

Ember was a beautiful dragon — green scales, golden horns, and honey-colored eyes. But Ember had one problem.

Every time he got angry — and he got angry OFTEN — fire would shoot from his mouth.

One morning, while Ember was waiting in line for fruit, a little squirrel stole his hazelnut. "HEY!" — Ember shouted, and flames burst from his mouth.

The flame singed the squirrel's tail. The squirrel cried. Ember cried even harder. He didn't want to hurt anyone. But the fire was faster than his thoughts.

The next day, Ember went to the Wise Owl who lived in the hollow of an old oak tree.

"Owl, I can't stop breathing fire when I'm angry. What should I do?"

The Owl looked at him with a long, wise gaze and said: "Ember, you can't put out the fire. But you can learn to BREATHE before you let it out."

"Breathe? But I always breathe!"

"Not THAT kind of breathing," said the Owl. "Like this: when you feel the fire growing in your belly — STOP. Put your paws on your belly. And breathe slowly. In... 1, 2, 3, 4. Out... 1, 2, 3, 4."

Ember tried. He breathed in cool mountain air. He felt the fire in his belly shrinking. Slowly, slowly, the fire turned into warmth. Pleasant warmth.

"See?" said the Owl. "The fire doesn't disappear. But it becomes WARMTH. And warmth is good. Warmth warms, it doesn't burn."

From that day on, Ember practiced every day. When he got angry — and he still did, because that's normal — he put his paws on his belly and breathed.

Sometimes he needed one breath. Sometimes five. Once he needed ten. But it ALWAYS helped.

And you know what? Ember's friends noticed the change. They weren't afraid anymore. They started playing with him again.

And the squirrel? The squirrel's tail grew back. And now she laughs when she sees Ember breathing with his eyes closed.

"He's practicing again," says the squirrel. "My little dragon who breathes instead of burning."

And they lived happily. Not perfectly — because perfect doesn't exist. But happily. And that's quite enough.""",
            },
        ]

        created = 0
        for s_data in stories:
            _, was_created = ParallelStory.objects.using(DB).update_or_create(
                slug=s_data.pop("slug"),
                defaults={**s_data, "is_published": True},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"ParallelStory (anger): {created} created"))

    def _seed_conflicts(self):
        from memio_world.comfort_models import ConflictScenario

        scenarios = [
            {
                "title": "Brat je uzeo moju igračku",
                "title_de": "Mein Bruder hat mein Spielzeug genommen",
                "title_en": "My brother took my toy",
                "situation": "Upravo se igraš svojom najdražom igračkom. Tvoj brat/sestra dolazi i uzme ti je iz ruku bez pitanja. Osjećaš bijes.",
                "situation_de": "Du spielst gerade mit deinem Lieblingsspielzeug. Dein Bruder/deine Schwester kommt und nimmt es dir einfach weg. Du bist wütend.",
                "emoji": "🧸",
                "age_min": 4,
                "choices": [
                    {
                        "text": "Viknem i uzmem natrag silom",
                        "emoji": "😡",
                        "consequence": "Počinje svađa. Oboje plačete. Mama dolazi i oduzima igračku OBOMA.",
                        "score": -1,
                        "skill": "impulse_control",
                    },
                    {
                        "text": "Kažem: 'Ljut sam jer si uzeo moju igračku bez pitanja'",
                        "emoji": "💬",
                        "consequence": "Brat te čuje. Kaže oprosti i pita: 'Možemo li se zajedno igrati?' Pristaneš.",
                        "score": 2,
                        "skill": "i_message",
                    },
                    {
                        "text": "Odšetam se i dišem",
                        "emoji": "🚶",
                        "consequence": "Smiriš se. Ali igračka je još kod brata. Trebaš se vratiti i razgovarati.",
                        "score": 1,
                        "skill": "self_regulation",
                    },
                    {
                        "text": "Kažem mami/tati",
                        "emoji": "👨‍👩‍👧",
                        "consequence": "Roditelj pomaže riješiti situaciju. Dobro je tražiti pomoć kad ne možeš sam.",
                        "score": 1,
                        "skill": "help_seeking",
                    },
                ],
                "sort_order": 1,
            },
            {
                "title": "Izgubio sam igru",
                "title_de": "Ich habe das Spiel verloren",
                "title_en": "I lost the game",
                "situation": "Igraš društvenu igru s prijateljima. Jako si se trudio, ali si izgubio. Prijatelj koji je pobijedio se raduje. Osjećaš ljutnju i tugu.",
                "emoji": "🎲",
                "age_min": 5,
                "choices": [
                    {
                        "text": "Bacim igru na pod i kažem da je glupa",
                        "emoji": "💥",
                        "consequence": "Igra se slomi. Prijatelji su tužni. Nitko se više ne želi igrati s tobom danas.",
                        "score": -2,
                        "skill": "frustration_tolerance",
                    },
                    {
                        "text": "Kažem: 'Čestitam' i pitam za revanš",
                        "emoji": "🤝",
                        "consequence": "Prijatelj se zahvali. Igrate opet. Ovaj put pobijediš TI! Osjećaš ponos jer nisi odustao.",
                        "score": 3,
                        "skill": "sportsmanship",
                    },
                    {
                        "text": "Šutim i odšetam se",
                        "emoji": "😶",
                        "consequence": "Nitko ne zna da si tužan. Osjećaš se usamljeno. Bolje je reći kako se osjećaš.",
                        "score": 0,
                        "skill": "emotional_expression",
                    },
                ],
                "sort_order": 2,
            },
            {
                "title": "Netko me zadirkuje",
                "title_de": "Jemand ärgert mich",
                "title_en": "Someone is teasing me",
                "situation": "U školi te kolega iz razreda stalno zadirkuje. Govori ti ružne riječi. Osjećaš se loše i ljuto.",
                "emoji": "😢",
                "age_min": 6,
                "choices": [
                    {
                        "text": "Uzvratim ružnim riječima",
                        "emoji": "🗯️",
                        "consequence": "Svađa eskalira. Oboje dobijete opomenu. Situacija je još gora.",
                        "score": -1,
                        "skill": "impulse_control",
                    },
                    {
                        "text": "Kažem mu mirno: 'Prestani. To me povrijeđuje.'",
                        "emoji": "✋",
                        "consequence": "Kolega je iznenađen. Zastane. Možda ne prestane odmah, ali zna da te boli.",
                        "score": 2,
                        "skill": "assertiveness",
                    },
                    {
                        "text": "Kažem učiteljici/učitelju",
                        "emoji": "🏫",
                        "consequence": "Učiteljica razgovara s kolegom. Kolega se ispriča. Tražiti pomoć je HRABROST, ne slabost.",
                        "score": 2,
                        "skill": "help_seeking",
                    },
                    {
                        "text": "Ignoriram i odem do prijatelja",
                        "emoji": "👫",
                        "consequence": "Prijatelji te podrže. Zajedno ste jači. Kolega vidi da ima više ljudi na tvojoj strani.",
                        "score": 1,
                        "skill": "social_support",
                    },
                ],
                "sort_order": 3,
            },
        ]

        created = 0
        for sc_data in scenarios:
            _, was_created = ConflictScenario.objects.using(DB).update_or_create(
                title=sc_data.pop("title"),
                defaults={**sc_data, "is_published": True},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"ConflictScenario: {created} created"))
