"""
memio_farm/models.py — Digitalni identitet farmskih životinja

Filozofija: Ista infrastruktura kao memio.pet, drugi vizualni identitet.
Most prema livestock/ modulu i prema memio_pet.AnimalProfile.

Baza: memio_farm (odvojena od memio_pets)
"""
import uuid

from django.db import models


class FarmProfile(models.Model):
    """
    OPG / Farma — vlasnik životinja na memio.farm.
    Analogno BreederProfile na memio.pet.
    """
    FARM_TYPES = [
        ('opg',          '🌿 OPG'),
        ('govedarstvo',  '🐄 Govedarstvo'),
        ('ovcarstvo',    '🐑 Ovčarstvo / Kozarstvo'),
        ('svinjogojstvo','🐷 Svinjogojstvo'),
        ('peradarstvo',  '🐔 Peradarstvo'),
        ('konjogojstvo', '🐎 Konjogojstvo'),
        ('pcelarstvo',   '🍯 Pčelarstvo'),
        ('misovito',     '🌾 Mješovita farma'),
        ('rescue',       '🏠 Rescue / Azil za farmske životinje'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200, verbose_name='Naziv farme / OPG-a')
    farm_type   = models.CharField(max_length=20, choices=FARM_TYPES, default='opg')
    oib         = models.CharField(max_length=11, blank=True, verbose_name='OIB')
    mibpg       = models.CharField(max_length=20, blank=True,
                                    verbose_name='MIBPG (Matični identifikacijski broj poljoprivrednog gospodarstva)')
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=20, blank=True)
    website     = models.URLField(blank=True)
    city        = models.CharField(max_length=100, blank=True)
    county      = models.CharField(max_length=100, blank=True, verbose_name='Županija')
    country     = models.CharField(max_length=2, default='HR')
    # Veza na LIMIT Connect company (ako je klijent)
    limit_company_id = models.UUIDField(null=True, blank=True,
                                         verbose_name='LIMIT Connect company ID')
    # Verifikacija
    is_agronet_verified = models.BooleanField(default=False,
                                               verbose_name='Verificiran u AGRONET-u')
    trust_score  = models.PositiveSmallIntegerField(default=40)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_farm'
        db_table  = 'mf_farm_profile'
        verbose_name = 'Farma / OPG'

    def __str__(self):
        return f'{self.name} ({self.get_farm_type_display()})'


