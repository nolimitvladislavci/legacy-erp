# CC TASK: Udruge branitelja — model + views + template
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-26
## Naručitelj: Ivan Anić (sam branitelj — osobno relevantan)

## OBAVEZNO PROČITAJ PRVO
```bash
cat udruge/models.py | head -200
cat udruge/migrations/0009_segment_models_dvd_kud_ribolov_pcelari_rakija_vocari.py | head -30
cat udruge/views.py | grep "def branitelj\|def bran\|def veteran" | head -10
ls templates/udruge/ | grep -i bran
```

## Kontekst
Udruge modul već ima:
- Clan model s membership_type='branitelj' (samo label, bez logike)
- DVD, KUD, Ribolov, Pčelari, Rakija, Voćari — potpuno implementirani

Nedostaje: dedicirani segment za udruge branitelja (HVIDRA, HDR, UHDDR, LD 105 i sl.)
Ovo je zakonski najsloženiji segment — ima vlastitu legislativu.

## Zakonski okvir
- Zakon o hrvatskim braniteljima iz Domovinskog rata NN 121/17, 98/19, 84/21, 156/23
- Pravilnik o Evidenciji branitelja NN 127/21
- Pravilnik o vođenju evidencija i kontroli isplata NN 2024
- Statusi: branitelj / HRVI (I-IV skupina) / smrtno_stradali / nestali / dragovoljac
- Fond branitelja — udjeli, nasljednici
- 19 kategorija prava: zdravstvo, mirovina, stambeno, obrazovanje djece...

## Migracija — novi model

