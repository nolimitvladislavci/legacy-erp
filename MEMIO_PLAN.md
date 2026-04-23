# MEMIO.PET — MASTER PLAN v2 "Živi portal"

Status backend-a (postojeće, ne dira se):
- memio_pet: AnimalProfile (9 vrsta), BreederProfile (10 tipova), PetHealthRecord,
  PetOwnership, LifeMilestone, MemorialProfile, DigitalHeritage, RawFoodListing
- boxgram: PetProfile, LifeEvent, EventMedia (image/video/audio), Competition,
  PetFollower, EventHeart, SocialImport — ovo JE memio.gram
- Nginx: / → statički index.html; sve ostalo → Django proxy (:8000)

---

## PLAN-001 — Design system: base template + design tokens
Kreirati: templates/memio/base.html
- Nav: Logo | 🔍 Pretraga | 📸 Gram | 🏪 Marketplace | + Registracija | Prijava
- Footer: links + inovacijski badgevi (.dok / Folija / ChainBlock)
- CSS varijable: --ink, --gold, --surface, --muted (isti kao login)
- Mobile-first, touch-friendly
- Include: CSRF, i18n, Umami analytics snippet

## PLAN-002 — Landing page → Django view s live podacima
- Maknuti statički index.html sa /
- Nginx: location / → proxy Django
- View: landing_page() — dohvaća iz baze:
  * 6 najnovijih AnimalProfile s fotom (hero grid)
  * 4 najnovija boxgram LifeEvent (feed preview)
  * Statistike: broj životinja, uzgajivača, udomljenih
  * Pretraga forma → /pretraga/
- Template: memio/landing.html (nasljeđuje base.html)

## PLAN-003 — Profil životinje — puni karton
Template: memio/pet_profile.html (za view pet_profile_page)
- Hero: profilna foto, ime, vrsta ikona, dob, spol, rasa, QR kod
- Tab 1 "Mediji": boxgram EventMedia grid (foto + video + audio player)
- Tab 2 "Zdravlje": PetHealthRecord timeline (cjepljenja, pregledi, dijagnoze)
- Tab 3 "Prekretnice": LifeMilestone feed s fotografijama
- Tab 4 "Rodovnica": otac/majka chip linkovi + genealoško stablo (2 razine)
- Tab 5 "Vlasništvo": PetOwnership lanac proveniencije
- Sidebar: QR kod (klikabilan za download), status badge, [⬇ Putovnica] gumb (PLAN-008)
- CTA za nelogirane: "Ova životinja traži dom" ili "Kontaktiraj uzgajivača"

## PLAN-004 — boxgram / memio.gram integracija
- /gram/ → Django URL → redirect /boxgram/feed/ (nginx location + url)
- Redesign boxgram templates da nasljeđuju memio/base.html
- Upload stranica: drag&drop foto/video + gumb 🎙 za glasovni zapis
- Post card: foto/video/audio + srce + komentar + dijeli (WhatsApp/IG)
- boxgram feed embedded na landing (PLAN-002)

## PLAN-005 — Pretraga i otkrivanje
- Nova URL + view: /pretraga/
- Filtri: vrsta (pas/mačka/konj...), pasmina, lokacija (grad), status
- Rezultati: kartica s foto, ime, rasa, uzgajivač, badge Trust Score
- Sorting: najnoviji | verificirani | blizina
- Nginx: location /pretraga/ → Django

## PLAN-006 — Marketplace: udomljavanje i prodaja
- Redesign /udomljavanje/ — udomljavanje karton s filtrom (vrsta, grad)
- Nova /prodaja/ — životinje na prodaju (AnimalProfile.status = "rezerviran")
- Animal kartica: foto, ime, rasa, cijena/besplatno, lokacija, kontakt
- Kontakt bez login-a: token form → email/WhatsApp uzgajivaču
- Nginx: location /prodaja/ → Django

## PLAN-007 — Registracija — self-service s trenutnim QR-om
- Redesign /registracija/ s memio.pet brandingom (base.html)
- Korak 1: Email + ime + tip (vlasnik / uzgajivač / azil)
- Korak 2: Dodaj prvog ljubimca (ime, vrsta, chip/tag, foto)
- Korak 3: QR prikazan odmah — "Skenaj i podijeli"
- Share gumb: WhatsApp / Instagram / Download QR PNG

## PLAN-008 — .dok Putovnica (ugrađena inovacija)
- View: /pas/<chip>/putovnica/ → generira .dok ZIP on-the-fly
- Sadržaj: payload.json (AnimalProfile + health + ownership) +
           outfit.json (metapodaci) + proof.json (Folija seal) + viewer.html
- Na profilu: gumb "⬇ Preuzmi Putovnicu" + shield ikonica + tekst
  "Kriptografski verificirano · Folija" (link na inovaciju)
- Nginx: location /pas/ već proxiran

## PLAN-009 — Farma sekcija (odvojena)
- Nova URL grana: /farma/
- Farma landing: konj, ovca, koza, svinja, peradarstvo — komercijalni angle
- Farma profil: /farma/<chip>/ — matični broj, stado, tržišna vrijednost, klaonica/prodaja
- Farma karton: iste tabs kao ljubimac ali s komercijalnim poljima
- Odvojen dizajn: zelenija paleta, manje emotivno, više podatkovni
- Nginx: location /farma/ → Django (novo dodati)

## PLAN-010 — Moj profil (dashboard za vlasnike/uzgajivače)
- Redesign /moj-profil/
- Grid: moje životinje s foto i status badge
- Gumb "Dodaj ljubimca" → token flow → QR odmah
- Marketplace moji oglasi
- Trust Score prikaz s razlogom
- Download svih Putovnica

## PLAN-011 — Brzi login (ugrađen, ne opisan)
- Redesign /prijava/ s memio.pet brandingom
- PIN gumb funkcionalan (QuickLogin view — već postoji, samo wiring)
- "Zaboravljen PIN?" → email reset
- Magic link opcija (email → link → login bez lozinke)
- Passkey support (WebAuthn) — Future

## PLAN-012 — Nginx proširenje (sve rute)
- Dodati: /gram/ /pretraga/ /prodaja/ /farma/ /putovnica/ (ako treba)
- Konsolidirati sve lokacije u jedan nginx block pattern
- CSP header s Umami analytics dopušten
- Media upload limit: 50MB za video

## PLAN-013 — AI media obrada (background)
- Glasovni zapis upload → Celery task → Whisper/Gemini transkripcija → tekst
- Foto upload → Gemini vision → auto-detekcija rase → predloži breed field
- Video upload → thumbnail ekstrakcija (ffmpeg) → cover za post
- Sve u pozadini, korisnik ne čeka

## PLAN-014 — Vet most (Fenix V3 ↔ memio.pet)
- API endpoint na memio.pet: POST /api/vet/health-record/ (signed s api_key)
- Fenix V3 veterinar dodaje pregled → šalje na memio.pet API
- Pojavljuje se u Tab "Zdravlje" na profilu životinje
- Vet vidi životinju na /hr/veterinar/<chip>/ u Fenix V3
- Obostrani prikaz: vlasnik vidi vet zapise, vet vidi cijeli karton

---

## REDOSLJED IMPLEMENTACIJE
001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 010 → 011 → 012 → 013 → 014

## DEFINICIJA DONE po PLANU
Svaki PLAN: view radi, template postoji, nginx ruta wirana, manage.py check OK, commit.
