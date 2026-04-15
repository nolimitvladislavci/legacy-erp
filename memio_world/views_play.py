"""
PLAY.EU Frontend Views — Faza E
All views are PUBLIC (no login required) — Creative Europe demo.
All queries use .using("memio_world") — separate database.
"""

import json
import random
from collections import OrderedDict

from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_page

from memio_world.comfort_models import ComfortCard, DreamGuard, JokeEntry
from memio_world.growth_models import FamilyQuest
from memio_world.kurikulum_models import LearningPath, SafetyTopic, WisdomEntry
from memio_world.play_eu_models import EuropeanaItem, HeritageCard, ParallelStory
from memio_world.quiz_models import Quiz


DB = "memio_world"


def _lang(request):
    """Get preferred language from ?lang= param, default hr."""
    return request.GET.get("lang", "hr")


# ═══════════════════════════════════════════════════════════════
# HOME
# ═══════════════════════════════════════════════════════════════


@cache_page(60)
def play_home(request):
    lang = _lang(request)
    featured_stories = (
        ParallelStory.objects.using(DB).filter(is_published=True).order_by("-is_featured", "-view_count")[:6]
    )

    # Card sets with counts
    card_qs = HeritageCard.objects.using(DB).filter(is_published=True)
    card_sets_raw = card_qs.values_list("card_set", flat=True).distinct()
    card_sets = {}
    for s in card_sets_raw:
        card_sets[s] = card_qs.filter(card_set=s).count()

    quiz_count = Quiz.objects.using(DB).filter(status="active").count()
    joke_count = JokeEntry.objects.using(DB).filter(is_published=True).count()
    story_count = ParallelStory.objects.using(DB).filter(is_published=True).count()
    card_count = HeritageCard.objects.using(DB).filter(is_published=True).count()
    europeana_count = EuropeanaItem.objects.using(DB).count()

    return render(
        request,
        "memio_world/play_home.html",
        {
            "nav": "home",
            "lang": lang,
            "featured_stories": featured_stories,
            "card_sets": card_sets,
            "quiz_count": quiz_count,
            "joke_count": joke_count,
            "total_items": story_count + card_count + europeana_count,
            "story_count": story_count,
            "card_count": card_count,
            "europeana_count": europeana_count,
            "wisdom_count": WisdomEntry.objects.using(DB).filter(is_published=True).count(),
            "safety_count": SafetyTopic.objects.using(DB).filter(is_published=True).count(),
            "quest_count": FamilyQuest.objects.using(DB).filter(is_published=True).count(),
            "path_count": LearningPath.objects.using(DB).filter(is_published=True).count(),
        },
    )


# ═══════════════════════════════════════════════════════════════
# STORIES
# ═══════════════════════════════════════════════════════════════


@cache_page(60)
def story_list(request):
    lang = _lang(request)
    type_filter = request.GET.get("type", "")
    qs = ParallelStory.objects.using(DB).filter(is_published=True)
    if type_filter:
        qs = qs.filter(story_type=type_filter)

    return render(
        request,
        "memio_world/story_list.html",
        {
            "nav": "read",
            "lang": lang,
            "stories": qs,
            "type_filter": type_filter,
        },
    )


def story_detail(request, slug):
    lang = _lang(request)
    story = get_object_or_404(ParallelStory.objects.using(DB), slug=slug, is_published=True)

    # Increment view count
    ParallelStory.objects.using(DB).filter(pk=story.pk).update(view_count=story.view_count + 1)

    languages = story.available_languages()
    if lang not in languages and languages:
        lang = languages[0]

    title = getattr(story, f"title_{lang}", "") or story.title_hr
    text = getattr(story, f"text_{lang}", "") or story.text_hr
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    return render(
        request,
        "memio_world/story_detail.html",
        {
            "nav": "read",
            "lang": lang,
            "story": story,
            "title": title,
            "languages": languages,
            "paragraphs": paragraphs,
        },
    )


# ═══════════════════════════════════════════════════════════════
# WISDOM
# ═══════════════════════════════════════════════════════════════