```python
# Dodati u udruge/models.py (na kraj, nakon TretmanVocnjaka)

class StatusBranitelja(models.Model):
    """
    Detalji braniteljskog statusa — uz Clan model.
    Jedan Clan može imati jedan StatusBranitelja.
    Zakon: NN 121/17 čl.3-6 + Pravilnik o Evidenciji NN 127/21
    """
    VRSTA_STATUSA = [
        ('branitelj',      'Hrvatski branitelj iz DR'),
        ('dragovoljac',    'Dragovoljac iz DR'),
        ('hrvi_1',         'HRVI — I. skupina (80-100%)'),
        ('hrvi_2',         'HRVI — II. skupina (60-79%)'),
        ('hrvi_3',         'HRVI — III. skupina (40-59%)'),
        ('hrvi_4',         'HRVI — IV. skupina (20-39%)'),
        ('civilni_invalid','Civilni invalid rata'),
        ('smrtno_stradali','Smrtno stradali (nasljednici)'),
        ('nestali',        'Nestali (obitelj)'),
    ]

    POSTROJBA_CHOICES = [
        ('HV',   'Hrvatska vojska'),
        ('MUP',  'Ministarstvo unutarnjih poslova'),
        ('ZNG',  'Zbor narodne garde'),
        ('HOS',  'Hrvatske obrambene snage'),
        ('NZ',   'Narodna zaštita'),
        ('HVO',  'Hrvatsko vijeće obrane (BiH)'),
        ('ostalo','Ostalo'),
    ]

    clan = models.OneToOneField(
        'Clan', on_delete=models.CASCADE,
        related_name='status_branitelja',
        verbose_name='Član'
    )
    vrsta_statusa = models.CharField(
        max_length=20, choices=VRSTA_STATUSA,
        default='branitelj', verbose_name='Vrsta statusa'
    )
    postrojba = models.CharField(
        max_length=10, choices=POSTROJBA_CHOICES,
        blank=True, verbose_name='Postrojba'
    )
    naziv_postrojbe = models.CharField(
        max_length=200, blank=True,
        verbose_name='Puni naziv postrojbe'
    )
    od_datuma = models.DateField(
        null=True, blank=True,
        verbose_name='Sudjelovanje od'
    )
    do_datuma = models.DateField(
        null=True, blank=True,
        verbose_name='Sudjelovanje do'
    )
    dana_sudjelovanja = models.PositiveIntegerField(
        default=0,
        verbose_name='Ukupno dana sudjelovanja',
        help_text='Iz potvrde Ministarstva branitelja'
    )
    borbeni_sektor = models.BooleanField(
        default=False,
        verbose_name='Borbeni sektor',
        help_text='100+ dana u borbenom sektoru — posebna prava'
    )
    # Registar i potvrde
    broj_potvrde_ministarstva = models.CharField(
        max_length=50, blank=True,
        verbose_name='Broj potvrde Ministarstva branitelja'
    )
    datum_potvrde = models.DateField(
        null=True, blank=True,
        verbose_name='Datum potvrde'
    )
    # HRVI specifično
    postotak_invalidnosti = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Postotak oštećenja organizma (%)',
        help_text='Samo za HRVI — 20-100%'
    )
    ima_njegovatelja = models.BooleanField(
        default=False,
        verbose_name='Pravo na njegovatelja',
        help_text='HRVI I. skupina 100% — pravo na osobu za njegu'
    )
    # Fond branitelja
    fond_udjeli = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        verbose_name='Udjeli u Fondu HB'
    )
    fond_nasljednici = models.CharField(
        max_length=500, blank=True,
        verbose_name='Nasljednici udjela u Fondu'
    )
    # Prava koja se koriste (JSONField za fleksibilnost)
    ostvarena_prava = models.JSONField(
        default=dict, blank=True,
        verbose_name='Ostvarena prava',
        help_text='npr. {"zdravstvo": true, "stambeno": false, "mirovina_branitelja": true}'
    )
    # Odlikovanja
    odlikovanja = models.TextField(
        blank=True,
        verbose_name='Odlikovanja i priznanja',
        help_text='Red Danice, Domovinska medalja, itd.'
    )
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_status_branitelja'
        verbose_name = 'Status branitelja'
        verbose_name_plural = 'Statusi branitelja'

    def __str__(self):
        return f'{self.clan} — {self.get_vrsta_statusa_display()}'

    @property
    def je_hrvi(self):
        return self.vrsta_statusa.startswith('hrvi_')

    @property
    def hrvi_skupina(self):
        if not self.je_hrvi:
            return None
        return int(self.vrsta_statusa.split('_')[1])

    @property
    def prava_summary(self):
        """Sažetak ostvarenih prava za dashboard."""
        prava = self.ostvarena_prava or {}
        aktivna = [k for k, v in prava.items() if v]
        return activna


class OdlikovanjeBranitelja(models.Model):
    """Odlikovanje ili priznanje — za evidenciju u udruzi."""
    ODLIKOVANJE_VRSTA = [
        ('red_danice_hr',     'Red Danice Hrvatske'),
        ('red_danice_obr',    'Red Danice — s likom Franje Buntića'),
        ('red_danice_bla',    'Red Danice — s likom bl. Alojzija'),
        ('domovinska_rat',    'Domovinska medalja — ratna'),
        ('domovinska_mir',    'Domovinska medalja — mirovna'),
        ('sjepan_medalja',    'Medalja kralja Zvonimira'),
        ('medalja_slobode',   'Medalja slobode'),
        ('streljacki_red',    'Streljačke počasne oznake'),
        ('ostalo',            'Ostalo odlikovanje'),
    ]
    clan = models.ForeignKey(
        'Clan', on_delete=models.CASCADE,
        related_name='odlikovanja_bran'
    )
    vrsta = models.CharField(max_length=30, choices=ODLIKOVANJE_VRSTA)
    naziv = models.CharField(max_length=200, verbose_name='Puni naziv')
    datum_dodjeljivanja = models.DateField(null=True, blank=True)
    broj_odluke = models.CharField(max_length=100, blank=True)
    napomena = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'udruge_odlikovanje_branitelja'
        verbose_name = 'Odlikovanje'
        ordering = ['-datum_dodjeljivanja']
```

## Što graditi

### 1. Migracija
```bash
venv/bin/python manage.py makemigrations udruge --name="branitelji_status_odlikovanja"
venv/bin/python manage.py migrate udruge
```

