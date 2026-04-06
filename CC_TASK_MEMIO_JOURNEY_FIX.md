# CC TASK — MEMIO.PET KOMPLETNI USER JOURNEY FIX
# Prioritet: 🔴 KRITIČNO | Rok: 07.04.2026. prije 10:00
# Ivan: "krkljanac na dodaj profil — katastrofa, linkovi vode na LIMIT Connect"
# Assignee: Claude Code

## OBVEZNO PRVO — čitaj stvarne modele i URL-e
```bash
grep -n "^class\|email\|user_id\|token" /var/www/fina-connect/memio_pet/models.py | head -40
cat /var/www/fina-connect/memio_pet/urls.py
grep -n "def registracija\|def add_animal\|def breeder" /var/www/fina-connect/memio_pet/views.py | head -20
```

---

## MAPA PROBLEMA (verificirano 07.04.)

Korisnikov put:
  landing → registracija ✅
  registracija → uzgajivac/UUID/ ✅
  uzgajivac/UUID/ → "Dodaj ljubimca" → /ljubimac/zatrazi/ → 404 ❌  ← BLOKER
  uzgajivac/UUID/ → "Kreiraj novi profil" → /registracija/ ✅
  moj-profil/ → traži LIMIT Connect login koji ne postoji na memio.pet ❌

---

## ZADATAK 1 — Session auth za "Dodaj ljubimca" (MVP, brzo)

### Zašto session, ne magic token (za sad):
Magic token zahtijeva email slanje (SMTP konfiguracija za memio.pet).
Session je dovoljan za pilot fazu — korisnik je upravo registriran,
session je svjež, breeder UUID je u sessionu.

### Korak A: Spremi breeder u session pri registraciji

U `views.py`, funkcija `registracija()`, nakon uspješnog kreiranja bp:
```python
# DODAJ ovo PRIJE return redirect:
request.session['memio_breeder_pk'] = str(bp.pk)
request.session['memio_breeder_email'] = bp.email
request.session.set_expiry(86400 * 7)  # 7 dana
```

### Korak B: add_animal čita iz sessiona

Zamijeni cijeli `def add_animal(request)` — PROČITAJ STVARNA POLJA MODELA PRVO:
```bash
grep -A 50 "class AnimalProfile" /var/www/fina-connect/memio_pet/models.py | grep "= models\."
```

Nova view logika (bez @login_required):
```python
def add_animal(request):
    db = 'memio_pets'
    
    # 1. Provjeri session (svježa registracija)
    breeder_pk = request.session.get('memio_breeder_pk')
    
    # 2. Fallback: GET param + session potvrda (sigurno jer provjeravamo oboje)
    if not breeder_pk:
        breeder_pk = request.GET.get('breeder') or request.POST.get('breeder_id')
    
    # 3. Nema ničega → forma za email verifikaciju
    if not breeder_pk:
        return render(request, 'memio_pet/add_animal_auth.html', {})
    
    try:
        import uuid as _u
        breeder = BreederProfile.objects.using(db).get(pk=_u.UUID(str(breeder_pk)))
    except Exception:
        messages.error(request, 'Profil nije pronađen.')
        return redirect('memio_pet:registracija')
    
    if request.method == 'POST':
        # ČITAJ STVARNA POLJA IZ MODELA - ne pretpostavljaj
        # ... procesiranje ...
        animal.save(using=db)
        request.session['memio_breeder_pk'] = str(breeder.pk)  # osvježi session
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)
    
    return render(request, 'memio_pet/add_animal.html', {
        'breeder': breeder,
        'breeder_id': str(breeder.pk),  # za hidden field u formi
    })
```

### Korak C: Dodaj URL za add_animal
```python
# urls.py — dodaj:
path("ljubimac/novi/", views.add_animal, name="add_animal"),
path("ljubimac/zatrazi/", views.add_animal, name="add_animal_zatrazi"),  # alias
```

### Korak D: add_animal.html forma mora imati hidden breeder_id
```html
<form method="post" action="/ljubimac/novi/">
  {% csrf_token %}
  <input type="hidden" name="breeder_id" value="{{ breeder_id }}">
  <!-- ostala polja -->
</form>
```

---

## ZADATAK 2 — add_animal.html template (ako ne postoji ili je neispravan)

Provjeri:
```bash
ls /var/www/fina-connect/templates/memio_pet/add_animal.html
```

Template mora:
- Prikazati ime breeder-a ("Dodaješ ljubimca za: Ivan Brtan")
- Forma: ime, vrsta (select), pasmina, čip broj (opcionalno), datum rodjenja, spol, foto upload
- Submit → POST na /ljubimac/novi/
- Nazad link → /uzgajivac/BREEDER_UUID/
- Vizual: isti CSS kao breeder.html (--gold, --ink, --bg, --serif)
- NIKAKAV link na limit-connect.com/hr/

---

## ZADATAK 3 — KOMPLETNA VERIFIKACIJA SVIH LINKOVA

