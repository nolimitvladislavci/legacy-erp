"""
AML — Anti-Money Laundering / Dubinska analiza klijenta.
Zakon o sprjecavanju pranja novca i financiranja terorizma (NN 108/17).
"""
from django.db import models
from django.conf import settings


class AMLRiskCategory(models.Model):
    """Kategorija rizika."""
    RISK_LEVELS = [
        ('low', 'Nizak'),
        ('medium', 'Srednji'),
        ('high', 'Visok'),
        ('very_high', 'Vrlo visok'),
    ]
    name = models.CharField(max_length=100)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Kategorija rizika'
        verbose_name_plural = 'Kategorije rizika'

    def __str__(self):
        return f'{self.name} ({self.get_risk_level_display()})'


class AMLClientProfile(models.Model):
    """Profil dubinske analize klijenta."""
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('active', 'Aktivno'),
        ('review_needed', 'Potreban pregled'),
        ('expired', 'Isteklo'),
        ('archived', 'Arhivirano'),
    ]
    CLIENT_TYPE_CHOICES = [
        ('fizicka', 'Fizicka osoba'),
        ('pravna', 'Pravna osoba'),
    ]
    RISK_CHOICES = [
        ('low', 'Nizak'),
        ('medium', 'Srednji'),
        ('high', 'Visok'),
        ('very_high', 'Vrlo visok'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='aml_profiles')
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name='aml_assessments')
    assessment_date = models.DateField()
    next_review_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Identifikacija
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPE_CHOICES, default='pravna')
    legal_form = models.CharField(max_length=50, blank=True,
        help_text='d.o.o., j.d.o.o., obrt, udruga, itd.')
    ownership_structure = models.TextField(blank=True,
        verbose_name='Vlasnička struktura')
    beneficial_owners = models.TextField(blank=True,
        verbose_name='Krajnji korisnici (stvarni vlasnici)')

    # Rizik
    risk_categories = models.ManyToManyField(AMLRiskCategory, blank=True)
    overall_risk = models.CharField(max_length=20, choices=RISK_CHOICES, default='low')
    risk_score = models.IntegerField(default=0,
        help_text='0-100, automatski izracunat ili rucni')

    # Provjere
    id_verified = models.BooleanField(default=False,
        verbose_name='Osobna iskaznica provjerena')
    registry_checked = models.BooleanField(default=False,
        verbose_name='Sudski registar provjeren')
    pep_check = models.BooleanField(default=False,
        verbose_name='PEP provjera (politicki eksponirane osobe)')
    sanctions_check = models.BooleanField(default=False,
        verbose_name='Lista sankcija provjerena')
    adverse_media = models.BooleanField(default=False,
        verbose_name='Negativni medijski clanci provjereni')

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-assessment_date']
        verbose_name = 'AML profil klijenta'
        verbose_name_plural = 'AML profili klijenata'

    def __str__(self):
        return f'AML: {self.company.name} ({self.get_overall_risk_display()})'

    @property
    def is_expired(self):
        from datetime import date
        return self.next_review_date < date.today()

    @property
    def checks_completed(self):
        checks = [self.id_verified, self.registry_checked, self.pep_check,
                   self.sanctions_check, self.adverse_media]
        return sum(checks), len(checks)


class AMLTransaction(models.Model):
    """Sumnjiva transakcija."""
    STATUS_CHOICES = [
        ('detected', 'Detektirano'),
        ('under_review', 'U pregledu'),
        ('reported', 'Prijavljeno AMLA uredu'),
        ('cleared', 'Razrijeseno'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='aml_transactions')
    client_profile = models.ForeignKey(AMLClientProfile, on_delete=models.CASCADE,
                                        related_name='transactions', null=True, blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField()
    suspicion_reason = models.TextField(verbose_name='Razlog sumnje')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    reported_to_amla = models.BooleanField(default=False,
        verbose_name='Prijavljeno Uredu za sprecavanje pranja novca')
    report_date = models.DateField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True,
        verbose_name='AMLA referenca')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date']
        verbose_name = 'Sumnjiva transakcija'
        verbose_name_plural = 'Sumnjive transakcije'

    def __str__(self):
        return f'AML TX: {self.amount} EUR ({self.get_status_display()})'


class AMLDocument(models.Model):
    """Prilog uz AML profil."""
    DOC_TYPE_CHOICES = [
        ('osobna', 'Osobna iskaznica'),
        ('izvadak_sudski', 'Izvadak iz sudskog registra'),
        ('izvadak_oib', 'Izvadak iz OIB sustava'),
        ('potvrda_adrese', 'Potvrda adrese'),
        ('izjava_vlasnika', 'Izjava o stvarnom vlasniku'),
        ('ostalo', 'Ostalo'),
    ]

    profile = models.ForeignKey(AMLClientProfile, on_delete=models.CASCADE,
                                 related_name='documents')
    document_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='aml/documents/%Y/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'AML dokument'
        verbose_name_plural = 'AML dokumenti'

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.profile.company.name}'
