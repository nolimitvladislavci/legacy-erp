"""
PLAY.EU Games — Interaktivne edukativne igre
=============================================
Šah škola: Figure kao likovi iz bajki, interaktivni tutoriali
Čovječe ne ljuti se: Najvažnija lekcija — gubiti s dostojanstvom
Sve igre su PUBLIC (no login required).
"""

from django.shortcuts import render


def _lang(request):
    return request.GET.get("lang", "hr")


# ═══════════════════════════════════════════════════════════════
# ŠAH ŠKOLA — Nivo 1: Upoznaj figure
# ═══════════════════════════════════════════════════════════════


def chess_home(request):
    """Šah škola — početna stranica s nivoima."""
    lang = _lang(request)
    return render(request, "memio_world/chess_home.html", {"nav": "play", "lang": lang})


def chess_learn(request, piece):
    """Interaktivno učenje jedne figure."""
    lang = _lang(request)

    PIECES = {
        "king": {
            "name_hr": "Kralj",
            "name_de": "König",
            "name_en": "King",
            "symbol": "♚",
            "fairy_char": "Mudri Kralj iz bajke",
            "fairy_story": "Kralj je najvažnija figura — ako padne, igra je gotova. "
            "Ali kreće se samo jedno polje. Zašto? Jer pravi kralj ne juri naprijed — "
            "on promišlja svaki korak. Kao Striborov otac koji je pažljivo čuvao svoju obitelj.",
            "moves": "one_all",
            "color": "#c9a84c",
        },
        "queen": {
            "name_hr": "Kraljica",
            "name_de": "Dame",
            "name_en": "Queen",
            "symbol": "♛",
            "fairy_char": "Čarobnica iz Rapunzela",
            "fairy_story": "Kraljica je najmoćnija figura na ploči. Kreće se koliko god želi — "
            "ravno, dijagonalno, u svim smjerovima. Poput čarobnice koja vlada cijelim tornjem. "
            "Ali pazi — i najmoćniji mogu pasti ako nisu oprezni!",
            "moves": "unlimited_all",
            "color": "#8b2500",
        },
        "rook": {
            "name_hr": "Top",
            "name_de": "Turm",
            "name_en": "Rook",
            "symbol": "♜",
            "fairy_char": "Toranj u kojem je Rapunzel zatočena",
            "fairy_story": "Top je čvrst poput kamenog tornja. Kreće se ravno — gore, dolje, lijevo, desno — "
            "koliko želi. Ne može dijagonalno jer je toranj RAVNA građevina. "
            "Dva topa zajedno su nevjerojatno jaki — kao dva tornja koja čuvaju dvorac.",
            "moves": "unlimited_straight",
            "color": "#5c3d1a",
        },
        "bishop": {
            "name_hr": "Lovac",
            "name_de": "Läufer",
            "name_en": "Bishop",
            "symbol": "♝",
            "fairy_char": "Lovac koji je spasio Snjeguljicu",
            "fairy_story": "Lovac se kreće dijagonalno — ukoso, koliko želi. "
            "Jedan lovac uvijek ostaje na bijelim poljima, drugi na crnim. "
            "Nikad ne mijenjaju boju! Kao lovac u Snjeguljici koji nikad nije promijenio stranu — "
            "ostao je dobar čak i kad mu je kraljica naredila zlo.",
            "moves": "unlimited_diagonal",
            "color": "#2e7d32",
        },
        "knight": {
            "name_hr": "Konj",
            "name_de": "Springer",
            "name_en": "Knight",
            "symbol": "♞",
            "fairy_char": "Prinčev konj koji je jahao kroz šumu",
            "fairy_story": "Konj je najneobičnija figura — skače u obliku slova L! "
            "Dva polja ravno, pa jedno u stranu. I može PRESKAKATI druge figure! "
            "Nijedna druga figura to ne može. Kao prinčev konj koji je preskočio trnje "
            "da stigne do uspavane Trnoružice.",
            "moves": "l_shape",
            "color": "#1565c0",
        },
        "pawn": {
            "name_hr": "Pješak",
            "name_de": "Bauer",
            "name_en": "Bauer",
            "symbol": "♟",
            "fairy_char": "Hrabri mali Hlapić",
            "fairy_story": "Pješak je najmanji, ali NAJHRABRIJI. Ide samo naprijed — nikad natrag! "
            "Jede dijagonalno. I ako stigne do kraja ploče — postaje BILO KOJA figura! "
            "Čak i kraljica! Baš kao mali Hlapić koji je krenuo sam u svijet i postao heroj. "
            "Nikad ne podcjenjuj najmanijeg.",
            "moves": "pawn_special",
            "color": "#6d4c41",
        },
    }

    piece_data = PIECES.get(piece)
    if not piece_data:
        from django.http import Http404

        raise Http404

    # Piece order for navigation
    piece_order = ["king", "queen", "rook", "bishop", "knight", "pawn"]
    current_idx = piece_order.index(piece) if piece in piece_order else 0
    next_piece = piece_order[current_idx + 1] if current_idx < len(piece_order) - 1 else None
    prev_piece = piece_order[current_idx - 1] if current_idx > 0 else None

    return render(
        request,
        "memio_world/chess_learn.html",
        {
            "nav": "play",
            "lang": lang,
            "piece": piece,
            "piece_data": piece_data,
            "next_piece": next_piece,
            "prev_piece": prev_piece,
            "piece_index": current_idx + 1,
            "total_pieces": len(piece_order),
        },
    )


