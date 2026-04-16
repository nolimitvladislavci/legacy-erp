# CC TASK: no-limit.world — Transformacija u EU Umbrella portal

**Prioritet:** HIGH  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Odobrio:** Sonnet  
**Vlasnik:** Ivan Brtan / No-limit udruga (u postupku registracije, predsjednik Ivan)

---

## KONTEKST I VIZIJA

No-limit udruga postaje EU umbrella za cijeli ekosustav:
- **play.eu / memio.world** — dječja obrazovna platforma
- **memio.pet** — digitalni identitet ljubimaca  
- **evalidator.eu** — javni validacijski servis (CroValidator)
- **LIMIT Connect** — ERP/POS (komercijalni arm, Konjik d.o.o.)

Trenutni portal (`no-limit.world`) je azil prototip — 3 URL-a, 1 model.  
Treba ga pretvoriti u **profesionalni NGO/udruga portal** koji može:
1. Primati ambasadore iz EU zemalja  
2. Prikazivati statute i pravne dokumente  
3. Biti kredibilan za Creative Europe i Interreg prijave  
4. Upravljati partnerskim mrežama

---

## ŠTO TREBA NAPRAVITI

### KORAK 1 — Audit i čišćenje

Pročitaj sve:
```bash
cat /var/www/fina-connect/no_limit/models.py
cat /var/www/fina-connect/no_limit/views.py
cat /var/www/fina-connect/no_limit/urls.py
ls /var/www/fina-connect/no_limit/templates/no_limit/
cat /etc/nginx/sites-enabled/no-limit-world
```

`AzilPrijava` model **ne brišeš** — arhiviraš (ostaje u bazi, makloneš s portala).

---

### KORAK 2 — Novi modeli (`no_limit/models.py`)

Dodaj uz `AzilPrijava`:

