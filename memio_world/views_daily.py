"""
PLAY.EU Daily Discovery + Parent Dashboard
============================================
Daily Discovery: Svaki dan drugačiji sadržaj po danu u tjednu.
Parent Dashboard: Pregled sadržaja platforme za roditelje.
"""

import hashlib
from datetime import date

from django.shortcuts import render

from memio_world.comfort_models import ComfortCard, DreamGuard, JokeEntry
from memio_world.growth_models import FamilyQuest
from memio_world.kurikulum_models import SafetyTopic, WisdomEntry
from memio_world.play_eu_models import ParallelStory
from memio_world.quiz_models import Quiz

DB = "memio_world"


def _lang(request):
    return request.GET.get("lang", "hr")


def _daily_seed():
    """Deterministic seed from today's date — same content all day."""
    return int(hashlib.md5(str(date.today()).encode()).hexdigest()[:8], 16)


# ═══════════════════════════════════════════════════════════════
# DAILY DISCOVERY — Svaki dan drugačiji sadržaj
# ═══════════════════════════════════════════════════════════════

# Day themes
DAY_THEMES = {
    0: {"icon": "📖", "theme_hr": "Ponedjeljak — Priča + Kviz", "theme_de": "Montag — Geschichte + Quiz", "theme_en": "Monday — Story + Quiz"},
    1: {"icon": "🎮", "theme_hr": "Utorak — Igra + Bakina mudrost", "theme_de": "Dienstag — Spiel + Omas Weisheit", "theme_en": "Tuesday — Game + Grandma's Wisdom"},
    2: {"icon": "🛡️", "theme_hr": "Srijeda — Sigurnost + Scenarij", "theme_de": "Mittwoch — Sicherheit + Szenario", "theme_en": "Wednesday — Safety + Scenario"},
    3: {"icon": "🎨", "theme_hr": "Četvrtak — Kreativni dan", "theme_de": "Donnerstag — Kreativtag", "theme_en": "Thursday — Creative Day"},
    4: {"icon": "🏡", "theme_hr": "Petak — Obiteljski izazov", "theme_de": "Freitag — Familien-Challenge", "theme_en": "Friday — Family Challenge"},
    5: {"icon": "🌟", "theme_hr": "Subota — Slobodan dan!", "theme_de": "Samstag — Freier Tag!", "theme_en": "Saturday — Free Day!"},
    6: {"icon": "🔄", "theme_hr": "Nedjelja — Ponavljanje tjedna", "theme_de": "Sonntag — Wochenrückblick", "theme_en": "Sunday — Week Review"},
}

GREETINGS_HR = [
    "Dobro jutro, sunce! ☀️",
    "Hej, heroju! 🦸",
    "Dobrodošao/la natrag! 🌈",
    "Super dan za učenje! 📚",
    "Ajmo zajedno! 🤝",
]
GREETINGS_DE = [
    "Guten Morgen, Sonnenschein! ☀️",
    "Hey, Held! 🦸",
    "Willkommen zurück! 🌈",
    "Ein toller Tag zum Lernen! 📚",
    "Los geht's zusammen! 🤝",
]
GREETINGS_EN = [
    "Good morning, sunshine! ☀️",
    "Hey there, hero! 🦸",
    "Welcome back! 🌈",
    "A great day for learning! 📚",
    "Let's go together! 🤝",
]


def daily_discovery(request):
    lang = _lang(request)
    today = date.today()
    weekday = today.weekday()
    seed = _daily_seed()
    theme = DAY_THEMES.get(weekday, DAY_THEMES[0])

    # Pick greeting
    greetings = {"hr": GREETINGS_HR, "de": GREETINGS_DE, "en": GREETINGS_EN}
    greeting = greetings.get(lang, GREETINGS_HR)[seed % 5]

    # Pick daily story
    stories = list(ParallelStory.objects.using(DB).filter(is_published=True).order_by("slug"))
    daily_story = stories[seed % len(stories)] if stories else None

    # Pick daily wisdom
    wisdoms = list(WisdomEntry.objects.using(DB).filter(is_published=True))
    daily_wisdom = wisdoms[seed % len(wisdoms)] if wisdoms else None

    # Pick daily joke
    jokes = list(JokeEntry.objects.using(DB).filter(is_published=True))
    daily_joke = jokes[seed % len(jokes)] if jokes else None

    # Pick daily safety topic
    safety = list(SafetyTopic.objects.using(DB).filter(is_published=True))
    daily_safety = safety[seed % len(safety)] if safety else None

    # Pick daily quest
    quests = list(FamilyQuest.objects.using(DB).filter(is_published=True))
    daily_quest = quests[seed % len(quests)] if quests else None

    # Pick daily quiz
    quizzes = list(Quiz.objects.using(DB).filter(status="active"))
    daily_quiz = quizzes[seed % len(quizzes)] if quizzes else None

    return render(
        request,
        "memio_world/daily_discovery.html",
        {
            "nav": "home",
            "lang": lang,
            "today": today,
            "weekday": weekday,
            "theme": theme,
            "greeting": greeting,
            "daily_story": daily_story,
            "daily_wisdom": daily_wisdom,
            "daily_joke": daily_joke,
            "daily_safety": daily_safety,
            "daily_quest": daily_quest,
            "daily_quiz": daily_quiz,
        },
    )


# ═══════════════════════════════════════════════════════════════
# PARENT DASHBOARD — Pregled za roditelje
# ═══════════════════════════════════════════════════════════════


def parent_dashboard(request):
    lang = _lang(request)

    # Content stats
    story_count = ParallelStory.objects.using(DB).filter(is_published=True).count()
    stories = ParallelStory.objects.using(DB).filter(is_published=True)

    # Group stories by region
    regions = {}
    for s in stories:
        r = s.country_of_origin or "Europa"
        regions.setdefault(r, []).append(s)

    total_pages = sum(
        len([p for p in (s.text_hr or "").split("\n") if p.strip()]) + 2 for s in stories
    )

    quiz_count = Quiz.objects.using(DB).filter(status="active").count()
    wisdom_count = WisdomEntry.objects.using(DB).filter(is_published=True).count()
    safety_count = SafetyTopic.objects.using(DB).filter(is_published=True).count()
    quest_count = FamilyQuest.objects.using(DB).filter(is_published=True).count()
    joke_count = JokeEntry.objects.using(DB).filter(is_published=True).count()
    comfort_count = ComfortCard.objects.using(DB).filter(is_published=True).count()
    dream_count = DreamGuard.objects.using(DB).filter(is_published=True).count()

    # Calming exercises
    try:
        from memio_world.comfort_models import CalmingExercise
        calming_count = CalmingExercise.objects.using(DB).filter(is_published=True).count()
    except Exception:
        calming_count = 0

    return render(
        request,
        "memio_world/parent_dashboard.html",
        {
            "nav": "home",
            "lang": lang,
            "story_count": story_count,
            "total_pages": total_pages,
            "regions": regions,
            "quiz_count": quiz_count,
            "wisdom_count": wisdom_count,
            "safety_count": safety_count,
            "quest_count": quest_count,
            "joke_count": joke_count,
            "comfort_count": comfort_count,
            "dream_count": dream_count,
            "calming_count": calming_count,
        },
    )
