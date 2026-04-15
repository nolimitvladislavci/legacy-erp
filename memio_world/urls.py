from django.urls import path

from memio_world import views, views_play

app_name = "memio_world"

urlpatterns = [
    # Existing
    path("waitlist/", views.waitlist_signup, name="waitlist_signup"),
    path("waitlist/count/", views.waitlist_count, name="waitlist_count"),
    path("registracija/", views.registracija_page, name="registracija"),
    path("o-projektu/", views.o_projektu_page, name="o_projektu"),
    # PLAY.EU Frontend — Faza E
    path("play/", views_play.play_home, name="play_home"),
    # Stories
    path("play/stories/", views_play.story_list, name="story_list"),
    path("play/stories/<slug:slug>/", views_play.story_detail, name="story_detail"),
    # Heritage Cards
    path("play/cards/", views_play.card_list, name="card_list"),
    path("play/memory/", views_play.memory_game, name="memory_game"),
    # Quiz
    path("play/quiz/", views_play.quiz_list, name="quiz_list"),
    path("play/quiz/<uuid:quiz_id>/", views_play.quiz_play, name="quiz_play"),
    # Comfort
    path("play/comfort/", views_play.comfort_home, name="comfort_home"),
    path("play/comfort/<str:situation>/", views_play.comfort_detail, name="comfort_detail"),
    # DreamGuard
    path("play/night/", views_play.dreamguard, name="dreamguard"),
    # JokeBox
    path("play/joke/", views_play.joke_box, name="joke_box"),
]