def chess_puzzle(request):
    """Šah puzzle — mat u 1 potezu."""
    lang = _lang(request)
    return render(request, "memio_world/chess_puzzle.html", {"nav": "play", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# ČOVJEČE NE LJUTI SE
# ═══════════════════════════════════════════════════════════════


def ludo_game(request):
    """Čovječe ne ljuti se — najvažnija igra na svijetu.
    Uči: strpljivost, poštivanje pravila, gubiti s dostojanstvom.
    """
    lang = _lang(request)
    return render(request, "memio_world/ludo_game.html", {"nav": "play", "lang": lang})


def chess_memory(request):
    """Šah Memory — spoji figuru s imenom."""
    lang = _lang(request)
    return render(request, "memio_world/chess_memory.html", {"nav": "play", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# INTERAKTIVNA SLOVARICA — A-Ž sa zvukom i slikom
# ═══════════════════════════════════════════════════════════════


def alphabet_game(request):
    """Interaktivna slovarica — svako slovo sa zvukom, slikom i riječju."""
    lang = _lang(request)
    return render(request, "memio_world/alphabet_game.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# BROJEVI — Učenje brojeva 1-20 + zbrajanje
# ═══════════════════════════════════════════════════════════════


def numbers_game(request):
    """Brojevi 1-20 + jednostavno zbrajanje."""
    lang = _lang(request)
    return render(request, "memio_world/numbers_game.html", {"nav": "learn", "lang": lang})


def coloring_page(request):
    """Bojanka — dijete crta i boji likove iz bajki."""
    lang = _lang(request)
    return render(request, "memio_world/coloring_page.html", {"nav": "play", "lang": lang})


def hangman_game(request):
    """Vješalica — pogodi riječ slovo po slovo."""
    lang = _lang(request)
    return render(request, "memio_world/hangman_game.html", {"nav": "play", "lang": lang})


def clock_game(request):
    """Sat — nauči čitati vrijeme."""
    lang = _lang(request)
    return render(request, "memio_world/clock_game.html", {"nav": "learn", "lang": lang})


def battleship_game(request):
    """Potapanje brodova — uči koordinatni sustav."""
    lang = _lang(request)
    return render(request, "memio_world/battleship_game.html", {"nav": "play", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# KREATIVNO PISANJE — Nastavi priču
# ═══════════════════════════════════════════════════════════════

def creative_writing(request):
    """Kreativno pisanje — dijete nastavlja bajku."""
    lang = _lang(request)
    return render(request, "memio_world/creative_writing.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# ŽIVOTINJE — Zvukovi, slike, kviz
# ═══════════════════════════════════════════════════════════════

def animal_sounds(request):
    """Životinje — zvukovi i kviz."""
    lang = _lang(request)
    return render(request, "memio_world/animal_sounds.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# KUHANJE — Recepti za djecu korak po korak
# ═══════════════════════════════════════════════════════════════

def cooking_recipes(request):
    """Kuhanje za djecu — recepti korak po korak."""
    lang = _lang(request)
    return render(request, "memio_world/cooking_recipes.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# KARTA PRIČA — Gdje se bajka događa?
# ═══════════════════════════════════════════════════════════════

def story_map(request):
    """Karta priča — interaktivna mapa Europe s bajkama."""
    lang = _lang(request)
    from memio_world.play_eu_models import ParallelStory
    stories = ParallelStory.objects.using('memio_world').filter(is_published=True).exclude(country_of_origin='')
    return render(request, "memio_world/story_map.html", {"nav": "learn", "lang": lang, "stories": stories})


# ═══════════════════════════════════════════════════════════════
# PET CORNER — Veza s Memio.pet, briga o ljubimcima
# ═══════════════════════════════════════════════════════════════

def pet_corner(request):
    """Kutak za ljubimce — edukacija o brizi, odgovornost, veza s memio.pet."""
    lang = _lang(request)
    return render(request, "memio_world/pet_corner.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# GLAZBA — Pjesmice, brojalice, kajdanka, instrumenti
# ═══════════════════════════════════════════════════════════════

def music_corner(request):
    """Glazbeni kutak — pjesmice, brojalice, kajdanka, instrumenti."""
    lang = _lang(request)
    return render(request, "memio_world/music_corner.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# SPORT — Vježbe, pokret, yoga za djecu
# ═══════════════════════════════════════════════════════════════

def sports_corner(request):
    """Sport i pokret — vježbe, yoga za djecu, ples."""
    lang = _lang(request)
    return render(request, "memio_world/sports_corner.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# VIRTUALNA TRGOVINA — Financijska pismenost
# ═══════════════════════════════════════════════════════════════

def virtual_shop(request):
    """Virtualna trgovina — nauči novac, kupovanje, kusur."""
    lang = _lang(request)
    return render(request, "memio_world/virtual_shop.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# SPACED REPETITION — Leitner kutije vizualno
# ═══════════════════════════════════════════════════════════════

def flashcards(request):
    """Kartice za ponavljanje — Leitner sustav."""
    lang = _lang(request)
    return render(request, "memio_world/flashcards.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# AZILI + DJECA — NO LIMIT projekt, djeca i azili za životinje
# ═══════════════════════════════════════════════════════════════

def shelter_program(request):
    """Azili + Djeca — NO LIMIT projekt povezuje djecu s azilima."""
    lang = _lang(request)
    return render(request, "memio_world/shelter_program.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# OBITELJSKO STABLO — Interaktivno učenje o obitelji
# ═══════════════════════════════════════════════════════════════

def family_tree(request):
    """Obiteljsko stablo — tko je tko u obitelji, crtanje, intervju bake/djeda."""
    lang = _lang(request)
    return render(request, "memio_world/family_tree.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# KALENDAR — Godišnji, sezonski, adventski
# ═══════════════════════════════════════════════════════════════

def calendar_page(request):
    """Interaktivni kalendar — mjeseci, godišnja doba, praznici."""
    lang = _lang(request)
    return render(request, "memio_world/calendar_page.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# NATJEČAJ — Naj priča, naj igra, naj...
# ═══════════════════════════════════════════════════════════════

def contest_page(request):
    """Natječaj — pošalji svoju priču, glasaj za najbolju."""
    lang = _lang(request)
    return render(request, "memio_world/contest_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# ZANIMANJA — Što želiš biti kad odrasteš?
# ═══════════════════════════════════════════════════════════════

def careers_page(request):
    """Zanimanja — istraži profesije kroz igru."""
    lang = _lang(request)
    return render(request, "memio_world/careers_page.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# VIRTUALNI DOGAĐAJI — Zajedničke aktivnosti
# ═══════════════════════════════════════════════════════════════

def events_page(request):
    """Virtualni događaji — čitaonica, kviz noć, talent show."""
    lang = _lang(request)
    return render(request, "memio_world/events_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# BOJE — Učenje boja, miješanje, kviz
# ═══════════════════════════════════════════════════════════════

def colors_game(request):
    """Boje — učenje 12 boja, miješanje boja, kviz prepoznavanja."""
    lang = _lang(request)
    return render(request, "memio_world/colors_game.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# GEOMETRIJSKI OBLICI — Učenje oblika, kviz, gradnja
# ═══════════════════════════════════════════════════════════════

def shapes_game(request):
    """Geometrijski oblici — 8 oblika, pronađi oblik kviz, shape builder."""
    lang = _lang(request)
    return render(request, "memio_world/shapes_game.html", {"nav": "learn", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# MEMIO ŠKOLA — Strukturirani put od mulca do znalca
# ═══════════════════════════════════════════════════════════════

def memio_school(request):
    """Memio Škola — razine, zadaci, diplome, napredak."""
    lang = _lang(request)
    return render(request, "memio_world/memio_school.html", {"nav": "home", "lang": lang})


def diploma_page(request):
    """Diploma generator — certificat za završenu razinu."""
    lang = _lang(request)
    return render(request, "memio_world/diploma_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# MEMIO MASKOTA — Pitaj Memia, on zna SVE
# ═══════════════════════════════════════════════════════════════

def memio_mascot(request):
    """Memio maskota — interaktivni asistent koji odgovara na pitanja."""
    lang = _lang(request)
    return render(request, "memio_world/memio_mascot.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# BUDDY PAIR — Pronađi prijatelja istomišljenika
# ═══════════════════════════════════════════════════════════════

def buddy_finder(request):
    """Pronađi prijatelja — spajanje po interesima."""
    lang = _lang(request)
    return render(request, "memio_world/buddy_finder.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# PARENT ONBOARDING — Zašto i kako omogućiti djetetu
# ═══════════════════════════════════════════════════════════════

def parent_onboarding(request):
    """Onboarding za roditelje — korak po korak."""
    lang = _lang(request)
    return render(request, "memio_world/parent_onboarding.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# DIGITALNI SPOMENAR — Knjiga sjećanja
# ═══════════════════════════════════════════════════════════════

def spomenar_page(request):
    """Digitalni spomenar — djeca zapisuju životne uspomene."""
    lang = _lang(request)
    return render(request, "memio_world/spomenar_page.html", {"nav": "family", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# DJEČJI PORTAL IDEJA — Djeca predlažu i glasaju
# ═══════════════════════════════════════════════════════════════

def kids_ideas(request):
    """Dječji portal ideja — predloži ideju za PLAY.EU i glasaj."""
    lang = _lang(request)
    return render(request, "memio_world/kids_ideas.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# PAYMENT — Plaćanje i pretplata
# ═══════════════════════════════════════════════════════════════

def payment_page(request):
    """Stranica za plaćanje — svi načini plaćanja."""
    lang = _lang(request)
    return render(request, "memio_world/payment_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# REFERRAL — Preporuči prijatelju, zaradi
# ═══════════════════════════════════════════════════════════════

def referral_page(request):
    """Referral program — preporuči i oboje dobijete bonus."""
    lang = _lang(request)
    return render(request, "memio_world/referral_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# DIGITALNA KNJIŽNICA — Sve knjige na jednom mjestu
# ═══════════════════════════════════════════════════════════════

def digital_library(request):
    """Digitalna knjižnica — veza s NO LIMIT knjižnicom."""
    lang = _lang(request)
    from memio_world.play_eu_models import ParallelStory
    stories = ParallelStory.objects.using('memio_world').filter(is_published=True).order_by('country_of_origin', 'title_hr')
    return render(request, "memio_world/digital_library.html", {"nav": "read", "lang": lang, "stories": stories})


# ═══════════════════════════════════════════════════════════════
# PEDAGOŠKE SMJERNICE — Naš pristup
# ═══════════════════════════════════════════════════════════════

def pedagogy_page(request):
    """Pedagoške smjernice — metode, ideje, filozofija."""
    lang = _lang(request)
    return render(request, "memio_world/pedagogy_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# UPUTE — Kako koristiti platformu
# ═══════════════════════════════════════════════════════════════

def help_page(request):
    """Upute za korištenje — glasovne i tekst."""
    lang = _lang(request)
    return render(request, "memio_world/help_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# PRAVNI DOKUMENTI — ToS, Privacy, GDPR
# ═══════════════════════════════════════════════════════════════

def legal_page(request):
    """Pravni dokumenti — Uvjeti korištenja, Privatnost, GDPR."""
    lang = _lang(request)
    return render(request, "memio_world/legal_page.html", {"nav": "home", "lang": lang})


# ═══════════════════════════════════════════════════════════════
# AMBASADORSKI PROGRAM — Poziv školama i knjižnicama
# ═══════════════════════════════════════════════════════════════

def ambassador_page(request):
    """Ambasadorski program — postani PLAY.EU ambasador u svojoj zemlji."""
    lang = _lang(request)
    return render(request, "memio_world/ambassador_page.html", {"nav": "home", "lang": lang})
