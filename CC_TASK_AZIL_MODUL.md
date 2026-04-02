# CC_TASK: Azil za životinje — Udruge modul proširenje
**Datum:** 02.04.2026.
**Prioritet:** 🟡 SREDNJI — lansiranje 8–12.4. (nakon Dron1+Dron2)
**Procjena:** 6-8 sati (4 sprinta)
**Zakon:** Zakon o zaštiti životinja (NN 102/17), Pravilnik o skloništima (NN 99/2019)
**Vođa projekta:** Sonnet — autonomno, bez traženja odobrenja

---

## ZAKONSKI OKVIR — OBVEZNO RAZUMJETI PRIJE PISANJA KODA

Sklonište mora voditi:
- Evidenciju svake primljene životinje (chip, vrsta, datum ulaska)
- Evidenciju udomljavanja (OIB udomitelja, ugovor, datum)
- Intervencijsku evidenciju (teren, km, GPS koordinate)
- Zdravstvene kartone (cijepljenja, kastracija, liječenja)
- Mjesečni izvještaj prema JLS (lokalna samouprava)
- Registraciju kroz JIC (jic.mps.hr) — Ministarstvo poljoprivrede

---

## ARHITEKTURA — NOVA UDRUGE VRSTA

### Kako se uklapa:
- Postojeći `Clan` model → za skloništa postaje `Volonter` (isti pattern)
- Nova Django app: NE — sve ide u `udruge/` kao novi `udruge_type='azil'`
- Novi modeli u `udruge/models.py` (na dnu, iza golubar sekcije)
- Novi URL prefix: `/udruge/azil/`
- Dashboard: `/udruge/azil/dashboard/` — isti pattern kao /udruge/dvd/

---

## SPRINT 1: Modeli (2h)

### OBAVEZNO: Pročitaj stvarne modele PRIJE pisanja
```bash
grep -n "class Clan\|class Clanarina\|class Golub\|class Golubinjak" udruge/models.py | head -20
python manage.py dbshell -c "\d udruge_clan" 2>/dev/null || true
```

### Novi modeli u `udruge/models.py`:

