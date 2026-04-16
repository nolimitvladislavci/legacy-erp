# PLAY.EU — Session Resume Plan
# Datum: 16.04.2026.
# Kontekst: Mega sesija — od 10 sažetaka do 77 URL-ova produkcijske platforme

## ŠTO JE NAPRAVLJENO (kompletno)

### Infrastruktura: 77 URL-ova, 15 migracija, 71 template
- App: memio_world
- Baza: memio_world (odvojena PostgreSQL)
- Server: /var/www/fina-connect, gunicorn-fina
- Venv: /var/www/fina-connect/venv
- Restart: sudo systemctl restart gunicorn-fina

### View fajlovi:
- views_play.py — priče, kvizovi, comfort, rage engine (662→ linija)
- views_games.py — šah, čovječe, slovarica, brojevi, bojanka, vješalica, sat, brodovi, životinje, kuhanje, karta, kreativno pisanje, glazba, sport, ljubimci, azili, obiteljsko stablo, trgovina, flashcards, kalendar, zanimanja, natječaj, događaji, memio škola, diploma, memio maskota, buddy finder, parent onboarding, payment, referral, digital library, pedagogy, help, legal, ambassador, boje, oblici, spomenar, kids ideas
- views_daily.py — daily discovery, parent dashboard
- views_auth.py — register, login, logout, setup, account

### Model fajlovi:
- models.py — core (ChildProfile, TimeCapsule, VoiceLegacy, etc.)
- play_eu_models.py — EuropeanaItem, ParallelStory, HeritageCard
- quiz_models.py — Quiz, QuizQuestion, QuizAnswer, QuizAttempt
- kurikulum_models.py — LearningPath, LifeLesson, WisdomEntry, SafetyTopic, ContentLink
- growth_models.py — TalentProfile, RealWorldVenue, BuddyPair, FamilyQuest, SpacedRepetitionCard, PetBridgePost
- comfort_models.py — ComfortCard, DreamGuard, JokeEntry, CalmingExercise, ConflictScenario, EmotionCheckIn, LegalCompliance
- book_models.py — StoryBookStyle, StoryPage
- parent_models.py — ParentAccount, SessionToken, ChildProgress

### Sadržaj u bazi:
- 22 pune bajke (HR/DE/EN) iz 8 regija (~508 stranica)
- 7 kvizova, 84 pitanja, 336 odgovora
- 20 mudrosti, 15 comfort, 10 dreamguard, 40 šala
- 6 calming vježbi, 3 conflict scenarija
- 40 heritage kartica, 74 europeana items
- 10 obiteljskih izazova, 23 putova učenja, 9 sigurnosnih tema
- 2 admin računa (Marija Čačić, Seki)

### Sigurnost:
- Lozinke: Django hashers (bcrypt/argon2)
- Cookies: httponly + samesite + secure
- SQL: samo ORM, nema raw SQL
- Enkripcija: 12 WorldEncryptedField
- GDPR: consent + deletion fields (migracija 0015)

### Pravni dokumenti:
- ToS (8 članaka)
- Privacy Policy
- GDPR usklađenost (čl. 6, 8, 15-21)
- Zaštita djece (DSA čl.28, AVMSD)
- Licencni ugovor za ambasadore

### Pedagoške smjernice:
- 8 principa
- 8 metoda s akademskim referencama
- 5 dobnih skupina

## ŠTO JOŠ TREBA (sljedeća sesija)

### PRIORITET 1 — Za testiranje s roditeljima
- [ ] Browser test svih stranica (Chrome, Safari, Firefox, mobile)
- [ ] TTS verifikacija na mobilnim uređajima
- [ ] Fix 2 pre-existing broken templates (o_projektu, registracija)
- [ ] Test auth flow end-to-end u browseru

### PRIORITET 2 — Za Mariju Čačić
- [ ] Prezentacija platforme (demo video ili live)
- [ ] Admin dashboard za pedagoški pregled sadržaja
- [ ] Sadržaj validacija checklist

### PRIORITET 3 — Za EU Creative Europe prijavu (svibanj)
- [ ] Udruga registracija
- [ ] Licencni ugovor d.o.o. ↔ udruga
- [ ] Projektni prijedlog (concept note)
- [ ] Proračun projekta
- [ ] Partneri (min 2 EU zemlje)

### PRIORITET 4 — Tehnički
- [ ] Stripe integracija za plaćanje
- [ ] Email sustav (registracija, reset password, izvještaji)
- [ ] AI ilustracije za bajke
- [ ] Europeana API key (pravi, ne demo)
- [ ] CDN za statičke fajlove
- [ ] Automatski backup baze

### PRIORITET 5 — Sadržaj
- [ ] Još 10-15 bajki (Andersen komplet, turske, talijanske, španjolske)
- [ ] Više kvizova (auto-generate za sve bajke)
- [ ] Video tutoriali za roditelje
- [ ] Podcast "Baka čita" (audio snimke pravih baka)

## ADMIN PRISTUP
- Marija: marija.cacic@play.eu / PlayEU-Marija-2026! / ref: PLAY-AE4083
- Seki: seki@nolimit.hr / NoLimit-Seki-2026! / ref: PLAY-0CD016

## KLJUČNI URL-ovi
- Homepage: /api/memio-world/play/
- Registracija: /api/memio-world/play/register/
- Škola: /api/memio-world/play/school/
- Diploma: /api/memio-world/play/diploma/
- Ambasador: /api/memio-world/play/ambassador/
- Parent Dashboard: /api/memio-world/play/parents/
- Plaćanje: /api/memio-world/play/pay/
- Pedagoške smjernice: /api/memio-world/play/pedagogy/
- Pravni dokumenti: /api/memio-world/play/legal/
- Upute: /api/memio-world/play/help/
