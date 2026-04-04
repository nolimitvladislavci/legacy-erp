# CC_TASK: Kućni ljubimci — MASTER PLAN (Azil + Kinologija + Burza)
**Datum:** 02.04.2026. | **Vođa:** Sonnet
**Cilj:** 10/10, #1 u EU za kućne ljubimce u ERP/udruge kontekstu
**Zakon:** ZoZŽ (NN 102/17), Pravilnik o skloništima (NN 99/2019), HKS Pravilnik o uzgoju/upisu, FCI standardi
**Procjena:** 3-4 tjedna (po fazama, CC Code ide fazom 1 prvo)

---

## MAPA SEGMENATA — tko su korisnici

```
LIMIT Connect Kućni ljubimci ekosustav
│
├── 🏠 AZIL / SKLONIŠTE (40-60 subjekata HR, +EU)
│   ├── JLS skloništa (gradska, komunalna)
│   ├── Udruge (no-kill, volonterska)
│   └── Privatne koncesije
│
├── 🐕 UZGAJIVAČ (HKS mreža: 135 udruga, tisuće uzgajivača)
│   ├── Pasminski klubovi
│   ├── Individualni uzgajivači (uzgajivačnica)
│   └── Sportski/radni psi (agility, traganje, lovni)
│
└── 🛍️ BURZA KUĆNIH LJUBIMACA (online marketplace)
    ├── Verificirana legla (s rodovnicom, chip potvrdom)
    ├── Udomljavanje (azilske životinje)
    └── Parenje (uzgajivači nude rasplodnjake)
```

---

## ŠTO JE PROMAKLO ISPOD RADARA — kritični nalazi

### 1. EUTANAZIJA — zakonska distinkcija (najosjetljiviji podatak u sustavu)

**HR zakon (NN 102/17) — konačna pozicija:**
- **ZABRANJENO:** usmrćivanje zdravih napuštenih životinja u skloništu
- **DOZVOLJENO:** eutanazija isključivo za neizlječivo bolesne/teško ozlijeđene životinje,
  isključivo veterinarskom odlukom i provodi je ovlašteni veterinar
- **Softverska implikacija:** model `VeterinarskaEutanazija` mora biti:
  - Zaključan iza veterinarskog potpisa (ne može unijeti djelatnik skloništa)
  - Obvezan razlog: dijagnoza + veterinar OIB + klinika
  - Automatski upis u JIC evidenciju Ministarstva
  - **Ne smije se zvati "eutanazija" za zdrave životinje** — to je zakonski prekršaj

### 2. KINOLOŠKA DOKUMENTACIJA — papirna noćna mora (business opportunity)

Što uzgajivač danas mora ručno:
- Obrazac HKS prijave legla (papir → HKS Zagreb poštom!)
- Potvrda o parenju (original, ne kopija)
- Uzgojna dozvola (za svaki par posebno)
- Veterinarska dokumentacija čipiranja (za svako štene)
- HD/ED RTG nalaz (displazija kukova/lakata — obvezno za mnoge pasmine)
- Izvješće o mikročipiranju (veterinar potpisuje za svako štene posebno)
- Putovnica kućnog ljubimca (za svako štene)
- Rodovnica (tek kad HKS odobri — tjedni čekanje)

**Nitko u HR/EU nema digitalni workflow za ovo.**
HKS app (app.hks.hr) — samo online prijava za izložbe.

### 3. IZLOŽBENI TITULI — tracking šampionata

Sustav titula koji uzgajivač mora ručno pratiti:
- **CAC-HR** (Certifikat za prvaka HR) — 4 CAC od min. 3 suca + 2 na CACIB
- **CACIB** (Certifikat za međ. prvaka) — 4 CACIB iz 3 države + 4 suca
- **Prvak HR u ljepoti** → **Prvak HR u radu** → **Apsolutni prvak**
- Bodovi se upisuju u rodovnicu i izložbenu knjižicu ručno

**Što se može automatizirati:** unos rezultata izložbe → automatski tracker
"još 2 CAC-a do titule, sljedeća prikladna izložba: [datum]"

### 4. GENETSKI ZDRAVSTVENI TESTOVI — obveza za mnoge pasmine

- **HD/ED** (displazija kukova/lakata) — RTG, ocjenjuje veterinar ovlašteni od HKS
- **PRA** (progresivna atrofija mrežnice) — DNA test
- **Cerebralna ataksija** (neke pasmine) — DNA CLEAR test
- **Kriptorhizam/monorhizam** — veterinarski pregled
- Rezultati se moraju priložiti prijavi legla

