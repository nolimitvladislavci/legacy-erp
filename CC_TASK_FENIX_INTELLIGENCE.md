# CC Task — Fenix Intelligence + OPG Livestock/CropPlan

## Pročitaj prvo — OBAVEZNO
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
grep -n "^class\|business_type\|OPG" /var/www/fina-connect/companies/models.py | head -10
grep -n "^class\|def run_task\|max_steps" /var/www/fina-connect/core/gemini_agent.py | head -10
grep -n "^class\|shared_task\|run_gemini" /var/www/fina-connect/core/gemini_tasks.py | head -5
cat /var/www/fina-connect/core/notify.py | head -40
grep -n "^class\|is_organic\|seller_company\|FuturesListing" /var/www/fina-connect/marketplace/models.py | head -20
grep -n "beat_schedule\|crontab\|02:30\|03:00" /var/www/fina-connect/core/settings.py | head -10
grep -n "^class" /var/www/fina-connect/ai_assistant/tasks.py | head -5
grep -n "^class" /var/www/fina-connect/burza/models.py | head -5
```

## Što gradimo
Tri nova Django app-a:

1. **`livestock/`** — evidencija farme goveda za OPG Kruljac (i sve buduće OPG-ove)
2. **`intelligence/`** — autonomni noćni agent koji prati web i kreira prilike
3. Proširenje **`burza/`** — agro kategorije + AI auto-listing

---

## APP 1 — livestock/

### Korak 1.1 — Kreiraj Django app
```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp livestock
```

### Korak 1.2 — livestock/models.py

```python
"""
livestock/models.py
Evidencija goveda za OPG. Prati: grlo, zdravlje, mlijeko,
plan ishrane, parcele, usjeve i put prema bio certifikaciji.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Livestock(models.Model):
    """Jedno grlo — krava, junica, tele, bik."""

    VRSTA_CHOICES = [
        ('krava', 'Krava (muzara)'),
        ('junica', 'Junica'),
        ('tele', 'Tele'),
        ('bik', 'Bik'),
        ('vo', 'Vo (tov)'),
    ]
    STATUS_CHOICES = [
        ('aktivno', 'Aktivno'),
        ('gravidno', 'Gravidno'),
        ('zasušeno', 'Zasušeno'),
        ('tov', 'U tovu'),
        ('prodano', 'Prodano'),
        ('uginulo', 'Uginulo'),
        ('izlučeno', 'Izlučeno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='livestock', verbose_name='OPG'
    )
    # Identifikacija (EU označavanje — obavezno za preživače)
    ear_tag = models.CharField(max_length=20, verbose_name='Broj ušne markice',
                                help_text='HR format: HR + OIB + redni br, npr. HR12345678901001',
                                db_index=True)
    name = models.CharField(max_length=50, blank=True, verbose_name='Ime (opcionalno)')
    vrsta = models.CharField(max_length=15, choices=VRSTA_CHOICES, default='krava')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivno')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Datum rođenja')
    breed = models.CharField(max_length=50, blank=True, verbose_name='Pasmina',
                              help_text='npr. Simentalac, Holstein, Siva')
    weight_kg = models.DecimalField(max_digits=7, decimal_places=1,
                                     null=True, blank=True, verbose_name='Težina (kg)')
    # Mliječnost (samo za krave)
    avg_daily_milk_l = models.DecimalField(max_digits=6, decimal_places=2,
                                            null=True, blank=True,
                                            verbose_name='Prosj. dnevna mliječnost (L)')
    # Reprodukcija
    last_calving = models.DateField(null=True, blank=True, verbose_name='Zadnje teljenje')
    expected_calving = models.DateField(null=True, blank=True, verbose_name='Očekivano teljenje')

    # Bio status
    is_organic = models.BooleanField(default=False, verbose_name='Ekološki uzgoj')
    organic_since = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'livestock_animal'
        ordering = ['ear_tag']
        unique_together = [('company', 'ear_tag')]
        verbose_name = 'Grlo'
        verbose_name_plural = 'Grla'

    def __str__(self):
        return f'{self.ear_tag} — {self.get_vrsta_display()} ({self.get_status_display()})'

    @property
    def age_months(self):
        if not self.date_of_birth:
            return None
        delta = timezone.now().date() - self.date_of_birth
        return delta.days // 30

    @property
    def calving_soon(self):
        if not self.expected_calving:
            return False
        return (self.expected_calving - timezone.now().date()).days <= 21


class HealthRecord(models.Model):
    """Veterinarski zapis — cjepiva, bolesti, tretmani."""

    TIP_CHOICES = [
        ('cijepljenje', 'Cijepljenje'),
        ('pregled', 'Veterinarski pregled'),
        ('tretman', 'Tretman / Lijek'),
        ('bolest', 'Bolest'),
        ('operacija', 'Operacija'),
        ('karantena', 'Karantena'),
    ]

    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE,
                                related_name='health_records')
    datum = models.DateField(verbose_name='Datum')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    opis = models.CharField(max_length=255, verbose_name='Opis')
    veterinar = models.CharField(max_length=100, blank=True, verbose_name='Veterinar')
    lijek = models.CharField(max_length=100, blank=True, verbose_name='Lijek / Preparat')
    kolicina = models.CharField(max_length=50, blank=True, verbose_name='Količina doze')
    # EU zakonski zahtjev: evidencija karencije
    karencija_do = models.DateField(null=True, blank=True,
                                     verbose_name='Karencija do (zabrana mlijeka/mesa)')
    trošak_eur = models.DecimalField(max_digits=8, decimal_places=2,
                                      null=True, blank=True, verbose_name='Trošak (EUR)')
    photo = models.ImageField(upload_to='livestock/health/%Y/', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_health_record'
        ordering = ['-datum']
        verbose_name = 'Zdravstveni zapis'
        verbose_name_plural = 'Zdravstveni zapisi'

    def __str__(self):
        return f'{self.animal.ear_tag} — {self.get_tip_display()} ({self.datum})'

    @property
    def u_karenciji(self):
        if not self.karencija_do:
            return False
        return self.karencija_do >= timezone.now().date()


class MilkRecord(models.Model):
    """Dnevna evidencija mliječnosti — kontrolni muzni list."""

    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE,
                                related_name='milk_records')
    datum = models.DateField()
    jutarnja_l = models.DecimalField(max_digits=6, decimal_places=2,
                                      default=0, verbose_name='Jutarnja muža (L)')
    večernja_l = models.DecimalField(max_digits=6, decimal_places=2,
                                      default=0, verbose_name='Večernja muža (L)')
    ukupno_l = models.DecimalField(max_digits=6, decimal_places=2,
                                    default=0, editable=False)
    masnoća_posto = models.DecimalField(max_digits=4, decimal_places=2,
                                         null=True, blank=True, verbose_name='Masnoća (%)')
    proteini_posto = models.DecimalField(max_digits=4, decimal_places=2,
                                          null=True, blank=True, verbose_name='Proteini (%)')
    notes = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_milk_record'
        unique_together = [('animal', 'datum')]
        ordering = ['-datum']
        verbose_name = 'Muzni zapis'
        verbose_name_plural = 'Muzni zapisi'

    def save(self, *args, **kwargs):
        self.ukupno_l = self.jutarnja_l + self.večernja_l
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.animal.ear_tag} — {self.datum}: {self.ukupno_l}L'


class Field(models.Model):
    """Parcela — katastarska čestica ili radna jedinica."""

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='fields')
    naziv = models.CharField(max_length=100, verbose_name='Naziv parcele')
    katastarska_cestica = models.CharField(max_length=50, blank=True,
                                            verbose_name='Katastarska čestica')
    povrsina_ha = models.DecimalField(max_digits=8, decimal_places=4,
                                       verbose_name='Površina (ha)')
    tip_tla = models.CharField(max_length=50, blank=True,
                                verbose_name='Tip tla',
                                help_text='npr. ilovača, pjeskovita ilovača, černozem')
    ph_tla = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                  verbose_name='pH tla')
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_organic = models.BooleanField(default=False, verbose_name='Ekološka parcela')
    # ARKOD broj (Agencija za plaćanja u poljoprivredi)
    arkod_id = models.CharField(max_length=50, blank=True, verbose_name='ARKOD ID',
                                 help_text='Potreban za APPRRR poticaje')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_field'
        ordering = ['naziv']
        verbose_name = 'Parcela'
        verbose_name_plural = 'Parcele'

    def __str__(self):
        return f'{self.naziv} ({self.povrsina_ha} ha) — {self.company.name}'


class CropPlan(models.Model):
    """Plan sjetve i žetve po parceli i godini."""

    STATUS_CHOICES = [
        ('plan', 'U planu'),
        ('posijano', 'Posijano'),
        ('raste', 'Raste'),
        ('berba', 'U berbi'),
        ('zavrseno', 'Završeno'),
        ('propalo', 'Propalo'),
    ]
    KULTURA_CHOICES = [
        ('kukuruz', 'Kukuruz (zrno)'),
        ('kukuruz_silaža', 'Kukuruz (silaža)'),
        ('djetelina', 'Djetelina'),
        ('livada', 'Livada / Trava'),
        ('pšenica', 'Pšenica'),
        ('ječam', 'Ječam'),
        ('soja', 'Soja'),
        ('šećerna_repa', 'Šećerna repa'),
        ('suncokret', 'Suncokret'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='crop_plans')
    parcela = models.ForeignKey(Field, on_delete=models.CASCADE,
                                 related_name='crop_plans', null=True, blank=True)
    godina = models.PositiveSmallIntegerField(verbose_name='Godina')
    kultura = models.CharField(max_length=30, choices=KULTURA_CHOICES)
    sorta = models.CharField(max_length=100, blank=True, verbose_name='Sorta / Hibrid')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='plan')

    # Rokovi
    datum_sjetve = models.DateField(null=True, blank=True, verbose_name='Planirani datum sjetve')
    datum_berbe = models.DateField(null=True, blank=True, verbose_name='Planirani datum berbe')
    stvarni_datum_berbe = models.DateField(null=True, blank=True)

    # Prinosi
    planrani_prinos_t_ha = models.DecimalField(max_digits=6, decimal_places=2,
                                                null=True, blank=True,
                                                verbose_name='Planirani prinos (t/ha)')
    stvarni_prinos_t = models.DecimalField(max_digits=8, decimal_places=2,
                                            null=True, blank=True,
                                            verbose_name='Stvarni prinos (t)')

    # Namjena
    za_vlastite_potrebe = models.BooleanField(default=True,
                                               verbose_name='Za vlastite potrebe (stoka)')
    za_prodaju = models.BooleanField(default=False, verbose_name='Za prodaju')
    procijenjeni_višak_t = models.DecimalField(max_digits=8, decimal_places=2,
                                                null=True, blank=True,
                                                verbose_name='Procijenjeni višak za prodaju (t)')

    # Bio
    is_organic = models.BooleanField(default=False)
    gnojidba_opis = models.CharField(max_length=255, blank=True,
                                      verbose_name='Gnojidba (sredstvo, količina)')
    zastita_opis = models.CharField(max_length=255, blank=True,
                                     verbose_name='Zaštita bilja (sredstvo)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'livestock_crop_plan'
        ordering = ['-godina', 'kultura']
        verbose_name = 'Plan sjetve'
        verbose_name_plural = 'Planovi sjetve'

    def __str__(self):
        return f'{self.get_kultura_display()} {self.godina} — {self.company.name}'

    @property
    def auto_listing_ready(self):
        """True ako ima procijenjeni višak i berba je u tijeku ili završena."""
        return (
            self.za_prodaju and
            self.procijenjeni_višak_t and
            self.procijenjeni_višak_t > 0 and
            self.status in ('berba', 'zavrseno')
        )
```

### Korak 1.3 — Dodaj u INSTALLED_APPS, migracije
```bash
# Dodaj 'livestock' u core/settings.py INSTALLED_APPS

cd /var/www/fina-connect
venv/bin/python manage.py makemigrations livestock
venv/bin/python manage.py migrate livestock
venv/bin/python manage.py check
```

---

## APP 2 — intelligence/

### Korak 2.1 — Kreiraj app
```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp intelligence
```

### Korak 2.2 — intelligence/models.py

```python
"""
intelligence/models.py
Fenix Intelligence — autonomni istraživački agent.

