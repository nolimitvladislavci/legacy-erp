# CC TASK — PRAVNI BLOKERI + VETERINAR STRANICA
# Prioritet: 🔴 VISOK — blokira go-live 15.04.
# Assignee: Claude Code
# Rok: 08.04.2026. (prije Marija dry-run)

## OBVEZNO PRVO
```bash
cd /var/www/fina-connect
git log --oneline -3
venv/bin/python manage.py check 2>&1 | tail -2
grep -n "^class\|cookie\|privacy\|uvjeti" memio_pet/models.py | head -10
```

---

## ZADATAK 1 — COOKIE BANNER (EU zahtjev, bloker)

### Gdje dodati
SVE stranice koje imaju vlastiti HTML (ne nasljeđuju base.html):
- /var/www/memio-pet/index.html          ← statički
- templates/memio_pet/registracija.html
- templates/memio_pet/breeder.html
- templates/memio_pet/profile.html
- templates/memio_pet/add_animal.html
- templates/memio_pet/dashboard.html
- templates/memio_world/landing.html
- templates/no_limit/azil_landing.html

### Što implementirati
Minimalni GDPR-compliant cookie banner:

```html
<!-- COOKIE BANNER — dodaj prije </body> -->
<div id="cookie-banner" style="
  display:none;position:fixed;bottom:0;left:0;right:0;z-index:9999;
  background:var(--ink,#1a1a2e);color:rgba(248,246,240,.9);
  padding:16px 24px;font-size:13px;
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:12px;
  border-top:2px solid var(--gold,#c9a84c)">
  <span>
    Koristimo kolačiće za poboljšanje iskustva.
    <a href="/privatnost/" style="color:var(--gold,#c9a84c)">Politika privatnosti</a>
  </span>
  <div style="display:flex;gap:8px">
    <button onclick="acceptCookies()"
      style="background:var(--gold,#c9a84c);border:none;padding:8px 20px;
             border-radius:6px;font-weight:700;cursor:pointer;color:#1a1a2e;
             font-family:inherit;font-size:13px">Prihvati</button>
    <button onclick="declineCookies()"
      style="background:transparent;border:1px solid rgba(255,255,255,.3);
             padding:8px 20px;border-radius:6px;cursor:pointer;color:inherit;
             font-family:inherit;font-size:13px">Samo nužni</button>
  </div>
</div>

<script>
(function(){
  var cb = document.getElementById('cookie-banner');
  if (!cb) return;
  if (!localStorage.getItem('cookie-consent')) {
    cb.style.display = 'flex';
  }
})();

function acceptCookies() {
  localStorage.setItem('cookie-consent', 'all');
  document.getElementById('cookie-banner').style.display = 'none';
}
function declineCookies() {
  localStorage.setItem('cookie-consent', 'essential');
  document.getElementById('cookie-banner').style.display = 'none';
}
</script>
```

### Dodaj u SVE template fajlove gore
PROVJERI da svaki ima `id="cookie-banner"` samo jednom (ne duplikat).

---

## ZADATAK 2 — POLITIKA PRIVATNOSTI + OPĆI UVJETI

### Kreiraj view u memio_pet/views.py
```python
def privatnost(request):
    return render(request, 'memio_pet/privatnost.html', {
        'page_title': 'Politika privatnosti — Memio.pet'
    })

def uvjeti(request):
    return render(request, 'memio_pet/uvjeti.html', {
        'page_title': 'Opći uvjeti korištenja — Memio.pet'
    })
```

### Dodaj URLs
```python
path("privatnost/", views.privatnost, name="privatnost"),
path("uvjeti/", views.uvjeti, name="uvjeti"),
```

### Template: privatnost.html
Dizajn: isti kao registracija.html (--gold, --ink, --serif)
Sadržaj (GDPR minimum):

```
POLITIKA PRIVATNOSTI — Memio.pet
Zadnje ažuriranje: 08.04.2026.
Operator: Konjik d.o.o. | OIB: [iz .env ili DB] | ivan@limit-connect.com

1. KOJE PODATKE PRIKUPLJAMO
   - Ime i email adresa (pri registraciji)
   - Podaci o ljubimcu (čip, pasmina, zdravlje)
   - IP adresa i kolačići sesije (tehnički nužni)

2. KAKO KORISTIMO PODATKE
   - Kreiranje i upravljanje profilom ljubimca
   - Javni prikaz profila (samo podaci koje vi dodate)
   - Slanje potvrda putem emaila

3. DIJELJENJE PODATAKA
   - Ne prodajemo podatke trećim stranama
   - Javni profil je dostupan svima s linkom
   - Hetzner (hosting, EU) — GDPR sukladan

4. VAŠA PRAVA (GDPR čl. 15-22)
   - Pristup, ispravak, brisanje podataka: ivan@limit-connect.com
   - Prigovor nadzornom tijelu: AZOP (azop.hr)

5. KOLAČIĆI
   - Nužni: session kolačić (prijava)
   - Analitički: samo uz vašu suglasnost

6. KONTAKT
   Konjik d.o.o. | ivan@limit-connect.com
```

### Template: uvjeti.html
```
OPĆI UVJETI KORIŠTENJA — Memio.pet
Zadnje ažuriranje: 08.04.2026.

1. USLUGA
   Memio.pet je digitalna platforma za upravljanje profilima ljubimaca.
   Operator: Konjik d.o.o., Čepin, Hrvatska

2. REGISTRACIJA
   Za korištenje usluge unosite email i osnovne podatke.
   Odgovorni ste za točnost unesenih podataka.

3. SADRŽAJ
   Vlasnik ste sadržaja koji unosite.
   Dajete nam licencu za prikaz tog sadržaja na platformi.

4. BESPLATNA USLUGA
   Osnovna usluga je besplatna i ostaje besplatna.
   Premium funkcije mogu biti naplaćene uz prethodnu obavijest.

5. ODGOVORNOST
   Platforma se pruža "kakva jest". Ne jamčimo neprekidan rad.
   Nismo odgovorni za točnost podataka koje korisnici unose.

6. IZMJENE
   Uvjeti se mogu mijenjati uz 30 dana obavijesti emailom.

7. PRAVO
   Primjenjuje se hrvatsko pravo. Nadležan sud: Osijek.
```