```python
class Zivotinja(models.Model):
    """Životinja u skloništu — središnji model."""
    
    class Vrsta(models.TextChoices):
        PAS     = 'pas',     'Pas'
        MACKA   = 'macka',   'Mačka'
        KUNIĆ   = 'kunic',   'Kunić'
        PTICA   = 'ptica',   'Ptica'
        OSTALO  = 'ostalo',  'Ostalo'

    class Status(models.TextChoices):
        KARANTENA    = 'karantena',    'Karantena (0-15 dana)'
        SLOBODAN     = 'slobodan',     'Slobodan za udomljenje'
        REZERVIRAN   = 'rezerviran',   'Rezerviran'
        UDOMLJEN     = 'udomljen',     'Udomljen'
        VRAĆEN       = 'vrácen',       'Vraćen vlasniku'
        POGINUO      = 'poginuo',      'Poginuo/Umro'

    company         = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                        related_name='zivotinje')
    evidencijski_br = models.CharField(max_length=20, unique=True, db_index=True,
                                       help_text='Interni evidencijski broj (automatski)')
    mikrocip        = models.CharField(max_length=20, blank=True, db_index=True,
                                       help_text='15-znamenkasti ISO 11784 broj. Ručni unos ili Bluetooth čitač.')
    vrsta           = models.CharField(max_length=10, choices=Vrsta.choices, default='pas')
    naziv_pasmina   = models.CharField(max_length=100, blank=True, help_text='Pasmina ili opis')
    ime             = models.CharField(max_length=100, blank=True, help_text='Ime koje je dao azil')
    spol            = models.CharField(max_length=1, choices=[('M','Muški'),('Ž','Ženski'),('N','Nepoznat')], default='N')
    dob_procjena    = models.CharField(max_length=50, blank=True, help_text='Npr. "oko 2 godine"')
    boja_opis       = models.CharField(max_length=200, blank=True)
    fotografija     = models.ImageField(upload_to='azil/zivotinje/', null=True, blank=True)
    
    # Primitak
    datum_ulaska    = models.DateField(help_text='Datum dolaska u sklonište')
    nacin_primitka  = models.CharField(max_length=50,
                                       choices=[('pronađen','Pronađen na terenu'),('priveden','Priveden'),
                                                ('ostavljen','Ostavljeno od vlasnika'),('premješten','Premješten iz drugog skloništa')],
                                       default='pronađen')
    lokacija_nalaza = models.CharField(max_length=300, blank=True, help_text='Adresa ili opis mjesta nalaza')
    lokacija_gps    = models.CharField(max_length=50, blank=True, help_text='lat,lng — popunjava terenska forma')
    napomena_ulaz   = models.TextField(blank=True)
    
    # Status
    status          = models.CharField(max_length=15, choices=Status.choices, default='karantena')
    datum_karantena_kraj = models.DateField(null=True, blank=True,
                                            help_text='Automatski: datum_ulaska + 15 dana')
    
    # Metapodaci
    objects         = CompanyManager()
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-datum_ulaska']
        verbose_name = 'Životinja'
        verbose_name_plural = 'Životinje'

    def save(self, *args, **kwargs):
        if not self.evidencijski_br:
            # Format: AZ-2026-0001 (auto-inkrement po company)
            last = Zivotinja.objects.filter(company=self.company).order_by('-id').first()
            br = (int(last.evidencijski_br.split('-')[-1]) + 1) if last else 1
            self.evidencijski_br = f"AZ-{timezone.now().year}-{br:04d}"
        if not self.datum_karantena_kraj and self.datum_ulaska:
            from datetime import timedelta
            self.datum_karantena_kraj = self.datum_ulaska + timedelta(days=15)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.evidencijski_br} — {self.ime or self.vrsta} ({self.get_status_display()})"


class KartonZdravlja(models.Model):
    """Zdravstveni zapis za životinju."""
    class VrstaTretmana(models.TextChoices):
        CIJEPLJENJE  = 'cijepljenje',  'Cijepljenje'
        KASTRACIJA   = 'kastracija',   'Kastracija/Sterilizacija'
        ČIPIRANJE    = 'cipiranje',    'Čipiranje'
        ANTIPARAZIT  = 'antiparazit',  'Antiparazitna terapija'
        PREGLED      = 'pregled',      'Veterinarski pregled'
        LIJEK        = 'lijek',        'Lijek/Terapija'
        OSTALO       = 'ostalo',       'Ostalo'

    zivotinja       = models.ForeignKey(Zivotinja, on_delete=models.CASCADE, related_name='zdravlje')
    datum           = models.DateField()
    vrsta_tretmana  = models.CharField(max_length=15, choices=VrstaTretmana.choices)
    opis            = models.TextField(help_text='Lijek, doza, napomena')
    veterinar       = models.CharField(max_length=200, blank=True)
    sljedeći_pregled = models.DateField(null=True, blank=True)
    trošak_eur      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dokument        = models.FileField(upload_to='azil/zdravlje/', null=True, blank=True,
                                       help_text='Skeniran veterinarski nalaz')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum']
        verbose_name = 'Zdravstveni zapis'


class Udomljavanje(models.Model):
    """Evidencija udomljavanja — zakonska obveza (OIB, ugovor)."""
    zivotinja       = models.ForeignKey(Zivotinja, on_delete=models.CASCADE, related_name='udomljavanja')
    datum           = models.DateField()
    
    # Udomitelj (zakonski obvezno)
    ime_prezime     = models.CharField(max_length=200)
    oib             = models.CharField(max_length=11, help_text='OIB udomitelja — zakonski obvezno')
    adresa          = models.CharField(max_length=300)
    telefon         = models.CharField(max_length=30)
    email           = models.EmailField(blank=True)
    
    # Tip
    tip             = models.CharField(max_length=15,
                                       choices=[('trajno','Trajno udomljavanje'),
                                                ('privremeno','Privremeni smještaj'),
                                                ('povrat_vlasnik','Povrat vlasniku')],
                                       default='trajno')
    napomena        = models.TextField(blank=True)
    
    # Ugovor PDF — generira se automatski
    ugovor_potpisan = models.BooleanField(default=False)
    
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum']
        verbose_name = 'Udomljavanje'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ažuriraj status životinje
        if self.tip == 'povrat_vlasnik':
            self.zivotinja.status = 'vraćen'
        else:
            self.zivotinja.status = 'udomljen'
        self.zivotinja.save(update_fields=['status'])


class AzilIntervencija(models.Model):
    """Terenska intervencija — hvatanje, transport, spašavanje."""
    company         = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                        related_name='azil_intervencije')
    datum_vrijeme   = models.DateTimeField()
    adresa          = models.CharField(max_length=300)
    gps             = models.CharField(max_length=50, blank=True)
    opis            = models.TextField()
    djelatnik       = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    km_prijeđeno    = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    broj_životinja  = models.PositiveSmallIntegerField(default=1)
    rezultat        = models.CharField(max_length=20,
                                       choices=[('preuzeto','Preuzeto u sklonište'),
                                                ('nije_uhvaćeno','Nije uhvaćeno'),
                                                ('vraćeno','Vraćeno vlasniku'),
                                                ('veterinar','Upućeno veterinaru')],
                                       default='preuzeto')
    zivotinje       = models.ManyToManyField(Zivotinja, blank=True, related_name='intervencije')
    objects         = CompanyManager()
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum_vrijeme']
        verbose_name = 'Intervencija'


class MjesecniIzvjestajAzil(models.Model):
    """Automatski generiran izvještaj za JLS — zakonska obveza."""
    company         = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    godina          = models.PositiveSmallIntegerField()
    mjesec          = models.PositiveSmallIntegerField()  # 1-12
    
    # Statistike
    primljeno       = models.PositiveSmallIntegerField(default=0)
    udomljeno       = models.PositiveSmallIntegerField(default=0)
    vraćeno_vlasniku = models.PositiveSmallIntegerField(default=0)
    uginulo         = models.PositiveSmallIntegerField(default=0)
    trenutno_stanje = models.PositiveSmallIntegerField(default=0)
    
    # Troškovi
    trošak_hrana_eur    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trošak_vet_eur      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trošak_ostalo_eur   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    pdf_generiran   = models.BooleanField(default=False)
    objects         = CompanyManager()

    class Meta:
        unique_together = [('company', 'godina', 'mjesec')]
        verbose_name = 'Mjesečni izvještaj'
```