**Nitko ne nudi digitalni karton genetskih testova psa s history-jem.**

### 5. BURZA — tržišna rupa

Njuškalo.hr i oglasnik.hr:
- Bez verifikacije chip broja
- Bez provjere je li uzgajivač registriran u HKS
- Bez potvrde rodovnice
- Bez health testova
- Kupac ne zna ništa o porijeklu psa

**LIMIT Connect verificirana burza:**
- Leglo objavljuje samo registrirani uzgajivač (HKS broj)
- Svako štene ima chip broj verificiran
- Rodovnica broj vidljiv
- Health testovi roditelja priloženi
- Ugovor o prodaji/udomljavanju → PDF autogenerirani

---

## ARHITEKTURA — 3 modula u udruge/

```
udruge/
├── models.py (postojeći — dodajemo na dnu)
│   ├── === AZIL segment ===
│   ├── Zivotinja
│   ├── KartonZdravlja
│   ├── VeterinarskaEutanazija   ← novi, osjetljiv
│   ├── Udomljavanje
│   ├── AzilIntervencija
│   └── MjesecniIzvjestajAzil
│   ├── === KINOLOGIJA segment ===
│   ├── Pas                      ← centralni model uzgajivača
│   ├── Uzgajivacnica
│   ├── Leglo
│   ├── GenetskiTest             ← HD, PRA, DNA
│   ├── KinoloskaTitula          ← CAC, CACIB tracker
│   └── IzlozbeniNastup
└── views_azil.py (novi file, ne diramo postojeće)
└── views_kinologija.py (novi file)
```

---

## FAZA 1: Azil modul (Sprint 1-4, ~8h)

### OBAVEZNA PROVJERA MODELA PRIJE PISANJA:
```bash
tail -100 udruge/models.py
grep -n "class.*Golub\|class.*Par\|class.*Zdravstveni" udruge/models.py | tail -10
```

### Modeli (Sprint 1):

