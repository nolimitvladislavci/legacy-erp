# CC TASK: Lovačka društva — Lov modul
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-26
## Zakon: Zakon o lovstvu (NN), Pravilnik o uvjetima i načinu lova NN 48/22
## SLE: Središnja lovna evidencija aktivna od 5. lipnja 2025.

## OBAVEZNO PROČITAJ PRVO
```bash
# Provjeri što postoji za ribolov — lov treba isti pattern
grep "class Revir\|class Ribolovna\|class Ulov" udruge/models.py
cat udruge/migrations/0009_segment_models_dvd_kud_ribolov_pcelari_rakija_vocari.py | grep "Revir\|Ribolov" | head -20
ls templates/udruge/ribolov*
```

## Kontekst
Ribolov je već implementiran u potpunosti:
- Revir, RibolovnaDozvola (A-D), UlovEvidencija (Obrazac UL), Poribljavanje, CuvarskaStraza
- 4 templatea: ribolov_dashboard, reviri_list, dozvole_list, ulovi_list

Lov treba **isti tretman** — analogna struktura ali s lovačkom specifičnošću:
- Lovačka iskaznica (5 god + godišnja markica) — HLS izdaje
- Dopuštenje za lov (numerirana isprava) — lovoovlaštenik izdaje
- Zapisnik o obavljenom lovu (ZOL) — obveza od 5.6.2025. elektronički u SLE
- Trofej — vrjednovanje sukladno Pravilniku NN 99/18
- Lovnogospodarska osnova — plan odstrjela po vrstama

## Novi modeli (dodati u udruge/models.py)

