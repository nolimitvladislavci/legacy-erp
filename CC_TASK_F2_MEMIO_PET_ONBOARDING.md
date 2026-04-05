# CC TASK F2 — memio.pet Onboarding Flow
# Prioritet: 🔥 ODMAH | Rok: 07.04.2026.
# Assignee: Claude Code
# Pilot korisnici: Ljubeta (uzgajivač pasa), Pero Lapis (pčelar/OPG)

## KONTEKST
memio.pet ima solidnu infrastrukturu (16/16 audit ✅, DB odvojen: memio_pets).
Problem: nema načina da se Ljubeta ili Pero registriraju i počnu koristiti sustav.
Nema landing page za memio.pet domenu.
Nema dashboard za uzgajivače.

## ŠTO POSTOJI
- `/pas/<chip>/` — javni profil ljubimca (radi)
- `/uzgajivac/<uuid>/` — javni profil uzgajivača (radi)
- `/barf/` — BARF marketplace (radi)
- `/hotel/` — pet hotel (radi)
- Modeli: BreederProfile, AnimalProfile, PetHealthRecord, PetOwnership...

## ŠTO TREBAŠ IZGRADITI

### 1. memio.pet Landing Page
OBAVEZNO pročitaj modele PRIJE pisanja koda:
```bash
grep -n "^class \|account_type\|is_cro_validated\|trust_score" /var/www/fina-connect/memio_pet/models.py
```

Nova view + template: `GET /` (samo za memio.pet domenu)
- Hero section: "Digitalni identitet vašeg ljubimca"
- 3 CTA: "Registriraj uzgajivača", "Pretraži ljubimce", "BARF Marketplace"
- Design: koristi ISTE CSS varijable kao profile.html (--serif, --sans, --gold, --bg)
- Mobile-first, dark/light toggle

URL: dodaj u memio_pet/urls.py:
```python
path("", views.landing_page, name="landing"),
```

### 2. Registracija uzgajivača (3-korak flow)
URL: `/registracija/`

Korak 1 — Tip računa:
- Radio: uzgajivač pasa / pčelar / OPG / veterinar / pet hotel / dresura
- Ovo puni: BreederProfile.account_type

Korak 2 — Osnovni podaci:
PROVJERI TOČNA POLJA u models.py:
```bash
grep -A 60 "class BreederProfile" /var/www/fina-connect/memio_pet/models.py
```
Forma za: name, email, phone, oib (opcionalno), city, website

Korak 3 — Potvrda:
- "Vaš profil je kreiran. Link vašeg profila: memio.pet/uzgajivac/UUID/"
- Pošalji email s linkom (Django send_mail, SMTP već konfiguriran)

Sesija: koristi request.session za multi-step (bez JS framework-a)

### 3. Breeder Dashboard (login_required)
URL: `/moj-profil/`

Predujet: koristiti LIMIT Connect auth (CustomUser) koji je poveza s BreederProfile.
PROVJERI vezu:
```bash
grep -n "user\|CustomUser\|OneToOne" /var/www/fina-connect/memio_pet/models.py
```

Ako veze nema → dodaj ForeignKey/OneToOne na CustomUser.

Dashboard sadrži:
- Moji ljubimci (lista AnimalProfile)
- Dodaj ljubimca (forma)
- Moji recenzije
- QR kod za svaki ljubimac (link na /pas/CHIP/qr/)
- Trust Score vizualizacija (progress bar)

### 4. Dodaj ljubimca (forma)
URL: `/ljubimac/novi/`
PROVJERI TOČNA POLJA:
```bash
grep -A 80 "class AnimalProfile" /var/www/fina-connect/memio_pet/models.py
```
Forma: name, vrsta (select), breed, chip_number, ear_tag, datum_rodjenja, photo (upload)
Nakon save: redirect na `/pas/CHIP/`

## TEHNIČKE NAPOMENE
- SVE DB operacije: `.using('memio_pets')`
- Auth: standardni Django login_required, LIMIT Connect session
- Templates: nasljeđivanje memio_pet/base.html (ako ne postoji, stvori ga iz profile.html CSS-a)
- Nema Bootstrap, nema jQuery — čisti CSS + vanilla JS
- Mobile-first uvijek

## COMMITI
Format: `feat(memio-pet): [opis]`
Minimum: landing, registracija, dashboard, add-animal = 4 veće commit grupe
