"""
PLAY.EU Comfort Engine — Emocionalna sigurnost djece
=====================================================

Platforma koja je uz dijete i kad spava.
Platforma koja tješi, nasmijava, i čuva.

3 stupa:
  DreamGuard    → noćne more, tumačenje snova, bakino tješenje
  ComfortCard   → "boli me" / "tužan sam" → baka tješi, mama grli
  JokeBox       → pošalice, zagonetke, igre riječima — osmijeh na lice

Zakonski okvir:
  - EU Copyright Directive 2019/790: sadržaj je ORIGINALAN, ne preuzet
  - GDPR čl. 8: dječji podaci — parent consent, minimalna kolekcija
  - DSA čl. 28: NEMA profiliranja djece, NEMA reklama, NEMA dark patterns
  - JuSchG (DE): sadržaj samoclassificiran kao "bez dobnog ograničenja"
  - AVMSD (EU): audio sadržaj za djecu — mora biti prikladan, bez nasilja
  - Etički standard: NIKAD ne zamjenjujemo terapeuta/liječnika.
    Uvijek usmjeravamo na roditelja. Uvijek.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

# ════════════════════════════════════════════════════════════════
# LEGAL COMPLIANCE — Zakonska usklađenost
# ════════════════════════════════════════════════════════════════


class LegalCompliance(models.Model):
    """
    Praćenje zakonske usklađenosti svakog sadržaja.

    SVAKI sadržaj na platformi MORA imati:
    1. Provjeru autorskih prava (source + license)
    2. Dobnu prikladnost (age_rating)
    3. Edukativnu validaciju (educational_reviewed)
    4. GDPR status (no_personal_data)

    Ovo nije birokratija — ovo je ZAŠTITA.
    Jedan krivi sadržaj = kraj platforme.
    """

    AGE_RATING_CHOICES = [
        ("all", _("Svi uzrasti (0+)")),
        ("3plus", _("3+")),
        ("6plus", _("6+")),
        ("10plus", _("10+")),
        ("12plus", _("12+")),
    ]

    LICENSE_CHOICES = [
        ("original", _("PLAY.EU original — sva prava zadržana")),
        ("cc0", _("CC0 — javna domena")),
        ("cc_by", _("CC BY 4.0 — navođenje autora")),
        ("cc_by_sa", _("CC BY-SA 4.0 — navođenje + dijeli pod istim")),
        ("public_domain", _("Javna domena (autor umro 70+ godina)")),
        ("fair_use_edu", _("Obrazovna uporaba — čl. 5 Directive 2019/790")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Koji sadržaj
    content_model = models.CharField(max_length=50, help_text="ParallelStory, WisdomEntry, JokeEntry...")
    content_id = models.UUIDField()

    # Autorska prava
    license_type = models.CharField(max_length=30, choices=LICENSE_CHOICES)
    source_attribution = models.TextField(blank=True, help_text="Navođenje izvora ako je potrebno")
    copyright_verified = models.BooleanField(default=False)
    copyright_verified_by = models.CharField(max_length=100, blank=True)
    copyright_verified_at = models.DateTimeField(null=True, blank=True)

    # Dobna prikladnost
    age_rating = models.CharField(max_length=10, choices=AGE_RATING_CHOICES, default="all")
    age_rating_reason = models.TextField(blank=True)

    # Edukativna validacija
    educational_reviewed = models.BooleanField(default=False)
    educational_reviewer = models.CharField(max_length=100, blank=True, help_text="Ime pedagoga/učitelja")

    # GDPR
    contains_personal_data = models.BooleanField(default=False)
    gdpr_note = models.TextField(blank=True)

    # Napomene
    country_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text="Zemlje u kojima sadržaj NIJE primjenjiv (npr. Saint-Exupéry u FR)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_legal_compliance"
        indexes = [
            models.Index(fields=["content_model", "content_id"]),
        ]
        verbose_name = _("Zakonska usklađenost")
        verbose_name_plural = _("Zakonske usklađenosti")

    def __str__(self):
        verified = "VERIFIED" if self.copyright_verified else "PENDING"
        return f"[{verified}] {self.content_model}#{self.content_id}"


# ════════════════════════════════════════════════════════════════
# DREAM GUARD — Noćne more, snovi, tješenje
# ════════════════════════════════════════════════════════════════


class DreamGuard(models.Model):
    """
    Kad se dijete probudi od noćne more — platforma je tu.

    NE dijagnosticiramo. NE liječimo. NE zamjenjujemo roditelja.
    ALI:
    - Objašnjavamo da su snovi NORMALNI
    - Bakina priča umiruje
    - Tehnika disanja pomaže
    - Meko svjetlo i topli zvuk smiruju

    Ako se noćne more ponavljaju — predlažemo roditelju razgovor s pedijatrom.
    MI NISMO TERAPEUTI. Mi smo digitalna baka koja tješi.

    Zakonski: ovo je EDUKATIVNI sadržaj o snovima, ne medicinski savjet.
    Disclaimer je obavezan na svakom ekranu.
    """

    DREAM_TYPE_CHOICES = [
        ("nightmare", _("Noćna mora")),
        ("scary", _("Strašan san")),
        ("falling", _("San o padanju")),
        ("chasing", _("Netko me juri")),
        ("lost", _("Izgubio/la sam se")),
        ("monster", _("Čudovište")),
        ("dark", _("Mrak")),
        ("water", _("Voda / utapanje")),
        ("school", _("Škola / ispit")),
        ("general_fear", _("Općeniti strah")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream_type = models.CharField(max_length=20, choices=DREAM_TYPE_CHOICES, db_index=True)

    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    # Bakino tješenje — SRCE ovog modela
    grandma_comfort = models.TextField(
        help_text="Bakine riječi utjehe — toplo, nježno, sigurno",
    )
    mama_comfort = models.TextField(
        blank=True,
        help_text="Mamina verzija — praktičnija, bliža",
    )

    # Objašnjenje (za dijete)
    explanation_for_child = models.TextField(
        help_text="Zašto se ovo događa — jednostavnim riječima, bez straha",
    )

    # Tehnika smirivanja
    calming_technique = models.TextField(
        help_text="Konkretna tehnika: disanje, brojanje, zamišljanje sigurnog mjesta...",
    )

    # Audio (ako postoji)
    audio_comfort = models.FileField(upload_to="play_eu/comfort/", blank=True, help_text="Umirujuća audio snimka")

    # Vizualno
    warm_color = models.CharField(max_length=7, default="#FFF8E7", help_text="Topla boja pozadine")

    # Kada usmjeriti na roditelja/stručnjaka
    escalation_note = models.TextField(
        blank=True,
        help_text="Kad predložiti roditelju razgovor s pedijatrom (npr. ponavljanje 3+ noći)",
    )

    # Zakonski disclaimer
    DISCLAIMER = (
        "Ovaj sadržaj je edukativnog karaktera i ne zamjenjuje medicinski savjet. "
        "Ako se noćne more ponavljaju ili uzrokuju značajan stres, "
        "razgovarajte s pedijatrom ili dječjim psihologom."
    )

    # Meta
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_dream_guard"
        ordering = ["dream_type"]
        verbose_name = _("Dream Guard")
        verbose_name_plural = _("Dream Guard zapisi")

    def __str__(self):
        return f"[{self.get_dream_type_display()}] {self.title}"


# ════════════════════════════════════════════════════════════════
# COMFORT CARD — Tješenje za svakodnevne situacije
# ════════════════════════════════════════════════════════════════


class ComfortCard(models.Model):
    """
    "Boli me" / "Tužan sam" / "Svađao sam se s prijateljem"

    Baka tješi. Mama grli. Djed objašnjava.
    Konkretan savjet + emocionalna podrška + tehnika.

    NIKAD ne umanjujemo djetetov osjećaj.
    "Ne budi plačljiv" — NIKAD.
    "Razumijem da te boli. Hajde da vidimo kako možemo pomoći." — UVIJEK.
    """

    SITUATION_CHOICES = [
        ("hurt_knee", _("Udario/la sam se")),
        ("sad", _("Tužan/na sam")),
        ("angry", _("Ljut/a sam")),
        ("fight_friend", _("Posvađao/la sam se s prijateljem")),
        ("scared", _("Strah me")),
        ("lonely", _("Osjećam se sam/a")),
        ("bullied", _("Netko me zadirkuje")),
        ("bad_grade", _("Dobio/la sam lošu ocjenu")),
        ("parents_fight", _("Mama i tata se svađaju")),
        ("moving", _("Selimo se / mijenjam školu")),
        ("lost_pet", _("Moj ljubimac je umro")),
        ("miss_grandma", _("Nedostaje mi baka/djed")),
        ("cant_sleep", _("Ne mogu zaspati")),
        ("jealous", _("Ljubomoran/na sam na brata/sestru")),
        ("embarrassed", _("Sramim se")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    situation = models.CharField(max_length=30, choices=SITUATION_CHOICES, db_index=True)

    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    # 3 glasa utjehe
    grandma_says = models.TextField(help_text="Baka — topla, priča, zagrljaj riječima")
    mama_says = models.TextField(blank=True, help_text="Mama — praktična, bliska, rješenje")
    grandpa_says = models.TextField(blank=True, help_text="Djed — mudar, iskustvo, ponekad šala")

    # Konkretni koraci
    what_to_do = models.TextField(help_text="1-2-3 koraka: što dijete MOŽE učiniti")
    what_not_to_do = models.TextField(blank=True, help_text="Što NE raditi (i zašto)")

    # Priča koja pomaže
    healing_story = models.TextField(
        blank=True,
        help_text="Kratka priča o djetetu koje je prošlo isto i kako je prevladalo",
    )

    # Meta
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=12)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_comfort_card"
        ordering = ["situation"]
        verbose_name = _("Kartica utjehe")
        verbose_name_plural = _("Kartice utjehe")

    def __str__(self):
        return f"[{self.get_situation_display()}] {self.title}"


# ════════════════════════════════════════════════════════════════
# JOKE BOX — Pošalice, zagonetke, igre riječima
# ════════════════════════════════════════════════════════════════


class JokeEntry(models.Model):
    """
    Osmijeh na lice. Svaki dan. Bez iznimke.

    Tipovi:
    - Pošalica (Zašto patka nosi kišobran? Zato što nema ruke da drži!)
    - Zagonetka (Što ima glavu a nema tijelo? — Čavao)
    - Igra riječima (Kako se zove riba koja pjeva? — Tuna Turner)
    - Knock-knock (Tko je? — Banana. Banana tko? — Banana split!)
    - Bakina šala (Djed kaže: Kad sam bio mali, hodao sam 10 km u školu.
                   Baka kaže: Uzbrdo. U oba smjera. Po snijegu. Bosonog.)
    - Činjenični humor (Puževi spavaju i do 3 godine. I meni se ponekad tako čini.)

    Zakonski: SVE šale su originalne ili public domain.
    Nikad na račun: rase, spola, vjere, invaliditeta, tjelesnog izgleda.
    Humor SPAJA, ne DIJELI.
    """

    JOKE_TYPE_CHOICES = [
        ("joke", _("Pošalica")),
        ("riddle", _("Zagonetka")),
        ("wordplay", _("Igra riječima")),
        ("knock_knock", _("Tko je? Tko je?")),
        ("grandma_joke", _("Bakina/Djedova šala")),
        ("fun_fact", _("Smiješna činjenica")),
        ("tongue_twister", _("Brzalica")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    joke_type = models.CharField(max_length=20, choices=JOKE_TYPE_CHOICES)

    # Tekst
    setup = models.TextField(help_text="Početak šale / pitanje zagonetke")
    punchline = models.TextField(help_text="Poanta / odgovor")

    # Višejezičnost
    setup_de = models.TextField(blank=True)
    punchline_de = models.TextField(blank=True)
    setup_en = models.TextField(blank=True)
    punchline_en = models.TextField(blank=True)

    # Meta
    age_min = models.PositiveSmallIntegerField(default=4)
    age_max = models.PositiveSmallIntegerField(default=12)
    tags = models.JSONField(default=list, blank=True, help_text="['životinje', 'škola', 'hrana']")
    is_published = models.BooleanField(default=False)
    laugh_count = models.PositiveIntegerField(default=0, help_text="Koliko djece se nasmijalo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_joke"
        ordering = ["-laugh_count"]
        verbose_name = _("Šala")
        verbose_name_plural = _("Šale")

    def __str__(self):
        return f"[{self.get_joke_type_display()}] {self.setup[:50]}"