```python
# ══════════════════════════════════════════════════════════════════
# AZIL SEGMENT — udruge/models.py (dodati na dnu)
# ══════════════════════════════════════════════════════════════════

class Zivotinja(models.Model):
    class Vrsta(models.TextChoices):
        PAS    = 'pas',    'Pas'
        MACKA  = 'macka',  'Mačka'
        KUNIC  = 'kunic',  'Kunić'
        PTICA  = 'ptica',  'Ptica'
        OSTALO = 'ostalo', 'Ostalo'

    class Status(models.TextChoices):
        KARANTENA  = 'karantena',  'Karantena (0-15 dana)'
        SLOBODAN   = 'slobodan',   'Slobodan za udomljenje'
        REZERVIRAN = 'rezerviran', 'Rezerviran'
        UDOMLJEN   = 'udomljen',   'Udomljen'
        VRAĆEN     = 'vrácen',     'Vraćen vlasniku'
        UGINUO     = 'uginuo',     'Uginuo (prirodno)'
        EUTANAZIJA = 'eutanazija', 'Eutanazija (veterinarska odluka)'

    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    evidencijski_br  = models.CharField(max_length=20, unique=True, db_index=True)
    mikrocip         = models.CharField(max_length=20, blank=True, db_index=True,
                                        help_text='15-znamenkasti ISO 11784 broj')
    vrsta            = models.CharField(max_length=10, choices=Vrsta.choices, default='pas')
    naziv_pasmina    = models.CharField(max_length=100, blank=True)
    ime              = models.CharField(max_length=100, blank=True)
    spol             = models.CharField(max_length=1,
                                        choices=[('M','Muški'),('Ž','Ženski'),('N','Nepoznat')],
                                        default='N')
    dob_procjena     = models.CharField(max_length=50, blank=True)
    boja_opis        = models.CharField(max_length=200, blank=True)
    fotografija      = models.ImageField(upload_to='azil/zivotinje/', null=True, blank=True)
    datum_ulaska     = models.DateField()
    nacin_primitka   = models.CharField(max_length=20,
                                        choices=[('pronađen','Pronađen'),('priveden','Priveden'),
                                                 ('ostavljen','Ostavljeno od vlasnika'),
                                                 ('premješten','Premješten')],
                                        default='pronađen')
    lokacija_nalaza  = models.CharField(max_length=300, blank=True)
    lokacija_gps     = models.CharField(max_length=50, blank=True, help_text='lat,lng')
    napomena_ulaz    = models.TextField(blank=True)
    status           = models.CharField(max_length=15, choices=Status.choices, default='karantena')
    datum_karantena_kraj = models.DateField(null=True, blank=True)
    javno_oglaseno   = models.BooleanField(default=False,
                                           help_text='Prikazuje se na burzi za udomljenje')
    objects          = CompanyManager()
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.evidencijski_br:
            from django.utils import timezone
            last = Zivotinja.objects.filter(company=self.company).order_by('-id').first()
            br = (int(last.evidencijski_br.split('-')[-1]) + 1) if last else 1
            self.evidencijski_br = f"AZ-{timezone.now().year}-{br:04d}"
        if not self.datum_karantena_kraj and self.datum_ulaska:
            from datetime import timedelta
            self.datum_karantena_kraj = self.datum_ulaska + timedelta(days=15)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-datum_ulaska']
        verbose_name = 'Životinja'


class KartonZdravlja(models.Model):
    class VrstaTretmana(models.TextChoices):
        CIJEPLJENJE  = 'cijepljenje',  'Cijepljenje'
        KASTRACIJA   = 'kastracija',   'Kastracija/Sterilizacija'
        CIPIRANJE    = 'cipiranje',    'Čipiranje'
        ANTIPARAZIT  = 'antiparazit',  'Antiparazitna terapija'
        PREGLED      = 'pregled',      'Veterinarski pregled'
        LIJEK        = 'lijek',        'Lijek/Terapija'
        OZLJEDA      = 'ozljeda',      'Liječenje ozljede'
        OSTALO       = 'ostalo',       'Ostalo'

    zivotinja        = models.ForeignKey(Zivotinja, on_delete=models.CASCADE,
                                         related_name='zdravlje')
    datum            = models.DateField()
    vrsta_tretmana   = models.CharField(max_length=15, choices=VrstaTretmana.choices)
    opis             = models.TextField()
    veterinar        = models.CharField(max_length=200, blank=True)
    klinika          = models.CharField(max_length=200, blank=True)
    sljedeci_pregled = models.DateField(null=True, blank=True)
    trosak_eur       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dokument         = models.FileField(upload_to='azil/zdravlje/', null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum']


class VeterinarskaEutanazija(models.Model):
    """
    POSEBNO OSJETLJIV MODEL — samo za neizlječivo bolesne životinje.
    Zakon HR (NN 102/17): usmrćivanje zdravih životinja je ZABRANJENO.
    Ovaj model smije kreirati SAMO veterinar (role check u view-u).
    """
    zivotinja        = models.OneToOneField(Zivotinja, on_delete=models.CASCADE,
                                            related_name='eutanazija')
    datum            = models.DateField()
    veterinar_ime    = models.CharField(max_length=200, help_text='Ime i prezime veterinara')
    veterinar_oib    = models.CharField(max_length=11, help_text='OIB veterinara')
    klinika          = models.CharField(max_length=200)
    dijagnoza        = models.TextField(
        help_text='Obavezna klinička dijagnoza neizlječive bolesti ili teške ozljede')
    metoda           = models.CharField(max_length=200,
                                        default='IV barbiturni koktel (standard WSAVA)')
    potvrda_pdf      = models.FileField(upload_to='azil/eutanazija/', null=True, blank=True,
                                        help_text='Skenirana veterinarska potvrda')
    napomena         = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Automatski ažuriraj status životinje
        self.zivotinja.status = 'eutanazija'
        self.zivotinja.save(update_fields=['status'])

    class Meta:
        verbose_name = 'Veterinarska eutanazija'
        verbose_name_plural = 'Veterinarska eutanazija'


class Udomljavanje(models.Model):
    zivotinja        = models.ForeignKey(Zivotinja, on_delete=models.CASCADE,
                                         related_name='udomljavanja')
    datum            = models.DateField()
    ime_prezime      = models.CharField(max_length=200)
    oib              = models.CharField(max_length=11, help_text='OIB — zakonski obvezno')
    adresa           = models.CharField(max_length=300)
    telefon          = models.CharField(max_length=30)
    email            = models.EmailField(blank=True)
    tip              = models.CharField(max_length=15,
                                        choices=[('trajno','Trajno'),
                                                 ('privremeno','Privremeni smještaj'),
                                                 ('povrat','Povrat vlasniku')],
                                        default='trajno')
    napomena         = models.TextField(blank=True)
    ugovor_potpisan  = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.zivotinja.status = 'vraćen' if self.tip == 'povrat' else 'udomljen'
        self.zivotinja.save(update_fields=['status'])


class AzilIntervencija(models.Model):
    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    datum_vrijeme    = models.DateTimeField()
    adresa           = models.CharField(max_length=300)
    gps              = models.CharField(max_length=50, blank=True)
    opis             = models.TextField()
    djelatnik        = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                         null=True, blank=True)
    km_prijedeno     = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    broj_zivotinja   = models.PositiveSmallIntegerField(default=1)
    rezultat         = models.CharField(max_length=20,
                                        choices=[('preuzeto','Preuzeto'),
                                                 ('nije_uhvaceno','Nije uhvaćeno'),
                                                 ('vráceno','Vraćeno vlasniku'),
                                                 ('veterinar','Upućeno veterinaru')],
                                        default='preuzeto')
    zivotinje        = models.ManyToManyField(Zivotinja, blank=True,
                                              related_name='intervencije')
    objects          = CompanyManager()
    created_at       = models.DateTimeField(auto_now_add=True)


class MjesecniIzvjestajAzil(models.Model):
    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    godina           = models.PositiveSmallIntegerField()
    mjesec           = models.PositiveSmallIntegerField()
    primljeno        = models.PositiveSmallIntegerField(default=0)
    udomljeno        = models.PositiveSmallIntegerField(default=0)
    vráceno_vlasniku = models.PositiveSmallIntegerField(default=0)
    uginulo          = models.PositiveSmallIntegerField(default=0)
    eutanazirano     = models.PositiveSmallIntegerField(default=0)
    trenutno_stanje  = models.PositiveSmallIntegerField(default=0)
    trosak_hrana_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trosak_vet_eur   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trosak_ostalo_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pdf_generiran    = models.BooleanField(default=False)
    objects          = CompanyManager()

    class Meta:
        unique_together = [('company', 'godina', 'mjesec')]
```

