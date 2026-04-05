# FENIX STATUS
# Zadnje azuriranje: 2026-04-06 00:10 — Sonnet koordinacija
# Git HEAD: 95f0a6f9
# Server: gunicorn ✅ nginx ✅ celery ✅ mcp-fina ✅ | disk 39% | RAM 3.8/7.6GB

---

## SESIJA 06.04.2026. (nastavak) — RATNA SOBA AKTIVNA

### Novi commiti ove sesije:
  95f0a6f9  fix(pdf): CSS var() → inline values — xhtml2pdf crash fix (22 templates)
  fb5703b2  fix(boxgram): signals correct field names + video_downloader.py
  (+ svi prethodni iz CC sesije — boxgram, memio_world, no_limit, docs)

---

## STANJE FRONTOVA (06.04. 00:10)

### ✅ IZGRAĐENO (CC + Sonnet ova sesija):

  BOXGRAM (memio.pet socijalni sloj):
    - PetProfile, LifeEvent, EventMedia, SocialImport, Competition, PetFollower, EventHeart
    - Views: feed, public_profile, competition, add_event, social import flow
    - Services: social_import.py, video_downloader.py, ai_enrichment.py, memio_bridge.py
    - Templates: feed.html, public_profile.html, competition_detail.html, import_wizard.html
    - Bridge: AnimalProfile signal → auto Boxgram PetProfile + LifeEvent
    - LIVE: memio.pet/boxgram/ljubimac/rex-pas-232d99f5/ ✅ 200
    - LIVE: memio.pet/boxgram/ljubimac/bella-pas-c94b0fa2/ ✅ 200
    - LIVE: memio.pet/boxgram/feed/ ✅ 200
    - Migration: 0001_initial ✅

  MEMIO_WORLD (digitalizacija djetinjstva):
    - Modeli: WaitlistEntry, TimeCapsule, MemoryVault, FamilyStory
    - API: /api/memio-world/waitlist/ (POST) ✅
    - Migration: 0001_initial ✅
    - Čeka: Marija Čačić (knjižničar) za pokretanje

  NO_LIMIT (udruga + azil):
    - Model: AzilPrijava
    - Views: preuzmi_vodic (PDF), vodic_online, prijava_azila
    - Templates: vodic_online.html, PDF vodič
    - Azil dashboard, forme (intervencija, terenska, udomljavanje, životinja)
    - LIVE: /no-limit/vodic/ ✅ 200
    - LIVE: /no-limit/azili/prijava/ → login ✅

  PDF FIX (Sonnet — direktno):
    - 22 PDF template fajla popravljena: var() → inline boje
    - xhtml2pdf crash eliminiran (bio: ValueError: Invalid color value var(--gold))
    - Commit: 95f0a6f9

---

## TASK FAJLOVI NA SERVERU (CC čita redom):

  CC_TASK_F1_UI_AUDIT.md        — LIMIT Connect UI/UX audit (POS + interni moduli)
  CC_TASK_F2_MEMIO_PET_ONBOARDING.md — memio.pet landing + registracija uzgajivača
  CC_TASK_F3_MEMIO_WORLD.md     — memio.world landing + ChildProfile modeli
  CC_TASK_F5_NO_LIMIT_AZIL.md   — azil mobile POS skin + public landing
  GEMINI_TASK_F6_QA_AUDIT.md    — full QA audit za 07.04.
  MARIJA_BRIEF_08_04.md         — brief za Marija dry-run (Ivan šalje)

---

## LIVE HTTP AUDIT (06.04. 00:05):
  ✅ memio.pet/boxgram/ljubimac/rex-*     — 200
  ✅ memio.pet/boxgram/ljubimac/bella-*   — 200
  ✅ memio.pet/boxgram/feed/              — 200
  ✅ memio.pet/barf/                      — 200
  ✅ limit-connect.com/no-limit/vodic/    — 200
  ✅ limit-connect.com/hr/               — 302 → login
  ✅ Django check: 0 errors, 0 new warnings
  ✅ Migracije: sve aplicirane

  BUGS RIJEŠENI:
  ✅ PDF xhtml2pdf CSS var() crash — FIXED 95f0a6f9
  ✅ fenix-mcp inactive — FIXED (restartan)

  PENDING (LOW):
  ⚠️  FenixScan OCR fallback — graceful handling kad Haiku odbija sliku

---

## RATNI RASPORED:
  07.04. | QA audit (Gemini F6) + UI popravci (CC F1)    | CC+Gemini | 🔥
  07.04. | memio.pet onboarding + memio.world landing     | CC F2+F3  | 🔥
  08.04. | Marija dry-run                                  | Marija    | ⏳
  12.04. | Load test (CCX33)                               | CC        | ⏳
  14.04. | DNS cutover priprema                            | Ivan      | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                           | Ivan+Marija | ⏳

## PENDING (Ivan):
  - Konjik razgovor: Scenarij A (639€/mj umjesto 359€)
  - Marija: email brief — MARIJA_BRIEF_08_04.md je spreman, Ivan šalje
  - Gmail OAuth credentials
  - memio.hr registracija domene
  - EUIPO MEMIO trademark prijava
  - HZZ Osijek kvotni upit (10 ambasadora)

## PRICING (finalizirati):
  - Micro: 9€ ili 10€?
  - Starter: 19€ ili 22€?
  - Professional: 49€ ili 69€?
  - Komunalni jednokratni: 990€/1.990€ OK?
  - Računovođa: odvojen plan ili Professional?

## OCJENE STANJA (06.04. 00:10):
  LIMIT Connect backend:    8.5/10
  LIMIT Connect UI/UX:      6.5/10 ← F1 task aktivan
  Boxgram:                  7.5/10 ← feed + profili živi, treba onboarding
  memio.pet:                7/10  ← infrastruktura OK, nema landing/registracija
  memio.world:              4/10  ← modeli OK, nema sučelje
  NO LIMIT / azil:          5/10  ← backend OK, nema public landing + mobile skin
  Server stabilnost:        9.5/10

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
