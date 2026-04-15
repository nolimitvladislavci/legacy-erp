"""
PLAY.EU Slikovnice — Picture Book Engine
==========================================
Svaka priča = digitalna slikovnica s ilustracijama, audio naracijom,
i page-flip iskustvom.

Arhitektura:
  StoryBookStyle  → vizualni identitet (prompt template, paleta, font)
  StoryPage       → jedna stranica (ilustracija + tekst + audio)

Baza: memio_world (potpuno odvojena od ERP-a)
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class StoryBookStyle(models.Model):
    """Vizualni stil za grupu slikovnica — osigurava konzistentnost."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    # AI prompt template
    prompt_prefix = models.TextField(
        help_text="Dodaje se na početak svakog AI prompta za ilustraciju",
    )
    prompt_suffix = models.TextField(
        blank=True,
        help_text="Dodaje se na kraj (kvaliteta, rezolucija)",
    )
    negative_prompt = models.TextField(
        blank=True,
        help_text="Što izbjegavati u generaciji",
    )

    # Vizualni parametri
    dominant_palette = models.JSONField(
        default=list,
        blank=True,
        help_text='HEX boje: ["#FDF6E3", "#C9A84C", "#8B4513"]',
    )
    font_family = models.CharField(max_length=100, default="Cormorant Garamond")
    page_texture = models.CharField(
        max_length=50,
        default="parchment",
        choices=[
            ("parchment", _("Pergament")),
            ("paper", _("Papir")),
            ("canvas", _("Platno")),
            ("clean", _("Čisto bijelo")),
        ],
    )

    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_book_style"
        verbose_name = _("Stil slikovnice")
        verbose_name_plural = _("Stilovi slikovnica")

    def __str__(self):
        return self.name


class StoryPage(models.Model):
    """Jedna stranica slikovnice — ilustracija + tekst + audio."""

    PAGE_TYPE_CHOICES = [
        ("cover", _("Naslovnica")),
        ("inner", _("Unutarnja stranica")),
        ("back", _("Zadnja stranica")),
    ]

    LAYOUT_CHOICES = [
        ("full_bleed", _("Slika preko cijele stranice")),
        ("top_image", _("Slika gore, tekst dolje")),
        ("bottom_image", _("Tekst gore, slika dolje")),
        ("left_image", _("Slika lijevo, tekst desno")),
        ("split_50_50", _("Pola slika, pola tekst")),
        ("text_overlay", _("Tekst preko slike")),
    ]

    IMAGE_SOURCE_CHOICES = [
        ("ai_generated", _("AI generirano")),
        ("europeana", _("Europeana")),
        ("original", _("Originalna ilustracija")),
        ("public_domain", _("Javna domena")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.ForeignKey(
        "memio_world.ParallelStory",
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveSmallIntegerField(
        help_text="0 = naslovnica, 1+ = unutarnje, zadnja = max",
    )
    page_type = models.CharField(max_length=10, choices=PAGE_TYPE_CHOICES)
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default="top_image")

    # ── Ilustracija ──────────────────────────────────────────
    image = models.ImageField(upload_to="play_eu/pages/", blank=True)
    image_thumbnail = models.ImageField(upload_to="play_eu/pages/thumbs/", blank=True)
    image_alt_text = models.CharField(max_length=500, blank=True)
    image_prompt = models.TextField(
        blank=True,
        help_text="Puni AI prompt koji je generirao sliku",
    )
    image_style = models.CharField(max_length=30, default="watercolor_parchment")
    image_source = models.CharField(
        max_length=20,
        choices=IMAGE_SOURCE_CHOICES,
        default="ai_generated",
    )
    image_approved = models.BooleanField(
        default=False,
        help_text="Ručna provjera kvalitete prije publishanja",
    )

    # ── Tekst po jezicima ────────────────────────────────────
    text_hr = models.TextField(blank=True)
    text_de = models.TextField(blank=True)
    text_en = models.TextField(blank=True)

    # ── Audio naracija ───────────────────────────────────────
    audio_hr = models.FileField(upload_to="play_eu/audio/pages/hr/", blank=True)
    audio_de = models.FileField(upload_to="play_eu/audio/pages/de/", blank=True)
    audio_en = models.FileField(upload_to="play_eu/audio/pages/en/", blank=True)

    # ── Scene za AI ──────────────────────────────────────────
    scene_description = models.TextField(
        blank=True,
        help_text="Opis scene na engleskom za AI generator",
    )

    # ── Vizualno ─────────────────────────────────────────────
    background_color = models.CharField(max_length=7, default="#FDF6E3")
    text_color = models.CharField(max_length=7, default="#2D1B00")

    # ── Meta ─────────────────────────────────────────────────
    style = models.ForeignKey(
        StoryBookStyle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pages",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_story_page"
        unique_together = ("story", "page_number")
        ordering = ["story", "page_number"]
        indexes = [
            models.Index(fields=["story", "page_number"]),
        ]
        verbose_name = _("Stranica slikovnice")
        verbose_name_plural = _("Stranice slikovnica")

    def __str__(self):
        return f"[{self.story.slug}] P{self.page_number} ({self.get_page_type_display()})"
