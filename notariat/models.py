"""
notariat/models.py
Bilježnik + Odvjetnik + Dimnjačar — zajednički modeli
"""
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class NotariatPredlozak(models.Model):
    """Katalog dostupnih predložaka po firmi."""
    VRSTE = [
        ('punomoc',          'Opunomoćenje (punomoć)'),
        ('osnivanje_jdoo',   'Osnivački akt j.d.o.o.'),
        ('osnivanje_doo',    'Osnivački akt d.o.o.'),
        ('kupoprodaja_nekr', 'Kupoprodaja nekretnine'),
        ('zaduznica',        'Zadužnica'),
        ('bjanko_zaduznica', 'Bjanko zadužnica'),
        ('darovanje',        'Ugovor o darovanju'),
        ('maloljetnik_put',  'Suglasnost za putovanje maloljetnika'),
        ('nasljedstvo',      'Izjava o prihvatu nasljedstva'),
        ('dozivotno_uzdrz',  'Ugovor o doživotnom uzdržavanju'),
        ('potvrda_dimnjak',  'Potvrda o ispravnosti dimnjaka'),
        ('nalaz_dimnjak',    'Nalaz i mišljenje dimnjačara'),
        ('plan_obilasku',    'Godišnji plan obilazaka'),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Firma'),
    )
    vrsta   = models.CharField(max_length=30, choices=VRSTE, verbose_name=_('Vrsta'))
    naslov  = models.CharField(max_length=200, verbose_name=_('Naslov'))
    aktivan = models.BooleanField(default=True, verbose_name=_('Aktivan'))

    objects = CompanyManager()

    class Meta:
        unique_together = ['company', 'vrsta']
        verbose_name = 'Notariat predložak'
        verbose_name_plural = 'Notariat predlošci'

    def __str__(self):
        return f"{self.get_vrsta_display()} — {self.company}"


class PravniPredmet(models.Model):
    """Odvjetnički predmet / dosje klijenta."""
    VRSTE = [
        ('parnica',    'Parnični postupak'),
        ('ovrha',      'Ovršni postupak'),
        ('ugovor',     'Izrada ugovora'),
        ('savjet',     'Pravni savjet'),
        ('nekretnina', 'Promet nekretnina'),
        ('osnivanje',  'Osnivanje d.o.o./obrta'),
        ('ostalo',     'Ostalo'),
    ]
    STATUS = [
        ('aktivan',  'Aktivan'),
        ('zatvoren', 'Zatvoren'),
        ('arhiva',   'Arhiva'),
    ]
    company         = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Firma'),
    )
    klijent         = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Klijent'),
    )
    naziv           = models.CharField(max_length=300, verbose_name=_('Naziv predmeta'))
    vrsta           = models.CharField(max_length=20, choices=VRSTE, verbose_name=_('Vrsta'))
    status          = models.CharField(max_length=20, choices=STATUS, default='aktivan', verbose_name=_('Status'))
    satnica_eur     = models.DecimalField(max_digits=8, decimal_places=2, default=100.00, verbose_name=_('Satnica (EUR)'))
    datum_otvaranja = models.DateField(auto_now_add=True, verbose_name=_('Datum otvaranja'))
    rok             = models.DateField(null=True, blank=True, verbose_name=_('Rok'))
    napomena        = models.TextField(blank=True, verbose_name=_('Napomena'))

    objects = CompanyManager()

    class Meta:
        ordering = ['-datum_otvaranja']
        verbose_name = 'Pravni predmet'
        verbose_name_plural = 'Pravni predmeti'

    def __str__(self):
        return f"{self.naziv} ({self.get_vrsta_display()})"


class DimnjacarskaInspekcija(models.Model):
    """
    Evidencija dimnjačarskog pregleda.
    Zakonska osnova: Zakon o obavljanju dimnjačarskih poslova (NN 103/15)
    """
    STATUS = [
        ('ispravan',   'Ispravan — dimnjak u redu'),
        ('uvjetno',    'Uvjetno ispravan — potrebni popravci'),
        ('neispravan', 'Neispravan — zabrana korištenja'),
    ]
    company          = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Firma'),
    )
    klijent          = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Klijent / Vlasnik'),
    )
    adresa           = models.CharField(max_length=300, verbose_name=_('Adresa objekta'))
    kat_cestica      = models.CharField(max_length=50, blank=True, verbose_name=_('Katastarska čestica'))
    broj_dimnjaka    = models.CharField(max_length=30, verbose_name=_('Broj / oznaka dimnjaka'))
    vrsta_goriva     = models.CharField(max_length=100, blank=True, verbose_name=_('Vrsta goriva'))
    datum_pregleda   = models.DateField(verbose_name=_('Datum pregleda'))
    status_dimnjaka  = models.CharField(max_length=20, choices=STATUS, verbose_name=_('Status dimnjaka'))
    opis_nalaza      = models.TextField(blank=True, verbose_name=_('Opis nalaza'))
    preporuke        = models.TextField(blank=True, verbose_name=_('Preporuke'))
    sljedeci_pregled = models.DateField(null=True, blank=True, verbose_name=_('Sljedeći pregled'))
    pdf_sha256       = models.CharField(max_length=64, blank=True, verbose_name=_('SHA-256 potvrde'))

    objects = CompanyManager()

    class Meta:
        ordering = ['-datum_pregleda']
        verbose_name = 'Dimnjačarska inspekcija'
        verbose_name_plural = 'Dimnjačarske inspekcije'

    def __str__(self):
        return f"{self.adresa} — {self.datum_pregleda} ({self.get_status_dimnjaka_display()})"
