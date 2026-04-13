"""
intelligence/models.py
Fenix Intelligence -- autonomni istrazivacki agent.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import CompanyManager


class IntelligenceSource(models.Model):
    """Izvor podataka -- sto autonomni agent prati."""

    TIP_CHOICES = [
        ('eu_fond', 'EU fond natjecaj (eKohezija)'),
        ('hr_poticaj', 'HR poticaj (APPRRR, ARR, HAPIH)'),
        ('trzisna_cijena', 'Trzisna cijena (TISUP, Agroklub)'),
        ('vijest', 'Agro vijest / objava'),
        ('natjecaj_opg', 'Natjecaj za OPG'),
        ('natjecaj_udruga', 'Natjecaj za udruge'),
        ('bio_certifikacija', 'Bio certifikacija novosti'),
    ]

    naziv = models.CharField(max_length=100)
    tip = models.CharField(max_length=25, choices=TIP_CHOICES)
    url = models.URLField(verbose_name='URL izvora',
                          help_text='Npr. https://www.apprrr.hr/natjecaji/')
    xpath_ili_opis = models.TextField(blank=True,
                                      verbose_name='XPath/CSS selektor ili opis za AI',
                                      help_text='AI cita i razumije -- moze biti slobodan opis')
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
    """Konfiguracija pracenja za jednu kompaniju."""

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='intelligence_jobs'
    )
    sources = models.ManyToManyField(IntelligenceSource, blank=True,
                                     verbose_name='Praceni izvori')
    aktivan = models.BooleanField(default=True)

    opis_poslovanja = models.TextField(blank=True,
                                       verbose_name='Opis poslovanja (za AI matching)',
                                       help_text='Sto firma radi, koje su joj potrebe, ciljevi')
    kljucne_rijeci = models.JSONField(default=list, blank=True,
                                      verbose_name='Kljucne rijeci',
                                      help_text='["govedo", "sir", "bio", "kukuruz"]')
    min_fond_iznos_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True,
                                              verbose_name='Min. iznos fonda (EUR)')
    max_fond_iznos_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True,
                                              verbose_name='Max. iznos fonda (EUR)')

    obavijesti_whatsapp = models.BooleanField(default=True,
                                               verbose_name='Salji na WhatsApp')
    whatsapp_broj = models.CharField(max_length=20, blank=True,
                                      verbose_name='WhatsApp broj (ako ne korisnik)')
    obavijesti_email = models.BooleanField(default=False)

    zadnji_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        db_table = 'intelligence_job'
        verbose_name = 'Intelligence job'
        verbose_name_plural = 'Intelligence jobs'

    def __str__(self):
        return f'Job: {self.company.name}'


class IntelligenceResult(models.Model):
    """Rezultat jednog ciklusa pretrage za jednu kompaniju."""

    STATUS_CHOICES = [
        ('novo', 'Novo -- ceka objavu'),
        ('obavljeno', 'Objavljeno korisniku'),
        ('odbaceno', 'Odbaceno (nije relevantno)'),
    ]

    job = models.ForeignKey(IntelligenceJob, on_delete=models.CASCADE,
                             related_name='results')
    source = models.ForeignKey(IntelligenceSource, on_delete=models.SET_NULL,
                                null=True, blank=True)

    naslov = models.CharField(max_length=300, verbose_name='Naslov pronalaska')
    summary = models.TextField(verbose_name='AI sazetak')
    url = models.URLField(blank=True, verbose_name='Izvorni URL')
    ai_relevantnost = models.SmallIntegerField(default=0,
                                                verbose_name='AI relevantnost (0-100)')
    promo_tekst = models.TextField(blank=True,
                                    verbose_name='AI generirani promo materijal')

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='novo')
    obavljeno_at = models.DateTimeField(null=True, blank=True)

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
        return f'{self.naslov[:60]} -- {self.job.company.name} ({self.ai_relevantnost}%)'


class FundOpportunity(models.Model):
    """EU fond ili HR poticaj -- konkretni natjecaj."""

    TIP_CHOICES = [
        ('eu_esf', 'EU ESF+ (socijalni fond)'),
        ('eu_erdf', 'EU ERDF (regionalni razvoj)'),
        ('eu_eafrd', 'EU EAFRD (ruralni razvoj / Intervencijski plan)'),
        ('hr_apprrr', 'HR APPRRR (Agencija za placanja)'),
        ('hr_arr', 'HR ARR (Agencija za regionalni razvoj)'),
        ('hr_hapih', 'HR HAPIH (fitosanitarni poticaji)'),
        ('hr_minpol', 'HR MINPOL (Ministarstvo poljoprivrede)'),
        ('hr_ostalo', 'HR ostalo'),
    ]
    STATUS_CHOICES = [
        ('aktivan', 'Aktivan natjecaj'),
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

    naziv = models.CharField(max_length=300, verbose_name='Naziv natjecaja')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivan')
    ciljna_skupina = models.CharField(max_length=10, choices=CILJNA_SKUPINA, default='svi')

    tijelo = models.CharField(max_length=200, verbose_name='Tijelo (npr. APPRRR, SAFU)')
    opis = models.TextField(verbose_name='Opis natjecaja')
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

    ai_summary = models.TextField(blank=True, verbose_name='AI sazetak (kratko)')
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
        return f'{self.naziv} ({self.get_tip_display()}) -- rok: {self.rok_prijave}'

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
    """Prijava firme na fond/natjecaj -- pracenje statusa."""

    STATUS_CHOICES = [
        ('priprema', 'Priprema dokumentacije'),
        ('predan', 'Predan'),
        ('evaluacija', 'U evaluaciji'),
        ('odobren', 'Odobren'),
        ('odbijen', 'Odbijen'),
        ('u_provedbi', 'U provedbi'),
        ('zatvoren', 'Zatvoren / Zavrsen'),
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

    dokumenti_checklist = models.JSONField(default=list, blank=True)
    biljeske = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        db_table = 'intelligence_fund_application'
        ordering = ['-created_at']
        unique_together = [('company', 'opportunity')]
        verbose_name = 'Prijava na fond'
        verbose_name_plural = 'Prijave na fondove'

    def __str__(self):
        return f'{self.company.name} -> {self.opportunity.naziv[:50]} [{self.get_status_display()}]'