### NGINX — dodaj rute za /privatnost/ i /uvjeti/ na memio.pet
Provjeri:
```bash
grep "privatnost\|uvjeti" /etc/nginx/sites-enabled/memio-pet
```
Ako ne postoji → dodaj:
```nginx
location /privatnost/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /uvjeti/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Potom: `nginx -t && systemctl reload nginx`

---

## ZADATAK 3 — VETERINAR JAVNA STRANICA

### Provjeri model
```bash
grep -A 30 "class VeterinarProfile" /var/www/fina-connect/memio_pet/models.py
```

### View
```python
def veterinar_profile_page(request, vet_id):
    db = 'memio_pets'
    try:
        import uuid as _u
        vet = VeterinarProfile.objects.using(db).get(pk=_u.UUID(str(vet_id)))
    except VeterinarProfile.DoesNotExist:
        return render(request, 'memio_pet/not_found.html', {
            'chip_or_tag': 'veterinar'
        }, status=404)

    # Životinje koje je verificirao
    verified_animals = AnimalProfile.objects.using(db).filter(
        verified_by=vet
    ).order_by('-created_at')[:10] if hasattr(AnimalProfile, 'verified_by') else []

    return render(request, 'memio_pet/veterinar.html', {
        'vet': vet,
        'verified_count': verified_animals.count() if verified_animals else 0,
        'page_title': f'Dr. {vet.name} — Memio.pet',
    })
```

PROVJERI stvarna polja modela VeterinarProfile PRIJE pisanja koda:
```bash
grep -A 40 "class VeterinarProfile" /var/www/fina-connect/memio_pet/models.py | grep "= models\."
```

### URL
```python
path("veterinar/<uuid:vet_id>/", views.veterinar_profile_page, name="veterinar_profile"),
```

### Template: veterinar.html
Dizajn: kao breeder.html ali s medicinskim ikonama
Prikazuje: ime, grad, licenca, broj verificiranih ljubimaca, kontakt
Trust badge: "Registrirani veterinar — Memio.pet"

### NGINX
```nginx
location /veterinar/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

## ZADATAK 4 — REGISTRACIJA: POSEBNA POLJA ZA VET/AZIL

U `views.py` → `registracija()` POST handler, dodaj za tip "vet":
```python
if account_type == 'vet':
    oib = request.POST.get('oib','').strip()
    licenca = request.POST.get('licenca_broj','').strip()
    # trust_score ostaje 30 dok admin ne verificira
    bp = BreederProfile.objects.using(db).create(
        name=ime, email=email, phone=telefon,
        city=grad, account_type='vet', country='HR',
        oib=oib, trust_score=30, is_cro_validated=False,
        notes=f'Licenca: {licenca}'
    )
elif account_type in ('shelter','azil'):
    bp = BreederProfile.objects.using(db).create(
        ...
        is_no_limit_partner=True,  # automatski
        trust_score=50,
        shelter_sponsor=True,
    )
```

U `registracija.html` dodaj conditional JS koji prikazuje extra polja:
```javascript
document.querySelectorAll('.type-btn input').forEach(function(radio) {
    radio.addEventListener('change', function() {
        var extra = document.getElementById('extra-fields');
        if (this.value === 'vet') {
            extra.innerHTML = `
              <div class="field">
                <label>OIB veterinarske ordinacije</label>
                <input type="text" name="oib" placeholder="11-znamenkasti OIB" maxlength="11">
              </div>
              <div class="field">
                <label>Broj licence (HVK)</label>
                <input type="text" name="licenca_broj" placeholder="npr. HVK-2024-1234">
              </div>`;
            extra.style.display = 'block';
        } else if (this.value === 'shelter') {
            extra.innerHTML = `
              <div class="field">
                <label>Naziv azila</label>
                <input type="text" name="azil_naziv" placeholder="npr. Azil Osijek">
              </div>
              <div class="field" style="background:rgba(76,175,125,.08);border-radius:8px;padding:12px;font-size:.85rem;color:#2d6a4f">
                ✓ Azili dobivaju besplatan pristup kroz NO LIMIT udrugu
              </div>`;
            extra.style.display = 'block';
        } else {
            extra.style.display = 'none';
            extra.innerHTML = '';
        }
    });
});
```

Dodaj `<div id="extra-fields" style="display:none"></div>` u HTML formu.

---

## VERIFIKACIJA (obavezna)

```bash
# 1. Sve nove rute rade
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/privatnost/ && echo " /privatnost/"
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/uvjeti/ && echo " /uvjeti/"
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/veterinar/ && echo " /veterinar/ (treba 404 bez UUID)"

# 2. Cookie banner vidljiv (HTML sadrži id="cookie-banner")
curl -s https://memio.pet/ | grep -c "cookie-banner" && echo " cookie-banner u landing"

# 3. Django check
venv/bin/python manage.py check

# 4. Nema zabranjenih linkova
grep -rn "limit-connect.com/hr/register\|no-limit.world" templates/memio_pet/
```

## COMMITI
1. `legal(memio-pet): cookie banner na svim stranicama`
2. `legal(memio-pet): politika privatnosti + opći uvjeti`
3. `feat(memio-pet): veterinar javna stranica`
4. `feat(memio-pet): registracija posebna polja za vet/azil`
