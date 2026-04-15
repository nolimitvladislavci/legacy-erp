# PLAY.EU — FAZA E: FRONTEND UI
> Agent: Opus CC | Start: 2026-04-15 | Deadline: Creative Europe 2026-05-07

## STANJE PRIJE
- 23 modela, 237 sadržaja u memio_world bazi
- 2 template-a (registracija + o_projektu)
- 4 URL rute (waitlist API)
- 0 static fajlova za memio_world
- Dizajn jezik: dark + gold (#c9a84c) + Cormorant Garamond serif

## PLAN

### E1: PWA Shell + Base Template
- [ ] `static/memio_world/manifest.json` — PWA manifest
- [ ] `static/memio_world/sw.js` — Service Worker (offline shell)
- [ ] `static/memio_world/play-eu.css` — Parchment tema (topla, dječja, mobile-first)
- [ ] `templates/memio_world/base_play.html` — PWA base sa bottom nav
- [ ] `templates/memio_world/home.html` — Landing/discover page
- [ ] URL: `/api/memio-world/play/` — home view

### E2: Bajka Reader (Demo A)
- [ ] `views_play.py` — story_list, story_detail, heritage_cards, quiz_play
- [ ] `templates/memio_world/story_list.html` — Popis priča s filterima
- [ ] `templates/memio_world/story_detail.html` — Reader s HR/DE/EN toggle
- [ ] URL: `/api/memio-world/play/stories/`
- [ ] URL: `/api/memio-world/play/stories/<id>/`

### E3: Heritage Cards + Memory Game (Demo B)
- [ ] `templates/memio_world/cards.html` — Galerija kartica (slovarica + bestijarij)
- [ ] `templates/memio_world/memory_game.html` — Memory igra (JS flip cards)
- [ ] URL: `/api/memio-world/play/cards/`
- [ ] URL: `/api/memio-world/play/memory/`

### E4: Quiz Engine UI (Demo B nastavak)
- [ ] `templates/memio_world/quiz_list.html` — Popis kvizova
- [ ] `templates/memio_world/quiz_play.html` — Igranje kviza (HTMX/JS)
- [ ] `templates/memio_world/quiz_result.html` — Rezultat + badges
- [ ] URL: `/api/memio-world/play/quiz/`
- [ ] URL: `/api/memio-world/play/quiz/<id>/`

### E5: Kurikulum + Parent Dashboard (Demo C)
- [ ] `templates/memio_world/learning_paths.html` — Putovi učenja po dobi
- [ ] `templates/memio_world/dashboard_parent.html` — Napredak djeteta
- [ ] URL: `/api/memio-world/play/learn/`
- [ ] URL: `/api/memio-world/play/dashboard/`

### E6: Comfort Engine UI
- [ ] `templates/memio_world/dreamguard.html` — Noćni UI (topla žuta, veliki font, audio)
- [ ] `templates/memio_world/jokebox.html` — Dnevna šala/zagonetka
- [ ] `templates/memio_world/comfort.html` — ComfortCard (dijete bira emociju)
- [ ] URL: `/api/memio-world/play/night/`
- [ ] URL: `/api/memio-world/play/joke/`
- [ ] URL: `/api/memio-world/play/comfort/`

### E7: Deploy + Test
- [ ] collectstatic
- [ ] gunicorn reload
- [ ] Browser test: mobile + desktop
- [ ] Offline test (SW cache)

## REDOSLIJED
E1 → E2 → E3 → E4 → E5 → E6 → E7

## NAPOMENA
Sve rute PUBLIC (bez logina) — ovo je demo za Creative Europe komisiju.
Baza: memio_world (separate DB, router handles it).