class FarmAnimal(models.Model):
    """
    Farmska životinja s digitalnim identitetom.
    Odvojen model od memio_pet.AnimalProfile —
    farmski kontekst (markice, produktivnost, stado) je drugačiji.
    """
    VRSTA = [
        ('krava',    '🐄 Krava / Govedo'),
        ('konj',     '🐎 Konj'),
        ('ovca',     '🐑 Ovca'),
        ('koza',     '🐐 Koza'),
        ('svinja',   '🐷 Svinja'),
        ('kokoska',  '🐔 Kokoška / Perad'),
        ('zec',      '🐇 Kunić / Zec'),
        ('ostalo',   '🐾 Ostalo'),
    ]
    SPOL = [('M','Mužjak'), ('F','Ženka'), ('N','Nepoznato')]
    STATUS = [
        ('aktivno',    'Aktivno'),
        ('gravidno',   'Gravidno'),
        ('tov',        'U tovu'),
        ('prodano',    'Prodano'),
        ('uginulo',    'Uginulo'),
        ('izluceno',   'Izlučeno iz stada'),
        ('u_miru',     'U mirovini'),   # stara radna konja npr.
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm        = models.ForeignKey(FarmProfile, on_delete=models.CASCADE,
                                    related_name='animals')
    # Identifikatori (EU obaveza)
    ear_tag     = models.CharField(max_length=20, db_index=True,
                                    verbose_name='Broj ušne markice',
                                    help_text='HR format npr. HR123456789')
    chip_number = models.CharField(max_length=20, blank=True, db_index=True,
                                    verbose_name='Broj mikročipa')
    passport_number = models.CharField(max_length=50, blank=True,
                                        verbose_name='Broj pasoša (za konje)')
    # Podaci
    name        = models.CharField(max_length=100, blank=True,
                                    verbose_name='Ime (opcionalno)')
    vrsta       = models.CharField(max_length=20, choices=VRSTA, default='krava')
    breed       = models.CharField(max_length=100, blank=True, verbose_name='Pasmina')
    spol        = models.CharField(max_length=1, choices=SPOL, default='N')
    date_of_birth = models.DateField(null=True, blank=True)
    weight_kg   = models.DecimalField(max_digits=7, decimal_places=1,
                                       null=True, blank=True)
    photo       = models.ImageField(upload_to='memio_farm/photos/', null=True, blank=True)
    status      = models.CharField(max_length=15, choices=STATUS, default='aktivno')
    notes       = models.TextField(blank=True)
    # Veza na memio_pet (ako rescuiran ili prebačen)
    memio_pet_profile_id = models.UUIDField(null=True, blank=True,
                                             verbose_name='memio.pet profil ID')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_farm'
        db_table  = 'mf_farm_animal'
        ordering  = ['ear_tag']

    def __str__(self):
        return f'{self.name or self.ear_tag} ({self.get_vrsta_display()})'

    @property
    def display_id(self):
        return self.ear_tag or self.chip_number or str(self.id)[:8]


class AnimalCustody(models.Model):
    """
    Skrbništvo životinje — dijeljeno, privremeno, terapijsko.
    Jedinstven model koji ne postoji nigdje u HR.
    """
    CUSTODY_TYPES = [
        ('permanent',  '🏠 Stalni vlasnik'),
        ('foster',     '💛 Udomiteljska obitelj'),
        ('shared',     '🔄 Dijeljeno skrbništvo (vikend)'),
        ('riding',     '🐎 Jahač / korisnik'),
        ('therapy',    '💙 Terapijski program'),
        ('training',   '🎓 Dresura / trening'),
        ('breeding',   '🌿 Razplodna posudba'),
        ('temporary',  '⏰ Privremeni čuvar'),
        ('researcher', '🔬 Istraživač / student'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Može biti farm animal ILI memio.pet animal (UUID)
    farm_animal    = models.ForeignKey(FarmAnimal, null=True, blank=True,
                                        on_delete=models.CASCADE,
                                        related_name='custodies')
    memio_pet_chip = models.CharField(max_length=20, blank=True,
                                       verbose_name='memio.pet čip (za ljubimce)')
    # Skrbnik
    custodian_name  = models.CharField(max_length=200)
    custodian_email = models.EmailField(blank=True)
    custodian_phone = models.CharField(max_length=20, blank=True)
    custody_type    = models.CharField(max_length=15, choices=CUSTODY_TYPES)
    # Raspored
    start_date      = models.DateField()
    end_date        = models.DateField(null=True, blank=True)  # null = aktivno
    schedule_note   = models.CharField(max_length=300, blank=True,
                                        verbose_name='Raspored',
                                        help_text='npr. "Svaki vikend Pet-Ned" ili "Utorkom 10-12h"')
    # Javno vidljivo?
    is_public       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_farm'
        db_table  = 'mf_animal_custody'

    def __str__(self):
        animal = self.farm_animal or f'memio.pet:{self.memio_pet_chip}'
        return f'{self.get_custody_type_display()} — {animal} / {self.custodian_name}'

    @property
    def is_active(self):
        from django.utils import timezone
        if self.end_date is None:
            return True
        return self.end_date >= timezone.now().date()


class Beehive(models.Model):
    """
    Košnica — poseban slučaj. Ne prati se individua nego košnica.
    EU Uredba 2016/429 — registracija pčelinjaka obavezna.
    """
    STATUS = [
        ('aktivna',   'Aktivna'),
        ('zimovanje', 'Zimovanje'),
        ('roj_izgubljen', 'Roj izgubljen'),
        ('neaktivna', 'Neaktivna'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm            = models.ForeignKey(FarmProfile, on_delete=models.CASCADE,
                                         related_name='beehives')
    hive_number     = models.CharField(max_length=20, verbose_name='Broj košnice',
                                        db_index=True)
    location_name   = models.CharField(max_length=200, blank=True,
                                        verbose_name='Lokacija pčelinjaka')
    queen_year      = models.PositiveSmallIntegerField(null=True, blank=True,
                                                        verbose_name='Godina matice')
    bee_race        = models.CharField(max_length=100, blank=True,
                                        verbose_name='Soj pčela',
                                        help_text='npr. Carnica, Buckfast, Krajinska')
    status          = models.CharField(max_length=20, choices=STATUS, default='aktivna')
    agronet_id      = models.CharField(max_length=50, blank=True,
                                        verbose_name='AGRONET ID pčelinjaka')
    last_inspection = models.DateField(null=True, blank=True,
                                        verbose_name='Zadnji pregled')
    honey_yield_kg  = models.DecimalField(max_digits=7, decimal_places=1,
                                           null=True, blank=True,
                                           verbose_name='Prinos meda (kg/god)')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_farm'
        db_table  = 'mf_beehive'
        ordering  = ['hive_number']

    def __str__(self):
        return f'Košnica {self.hive_number} — {self.farm.name}'
