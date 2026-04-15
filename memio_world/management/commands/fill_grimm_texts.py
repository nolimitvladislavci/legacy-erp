"""
Popuni ParallelStory zapise s punim tekstovima bajki.
Koristi DeepSeek direktni API za prijevode (bez klijentskih podataka — samo public domain tekst).

Pokretanje:
  manage.py fill_grimm_texts                    # sve koje nemaju tekst
  manage.py fill_grimm_texts --slug rapunzel    # samo jedna
  manage.py fill_grimm_texts --dry-run          # bez pisanja
  manage.py fill_grimm_texts --lang hr,de       # samo HR i DE
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("play_eu")

# Skracene verzije bajki za djecu (3-10 god) — public domain prepricane
# Svaka bajka ima HR tekst, ostali jezici se generiraju putem DeepSeek
GRIMM_TEXTS_HR = {
    "little-red-riding-hood": (
        "Bila jednom jedna djevojčica koju su svi zvali Crvenkapica jer je uvijek "
        "nosila crvenu kapicu koju joj je sašila baka.\n\n"
        'Jednog dana mama joj reče: "Odnesi baki kolač i malo vina. Bolesna je '
        'i slaba, a ovo će joj pomoći da ozdravi. Idi ravno kroz šumu i ne skreći s puta!"\n\n'
        'Crvenkapica krenu kroz šumu. Usput sretne vuka. "Kamo ideš, djevojčice?" upita vuk. '
        '"Idem baki koja živi iza tri velika hrasta," odgovori Crvenkapica.\n\n'
        "Vuk otrča prečicom do bakine kuće. Pojede baku i obuče njezinu odjeću. "
        "Legne u krevet i čeka.\n\n"
        'Kad Crvenkapica stigne, začudi se: "Bako, kakve imaš velike oči!" — "Da te bolje vidim!" '
        '"Bako, kakve imaš velike uši!" — "Da te bolje čujem!" '
        '"Bako, kakva imaš velika usta!" — "Da te bolje pojedem!"\n\n'
        "Vuk skoči iz kreveta! Ali lovac koji je prolazio čuo je viku. "
        "Utrčao je u kuću i spasio Crvenkapicu i baku.\n\n"
        "Od tog dana Crvenkapica više nikad nije skretala s puta."
    ),
    "cinderella": (
        "Pepeljuga je bila dobra i lijepa djevojka koja je živjela s okrutnom maćehom "
        "i dvije zle polusestre. Morala je raditi sve kućanske poslove od jutra do mraka.\n\n"
        "Jednog dana kralj je priredio bal za svog sina princa. Polusestre su otišle u "
        "prekrasnim haljinama, a Pepeljuga je ostala sama i plakala.\n\n"
        "Tada se pojavila dobra vila i dotakla Pepeljugu čarobnim štapićem. "
        "Prljava haljina pretvori se u prekrasnu zlatnu haljinu, a stare cipele u staklene cipelice. "
        '"Ali moraš se vratiti prije ponoći!" upozori vila.\n\n'
        "Na balu je princ plesao samo s Pepeljugom. Bila je najljepša na cijelom balu. "
        "Ali kad je sat otkucao ponoć — Pepeljuga je pobjegla! Na stepenicama je izgubila "
        "jednu staklenu cipelicu.\n\n"
        "Princ je obilazio cijelo kraljevstvo s cipelicom. Kad je došao do Pepeljugine kuće, "
        "cipelica je savršeno pristajala samo njoj.\n\n"
        "Princ i Pepeljuga vjenčali su se i živjeli sretno do kraja života."
    ),
    "snow-white": (
        "Davno, davno živjela je princeza bijele kože i crne kose — zvali su je Snjeguljica. "
        "Njezina maćeha, kraljica, imala je čarobno ogledalo.\n\n"
        '"Ogledalce, ogledalce, reci mi tko je najljepša na svijetu?"\n'
        '"Ti si, kraljice," odgovaralo je ogledalo. Ali jednog dana reče: '
        '"Snjeguljica je sada najljepša."\n\n'
        "Ljubomorna kraljica naredi lovcu da odvede Snjeguljicu u šumu. "
        "Ali lovac se sažali i pusti je. Snjeguljica pronađe malu kućicu u šumi "
        "— u njoj živi sedam patuljaka!\n\n"
        'Patuljci je zavolješe i rekli: "Ostani s nama, ali ne otvaraj vrata nikome!"\n\n'
        "Kraljica se prerušila u staricu i donijela otrovanu jabuku. "
        "Snjeguljica zagrize — i padne u dubok san.\n\n"
        "Patuljci je položiše u stakleni lijes. Jednoga dana dođe princ, "
        "poljubi Snjeguljicu, i ona se probudi!\n\n"
        "Vjenčali su se, a zla kraljica više nikad nikome nije mogla nauditi."
    ),
    "hansel-and-gretel": (
        "Ivica i Marica živjeli su na rubu velike šume s ocem drvosječom i zločestom maćehom. "
        "Bili su tako siromašni da jedva da su imali što za jesti.\n\n"
        "Maćeha nagovori oca da djecu ostavi u šumi. Ali pametni Ivica skupi bijele kamenčiće "
        "i baci ih po putu — tako su našli put kući!\n\n"
        "Drugi put maćeha ih opet odvede, ali Ivica je imao samo mrvice kruha. "
        "Ptice su pojele mrvice i djeca su se izgubila.\n\n"
        "U dubokoj šumi ugledaše kućicu od kolača, bombona i čokolade! "
        '"Tko mi grize kućicu?" zaškripa glas. Bila je to zla vještica!\n\n'
        "Vještica zatvori Ivicu u kavez i tjera Maricu da kuha. "
        '"Kad se Ivica udeblja, pojest ću ga!" kreveljila se.\n\n'
        "Ali hrabra Marica smisli plan. Kad je vještica zagledala u peć, "
        "Marica je gurne unutra i zatvori vrata!\n\n"
        "Djeca nađoše vještičino blago, put kući i oca koji ih je čekao. "
        "Maćehe više nije bilo. Živjeli su sretno zauvijek."
    ),
    "sleeping-beauty": (
        "Kad se rodila princeza, kralj pozva na proslavu dvanaest vila. "
        "Ali trinaesta vila, koja nije bila pozvana, dođe ljutita.\n\n"
        '"Na svoj petnaesti rođendan, princeza će se ubosti na vreteno i umrijeti!" '
        "prokune zla vila. Ali dvanaesta vila ublaži kletvu: "
        '"Neće umrijeti — zaspat će dubokim snom sto godina."\n\n'
        "Kralj naredi da se spale sva vretena u kraljevstvu. "
        "Ali na petnaesti rođendan princeza nađe skriveni toranj "
        "s bakecom koja je prela. Ubode se — i zaspi.\n\n"
        "Cijeli dvorac zaspi: kralj, kraljica, konji, psi, golubovi — sve!\n"
        "Oko dvorca izraste gusta živica od trnja.\n\n"
        "Sto godina kasnije dođe hrabar princ. Trnje se rastvori pred njim "
        "kao da mu želi pokazati put. Nađe princezu i poljubi je.\n\n"
        "Princeza otvori oči. Cijeli dvorac se probudi! "
        "Princ i Trnoružica vjenčali su se istog dana."
    ),
    "the-wolf-and-the-seven-young-goats": (
        "Mama koza imala je sedam kozlića. Jednog dana morala je u šumu po hranu.\n\n"
        '"Djeco, ne otvarajte nikome osim meni! Vuk ima grub glas i crne šape — '
        'po tome ćete ga prepoznati."\n\n'
        'Vuk dođe i pokuca: "Djeco, otvorite, mama je došla!" '
        'Ali kozlići prepoznaše grub glas. "Ti nisi mama!"\n\n'
        "Vuk ode i pojede kredu da mu glas postane nježan. "
        'Vrati se: "Djeco, otvorite!" Ali kozlići vide crne šape ispod vrata. '
        '"Ti nisi mama — mama ima bijele šape!"\n\n'
        "Vuk ode i umoči šape u bijelo brašno. Vrati se treći put. "
        "Glas nježan, šape bijele — kozlići otvore.\n\n"
        "Vuk pojede šest kozlića! Samo najmanji se sakrio u sat.\n\n"
        "Mama koza se vrati, pronađe najmlađeg i saznà što se dogodilo. "
        "Nađu vuka kako spava pod drvetom. Mama koza mu otvori trbuh, "
        "izvadi šest kozlića — svi živi! Napune mu trbuh kamenjem.\n\n"
        "Kad se vuk probudio i htio piti vode — kamenje ga povuče u bunar i više ga nitko nije vidio."
    ),
    "the-frog-prince": (
        "Princeza je igrala zlatnom kuglom pokraj bunara. Kugla joj upadne u vodu!\n\n"
        '"Ja ću ti je izvaditi," reče žaba, "ali moraš obećati da ću jesti s tvojeg tanjura '
        'i spavati na tvojem jastuku."\n'
        "Princeza obeća — samo da dobije kuglu natrag.\n\n"
        "Žaba izvadi kuglu, ali princeza pobjegne u dvorac zaboravivši obećanje.\n\n"
        "Navečer žaba pokuca na vrata dvorca. Kralj reče: "
        '"Obećanje se mora držati. Pusti žabu unutra."\n\n'
        "Žaba jede s princezinog tanjura i legne na jastuk. "
        "Princeza se naljuti i baci žabu o zid — ali umjesto žabe, "
        "pred njom stoji lijep princ!\n\n"
        '"Bio sam začaran," reče princ. "Tvoj postupak me oslobodio."\n\n'
        "Princ i princeza postadoše prijatelji, a onda se i vjenčaše."
    ),
    "rapunzel": (
        "Čarobnica je ukrala dijete od jednog para i zatvorila ga u visoki toranj bez vrata. "
        "Djevojčica se zvala Rapunzel i imala je predugu zlatnu kosu.\n\n"
        'Svaki dan čarobnica je dozivala: "Rapunzel, Rapunzel, spusti svoju kosu!" '
        "Rapunzel bi spustila pletenicu kroz prozor, a čarobnica bi se popela.\n\n"
        "Jednog dana princ je čuo Rapunzelin prekrasan pjev. "
        "Sakrio se i čuo čarobničine riječi. Navečer dođe sam: "
        '"Rapunzel, Rapunzel, spusti svoju kosu!"\n\n'
        "Rapunzel spusti kosu i princ se popne. Zaljubiše se.\n\n"
        "Ali čarobnica sazna! Odreže Rapunzelinu kosu i protjera je u pustinju. "
        "Princa zbaci s tornja i on oslijepi.\n\n"
        "Princ je godinama lutao tražeći Rapunzel. "
        "Kad je napokon pronađe, njezine suze padnu na njegove oči — i on progleda!\n\n"
        "Zajedno se vratiše u prinčevo kraljevstvo i živjeli sretno."
    ),
    "the-town-musicians-of-bremen": (
        "Stari magarac pobjegne od gospodara koji ga je htio se riješiti. "
        '"Idem u Bremen — postat ću gradski muzikant!" odluči magarac.\n\n'
        'Putem sretne starog psa. "I mene su htjeli istjerati," reče pas. '
        '"Hajdemo zajedno!" Zatim im se pridruži stara mačka, pa stari pijetao.\n\n'
        "Navečer ugledaju osvijetljenu kuću u šumi. Unutra — razbojnici jedu i piju!\n\n"
        "Magarac stane na prozor, pas skoči na magarca, mačka na psa, pijetao na mačku. "
        "I svi zajedno zapjevaju!\n\n"
        '"IIII-AAAA! AV-AV! MIJAU! KUKURIKUUUU!"\n\n'
        "Razbojnici pomisle da je to strašno čudovište — i pobjegnu u šumu!\n\n"
        "Četvorica prijatelja uđu u kuću. Magarac legne na slamu, pas iza vrata, "
        "mačka uz peć, pijetao na gredu.\n\n"
        "Razbojnici se nikad više nisu vratili. A četiri prijatelja? "
        "Nikad nisu stigli u Bremen — ali našli su dom. A to je još bolje."
    ),
    "the-star-money": (
        "Bila jednom djevojčica koja je ostala sama na svijetu. "
        "Nije imala ni kuću ni krevet — samo odjeću na sebi i komadić kruha.\n\n"
        "Krenu u svijet. Sretne gladnog čovjeka i dade mu kruh. "
        "Sretne dijete bez kape — dade mu svoju kapu. "
        "Sretne dijete bez jakne — dade mu jaknu. "
        "Sretne dijete bez haljine — dade mu i haljinu.\n\n"
        "Ostade sama u mraku, bez ičega. I tada — sa zvjezdanog neba "
        "počeše padati zlatni taliri! Padali su i padali, "
        "a djevojčica je odjednom imala novu bijelu košuljicu.\n\n"
        "Skupila je talire i bila bogata do kraja života. "
        "Ali najvažnije — nikad nije prestala dijeliti s drugima."
    ),
}


class Command(BaseCommand):
    help = "Popuni ParallelStory zapise s punim HR tekstovima bajki"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Samo ova bajka")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--translate", action="store_true", help="Koristi DeepSeek za DE/EN prijevode")
        parser.add_argument("--lang", type=str, default="hr", help="Jezici za popuniti (hr,de,en)")

    def handle(self, *args, **options):
        from memio_world.play_eu_models import ParallelStory

        dry_run = options["dry_run"]
        target_slug = options.get("slug")
        do_translate = options["translate"]
        langs = options["lang"].split(",")

        stories = ParallelStory.objects.using("memio_world").all()
        if target_slug:
            stories = stories.filter(slug=target_slug)

        filled = 0
        skipped = 0

        for story in stories:
            hr_text = GRIMM_TEXTS_HR.get(story.slug, "")
            if not hr_text:
                skipped += 1
                continue

            if story.text_hr and not dry_run:
                self.stdout.write(f"  [SKIP] {story.title_hr} (već ima tekst)")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  [WOULD FILL] {story.title_hr} ({len(hr_text)} chars)")
                filled += 1
                continue

            story.text_hr = hr_text

            # Prijevodi putem DeepSeek ako je zatraženo
            if do_translate and "de" in langs and not story.text_de:
                story.text_de = self._translate(hr_text, "de", story.title_de)
            if do_translate and "en" in langs and not story.text_en:
                story.text_en = self._translate(hr_text, "en", story.title_en)

            story.is_published = True
            story.save(using="memio_world")
            filled += 1
            self.stdout.write(f"  [FILLED] {story.title_hr} ({len(hr_text)} chars)")

        self.stdout.write(self.style.SUCCESS(f"\nDONE: {filled} popunjeno, {skipped} preskočeno"))

    def _translate(self, text: str, target_lang: str, target_title: str) -> str:
        """Prevedi tekst putem DeepSeek direktnog API-ja (bez klijentskih podataka)."""
        try:
            from core.deepseek_client import deepseek_direct

            lang_names = {"de": "German", "en": "English", "fr": "French", "it": "Italian"}
            lang_name = lang_names.get(target_lang, target_lang)

            result = deepseek_direct(
                prompt=(
                    f"Translate this children's fairy tale to {lang_name}. "
                    f'The story is called "{target_title}". '
                    f"Keep the same paragraph structure. Use simple language for children aged 4-10. "
                    f"Return ONLY the translated text, no commentary.\n\n{text}"
                ),
                system=f"You are a professional children's book translator. Translate to {lang_name}.",
                max_tokens=2000,
                temperature=0.3,
            )
            self.stdout.write(f"    [{target_lang.upper()}] Prevedeno ({len(result)} chars)")
            return result
        except Exception as e:
            logger.error("Translation error for %s: %s", target_lang, e)
            self.stdout.write(self.style.WARNING(f"    [{target_lang.upper()}] GREŠKA: {e}"))
            return ""
