# CC TASK: no-limit.world — Finalni sprint (statut, ciljevi, partneri, ambasadori)

**Prioritet:** CRITICAL  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Kontekst:** Karla dolazi DANAS s dvoje djece na fizičko testiranje portala.
              Marija Čačić (HR ambasador) dobiva link čim ovo bude OK.
              No-limit udruga: u postupku registracije, predsjednik Ivan Brtan.

---

## STANJE

`no-limit.world` je live (nginx, SSL). Portal je azil prototip (3 URL-a).
`CC_TASK_NOLIMIT_EU_UMBRELLA.md` je kompleksniji long-term plan.
**Ovaj task je hitni MVP** — minimum za danas i za Mariju Čačić.

---

## ŠTO TREBA (danas, ne sutra)

### 1. LANDING PAGE — no-limit.world (redesign)

Pročitaj trenutni:
```bash
cat /var/www/fina-connect/no_limit/templates/no_limit/vodic_online.html
ls /var/www/fina-connect/no_limit/templates/no_limit/
```

**Novi landing** (`no_limit/templates/no_limit/landing.html`) mora imati:

**Hero:**
"No Limit — Europska udruga za digitalno djetinjstvo i inovacije"
Podnaslov: "Razvijamo otvorene digitalne platforme za djecu, životinje i institucije diljem EU. Osnivač i predsjednik: Ivan Brtan."

**4 projekta (kartice):**
- 🎓 **PLAY.EU** — Multikulturalna dječja obrazovna platforma (22 bajke, 8 regija, 3 jezika)  
  Link: memio.world
- 🐾 **memio.pet** — Digitalni identitet ljubimaca i zaštita životinja  
  Link: memio.pet
- ✅ **eValidator** — Javni EU validacijski servis (OIB, IBAN, VAT)  
  Link: evalidator.eu
- 💼 **LIMIT Connect** — ERP/POS sustav za hrvatska i EU poduzeća  
  Link: limit-connect.com

**Ciljevi udruge (nova sekcija):**
```
1. Razvoj digitalnih obrazovnih sadržaja za djecu u EU
2. Zaštita životinja kroz digitalne identifikacijske sustave
3. Javni digitalni servisi — eValidator infrastruktura povjerenja
4. Podrška diaspora zajednicama (HR u DE, AT, SI)
5. EU projekt prijave (Creative Europe, Interreg, Erasmus+)
6. Ambasadorska mreža u svim EU državama
7. Digitalna baština i kulturno pamćenje
8. Podrška NGO-ima i azilima (No Limit azil program)
```

**Partneri (nova sekcija):**
```
🇩🇪 Viskovic Bau, Nufringen (DE) — Poslovni partner i pokrovitelj
🇭🇷 Konjik d.o.o., Osijek (HR) — Tehnološki partner
[Tvoje mjesto ovdje — ambasador iz tvoje zemlje]
```

**Ambasadori (nova sekcija):**
```
🇭🇷 Marija Čačić — HR Ambasador, pedagog, magistra pedagogije
[Prijavite se — forme za ambasadore]
```

**CTA gumbi:**
- "Postani ambasador" → /no-limit/ambasadori/prijava/
- "Kontakt" → /no-limit/kontakt/

