from django.urls import path

from memio_world import views, views_play

app_name = "memio_world"

urlpatterns = [
    # ── Existing ──────────────────────────────────────────────
    path("waitlist/", views.waitlist_signup, name="waitlist_signup"),
    path("waitlist/count/", views.waitlist_count, name="waitlist_count"),
    path("registracija/", views.registracija_page, name="registracija"),
    path("o-projektu/", views.o_projektu_page, name="o_projektu"),
    # ── PLAY.EU — Home ────────────────────────────────────────
    path("play/", views_play.play_home, name="play_home"),
    # ── Čitaj (Read) ──────────────────────────────────────────
    path("play/stories/", views_play.story_list, name="story_list"),
    path("play/stories/<slug:slug>/", views_play.story_detail, name="story_detail"),
    path("play/wisdom/", views_play.wisdom_list, name="wisdom_list"),
    # ── Igraj (Play) ──────────────────────────────────────────
    path("play/cards/", views_play.card_list, name="card_list"),
    path("play/memory/", views_play.memory_game, name="memory_game"),
    path("play/quiz/", views_play.quiz_list, name="quiz_list"),
    path("play/quiz/<uuid:quiz_id>/", views_play.quiz_play, name="quiz_play"),
    # ── Uči (Learn) ───────────────────────────────────────────
    path("play/learn/", views_play.learning_paths, name="learning_paths"),
    path("play/safety/", views_play.safety_list, name="safety_list"),
    path("play/safety/<uuid:topic_id>/", views_play.safety_detail, name="safety_detail"),
    path("play/europeana/", views_play.europeana_gallery, name="europeana_gallery"),
    # ── Obitelj (Family) ──────────────────────────────────────
    path("play/comfort/", views_play.comfort_home, name="comfort_home"),
    path("play/comfort/<str:situation>/", views_play.comfort_detail, name="comfort_detail"),
    path("play/night/", views_play.dreamguard, name="dreamguard"),
    path("play/joke/", views_play.joke_box, name="joke_box"),
    path("play/quests/", views_play.family_quests, name="family_quests"),
    # ── Rage Engine (Upravljanje bijesom) ─────────────────────
    path("play/emotions/", views_play.emotion_checkin, name="emotion_checkin"),
    path("play/calm/<str:technique>/", views_play.calming_exercise, name="calming_exercise"),
    path("play/conflict/", views_play.conflict_simulator, name="conflict_simulator"),
    # ── Book API (JSON za flip engine) ────────────────────────
    path("play/book/<slug:slug>/", views_play.book_api, name="book_api"),
]
