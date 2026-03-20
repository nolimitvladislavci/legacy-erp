import uuid

from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from companies.models import Company
from core.managers import CompanyManager


class Partner(models.Model):
    TYPE_CHOICES = [
        ('client',   _('Klijent (Kupac)')),
        ('supplier', _('Dobavljač')),
        ('both',     _('Partner (Oboje)')),
        ('employee', _('Zaposlenik')),
        ('agent',    _('Prodajni agent / Tippgeber')),
    ]

    class Country(models.TextChoices):
        HR = 'HR', _('Hrvatska')
        DE = 'DE', _('Njemačka')
        AT = 'AT', _('Austrija')
        SI = 'SI', _('Slovenija')
        BA = 'BA', _('Bosna i Hercegovina')
        RS = 'RS', _('Srbija')
        IT = 'IT', _('Italija')
        HU = 'HU', _('Mađarska')
        OTHER = 'OTHER', _('Ostalo')

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='partners',
                                 verbose_name=_('Vlasnik podataka'))
    objects = CompanyManager()

    # Osnovni podaci
    name = models.CharField(max_length=200, verbose_name=_('Naziv / Ime'))
    oib  = models.CharField(max_length=13, blank=True, verbose_name=_('OIB / Steuer-Nr.'))

    # Lokacija
    address  = models.CharField(max_length=255, blank=True, verbose_name=_('Ulica i broj'))
    city     = models.CharField(max_length=100, blank=True, verbose_name=_('Grad'))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_('Poštanski broj'))
    country  = models.CharField(
        max_length=10,
        choices=Country.choices,
        default=Country.HR,
        verbose_name=_('Država'),
    )

    # Kontakt
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    web   = models.URLField(blank=True, verbose_name=_('Web stranica'))

    # Kontakt osoba
    contact_person = models.CharField(max_length=200, blank=True, verbose_name=_('Kontakt osoba'))
    contact_phone  = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon kontakt osobe'))
    contact_email  = models.EmailField(blank=True, verbose_name=_('Email kontakt osobe'))

    # Bankovni podaci
    iban  = models.CharField(max_length=34, blank=True, verbose_name='IBAN')
    swift = models.CharField(max_length=11, blank=True, verbose_name='SWIFT / BIC')

    # PDV
    is_vat_registered = models.BooleanField(default=False, verbose_name=_('U sustavu PDV-a'))
    vat_id = models.CharField(
        max_length=20, blank=True,
        verbose_name=_('PDV ID / VAT ID'),
        help_text=_('EU PDV identifikacijski broj (npr. HR12345678901)'),
    )

    # Komercijalni uvjeti
    partner_type   = models.CharField(max_length=10, choices=TYPE_CHOICES, default='client',
                                       verbose_name=_('Tip partnera'))
    payment_term   = models.IntegerField(default=0, verbose_name=_('Rok plaćanja (dana)'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                                            verbose_name=_('Rabat (%)'))
    credit_limit   = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                          verbose_name=_('Kreditni limit'))

    # Sistem
    notes     = models.TextField(blank=True, verbose_name=_('Interne napomene'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    portal_token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # AUTOMATIZACIJA (ne dira se ručno)
    cached_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,
                                          verbose_name=_('Saldo'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    nkd_code = models.ForeignKey(
        'companies.NKDCode',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='NKD djelatnost',
    )

    class Meta:
        unique_together = ('company', 'oib')
        verbose_name = _('Partner')
        verbose_name_plural = _('Partneri')
        ordering = ['name']


    @property
    def is_complete(self):
        return bool(self.name and self.oib and self.address and self.city and self.email)

    @property
    def missing_fields(self):
        missing = []
        if not self.oib: missing.append("OIB")
        if not self.address: missing.append("Adresa")
        if not self.city: missing.append("Grad")
        if not self.email: missing.append("Email")
        if not self.phone: missing.append("Telefon")
        return missing
    def __str__(self):
        return f"{self.name} ({self.city or 'N/A'})"

    def update_balance(self):
        inflow  = self.transactions.filter(direction='income').aggregate(Sum('amount'))['amount__sum'] or 0
        outflow = self.transactions.filter(direction='expense').aggregate(Sum('amount'))['amount__sum'] or 0
        self.cached_balance = inflow - outflow
        self.save(update_fields=['cached_balance'])


class AgentReferral(models.Model):
    """
    Veza: Agent (Tippgeber) → preporučeni korisnik → pretplata → provizija.
    Prati tko je koga doveo, koliko zarađuje, i kad je isplaćeno.
    """
    STATUS_CHOICES = [
        ('pending', _('Čeka aktivaciju')),
        ('active', _('Aktivan — provizija teče')),
        ('expired', _('Istekao (12 mj)')),
        ('cancelled', _('Otkazan')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Partner, on_delete=models.CASCADE,
        related_name='referrals', verbose_name=_('Agent'),
        limit_choices_to={'partner_type': 'agent'},
    )
    referred_company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        related_name='referred_by', verbose_name=_('Preporučena tvrtka'),
    )
    referral_code = models.CharField(
        max_length=30, unique=True, verbose_name=_('Referral kod'),
        help_text=_('Jedinstveni kod za praćenje (npr. REF-ANTONIO-001)'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # Provizija
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=20,
        verbose_name=_('Provizija (%)'),
    )
    commission_months = models.PositiveSmallIntegerField(
        default=12, verbose_name=_('Trajanje provizije (mjeseci)'),
    )
    total_earned = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Ukupno zarađeno (EUR)'),
    )
    total_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Ukupno isplaćeno (EUR)'),
    )

    # Ugovor
    contract_signed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Ugovor potpisan'),
    )
    contract_ip = models.GenericIPAddressField(null=True, blank=True)
    contract_user_agent = models.CharField(max_length=200, blank=True)

    # IBAN za isplatu
    agent_iban = models.CharField(max_length=34, blank=True, verbose_name=_('IBAN agenta'))

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Istječe'))

    class Meta:
        verbose_name = _('Agent Referral')
        verbose_name_plural = _('Agent Referrals')
        ordering = ['-created_at']

    def __str__(self):
        return '%s → %s (%s)' % (self.agent.name, self.referred_company.name, self.status)

    @property
    def balance_due(self):
        """Neisplaćeni saldo."""
        return self.total_earned - self.total_paid


class AgentPayout(models.Model):
    """Mjesečna isplata provizije agentu — audit trail."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Partner, on_delete=models.CASCADE,
        related_name='payouts', verbose_name=_('Agent'),
    )
    period_month = models.PositiveSmallIntegerField(verbose_name=_('Mjesec'))
    period_year = models.PositiveSmallIntegerField(verbose_name=_('Godina'))
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Iznos (EUR)'))
    referrals_count = models.PositiveSmallIntegerField(default=0, verbose_name=_('Broj referrala'))

    # Detalji
    breakdown = models.JSONField(default=list, verbose_name=_('Razrada po klijentima'))
    iban = models.CharField(max_length=34, verbose_name=_('IBAN za isplatu'))

    status = models.CharField(max_length=15, choices=[
        ('calculated', _('Izračunato')),
        ('approved', _('Odobreno')),
        ('paid', _('Isplaćeno')),
    ], default='calculated')

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Agent isplata')
        verbose_name_plural = _('Agent isplate')
        unique_together = [('agent', 'period_month', 'period_year')]
        ordering = ['-period_year', '-period_month']

    def __str__(self):
        return '%s — %02d/%d — %s EUR' % (self.agent.name, self.period_month, self.period_year, self.amount)
