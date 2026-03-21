"""
livestock/models.py
Evidencija goveda za OPG. Prati: grlo, zdravlje, mlijeko,
plan ishrane, parcele, usjeve i put prema bio certifikaciji.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Livestock(models.Model):
    """Jedno grlo -- krava, junica, tele, bik."""

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
        ('zasuseno', 'Zasuseno'),
        ('tov', 'U tovu'),
        ('prodano', 'Prodano'),
        ('uginulo', 'Uginulo'),
        ('izluceno', 'Izluceno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='livestock', verbose_name='OPG'
    )
    ear_tag = models.CharField(max_length=20, verbose_name='Broj usne markice',
                                help_text='HR format: HR + OIB + redni br',
                                db_index=True)
    name = models.CharField(max_length=50, blank=True, verbose_name='Ime (opcionalno)')
    vrsta = models.CharField(max_length=15, choices=VRSTA_CHOICES, default='krava')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivno')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Datum rodjenja')
    breed = models.CharField(max_length=50, blank=True, verbose_name='Pasmina',
                              help_text='npr. Simentalac, Holstein, Siva')
    weight_kg = models.DecimalField(max_digits=7, decimal_places=1,
                                     null=True, blank=True, verbose_name='Tezina (kg)')
    avg_daily_milk_l = models.DecimalField(max_digits=6, decimal_places=2,
                                            null=True, blank=True,
                                            verbose_name='Prosj. dnevna mlijecnost (L)')
    last_calving = models.DateField(null=True, blank=True, verbose_name='Zadnje teljenje')
    expected_calving = models.DateField(null=True, blank=True, verbose_name='Ocekivano teljenje')
    is_organic = models.BooleanField(default=False, verbose_name='Ekoloski uzgoj')
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
        return f'{self.ear_tag} -- {self.get_vrsta_display()} ({self.get_status_display()})'

    @property
    def age_months(self):
        if not self.date_of_birth:
            return None
        delta = timezone.now().date() - self.date_of_birth
        return delta.days // 30

    @property
    def is_in_karencija(self):
        """True ako grlo ima aktivnu karenciju — zabrana prodaje mlijeka/mesa."""
        today = timezone.now().date()
        return self.health_records.filter(
            karencija_do__gte=today
        ).exists()

    @property
    def karencija_end(self):
        """Datum isteka karencije (najkasniji)."""
        today = timezone.now().date()
        rec = self.health_records.filter(
            karencija_do__gte=today
        ).order_by('-karencija_do').first()
        return rec.karencija_do if rec else None

    @property
    def karencija_reason(self):
        """Razlog karencije (zadnji tretman)."""
        today = timezone.now().date()
        rec = self.health_records.filter(
            karencija_do__gte=today
        ).order_by('-karencija_do').first()
        return '%s (%s)' % (rec.lijek, rec.opis) if rec else ''

    @property
    def calving_soon(self):
        if not self.expected_calving:
            return False
        return (self.expected_calving - timezone.now().date()).days <= 21


class HealthRecord(models.Model):
    """Veterinarski zapis -- cjepiva, bolesti, tretmani."""

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
    kolicina = models.CharField(max_length=50, blank=True, verbose_name='Kolicina doze')
    karencija_do = models.DateField(null=True, blank=True,
                                     verbose_name='Karencija do (zabrana mlijeka/mesa)')
    trosak_eur = models.DecimalField(max_digits=8, decimal_places=2,
                                      null=True, blank=True, verbose_name='Trosak (EUR)')
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
        return f'{self.animal.ear_tag} -- {self.get_tip_display()} ({self.datum})'

    @property
    def u_karenciji(self):
        if not self.karencija_do:
            return False
        return self.karencija_do >= timezone.now().date()


class MilkRecord(models.Model):
    """Dnevna evidencija mlijecnosti -- kontrolni muzni list."""

    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE,
                                related_name='milk_records')
    datum = models.DateField()
    jutarnja_l = models.DecimalField(max_digits=6, decimal_places=2,
                                      default=0, verbose_name='Jutarnja muza (L)')
    vecernja_l = models.DecimalField(max_digits=6, decimal_places=2,
                                      default=0, verbose_name='Vecernja muza (L)')
    ukupno_l = models.DecimalField(max_digits=6, decimal_places=2,
                                    default=0, editable=False)
    masnoca_posto = models.DecimalField(max_digits=4, decimal_places=2,
                                         null=True, blank=True, verbose_name='Masnoca (%)')
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
        self.ukupno_l = self.jutarnja_l + self.vecernja_l
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.animal.ear_tag} -- {self.datum}: {self.ukupno_l}L'


class Field(models.Model):
    """Parcela -- katastarska cestica ili radna jedinica."""

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='fields')
    naziv = models.CharField(max_length=100, verbose_name='Naziv parcele')
    katastarska_cestica = models.CharField(max_length=50, blank=True,
                                            verbose_name='Katastarska cestica')
    povrsina_ha = models.DecimalField(max_digits=8, decimal_places=4,
                                       verbose_name='Povrsina (ha)')
    tip_tla = models.CharField(max_length=50, blank=True,
                                verbose_name='Tip tla',
                                help_text='npr. ilovaca, pjeskovita ilovaca, cernozem')
    ph_tla = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                  verbose_name='pH tla')
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_organic = models.BooleanField(default=False, verbose_name='Ekoloska parcela')
    arkod_id = models.CharField(max_length=50, blank=True, verbose_name='ARKOD ID',
                                 help_text='Potreban za APPRRR poticaje')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_field'
        ordering = ['naziv']
        verbose_name = 'Parcela'
        verbose_name_plural = 'Parcele'

    def __str__(self):
        return f'{self.naziv} ({self.povrsina_ha} ha) -- {self.company.name}'


class CropPlan(models.Model):
    """Plan sjetve i zetve po parceli i godini."""

    STATUS_CHOICES = [
        ('plan', 'U planu'),
        ('posijano', 'Posijano'),
        ('raste', 'Raste'),
        ('berba', 'U berbi'),
        ('zavrseno', 'Zavrseno'),
        ('propalo', 'Propalo'),
    ]
    KULTURA_CHOICES = [
        ('kukuruz', 'Kukuruz (zrno)'),
        ('kukuruz_silaza', 'Kukuruz (silaza)'),
        ('djetelina', 'Djetelina'),
        ('livada', 'Livada / Trava'),
        ('psenica', 'Psenica'),
        ('jecam', 'Jecam'),
        ('soja', 'Soja'),
        ('secerna_repa', 'Secerna repa'),
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

    datum_sjetve = models.DateField(null=True, blank=True, verbose_name='Planirani datum sjetve')
    datum_berbe = models.DateField(null=True, blank=True, verbose_name='Planirani datum berbe')
    stvarni_datum_berbe = models.DateField(null=True, blank=True)

    planrani_prinos_t_ha = models.DecimalField(max_digits=6, decimal_places=2,
                                                null=True, blank=True,
                                                verbose_name='Planirani prinos (t/ha)')
    stvarni_prinos_t = models.DecimalField(max_digits=8, decimal_places=2,
                                            null=True, blank=True,
                                            verbose_name='Stvarni prinos (t)')

    za_vlastite_potrebe = models.BooleanField(default=True,
                                               verbose_name='Za vlastite potrebe (stoka)')
    za_prodaju = models.BooleanField(default=False, verbose_name='Za prodaju')
    procijenjeni_visak_t = models.DecimalField(max_digits=8, decimal_places=2,
                                                null=True, blank=True,
                                                verbose_name='Procijenjeni visak za prodaju (t)')

    is_organic = models.BooleanField(default=False)
    gnojidba_opis = models.CharField(max_length=255, blank=True,
                                      verbose_name='Gnojidba (sredstvo, kolicina)')
    zastita_opis = models.CharField(max_length=255, blank=True,
                                     verbose_name='Zastita bilja (sredstvo)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'livestock_crop_plan'
        ordering = ['-godina', 'kultura']
        verbose_name = 'Plan sjetve'
        verbose_name_plural = 'Planovi sjetve'

    def __str__(self):
        return f'{self.get_kultura_display()} {self.godina} -- {self.company.name}'

    @property
    def auto_listing_ready(self):
        """True ako ima procijenjeni visak i berba je u tijeku ili zavrsena."""
        return (
            self.za_prodaju and
            self.procijenjeni_visak_t and
            self.procijenjeni_visak_t > 0 and
            self.status in ('berba', 'zavrseno')
        )
