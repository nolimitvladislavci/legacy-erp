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


# ════════════════════════════════════════════════════════════════
# RAGE ENGINE — Upravljanje bijesom (Magistar pedagogije)
# ════════════════════════════════════════════════════════════════


class EmotionCheckIn(models.Model):
    """
    Dnevni check-in emocija djeteta.

    Pedagoški temelj:
    - Zones of Regulation (Leah Kuypers, 2011)
    - RULER Approach (Yale Center for Emotional Intelligence)
    - CASEL SEL Framework — Self-Awareness pillar

    Dijete NE MOŽE kontrolirati emocije koje NE PREPOZNAJE.
    Prvo imenujemo. Onda dišemo. Onda razmišljamo.
    """

    EMOTION_CHOICES = [
        ("furious", "Jako ljut 😡"),
        ("angry", "Ljut 😤"),
        ("frustrated", "Frustriran 😣"),
        ("anxious", "Zabrinut 😰"),
        ("sad", "Tužan 😢"),
        ("neutral", "Ok 😐"),
        ("happy", "Veseo 🙂"),
        ("very_happy", "Jako veseo 😊"),
        ("ecstatic", "Presretan 😄"),
    ]
    TRIGGER_CHOICES = [
        ("sibling", "Svađa s bratom/sestrom"),
        ("school", "Škola / zadaća"),
        ("friend", "Prijatelj"),
        ("tired", "Umor"),
        ("hungry", "Glad"),
        ("unfair", "Nepravda"),
        ("lost_game", "Izgubio igru"),
        ("scared", "Strah"),
        ("lonely", "Usamljenost"),
        ("other", "Nešto drugo"),
    ]
    ACTION_CHOICES = [
        ("breathing", "Disao/la duboko"),
        ("counting", "Brojao/la do 10"),
        ("walked_away", "Odšetao/la se"),
        ("talked", "Pričao/la s nekim"),
        ("cried", "Plakao/la"),
        ("yelled", "Vikao/la"),
        ("hit", "Udario/la"),
        ("pillow", "Stisnuo/la jastuk"),
        ("drew", "Nacrtao/la bijes"),
        ("music", "Slušao/la glazbu"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="emotion_checkins",
        null=True,
        blank=True,
    )
    session_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Za anonimne check-ine bez ChildProfile",
    )
    emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    intensity = models.PositiveSmallIntegerField(
        default=5,
        help_text="1-10 intenzitet emocije",
    )
    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES, blank=True)
    action_taken = models.CharField(max_length=30, choices=ACTION_CHOICES, blank=True)
    reflection_text = models.TextField(blank=True)
    reflection_audio = models.FileField(upload_to="play_eu/emotions/", blank=True)
    calming_technique_used = models.CharField(max_length=30, blank=True)
    felt_better_after = models.BooleanField(null=True)
    # Body Map — gdje u tijelu osjeti emociju (budućnost #1)
    body_zones = models.JSONField(
        default=list,
        blank=True,
        help_text='["chest","stomach","fists","head","throat"] — gdje pecka/gori',
    )
    # Empathy Mirror — kako se drugi osjeća (budućnost #3)
    other_person_feeling = models.CharField(
        max_length=20,
        blank=True,
        choices=EMOTION_CHOICES,
        help_text="Kako misliš da se druga osoba osjeća?",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_emotion_checkin"
        ordering = ["-created_at"]
        verbose_name = _("Emotion Check-In")
        verbose_name_plural = _("Emotion Check-Ins")

    def __str__(self):
        return f"{self.get_emotion_display()} — {self.date}"

    @property
    def needs_calming(self):
        return self.emotion in ("furious", "angry", "anxious")


class CalmingExercise(models.Model):
    """
    Tehnika smirivanja — svaka ima animaciju, bakine riječi, i timer.

    Izvori:
    - Square Breathing (US Navy SEALs — 4-4-4-4)
    - Progressive Muscle Relaxation (Jacobson, 1938)
    - Mindfulness for Children (Kabat-Zinn adapted)
    - STOP Technique (DBT for adolescents)
    """

    TECHNIQUE_CHOICES = [
        ("breathing", "Duboko disanje"),
        ("counting", "Brojanje unatrag"),
        ("volcano", "Vulkan vježba"),
        ("balloon", "Balon se napuhuje"),
        ("jellyfish", "Meduza plutanje"),
        ("turtle", "Kornjačina ljuska"),
        ("traffic_light", "Semafor"),
        ("body_scan", "Skeniranje tijela"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technique = models.CharField(max_length=30, choices=TECHNIQUE_CHOICES, unique=True)
    title = models.CharField(max_length=200)
    title_de = models.CharField(max_length=200, blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    instruction_text = models.TextField(help_text="Korak-po-korak upute (HR)")
    instruction_text_de = models.TextField(blank=True)
    instruction_text_en = models.TextField(blank=True)
    grandma_voice = models.TextField(
        blank=True,
        help_text="Bakine riječi — toplo, nježno, sigurno",
    )
    grandma_voice_de = models.TextField(blank=True)
    grandma_voice_en = models.TextField(blank=True)
    duration_seconds = models.PositiveSmallIntegerField(default=60)
    animation_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"type":"balloon","inhale_sec":4,"exhale_sec":4,"cycles":5,"color":"#87CEEB"}',
    )
    emoji = models.CharField(max_length=10, default="🎈")
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=12)
    sort_order = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=False)
    times_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_calming_exercise"
        ordering = ["sort_order"]
        verbose_name = _("Vježba smirivanja")
        verbose_name_plural = _("Vježbe smirivanja")

    def __str__(self):
        return f"{self.emoji} {self.title}"

    def get_title(self, lang="hr"):
        if lang == "de" and self.title_de:
            return self.title_de
        if lang == "en" and self.title_en:
            return self.title_en
        return self.title


class ConflictScenario(models.Model):
    """
    Budućnost #2 — Interaktivni scenariji rješavanja konflikata.

    Pedagoški temelj:
    - Second Step Program (Committee for Children)
    - PATHS curriculum (Promoting Alternative THinking Strategies)
    - Collaborative Problem Solving (Dr. Ross Greene)

    Dijete čita situaciju → bira odgovor → vidi posljedice.
    Nema "krivog" odgovora — ali svaki ima RAZLIČITE posljedice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    title_de = models.CharField(max_length=200, blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    situation = models.TextField(help_text="Opis situacije (HR)")
    situation_de = models.TextField(blank=True)
    situation_en = models.TextField(blank=True)
    emoji = models.CharField(max_length=10, default="🤔")
    # Opcije i posljedice kao JSON
    choices = models.JSONField(
        default=list,
        help_text="""[
            {"text":"Viknem na njega","emoji":"😡","consequence":"Prijatelj se rasplače i ode.","score":-1,"skill":"impulse_control"},
            {"text":"Kažem: Ljut sam jer...","emoji":"💬","consequence":"Prijatelj sluša i kaže oprosti.","score":2,"skill":"i_message"},
            {"text":"Odšetam se","emoji":"🚶","consequence":"Smiriš se, ali problem ostaje.","score":1,"skill":"self_regulation"}
        ]""",
    )
    choices_de = models.JSONField(default=list, blank=True)
    choices_en = models.JSONField(default=list, blank=True)
    age_min = models.PositiveSmallIntegerField(default=5)
    age_max = models.PositiveSmallIntegerField(default=12)
    is_published = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_conflict_scenario"
        ordering = ["sort_order"]
        verbose_name = _("Scenarij konflikta")
        verbose_name_plural = _("Scenariji konflikata")

    def __str__(self):
        return f"{self.emoji} {self.title}"
