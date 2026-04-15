"""
PLAY.EU Kurikulum 2.0 — Učenje kroz život
===========================================
Djeca ne uče predmete. Djeca uče ŽIVJETI.

Arhitektura:
  LearningPath      → put učenja po dobi (1. razred, 2. razred...)
  LifeLesson        → jedna lekcija (prometni znak, bakina mudrost, opasna riječ...)
  ContentLink       → povezuje priču + karticu + kviz + lekciju u smislenu cjelinu
  WisdomEntry       → "Što bi baka rekla" — generacijska mudrost
  SafetyTopic       → opasne situacije (promet, internet, nepoznati ljudi...)

Filozofija:
  - Nema reklama. NIKAD.
  - Sadržaj koji roditelji RADO plate jer čuva njihovu djecu.
  - Baka i djed NISU dekoracija — oni su GLAS iskustva.
  - Svaki kviz je lekcija. Svaka lekcija je priča. Svaka priča je igra.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

# ════════════════════════════════════════════════════════════════
# LEARNING PATH — Put učenja po dobi i razredu
# ════════════════════════════════════════════════════════════════


class LearningPath(models.Model):
    """
    Kurikularni put — prati školski sustav ali dodaje ono što škola ne uči:
    promet, internet sigurnost, emocionalna inteligencija, životne vještine.
    """

    AGE_GROUP_CHOICES = [
        ("preschool", _("Predškolski (3-6)")),
        ("grade_1_2", _("1.-2. razred (6-8)")),
        ("grade_3_4", _("3.-4. razred (8-10)")),
        ("grade_5_6", _("5.-6. razred (10-12)")),
        ("grade_7_8", _("7.-8. razred (12-14)")),
    ]

    SUBJECT_CHOICES = [
        # Školski predmeti
        ("croatian", _("Hrvatski jezik")),
        ("math", _("Matematika")),
        ("nature", _("Priroda i društvo")),
        ("history", _("Povijest")),
        ("geography", _("Zemljopis")),
        ("music", _("Glazbena kultura")),
        ("art", _("Likovna kultura")),
        ("languages", _("Strani jezici")),
        # Životne vještine — ONO ŠTO ŠKOLA NE UČI
        ("traffic_safety", _("Sigurnost u prometu")),
        ("internet_safety", _("Sigurnost na internetu")),
        ("emotional_iq", _("Emocionalna inteligencija")),
        ("first_aid", _("Prva pomoć")),
        ("ecology", _("Ekologija i priroda")),
        ("money_basics", _("Osnove financija")),
        ("cooking_basics", _("Kuhanje za početnike")),
        ("grandma_wisdom", _("Bakina mudrost")),
        ("cultural_heritage", _("Kulturna baština")),
        ("digital_citizenship", _("Digitalno građanstvo")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)
    age_group = models.CharField(max_length=20, choices=AGE_GROUP_CHOICES, db_index=True)
    subject = models.CharField(max_length=30, choices=SUBJECT_CHOICES, db_index=True)
    description = models.TextField(blank=True)
    icon_emoji = models.CharField(max_length=10, blank=True, help_text="Emoji ikona za path")
    color = models.CharField(max_length=7, default="#4A90D9")
    position = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_learning_path"
        ordering = ["age_group", "position"]
        verbose_name = _("Put učenja")
        verbose_name_plural = _("Putovi učenja")

    def __str__(self):
        return f"[{self.get_age_group_display()}] {self.title}"


# ════════════════════════════════════════════════════════════════
# LIFE LESSON — Lekcije za život
# ════════════════════════════════════════════════════════════════


class LifeLesson(models.Model):
    """
    Jedna lekcija. Nije suhi udžbenik — to je PRIČA + MUDROST + KVIZ u jednom.

    Primjeri:
    - "Zašto ne trčimo preko ceste" (promet, 1. razred)
    - "Što znači STOP znak" (promet, predškolski)
    - "Netko mi šalje čudne poruke" (internet, 5. razred)
    - "Baka kaže: tko rano rani..." (mudrost)
    - "Kako se ponašati na romobilu" (promet, 3. razred)
    """

    LESSON_TYPE_CHOICES = [
        ("story_lesson", _("Priča s poukom")),
        ("safety_rule", _("Sigurnosno pravilo")),
        ("wisdom", _("Bakina/Djedova mudrost")),
        ("skill", _("Praktična vještina")),
        ("quiz_lesson", _("Lekcija kroz kviz")),
        ("scenario", _("Što bi ti napravio/la?")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="lessons")
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES)

    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    # Sadržaj
    content_hr = models.TextField(help_text="Tekst lekcije na HR")
    content_de = models.TextField(blank=True)
    content_en = models.TextField(blank=True)

    # Bakina/Djedova mudrost — UVIJEK prisutna
    grandma_says = models.TextField(blank=True, help_text="Što bi baka rekla o ovoj temi")
    grandpa_says = models.TextField(blank=True, help_text="Što bi djed rekao (može se ne slagati!)")
    grandparents_agree = models.BooleanField(
        default=True,
        help_text="Slažu li se baka i djed? Ako NE — to je lekcija o različitim mišljenjima!",
    )

    # Vizualno
    illustration_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)

    # Veza na Heritage/Story sadržaj
    related_story = models.ForeignKey(
        "memio_world.ParallelStory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lessons",
    )
    related_quiz = models.ForeignKey(
        "memio_world.Quiz",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lessons",
    )

    # Meta
    position = models.PositiveSmallIntegerField(default=0)
    difficulty = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    estimated_minutes = models.PositiveSmallIntegerField(default=5)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_life_lesson"
        ordering = ["path", "position"]
        verbose_name = _("Životna lekcija")
        verbose_name_plural = _("Životne lekcije")

    def __str__(self):
        return f"[{self.path.get_subject_display()}] {self.title}"


# ════════════════════════════════════════════════════════════════
# WISDOM ENTRY — Bakina i Djedova mudrost
# ════════════════════════════════════════════════════════════════


class WisdomEntry(models.Model):
    """
    "Što bi baka rekla?"

    Ovo NIJE dekoracija. Ovo je SRCE platforme.
    Baka i djed su glas iskustva koji digitalni svijet pokušava ugasiti.
    Mi ga pojačavamo.

    Svaka mudrost ima:
    - Bakinu verziju (nježna, emotivna, praktična)
    - Djedovu verziju (direktna, iskustvena, ponekad drugačija)
    - Moderni kontekst (kako se ovo primjenjuje danas)
    - Priča iz života (anegdota koja to ilustrira)
    """

    CATEGORY_CHOICES = [
        ("safety", _("Sigurnost")),
        ("manners", _("Bonton i ponašanje")),
        ("health", _("Zdravlje")),
        ("nature", _("Priroda")),
        ("friendship", _("Prijateljstvo")),
        ("honesty", _("Iskrenost")),
        ("courage", _("Hrabrost")),
        ("patience", _("Strpljivost")),
        ("money", _("Novac i štednja")),
        ("food", _("Hrana i kuhanje")),
        ("weather", _("Vrijeme i godišnja doba")),
        ("proverb", _("Poslovica")),
        ("tradition", _("Tradicija")),
        ("digital", _("Digitalni svijet")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)

    # Tekst
    title = models.CharField(max_length=300, help_text="Naslov/poslovica")
    grandma_version = models.TextField(help_text="Bakina verzija — nježna, topla, priča")
    grandpa_version = models.TextField(help_text="Djedova verzija — direktna, iskustvo, savjet")
    they_agree = models.BooleanField(
        default=True,
        help_text="Ako se NE slažu — to uči djecu da je OK imati različita mišljenja",
    )
    modern_context = models.TextField(
        blank=True,
        help_text="Kako se ova mudrost primjenjuje u 2026. godini",
    )
    life_story = models.TextField(
        blank=True,
        help_text="Kratka anegdota iz života koja ilustrira poantu",
    )

    # Višejezičnost
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    # Meta
    age_min = models.PositiveSmallIntegerField(default=4)
    age_max = models.PositiveSmallIntegerField(default=12)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_wisdom"
        ordering = ["category", "title"]
        verbose_name = _("Bakina mudrost")
        verbose_name_plural = _("Bakine mudrosti")

    def __str__(self):
        agree = "slazu se" if self.they_agree else "NE SLAZU SE"
        return f"[{self.get_category_display()}] {self.title} ({agree})"


# ════════════════════════════════════════════════════════════════
# SAFETY TOPIC — Opasne situacije
# ════════════════════════════════════════════════════════════════


class SafetyTopic(models.Model):
    """
    Opasne riječi, situacije, scenariji.

    Ovo je ono što roditelje drži budnima noću:
    - Promet: bicikl bez kacige, romobil na cesti, trčanje preko ceste
    - Internet: nepoznati koji traže slike, cyberbullying, lažni profili
    - Stvarni svijet: nepoznati nudi slatkiše, vatra, utapanje
    - Digitalno: pretjerano korištenje ekrana, gambling igre, in-app kupnje

    Svaki topic ima:
    - Scenarij (što se događa)
    - Ispravnu reakciju (što napraviti)
    - Krivu reakciju (što NE napraviti i zašto)
    - Koga nazvati (roditelj, policija, vatrogasci)
    """

    DANGER_CATEGORY_CHOICES = [
        ("traffic_pedestrian", _("Promet — Pješak")),
        ("traffic_bicycle", _("Promet — Bicikl")),
        ("traffic_scooter", _("Promet — Romobil")),
        ("traffic_signs", _("Prometni znakovi")),
        ("traffic_rules", _("Prometna pravila")),
        ("internet_strangers", _("Internet — Nepoznati ljudi")),
        ("internet_cyberbully", _("Internet — Cyberbullying")),
        ("internet_privacy", _("Internet — Privatnost")),
        ("internet_screens", _("Internet — Pretjerano korištenje")),
        ("internet_fake", _("Internet — Lažne vijesti i profili")),
        ("stranger_danger", _("Nepoznati ljudi u stvarnom svijetu")),
        ("fire_safety", _("Požar i vatrogasci")),
        ("water_safety", _("Voda i utapanje")),
        ("first_aid_basic", _("Osnove prve pomoći")),
        ("emotional_danger", _("Emocionalno nasilje")),
        ("peer_pressure", _("Pritisak vršnjaka")),
    ]

    SEVERITY_CHOICES = [
        (1, _("Informativno")),
        (2, _("Važno")),
        (3, _("Kritično — zapamti zauvijek")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    danger_category = models.CharField(max_length=30, choices=DANGER_CATEGORY_CHOICES, db_index=True)
    severity = models.PositiveSmallIntegerField(choices=SEVERITY_CHOICES, default=2)

    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    # Scenarij
    scenario = models.TextField(help_text="Opis situacije — što se događa (prilagođeno dobi)")
    correct_action = models.TextField(help_text="Što TREBA napraviti")
    wrong_action = models.TextField(help_text="Što NE treba napraviti i ZAŠTO")
    who_to_call = models.CharField(max_length=200, blank=True, help_text="Roditelj, 112, policija...")

    # Baka/Djed perspektiva
    grandma_advice = models.TextField(blank=True, help_text="Bakina perspektiva")
    grandpa_advice = models.TextField(blank=True, help_text="Djedova perspektiva")

    # Vizualno
    illustration_url = models.URLField(blank=True)
    traffic_sign_image = models.ImageField(upload_to="play_eu/safety/", blank=True)

    # Meta
    age_min = models.PositiveSmallIntegerField(default=4)
    age_max = models.PositiveSmallIntegerField(default=14)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_safety_topic"
        ordering = ["danger_category", "-severity"]
        verbose_name = _("Sigurnosna tema")
        verbose_name_plural = _("Sigurnosne teme")

    def __str__(self):
        sev = {1: "INFO", 2: "VAŽNO", 3: "KRITIČNO"}.get(self.severity, "?")
        return f"[{sev}] {self.title}"


# ════════════════════════════════════════════════════════════════
# CONTENT LINK — Povezuje sve u smislene cjeline
# ════════════════════════════════════════════════════════════════


class ContentLink(models.Model):
    """
    Ljepilo koje spaja SVE sadržaje u smislenu cjelinu.

    Primjer: "Crvenkapica" priča povezuje se sa:
    - SafetyTopic: "Ne razgovaraj s nepoznatima"
    - WisdomEntry: "Slušaj mamu i tatu"
    - HeritageCard: "Vuk" iz bestiarija
    - Quiz: "Što bi Crvenkapica trebala napraviti?"
    - LearningPath: "Sigurnost — predškolski"
    """

    LINK_TYPE_CHOICES = [
        ("story_to_safety", _("Priča → Sigurnosna lekcija")),
        ("story_to_wisdom", _("Priča → Bakina mudrost")),
        ("card_to_lesson", _("Kartica → Lekcija")),
        ("lesson_to_quiz", _("Lekcija → Kviz")),
        ("safety_to_quiz", _("Sigurnost → Kviz")),
        ("wisdom_to_story", _("Mudrost → Priča")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link_type = models.CharField(max_length=30, choices=LINK_TYPE_CHOICES)

    # Generičke veze (UUID jer su svi modeli UUID PK)
    source_model = models.CharField(max_length=50, help_text="ParallelStory, HeritageCard, etc.")
    source_id = models.UUIDField()
    target_model = models.CharField(max_length=50)
    target_id = models.UUIDField()

    # Kontekst
    context_note = models.CharField(max_length=500, blank=True, help_text="Zašto su povezani")

    class Meta:
        app_label = "memio_world"
        db_table = "play_content_link"
        indexes = [
            models.Index(fields=["source_model", "source_id"]),
            models.Index(fields=["target_model", "target_id"]),
        ]
        verbose_name = _("Veza sadržaja")
        verbose_name_plural = _("Veze sadržaja")

    def __str__(self):
        return f"{self.source_model}→{self.target_model}: {self.context_note[:50]}"
