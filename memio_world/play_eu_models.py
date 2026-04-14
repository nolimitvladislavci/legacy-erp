"""
PLAY.EU — Dječja Digitalna Baština Europe
==========================================
3 core modela za Sprint 1 (deadline: 2026-05-07 Creative Europe)

Arhitektura:
  EuropeanaItem  → cache/proxy za Europeana API (55M+ objekata, 20M CC0)
  ParallelStory  → ista priča na N jezika paralelno
  HeritageCard   → digitalne rekonstrukcije starih igara/slovarica

Baza: memio_world (potpuno odvojena od ERP-a)
Disk: <200MB od 85GB slobodnih — manje od 1% diska
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


# ════════════════════════════════════════════════════════════════
# MODEL 1: EuropeanaItem — Cache za Europeana API
# ════════════════════════════════════════════════════════════════


class EuropeanaItem(models.Model):
    """
    Cache/proxy za Europeana API objekte.
    Ne kopiramo sadržaj — čuvamo metadata + thumbnail URL + rights info.
    Originali ostaju na Europeana serverima (IIIF).

    Refresh: tjedni Celery sync novih items.
    API: api.europeana.eu (REST, free key, IIIF bez ključa)
    """

    MEDIA_TYPE_CHOICES = [
        ("IMAGE", _("Slika")),
        ("SOUND", _("Zvuk")),
        ("TEXT", _("Tekst")),
        ("VIDEO", _("Video")),
        ("3D", _("3D objekt")),
    ]

    CATEGORY_CHOICES = [
        ("alphabet", _("Slovarica / Abeceda")),
        ("counting", _("Brojalica")),
        ("story", _("Priča / Bajka")),
        ("song", _("Pjesma")),
        ("game", _("Igra")),
        ("illustration", _("Ilustracija")),
        ("map", _("Karta")),
        ("manuscript", _("Rukopis")),
        ("bestiary", _("Bestijarij")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    europeana_id = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Europeana record ID (npr. /2021672/resource_...)",
    )

    # Višejezični naslovi
    title = models.CharField(max_length=500)
    title_hr = models.CharField(max_length=500, blank=True)
    title_de = models.CharField(max_length=500, blank=True)
    title_en = models.CharField(max_length=500, blank=True)
    title_fr = models.CharField(max_length=500, blank=True)
    title_it = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    # Europeana metadata
    provider = models.CharField(max_length=200, help_text="Gallica, Deutsche Digitale Bibliothek, NSK...")
    country = models.CharField(max_length=10, blank=True, help_text="ISO 3166-1 alpha-2")
    data_provider = models.CharField(max_length=200, blank=True)

    # Media — linkovi na Europeana, ne lokalne kopije
    thumbnail_url = models.URLField(max_length=500, blank=True)
    media_url = models.URLField(max_length=500, blank=True)
    iiif_manifest = models.URLField(max_length=500, blank=True, help_text="IIIF Manifest URL (ne treba API key)")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)

    # Prava — KRITIČNO za legalnost
    rights = models.CharField(max_length=200, help_text="CC0, CC-BY-4.0, CC-BY-SA-4.0, InC, etc.")
    is_commercially_usable = models.BooleanField(default=False, db_index=True)
    attribution_text = models.TextField(blank=True)

    # Kategorija i dob
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=12)

    # Povijesni kontekst
    year_created = models.IntegerField(null=True, blank=True, help_text="Godina nastanka originala")
    original_language = models.CharField(max_length=10, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Kuracija
    is_curated = models.BooleanField(default=False, help_text="Ručno odabran za PLAY.EU")
    is_active = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_europeana_item"
        ordering = ["-is_curated", "-year_created"]
        indexes = [
            models.Index(fields=["category", "is_commercially_usable"]),
            models.Index(fields=["country", "category"]),
        ]
        verbose_name = _("Europeana Item")
        verbose_name_plural = _("Europeana Items")

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title[:60]}"


# ════════════════════════════════════════════════════════════════
# MODEL 2: ParallelStory — Ista priča na N jezika
# ════════════════════════════════════════════════════════════════


class ParallelStory(models.Model):
    """
    Ista priča na N jezika paralelno — USP koji nitko nema.

    Izvori (svi legalni):
    - GrimmStories.com: 13 EU jezika, public domain
    - Project Gutenberg: Grimm, Andersen, Perrault
    - StoryWeaver: 40K priča, CC BY 4.0
    - ICDL: 4,600 knjiga, 59 jezika
    - Narodna predaja: public domain

    UX: dijete čita na HR → jednim klikom prebacuje na DE → sluša audio na EN
    """

    STORY_TYPE_CHOICES = [
        ("fairy_tale", _("Bajka")),
        ("folk_tale", _("Narodna priča")),
        ("fable", _("Basna")),
        ("counting_rhyme", _("Brojalica")),
        ("nursery_rhyme", _("Uspavanka")),
        ("legend", _("Legenda")),
        ("alphabet_story", _("Slovarica")),
    ]

    SOURCE_CHOICES = [
        ("grimm", "Brothers Grimm (public domain)"),
        ("andersen", "H.C. Andersen (public domain)"),
        ("perrault", "Charles Perrault (public domain)"),
        ("storyweaver", "StoryWeaver (CC BY 4.0)"),
        ("gutenberg", "Project Gutenberg (public domain)"),
        ("europeana", "Europeana (various)"),
        ("mama_lisa", "Mama Lisa's World (traditional)"),
        ("original", "PLAY.EU original"),
        ("folk", "Narodna predaja (public domain)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=200, unique=True)

    # Naslovi po jezicima
    title_hr = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)
    title_fr = models.CharField(max_length=300, blank=True)
    title_it = models.CharField(max_length=300, blank=True)
    title_es = models.CharField(max_length=300, blank=True)
    title_tr = models.CharField(max_length=300, blank=True)

    story_type = models.CharField(max_length=20, choices=STORY_TYPE_CHOICES)

    # Izvor i prava
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_url = models.URLField(blank=True)
    license = models.CharField(max_length=50, default="public_domain")
    attribution = models.TextField(blank=True)

    # Tekst po jezicima
    text_hr = models.TextField(blank=True)
    text_de = models.TextField(blank=True)
    text_en = models.TextField(blank=True)
    text_fr = models.TextField(blank=True)
    text_it = models.TextField(blank=True)
    text_es = models.TextField(blank=True)
    text_tr = models.TextField(blank=True)

    # Audio naracija
    audio_hr = models.FileField(upload_to="play_eu/audio/hr/", blank=True)
    audio_de = models.FileField(upload_to="play_eu/audio/de/", blank=True)
    audio_en = models.FileField(upload_to="play_eu/audio/en/", blank=True)

    # Ilustracije iz Europeana
    cover_image = models.ForeignKey(
        EuropeanaItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stories_as_cover",
    )
    illustrations = models.ManyToManyField(
        EuropeanaItem,
        blank=True,
        related_name="stories_as_illustration",
    )

    # Metapodaci
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=10)
    reading_time_minutes = models.PositiveSmallIntegerField(default=5)
    difficulty_level = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    country_of_origin = models.CharField(max_length=100, blank=True)
    moral_lesson = models.TextField(blank=True, help_text="Za učitelje — pouka priče")

    # Status
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_parallel_story"
        ordering = ["-is_featured", "-view_count"]
        verbose_name = _("Paralelna priča")
        verbose_name_plural = _("Paralelne priče")

    def available_languages(self):
        """Vraća listu jezika za koje postoji tekst."""
        return [
            code for code in ("hr", "de", "en", "fr", "it", "es", "tr") if getattr(self, f"text_{code}", "").strip()
        ]

    def __str__(self):
        return f"{self.title_hr} ({len(self.available_languages())} jezika)"


# ════════════════════════════════════════════════════════════════
# MODEL 3: HeritageCard — Digitalne rekonstrukcije starih igara
# ════════════════════════════════════════════════════════════════


class HeritageCard(models.Model):
    """
    Digitalna rekonstrukcija starih europskih igara, slovarica, kartica.

    Primjeri:
    - Le Quadrille des Enfans (1779): bakrorezne karte — nikad digitalizirano
    - Hornbooks (15-19. st.): drvene abecedne tablice
    - Aberdeen Bestiary (~1200 AD): zmajevi, jednoroži, feniksi
    - Školica, Mlin, Lovice: tradicionalne EU igre

    Svaka kartica = jedan interaktivni element u heritage igri.
    Kartice se grupiraju u setove (hr_alphabet, grimm_bestiary, etc.)
    """

    CARD_TYPE_CHOICES = [
        ("alphabet", _("Slovo (A-Ž)")),
        ("number", _("Broj (0-100)")),
        ("animal", _("Životinja (bestijarij)")),
        ("game_piece", _("Igra (Le Quadrille, Mlin)")),
        ("map_region", _("Regija na karti")),
        ("instrument", _("Glazbalo")),
        ("folk_costume", _("Narodna nošnja")),
        ("landmark", _("Znamenitost")),
    ]

    GAME_CHOICES = [
        ("memory", _("Memory (parovi)")),
        ("quiz", _("Kviz")),
        ("sequence", _("Slagalica (redoslijed)")),
        ("matching", _("Spajanje")),
        ("collection", _("Kolekcija (sakupljanje)")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=200, unique=True)

    # Višejezični naslovi
    title = models.CharField(max_length=300)
    title_hr = models.CharField(max_length=300, blank=True)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)

    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES)

    # Sadržaj
    front_text = models.CharField(max_length=200, help_text="Tekst na prednjoj strani kartice")
    back_text = models.TextField(blank=True, help_text="Objašnjenje na stražnjoj strani")
    fun_fact = models.TextField(blank=True, help_text="Zanimljivost za djecu")

    # Vizualno
    original_image = models.ForeignKey(
        EuropeanaItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="heritage_cards",
    )
    modern_illustration = models.ImageField(upload_to="play_eu/cards/", blank=True)
    background_color = models.CharField(max_length=7, default="#F5E6CC", help_text="Parchment boja")

    # Heritage kontekst
    historical_period = models.CharField(max_length=100, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    source_collection = models.CharField(max_length=200, blank=True, help_text="Aberdeen Bestiary, Gallica, NSK...")
    year_created = models.IntegerField(null=True, blank=True)

    # Igra mehanika
    game_type = models.CharField(max_length=20, choices=GAME_CHOICES, blank=True)
    difficulty = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    points_value = models.PositiveSmallIntegerField(default=10)

    # Set/Grupa — kartice idu u setove
    card_set = models.CharField(max_length=100, db_index=True, help_text="grimm_bestiary, hr_alphabet, etc.")
    position_in_set = models.PositiveSmallIntegerField(default=0)

    # Status
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_heritage_card"
        ordering = ["card_set", "position_in_set"]
        indexes = [
            models.Index(fields=["card_type", "is_published"]),
            models.Index(fields=["card_set", "position_in_set"]),
        ]
        verbose_name = _("Heritage kartica")
        verbose_name_plural = _("Heritage kartice")

    def __str__(self):
        return f"[{self.card_set}] {self.front_text}"