**Dizajn:** Tamna tema (no-limit.world ima #0a0a0a), zlatni/zeleni akcenti.
Inspiracija: evalidator.eu landing koji je upravo napravljen.

---

### 2. STATUT (HTML stranica + PDF download)

Kreiraj `no_limit/templates/no_limit/statut.html` (online čitanje)
i `no_limit/templates/no_limit/pdf/statut_no_limit.html` (WeasyPrint PDF)

**Sadržaj statuta** (Ivan će popuniti [brackete]):

```
STATUT UDRUGE "NO LIMIT"

Članak 1 — Naziv, sjedište i OIB
Naziv: NO LIMIT
Sjedište: [ČEPIN ili OSIJEK — Ivan popunjava]
OIB: [popunjava se nakon registracije]
Skraćeni naziv: NL | Web: no-limit.world

Članak 2 — Misija
No Limit je neprofitna udruga koja razvija otvorene digitalne 
platforme za djecu, životinje i institucije u Europskoj uniji.
Filozofija: "Bez papira. Bez granica. Bez ograničenja."

Članak 3 — Ciljevi [isti kao gore, 8 stavki]

Članak 4 — Djelatnosti
- Razvoj i održavanje digitalnih platformi
- Organizacija edukacija, radionica i EU događanja
- EU projekt menadžment i provedba
- Licenciranje sadržaja institucijama
- Ambasadorska mreža u EU
- Podrška azilima digitalnim alatima

Članak 5 — Financiranje
- Članarine
- Donacije i sponzorstava (Viskovic Bau, Konjik d.o.o.)
- EU grantovi (Creative Europe, Interreg, Erasmus+)
- Licencni prihodi od poslovnih partnera

Članak 6 — Tijela udruge
- Skupština
- Predsjednik: Ivan Brtan
- Tajnik: [ime]
- Nadzorni odbor

Članak 7 — Ambasadorska mreža EU
Udruga osniva mrežu nacionalnih ambasadora. Svaki ambasador 
potpisuje Ugovor o ambasadorskoj suradnji (dokument A1).

Članak 8 — Partnerstva
Udruga sklapa licencne i partnerske ugovore...
Aktivni partneri: Konjik d.o.o. (HR), Viskovic Bau (DE)

Članak 9 — Zaštita djece
Svi sadržaji za djecu usklađeni su s GDPR-Kids politikom (dokument G1).

Članak 10 — Prijelazne odredbe
Statut stupa na snagu danom osnivačke skupštine.
```

---

### 3. URL-OVI (dodati u no_limit/urls.py)

```python
path('', views.landing, name='home'),           # Nova landing
path('o-nama/', views.o_nama, name='o_nama'),
path('statut/', views.statut, name='statut'),
path('statut/pdf/', views.statut_pdf, name='statut_pdf'),
path('ambasadori/', views.ambasadori, name='ambasadori'),
path('ambasadori/prijava/', views.ambasador_prijava, name='ambasador_prijava'),
path('partneri/', views.partneri, name='partneri'),
path('kontakt/', views.kontakt, name='kontakt'),
path('projekti/', views.projekti, name='projekti'),
# Zadrži staro:
path('azili/prijava/', views.prijava_azila, name='prijava_azila'),
```

---

### 4. VIEWS (no_limit/views.py)

Dodaj:
```python
def landing(request): 
    return render(request, 'no_limit/landing.html', {})

def o_nama(request):
    return render(request, 'no_limit/o_nama.html', {})

def statut(request):
    return render(request, 'no_limit/statut.html', {})

def statut_pdf(request):
    # WeasyPrint — isti pattern kao preuzmi_vodic()
    ...

def ambasadori(request):
    return render(request, 'no_limit/ambasadori.html', {})

def ambasador_prijava(request):
    # Forma: ime, email, zemlja, organizacija, motivacija
    # POST → spremi u AzilPrijava ili novi model
    # WA notifikacija Ivanu
    ...

def partneri(request):
    return render(request, 'no_limit/partneri.html', {})

def kontakt(request):
    return render(request, 'no_limit/kontakt.html', {})

def projekti(request):
    return render(request, 'no_limit/projekti.html', {})
```

---

### 5. SIMPLE AMBASADOR MODEL (ako ne postoji)

Provjeri ima li model:
```bash
cat /var/www/fina-connect/no_limit/models.py
```

Ako nema `AmbassadorApplication`, dodaj minimalni:
```python
class AmbassadorApplication(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    country = models.CharField(max_length=100)
    organization = models.CharField(max_length=200, blank=True)
    motivation = models.TextField()
    status = models.CharField(max_length=20, default='pending',
        choices=[('pending','Na čekanju'),('approved','Odobreno'),('declined','Odbijeno')])
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Prijava ambasadora"
```

Makemigrations + migrate.

---

### 6. NGINX UPDATE

Provjeri routira li nginx `/` na Django:
```bash
cat /etc/nginx/sites-enabled/no-limit-world
```

Mora imati:
```nginx
location = / { proxy_pass http://127.0.0.1:8000/no-limit/; }
location / { proxy_pass http://127.0.0.1:8000; }
```

---

### 7. FINALNI KORACI

```bash
python manage.py makemigrations no_limit
python manage.py migrate
python manage.py collectstatic --noinput
systemctl reload gunicorn-fina
nginx -t && systemctl reload nginx
```

Testiraj:
```bash
curl -sk https://no-limit.world/ | grep "<title>"
curl -sk https://no-limit.world/statut/ | head -5
```

---

## IZVJEŠTAJ

`/var/www/fina-connect/CC_REPORT_NOLIMIT_FINAL.md`:
- Kreirani fajlovi
- Live URL-ovi koji rade
- Što je ostalo (AmbassadorApplication full model iz CC_TASK_NOLIMIT_EU_UMBRELLA.md)

---

## DEFINICIJA DONE
- [ ] no-limit.world/ prikazuje novi landing s projektima, ciljevima, partnerima
- [ ] /statut/ radi (HTML + PDF download)
- [ ] /ambasadori/prijava/ forma radi + WA notifikacija Ivanu
- [ ] WA poruka: "Nova ambasadorska prijava: {ime}, {zemlja}"
- [ ] CC_REPORT_NOLIMIT_FINAL.md napisan