### 2. Views (udruge/views.py — dodaj na kraj)
```python
@login_required
def branitelji_dashboard(request):
    """Dashboard za udrugu branitelja."""
    company = get_user_company(request)
    from .models import Clan, StatusBranitelja
    
    clanovi = Clan.objects.filter(company=company, status='aktivan')
    branitelji = StatusBranitelja.objects.filter(clan__company=company)
    
    stats = {
        'ukupno': branitelji.count(),
        'hrvi': branitelji.filter(vrsta_statusa__startswith='hrvi_').count(),
        'dragovoljci': branitelji.filter(vrsta_statusa='dragovoljac').count(),
        'borbeni_sektor': branitelji.filter(borbeni_sektor=True).count(),
        's_odlikovanjem': branitelji.filter(
            clan__odlikovanja_bran__isnull=False
        ).distinct().count(),
    }
    
    return render(request, 'udruge/branitelji_dashboard.html', {
        'branitelji': branitelji.select_related('clan').order_by('clan__last_name'),
        'stats': stats,
    })


@login_required
def branitelj_status_create(request, clan_pk):
    """Unos braniteljskog statusa za člana."""
    company = get_user_company(request)
    from .models import Clan, StatusBranitelja
    
    clan = get_object_or_404(Clan, pk=clan_pk, company=company)
    
    if hasattr(clan, 'status_branitelja'):
        return redirect('udruge:branitelj_status_edit', pk=clan.status_branitelja.pk)
    
    if request.method == 'POST':
        data = request.POST
        StatusBranitelja.objects.create(
            clan=clan,
            vrsta_statusa=data.get('vrsta_statusa', 'branitelj'),
            postrojba=data.get('postrojba', ''),
            naziv_postrojbe=data.get('naziv_postrojbe', ''),
            od_datuma=data.get('od_datuma') or None,
            do_datuma=data.get('do_datuma') or None,
            dana_sudjelovanja=int(data.get('dana_sudjelovanja') or 0),
            borbeni_sektor=bool(data.get('borbeni_sektor')),
            broj_potvrde_ministarstva=data.get('broj_potvrde_ministarstva', ''),
            datum_potvrde=data.get('datum_potvrde') or None,
            postotak_invalidnosti=int(data.get('postotak_invalidnosti') or 0) or None,
            odlikovanja=data.get('odlikovanja', ''),
            napomena=data.get('napomena', ''),
        )
        return redirect('udruge:branitelji_dashboard')
    
    return render(request, 'udruge/branitelj_status_form.html', {
        'clan': clan,
        'vrsta_choices': StatusBranitelja.VRSTA_STATUSA,
        'postrojba_choices': StatusBranitelja.POSTROJBA_CHOICES,
    })
```

### 3. URLs (udruge/urls.py — dodaj)
```python
path('branitelji/', views.branitelji_dashboard, name='branitelji_dashboard'),
path('branitelji/status/<int:clan_pk>/create/', views.branitelj_status_create, name='branitelj_status_create'),
```

### 4. Templates — kreirati
- `templates/udruge/branitelji_dashboard.html`
- `templates/udruge/branitelj_status_form.html`

**Stil**: kopirati strukturu iz `templates/udruge/dvd_dashboard.html` — isti CSS pattern.

**Dashboard treba prikazati:**
- Stats grid: ukupno / HRVI / dragovoljci / borbeni sektor / s odlikovanjem
- Tablica članova s kolonama: Ime, Vrsta statusa, Postrojba, Dana, HRVI%, Fond udjeli, Odlikovanja
- Gumb "Unesi status" na svakom članu bez statusa
- Filter po vrsti statusa
- Export CSV (koristiti postojeći pattern iz clan_list.html)

### 5. Provjera
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/hr/udruge/branitelji/
# Očekivano: 302 (redirect na login) = OK
```

## DONE kriterij
```bash
venv/bin/python manage.py migrate udruge --check  # 0 pending
venv/bin/python manage.py check  # no errors
grep "branitelji_dashboard\|StatusBranitelja" udruge/views.py | wc -l  # >= 2
ls templates/udruge/branitelji_dashboard.html  # postoji
```