### FenixScan (Sprint 2):
Dodati `'azil_zivotinja'` u `core/views_scan.py` SCAN_HANDLERS:
- AI opisuje: vrsta, pasmina procjena, spol, boja, vidljive ozljede
- Čita chip broj s **naljepnice/dokumenta** (ne implantiranog chip-a)
- fieldMap: `vrsta`, `naziv_pasmina`, `spol`, `boja_opis`, `mikrocip`

### Web Bluetooth (Sprint 2.5):
Dodati u terenska_forma.html:
```javascript
async function connectChipReader() {
  try {
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ services: ['battery_service'] }], // RFID čitač
      optionalServices: ['generic_access', 'generic_attribute']
    });
    const server = await device.gatt.connect();
    // Čitač šalje chip broj kao keyboard events — popunjava #mikrocip input
    document.getElementById('chipReaderStatus').textContent = '✅ Čitač spojen: ' + device.name;
    document.getElementById('btnChipScan').disabled = false;
  } catch(err) {
    // Fallback: ručni unos
    document.getElementById('chipReaderStatus').textContent = '⚠️ Ručni unos chip broja';
  }
}
// Napomena: RFID čitači (Agrident, Datamars) emuliraju BT tipkovnicu
// → chip broj automatski ide u fokusirani input bez posebnog BT protokola
```

### Views, URLs, Templates (Sprint 3):
```
/udruge/azil/                         → dashboard
/udruge/azil/zivotinja/nova/          → forma s FenixScan + GPS
/udruge/azil/zivotinja/<pk>/          → detalj + kartoni + history
/udruge/azil/terenska/                → mobitel-first, offline-aware
/udruge/azil/intervencija/nova/       → GPS automatch, foto
/udruge/azil/izvjestaj/               → PDF za JLS, auto-generiran
/api/azil/chip-lookup/                → lookup u javnim registrima
```

### Celery + PDF (Sprint 4):
- Karantena alarm svako jutro 08:00 (15 dana → slobodan)
- Mjesečni izvještaj 1. u mjesecu (WeasyPrint PDF za JLS)
- WhatsApp adminu pri svakom udomljavanju

---

## FAZA 2: Kinologija / Uzgajivač modul (~12h)

