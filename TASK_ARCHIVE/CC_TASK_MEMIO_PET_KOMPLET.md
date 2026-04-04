# CC_TASK: MEMIO.PET KOMPLET — Dresura, Hotel, Ovce, Koze
# Datum: 04.04.2026. | Rok: 05.04.2026. | Prioritet: P0
# Cilj: zatvori memio.pet ekosustav — 10/10, bez rupa

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: venv/bin/python manage.py check + migrate 2>&1 | tail -5

---

## KORAK 1 — PROVJERI TEREN

```bash
grep -n "VRSTA_CHOICES\|account_type\|ACCOUNT_TYPE" memio_pet/models.py | head -20
grep -n "VRSTA_CHOICES" livestock/models.py | head -10
grep -n "appointment_type\|APPOINTMENT_TYPE" appointments/models.py | head -10
grep -rn "class DogTraining\|class PetBoarding\|class PetHotel" --include="*.py" | grep -v venv
```

---

## KORAK 2 — AnimalProfile VRSTA proširenje

READ: `memio_pet/models.py` (VRSTA_CHOICES blok, ~linija 85-115)

U VRSTA_CHOICES listi DODAJ (bez brisanja postojećih):
```python
('ovca',   'Ovca'),
('koza',   'Koza'),
('svinja', 'Svinja/Prasac'),
('ptica',  'Ptica/Peradar'),
('zec',    'Zec'),
('konj',   'Konj'),  # ako već nije
('ostalo', 'Ostalo'),
```

NEMA MIGRACIJE — CharField choices promjena.

---

## KORAK 3 — Livestock VRSTA proširenje

READ: `livestock/models.py` (VRSTA_CHOICES blok, ~linija 14-30)

DODAJ u VRSTA_CHOICES:
```python
('ovca',   'Ovca'),
('janje',  'Janje'),
('ovan',   'Ovan'),
('koza',   'Koza'),
('kozle',  'Kozle'),
('jarac',  'Jarac'),
('svinja', 'Svinja'),
('prasac', 'Prasac'),
('nerast', 'Nerast'),
('krmaca', 'Krmača'),
('kokoska','Kokoška/Peradar'),
('purica', 'Purica'),
```

MIGRACIJA (samo choices, ne mijenja shemu — provjeri je li auto):
```bash
venv/bin/python manage.py makemigrations livestock --name="add_ovce_koze_svinje" 2>&1
venv/bin/python manage.py migrate 2>&1 | tail -3
```

---

## KORAK 4 — BreederProfile account_type proširenje

READ: `memio_pet/models.py` (ACCOUNT_TYPE_CHOICES, ~linija 20-25)

DODAJ tipove:
```python
('trainer',      'Kinolog / Dresura pasa'),
('hotel',        'Pet Hotel / Pension'),
('sheep_farmer', 'Uzgajivač ovaca i koza'),
('pig_farmer',   'Uzgajivač svinja'),
('poultry',      'Peradarstvo'),
('horse',        'Konjički sport / uzgoj konja'),
```

NEMA MIGRACIJE — CharField choices.

---

## KORAK 5 — DogTrainingSession model

READ: `memio_pet/models.py` (zadnjih 30 linija + importse)

DODAJ na kraj memio_pet/models.py:

