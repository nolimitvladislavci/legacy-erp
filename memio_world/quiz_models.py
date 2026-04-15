"""
PLAY.EU Quiz Engine — Kviz sustav za škole
============================================
- Učitelji kreiraju kvizove iz HeritageCard setova ili slobodno
- Učenici rješavaju (live ili domaća zadaća)
- Auto-grading + adaptivna težina
- Roditelji vide napredak

Baza: memio_world
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Quiz(models.Model):
    """Kviz — skup pitanja, može biti domaća zadaća ili live igra."""

    QUIZ_TYPE_CHOICES = [
        ("homework", _("Domaća zadaća")),
        ("live", _("Uživo u razredu")),
        ("practice", _("Vježba (bez ocjene)")),
        ("exam", _("Ispit")),
    ]

    STATUS_CHOICES = [
        ("draft", _("Nacrt")),
        ("active", _("Aktivan")),
        ("closed", _("Zatvoren")),
        ("archived", _("Arhiviran")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPE_CHOICES, default="practice")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Kreator (email jer memio_world nema FK na auth_user)
    created_by_email = models.EmailField(help_text="Email učitelja/kreatora")
    created_by_name = models.CharField(max_length=200, blank=True)

    # Postavke
    time_limit_minutes = models.PositiveSmallIntegerField(null=True, blank=True, help_text="0 = bez limita")
    pass_percentage = models.PositiveSmallIntegerField(default=60, help_text="Postotak za prolaz")
    shuffle_questions = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=True, help_text="Pokaži točne odgovore nakon završetka")
    max_attempts = models.PositiveSmallIntegerField(default=3, help_text="0 = neograničeno")
    adaptive_difficulty = models.BooleanField(default=False, help_text="Prilagodi težinu prema učeniku")

    # Veza na Heritage Card set (opcionalno)
    heritage_card_set = models.CharField(max_length=100, blank=True, help_text="Auto-generiraj pitanja iz card seta")

    # Jezik
    language = models.CharField(max_length=5, default="hr")

    # Dobna skupina
    age_min = models.PositiveSmallIntegerField(default=5)
    age_max = models.PositiveSmallIntegerField(default=12)

    # Domaća zadaća
    deadline = models.DateTimeField(null=True, blank=True, help_text="Rok za domaću zadaću")
    class_name = models.CharField(max_length=100, blank=True, help_text="Naziv razreda (npr. 3.a)")

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_quiz"
        ordering = ["-created_at"]
        verbose_name = _("Kviz")
        verbose_name_plural = _("Kvizovi")

    def __str__(self):
        return f"{self.title} ({self.get_quiz_type_display()})"

    @property
    def question_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    """Jedno pitanje u kvizu."""

    QUESTION_TYPE_CHOICES = [
        ("multiple_choice", _("Višestruki izbor")),
        ("true_false", _("Točno / Netočno")),
        ("matching", _("Spajanje parova")),
        ("sequence", _("Poredaj redoslijed")),
        ("fill_blank", _("Popuni prazninu")),
        ("image_choice", _("Odaberi sliku")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default="multiple_choice")

    # Tekst pitanja
    text = models.TextField(help_text="Tekst pitanja")
    explanation = models.TextField(blank=True, help_text="Objašnjenje točnog odgovora (prikazuje se nakon)")

    # Veza na Heritage Card (opcionalno)
    heritage_card = models.ForeignKey(
        "memio_world.HeritageCard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quiz_questions",
    )

    # Slika pitanja (opcionalno)
    image_url = models.URLField(blank=True, help_text="Slika uz pitanje (Europeana thumbnail)")

    # Bodovi i težina
    points = models.PositiveSmallIntegerField(default=10)
    difficulty = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = "memio_world"
        db_table = "play_quiz_question"
        ordering = ["position"]

    def __str__(self):
        return f"Q{self.position}: {self.text[:60]}"


class QuizAnswer(models.Model):
    """Jedan mogući odgovor na pitanje."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="answers")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    # Za matching tip: match_pair je tekst koji se spaja s ovim odgovorom
    match_pair = models.CharField(max_length=500, blank=True, help_text="Za matching: tekst para")

    # Slika odgovora (za image_choice tip)
    image_url = models.URLField(blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_quiz_answer"
        ordering = ["position"]

    def __str__(self):
        marker = "✓" if self.is_correct else "✗"
        return f"{marker} {self.text[:60]}"


class QuizAttempt(models.Model):
    """Pokušaj rješavanja kviza od strane učenika."""

    STATUS_CHOICES = [
        ("in_progress", _("U tijeku")),
        ("completed", _("Završen")),
        ("timed_out", _("Isteklo vrijeme")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")

    # Učenik (email + ime jer nema FK)
    student_email = models.EmailField()
    student_name = models.CharField(max_length=200, blank=True)

    # Roditelj (za parent dashboard)
    parent_email = models.EmailField(blank=True)

    # Rezultati
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    score = models.PositiveSmallIntegerField(default=0, help_text="Osvojeni bodovi")
    max_score = models.PositiveSmallIntegerField(default=0, help_text="Maksimalni mogući bodovi")
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)

    # Odgovori (JSON: [{question_id, answer_id, is_correct, time_seconds}])
    responses = models.JSONField(default=list, blank=True)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    # Adaptivna težina
    difficulty_progression = models.JSONField(default=list, blank=True, help_text="Tijek težine pitanja")

    class Meta:
        app_label = "memio_world"
        db_table = "play_quiz_attempt"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student_name}: {self.quiz.title} — {self.percentage}%"

    def calculate_score(self):
        """Izračunaj bodove iz odgovora."""
        if not self.responses:
            return
        correct = sum(1 for r in self.responses if r.get("is_correct"))
        total = len(self.responses)
        self.score = sum(r.get("points", 10) for r in self.responses if r.get("is_correct"))
        self.max_score = sum(r.get("points", 10) for r in self.responses)
        self.percentage = round((correct / total * 100) if total > 0 else 0, 2)
        self.passed = self.percentage >= self.quiz.pass_percentage


# Import u memio_world/models.py
# from memio_world.quiz_models import Quiz, QuizQuestion, QuizAnswer, QuizAttempt
