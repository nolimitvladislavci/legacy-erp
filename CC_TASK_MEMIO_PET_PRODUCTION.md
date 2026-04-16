# CC TASK: memio.pet — Testna faza → Produkcija

**Prioritet:** CRITICAL  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Odobrio:** Sonnet (koordinator)

---

## TRENUTNO STANJE (izmjereno 2026-04-16)

```
AnimalProfiles: 2
BreederProfiles: 15
Nginx: LIVE na memio.pet (SSL certifikat aktivan)
Landing: statički /var/www/memio-pet/index.html (postoji, radi)
Django app: memio_pet/ postoji u LIMIT Connect projektu
Nginx routing: /pas/, /uzgajivac/, /badge/, /barf/, /hotel/ → proxy 127.0.0.1:8000
```

**Problem:** Landing page je statički HTML. Django backend živi unutar  
LIMIT Connect projekta ali **nema vlastiti entry point** za memio.pet.

---

## CILJ

memio.pet mora biti funkcionalan javni portal:
1. Besplatna registracija uzgajivača
2. Profil ljubimca s QR kodom (javno dostupno bez login-a)
3. Pretraga ljubimaca / uzgajivača
4. Priprema za Petar Brtan (golubovi, pilot user)

---

## ŠTO TREBA NAPRAVITI

### KORAK 1 — Audit postojećeg stanja

```bash
# Pročitaj SVE relevantne fajlove
cat /var/www/fina-connect/memio_pet/models.py
cat /var/www/fina-connect/memio_pet/views.py
cat /var/www/fina-connect/memio_pet/urls.py
cat /etc/nginx/sites-enabled/memio-pet
```

Napiši popis:
- Koje views postoje i rade?
- Koje views postoje ali imaju bugove?
- Što nedostaje za MVP?

### KORAK 2 — Provjeri RouteRegistry

```python
# U core/route_registry.py provjeri je li memio_pet registriran
grep -r "memio_pet\|memio.pet" /var/www/fina-connect/core/route_registry.py
```

Ako nije registriran → add:
```python
"memio_pet": AccessLevel.PUBLIC,  # Landing + profili su javni
```

### KORAK 3 — Fix critical bugs

Provjeri Sentry ili logove za memio_pet greške:
```bash
tail -200 /var/log/nginx/error.log | grep memio
journalctl -u gunicorn --since "24 hours ago" | grep memio_pet | head -20
```

Fix sve BLOCK-level bugove (stranica se ne učitava, 500 greška, redirect loop).

### KORAK 4 — Landing page integracija

Trenutni landing (`/var/www/memio-pet/index.html`) je statički.  
Provjeri postoji li Django view za landing:
```python
# memio_pet/views.py — postoji li landing_page view?
```

Ako postoji:  
→ Update nginx da `/` ide na Django, ne statički HTML  
→ Zadrži statički kao fallback

Ako ne postoji:  
→ Kreiraj jednostavan `landing_page` view koji servira index.html kao template

### KORAK 5 — QR kod flow (core feature)

Ovo je srž memio.pet — ljubimac dobije QR koji vodi na javni profil.

Provjeri:
- `AnimalProfile` ima li `chip_or_tag` polje za URL
- `pet_profile_page` view radi li za anonimnog korisnika
- QR generiranje radi li (postoji li `pet_qr_code` view)

Testiraj ručno:
```bash
curl -s "https://memio.pet/pas/test-qr-123/" | head -20
```

Fix što ne radi.

### KORAK 6 — Testna faza setup

Napravi test uzgajivača i test ljubimca:
```python
# U Django shell
from memio_pet.models import BreederProfile, AnimalProfile
# Kreiraj test profile ako ne postoje
```

Generiraj QR kod, provjeri da link radi javno bez logina.

### KORAK 7 — Smoke testovi

Napiši `/var/www/fina-connect/memio_pet/tests_smoke.py`:

```python
# Minimalni smoke testovi:
# 1. GET /                 → 200 (landing)
# 2. GET /pas/{chip}/      → 200 (javni profil)  
# 3. GET /registracija/    → 200 (forma za uzgajivače)
# 4. GET /uzgajivac/{id}/  → 200 (profil uzgajivača)
# 5. GET /pas/{chip}/qr/   → 200 ili redirect na QR sliku
```

Svi moraju proći bez 500 greške.

### KORAK 8 — Nginx finalizacija

Provjeri nginx config:
```bash
nginx -t
cat /etc/nginx/sites-enabled/memio-pet
```

- `location /` mora servirati Django (ne statički HTML)
- `location /static/` mora servirati `/var/www/fina-connect/staticfiles/`
- `location /media/` mora servirati media
- SSL certifikat valjan?

### KORAK 9 — Petar Brtan modul (golubovi)

Provjeri postoji li Golubar modul:
```bash
find /var/www/fina-connect -name "*golubar*" -o -name "*pigeon*" | grep -v venv
```

Ako postoji → provjeri je li integriran s memio_pet  
Ako ne postoji → **samo napiši u izvještaju šta treba**, ne implementiraj sada

---

## IZVJEŠTAJ ZA SONETA

Napiši `/var/www/fina-connect/CC_REPORT_MEMIO_PET.md`:

```markdown
## Stanje (2026-04-16)
- Što radi: ...
- Što ne radi: ...
- Kritični bugovi: ...

## Napravljeno
- ...

## Smoke testovi
- X/5 prolazi

## Preporuka za produkciju
- DA odmah / DA uz uvjete / NE (razlog)
- Uvjeti: ...

## Petar Brtan (Golubar)
- Postoji li modul? ...
- Što treba za pilot?
```

---

## ŠTO NE RADIŠ
- ❌ Ne mijenjaš LIMIT Connect ERP (samo memio_pet app)
- ❌ Ne radiš novi dizajn — koristi postojeće templatese
- ❌ Ne implementiraš plaćanje/pretplatu
- ❌ Ne commitas bez testa

---

## DEFINICIJA DONE
- [ ] 5/5 smoke testova prolazi
- [ ] Javni profil ljubimca dostupan bez login-a
- [ ] QR kod generira se i radi
- [ ] CC_REPORT_MEMIO_PET.md napisan
- [ ] nginx config ispravan

