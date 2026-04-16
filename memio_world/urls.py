from django.urls import path

from memio_world import views, views_auth, views_daily, views_games, views_play

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
    path("play/shop/", views_games.virtual_shop, name="virtual_shop"),
    path("play/flashcards/", views_games.flashcards, name="flashcards"),
    path("play/calendar/", views_games.calendar_page, name="calendar_page"),
    path("play/contest/", views_games.contest_page, name="contest_page"),
    path("play/careers/", views_games.careers_page, name="careers_page"),
    path("play/events/", views_games.events_page, name="events_page"),
    path("play/school/", views_games.memio_school, name="memio_school"),
    path("play/diploma/", views_games.diploma_page, name="diploma_page"),
    path("play/memio/", views_games.memio_mascot, name="memio_mascot"),
    path("play/buddy/", views_games.buddy_finder, name="buddy_finder"),
    path("play/start/", views_games.parent_onboarding, name="parent_onboarding"),
    path("play/pay/", views_games.payment_page, name="payment_page"),
    path("play/refer/", views_games.referral_page, name="referral_page"),
    path("play/library/", views_games.digital_library, name="digital_library"),
    path("play/pedagogy/", views_games.pedagogy_page, name="pedagogy_page"),
    path("play/help/", views_games.help_page, name="help_page"),
    path("play/legal/", views_games.legal_page, name="legal_page"),
    path("play/ambassador/", views_games.ambassador_page, name="ambassador_page"),
    # ── Boje + Geometrijski oblici ────────────────────────────
    path("play/colors/", views_games.colors_game, name="colors_game"),
    path("play/shapes/", views_games.shapes_game, name="shapes_game"),
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
    # ── Azili + Obiteljsko stablo ─────────────────────────────
    path("play/shelter/", views_games.shelter_program, name="shelter_program"),
    path("play/family-tree/", views_games.family_tree, name="family_tree"),
    # -- Spomenar + Ideje ----------------------------------------
    path("play/spomenar/", views_games.spomenar_page, name="spomenar_page"),
    path("play/ideas/", views_games.kids_ideas, name="kids_ideas"),
    # ── Auth (registracija, login, setup) ─────────────────
    path("play/register/", views_auth.register_page, name="register_page"),
    path("play/register/do/", views_auth.register_action, name="register_action"),
    path("play/login/", views_auth.login_page, name="login_page"),
    path("play/login/do/", views_auth.login_action, name="login_action"),
    path("play/logout/", views_auth.logout_action, name="logout_action"),
    path("play/setup/", views_auth.setup_page, name="setup_page"),
    path("play/setup/child/", views_auth.setup_child_action, name="setup_child_action"),
    path("play/account/", views_auth.account_page, name="account_page"),
    # ── Book API (JSON za flip engine) ────────────────────────
    path("play/book/<slug:slug>/", views_play.book_api, name="book_api"),
]