Logika:
  IntelligenceSource  — što pratiti (eKohezija, APPRRR, TISUP, Agroklub...)
  IntelligenceJob     — konfiguracija za jednu firmu (što je relevantno)
  IntelligenceResult  — što je pronađeno u jednom ciklusu
  FundOpportunity     — natječaj/poticaj (EU fond ili HR)
  FundApplication     — prijava firme na natječaj

Celery beat pokreće intelligence_nightly_patrol() svako jutro u 03:30.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class IntelligenceSource(models.Model):
    """Izvor podataka — što autonomni agent prati."""

    TIP_CHOICES = [
        ('eu_fond', 'EU fond natječaj (eKohezija)'),
        ('hr_poticaj', 'HR poticaj (APPRRR, ARR, HAPIH)'),
        ('trzisna_cijena', 'Tržišna cijena (TISUP, Agroklub)'),
        ('vijest', 'Agro vijest / objava'),
        ('natjecaj_opg', 'Natječaj za OPG'),
        ('natjecaj_udruga', 'Natječaj za udruge'),
        ('bio_certifikacija', 'Bio certifikacija novosti'),
    ]

    naziv = models.CharField(max_length=100)
    tip = models.CharField(max_length=25, choices=TIP_CHOICES)
    url = models.URLField(verbose_name='URL izvora',
                          help_text='Npr. https://www.apprrr.hr/natjecaji/')
    xpath_ili_opis = models.TextField(blank=True,
                                      verbose_name='XPath/CSS selektor ili opis za AI',
                                      help_text='AI čita i razumije — može biti slobodan opis')
    aktivan = models.BooleanField(default=True)
    provjeri_svakih_sati = models.PositiveSmallIntegerField(default=24,
                                                             verbose_name='Interval provjere (h)')
    zadnja_provjera = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'intelligence_source'
        ordering = ['naziv']
        verbose_name = 'Izvor podataka'
        verbose_name_plural = 'Izvori podataka'

    def __str__(self):
        return f'{self.naziv} ({self.get_tip_display()})'


