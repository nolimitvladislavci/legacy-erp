"""
Auto-generiraj kviz pitanja iz HeritageCard setova.

Pokretanje:
  manage.py generate_quiz --card-set hr_alphabet --title "Hrvatska Abeceda"
  manage.py generate_quiz --card-set eu_bestiary --title "Europski Bestijarij"
  manage.py generate_quiz --dry-run
"""

import random

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generiraj kviz iz HeritageCard seta"

    def add_arguments(self, parser):
        parser.add_argument("--card-set", type=str, required=True)
        parser.add_argument("--title", type=str, required=True)
        parser.add_argument("--quiz-type", type=str, default="practice")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from memio_world.play_eu_models import HeritageCard
        from memio_world.quiz_models import Quiz, QuizAnswer, QuizQuestion

        card_set = options["card_set"]
        title = options["title"]
        dry_run = options["dry_run"]

        cards = list(
            HeritageCard.objects.using("memio_world")
            .filter(card_set=card_set, is_published=True)
            .order_by("position_in_set")
        )
        if not cards:
            self.stdout.write(self.style.ERROR(f"Nema kartica u setu '{card_set}'"))
            return

        self.stdout.write(self.style.SUCCESS(f"Generiram kviz '{title}' iz {len(cards)} kartica"))

        if dry_run:
            for c in cards:
                self.stdout.write(f"  Q: Što je {c.front_text}? -> {c.back_text[:50]}")
            return

        quiz = Quiz.objects.using("memio_world").create(
            title=title,
            description=f"Kviz generiran iz {card_set} seta ({len(cards)} pitanja)",
            quiz_type=options["quiz_type"],
            status="active",
            created_by_email="system@play.eu",
            created_by_name="PLAY.EU Auto-Generator",
            shuffle_questions=True,
            show_correct_answers=True,
            heritage_card_set=card_set,
            language="hr",
            age_min=cards[0].difficulty + 3,
            age_max=12,
        )

        for i, card in enumerate(cards):
            # Generiraj pitanje ovisno o tipu kartice
            if card.card_type == "alphabet":
                q = QuizQuestion.objects.using("memio_world").create(
                    quiz=quiz,
                    question_type="multiple_choice",
                    text=f"Koje slovo nedostaje? _{card.back_text.split(' kao ')[1] if ' kao ' in card.back_text else card.front_text}_",
                    explanation=card.fun_fact,
                    heritage_card=card,
                    points=10,
                    difficulty=card.difficulty,
                    position=i,
                )
                # Točan odgovor
                QuizAnswer.objects.using("memio_world").create(
                    question=q,
                    text=card.front_text,
                    is_correct=True,
                    position=0,
                )
                # 3 kriva odgovora (random slova)
                wrong = [
                    c.front_text for c in random.sample([x for x in cards if x.pk != card.pk], min(3, len(cards) - 1))
                ]
                for j, w in enumerate(wrong):
                    QuizAnswer.objects.using("memio_world").create(
                        question=q,
                        text=w,
                        is_correct=False,
                        position=j + 1,
                    )

            elif card.card_type == "animal":
                q = QuizQuestion.objects.using("memio_world").create(
                    quiz=quiz,
                    question_type="multiple_choice",
                    text=f"Koji mitski stvor: {card.back_text}",
                    explanation=card.fun_fact,
                    heritage_card=card,
                    points=15,
                    difficulty=card.difficulty,
                    position=i,
                )
                QuizAnswer.objects.using("memio_world").create(
                    question=q,
                    text=card.front_text,
                    is_correct=True,
                    position=0,
                )
                wrong = [
                    c.front_text for c in random.sample([x for x in cards if x.pk != card.pk], min(3, len(cards) - 1))
                ]
                for j, w in enumerate(wrong):
                    QuizAnswer.objects.using("memio_world").create(
                        question=q,
                        text=w,
                        is_correct=False,
                        position=j + 1,
                    )
            else:
                q = QuizQuestion.objects.using("memio_world").create(
                    quiz=quiz,
                    question_type="true_false",
                    text=f"Točno ili netočno: {card.back_text}",
                    explanation=card.fun_fact,
                    heritage_card=card,
                    points=10,
                    difficulty=card.difficulty,
                    position=i,
                )
                QuizAnswer.objects.using("memio_world").create(
                    question=q,
                    text="Točno",
                    is_correct=True,
                    position=0,
                )
                QuizAnswer.objects.using("memio_world").create(
                    question=q,
                    text="Netočno",
                    is_correct=False,
                    position=1,
                )

            self.stdout.write(f"  [Q{i + 1}] {card.front_text}")

        self.stdout.write(self.style.SUCCESS(f"\nKVIZ KREIRAN: '{quiz.title}' — {quiz.question_count} pitanja"))