```python
# ══════════════════════════════════════════════════════════════════
# KINOLOGIJA SEGMENT — udruge/models.py (dodati ispod azil bloka)
# ══════════════════════════════════════════════════════════════════

class Uzgajivacnica(models.Model):
    """Registrirana uzgajivačnica s HKS/FCI zaštićenim imenom."""
    company          = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    ime_uzgajivacnice = models.CharField(max_length=200,
                                         help_text='Zaštićeno ime pri HKS/FCI (npr. "Von Brtan")')
    hks_broj         = models.CharField(max_length=50, help_text='HKS evidencijski broj')
    fci_broj         = models.CharField(max_length=50, blank=True,
                                        help_text='FCI međunarodni broj')
    pasmina          = models.CharField(max_length=200, help_text='Pasmina/e — može ih biti više')
    adresa           = models.CharField(max_length=300)
    vlasnik          = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    aktivan          = models.BooleanField(default=True)
    objects          = CompanyManager()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Uzgajivačnica'


class Pas(models.Model):
    """Pas uzgajivača — evidencija za uzgoj i natjecanja."""
    class Spol(models.TextChoices):
        MUZ  = 'M', 'Mužjak'
        ZEN  = 'Ž', 'Ženka'

    class Status(models.TextChoices):
        AKTIVAN   = 'aktivan',   'Aktivan u uzgoju'
        PENZIONER = 'penzioner', 'U mirovini (previše legala/dob)'
        PRODAN    = 'prodan',    'Prodan'
        UGINUO    = 'uginuo',    'Uginuo'

    company           = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    ime_puno          = models.CharField(max_length=300,
                                         help_text='Puno ime s uzgojnim imenom (npr. "Von Brtan Igor")')
    ime_zvanje        = models.CharField(max_length=100, blank=True,
                                         help_text='Kućno/nadimak')
    pasmina           = models.CharField(max_length=200)
    spol              = models.CharField(max_length=1, choices=Spol.choices)
    datum_rodenja     = models.DateField(null=True, blank=True)
    mikrocip          = models.CharField(max_length=20, db_index=True,
                                         help_text='15-znamenkasti ISO 11784')
    rodovnica_broj    = models.CharField(max_length=100, blank=True,
                                         help_text='HKS broj rodovnice')
    status            = models.CharField(max_length=15, choices=Status.choices, default='aktivan')
    fotografija       = models.ImageField(upload_to='kinologija/psi/', null=True, blank=True)
    uzgajivacnica     = models.ForeignKey(Uzgajivacnica, on_delete=models.SET_NULL, null=True,
                                          blank=True, related_name='psi')
    
    # Roditelji (rodovnik)
    otac_ime          = models.CharField(max_length=300, blank=True)
    otac_rodovnica    = models.CharField(max_length=100, blank=True)
    majka_ime         = models.CharField(max_length=300, blank=True)
    majka_rodovnica   = models.CharField(max_length=100, blank=True)
    
    # Uzgojni status
    uzgojna_dozvola   = models.BooleanField(default=False,
                                            help_text='Ima važeću uzgojnu dozvolu HKS')
    uzgojni_pregled_datum = models.DateField(null=True, blank=True)
    
    # Publiciranje na burzi
    dostupan_parenje  = models.BooleanField(default=False,
                                            help_text='Mužjak dostupan za parenje')
    cijena_parenje_eur = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    opis_burza        = models.TextField(blank=True, help_text='Opis za burzu parenja')
    
    objects           = CompanyManager()
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pas'
        verbose_name_plural = 'Psi'


class GenetskiTest(models.Model):
    """HD, PRA, DNA testovi — uvjet za uzgojnu dozvolu HKS."""
    class VrstaTest(models.TextChoices):
        HD    = 'HD',    'Displazija kukova (HD)'
        ED    = 'ED',    'Displazija lakata (ED)'
        PRA   = 'PRA',   'Progresivna atrofija mrežnice (PRA)'
        DNA   = 'DNA',   'DNA test (specifična bolest)'
        OCD   = 'OCD',   'Osteochondrosis dissecans'
        OSTALO = 'X',    'Ostalo'

    class Rezultat(models.TextChoices):
        CLEAR   = 'CLEAR',   'Clear (slobodan)'
        CARRIER = 'CARRIER', 'Носиlac (carrier)'
        AFFECTED = 'AFFECTED','Zahvaćen'
        A1      = 'A1',     'HD-A (slobodan)'
        A2      = 'A2',     'HD-A2 (slobodan granično)'
        B1      = 'B1',     'HD-B1 (blagi)'
        C       = 'C',      'HD-C (umjereni) — ne uzgaja se'
        D       = 'D',      'HD-D (teški) — ne uzgaja se'
        E       = 'E',      'HD-E (najteži) — ne uzgaja se'

    pas               = models.ForeignKey(Pas, on_delete=models.CASCADE,
                                          related_name='genetski_testovi')
    vrsta_testa       = models.CharField(max_length=10, choices=VrstaTest.choices)
    datum_testa       = models.DateField()
    rezultat          = models.CharField(max_length=10, choices=Rezultat.choices)
    laboratorij       = models.CharField(max_length=200, blank=True)
    veterinar         = models.CharField(max_length=200, blank=True)
    certifikat_broj   = models.CharField(max_length=100, blank=True)
    dokument          = models.FileField(upload_to='kinologija/testovi/', null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    @property
    def uzgojno_prihvatljiv(self):
        """Može li se pas s ovim rezultatom koristiti u uzgoju?"""
        nedopusteni = ['C', 'D', 'E', 'AFFECTED']
        return self.rezultat not in nedopusteni

    class Meta:
        ordering = ['-datum_testa']
        verbose_name = 'Genetski test'


class Leglo(models.Model):
    """Leglo štenadi — s HKS prijavom."""
    class Status(models.TextChoices):
        PRIPREMA   = 'priprema',   'U pripremi (parenje planirano)'
        OCEKIVANJE = 'ocekivanje', 'Ženka bređa'
        RODENO     = 'rodeno',     'Leglo rođeno'
        PRIJAVLJENO = 'prijavljeno', 'Prijavljeno HKS-u'
        RODOVNICE  = 'rodovnice',  'Rodovnice izdane'
        PRODANO    = 'prodano',    'Sva štenad prodana/udomljena'

    uzgajivacnica     = models.ForeignKey(Uzgajivacnica, on_delete=models.CASCADE,
                                          related_name='legla')
    otac              = models.ForeignKey(Pas, on_delete=models.SET_NULL, null=True,
                                          related_name='legla_otac')
    majka             = models.ForeignKey(Pas, on_delete=models.SET_NULL, null=True,
                                          related_name='legla_majka')
    datum_parenja     = models.DateField(null=True, blank=True)
    datum_rodenja     = models.DateField(null=True, blank=True)
    broj_stenadi      = models.PositiveSmallIntegerField(default=0)
    broj_muzjaka      = models.PositiveSmallIntegerField(default=0)
    broj_zenki        = models.PositiveSmallIntegerField(default=0)
    status            = models.CharField(max_length=15, choices=Status.choices, default='priprema')
    
    # HKS dokumentacija
    potvrda_parenja_br = models.CharField(max_length=100, blank=True,
                                           help_text='Broj potvrde o parenju')
    prijava_legla_datum = models.DateField(null=True, blank=True,
                                            help_text='Datum prijave HKS-u (rok: 6-12 tjedana)')
    hks_broj_legla    = models.CharField(max_length=100, blank=True,
                                          help_text='HKS dodijeljeni broj legla')
    pocetno_slovo     = models.CharField(max_length=1, blank=True,
                                          help_text='Sva štenad iz legla počinju ovim slovom')
    
    # Publiciranje
    javno_oglaseno    = models.BooleanField(default=False,
                                            help_text='Leglo vidljivo na burzi štenadi')
    cijena_stene_eur  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    opis_burza        = models.TextField(blank=True)
    
    objects           = models.Manager()  # Leglo je cross-company (burza)
    created_at        = models.DateTimeField(auto_now_add=True)

    @property
    def datum_najkasnije_prijave(self):
        """HKS rok: najkasnije 12 tjedana od štenjenja."""
        if self.datum_rodenja:
            from datetime import timedelta
            return self.datum_rodenja + timedelta(weeks=12)
        return None

    @property
    def alarm_prijava_hks(self):
        """True ako je blizu ili prošao rok za prijavu HKS."""
        if self.datum_najkasnije_prijave and self.status == 'rodeno':
            from datetime import date, timedelta
            return date.today() >= (self.datum_najkasnije_prijave - timedelta(weeks=2))
        return False

    class Meta:
        ordering = ['-datum_rodenja']
        verbose_name = 'Leglo'


class IzlozbeniNastup(models.Model):
    """Evidencija izložbenih nastupa — tracker za šampionatske titule."""
    class Ocjena(models.TextChoices):
        ODLICAN    = 'V',   'Odličan (Vorzüglich/Excellent)'
        VRLO_DOBAR = 'SG',  'Vrlo dobar (Sehr Gut/Very Good)'
        DOBAR      = 'G',   'Dobar (Gut/Good)'
        DOVOLJAN   = 'Ausreichend', 'Dovoljan'
        # Posebna odlikovanja
        CAC_HR     = 'CAC-HR',  'CAC-HR (kandidatura za HR prvaka)'
        CACIB      = 'CACIB',   'CACIB (kandidatura za međ. prvaka)'
        RCAC       = 'Res.CAC', 'Rezerva CAC'
        RCACIB     = 'Res.CACIB','Rezerva CACIB'
        BOS        = 'BOS',     'Best of Opposite Sex'
        BOB        = 'BOB',     'Best of Breed'
        BOG        = 'BOG',     'Best of Group'
        BIS        = 'BIS',     'Best in Show'

    pas               = models.ForeignKey(Pas, on_delete=models.CASCADE,
                                          related_name='nastupe')
    datum             = models.DateField()
    naziv_izlozbe     = models.CharField(max_length=300)
    tip_izlozbe       = models.CharField(max_length=20,
                                         choices=[('medunar','Međunarodna'),
                                                  ('nacional','Nacionalna'),
                                                  ('specijalna','Specijalna/Klupska')],
                                         default='nacional')
    grad              = models.CharField(max_length=100)
    drzava            = models.CharField(max_length=3, default='HR')
    sudac             = models.CharField(max_length=200)
    klasa             = models.CharField(max_length=100,
                                         help_text='Npr. otvorena, radna, prvak...')
    ocjena            = models.CharField(max_length=15, choices=Ocjena.choices)
    plasman           = models.PositiveSmallIntegerField(null=True, blank=True,
                                                          help_text='1=1. mjesto u klasi...')
    komentar_suca     = models.TextField(blank=True)
    certifikat        = models.FileField(upload_to='kinologija/izlozbe/', null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum']
        verbose_name = 'Izložbeni nastup'
```