class IntelligenceJob(models.Model):
    """Konfiguracija praćenja za jednu kompaniju."""

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='intelligence_jobs'
    )
    sources = models.ManyToManyField(IntelligenceSource, blank=True,
                                     verbose_name='Praćeni izvori')
    aktivan = models.BooleanField(default=True)

    # Profil firme za AI matching
    opis_poslovanja = models.TextField(blank=True,
                                       verbose_name='Opis poslovanja (za AI matching)',
                                       help_text='Što firma radi, koje su joj potrebe, ciljevi')
    kljucne_rijeci = models.JSONField(default=list, blank=True,
                                      verbose_name='Ključne riječi',
                                      help_text='["govedo", "sir", "bio", "kukuruz"]')
    min_fond_iznos_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True,
                                              verbose_name='Min. iznos fonda (EUR)')
    max_fond_iznos_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True,
                                              verbose_name='Max. iznos fonda (EUR)')

    # Notifikacije
    obavijesti_whatsapp = models.BooleanField(default=True,
                                               verbose_name='Šalji na WhatsApp')
    whatsapp_broj = models.CharField(max_length=20, blank=True,
                                      verbose_name='WhatsApp broj (ako ne korisnik)')
    obavijesti_email = models.BooleanField(default=False)

    zadnji_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'intelligence_job'
        verbose_name = 'Intelligence job'
        verbose_name_plural = 'Intelligence jobs'

    def __str__(self):
        return f'Job: {self.company.name}'


