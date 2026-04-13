import uuid

from django.db import models, DatabaseError, IntegrityError
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from companies.models import Company
from django.core.exceptions import ObjectDoesNotExist
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

    # Tip kupca za eRačun routing (Zakon o fiskalizaciji NN 89/25)
    BUYER_TYPE_CHOICES = [
        ('b2c',      'Građanin (B2C) — fiskalni bon'),
        ('b2b_vat',  'Tvrtka / obrt u PDV-u — eRačun F2.0'),
        ('b2b_novat','Tvrtka / obrt NIJE u PDV-u — eRačun F2.0'),
        ('b2g',      'Proračunski korisnik (škola, općina...) — eRačun B2G'),
        ('udruga_vat',   'Udruga / neprofitna u PDV-u — eRačun'),
        ('udruga_novat', 'Udruga / neprofitna NIJE u PDV-u — obični račun'),
        ('inozemstvo',   'Inozemni kupac — obični račun (nije tuzemna transakcija)'),
    ]
    buyer_type = models.CharField(
        max_length=20,
        choices=BUYER_TYPE_CHOICES,
        default='b2c',
        verbose_name=_('Tip kupca (routing računa)'),
        help_text=_(
            'Određuje koji tip računa sustav automatski izdaje. '            'B2C=fiskalni bon, B2B PDV=eRačun, proračunski=eRačun B2G, '            'udruga bez PDV=obični PDF, inozemstvo=obični PDF.'
        ),
    )
    is_budget_user = models.BooleanField(
        default=False,
        verbose_name=_('Proračunski korisnik'),
        help_text=_('Škole, bolnice, općine, državna tijela. Uvijek primaju eRačun (B2G).'),
    )
    is_nonprofit_no_activity = models.BooleanField(
        default=False,
        verbose_name=_('Neprofitna bez gospodarske djel.'),
        help_text=_(
            'Udruge/zaklade koje ne obavljaju gospodarsku djelatnost i nisu u PDV-u. '            'Primaju obični PDF račun — bez obveze eRačuna po NN 89/25.'
        ),
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

    # VIES validacija
    vies_valid = models.BooleanField(null=True, default=None, verbose_name=_('VIES validan'))
    vies_checked_at = models.DateTimeField(null=True, blank=True, verbose_name=_('VIES provjera'))
    vies_name = models.CharField(max_length=255, blank=True, verbose_name=_('VIES naziv'))
    vies_address = models.CharField(max_length=500, blank=True, verbose_name=_('VIES adresa'))


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

    def get_invoice_routing(self) -> dict:
        """
        Određuje koji tip računa treba izdati za ovog partnera.
        Zakon o fiskalizaciji NN 89/25 — pravila routing-a:

        Vraća dict:
            route:        'eracun_f20' | 'eracun_b2g' | 'fiskalni_f10' | 'obicni_pdf'
            label:        Opis za UI
            needs_oib:    bool — treba li OIB u fiskalizacijskoj poruci
            can_be_cash:  bool — može li se platiti gotovinom/karticom
        """
        # Inozemstvo — nema obveze eRačuna
        if self.country not in ('HR', ''):
            return {
                'route': 'obicni_pdf',
                'label': 'Obični račun (inozemstvo — nije tuzemna transakcija)',
                'needs_oib': False,
                'can_be_cash': False,
            }

        # Proračunski korisnik — uvijek eRačun B2G
        if self.is_budget_user:
            return {
                'route': 'eracun_b2g',
                'label': 'eRačun B2G (škola, općina, državno tijelo)',
                'needs_oib': True,
                'can_be_cash': False,
            }

        # Udruga/neprofitna bez gospodarske djelatnosti i bez PDV-a
        if self.is_nonprofit_no_activity and not self.is_vat_registered:
            return {
                'route': 'obicni_pdf',
                'label': 'Obični PDF račun (udruga bez PDV-a i gospodarske djelatnosti)',
                'needs_oib': False,
                'can_be_cash': True,
            }

        # Fizička osoba / građanin — fiskalni bon F1.0
        if self.buyer_type == 'b2c':
            return {
                'route': 'fiskalni_f10',
                'label': 'Fiskalni bon F1.0 (građanin / krajnja potrošnja)',
                'needs_oib': False,
                'can_be_cash': True,
            }

        # B2B — tvrtka ili obrtnik (PDV ili ne) — eRačun F2.0
        # Iznimka čl.39 ZOF: gotovina/kartica do 700€ → može ići kao F1.0 s OIB-om
        if self.is_vat_registered:
            return {
                'route': 'eracun_f20',
                'label': 'eRačun F2.0 (tvrtka u PDV-u)',
                'needs_oib': True,
                'can_be_cash': True,   # iznimka čl.39 — gotovina/kartica do 700€
            }
        else:
            return {
                'route': 'eracun_f20',
                'label': 'eRačun F2.0 (tvrtka/obrtnik NIJE u PDV-u)',
                'needs_oib': True,
                'can_be_cash': True,   # iznimka čl.39 — gotovina/kartica do 700€
            }

    @property
    def invoice_route(self) -> str:
        """Kratki string za template: 'eracun_f20', 'fiskalni_f10', 'obicni_pdf', 'eracun_b2g'"""
        return self.get_invoice_routing()['route']

    @property
    def invoice_route_label(self) -> str:
        """Opis routing-a za prikaz u UI."""
        return self.get_invoice_routing()['label']

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
    objects = CompanyManager()

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


class WizardDraft(models.Model):
    """
    Perzistentni state za Ured u džepu onboarding wizard.
    Kreira se na koraku 0 (T&C prihvat), ažurira se na svakom "Dalje".
    """
    KAPITAL_CHOICES = [('jdoo', 'j.d.o.o.'), ('doo', 'd.o.o.')]

    session_key      = models.CharField(max_length=64, unique=True, db_index=True)
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    user_agent       = models.TextField(blank=True, default='')

    # Korak 0 — T&C / GDPR
    tc_accepted      = models.BooleanField(default=False)
    tc_accepted_at   = models.DateTimeField(null=True, blank=True)

    # Korak 1 — djelatnosti (NKD)
    nkd_codes_json   = models.JSONField(default=list, blank=True)

    # Korak 2 — ime firme
    firma_ime        = models.CharField(max_length=200, blank=True, default='')

    # Korak 3 — osnivači
    broj_osnivaca    = models.PositiveSmallIntegerField(default=1)
    direktor_ime     = models.CharField(max_length=200, blank=True, default='')
    direktor_oib     = models.CharField(max_length=11, blank=True, default='')
    direktor_email   = models.EmailField(blank=True, default='')

    # Korak 4 — oblik društva
    kapital_tip      = models.CharField(max_length=10, default='jdoo', choices=KAPITAL_CHOICES)

    # Korak 5 — sjedište
    koristi_konjik   = models.BooleanField(default=True)
    sjediste_adresa  = models.CharField(max_length=200, blank=True, default='')
    sjediste_grad    = models.CharField(max_length=100, blank=True, default='')
    sjediste_zip     = models.CharField(max_length=20, blank=True, default='')

    # Funnel tracking
    current_step     = models.PositiveSmallIntegerField(default=0)
    completed        = models.BooleanField(default=False)
    completed_at     = models.DateTimeField(null=True, blank=True)

    # FK veze
    pending_company  = models.ForeignKey(
        'companies.Company', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='wizard_drafts')
    accounting_firm  = models.ForeignKey(
        'companies.Company', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='wizard_managed_drafts')

    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'partners_wizard_draft'
        ordering = ['-updated_at']
        verbose_name = 'Wizard Draft'
        verbose_name_plural = 'Wizard Drafts'

    def __str__(self):
        return f'{self.firma_ime or "(bez naziva)"} | korak {self.current_step} | {self.created_at:%d.%m.%Y}'

    @property
    def display_name(self):
        return self.firma_ime or f'Draft #{self.pk}'

    @property
    def registration_path(self):
        return 'biljeznik' if self.broj_osnivaca > 3 else 'start'
