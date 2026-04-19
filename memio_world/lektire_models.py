"""
memio_world/lektire_models.py — Školske lektire
================================================
Obavezne lektire prema HR kurikulumu, razredi 1–8.
Djeca čitaju, prate napredak, rješavaju kvizove vezane za lektiru.
Integrira se s postojećim ChildProgress (stories_read, quizzes_completed).

Filozofija:
  - Lektira je obveza, ali ne mora biti dosadna
  - Prati se stvarni napredak po poglavlju
  - Kratki sažetaci poglavlja dostupni SAMO nakon što je poglavlje pročitano
  - Kviz vezan za lektiru (extend Quiz model ili standalone)
  - Roditelj vidi napredak, može postaviti tjedni cilj
  - Kum vidi napredak ako ima can_see_progress=True
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


# ════════════════════════════════════════════════════════════════
# LEKTIRA BOOK — Knjiga iz HR kurikuluma
# ════════════════════════════════════════════════════════════════


class LektiraBook(models.Model):
    """
    Jedna lektira — naslov + autor + razred.
    Tekst može biti:
      a) Javna domena → full text u poglavljima
      b) Zaštićeno autorsko pravo → samo sažetaci + zadaci
    """

    GRADE_CHOICES = [
        (1, _("1. razred (6-7 god)")),
        (2, _("2. razred (7-8 god)")),
        (3, _("3. razred (8-9 god)")),
        (4, _("4. razred (9-10 god)")),
        (5, _("5. razred (10-11 god)")),
        (6, _("6. razred (11-12 god)")),
        (7, _("7. razred (12-13 god)")),
        (8, _("8. razred (13-14 god)")),
    ]

    LANGUAGE_CHOICES = [
        ("hr", "Hrvatski"),
        ("en", "English"),
        ("de", "Deutsch"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)

    # Bibliografski podaci
    title = models.CharField(max_length=300, verbose_name=_("Naslov"))
    author = models.CharField(max_length=200, verbose_name=_("Autor"))
    original_title = models.CharField(max_length=300, blank=True, help_text="Originalni naslov ako je prijevod")
    published_year = models.SmallIntegerField(null=True, blank=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="hr")

    # Kurikulum
    grade = models.PositiveSmallIntegerField(choices=GRADE_CHOICES, db_index=True)
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Obavezna lektira (True) ili dopunska (False)",
    )
    curriculum_note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Napomena iz kurikuluma (npr. 'po izboru razrednika')",
    )

    # Sadržaj
    cover_image = models.ImageField(upload_to="lektire/covers/", null=True, blank=True)
    synopsis = models.TextField(
        verbose_name=_("Kratki sadržaj (za roditelje)"),
        help_text="Vidljivo uvijek — motivira dijete",
    )
    pedagogical_note = models.TextField(
        blank=True,
        help_text="Pedagoška napomena — što dijete treba naučiti iz ove lektire",
    )

    # Autorska prava
    is_public_domain = models.BooleanField(
        default=False,
        help_text="Javna domena → možemo prikazati puni tekst poglavlja",
    )
    estimated_pages = models.PositiveSmallIntegerField(
        default=0,
        help_text="Procijenjeni broj stranica (za prikaz trajanja čitanja)",
    )
    estimated_minutes_per_chapter = models.PositiveSmallIntegerField(
        default=10,
        help_text="Procijenjeno vrijeme čitanja po poglavlju (minute)",
    )

    # Meta
    is_published = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0, help_text="Redoslijed prikaza unutar razreda")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_lektira_book"
        ordering = ["grade", "position", "title"]
        verbose_name = _("Lektira")
        verbose_name_plural = _("Lektire")
        indexes = [
            models.Index(fields=["grade", "is_published"]),
        ]

    def __str__(self):
        return f"[{self.grade}. razred] {self.title} — {self.author}"

    @property
    def chapter_count(self):
        return self.chapters.count()

    @property
    def read_time_hours(self):
        total = self.chapters.aggregate(models.Sum("estimated_minutes"))["estimated_minutes__sum"] or 0
        return round(total / 60, 1)


# ════════════════════════════════════════════════════════════════
# LEKTIRA CHAPTER — Poglavlje knjige
# ════════════════════════════════════════════════════════════════


class LektiraChapter(models.Model):
    """
    Jedno poglavlje lektire.
    Ako je javna domena → full_text dostupan.
    Ako nije → summary dostupan SAMO nakon što je dijete označilo
    da je pročitalo (čast sustav + rodительska provjera).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        LektiraBook,
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    number = models.PositiveSmallIntegerField(help_text="Redni broj poglavlja")
    title = models.CharField(max_length=300, verbose_name=_("Naziv poglavlja"))

    # Sadržaj
    full_text = models.TextField(
        blank=True,
        help_text="Puni tekst — samo ako je javna domena",
    )
    summary = models.TextField(
        verbose_name=_("Sažetak poglavlja"),
        help_text="Prikazuje se SAMO nakon što dijete označi da je pročitalo",
    )
    key_words = models.JSONField(
        default=list,
        blank=True,
        help_text='Ključne riječi za rječnik: [{"word":"...", "meaning":"..."}]',
    )
    discussion_questions = models.JSONField(
        default=list,
        blank=True,
        help_text="Pitanja za razgovor s roditeljem/kumom nakon čitanja",
    )

    estimated_minutes = models.PositiveSmallIntegerField(
        default=10,
        help_text="Procijenjeno vrijeme čitanja (minute)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_lektira_chapter"
        unique_together = [("book", "number")]
        ordering = ["book", "number"]
        verbose_name = _("Poglavlje lektire")
        verbose_name_plural = _("Poglavlja lektira")

    def __str__(self):
        return f"{self.book.title} — {self.number}. {self.title}"


# ════════════════════════════════════════════════════════════════
# LEKTIRA PROGRESS — Napredak djeteta
# ════════════════════════════════════════════════════════════════


class LektiraProgress(models.Model):
    """
    Napredak jednog djeteta na jednoj lektiri.
    Jedno dijete → jedna lektira = jedan LektiraProgress.
    """

    STATUS_CHOICES = [
        ("not_started", _("Nije početo")),
        ("in_progress", _("U tijeku")),
        ("completed", _("Pročitano")),
        ("quiz_done", _("Kviz riješen")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="lektira_progress",
    )
    book = models.ForeignKey(
        LektiraBook,
        on_delete=models.CASCADE,
        related_name="progress_records",
    )

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="not_started")

    # Koje je kapitule dijete označilo kao pročitane
    chapters_read = models.JSONField(
        default=list,
        help_text="Lista chapter.number vrijednosti koje je dijete pročitalo",
    )
    current_chapter = models.PositiveSmallIntegerField(
        default=1,
        help_text="Poglavlje na kojemu je dijete stalo",
    )

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    # Kviz
    quiz_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Postotak točnih odgovora u završnom kvizu",
    )
    quiz_attempts = models.PositiveSmallIntegerField(default=0)

    # Roditeljska potvrda (za zaštitu od "preskačem")
    parent_confirmed = models.BooleanField(
        default=False,
        help_text="Roditelj potvrdio da je dijete stvarno pročitalo",
    )

    # XP nagrađen
    xp_awarded = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_lektira_progress"
        unique_together = [("child", "book")]
        ordering = ["-updated_at"]
        verbose_name = _("Napredak lektire")
        verbose_name_plural = _("Napretci lektira")

    def __str__(self):
        pct = self.completion_pct
        return f"{self.child.name} — {self.book.title} ({pct}%)"

    @property
    def completion_pct(self):
        total = self.book.chapter_count
        if not total:
            return 0
        return round(len(self.chapters_read) / total * 100)

    def mark_chapter_read(self, chapter_number: int):
        """Dijete označi poglavlje kao pročitano."""
        from django.utils import timezone

        if chapter_number not in self.chapters_read:
            self.chapters_read.append(chapter_number)
        self.current_chapter = chapter_number + 1
        self.last_read_at = timezone.now()
        if not self.started_at:
            self.started_at = timezone.now()
        total = self.book.chapter_count
        if total and len(self.chapters_read) >= total:
            self.status = "completed"
            self.completed_at = timezone.now()
            self._award_xp()
        else:
            self.status = "in_progress"
        self.save(
            update_fields=[
                "chapters_read",
                "current_chapter",
                "last_read_at",
                "started_at",
                "status",
                "completed_at",
                "xp_awarded",
            ]
        )

    def _award_xp(self):
        """Nagradi XP za završenu lektiru."""
        xp = 50 + (self.book.grade * 10)  # 1. razred = 60 XP, 8. razred = 130 XP
        self.xp_awarded = xp
        try:
            progress = self.child.progress
            progress.add_xp(xp, task_id=f"lektira_{self.book.slug}")
            progress.save(update_fields=["xp", "total_xp", "completed_tasks"])
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
# LEKTIRA QUIZ — Kviz za lektiru (standalone, ne extend Quiz)
# ════════════════════════════════════════════════════════════════