```python
class AmbassadorApplication(models.Model):
    """Prijava za ambasadorsku ulogu u nekoj EU zemlji."""
    
    COUNTRY_CHOICES = [
        ('HR', 'Hrvatska'), ('DE', 'Njemačka'), ('AT', 'Austrija'),
        ('SI', 'Slovenija'), ('IT', 'Italija'), ('HU', 'Mađarska'),
        ('CZ', 'Češka'), ('SK', 'Slovačka'), ('PL', 'Poljska'),
        ('FR', 'Francuska'), ('NL', 'Nizozemska'), ('BE', 'Belgija'),
        ('SE', 'Švedska'), ('OTHER', 'Ostalo'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Na čekanju'),
        ('review', 'U pregledu'),
        ('approved', 'Odobreno'),
        ('declined', 'Odbijeno'),
        ('active', 'Aktivan ambasador'),
    ]
    
    ROLE_CHOICES = [
        ('national_coordinator', 'Nacionalni koordinator'),
        ('regional_ambassador', 'Regionalni ambasador'),
        ('institutional_partner', 'Institucionalni partner'),
        ('sponsor', 'Sponzor / Pokrovitelj'),
    ]
    
    # Osobni podaci
    full_name = models.CharField(max_length=200, verbose_name="Puno ime")
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=5, choices=COUNTRY_CHOICES)
    
    # Organizacija
    organization_name = models.CharField(max_length=200, blank=True, 
        verbose_name="Naziv organizacije (ako je primjenjivo)")
    organization_type = models.CharField(max_length=100, blank=True,
        verbose_name="Vrsta organizacije (škola, knjižnica, udruga...)")
    
    # Uloga i motivacija
    desired_role = models.CharField(max_length=30, choices=ROLE_CHOICES,
        default='national_coordinator')
    motivation = models.TextField(
        verbose_name="Zašto želiš biti ambasador? (max 500 znakova)")
    experience = models.TextField(blank=True,
        verbose_name="Relevantno iskustvo (pedagoško, digitalno, EU projekti)")
    languages = models.CharField(max_length=200,
        verbose_name="Jezici koje govorite")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.CharField(max_length=100, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Vremenski žig
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Prijava ambasadora"
        verbose_name_plural = "Prijave ambasadora"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.get_country_display()}) — {self.get_status_display()}"


class CountryChapter(models.Model):
    """Nacionalni ogranak No-limit udruge."""
    
    country = models.CharField(max_length=5, unique=True)
    country_name = models.CharField(max_length=100)
    coordinator_name = models.CharField(max_length=200, blank=True)
    coordinator_email = models.EmailField(blank=True)
    
    # Aktivnost
    is_active = models.BooleanField(default=False)
    launch_date = models.DateField(null=True, blank=True)
    
    # Statistike
    ambassador_count = models.IntegerField(default=0)
    user_count = models.IntegerField(default=0)
    
    # Sadržaj
    local_description = models.TextField(blank=True,
        verbose_name="Opis projekta na lokalnom jeziku")
    grant_applications = models.TextField(blank=True,
        verbose_name="EU grant prijave za ovu zemlju")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Nacionalni ogranak"
        verbose_name_plural = "Nacionalni ogranci"
    
    def __str__(self):
        return f"No-limit {self.country_name}"


class PartnershipLead(models.Model):
    """CRM za potencijalne partnere i sponzore."""
    
    STATUS_CHOICES = [
        ('new', 'Novi'),
        ('contacted', 'Kontaktiran'),
        ('negotiating', 'U pregovorima'),
        ('signed', 'Potpisano'),
        ('declined', 'Odbijeno'),
        ('inactive', 'Neaktivan'),
    ]
    
    TYPE_CHOICES = [
        ('sponsor', 'Sponzor'),
        ('partner', 'Partner'),
        ('eu_applicant', 'EU ko-aplikant'),
        ('letter_of_support', 'Letter of Support'),
    ]
    
    name = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=5, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    
    partnership_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    notes = models.TextField(blank=True)
    potential_value = models.DecimalField(max_digits=10, decimal_places=2, 
        null=True, blank=True, verbose_name="Potencijalna vrijednost (€)")
    
    source = models.CharField(max_length=100, blank=True,
        verbose_name="Kako smo saznali (WA, email, preporuka...)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Partnership lead"
        verbose_name_plural = "Partnership leads"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_partnership_type_display()}) — {self.get_status_display()}"
```

Napravi migraciju: `python manage.py makemigrations no_limit && python manage.py migrate`

---

### KORAK 3 — Novi URL-ovi (`no_limit/urls.py`)

```python
urlpatterns = [
    # Landing
    path("", views.landing, name="home"),
    
    # O nama
    path("o-nama/", views.about, name="about"),
    path("statut/", views.statut, name="statut"),
    path("ciljevi/", views.ciljevi, name="ciljevi"),
    
    # Ambasadori
    path("ambasadori/", views.ambassador_overview, name="ambassador_overview"),
    path("ambasadori/prijava/", views.ambassador_apply, name="ambassador_apply"),
    path("ambasadori/hvala/", views.ambassador_thank_you, name="ambassador_thank_you"),
    
    # Projekti
    path("projekti/", views.projects, name="projects"),
    path("projekti/play-eu/", views.project_play_eu, name="project_play_eu"),
    path("projekti/memio-pet/", views.project_memio_pet, name="project_memio_pet"),
    path("projekti/evalidator/", views.project_evalidator, name="project_evalidator"),
    
    # Partneri
    path("partneri/", views.partners, name="partners"),
    path("kontakt/", views.contact, name="contact"),
    
    # Dokumenti (PDF download)
    path("dokumenti/statut.pdf", views.download_statut, name="download_statut"),
    path("dokumenti/ambasadorski-ugovor.pdf", views.download_ambassador_agreement, 
         name="download_ambassador_agreement"),
    
    # Staro (zadrži kompatibilnost)
    path("azili/prijava/", views.prijava_azila, name="prijava_azila"),
]
```