@cache_page(120)
def wisdom_list(request):
    lang = _lang(request)
    wisdoms = WisdomEntry.objects.using(DB).filter(is_published=True)
    return render(
        request,
        "memio_world/wisdom.html",
        {
            "nav": "read",
            "lang": lang,
            "wisdoms": wisdoms,
        },
    )


# ═══════════════════════════════════════════════════════════════
# HERITAGE CARDS
# ═══════════════════════════════════════════════════════════════


@cache_page(60)
def card_list(request):
    lang = _lang(request)
    current_set = request.GET.get("set", "")
    qs = HeritageCard.objects.using(DB).filter(is_published=True)

    card_sets = list(qs.values_list("card_set", flat=True).distinct().order_by("card_set"))

    if current_set:
        qs = qs.filter(card_set=current_set)

    return render(
        request,
        "memio_world/card_list.html",
        {
            "nav": "play",
            "lang": lang,
            "cards": qs,
            "card_sets": card_sets,
            "current_set": current_set,
        },
    )


def memory_game(request):
    lang = _lang(request)
    current_set = request.GET.get("set", "")
    qs = HeritageCard.objects.using(DB).filter(is_published=True)
    if current_set:
        qs = qs.filter(card_set=current_set)

    cards = list(qs[:8])
    if not cards:
        cards = list(HeritageCard.objects.using(DB).filter(is_published=True)[:8])

    pairs = []
    for i, card in enumerate(cards):
        display = card.front_text
        if card.card_type == "alphabet" and card.back_text:
            pairs.append({"pair_id": str(i), "display": card.front_text})
            pairs.append({"pair_id": str(i), "display": card.back_text[:20]})
        else:
            pairs.append({"pair_id": str(i), "display": display})
            pairs.append({"pair_id": str(i), "display": display})

    random.shuffle(pairs)

    return render(
        request,
        "memio_world/memory_game.html",
        {
            "nav": "play",
            "lang": lang,
            "shuffled_cards": pairs,
            "pairs": cards,
            "current_set": current_set,
        },
    )


# ═══════════════════════════════════════════════════════════════
# QUIZ
# ═══════════════════════════════════════════════════════════════


@cache_page(60)
def quiz_list(request):
    lang = _lang(request)
    quizzes = Quiz.objects.using(DB).filter(status="active")
    return render(
        request,
        "memio_world/quiz_list.html",
        {
            "nav": "play",
            "lang": lang,
            "quizzes": quizzes,
        },
    )


def quiz_play(request, quiz_id):
    lang = _lang(request)
    quiz = get_object_or_404(Quiz.objects.using(DB), pk=quiz_id)
    questions_qs = quiz.questions.using(DB).prefetch_related("answers").order_by("position")

    questions_data = []
    for q in questions_qs:
        answers = list(q.answers.using(DB).all())
        if quiz.shuffle_questions:
            random.shuffle(answers)
        questions_data.append(
            {
                "text": q.text,
                "explanation": q.explanation,
                "image_url": q.image_url or "",
                "points": q.points,
                "answers": [{"text": a.text, "is_correct": a.is_correct} for a in answers],
            }
        )

    return render(
        request,
        "memio_world/quiz_play.html",
        {
            "nav": "play",
            "lang": lang,
            "quiz": quiz,
            "questions": questions_qs,
            "questions_json": json.dumps(questions_data, ensure_ascii=False),
        },
    )


# ═══════════════════════════════════════════════════════════════
# LEARNING PATHS
# ═══════════════════════════════════════════════════════════════


@cache_page(120)
def learning_paths(request):
    lang = _lang(request)
    age_filter = request.GET.get("age", "")
    qs = LearningPath.objects.using(DB).filter(is_published=True)
    if age_filter:
        qs = qs.filter(age_group=age_filter)

    # Group by age_group
    age_labels = dict(LearningPath.AGE_GROUP_CHOICES)
    grouped = OrderedDict()
    for path in qs:
        label = age_labels.get(path.age_group, path.age_group)
        grouped.setdefault(label, []).append(path)

    return render(
        request,
        "memio_world/learning_paths.html",
        {
            "nav": "learn",
            "lang": lang,
            "grouped_paths": grouped,
            "age_filter": age_filter,
        },
    )


