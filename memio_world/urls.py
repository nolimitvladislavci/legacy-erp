from django.urls import path

from memio_world import views, views_daily, views_games, views_play

app_name = "memio_world"

urlpatterns = [
    # ── Existing ──────────────────────────────────────────────
    path("waitlist/", views.waitlist_signup, name="waitlist_signup"),
    path("waitlist/count/", views.waitlist_count, name="waitlist_count"),
    path("registracija/", views.registracija_page, name="registracija"),
    path("o-projektu/", views.o_projektu_page, name="o_projektu"),
    # ── PLAY.EU — Home ────────────────────────────────────────
    path("play/", views_play.play_home, name="play_home"),
    # ── Daily Discovery ───────────────────────────────────────
    path("play/today/", views_daily.daily_discovery, name="daily_discovery"),
    # ── Parent Dashboard ──────────────────────────────────────
    path("play/parents/", views_daily.parent_dashboard, name="parent_dashboard"),
    # ── Čitaj (Read) ──────────────────────────────────────────
    path("play/stories/", views_play.story_list, name="story_list"),
    path("play/stories/<slug:slug>/", views_play.story_detail, name="story_detail"),
    path("play/wisdom/", views_play.wisdom_list, name="wisdom_list"),
    # ── Igraj (Play) ──────────────────────────────────────────
    path("play/cards/", views_play.card_list, name="card_list"),
    path("play/memory/", views_play.memory_game, name="memory_game"),
    path("play/quiz/", views_play.quiz_list, name="quiz_list"),
    path("play/quiz/<uuid:quiz_id>/", views_play.quiz_play, name="quiz_play"),
    # ── Šah škola ─────────────────────────────────────────────
    path("play/chess/", views_games.chess_home, name="chess_home"),
    path("play/chess/learn/<str:piece>/", views_games.chess_learn, name="chess_learn"),
    path("play/chess/puzzle/", views_games.chess_puzzle, name="chess_puzzle"),
    path("play/chess/memory/", views_games.chess_memory, name="chess_memory"),
    # ── Slovarica + Brojevi ────────────────────────────────
    path("play/alphabet/", views_games.alphabet_game, name="alphabet_game"),
    path("play/numbers/", views_games.numbers_game, name="numbers_game"),
    path("play/coloring/", views_games.coloring_page, name="coloring_page"),
    path("play/hangman/", views_games.hangman_game, name="hangman_game"),
    path("play/clock/", views_games.clock_game, name="clock_game"),
    path("play/battleship/", views_games.battleship_game, name="battleship_game"),
    # ── Kreativno + Životinje + Kuhanje + Karta ──────────
    path("play/write/", views_games.creative_writing, name="creative_writing"),
    path("play/animals/", views_games.animal_sounds, name="animal_sounds"),
    path("play/cooking/", views_games.cooking_recipes, name="cooking_recipes"),
    path("play/map/", views_games.story_map, name="story_map"),
    path("play/pets/", views_games.pet_corner, name="pet_corner"),
    path("play/music/", views_games.music_corner, name="music_corner"),
    path("play/sports/", views_games.sports_corner, name="sports_corner"),
    # ── Čovječe ne ljuti se ───────────────────────────────────
    path("play/ludo/", views_games.ludo_game, name="ludo_game"),
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