---

### KORAK 4 — Views (`no_limit/views.py`)

Implementiraj sve gore navedene views. Ključni su:

**`ambassador_apply`** — forma koja kreira `AmbassadorApplication` i:
1. Šalje WA Ivanu: "Nova prijava ambasadora: {ime}, {zemlja}"
2. Šalje email potvrdu podnositelju
3. Redirect na `ambassador_thank_you`

**`download_statut`** i **`download_ambassador_agreement`** — WeasyPrint PDF generiranje iz template-a (koristiš isti pattern kao `preuzmi_vodic`).

Ostali views mogu biti jednostavni `render()` pozivi s kontekstom.

---

### KORAK 5 — Sadržaj statuta (template za PDF)

Kreiraj `no_limit/templates/no_limit/pdf/statut.html`.

Statut mora sadržavati:

```
STATUT UDRUGE "NO LIMIT"

Članak 1 — Naziv i sjedište
Naziv: NO LIMIT
Sjedište: [Ivan unosi — Čepin ili Osijek]
Skraćeni naziv: NL

Članak 2 — Ciljevi udruge
1. Razvoj digitalnih obrazovnih sadržaja za djecu i mlade u EU
2. Zaštita i promicanje kulturne baštine putem digitalnih medija
3. Podrška djeci s posebnim potrebama kroz digitalne alate
4. Razvoj javnih digitalnih servisa (validacija, identifikacija)
5. Podrška azilima i zaštita životinja digitalnim platformama
6. Umrežavanje i podrška EU ambasadorskakim mrežama
7. Prijava i provedba EU projekata (Creative Europe, Interreg, Erasmus+)
8. Suradnja s institucijama, schulama, knjižnicama u EU

Članak 3 — Djelatnosti
- Razvoj i održavanje digitalnih platformi
- Organizacija edukacija, radionica i događanja
- Izdavaštvo (digitalno i tiskano)
- EU projekt menadžment
- Licenciranje sadržaja institucijama

Članak 4 — Financiranje
Udruga se financira iz:
- Članarina
- Donacija i sponzorstava
- EU grantova i fondova
- Prihoda od licencnih ugovora
- Naknada za usluge

Članak 5 — Tijela udruge
- Skupština (svi članovi)
- Predsjednik (Ivan Brtan)
- Tajnik
- Nadzorni odbor

Članak 6 — Ambasadorska mreža
Udruga osniva mrežu nacionalnih ambasadora u EU zemljama...
[detalji iz AmbassadorApplication modela]

Članak 7 — Suradnja s poslovnim subjektima
Udruga može sklapati licencne ugovore s poslovnim subjektima...
[Konjik d.o.o., Viskovic Bau...]

Članak 8 — Statusne promjene i prestanak
...

Članak 9 — Prijelazne odredbe
...
```

---

### KORAK 6 — Ambasadorski ugovor (template za PDF)

Kreiraj `no_limit/templates/no_limit/pdf/ambasadorski_ugovor.html`.

Ugovor sadrži:
```
UGOVOR O AMBASADORSKOJ SURADNJI

Sklopljen između:
- NO LIMIT udruge (Udruga), zastupane po predsjedniku Ivanu Brtanu
- [Ime ambasadora] (Ambasador)

1. PREDMET UGOVORA
Ambasador postaje nacionalni koordinator No-limit projekata 
u [zemlja] za period od 1 (jedne) godine uz automatski produžetak.

2. PRAVA AMBASADORA
- Besplatan pristup svim premium sadržajima platforme
- 20% prihoda od pretplata korisnika iz svoje zemlje
- Podrška u pisanju EU grant prijava za svoju zemlju
- Korištenje naziva "PLAY.EU National Coordinator — [zemlja]"
- Pedagoška i tehnička podrška Udruge

3. OBVEZE AMBASADORA
- Promovirati platformu u svojoj zemlji
- Validirati pedagoški sadržaj za svoju kulturnu sredinu
- Prevesti minimum 3 sadržaja godišnje
- Sudjelovati na min. 4 online susreta godišnje
- Potpisati Letter of Intent za EU projekt prijave

4. INTELEKTUALNO VLASNIŠTVO
Sav sadržaj na platformi ostaje vlasništvo Udruge.
Lokalni sadržaj koji kreira Ambasador postaje zajedničko vlasništvo.

5. POVJERLJIVOST
[standardna NDA klauzula]

6. TRAJANJE I RASKID
[standardne klauzule]
```