class IntelligenceResult(models.Model):
    """Rezultat jednog ciklusa pretrage za jednu kompaniju."""

    STATUS_CHOICES = [
        ('novo', 'Novo — čeka objavu'),
        ('obavljeno', 'Objavljeno korisniku'),
        ('odbačeno', 'Odbačeno (nije relevantno)'),
    ]

    job = models.ForeignKey(IntelligenceJob, on_delete=models.CASCADE,
                             related_name='results')
    source = models.ForeignKey(IntelligenceSource, on_delete=models.SET_NULL,
                                null=True, blank=True)

    naslov = models.CharField(max_length=300, verbose_name='Naslov pronalaska')
    summary = models.TextField(verbose_name='AI sažetak')
    url = models.URLField(blank=True, verbose_name='Izvorni URL')
    ai_relevantnost = models.SmallIntegerField(default=0,
                                                verbose_name='AI relevantnost (0-100)')
    promo_tekst = models.TextField(blank=True,
                                    verbose_name='AI generirani promo materijal')

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='novo')
    obavljeno_at = models.DateTimeField(null=True, blank=True)

    # Veza na FundOpportunity (ako je pronađen fond)
    fund_opportunity = models.ForeignKey(
        'FundOpportunity', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='results'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'intelligence_result'
        ordering = ['-ai_relevantnost', '-created_at']
        verbose_name = 'Intelligence result'

    def __str__(self):
        return f'{self.naslov[:60]} — {self.job.company.name} ({self.ai_relevantnost}%)'


class FundOpportunity(models.Model):
    """EU fond ili HR poticaj — konkretni natječaj."""

    TIP_CHOICES = [
        ('eu_esf', 'EU ESF+ (socijalni fond)'),
        ('eu_erdf', 'EU ERDF (regionalni razvoj)'),
        ('eu_eafrd', 'EU EAFRD (ruralni razvoj / Intervencijski plan)'),
        ('hr_apprrr', 'HR APPRRR (Agencija za plaćanja)'),
        ('hr_arr', 'HR ARR (Agencija za regionalni razvoj)'),
        ('hr_hapih', 'HR HAPIH (fitosanitarni poticaji)'),
        ('hr_minpol', 'HR MINPOL (Ministarstvo poljoprivrede)'),
        ('hr_ostalo', 'HR ostalo'),
    ]
    STATUS_CHOICES = [
        ('aktivan', 'Aktivan natječaj'),
        ('uskoro', 'Uskoro (najava)'),
        ('zatvoren', 'Zatvoren'),
        ('rezultati', 'Objavljeni rezultati'),
    ]
    CILJNA_SKUPINA = [
        ('opg', 'OPG'),
        ('udruga', 'Udruga'),
        ('obrt', 'Obrt'),
        ('doo', 'd.o.o.'),
        ('svi', 'Svi'),
    ]

    naziv = models.CharField(max_length=300, verbose_name='Naziv natječaja')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivan')
    ciljna_skupina = models.CharField(max_length=10, choices=CILJNA_SKUPINA, default='svi')

    tijelo = models.CharField(max_length=200, verbose_name='Tijelo (npr. APPRRR, SAFU)')
    opis = models.TextField(verbose_name='Opis natječaja')
    uvjeti = models.TextField(blank=True, verbose_name='Uvjeti prihvatljivosti')
    url = models.URLField(blank=True)

    iznos_min_eur = models.DecimalField(max_digits=12, decimal_places=2,
                                         null=True, blank=True, verbose_name='Min. iznos (EUR)')
    iznos_max_eur = models.DecimalField(max_digits=12, decimal_places=2,
                                         null=True, blank=True, verbose_name='Max. iznos (EUR)')
    sufinanciranje_posto = models.SmallIntegerField(default=0,
                                                     verbose_name='EU sufinanciranje (%)')

    datum_otvaranja = models.DateField(null=True, blank=True)
    rok_prijave = models.DateField(null=True, blank=True, verbose_name='Rok prijave')

    # AI generated
    ai_summary = models.TextField(blank=True, verbose_name='AI sažetak (kratko)')
    ai_checklist = models.JSONField(default=list, blank=True,
                                     verbose_name='AI checklist uvjeta',
                                     help_text='["Mora biti OPG", "Min. 1ha", "ARKOD broj"]')
    kljucne_rijeci = models.JSONField(default=list, blank=True)

    otkrio_intelligence = models.BooleanField(default=False,
                                               verbose_name='Otkrio autonomni agent')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_fund_opportunity'
        ordering = ['rok_prijave', '-created_at']
        verbose_name = 'Fond / Poticaj'
        verbose_name_plural = 'Fondovi / Poticaji'

    def __str__(self):
        return f'{self.naziv} ({self.get_tip_display()}) — rok: {self.rok_prijave}'

    @property
    def days_until_deadline(self):
        if not self.rok_prijave:
            return None
        return (self.rok_prijave - timezone.now().date()).days

    @property
    def hitno(self):
        d = self.days_until_deadline
        return d is not None and 0 < d <= 14


class FundApplication(models.Model):
    """Prijava firme na fond/natječaj — praćenje statusa."""

    STATUS_CHOICES = [
        ('priprema', 'Priprema dokumentacije'),
        ('predan', 'Predan'),
        ('evaluacija', 'U evaluaciji'),
        ('odobren', 'Odobren'),
        ('odbijen', 'Odbijen'),
        ('u_provedbi', 'U provedbi'),
        ('zatvoren', 'Zatvoren / Završen'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='fund_applications')
    opportunity = models.ForeignKey(FundOpportunity, on_delete=models.CASCADE,
                                     related_name='applications')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='priprema')

    odgovorna_osoba = models.ForeignKey(settings.AUTH_USER_MODEL,
                                         on_delete=models.SET_NULL, null=True, blank=True)
    datum_prijave = models.DateField(null=True, blank=True)
    referenca_prijave = models.CharField(max_length=100, blank=True,
                                          verbose_name='Referenca/broj prijave')

    trazeni_iznos_eur = models.DecimalField(max_digits=12, decimal_places=2,
                                             null=True, blank=True)
    odobreni_iznos_eur = models.DecimalField(max_digits=12, decimal_places=2,
                                              null=True, blank=True)

    # Dokumentacija checklist (JSON lista: [{"naziv": "PR-RAS-NPF", "uploaded": true}])
    dokumenti_checklist = models.JSONField(default=list, blank=True)
    biljeske = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_fund_application'
        ordering = ['-created_at']
        unique_together = [('company', 'opportunity')]
        verbose_name = 'Prijava na fond'
        verbose_name_plural = 'Prijave na fondove'

    def __str__(self):
        return f'{self.company.name} → {self.opportunity.naziv[:50]} [{self.get_status_display()}]'
```

### Korak 2.3 — intelligence/tasks.py (Celery agent)

```python
"""
intelligence/tasks.py
Autonomni noćni patrol — pokreće se svako jutro u 03:30.

Ciklus:
  1. Za svaki aktivan IntelligenceJob
  2. Gemini agent čita URL izvora
  3. Uspoređuje s profilom firme
  4. Kreira IntelligenceResult ako je relevantno
  5. Šalje WhatsApp ako je ai_relevantnost > 60
  6. Ako je fond pronađen → kreira FundOpportunity
  7. Ako CropPlan.auto_listing_ready → kreira FuturesListing
"""
import logging
from celery import shared_task

logger = logging.getLogger('intelligence')


@shared_task(bind=True, soft_time_limit=600, max_retries=0)
def intelligence_nightly_patrol(self):
    """Pokreće se u 03:30 svako jutro."""
    from intelligence.models import IntelligenceJob, IntelligenceSource
    from intelligence.services import run_intelligence_job
    from core.notify import notify

    jobs = IntelligenceJob.objects.filter(aktivan=True).select_related('company')
    total_results = 0
    total_sent = 0

    for job in jobs:
        try:
            results, sent = run_intelligence_job(job)
            total_results += results
            total_sent += sent
            logger.info('Intelligence job %s: %d rezultata, %d poslano', job.company.name, results, sent)
        except Exception as e:
            logger.error('Intelligence job failed %s: %s', job.company.name, e)

    notify('INFO', f'Fenix Intelligence patrol završen — {total_results} pronalazaka, {total_sent} obavijesti poslano')
    return {'results': total_results, 'sent': total_sent}


@shared_task(bind=True, soft_time_limit=120)
def check_auto_listings(self):
    """
    Pokreće se svako jutro u 07:00.
    Ako CropPlan.auto_listing_ready → kreira FuturesListing na Burzi.
    Ako Livestock krava u karenciji → upozorava.
    """
    from livestock.models import CropPlan, HealthRecord
    from django.utils import timezone

    today = timezone.now().date()

    # Auto-listing za višak usjeva
    ready = CropPlan.objects.filter(
        za_prodaju=True,
        status__in=('berba', 'zavrseno'),
        procijenjeni_višak_t__gt=0,
    ).select_related('company')

    listed = 0
    for plan in ready:
        try:
            from intelligence.services import create_futures_listing_from_crop
            created = create_futures_listing_from_crop(plan)
            if created:
                listed += 1
        except Exception as e:
            logger.error('Auto-listing failed %s: %s', plan, e)

    # Upozorenje za krave koje tele uskoro
    uskoro_teljenje = __import__('livestock.models', fromlist=['Livestock']).Livestock
    grla = uskoro_teljenje.objects.filter(
        expected_calving__range=(today, today + __import__('datetime').timedelta(days=21)),
        status='gravidno',
    ).select_related('company')

    for grlo in grla:
        from core.whatsapp import send_text
        admins = __import__('accounts.models', fromlist=['UserProfile']).UserProfile
        admin = admins.objects.filter(company=grlo.company, role='company_admin').first()
        if admin and admin.user:
            phone = getattr(admin.user, 'phone', '') or ''
            if phone:
                days = (grlo.expected_calving - today).days
                send_text(phone, f'Krava {grlo.ear_tag} ({grlo.name or "bez imena"}) teli za {days} dana!')

    logger.info('Auto-listings: %d novih listinga, %d upozorenja za teljenje', listed, grla.count())
```

### Korak 2.4 — intelligence/services.py

```python
"""
intelligence/services.py
Glavna logika Intelligence agenta.
"""
import logging
import requests
from django.utils import timezone

logger = logging.getLogger('intelligence')


def run_intelligence_job(job):
    """Pokreni jedan job — provjeri sve izvore i generiraj rezultate."""
    from intelligence.models import IntelligenceResult, IntelligenceSource, FundOpportunity
    from core.gemini_agent import GeminiAgent

    results_count = 0
    sent_count = 0
    sources = job.sources.filter(aktivan=True)

    for source in sources:
        # Provjeri je li prošlo dovoljno sati od zadnje provjere
        if source.zadnja_provjera:
            hours_since = (timezone.now() - source.zadnja_provjera).total_seconds() / 3600
            if hours_since < source.provjeri_svakih_sati:
                continue

        try:
            # Gemini čita izvor i matchuje s profilom
            agent = GeminiAgent(max_steps=5)
            task = f"""
Pročitaj URL: {source.url}
Opis izvora: {source.xpath_ili_opis or source.get_tip_display()}

Profil firme koja me zanima:
{job.opis_poslovanja or job.company.name}
Ključne riječi: {job.kljucne_rijeci}

Zadatak:
1. Pročitaj sadržaj URL-a (koristi exec_command s curl)
2. Pronađi relevantne natječaje/ponude/vijesti koji odgovaraju profilu
3. Za svaki relevantan pronalazak odgovori u formatu JSON:
{{
  "pronasci": [
    {{
      "naslov": "...",
      "summary": "...",
      "url": "...",
      "relevantnost": 85,  // 0-100
      "tip": "eu_fond|hr_poticaj|trzisna_cijena|vijest",
      "rok_prijave": "2026-06-01",  // null ako nema
      "iznos_max_eur": 50000,       // null ako nema
      "promo_tekst": "OPG Kruljac, ovo je idealna prilika za vas jer...",
      "checklist": ["Mora biti OPG", "Potreban ARKOD broj"]
    }}
  ]
}}
Ako nema ništa relevantno, vrati: {{"pronasci": []}}
Vrati SAMO JSON, bez komentara.
"""
            result = agent.run_task(task)

            # Parsirај JSON iz rezultata
            import json, re
            raw = result.get('files_read', [])
            # Traži JSON u task outputu
            output = str(result)
            json_match = re.search(r'\{.*"pronasci".*\}', output, re.DOTALL)
            if not json_match:
                source.zadnja_provjera = timezone.now()
                source.save(update_fields=['zadnja_provjera'])
                continue

            data = json.loads(json_match.group())
            pronasci = data.get('pronasci', [])

            for p in pronasci:
                relevantnost = int(p.get('relevantnost', 0))
                if relevantnost < 40:
                    continue

                # Kreira FundOpportunity za fond natječaje
                fund_opp = None
                if p.get('tip') in ('eu_fond', 'hr_poticaj') and p.get('rok_prijave'):
                    import datetime
                    try:
                        rok = datetime.date.fromisoformat(p['rok_prijave'])
                        fund_opp, _ = FundOpportunity.objects.get_or_create(
                            naziv=p['naslov'][:300],
                            defaults={
                                'tip': 'eu_eafrd' if 'EU' in p.get('tip','') else 'hr_apprrr',
                                'opis': p['summary'],
                                'url': p.get('url', ''),
                                'rok_prijave': rok,
                                'iznos_max_eur': p.get('iznos_max_eur'),
                                'ai_checklist': p.get('checklist', []),
                                'ai_summary': p['summary'][:500],
                                'otkrio_intelligence': True,
                            }
                        )
                    except Exception:
                        pass

                # Spremi rezultat
                ir = IntelligenceResult.objects.create(
                    job=job,
                    source=source,
                    naslov=p['naslov'][:300],
                    summary=p['summary'],
                    url=p.get('url', ''),
                    ai_relevantnost=relevantnost,
                    promo_tekst=p.get('promo_tekst', ''),
                    fund_opportunity=fund_opp,
                )
                results_count += 1

                # Pošalji WhatsApp ako relevantnost > 60
                if relevantnost >= 60 and job.obavijesti_whatsapp:
                    sent = _posalji_obavijest(job, ir)
                    if sent:
                        ir.status = 'obavljeno'
                        ir.obavljeno_at = timezone.now()
                        ir.save(update_fields=['status', 'obavljeno_at'])
                        sent_count += 1

            source.zadnja_provjera = timezone.now()
            source.save(update_fields=['zadnja_provjera'])

        except Exception as e:
            logger.error('Source %s failed: %s', source.naziv, e)

    job.zadnji_run = timezone.now()
    job.save(update_fields=['zadnji_run'])

    return results_count, sent_count


def _posalji_obavijest(job, result):
    """Pošalji WhatsApp obavijest korisniku."""
    from core.whatsapp import send_text
    try:
        phone = job.whatsapp_broj
        if not phone:
            from accounts.models import UserProfile
            profile = UserProfile.objects.filter(
                company=job.company, role='company_admin'
            ).first()
            if profile:
                phone = getattr(profile.user, 'phone', '') or ''

        if not phone:
            return False

        msg = (
            f'🔍 *Fenix Intelligence — nova prilika*\n\n'
            f'*{result.naslov}*\n\n'
            f'{result.summary[:300]}\n\n'
            f'Relevantnost: {result.ai_relevantnost}%\n'
        )
        if result.promo_tekst:
            msg += f'\n{result.promo_tekst[:200]}'
        if result.url:
            msg += f'\n\nLink: {result.url}'

        r = send_text(phone, msg)
        return r.get('success', False)
    except Exception as e:
        logger.error('Obavijest failed: %s', e)
        return False


def create_futures_listing_from_crop(crop_plan):
    """
    Automatski kreira FuturesListing na Burzi kad je višak usjeva spreman.
    Poziva se iz check_auto_listings Celery taska.
    """
    from marketplace.models import FuturesListing, MarketplaceCategory
    from django.utils import timezone

    # Provjeri nije li već kreiran listing za ovu godinu i kulturu
    existing = FuturesListing.objects.filter(
        seller_company=crop_plan.company,
        name__icontains=crop_plan.get_kultura_display(),
        available_from__year=crop_plan.godina,
    ).exists()

    if existing:
        return False

    # Dohvati ili kreiraj kategoriju
    cat_map = {
        'kukuruz': 'Žitarice',
        'kukuruz_silaža': 'Žitarice',
        'pšenica': 'Žitarice',
        'ječam': 'Žitarice',
        'djetelina': 'Krmno bilje',
        'livada': 'Krmno bilje',
        'soja': 'Uljarice',
        'suncokret': 'Uljarice',
    }
    cat_naziv = cat_map.get(crop_plan.kultura, 'Ostalo')
    category, _ = MarketplaceCategory.objects.get_or_create(name=cat_naziv)

    import datetime
    FuturesListing.objects.create(
        seller_company=crop_plan.company,
        category=category,
        name=f'{crop_plan.get_kultura_display()} — {crop_plan.sorta or "domaće"} {crop_plan.godina}',
        description=(
            f'OPG {crop_plan.company.name} nudi višak usjeva {crop_plan.get_kultura_display()}.\n'
            f'Godina: {crop_plan.godina} | Prinos: {crop_plan.stvarni_prinos_t or "U berbi"} t\n'
            f'{"Ekološka proizvodnja" if crop_plan.is_organic else "Konvencionalna proizvodnja"}'
        ),
        unit='t',
        unit_price=0,  # OPG postavlja cijenu
        total_capacity=crop_plan.procijenjeni_višak_t,
        available_from=datetime.date(crop_plan.godina, 9, 1),
        available_until=datetime.date(crop_plan.godina, 12, 31),
        booking_deadline=datetime.date(crop_plan.godina, 8, 1),
        is_organic=crop_plan.is_organic,
        status='open',
    )
    return True
```

### Korak 2.5 — Dodaj u INSTALLED_APPS i Celery beat
```python
# U core/settings.py INSTALLED_APPS dodaj:
# 'intelligence',

# U CELERY_BEAT_SCHEDULE dodaj:
'intelligence-nightly-patrol': {
    'task': 'intelligence.tasks.intelligence_nightly_patrol',
    'schedule': crontab(hour=3, minute=30),
},
'check-auto-listings': {
    'task': 'intelligence.tasks.check_auto_listings',
    'schedule': crontab(hour=7, minute=0),
},
```

### Korak 2.6 — Migracije i provjera
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations intelligence
venv/bin/python manage.py migrate intelligence
venv/bin/python manage.py check
```

---

## APP 3 — Burza proširenje

### Korak 3.1 — Dodaj agro kategorije u ProjectLead
Pročitaj `/var/www/fina-connect/burza/models.py` pa proširi `Category`:

```python
# Dodaj u ProjectLead.Category:
KUKURUZ     = 'kukuruz',     _('Kukuruz / Žitarice')
STOKA       = 'stoka',       _('Stoka / Životinje')
MLIJEKO_SIR = 'mlijeko_sir', _('Mlijeko / Sir')
POVRCE      = 'povrce',      _('Povrće / Voće')
MEHANIZACIJA= 'mehanizacija',_('Mehanizacija / Oprema')
EU_FOND     = 'eu_fond',     _('EU Fond / Poticaj')
```

### Korak 3.2 — Migracije burza
```bash
venv/bin/python manage.py makemigrations burza
venv/bin/python manage.py migrate burza
```

---

## Korak 4 — Kreiraj početne IntelligenceSources

Management command koji popunjava početne izvore:

```python
# intelligence/management/commands/setup_intelligence_sources.py

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Kreira početne intelligence izvore (APPRRR, eKohezija, TISUP...)'

    def handle(self, *args, **kwargs):
        from intelligence.models import IntelligenceSource

        sources = [
            {
                'naziv': 'APPRRR Natječaji',
                'tip': 'hr_poticaj',
                'url': 'https://www.apprrr.hr/natjecaji/',
                'xpath_ili_opis': 'Lista aktivnih natječaja APPRRR agencije za OPG-ove. Traži rokove, iznose, uvjete.',
                'provjeri_svakih_sati': 24,
            },
            {
                'naziv': 'eKohezija EU fondovi',
                'tip': 'eu_fond',
                'url': 'https://razvoj.gov.hr/eu-fondovi/eu-fondovi-2021-2027/natjecaji/531',
                'xpath_ili_opis': 'EU fondovi HR 2021-2027 otvoreni natječaji. Fokus na ruralni razvoj, EAFRD, ESF+.',
                'provjeri_svakih_sati': 24,
            },
            {
                'naziv': 'Ministarstvo poljoprivrede natječaji',
                'tip': 'hr_poticaj',
                'url': 'https://poljoprivreda.gov.hr/istaknute-teme/natjecaji-i-javni-pozivi-116/116',
                'xpath_ili_opis': 'Lista natječaja Ministarstva poljoprivrede HR. OPG, stočarstvo, bio certifikacija.',
                'provjeri_svakih_sati': 24,
            },
            {
                'naziv': 'Agroklub vijesti',
                'tip': 'vijest',
                'url': 'https://www.agroklub.com/vijesti/',
                'xpath_ili_opis': 'Agro vijesti HR. Tržišne cijene, subvencije, upute, regulative.',
                'provjeri_svakih_sati': 12,
            },
            {
                'naziv': 'TISUP tržišne cijene',
                'tip': 'trzisna_cijena',
                'url': 'https://www.tisup.hr/tr.aspx',
                'xpath_ili_opis': 'Tržišno informacijski sustav TISUP. Cijene kukuruza, pšenice, soje po tjednu.',
                'provjeri_svakih_sati': 6,
            },
            {
                'naziv': 'HAPIH bio certifikacija',
                'tip': 'bio_certifikacija',
                'url': 'https://www.hapih.hr/ekološka-proizvodnja/',
                'xpath_ili_opis': 'Uvjeti za ekološku certifikaciju u HR. Zahtjevi, rokovi, dokumentacija.',
                'provjeri_svakih_sati': 168,
            },
        ]

        created = 0
        for s in sources:
            obj, c = IntelligenceSource.objects.get_or_create(
                url=s['url'],
                defaults=s,
            )
            if c:
                created += 1
                self.stdout.write(f'✅ Kreiran: {obj.naziv}')
            else:
                self.stdout.write(f'  Postoji: {obj.naziv}')

        self.stdout.write(f'\nUkupno novih: {created}/{len(sources)}')
```

---

## Korak 5 — Kreiraj IntelligenceJob za OPG Kruljac
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from companies.models import Company
from intelligence.models import IntelligenceJob, IntelligenceSource

kruljac = Company.objects.get(name__icontains='Kruljac')
job, created = IntelligenceJob.objects.get_or_create(
    company=kruljac,
    defaults={
        'opis_poslovanja': 'OPG sa 60 grla goveda (muzare, telad), uzgoj kukuruza i djeteline za vlastite potrebe, proizvodnja sira. Cilj prelazak na ekološku/bio certifikaciju. Slavonija, okolica Vladislavaca.',
        'kljucne_rijeci': ['govedo', 'mliječno govedarstvo', 'sir', 'kukuruz', 'djetelina', 'bio', 'ekološka certifikacija', 'OPG', 'APPRRR', 'stočarstvo'],
        'min_fond_iznos_eur': 5000,
        'obavijesti_whatsapp': True,
        'aktivan': True,
    }
)
# Dodaj sve izvore
all_sources = IntelligenceSource.objects.filter(aktivan=True)
job.sources.set(all_sources)
print('Job kreiran:', created, '| Izvora:', job.sources.count())
"
```

---

## Korak 6 — Sim_livestock: test podaci za Kruljac
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from companies.models import Company
from livestock.models import Livestock, Field, CropPlan
from django.utils import timezone
import datetime

kruljac = Company.objects.get(name__icontains='Kruljac')
today = datetime.date.today()

# 5 primjernih krava
grla = [
    {'ear_tag': 'HR414399935730001', 'name': 'Ronja', 'vrsta': 'krava', 'status': 'aktivno', 'avg_daily_milk_l': 24.5},
    {'ear_tag': 'HR414399935730002', 'name': 'Luna',  'vrsta': 'krava', 'status': 'gravidno', 'expected_calving': today + datetime.timedelta(days=15)},
    {'ear_tag': 'HR414399935730003', 'name': 'Maja',  'vrsta': 'krava', 'status': 'zasušeno'},
    {'ear_tag': 'HR414399935730004', 'name': None,    'vrsta': 'tele',  'status': 'aktivno', 'date_of_birth': today - datetime.timedelta(days=45)},
    {'ear_tag': 'HR414399935730005', 'name': 'Stella','vrsta': 'krava', 'status': 'aktivno', 'is_organic': True, 'organic_since': today - datetime.timedelta(days=180)},
]
for g in grla:
    Livestock.objects.get_or_create(company=kruljac, ear_tag=g.pop('ear_tag'), defaults={**g, 'company': kruljac})

# Parcele
p1, _ = Field.objects.get_or_create(company=kruljac, naziv='Parcela Sjever', defaults={'povrsina_ha': 8.5, 'tip_tla': 'ilovača', 'is_organic': False, 'arkod_id': 'ARK-41439-001'})
p2, _ = Field.objects.get_or_create(company=kruljac, naziv='Livada Kruljac', defaults={'povrsina_ha': 4.2, 'tip_tla': 'pjeskovita ilovača', 'is_organic': True, 'arkod_id': 'ARK-41439-002'})

# Plan sjetve
CropPlan.objects.get_or_create(company=kruljac, godina=2026, kultura='kukuruz', defaults={
    'parcela': p1, 'sorta': 'Pioneer P9074', 'status': 'posijano',
    'datum_sjetve': today - datetime.timedelta(days=10),
    'datum_berbe': today + datetime.timedelta(days=150),
    'planrani_prinos_t_ha': 8.5,
    'za_vlastite_potrebe': True, 'za_prodaju': True,
    'procijenjeni_višak_t': 12.0,
    'gnojidba_opis': 'NPK 15-15-15, 300kg/ha pri sjetvi',
    'zastita_opis': 'Primextra Gold SC herbicid',
})
CropPlan.objects.get_or_create(company=kruljac, godina=2026, kultura='djetelina', defaults={
    'parcela': p2, 'status': 'raste',
    'planrani_prinos_t_ha': 6.0,
    'za_vlastite_potrebe': True, 'za_prodaju': False,
    'is_organic': True,
    'gnojidba_opis': 'Bez mineralnih gnojiva — bio parcela',
})

print('Livestock:', Livestock.objects.filter(company=kruljac).count())
print('Fields:', Field.objects.filter(company=kruljac).count())
print('CropPlans:', CropPlan.objects.filter(company=kruljac).count())
"
```

---

## Korak 7 — Test Intelligence patrol (suhi test)
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from intelligence.models import IntelligenceJob
from intelligence.services import run_intelligence_job

job = IntelligenceJob.objects.filter(company__name__icontains='Kruljac').first()
print('Job:', job)
# Samo suhi test — 1 izvor, bez WhatsApp slanja
job.obavijesti_whatsapp = False
results, sent = run_intelligence_job(job)
print(f'Rezultati: {results}, Poslano: {sent}')

from intelligence.models import IntelligenceResult
for r in IntelligenceResult.objects.filter(job=job).order_by('-ai_relevantnost')[:5]:
    print(f'  {r.ai_relevantnost}% — {r.naslov[:60]}')
" 2>&1 | tail -20
```

---

## Korak 8 — Setup sources + restart
```bash
cd /var/www/fina-connect
venv/bin/python manage.py setup_intelligence_sources
systemctl restart celery-worker
venv/bin/python manage.py check
```

---

## Korak 9 — Ažuriraj FENIX_STATUS.md
Kad sve prođe, dodaj u DONE sekciju:
```
### Livestock modul (NOVO)
- Livestock, HealthRecord, MilkRecord, Field, CropPlan modeli — DONE
- auto_listing_ready property — DONE
- Test podaci za OPG Kruljac (5 grla, 2 parcele, 2 CropPlana) — DONE

### Intelligence modul (NOVO)
- IntelligenceSource, IntelligenceJob, IntelligenceResult — DONE
- FundOpportunity, FundApplication — DONE
- intelligence_nightly_patrol Celery task (03:30) — DONE
- check_auto_listings Celery task (07:00) — DONE
- setup_intelligence_sources management command — DONE
- IntelligenceJob kreiran za OPG Kruljac — DONE
- Burza: agro kategorije dodane — DONE
```

---

## Definicija DONE
- [ ] livestock app: 5 modela, migracije OK
- [ ] intelligence app: 6 modela, migracije OK
- [ ] burza: agro kategorije dodane
- [ ] setup_intelligence_sources: 6 izvora kreirana
- [ ] IntelligenceJob za OPG Kruljac
- [ ] Test podaci: 5 grla, 2 parcele, 2 plana sjetve
- [ ] Test patrol pokrenut, barem 1 rezultat
- [ ] django check: 0 grešaka
- [ ] celery-worker restartan
- [ ] /tmp/intelligence_done.txt