---

## SPRINT 2: FenixScan AI integracija — chip i foto (1.5h)

### Što AI može na mobitelu:

**Može:** slikanje životinje za opis (boja, pasmina procjena, vidljive ozljede)
**Može:** čitanje chip broja s NALJEPNICE na nosiocu/dokumentaciji
**Ne može:** čitanje samog implantiranog chipa (134.2 kHz RFID — druga frekvencija od NFC)

### Novi docType u FenixScan: `'azil_zivotinja'`

Dodati u `core/views_scan.py` u `SCAN_HANDLERS`:

```python
'azil_zivotinja': {
    'system_prompt': """Analiziraš fotografiju životinje u skloništu.
    
Izvuci ove podatke (ako su vidljivi):
1. chip_broj: 15-znamenkasti broj mikročipa (samo ako je vidljiv na naljepnici/dokumentu uz životinju, ne možeš pročitati implantirani chip)
2. vrsta: pas/macka/kunic/ptica/ostalo
3. pasmina: procjena pasmine ili opis
4. spol: m/z/nepoznat (procjena ako nije vidljivo)
5. dob_procjena: procjena dobi (štene/mlad/odrasao/star)
6. boja_opis: opis boje i oznaka
7. vidljive_ozljede: opis vidljivih ozljeda ili "nije vidljivo"
8. napomena: sve ostalo relevantno

Odgovori SAMO JSON:
{"chip_broj":"","vrsta":"pas","pasmina":"","spol":"nepoznat","dob_procjena":"","boja_opis":"","vidljive_ozljede":"nije vidljivo","napomena":""}
""",
    'required_fields': ['vrsta'],
    'confidence_fields': ['pasmina', 'chip_broj'],
}
```

### Terenska forma (mobitel) — GPS + foto:

```html
<!-- templates/udruge/azil_terenska_forma.html -->
<!-- Minimalna forma za djelatnika na terenu -->
<!-- FenixScan za foto životinje + AI opis -->
<!-- GPS koordinate automatski -->
<!-- Offline-aware: sprema lokalno ako nema interneta -->
```

---

## SPRINT 3: Views, URLs, Templates (2.5h)