---

### KORAK 7 — Landing page dizajn

Kreiraj `no_limit/templates/no_limit/landing.html` koji prikazuje:

**Hero sekcija:**
"No Limit — Europska mreža za digitalno obrazovanje i zaštitu"
Podnaslov: "Neprofitna udruga koja razvija otvorene digitalne platforme za djecu, životinje i institucije diljem EU."

**Projekti kartica (3 kolone):**
- PLAY.EU — Multikulturalna obrazovna platforma
- memio.pet — Digitalni identitet ljubimaca  
- eValidator — Javni EU validacijski servis

**Ambasadori sekcija:**
Karta Europe s aktivnim i traženim lokacijama + CTA "Postani ambasador"

**Partneri:**
Viskovic Bau (DE), [mjesta za buduće partnere]

**Footer:**
Statut PDF, Kontakt, LinkedIn, GDPR

Koristi Tailwind iz existing projekta (ne instaliraj ništa novo).

---

### KORAK 8 — Admin

U `no_limit/admin.py` registriraj:
- `AmbassadorApplication` — s akcijama: `mark_approved`, `mark_declined`, `send_welcome_email`
- `CountryChapter`
- `PartnershipLead` — s akcijom `mark_declined` (za Palagruška tip situacija)

---

### KORAK 9 — WA notifikacije

U `ambassador_apply` view, kad stigme nova prijava:
```python
wa_msg = f"🌍 Nova ambasadorska prijava!\n{full_name} iz {country}\nUloga: {desired_role}\nEmail: {email}"
send_whatsapp(IVAN_WHATSAPP_NUMBER, wa_msg)
```

---

### KORAK 10 — Migracije i testovi

```bash
python manage.py makemigrations no_limit
python manage.py migrate
python manage.py test no_limit
```

Napiši `no_limit/tests.py`:
- Test da se može kreirati AmbassadorApplication
- Test da forma radi (valid i invalid input)
- Test da PDF download vraća 200
- Test da WA notifikacija se poziva pri novoj prijavi

---

## IZVJEŠTAJ

Napiši `/var/www/fina-connect/CC_REPORT_NOLIMIT.md`:
- Kreirani modeli + migracije
- Kreirani URL-ovi
- Kreirani PDF dokumenti
- Test rezultati
- Što je ostalo (Stripe, email, pravi sadržaj statuta koji Ivan mora popuniti)

---

## ŠTO NE RADIŠ
- ❌ Ne mijenjaš LIMIT Connect ERP
- ❌ Ne instaliraš nove pakete bez odobrenja
- ❌ Ne brišeš AzilPrijava model
- ❌ Ne deployaš bez Sonetovog odobrenja (nema `sudo systemctl restart`)
- ❌ Ne pišeš stvarni pravni tekst statuta — samo placeholder koji Ivan popunjava

## DEFINICIJA DONE
- [ ] 3 nova modela + migracije
- [ ] 10+ URL-ova
- [ ] PDF download radi (statut + ambasadorski ugovor template)
- [ ] Forma za ambasadore radi + WA notifikacija
- [ ] Admin s mark_declined akcijom
- [ ] 4+ testovi prolaze
- [ ] CC_REPORT_NOLIMIT.md