```python
# ───────────────────────────────────────────────────────────────
#  Lov — Zakon o lovstvu (NN), Pravilnik NN 48/22, SLE od 06/2025
# ───────────────────────────────────────────────────────────────

class Loviste(models.Model):
    """Lovište — površina kojom gospodari udruga."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='lovista'
    )
    naziv = models.CharField(max_length=200, verbose_name='Naziv lovišta')
    broj_lovista = models.CharField(
        max_length=30, blank=True,
        verbose_name='Broj lovišta (iz rješenja)',
        help_text='Dodijeljuje Ministarstvo/Županija'
    )
    povrsina_ha = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Površina (ha)'
    )
    vrsta = models.CharField(max_length=20, choices=[
        ('zajednicko', 'Zajedničko lovište'),
        ('privatno',   'Privatno lovište'),
        ('uzgajaliste', 'Uzgajalište divljači'),
    ], default='zajednicko')
    lovoovlastenik = models.CharField(
        max_length=200, blank=True,
        verbose_name='Lovoovlaštenik'
    )
    zakup_od = models.DateField(null=True, blank=True, verbose_name='Zakup od')
    zakup_do = models.DateField(null=True, blank=True, verbose_name='Zakup do')
    opis_granica = models.TextField(blank=True, verbose_name='Opis granica lovišta')
    napomena = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'udruge_loviste'
        verbose_name = 'Lovište'
        ordering = ['naziv']

    def __str__(self):
        return f'{self.naziv} ({self.povrsina_ha} ha)'


class LovackaIskaznica(models.Model):
    """
    Lovačka iskaznica — izdaje HLS.
    Pravilnik NN 48/22 čl. 9-11:
    - Rok važenja: 5 godina za HR državljane
    - Godišnja identifikacijska markica (lovna godina 1.4. - 31.3.)
    - Stranim državljanima: sezonska
    """
    KATEGORIJA_CHOICES = [
        ('hr_5god',  'HR državljanin (5 godina)'),
        ('inozemac', 'Strani državljanin (sezonska)'),
        ('pocasna',  'Počasna iskaznica'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='lovacke_iskaznice'
    )
    clan = models.ForeignKey(
        'Clan', on_delete=models.CASCADE,
        related_name='lovacke_iskaznice'
    )
    broj_iskaznice = models.CharField(
        max_length=30, verbose_name='Broj iskaznice'
    )
    kategorija = models.CharField(
        max_length=15, choices=KATEGORIJA_CHOICES,
        default='hr_5god'
    )
    datum_izdavanja = models.DateField(verbose_name='Datum izdavanja')
    vrijedi_do = models.DateField(verbose_name='Vrijedi do')
    # Godišnja markica (lovna godina)
    markica_godina = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Markica za lovnu godinu',
        help_text='Lovna godina počinje 1. travnja'
    )
    markica_datum = models.DateField(
        null=True, blank=True,
        verbose_name='Datum lijepljenja markice'
    )
    # Lovački ispit
    uvjerenje_ispit = models.CharField(
        max_length=50, blank=True,
        verbose_name='Broj uvjerenja o položenom ispitu'
    )
    datum_ispita = models.DateField(
        null=True, blank=True,
        verbose_name='Datum polaganja ispita'
    )
    napomena = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_lovacka_iskaznica'
        verbose_name = 'Lovačka iskaznica'
        ordering = ['-datum_izdavanja']

    def __str__(self):
        return f'Iskaznica {self.broj_iskaznice} — {self.clan}'

    @property
    def je_aktivna(self):
        from django.utils import timezone
        return self.vrijedi_do >= timezone.now().date()

    @property
    def treba_markicu(self):
        """Provjeri treba li obnova godišnje markice."""
        from django.utils import timezone
        today = timezone.now().date()
        lovna_god = today.year if today.month >= 4 else today.year - 1
        return self.markica_godina != lovna_god


class DopustenjeLova(models.Model):
    """
    Dopuštenje za lov — numerirana isprava (Pravilnik NN 48/22 čl. 13).
    Od 5.6.2025. elektronički u SLE (Središnja lovna evidencija).
    Lovoovlaštenik izdaje lovcu za konkretan dan/vrstu divljači.
    """
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='dopustenja_lova'
    )
    loviste = models.ForeignKey(
        Loviste, on_delete=models.PROTECT,
        related_name='dopustenja'
    )
    clan = models.ForeignKey(
        'Clan', on_delete=models.CASCADE,
        related_name='dopustenja_lova'
    )
    broj_dopustenja = models.CharField(
        max_length=20, verbose_name='Broj dopuštenja'
    )
    datum_lova = models.DateField(verbose_name='Datum lova')
    vrsta_divljaci = models.CharField(
        max_length=100,
        verbose_name='Vrsta divljači',
        help_text='npr. Srna, Divlja svinja, Fazan'
    )
    broj_komada = models.PositiveSmallIntegerField(
        default=1, verbose_name='Dozvoljeni broj komada'
    )
    sle_evidencija_br = models.CharField(
        max_length=50, blank=True,
        verbose_name='Broj u SLE',
        help_text='Srednja lovna evidencija — od 5.6.2025. obvezno'
    )
    napomena = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_dopustenje_lova'
        verbose_name = 'Dopuštenje za lov'
        ordering = ['-datum_lova']

    def __str__(self):
        return f'Dopuštenje {self.broj_dopustenja} — {self.vrsta_divljaci} ({self.datum_lova})'


class ZapisnikLova(models.Model):
    """
    Zapisnik o obavljenom lovu (ZOL) — Pravilnik NN 48/22 čl. 13.
    Obveza: evidencija svakog lova u kojem je bilo izlučenja divljači.
    Od 5.6.2025. elektronički u SLE.
    """
    NACIN_LOVA = [
        ('pojedinacni', 'Pojedinačni lov'),
        ('skupni',      'Skupni lov (hajka)'),
        ('tihacenje',   'Tihačenje'),
        ('iz_zasjede',  'Iz zasjede'),
        ('prihrana',    'S mjesta za prihrane'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='zapisnici_lova'
    )
    dopustenje = models.ForeignKey(
        DopustenjeLova, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='zapisnici'
    )
    loviste = models.ForeignKey(
        Loviste, on_delete=models.PROTECT,
        related_name='zapisnici'
    )
    clan = models.ForeignKey(
        'Clan', on_delete=models.CASCADE,
        related_name='zapisnici_lova'
    )
    datum = models.DateField(verbose_name='Datum lova')
    nacin_lova = models.CharField(
        max_length=15, choices=NACIN_LOVA,
        default='pojedinacni'
    )
    vrsta_divljaci = models.CharField(
        max_length=100, verbose_name='Vrsta divljači'
    )
    spol = models.CharField(max_length=10, choices=[
        ('muz', 'Mužjak'), ('zen', 'Ženka'), ('mlado', 'Mlado'),
    ], blank=True)
    masa_kg = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        verbose_name='Masa (kg)'
    )
    lokalitet = models.CharField(
        max_length=200, blank=True,
        verbose_name='Lokalitet (dio lovišta)'
    )
    sle_broj = models.CharField(
        max_length=50, blank=True,
        verbose_name='Broj u SLE'
    )
    photo = models.ImageField(
        upload_to='lov/zapisnici/%Y/', blank=True,
        verbose_name='Fotografija'
    )
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_zapisnik_lova'
        verbose_name = 'Zapisnik o lovu'
        ordering = ['-datum']

    def __str__(self):
        return f'{self.vrsta_divljaci} — {self.clan} ({self.datum})'


class Trofej(models.Model):
    """
    Trofej divljači — vrjednovanje sukladno Pravilniku NN 99/18, 32/19, 32/20.
    Rogonosci, čeljusti, lubanje — obvezno vrjednovanje za krupnu divljač.
    """
    VRSTA_TROFEJA = [
        ('jelen_paroske',  'Jelenje paroške'),
        ('srna_rogi',      'Srneće rogovlje'),
        ('vepar_kljove',   'Veprove kljove'),
        ('medvjed_lubanja','Medvjeđa lubanja'),
        ('los_loptate',    'Losove lopataste paroške'),
        ('muflon_rogi',    'Muflonovo rogovlje'),
        ('ostalo',         'Ostali trofej'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='trofeji'
    )
    zapisnik = models.OneToOneField(
        ZapisnikLova, on_delete=models.CASCADE,
        related_name='trofej', null=True, blank=True
    )
    clan = models.ForeignKey(
        'Clan', on_delete=models.CASCADE,
        related_name='trofeji'
    )
    vrsta = models.CharField(max_length=20, choices=VRSTA_TROFEJA)
    rok_lista = models.DecimalField(
        max_digits=5, decimal_places=1,
        null=True, blank=True,
        verbose_name='Rok lista (cm)'
    )
    teza_kg = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='Težina trofeja (kg)'
    )
    cis_tockova = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        verbose_name='CIC točaka (vrjednovanje)'
    )
    medalja = models.CharField(
        max_length=10, blank=True,
        choices=[('zlato','Zlato'), ('srebro','Srebro'), ('bronca','Bronca'), ('','Bez medalje')],
        verbose_name='Medalja'
    )
    datum_vrjednovanja = models.DateField(
        null=True, blank=True,
        verbose_name='Datum vrjednovanja'
    )
    photo = models.ImageField(upload_to='lov/trofeji/%Y/', blank=True)
    napomena = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'udruge_trofej'
        verbose_name = 'Trofej'
        ordering = ['-cis_tockova']

    def __str__(self):
        return f'{self.get_vrsta_display()} — {self.clan} ({self.cis_tockova or "?") } CIC'
```