### Views i URLs (Faza 2):
```
/udruge/kinologija/                           → dashboard uzgajivačnice
/udruge/kinologija/pas/<pk>/                  → detalj psa (rodovnik, testovi, titule, legla)
/udruge/kinologija/leglo/novo/                → novi workflow s alarm za HKS rok
/udruge/kinologija/leglo/<pk>/nastup/dodaj/   → unos izložbenih rezultata
/udruge/kinologija/titule/<pk>/               → tracker do narednog šampionata
/api/kinologija/chip-lookup/<chip>/           → provjera u JIC + petmaxx.com
```

### FenixScan za kinologiju (Faza 2):
- docType `'rodovnica'` — AI čita: ime psa, datum rođenja, rod. broj, pasmina, roditelji
- docType `'genetski_test'` — AI čita: tip testa, rezultat, datum, laboratorij
- docType `'putovnica_ljubimac'` — AI čita: chip broj, vlasnik, cjepiva

---

## FAZA 3: Online Burza kućnih ljubimaca (~6h)

### Dva toka na burzi:

**A) Štenad s rodovnicom** (uzgajivači)
- Vidljivo: `Leglo.javno_oglaseno = True`
- Prikazuje: pasmina, roditelji + titule, health testovi, cijena, dostupan termin
- Verifikacija: chip + HKS broj uzgajivačnice

