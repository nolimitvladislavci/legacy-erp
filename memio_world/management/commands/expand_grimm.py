"""Expand Grimm fairy tales from summaries to full text."""
from django.core.management.base import BaseCommand
from memio_world.play_eu_models import ParallelStory

DB = "memio_world"

STORIES = {
    "snow-white": {
        "reading_time": 14,
        "text_hr": """Bila jednom jedna kraljica koja je sjedila kraj prozora i šivala. Okvir prozora bio je od crnog ebanovine. Dok je šivala, ubola se iglom u prst i tri kapi krvi pale su na snijeg ispred prozora. Crveno na bijelom bilo je tako lijepo da kraljica pomisli: "Kamo sreće da imam dijete bijelo kao snijeg, rumeno kao krv, i crne kose poput ebanovine."

Ubrzo nakon toga kraljica rodi djevojčicu bijele kože, rumenih usana i crne kose. Nazvala ju je Snjeguljica. Ali kraljica umre ubrzo nakon poroda.

Godinu dana kasnije kralj se oženi drugom ženom. Nova kraljica bila je lijepa, ali ohola i zavidna. Imala je čarobno ogledalo i svako jutro bi ga upitala: "Ogledalce, ogledalce na zidu, tko je najljepša u cijelom svijetu?" A ogledalo bi odgovorilo: "Vi ste, kraljice, najljepša u svijetu." I kraljica bi bila zadovoljna.

Ali Snjeguljica je rasla i postajala sve ljepša. I jednog dana, kad je kraljica upitala ogledalo, ono odgovori: "Vi ste lijepi, kraljice, to je istina. Ali Snjeguljica je tisuću puta ljepša od vas."

Kraljica poblijedi od bijesa. Od tog trenutka, kad god bi pogledala Snjeguljicu, srce bi joj se stezalo od mržnje. Zavist je rasla u njoj poput korova dok nije mogla više izdržati.

Pozvala je lovca i naredila mu: "Odvedi dijete u šumu i ubij je. I donesi mi njezino srce kao dokaz." Lovac je odveo Snjeguljicu u šumu, ali kad je izvukao nož, djevojčica je zaplakala: "Dragi lovče, poštedi mi život! Otići ću duboko u šumu i nikad se neću vratiti."

Lovcu se slomi srce. "Bježi, jadna djevojčice," reče. Ubio je mladu košutu i njezino srce odnio kraljici. A Snjeguljica je trčala kroz šumu, sama i uplašena, dok nije pronašla malu kućicu u dolini.

Kućica je bila sićušna i čista, sa sedam malih stolaca, sedam malih tanjura i sedam malih kreveta. Snjeguljica je bila tako umorna da je pojela malo sa svakog tanjura, popila gutljaj iz svakog vrča, i legla na sedmi krevet i zaspala.

Kad se smračilo, vratili se vlasnici kućice — sedam patuljaka koji su radili u rudniku zlata u planini. Zapalili su svojih sedam svijećica i ugledali da netko spava u krevetu. "O bože!" šapnuli su. "Kako je ovo dijete lijepo!"

Ujutro se Snjeguljica probudila i prepala se — sedam malih lica zurilo je u nju. Ali patuljci su bili dobri. "Ako ćeš kuhati, prati i čistiti — možeš ostati s nama," rekoše. "Ali PAZI — nemoj nikoga puštati unutra dok nas nema. Tvoja maćeha te traži."

I tako je Snjeguljica živjela s patuljcima, sretna i sigurna. Ali kraljica je opet upitala ogledalo — i ogledalo je reklo: "Kraljice, vi ste ovdje najljepša, to je istina. Ali Snjeguljica, iza sedam gora, kod sedam patuljaka, tisuću je puta ljepša od vas."

Kraljica je preobukla se u staru prodavačicu i otišla iza sedam gora. Pokucala je na vrata kućice. Snjeguljica je pogledala kroz prozor i otvorila vrata. Kraljica joj je ponudila šarenu vrpcu i uvezala je tako čvrsto oko struka da djevojčica nije mogla disati i pala je na pod.

Kad su se patuljci vratili, brzo su presekli vrpcu i ona je opet mogla disati. "To je bila kraljica!" rekoše. "Nikoga više ne puštaj unutra!"

Ali kraljica je došla drugi put s otrovnim češljem. I treći put s otrovnom jabukom. Najljepša jabuka ikad viđena — jednom stranom crvena, drugom zelena. Kraljica je zagrizla zelenu stranu koja nije bila otrovna i ponudila Snjeguljici crvenu stranu.

Snjeguljica je zagrizla i pala mrtva.

Ovaj put patuljci je nisu mogli oživjeti. Plakali su tri dana. Ali Snjeguljica je bila tako lijepa čak i u smrti da je nisu htjeli staviti u zemlju. Napravili su lijes od stakla, stavili je unutra, i postavili ga na vrh planine. Jedan patuljak je uvijek čuvao stražu.

Prošlo je mnogo vremena. Jednog dana mladi kraljević je jahao kroz šumu i ugledao stakleni lijes. Kad je vidio Snjeguljicu, zastao je zadivljen. "Pustite me da je odnesem," molio je patuljke.

Ali dok su sluge nosili lijes, jedan se spotaknuo. Od potresa komad otrovne jabuke ispadne iz Snjeguljičina grla — i ona otvori oči!

"Gdje sam?" upitala je. Kraljević joj je ispričao sve i rekao: "Volim te više od svega na svijetu. Hoćeš li poći sa mnom i biti moja žena?"

Snjeguljica je pogledala njegove dobre oči i rekla da. Pripremilo se veliko vjenčanje. Pozvani su svi — pa čak i zla kraljica. Kad je stigla i ugledala Snjeguljicu živu i lijepu kao nikad — ogledalo kod kuće puklo je na tisuću komada. Jer zlo ne može podnijeti sreću dobrih.

Snjeguljica i kraljević živjeli su sretno i vladali pravedno. A sedam patuljaka dolazilo im je u goste svake godine — jer je prijateljstvo vrijedno više od zlata.""",

        "text_de": """Es war einmal mitten im Winter, und die Schneeflocken fielen wie Federn vom Himmel. Da sasz eine Koenigin an einem Fenster mit einem Rahmen aus schwarzem Ebenholz und naehte. Beim Naehen stach sie sich in den Finger, und drei Tropfen Blut fielen in den Schnee. Das sah so schoen aus, dass die Koenigin dachte: "Haett ich doch ein Kind, so weiss wie Schnee, so rot wie Blut und so schwarz wie Ebenholz."

Bald darauf bekam sie ein Toechterlein, das war so weiss wie Schnee, so rot wie Blut und so schwarzhaarig wie Ebenholz. Es wurde Schneewittchen genannt. Aber die Koenigin starb bald nach der Geburt.

Ein Jahr spaeter nahm der Koenig eine neue Gemahlin. Sie war schoen, aber stolz und eitel. Sie besasz einen Zauberspiegel, und jeden Morgen fragte sie: "Spieglein, Spieglein an der Wand, wer ist die Schoenste im ganzen Land?" Und der Spiegel antwortete: "Frau Koenigin, Ihr seid die Schoenste im Land."

Aber Schneewittchen wuchs heran und wurde immer schoener. Eines Tages antwortete der Spiegel: "Frau Koenigin, Ihr seid die Schoenste hier, aber Schneewittchen ist tausendmal schoener als Ihr."

Die Koenigin wurde blass vor Neid. Sie rief einen Jaeger und befahl: "Bring das Kind in den Wald und toete es." Aber der Jaeger hatte Mitleid und liess Schneewittchen frei. Sie rannte tief in den Wald und fand ein kleines Haeuschen mit sieben kleinen Stuehlchen, sieben Tellerlein und sieben Bettlein.

Als es dunkel wurde, kamen die Besitzer — sieben Zwerge, die in einem Goldbergwerk arbeiteten. Sie fanden Schneewittchen schlafend und waren entzueckt. "Wenn du fuer uns kochst und putzt, kannst du bei uns bleiben," sagten sie. "Aber huete dich — lass niemanden herein."

Dreimal kam die Koenigin verkleidet. Mit einem Schnuerband. Mit einem giftigen Kamm. Und schliesslich mit einem giftigen Apfel. Beim dritten Mal biss Schneewittchen in die rote Haelfte des Apfels und fiel tot um.

Die Zwerge legten sie in einen glaesernen Sarg auf dem Gipfel eines Berges. Ein Koenigssohn ritt vorbei und sah sie. Als seine Diener den Sarg trugen, stolperte einer. Das Stueck Apfel fiel aus Schneewittchens Kehle — und sie oeffnete die Augen.

Der Koenigssohn bat um ihre Hand, und Schneewittchen sagte ja. Bei der Hochzeit erkannte die boese Koenigin Schneewittchen — und ihr Spiegel daheim zerbrach in tausend Stuecke. Denn das Boese kann das Glueck der Guten nicht ertragen.

Schneewittchen und der Prinz lebten gluecklich. Die sieben Zwerge besuchten sie jedes Jahr — denn Freundschaft ist mehr wert als Gold.""",

        "text_en": """Once upon a time in the middle of winter, when the snowflakes fell from the sky like feathers, a queen sat sewing at a window with a frame of black ebony. As she sewed, she pricked her finger and three drops of blood fell upon the snow. The red on the white looked so beautiful that the queen thought: "If only I had a child as white as snow, as red as blood, and as black as ebony."

Soon after she bore a little daughter who was as white as snow, as red as blood, and as black-haired as ebony. She was called Snow White. But the queen died soon after.

A year later the king took a new wife. She was beautiful but proud and vain. She possessed a magic mirror, and every morning she would ask: "Mirror, mirror on the wall, who is the fairest of them all?" And the mirror would answer: "You, my queen, are the fairest of all."

But Snow White grew and became ever more beautiful. One day the mirror answered: "You, my queen, are fair, it is true. But Snow White is a thousand times fairer than you."

The queen turned pale with rage. She summoned a huntsman and commanded: "Take the child into the forest and kill her. Bring me her heart as proof." But the huntsman took pity and let Snow White go free. She ran deep into the forest and found a tiny cottage with seven little chairs, seven little plates, and seven little beds.

When darkness fell, the owners returned — seven dwarfs who worked in a gold mine in the mountain. They found Snow White asleep and were delighted. "If you will cook and clean for us, you may stay," they said. "But beware — let no one in. Your stepmother is searching for you."

Three times the queen came in disguise: with a lace, with a poisoned comb, and finally with a poisoned apple. The third time, Snow White bit into the red half of the apple and fell down dead.

The dwarfs laid her in a glass coffin on top of a mountain. A prince rode by and saw her. As his servants carried the coffin, one stumbled. The piece of apple fell from Snow White's throat — and she opened her eyes.

The prince asked for her hand, and Snow White said yes. At the wedding, the evil queen recognised Snow White — and her mirror at home shattered into a thousand pieces. For evil cannot bear the happiness of the good.

Snow White and the prince lived happily ever after. The seven dwarfs visited them every year, bringing gold — not because they had to, but because friendship is worth more than gold.""",
    },

    "little-red-riding-hood": {
        "reading_time": 10,
        "text_hr": """Bila jednom jedna djevojčica, tako ljupka da su je svi voljeli čim bi je ugledali. Baka ju je voljela najviše od svih i poklonila joj kapicu od crvenog baršuna. Djevojčica ju je toliko voljela nositi da su je svi zvali Crvenkapica.

Jednog dana mama joj je rekla: "Crvenkapice, odnesi baki kolač i bocu vina. Baka je bolesna i slaba, ovo će joj dobro doći. Kreni dok je još rano i hodi lijepo putem. Ne skreći s puta i nemoj se zadržavati u šumi."

"Bit ću pažljiva, mama," obećala je Crvenkapica i krenula na put. Baka je živjela duboko u šumi, pola sata hoda od sela.

Kad je Crvenkapica ušla u šumu, susretne je vuk. Crvenkapica ga se nije bojala jer nije znala kakva je to zla životinja. "Dobar dan, Crvenkapice," rekao je vuk ljubaznim glasom. "Kamo ideš tako rano?"

"Idem baki. Bolesna je, nosim joj kolač i vino." Vuk pomisli: "Ova mala bi bila dobar zalogaj. Ali ako budem pametan, mogu dobiti i nju i baku."

"Crvenkapice," reče vuk, "pogledaj kako lijepo cvijeće raste okolo. Zašto ne bi nabrala baki buket? I slušaj kako lijepo ptice pjevaju!"

Crvenkapica pogleda i doista — sunce je probijalo kroz krošnje, cvijeće je raslo svuda, i sve je bilo tako lijepo. "Baka bi se sigurno obradovala svježem buketu," pomisli. I skrene s puta u šumu, brati cvijeće. Svaki put kad bi ubrala jedan cvijet, vidjela bi ljepši malo dalje, i tako je odlazila sve dublje u šumu.

A vuk je otrčao ravno do bakine kuće. Pokucao je na vrata. "Tko je?" upitala je baka slabim glasom. "Crvenkapica," odgovori vuk tankim glasom. "Nosim ti kolač i vino. Otvori."

"Samo pritisni kvaku," reče baka. "Ja sam preslaba da ustanem."

Vuk pritisne kvaku, vrata se otvore, i on uđe. Progutao je baku, obukao njezinu spavaćicu i kapu, legao u krevet i navukao pokrivač do nosa.

Malo poslije dođe Crvenkapica. Uđe u kuću i priđe krevetu. "Bako, kakve imaš velike oči!" reče. "Da te bolje vidim, dijete moje." — "Bako, kakve imaš velike uši!" — "Da te bolje čujem, dijete moje." — "Bako, kakva ti je velika usta!" — "Da te bolje pojedem!"

I vuk skoči iz kreveta.

Ali upravo u tom trenutku prolazio je lovac pokraj bakine kuće. Začuo je čudne zvukove i uletio unutra. Kad je vidio vuka, shvatio je što se dogodilo. Uzeo je škare i oslobodio baku i Crvenkapicu. Obje su bile žive i zdrave!

Baka je pojela kolač i popila vino, i ubrzo joj je bilo puno bolje.

A Crvenkapica je pomislila: "Nikad više neću skretati s puta kad mi mama kaže da idem ravno. Da nisam zastala brati cvijeće, ništa se loše ne bi dogodilo."

I od tog dana, kad bi joj mama rekla "Idi ravno i ne skreći s puta" — Crvenkapica bi poslušala. Jer je naučila najvažniju lekciju: da dobronamjerni savjeti roditelja postoje s razlogom. Čak i kad nam se čini da znamo bolje — ponekad je mudrost poslušati one koji nas vole.""",

        "text_de": """Es war einmal ein kleines Maedchen, das war so huebsch, dass es jeder lieb hatte, der es nur ansah. Die Grossmutter liebte es am allermeisten und schenkte ihm ein Kaeppchen aus rotem Samt. Weil es dem Kind so gut stand und es nichts anderes mehr tragen wollte, nannte man es nur noch Rotkaeppchen.

Eines Tages sagte die Mutter: "Rotkaeppchen, bring der Grossmutter Kuchen und Wein. Sie ist krank und schwach. Geh frueh los, bleib auf dem Weg und lauf nicht in den Wald hinein."

"Ich werde vorsichtig sein, Mama," versprach Rotkaeppchen und machte sich auf den Weg. Die Grossmutter wohnte tief im Wald, eine halbe Stunde vom Dorf entfernt.

Als Rotkaeppchen in den Wald kam, begegnete ihr der Wolf. "Guten Tag, Rotkaeppchen," sagte der Wolf freundlich. "Wohin gehst du so frueh?"

"Zur Grossmutter. Sie ist krank. Ich bringe ihr Kuchen und Wein."

Der Wolf dachte: "Wenn ich schlau bin, kann ich beide bekommen." — "Rotkaeppchen, sieh die schoenen Blumen! Warum pflueckst du nicht einen Strauss fuer die Grossmutter?"

Rotkaeppchen schaute und ging tiefer und tiefer in den Wald, um Blumen zu pfluecken. Der Wolf aber rannte geradewegs zum Haus der Grossmutter. Er verschluckte die Grossmutter, zog ihr Nachthemd an und legte sich ins Bett.

Als Rotkaeppchen kam: "Grossmutter, was hast du fuer grosse Augen!" — "Damit ich dich besser sehen kann." — "Was hast du fuer grosse Ohren!" — "Damit ich dich besser hoeren kann." — "Was hast du fuer ein grosses Maul!" — "Damit ich dich besser fressen kann!"

Aber gerade in diesem Moment kam ein Jaeger vorbei. Er hoerte seltsame Geraeusche und stuermte hinein. Er befreite Grossmutter und Rotkaeppchen — beide waren wohlauf!

Von diesem Tag an, wenn die Mutter sagte "Geh geradeaus" — hoerte Rotkaeppchen zu. Denn sie hatte die wichtigste Lektion gelernt: dass die Ratschlaege der Eltern aus Liebe kommen.""",

        "text_en": """Once upon a time there was a little girl so sweet that everyone loved her at first sight. Her grandmother loved her most of all and gave her a little cap of red velvet. Because it suited the child so well and she would wear nothing else, everyone called her Little Red Riding Hood.

One day her mother said: "Little Red Riding Hood, take this cake and wine to Grandmother. She is ill and weak. Set out early, stay on the path, and do not stray into the forest."

"I will be careful, Mother," promised Little Red Riding Hood, and set off. Grandmother lived deep in the forest, half an hour's walk from the village.

When Little Red Riding Hood entered the forest, she met the wolf. "Good morning, Little Red Riding Hood," said the wolf in a friendly voice. "Where are you going so early?"

"To Grandmother's. She is ill. I am bringing her cake and wine."

The wolf thought: "If I am cunning, I can have them both." — "Little Red Riding Hood, look at the beautiful flowers! Why not pick a bouquet for your grandmother?"

Little Red Riding Hood looked around and wandered deeper into the forest, picking flowers. But the wolf ran straight to Grandmother's house. He swallowed Grandmother, put on her nightgown, and climbed into bed.

When Little Red Riding Hood arrived: "Grandmother, what big eyes you have!" — "All the better to see you with." — "What big ears you have!" — "All the better to hear you with." — "What a big mouth you have!" — "All the better to eat you with!"

But just at that moment a huntsman was passing by. He heard strange sounds and burst in. He freed Grandmother and Little Red Riding Hood — both were safe and sound!

From that day on, when her mother said "Go straight and do not stray" — Little Red Riding Hood listened. For she had learned the most important lesson: that the advice of those who love us exists for a reason.""",
    },
}


class Command(BaseCommand):
    help = "Expand Grimm fairy tales from summaries to full text"

    def handle(self, *args, **options):
        for slug, data in STORIES.items():
            try:
                story = ParallelStory.objects.using(DB).get(slug=slug)
                story.text_hr = data["text_hr"]
                story.text_de = data["text_de"]
                story.text_en = data["text_en"]
                story.reading_time_minutes = data["reading_time"]
                story.save(using=DB)

                hr_paras = len([p for p in story.text_hr.split("\n") if p.strip()])
                self.stdout.write(
                    f"  {slug}: HR={len(story.text_hr)}ch/{hr_paras}para "
                    f"| DE={len(story.text_de)}ch | EN={len(story.text_en)}ch"
                )
            except ParallelStory.DoesNotExist:
                self.stderr.write(f"  {slug}: NOT FOUND")

        self.stdout.write(self.style.SUCCESS("Done!"))