```python
class DogTrainingSession(models.Model):
    """Evidencija dresure / treninga psa."""

    TRAINING_TYPES = [
        ('osnovna',        'Osnovna poslušnost'),
        ('napredna',       'Napredna poslušnost'),
        ('agility',        'Agility / Prepreke'),
        ('zastitar',       'Zaštitarska obuka (IGP/IPO)'),
        ('lov',            'Lovačka dresura'),
        ('vodic',          'Pas vodič'),
        ('nos_mirisi',     'Nosenje mirisa / SAR traganje'),
        ('socijalizacija', 'Socijalizacija šteneta'),
        ('terapija',       'Terapijski pas'),
        ('ostalo',         'Ostalo'),
    ]
    OCJENA_CHOICES = [(i, str(i)) for i in range(1, 6)]

    animal   = models.ForeignKey(
        AnimalProfile, on_delete=models.CASCADE,
        related_name='training_sessions',
        verbose_name='Životinja',
    )
    trainer  = models.ForeignKey(
        BreederProfile, on_delete=models.SET_NULL, null=True,
        related_name='training_sessions',
        limit_choices_to={'account_type': 'trainer'},
        verbose_name='Trener / Kinolog',
    )
    datum          = models.DateField(verbose_name='Datum treninga')
    tip            = models.CharField(max_length=20, choices=TRAINING_TYPES, default='osnovna')
    trajanje_min   = models.PositiveIntegerField(default=60, verbose_name='Trajanje (min)')
    napomena       = models.TextField(blank=True, verbose_name='Napomena trenera')
    ocjena         = models.PositiveSmallIntegerField(
        choices=OCJENA_CHOICES, null=True, blank=True,
        verbose_name='Ocjena napretka (1-5)',
    )
    # AI generated summary (Haiku, generira se lazy)
    ai_summary     = models.TextField(blank=True, verbose_name='AI sažetak napretka')
    ai_generated   = models.BooleanField(default=False)

    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering = ['-datum']
        verbose_name = 'Trening sesija'
        verbose_name_plural = 'Trening sesije'

    def __str__(self):
        return f'{self.animal.name} — {self.get_tip_display()} ({self.datum})'
```

---

## KORAK 6 — PetBoardingReservation model

DODAJ odmah iza DogTrainingSession:

```python
class PetBoardingReservation(models.Model):
    """Rezervacija pet hotela / pensiona."""

    STATUS_CHOICES = [
        ('pending',     'Na čekanju'),
        ('confirmed',   'Potvrđeno'),
        ('checked_in',  'Prijavljen'),
        ('checked_out', 'Odjava'),
        ('cancelled',   'Otkazano'),
        ('no_show',     'Nije se pojavio'),
    ]

    animal        = models.ForeignKey(
        AnimalProfile, on_delete=models.CASCADE,
        related_name='boarding_reservations',
        verbose_name='Životinja',
    )
    hotel         = models.ForeignKey(
        BreederProfile, on_delete=models.CASCADE,
        related_name='boarding_reservations',
        limit_choices_to={'account_type': 'hotel'},
        verbose_name='Pet Hotel',
    )
    vlasnik_ime   = models.CharField(max_length=150, verbose_name='Ime vlasnika')
    vlasnik_tel   = models.CharField(max_length=30, verbose_name='Telefon vlasnika')
    vlasnik_email = models.EmailField(blank=True)

    datum_in      = models.DateField(verbose_name='Datum dolaska')
    datum_out     = models.DateField(verbose_name='Datum odlaska')
    soba_broj     = models.CharField(max_length=20, blank=True, verbose_name='Broj sobe/boks')

    cijena_po_noci = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Cijena po noći (EUR)',
    )
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # Posebne napomene (prehrana, lijekovi, karakter)
    napomene_prehrana = models.TextField(blank=True, verbose_name='Prehrana')
    napomene_lijekovi = models.TextField(blank=True, verbose_name='Lijekovi i doze')
    napomene_karakter = models.TextField(blank=True, verbose_name='Karakter / upozorenja')

    # AI polje — generira se pri check-in/check-out
    ai_checkin_summary  = models.TextField(blank=True)
    ai_checkout_summary = models.TextField(blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_pet'
        ordering = ['-datum_in']
        verbose_name = 'Pet Hotel rezervacija'
        verbose_name_plural = 'Pet Hotel rezervacije'

    def __str__(self):
        return f'{self.animal.name} @ {self.hotel.name} ({self.datum_in}→{self.datum_out})'

    @property
    def broj_nocenja(self):
        return max(0, (self.datum_out - self.datum_in).days)

    @property
    def ukupna_cijena(self):
        return self.broj_nocenja * self.cijena_po_noci
```

MIGRACIJA:
```bash
venv/bin/python manage.py makemigrations memio_pet --name="add_training_boarding"
venv/bin/python manage.py migrate 2>&1 | tail -5
```

---

## KORAK 7 — Appointments tip proširenje

READ: `appointments/models.py` — pronađi APPOINTMENT_TYPE ili choices za tip

DODAJ tipove:
```python
('dresura_pas',        'Dresura / Trening psa'),
('agility_session',   'Agility sesija'),
('pet_hotel_checkin', 'Pet Hotel — Check-in'),
('pet_hotel_checkout','Pet Hotel — Check-out'),
('pet_konsultacija',  'Konzultacija (pet savjetovanje)'),
```