**B) Udomljavanje** (azili)
- Vidljivo: `Zivotinja.javno_oglaseno = True`
- Prikazuje: fotografija, vrsta, dob, opis
- Bez cijene — udomljavanje je besplatno (ili simbolična naknada)
- Direktni kontakt skloništa

**C) Parenje** (uzgajivači)
- `Pas.dostupan_parenje = True AND Pas.spol = 'M'`
- Prikazuje: titule, health testovi, uzgojno ime, cijena

### URL:
```
/ljubimci/burza/          → javna stranica (bez prijave)
/ljubimci/burza/stenada/  → filtriraj po pasmini, lokaciji, cijeni
/ljubimci/burza/udomljavanje/ → azilske životinje
/ljubimci/burza/parenje/  → rasplodnjaci
/ljubimci/oglas/<pk>/     → detalj oglasa s kontakt formom
```

### Diferencijaija od njuškalo.hr:
- **Verified badge** = chip broj potvrđen + HKS broj uzgajivačnice
- Health test ikone (HD ✅, PRA ✅, ED ✅) vidljive na kartici
- Titule roditelja (Otac: CH HR, Majka: CAC ×3)
- Direktni link na HKS registar uzgajivačnice
- Ugovor o prodaji/udomljavanju — auto-generiran PDF pri rezervaciji