# ═══════════════════════════════════════════════════════════════
# SAFETY
# ═══════════════════════════════════════════════════════════════


@cache_page(120)
def safety_list(request):
    lang = _lang(request)
    topics = SafetyTopic.objects.using(DB).filter(is_published=True)
    return render(
        request,
        "memio_world/safety_list.html",
        {
            "nav": "learn",
            "lang": lang,
            "topics": topics,
        },
    )


def safety_detail(request, topic_id):
    lang = _lang(request)
    topic = get_object_or_404(SafetyTopic.objects.using(DB), pk=topic_id, is_published=True)
    return render(
        request,
        "memio_world/safety_detail.html",
        {
            "nav": "learn",
            "lang": lang,
            "topic": topic,
        },
    )


# ═══════════════════════════════════════════════════════════════
# EUROPEANA GALLERY
# ═══════════════════════════════════════════════════════════════


@cache_page(120)
def europeana_gallery(request):
    lang = _lang(request)
    cat_filter = request.GET.get("cat", "")
    qs = EuropeanaItem.objects.using(DB).all()
    if cat_filter:
        qs = qs.filter(category=cat_filter)

    return render(
        request,
        "memio_world/europeana.html",
        {
            "nav": "learn",
            "lang": lang,
            "items": qs,
            "cat_filter": cat_filter,
        },
    )


# ═══════════════════════════════════════════════════════════════
# COMFORT
# ═══════════════════════════════════════════════════════════════


@cache_page(60)
def comfort_home(request):
    lang = _lang(request)
    cards = ComfortCard.objects.using(DB).filter(is_published=True)
    return render(
        request,
        "memio_world/comfort_home.html",
        {
            "nav": "family",
            "lang": lang,
            "cards": cards,
        },
    )


def comfort_detail(request, situation):
    lang = _lang(request)
    card = get_object_or_404(
        ComfortCard.objects.using(DB),
        situation=situation,
        is_published=True,
    )
    return render(
        request,
        "memio_world/comfort_detail.html",
        {
            "nav": "family",
            "lang": lang,
            "card": card,
        },
    )


# ═══════════════════════════════════════════════════════════════
# DREAMGUARD
# ═══════════════════════════════════════════════════════════════


def dreamguard(request):
    lang = _lang(request)
    dream_type = request.GET.get("type", "")
    dreams = DreamGuard.objects.using(DB).filter(is_published=True)

    selected = None
    if dream_type:
        selected = dreams.filter(dream_type=dream_type).first()

    disclaimer = DreamGuard.DISCLAIMER

    return render(
        request,
        "memio_world/dreamguard.html",
        {
            "nav": "family",
            "lang": lang,
            "dreams": dreams,
            "selected": selected,
            "disclaimer": disclaimer,
        },
    )


# ═══════════════════════════════════════════════════════════════
# JOKEBOX
# ═══════════════════════════════════════════════════════════════


def joke_box(request):
    lang = _lang(request)
    jokes = list(JokeEntry.objects.using(DB).filter(is_published=True))
    random.shuffle(jokes)
    jokes = jokes[:5]

    return render(
        request,
        "memio_world/jokebox.html",
        {
            "nav": "family",
            "lang": lang,
            "jokes": jokes,
        },
    )


# ═══════════════════════════════════════════════════════════════
# FAMILY QUESTS
# ═══════════════════════════════════════════════════════════════


@cache_page(120)
def family_quests(request):
    lang = _lang(request)
    quests = FamilyQuest.objects.using(DB).filter(is_published=True)
    return render(
        request,
        "memio_world/family_quests.html",
        {
            "nav": "family",
            "lang": lang,
            "quests": quests,
        },
    )