## Migracija
```bash
venv/bin/python manage.py makemigrations udruge --name="lov_loviste_iskaznica_zapisnik_trofej"
venv/bin/python manage.py migrate udruge
```

## Views — potrebno kreirati
Isti pattern kao ribolov:

```python
# Views koje treba kreirati u udruge/views.py:
# lov_dashboard(request) → 'udruge/lov_dashboard.html'
# lov_iskaznice_list(request) → filter treba_markicu
# lov_dopustenja_list(request)
# lov_dopustenje_create(request)
# lov_zapisnici_list(request)
# lov_zapisnik_create(request)
# lov_trofeji_list(request)
```

## URLs
```python
path('lov/', views.lov_dashboard, name='lov_dashboard'),
path('lov/iskaznice/', views.lov_iskaznice_list, name='lov_iskaznice_list'),
path('lov/dopustenja/', views.lov_dopustenja_list, name='lov_dopustenja_list'),
path('lov/dopustenja/create/', views.lov_dopustenje_create, name='lov_dopustenje_create'),
path('lov/zapisnici/', views.lov_zapisnici_list, name='lov_zapisnici_list'),
path('lov/zapisnici/create/', views.lov_zapisnik_create, name='lov_zapisnik_create'),
path('lov/trofeji/', views.lov_trofeji_list, name='lov_trofeji_list'),
```

## Templates — 5 novih
- `templates/udruge/lov_dashboard.html` — kopirati ribolov_dashboard.html strukturu
- `templates/udruge/lov_iskaznice_list.html` — s alertom "treba_markicu"
- `templates/udruge/lov_dopustenja_list.html`
- `templates/udruge/lov_zapisnici_list.html`
- `templates/udruge/lov_trofeji_list.html`

**Dashboard stat kartice:**
- Ukupno lovaca / Aktivne iskaznice / Iskaznice za obnovu / Ukupno odstrjela / Trofeji s medaljom

## DONE kriterij
```bash
venv/bin/python manage.py migrate udruge --check
venv/bin/python manage.py check
grep "class Loviste\|class LovackaIskaznica\|class ZapisnikLova\|class Trofej" udruge/models.py | wc -l  # = 4
ls templates/udruge/lov_dashboard.html
```