---

## ŠTO SE PRESLIKAVA IZ GOLUBAR MODULA

Pattern je isti — provjeri i koristi:
```bash
grep -n "class Golub\|class Pedigre\|class GenetskiPecat\|class Utrka" udruge/models.py
```

| Golubar | Psi/Azil | Napomena |
|---------|----------|----------|
| `Golub` | `Pas` | Isti pattern evidencije |
| `prsten_broj` | `mikrocip` | Različit input — FenixScan za oboje |
| `Rodovnik PDF` | `Rodovnica PDF` | WeasyPrint, isti template pattern |
| `Utrka` | `IzlozbeniNastup` | Rezultati + statistika |
| `ZdravstveniZapisGolub` | `KartonZdravlja` | Identični pattern |

FenixScan za golubar prstenove (`'ring'` docType) preslikati za `'rodovnica'` i `'putovnica_ljubimac'`.

---

## COMMIT FORMAT
```
feat(udruge): kucni_ljubimci_master — Azil+Kinologija+Burza
- Azil: Zivotinja, KartonZdravlja, VeterinarskaEutanazija, Udomljavanje, Intervencija
- Kinologija: Uzgajivacnica, Pas, GenetskiTest, Leglo, IzlozbeniNastup
- Burza: /ljubimci/burza/ javna stranica, 3 tipa oglasa
- FenixScan: 3 nova docType (azil_zivotinja, rodovnica, putovnica_ljubimac)
- Web Bluetooth chip reader integration
- Celery: karantena alarm, HKS rok alarm, mjesečni izvještaj PDF
```

## MIGRACIJE
```bash
venv/bin/python manage.py makemigrations udruge --name kucni_ljubimci_master
venv/bin/python manage.py migrate
# Target: 0 grešaka, 0 konflikata s postojećim modelima
```

## TESTOVI (minimalni — 10 zelenih):
```
test_01_zivotinja_auto_evidencijski_broj
test_02_karantena_datum_auto_15_dana
test_03_udomljavanje_mijenja_status
test_04_eutanazija_zahtijeva_dijagnozu
test_05_eutanazija_mijenja_status_na_eutanazija
test_06_pas_rodovnik_roditelji
test_07_genetski_test_uzgojno_prihvatljiv_hd_c_false
test_08_leglo_rok_prijave_hks_12_tjedana
test_09_leglo_alarm_prijava_aktivira_se_2_tjedna_prije
test_10_burza_prikazuje_samo_javno_oglasene
```

## REDOSLIJED FAZA:
1. **Faza 1 — Azil** (8.4. - 10.4.) — blokira azil klijente, launch-ready
2. **Faza 2 — Kinologija** (11.4. - 15.4.) — uzgajivači, pilot: Ivan prijatelj
3. **Faza 3 — Burza** (post-launch, 1.5.) — marketing differentiator

---

## NAPOMENA O EUTANAZIJI (za CC Code — pročitati pažljivo)

U views_azil.py za kreiranje VeterinarskaEutanazija:
```python
@login_required
def azil_eutanazija_nova(request, pk):
    # Permission check: samo veterinari ili company_admin smiju kreirati
    if not (request.user.has_perm('udruge.add_veterinarskaeutanazija') or
            request.user.userprofile.role == 'company_admin'):
        messages.error(request, 'Samo ovlašteni veterinar može evidentirati eutanaziju.')
        return redirect('udruge:azil_zivotinja_detalj', pk=pk)
    # ...
```

Na formi obavezno prikazati zakonski okvir:
```html
<div class="alert alert-warning">
  <strong>Zakonska napomena (ZoZŽ NN 102/17):</strong>
  Usmrćivanje zdravih napuštenih životinja zabranjeno je u HR.
  Eutanazija je dopuštena isključivo za neizlječivo bolesne ili
  teško ozlijeđene životinje, isključivo veterinarskom odlukom.
</div>
```