### 3A: Provjeri sve href i action u svakom memio_pet templateu
```bash
grep -rh "href=\|action=" /var/www/fina-connect/templates/memio_pet/*.html \
  | grep -oP '(href|action)="[^"]+"' \
  | sort | uniq
```

**Zabranjena odredišta (moraju biti 0 pojavljivanja):**
```bash
# Ova provjera mora vratiti NIŠTA:
grep -rn "limit-connect.com/hr/register\|limit-connect.com/hr/login\|limit-connect.com/pricing\|no-limit.world" \
  /var/www/fina-connect/templates/memio_pet/ \
  /var/www/memio-pet/index.html
```

**Ako nađeš → fix odmah, ne nastavljaj bez fixa.**

### 3B: HTTP status svakog linka koji se pojavljuje u templateima
```python
# Pokreni ovaj test za sve memio.pet stranice:
import subprocess, re

pages = [
    'https://memio.pet/',
    'https://memio.pet/registracija/',
    'https://memio.pet/pas/191031000312345/',
    'https://memio.pet/uzgajivac/bb2747ca-6439-4e5d-9b2c-927dfccb881c/',
    'https://memio.pet/barf/',
    'https://memio.pet/hotel/',
    'https://memio.pet/dresura/',
]

BAD = ['limit-connect.com/hr', 'no-limit.world', '/pricing', '/paketi']
problems = []

for page in pages:
    html = subprocess.run(['curl','-s','--max-time','8',page],
                          capture_output=True,text=True).stdout
    hrefs = re.findall(r'href=["\']([^"\'#]+)["\']', html)
    for h in hrefs:
        for b in BAD:
            if b in h:
                problems.append(f'[{page}] BAD LINK: {h}')
        if h.startswith('/') and h not in ['/','#']:
            full = f'https://memio.pet{h}'
            code = subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code}',
                                   '--max-time','5',full],
                                  capture_output=True,text=True).stdout
            if code not in ['200','301','302']:
                problems.append(f'[{page}] HTTP {code}: {h}')

for p in problems:
    print('❌', p)
if not problems:
    print('✅ Svi linkovi čisti')
```

---

## ZADATAK 4 — KOMPLETNI USER JOURNEY TEST

Nakon implementacije, provjeri svaki korak ručno:

```
JOURNEY 1 — Nova registracija:
  memio.pet/ → klik "Kreiraj profil" → /registracija/
  Unesi: ime, email, grad, tip=breeder
  Submit → redirect /uzgajivac/UUID/  ✓
  Na profilu: klik "+ Dodaj ljubimca" → /ljubimac/novi/?breeder=UUID  ✓
  Forma za ljubimca: popuni → submit → redirect /pas/CHIP/  ✓
  Na psu: podaci vidljivi, QR link radi  ✓

JOURNEY 2 — Povratak bez sessiona:
  Otvori /uzgajivac/UUID/ (čist browser)
  Klik "+ Dodaj" → pita za email → verificira → dozvoli  ✓

JOURNEY 3 — Krive veze = NEMA:
  Nigdje ne smije biti: limit-connect.com/hr/register ili /pricing
  Svaki link → memio.pet ili limit-connect.com/no-limit/ (azil)  ✓
```

---

## ZADATAK 5 — NGINX: sve memio.pet rute kroz Gunicorn

Provjeri da nginx config ima proxy za SVE Django rute:
```bash
cat /etc/nginx/sites-enabled/memio-pet
```

Mora biti proxy za:
- /pas/ ✅
- /uzgajivac/ ✅ 
- /registracija/ ✅
- /ljubimac/ ✅
- /moj-profil/ ✅
- /barf/ ✅
- /hotel/ ✅
- /dresura/ ✅
- /boxgram/ ✅
- /badge/ ✅

Ako nešto nedostaje → dodaj.

---

## COMMITI

Format: `fix(memio-pet): [opis]`

1. `fix(memio-pet): add_animal session auth + url zatrazi`
2. `fix(memio-pet): add_animal.html template — forme bez limit-connect linkova`
3. `audit(memio-pet): nema zabranjenih linkova — verificirano`
4. `fix(nginx): sve memio.pet rute na Gunicorn`

---

## KRAJNJA VERIFIKACIJA (obavezna prije commita)

```bash
# 1. Django 0 errors
venv/bin/python manage.py check

# 2. Nema zabranjenih linkova
grep -rn "limit-connect.com/hr/register\|/pricing\|no-limit.world" \
  templates/memio_pet/ && echo "❌ PROBLEM" || echo "✅ ČISTO"

# 3. Sve rute žive
for url in \
  "https://memio.pet/ljubimac/novi/" \
  "https://memio.pet/ljubimac/zatrazi/" \
  "https://memio.pet/registracija/" \
  "https://memio.pet/uzgajivac/bb2747ca-6439-4e5d-9b2c-927dfccb881c/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url")
  echo "$code $url"
done
# SVE mora biti 200 ili 302-na-login (ne 404, ne 500)

# 4. Napiši JOURNEY_REPORT_07_04.md s rezultatima
```