### Struktura URLs (`udruge/urls.py` — dodati):
```python
# Azil
path('azil/', views.azil_dashboard, name='azil_dashboard'),
path('azil/zivotinja/nova/', views.azil_zivotinja_nova, name='azil_zivotinja_nova'),
path('azil/zivotinja/<int:pk>/', views.azil_zivotinja_detalj, name='azil_zivotinja_detalj'),
path('azil/zivotinja/<int:pk>/zdravlje/dodaj/', views.azil_zdravlje_dodaj, name='azil_zdravlje_dodaj'),
path('azil/zivotinja/<int:pk>/udomljavanje/', views.azil_udomljavanje, name='azil_udomljavanje'),
path('azil/intervencija/nova/', views.azil_intervencija_nova, name='azil_intervencija_nova'),
path('azil/terenska/', views.azil_terenska_forma, name='azil_terenska_forma'),
path('azil/izvjestaj/', views.azil_izvjestaj, name='azil_izvjestaj'),
path('api/azil/chip-lookup/', views.azil_chip_lookup, name='azil_chip_lookup'),
```

### Dashboard kartica (templates/udruge/azil_dashboard.html):
- Statistike: ukupno u skloništu / karantena / slobodni za udomljenje
- Lista životinja s filterima (status, vrsta, dob)
- Mapa intervencija (Leaflet, GPS koordinate)
- Alarm: životinje kojima je karantena gotova (status → slobodan)
- Gumb: Terenska forma (mobitel-first)
- Gumb: Generiraj mjesečni izvještaj

### Chip lookup API (`api/azil/chip-lookup/`):
```python
# Besplatna provjera u javnom HR registru (ako postoji API)
# Fallback: https://www.petmaxx.com ili https://www.europetnet.com
# Vraća: {vlasnik, adresa, vrsta, pasmina} ili {} ako nije registriran
```

---

## SPRINT 4: Izvještaj PDF + WhatsApp alarm (1h)

### Mjesečni izvještaj za JLS:
- WeasyPrint PDF template (isti pattern kao Z-izvještaj)
- Automatski se generira 1. u mjesecu (Celery beat)
- Sadrži: statistike, troškove, popis intervencija
- WhatsApp Ivanu (ili admin skloništa) za potvrdu

### Celery beat:
```python
'azil-karantena-check': {
    'task': 'udruge.tasks.azil_karantena_check',
    'schedule': crontab(hour=8, minute=0),  # svako jutro 08:00
},
'azil-mjesecni-izvjestaj': {
    'task': 'udruge.tasks.azil_generiraj_izvjestaj',
    'schedule': crontab(day_of_month=1, hour=6, minute=0),
},
```

### Karantena alarm:
```python
# Svako jutro 08:00: provjeri životinje kojima je istekla karantena (15 dana)
# Status: karantena → slobodan_za_udomljenje
# WhatsApp adminu: "5 životinja je završilo karantenu, slobodne za udomljenje"
```

---

## KOMPLETNA PROVJERA MODELA PRIJE PISANJA

```bash
# OBAVEZNO PRIJE PISANJA BILO KOJEG KODA:
grep -n "class\|company\|CompanyManager\|objects" udruge/models.py | grep -E "^udruge" | tail -30

# Provjeri zadnji model (za nastavak):
tail -50 udruge/models.py

# Provjeri views.py pattern:
grep -n "def.*dvd\|def.*kud\|def.*ribolo" udruge/views.py | head -10
```

---

## CHIP SCANNER — HARDWARE INTEGRACIJA (BONUS, nije blokira launch)

### Za skloništa koja imaju Bluetooth RFID čitač:
Čitač emulira Bluetooth tipkovnicu — automatski upiše chip broj u fokusirani input.

```html
<!-- chip_input polje u formi: -->
<input type="text" id="mikrocip" name="mikrocip" 
       placeholder="Klikni ovdje, zatim prisloni čitač uz životinju"
       pattern="[0-9]{15}"
       inputmode="numeric"
       autocomplete="off">
<small class="text-muted">
  15 znamenki. Bluetoooth čitač automatski upisuje. 
  Bez čitača: ručni unos ili ostavi prazno.
</small>
```

Nema posebnog koda — Bluetooth RFID čitač radi kao external keyboard. Plug & play.

---

## COMMIT FORMAT
```
feat(udruge): azil modul — Zivotinja, KartonZdravlja, Udomljavanje, Intervencija, FenixScan AI foto
```

## MIGRACIJA
```bash
venv/bin/python manage.py makemigrations udruge --name azil_modeli
venv/bin/python manage.py migrate
# Provjeri: 0 grešaka, 0 konflikata
```

## TESTOVI (minimalni, 5 zelenih):
```
test_01_zivotinja_auto_evidencijski_broj
test_02_karantena_datum_auto_15_dana
test_03_udomljavanje_mijenja_status
test_04_fenixscan_azil_zivotinja_doctype
test_05_chip_lookup_api_returns_json
```