---

## KORAK 8 — Borg Advisor keywords update

READ: `registration/borg_advisor.py` (KEYWORD_PLAN_MAP)

DODAJ u 'professional':
```python
# Dresura i pet services
'kinolog', 'dresura', 'dresiranje', 'agility', 'obedijencija',
'pet hotel', 'pension za pse', 'čuvanje pasa', 'pet boarding',
'lovački pas', 'pas vodič', 'terapijski pas',
# Stočarstvo proširenje
'ovčar', 'ovce', 'koza', 'kozar', 'jagnje', 'janjetina',
'kozletina', 'svinjogojstvo', 'svinja', 'peradarstvo',
'kokoške', 'purica', 'konjički', 'uzgoj konja',
```

DODAJ u 'starter':
```python
'ovca', 'koza', 'janje', 'kozle',  # mali OPG s ovcama
```

---

## KORAK 9 — Admin registracija

READ: `memio_pet/admin.py`

DODAJ:
```python
@admin.register(DogTrainingSession)
class DogTrainingSessionAdmin(admin.ModelAdmin):
    list_display = ('animal', 'trainer', 'datum', 'tip', 'ocjena')
    list_filter  = ('tip', 'datum')
    ordering     = ('-datum',)

@admin.register(PetBoardingReservation)
class PetBoardingReservationAdmin(admin.ModelAdmin):
    list_display = ('animal', 'hotel', 'datum_in', 'datum_out', 'status', 'ukupna_cijena')
    list_filter  = ('status', 'datum_in')
    ordering     = ('-datum_in',)
```

---

## KORAK 10 — BARF + Ovce connector

READ: `memio_pet/models.py` (RawFoodListing.PRODUCT_CHOICES, ~linija 415-430)

DODAJ u PRODUCT_CHOICES (janjetina i srodne):
```python
('janjetina',    'Janjetina (ovca)'),
('kozletina',    'Kozletina (koza)'),
('svinjetina',   'Svinjetina / Ćufte'),
('iznutrice_ov', 'Iznutrice ovce/koze'),
('jaja',         'Jaja (kure, purice)'),
('riba_cjelovita','Riba cjelovita'),
('divljac',      'Divljač (srna, zec, vepar)'),
```

→ OPG s ovcama ili svinjama → barf_partner=True → prodaje u BARF marketplace
→ Pas vlasnik naručuje janjetinu direktno od OPG-a koji je 3km daleko
→ Krug zatvoren.

NEMA MIGRACIJE — CharField choices.

---

## KORAK 11 — Verifikacija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -3
venv/bin/python manage.py migrate 2>&1 | tail -5
venv/bin/python manage.py shell -c "
from memio_pet.models import DogTrainingSession, PetBoardingReservation, BreederProfile, AnimalProfile
from livestock.models import Livestock
print('DogTrainingSession:', DogTrainingSession.objects.count(), 'OK')
print('PetBoardingReservation:', PetBoardingReservation.objects.count(), 'OK')
print('Livestock ovca postoji:', 'ovca' in dict(Livestock.VRSTA_CHOICES))
print('BreederProfile trainer postoji:', 'trainer' in dict(BreederProfile.ACCOUNT_TYPE_CHOICES))
print('AnimalProfile ovca postoji:', 'ovca' in dict(AnimalProfile.VRSTA_CHOICES))
" 2>/dev/null

git add -A
git commit -m "feat(memio-pet): dresura, pet hotel, ovce/koze/svinje, BARF proširenje"
```

---

## DONE KRITERIJI:
- [ ] AnimalProfile: ovca, koza, svinja, ptica u choices
- [ ] Livestock: ovca, janje, koza, svinja u choices
- [ ] BreederProfile: trainer, hotel, sheep_farmer u account_type
- [ ] DogTrainingSession model + migracija
- [ ] PetBoardingReservation model + migracija
- [ ] Appointments: dresura + hotel tipovi dodani
- [ ] Borg Advisor: ovce/dresura/hotel keywords
- [ ] BARF: janjetina, kozletina, divljač u choices
- [ ] Admin registriran za oba nova modela
- [ ] manage.py check: 0 errora
- [ ] git commit čist

STATUS: PENDING — čeka CC Code