class LektiraQuiz(models.Model):
    """
    Kviz specifičan za jednu lektiru.
    Može biti auto-generiran (AI) ili ručno unijet.
    Prikazuje se SAMO ako je dijete završilo lektiru (status=completed).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.OneToOneField(
        LektiraBook,
        on_delete=models.CASCADE,
        related_name="quiz",
    )
    title = models.CharField(max_length=300, blank=True)
    is_ai_generated = models.BooleanField(default=False)
    pass_percentage = models.PositiveSmallIntegerField(default=60)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_lektira_quiz"
        verbose_name = _("Kviz za lektiru")

    def __str__(self):
        return f"Kviz: {self.book.title}"


class LektiraQuizQuestion(models.Model):
    """Pitanje u kvizu za lektiru."""

    TYPE_CHOICES = [
        ("multiple_choice", _("Višestruki izbor")),
        ("true_false", _("Točno / Netočno")),
        ("fill_blank", _("Dopuni rečenicu")),
        ("who_said", _("Tko je rekao?")),
        ("what_happened", _("Što se dogodilo?")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(LektiraQuiz, on_delete=models.CASCADE, related_name="questions")
    chapter = models.ForeignKey(
        LektiraChapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quiz_questions",
        help_text="Iz kojeg poglavlja je pitanje (opcionalno)",
    )
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="multiple_choice")
    question_text = models.TextField()
    options = models.JSONField(
        default=list,
        help_text='Za multiple_choice: [{"text":"...", "correct":true/false}]',
    )
    correct_answer = models.TextField(blank=True, help_text="Za fill_blank i slično")
    explanation = models.TextField(blank=True, help_text="Objašnjenje točnog odgovora")
    difficulty = models.PositiveSmallIntegerField(
        default=1,
        help_text="1=lako, 2=srednje, 3=teško",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = "memio_world"
        db_table = "play_lektira_quiz_question"
        ordering = ["quiz", "position"]
        verbose_name = _("Pitanje kviza lektire")
