import uuid

from django.conf import settings
from django.db import models, DatabaseError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class NKDCode(models.Model):
    """
    NKD 2007 (Nacionalna klasifikacija djelatnosti) — HR verzija NACE Rev.2
    Hijerarhija: Odjeljak (A) → Područje (47) → Razred (47.1) → Podrazred (47.11)
    """

    class Level(models.TextChoices):
        SECTION  = 'section',  'Odjeljak (A–U)'
        DIVISION = 'division', 'Područje (XX)'
        GROUP    = 'group',    'Razred (XX.X)'
        CLASS    = 'class',    'Podrazred (XX.XX)'

    code     = models.CharField(max_length=10, unique=True, db_index=True, verbose_name='Šifra NKD',
                                 help_text='Npr. A, 47, 47.1, 47.11')
    level    = models.CharField(max_length=10, choices=Level.choices, verbose_name='Razina')
    section  = models.CharField(max_length=2, db_index=True, verbose_name='Odjeljak (A–U)')
    name_hr  = models.CharField(max_length=500, verbose_name='Naziv (HR)')
    name_en  = models.CharField(max_length=500, blank=True, verbose_name='Naziv (EN)')
    parent   = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE,
                                  related_name='children', verbose_name='Nadređena kategorija')
    is_active = models.BooleanField(default=True, verbose_name='Aktivna')
    allow_negative_stock = models.BooleanField(
        default=True,
        verbose_name='Dozvoli negativne zalihe',
        help_text='Ako je uklju\u010deno, prodaja je mogu\u0107a i kad je stanje 0.',
    )

    class Meta:
        verbose_name        = 'NKD šifra'
        verbose_name_plural = 'NKD šifarnik'
        ordering            = ['code']

    def __str__(self):
        return f'{self.code} \u2013 {self.name_hr}'


class Company(models.Model):

    class Country(models.TextChoices):
        HR    = 'HR',    _('Hrvatska')
        DE    = 'DE',    _('Njemačka')
        AT    = 'AT',    _('Austrija')
        SI    = 'SI',    _('Slovenija')
        BA    = 'BA',    _('Bosna i Hercegovina')
        RS    = 'RS',    _('Srbija')
        OTHER = 'OTHER', _('Ostalo')

    class BusinessType(models.TextChoices):
        DOO              = 'doo',              _('d.o.o. (Društvo s ograničenom odgovornošću)')
        JDOO             = 'jdoo',             _('j.d.o.o. (Jednostavno d.o.o.)')
        DD               = 'dd',               _('d.d. (Dioničko društvo)')
        OBRT             = 'obrt',             _('Obrt')
        GMBH             = 'gmbh',             _('GmbH')
        AG               = 'ag',               _('AG (Aktiengesellschaft)')
        EINZELUNTERNEHMEN = 'einzelunternehmen', _('Einzelunternehmen')
        OPG              = 'opg',              _('OPG (Obiteljsko poljoprivredno gospodarstvo)')
        UDRUGA           = 'udruga',           _('Udruga')
        ZADRUGA          = 'zadruga',          _('Zadruga')
        USTANOVA         = 'ustanova',         _('Ustanova')
        IZNAJMLJIVAC     = 'iznajmljivac',     _('Iznajmljivač (fizička osoba)')
        OTHER            = 'other',            _('Ostalo')
        ODVJETNIK        = 'odvjetnik',        _('Odvjetnički ured')
        BILJEZNIK        = 'biljeznik',        _('Javni bilježnik')
        DIMNJACARI       = 'dimnjacari',       _('Dimnjačarska služba')

    class Currency(models.TextChoices):
        EUR = 'EUR', 'EUR (Euro)'
        USD = 'USD', 'USD (US Dollar)'
        GBP = 'GBP', 'GBP (British Pound)'
        CHF = 'CHF', 'CHF (Swiss Franc)'
        BAM = 'BAM', 'BAM (Bosanska marka)'
        RSD = 'RSD', 'RSD (Srpski dinar)'

    class FiscalSystem(models.TextChoices):
        HR_FISCALIZATION = 'hr_fiscal', _('HR Fiskalizacija (CIS)')
        DE_GOBD          = 'de_gobd',   _('DE GoBD')
        AT_RKSV          = 'at_rksv',   _('AT RKSV')
        NONE             = 'none',      _('Bez fiskalizacije')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name     = models.CharField(max_length=200, verbose_name=_('Naziv tvrtke'))
    oib      = models.CharField(max_length=50, unique=True, verbose_name='OIB / Steuernummer')
    address  = models.CharField(max_length=255, blank=True, verbose_name=_('Adresa'))
    city     = models.CharField(max_length=100, blank=True, verbose_name=_('Grad'))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_('Poštanski broj'))
    iban     = models.CharField(max_length=34, blank=True, verbose_name='IBAN')
    swift    = models.CharField(max_length=11, blank=True, default='', verbose_name='BIC/SWIFT')

    # International fields
    country       = models.CharField(max_length=10, choices=Country.choices, default=Country.HR, verbose_name=_('Država'))
    business_type = models.CharField(max_length=30, choices=BusinessType.choices, default=BusinessType.DOO, verbose_name=_('Tip poslovnog subjekta'))
    tax_number    = models.CharField(max_length=50, blank=True, verbose_name=_('Porezni broj'), help_text=_('Porezni identifikacijski broj (za strana poduzeća)'))
    vat_id        = models.CharField(max_length=20, blank=True, verbose_name=_('PDV ID / VAT ID'), help_text=_('EU PDV identifikacijski broj (npr. HR12345678901)'))
    currency      = models.CharField(max_length=3, choices=Currency.choices, default=Currency.EUR, verbose_name=_('Valuta'))
    fiscal_system = models.CharField(max_length=20, choices=FiscalSystem.choices, default=FiscalSystem.HR_FISCALIZATION, verbose_name=_('Fiskalni sustav'))

    # Jezik UI za firmu — default za nove korisnike
    UI_LANGUAGE_CHOICES = [
        ('hr', 'Hrvatski'),
        ('de', 'Deutsch'),
        ('en', 'English'),
        ('tr', 'Turkce'),
        ('el', 'Ellinika'),
    ]
    ui_language = models.CharField(
        max_length=5, choices=UI_LANGUAGE_CHOICES, default='hr',
        verbose_name=_('Jezik sucenja'),
        help_text=_('Zadani jezik za nove korisnike ove tvrtke'),
    )
    fiscal_exempt = models.BooleanField(
        default=False, verbose_name=_('Izuzeto od fiskalizacije'),
        help_text=_('Samo za neprofitne udruge izvan sustava PDV-a (NN 133/12). '
                    'Računi se generiraju normalno ali se ne šalju u FINA CIS.'),
    )
    cash_register_limit = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name=_('Blagajnički maksimum (EUR)'),
        help_text=_('Zakonski limit gotovine u blagajni. Za udruge obavezno. Prazno = bez limita.'),
    )

    # PDF predložak
    PDF_TEMPLATE_CHOICES = [
        ('viskovic', 'Visković (Gold/Premium)'),
        ('datev', 'DATEV (Minimalistički)'),
        ('modern', 'Modern (Plavo/Bijeli)'),
    ]
    pdf_template = models.CharField(
        max_length=20, choices=PDF_TEMPLATE_CHOICES, default='viskovic',
        verbose_name=_('PDF predložak'),
        help_text=_('Izgled svih PDF dokumenata (računi, izvještaji, potvrde).'),
    )

    # NKD djelatnost
    nkd_code = models.ForeignKey(
        NKDCode, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('NKD djelatnost'),
        help_text=_('Nacionalna klasifikacija djelatnosti (npr. 56.10 – Restorani)'),
    )

    # Konfiguracija
    is_vat_registered = models.BooleanField(default=True, verbose_name=_('U sustavu PDV-a'))
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    email = models.EmailField(blank=True, verbose_name=_('E-mail'))
    website_url = models.URLField(blank=True, verbose_name=_('Web stranica'))
    # Grosmarkt partner fields
    GROSMARKT_ROLE_CHOICES = [
        ('logistik', 'Logistik-Hub'),
        ('gaertnerei', 'Gärtnerei / Frischware'),
        ('haendler', 'Händler / Großhandel'),
        ('gastro', 'Gastronomie'),
        ('sonstiges', 'Sonstiges'),
    ]
    grosmarkt_partner = models.BooleanField(default=False, verbose_name='Grosmarkt Partner', help_text='Prikazati na grosmarkt-online.eu?')
    grosmarkt_role = models.CharField(max_length=30, blank=True, choices=GROSMARKT_ROLE_CHOICES, verbose_name='Grosmarkt Rolle')
    grosmarkt_description = models.TextField(blank=True, max_length=300, verbose_name='Grosmarkt Beschreibung (DE)', help_text='Kratki opis za grosmarkt-online.eu kartice')
    grosmarkt_show_name = models.BooleanField(default=False, verbose_name='Prikaži naziv firme javno', help_text='Ako False, prikazuje se samo rola (anonimizirano)')

    mobile = models.CharField(max_length=50, blank=True, verbose_name=_('Mobitel'))
    booking_slug  = models.SlugField(max_length=200, unique=True, null=True, blank=True, verbose_name=_('Booking Slug'))
    booking_theme = models.CharField(
        max_length=20,
        choices=[('dark','Tamna'), ('light','Svijetla'), ('standard','Standard (Navy)')],
        default='dark',
        verbose_name=_('Booking tema'),
        help_text=_('Zadana tema za javnu booking stranicu ove kompanije'),
    )
    settings = models.JSONField(default=dict, blank=True, verbose_name=_("Postavke tvrtke"))

    # PDV / USt status
    PDV_STATUS_CHOICES = [
        ('none',             'Nije u sustavu PDV-a'),
        ('obveznik',         'Obveznik PDV-a'),
        ('pausalic',         'Paušalac (HR §90)'),
        ('kleinunternehmer', 'Kleinunternehmer (DE §19 UStG)'),
    ]
    pdv_status = models.CharField(
        max_length=20, choices=PDV_STATUS_CHOICES, default='none',
        verbose_name='PDV status',
    )
    is_kleinunternehmer = models.BooleanField(
        default=False,
        verbose_name='Kleinunternehmer §19 UStG',
        help_text='DE: oslobođen PDV-a prema §19 UStG ako god.prihodi < 22.000 EUR',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Vault / Deaktivacija (Data Vaulting paradigma) ───────────────────────
    is_vaulted = models.BooleanField(
        default=False, verbose_name=_('Zapecacena arhiva'),
        help_text=_('True = firma deaktivirana, podaci zapecaceni. Baza NETAKNUTA.'),
    )
    is_deactivated = models.BooleanField(
        default=False, verbose_name=_('Deaktiviran'),
    )
    deactivation_requested_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Zahtjev za deaktivacijom'),
    )
    deactivation_reason = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name=_('Razlog odlaska'),
    )

    # Geofence / GPS
    latitude = models.FloatField(null=True, blank=True, verbose_name='GPS Latitude')
    longitude = models.FloatField(null=True, blank=True, verbose_name='GPS Longitude')
    geofence_radius = models.PositiveIntegerField(
        default=200, verbose_name='Geofence radius (m)',
        help_text='Maksimalna udaljenost za clock-in (metara)')
    no_show_tolerance_minutes = models.PositiveIntegerField(default=15, verbose_name='Tolerancija kasnjenja (min)')

    is_platform_owner = models.BooleanField(
        default=False,
        verbose_name='Platform Owner',
        help_text='Firma vlasnika platforme – svi moduli otključani bez pretplate',
    )

    # Parent-Child (B2B2B Umbrella)
    umbrella_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='umbrella_children',
        verbose_name='Nadredjena tvrtka (Umbrella)',
    )
    UMBRELLA_RELATION_CHOICES = [
        ('subsidiary', 'Podru\u017enica / Sestrinska firma'),
        ('client', 'Klijent (knjigovodstvo)'),
        ('franchise', 'Fran\u0161iza'),
    ]
    is_umbrella = models.BooleanField(default=False, verbose_name='Umbrella tvrtka')
    umbrella_relation = models.CharField(
        max_length=20, choices=UMBRELLA_RELATION_CHOICES,
        default='client', blank=True,
        verbose_name='Tip veze s umbrella',
    )
    umbrella_max_children = models.PositiveIntegerField(default=0, verbose_name='Max podtvrtki')
    umbrella_monthly_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Umbrella mj. naknada (EUR)',
    )

    # ── Memio.pet / Shelter ──────────────────────────────────────────────────
    is_draft = models.BooleanField(default=False, verbose_name="Draft (nepotpuna registracija)")

    uses_double_entry = models.BooleanField(
        default=False,
        verbose_name='Dvojno knjigovodstvo',
        help_text='Članarina i Donacija auto-kreiraju JournalEntry. '
                  'Obvezno za udruge s prihodima > 30.000 EUR.',
    )

    is_shelter = models.BooleanField(
        default=False,
        verbose_name='Azil / Sklonište za životinje',
        help_text='Označava azil koji prima besplatnu Memio.pet licencu sponzoriranu od strane Udruge No Limit.',
    )
    shelter_sponsor = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Sponzor azila',
        help_text='Npr. "Udruga No Limit" — prikazuje se na javnom profilu ljubimca.',
    )

    # ── GDPR / T&C privola (čl. 6b) ─────────────────────────────────────────
    # SIGURNOST: bez has_signed_tc_consent=True sustav ne smije agregirati
    # institucijske podatke ove firme (FINA, Porezna uprava, Knowledge Graph).
    has_signed_tc_consent = models.BooleanField(
        default=False,
        verbose_name=_('Potpisao T&C (GDPR čl.6b)'),
        help_text=_('Mora biti True da sustav smije agregirati podatke ove firme.'),
    )
    tc_consent_signed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Datum potpisivanja T&C'),
    )
    tc_consent_version = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name=_('Verzija T&C'),
        help_text=_('Npr. v2.1-2026'),
    )

    def save(self, *args, **kwargs):
        if not self.booking_slug and self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            n = 1
            while Company.objects.filter(booking_slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.booking_slug = slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = _('Tvrtka')
        verbose_name_plural = _('Tvrtke')

    def __str__(self):
        return f'{self.name} ({self.oib})'

    # ── Nonprofit helpers ────────────────────────────────────────────
    NONPROFIT_TYPES = {'udruga', 'zadruga', 'ustanova'}

    @property
    def is_nonprofit(self):
        return self.business_type in self.NONPROFIT_TYPES

    @property
    def requires_simplified_accounting(self):
        if not self.is_nonprofit:
            return False
        return self.settings.get('simplified_accounting', True)

    @property
    def nonprofit_fiscal_mode(self):
        if not self.is_nonprofit:
            return 'full'
        return self.settings.get('nonprofit_fiscal_mode', 'commercial_only')


class TaxRate(models.Model):

    class Country(models.TextChoices):
        HR = 'HR', 'Hrvatska'
        DE = 'DE', 'Njemačka'
        AT = 'AT', 'Austrija'
        SI = 'SI', 'Slovenija'

    country     = models.CharField(max_length=10, choices=Country.choices, verbose_name=_('Država'))
    name        = models.CharField(max_length=100, verbose_name=_('Naziv stope'))
    rate        = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_('Stopa (%)'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('Opis'))
    is_default  = models.BooleanField(default=False, verbose_name=_('Zadana stopa'))
    is_active   = models.BooleanField(default=True, verbose_name=_('Aktivna'))

    class Meta:
        verbose_name        = _('Porezna stopa')
        verbose_name_plural = _('Porezne stope')
        ordering            = ['country', '-rate']
        unique_together     = [('country', 'rate')]

    def __str__(self):
        return f'{self.country} \u2013 {self.name} ({self.rate}%)'


class BusinessProfile(models.Model):
    """
    Industrijski profil tvrtke — kontrolira module, cjenik i workflow.

    Primjeri: frizer, mehaničar, građevina, optika, restoran, webshop...
    Vezan 1:1 na Company.
    """
    class ProfileType(models.TextChoices):
        FRIZER        = 'frizer',     _('Frizerski salon')
        MEHANIČAR     = 'mehaničar',  _('Auto mehaničar')
        GRAĐEVINA     = 'gradjevina', _('Građevina / Renovacija')
        OPTIKA        = 'optika',     _('Optika')
        RESTORAN      = 'restoran',   _('Restoran / Caffe bar')
        WEBSHOP       = 'webshop',    _('Online trgovina')
        CONSULTING    = 'consulting', _('Konzalting / IT usluge')
        CUSTOM        = 'custom',     _('Prilagođeno')

    company = models.OneToOneField(
        'Company', on_delete=models.CASCADE,
        related_name='business_profile',
        verbose_name=_('Tvrtka'),
    )
    profile_type = models.CharField(
        max_length=20, choices=ProfileType.choices,
        default=ProfileType.CUSTOM,
        verbose_name=_('Tip profila'),
    )

    # ── Vidljivost modula (nav) ───────────────────────────────────────────────
    module_invoicing    = models.BooleanField(default=True,  verbose_name=_('Fakturiranje'))
    module_pos          = models.BooleanField(default=False, verbose_name=_('POS kasa'))
    module_inventory    = models.BooleanField(default=False, verbose_name=_('Zalihe'))
    module_appointments = models.BooleanField(default=False, verbose_name=_('Termini'))
    module_projects     = models.BooleanField(default=False, verbose_name=_('Projekti'))
    module_worktime     = models.BooleanField(default=False, verbose_name=_('Radni sati'))
    module_finance      = models.BooleanField(default=True,  verbose_name=_('Financije'))
    module_partners     = models.BooleanField(default=True,  verbose_name=_('Partneri'))
    module_documents    = models.BooleanField(default=False, verbose_name=_('Dokumenti'))
    module_webshop      = models.BooleanField(default=False, verbose_name=_('Webshop'))
    module_rental       = models.BooleanField(default=False, verbose_name=_('Najam'))
    module_fitness      = models.BooleanField(default=False, verbose_name=_('Fitness'))

    # ── Workflow tip ──────────────────────────────────────────────────────────
    class WorkflowType(models.TextChoices):
        INVOICE_ONLY  = 'invoice',     _('Samo fakturiranje')
        APPOINTMENT   = 'appointment', _('Termini + fakturiranje')
        WORK_ORDER    = 'work_order',  _('Radni nalozi')
        PROJECT       = 'project',     _('Projektni rad')
        POS           = 'pos',         _('POS kasa (maloprodaja)')

    workflow_type = models.CharField(
        max_length=20, choices=WorkflowType.choices,
        default=WorkflowType.INVOICE_ONLY,
        verbose_name=_('Tip workflowa'),
    )

    # ── Prilagođeni nazivi dokumenata ─────────────────────────────────────────
    offer_label    = models.CharField(max_length=50, default='Ponuda',    verbose_name=_('Naziv ponude'))
    invoice_label  = models.CharField(max_length=50, default='Račun',     verbose_name=_('Naziv računa'))
    workorder_label = models.CharField(max_length=50, default='Radni nalog', verbose_name=_('Naziv radnog naloga'))

    # ── Prilagođena polja na dokumentima (JSON) ───────────────────────────────
    # Format: [{"name": "gradiliste", "label": "Gradilište", "type": "text", "required": false}]
    custom_invoice_fields = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Prilagođena polja na fakturi'),
        help_text=_('JSON lista polja koja se dodaju na formu računa/ponude'),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Poslovni profil')
        verbose_name_plural = _('Poslovni profili')

    def __str__(self):
        return f'{self.company.name} — {self.get_profile_type_display()}'

    @property
    def enabled_modules(self):
        """Vraća listu stringova s nazivima aktivnih modula."""
        return [
            mod for mod in [
                'invoicing', 'pos', 'inventory', 'appointments',
                'projects', 'worktime', 'finance', 'partners',
                'documents', 'webshop', 'rental', 'fitness',
            ]
            if getattr(self, f'module_{mod}', False)
        ]


class ServiceTemplate(models.Model):
    """
    Preddefinirani cjenik / usluge za industrijsku vertikalu.
    Može se kopirati kao startni cjenik za novu tvrtku.
    """
    profile_type = models.CharField(
        max_length=20,
        choices=BusinessProfile.ProfileType.choices,
        verbose_name=_('Tip profila'),
        db_index=True,
    )
    name         = models.CharField(max_length=200, verbose_name=_('Naziv usluge'))
    description  = models.TextField(blank=True, verbose_name=_('Opis'))
    unit         = models.CharField(max_length=20, default='kom', verbose_name=_('Jed. mjera'))
    default_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Zadana cijena (€)'))
    tax_rate     = models.DecimalField(max_digits=5, decimal_places=2, default=25, verbose_name=_('PDV %'))
    category     = models.CharField(max_length=100, blank=True, verbose_name=_('Kategorija'))
    sort_order   = models.PositiveSmallIntegerField(default=0)
    is_active    = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _('Predložak usluge')
        verbose_name_plural = _('Predlošci usluga (cjenik)')
        ordering            = ['profile_type', 'sort_order', 'name']

    def __str__(self):
        return f'[{self.profile_type}] {self.name} — {self.default_price} €'


# ── PODRUŽNICE / BRANCH SUSTAV ────────────────────────────────────────────────

class CompanyBranch(models.Model):
    """Pod-firma / poslovnica unutar matične tvrtke."""

    BRANCH_TYPES = [
        ('optika',      'Optika'),
        ('fitness',     'Fitness centar'),
        ('retail',      'Trgovina'),
        ('accounting',  'Knjigovodstvo'),
        ('restaurant',  'Restoran'),
        ('salon',       'Salon ljepote'),
        ('other',       'Ostalo'),
    ]

    parent_company = models.ForeignKey(
        'Company', on_delete=models.CASCADE,
        related_name='branches', verbose_name='Matična tvrtka',
    )
    name        = models.CharField(max_length=200, verbose_name='Naziv podružnice')
    branch_code = models.CharField(max_length=20, blank=True, verbose_name='Šifra')
    branch_type = models.CharField(
        max_length=20, choices=BRANCH_TYPES, default='other',
        verbose_name='Tip poslovnice',
    )
    address     = models.CharField(max_length=300, blank=True, verbose_name='Adresa')
    city        = models.CharField(max_length=100, blank=True, verbose_name='Grad')
    phone       = models.CharField(max_length=50, blank=True, verbose_name='Telefon')
    email       = models.EmailField(blank=True, verbose_name='E-mail')

    # Module override — empty list = inherit parent company subscription
    active_modules = models.JSONField(
        default=list, blank=True,
        verbose_name='Aktivni moduli (override)',
        help_text='Prazno = nasljeđuje plan matične tvrtke',
    )

    is_active  = models.BooleanField(default=True, verbose_name='Aktivna')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name        = 'Podružnica'
        verbose_name_plural = 'Podružnice'
        ordering            = ['name']
        unique_together     = [('parent_company', 'branch_code')]

    def __str__(self):
        return f'{self.name} ({self.get_branch_type_display()})'

    @property
    def allowed_modules(self):
        """Return set of allowed module names. Checks override first, then parent plan."""
        if self.active_modules:
            return set(self.active_modules)
        try:
            sub = self.parent_company.subscriptions.filter(status='active').first()
            if sub:
                return sub.allowed_modules
        except DatabaseError:
            pass
        return set()

    @property
    def dashboard_url(self):
        mapping = {
            'optika':     '/branches/optika/',
            'fitness':    '/branches/fitness/',
            'retail':     '/branches/retail/',
            'accounting': '/branches/accounting/',
            'restaurant': '/branches/restaurant/',
            'salon':      '/branches/salon/',
        }
        return mapping.get(self.branch_type, '/branches/other/')

    @property
    def badge_color(self):
        mapping = {
            'optika':     '#60a5fa',
            'fitness':    '#4ade80',
            'retail':     '#f97316',
            'accounting': '#a78bfa',
            'restaurant': '#fb923c',
            'salon':      '#f472b6',
        }
        return mapping.get(self.branch_type, '#888')



class OnboardingProgress(models.Model):
    company              = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='onboarding')
    profile_completed    = models.BooleanField(default=False)
    first_partner_added  = models.BooleanField(default=False)
    first_invoice_created = models.BooleanField(default=False)
    bank_account_added   = models.BooleanField(default=False)
    first_item_added     = models.BooleanField(default=False)
    first_employee_added = models.BooleanField(default=False)
    pos_configured       = models.BooleanField(default=False)
    ai_intro_completed   = models.BooleanField(default=False)
    ai_intro_shown       = models.BooleanField(default=False)
    dismissed            = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Onboarding napredak'
        verbose_name_plural = 'Onboarding napredak'

    def __str__(self):
        return f'Onboarding — {self.company}'

    @property
    def completed_steps(self):
        return sum([
            self.profile_completed,
            self.first_partner_added,
            self.first_invoice_created,
            self.bank_account_added,
            self.first_item_added,
            self.first_employee_added,
            self.ai_intro_completed,
        ])

    @property
    def total_steps(self):
        return 7

    @property
    def percent(self):
        return int(self.completed_steps / self.total_steps * 100)



class CompanyPartnership(models.Model):
    """
    Veza između partnera (resellera) i firme kojom upravlja.
    Partner plaća platformi, firma plaća partneru (ili je uključena u paket).
    """
    BILLING_TYPES = [
        ('included',    'Uključeno u paket'),
        ('discounted',  'Povlaštena cijena'),
        ('full',        'Puna cijena'),
        ('free',        'Besplatno'),
    ]

    ACCESS_LEVELS = [
        ('read',  'Samo čitanje'),
        ('full',  'Puni pristup'),
        ('admin', 'Admin pristup'),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner_company  = models.ForeignKey(
        'Company', on_delete=models.PROTECT,
        related_name='managed_companies',
        verbose_name='Partner (reseller)'
    )
    managed_company  = models.ForeignKey(
        'Company', on_delete=models.PROTECT,
        related_name='managing_partners',
        verbose_name='Upravljana firma'
    )
    billing_type     = models.CharField(max_length=20, choices=BILLING_TYPES, default='included')
    monthly_fee      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    access_level     = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='full')
    valid_from       = models.DateField(auto_now_add=True)
    valid_until      = models.DateField(null=True, blank=True)  # null = aktivan
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_partnerships'
    )

    class Meta:
        unique_together = [('partner_company', 'managed_company')]
        verbose_name = 'Partnerstvo'
        verbose_name_plural = 'Partnerstva'
        ordering = ['managed_company__name']

    def __str__(self):
        status = 'aktivan' if not self.valid_until else f'završen {self.valid_until}'
        return f"{self.partner_company.name} → {self.managed_company.name} ({status})"

    @property
    def is_active(self):
        from django.utils import timezone
        return self.valid_until is None or self.valid_until >= timezone.now().date()


class CompanyModuleConfig(models.Model):
    """Per-company module visibility configuration."""
    company = models.OneToOneField('Company', on_delete=models.CASCADE,
                                    related_name='module_config')
    enabled_modules = models.JSONField(default=list, blank=True,
        verbose_name='Aktivni moduli')
    sidebar_order = models.JSONField(default=list, blank=True,
        verbose_name='Redoslijed u sidebaru')
    ai_recommended = models.JSONField(default=list, blank=True,
        verbose_name='AI preporuceni moduli')
    NOTIFICATION_MODE_CHOICES = [
        ('digest', 'Tjedni digest (ponedjeljak 08:00)'),
        ('realtime', 'Real-time notifikacije'),
        ('off', 'Isključeno'),
    ]
    notification_mode = models.CharField(
        max_length=10, choices=NOTIFICATION_MODE_CHOICES, default='digest',
        verbose_name='Način notifikacija',
        help_text='digest=tjedni email, realtime=odmah, off=bez notifikacija',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Konfiguracija modula'

    def __str__(self):
        return f'{self.company.name}: {len(self.enabled_modules)} modula'

    def is_enabled(self, module_id):
        return module_id in self.enabled_modules

    def get_sidebar_modules(self):
        from companies.module_registry import get_module
        result = []
        order = self.sidebar_order or self.enabled_modules
        for mid in order:
            if mid in self.enabled_modules:
                mod = get_module(mid)
                if mod:
                    result.append(mod)
        return result


# ═══════════════════════════════════════════════════
#  KOMITENT MANAGER — KS LIMIT CRM za knjigovodstvo
# ═══════════════════════════════════════════════════

class KomitentStatus(models.TextChoices):
    LEAD       = 'lead',       _('Potencijalni klijent')
    ONBOARDING = 'onboarding', _('U procesu prijema')
    ACTIVE     = 'active',     _('Aktivan')
    PAUSED     = 'paused',     _('Pauziran')
    NOTICE     = 'notice',     _('U otkazu')
    ARCHIVED   = 'archived',   _('Arhiviran (otišao)')
    BLOCKED    = 'blocked',    _('Blokiran (dug)')


class KomitentProfile(models.Model):
    """
    Prošireni profil za upravljanje komitentima knjigovodstvenog servisa.
    Jedna firma = jedan komitent. Ovo je CRM sloj povrh Company modela.
    """
    company = models.OneToOneField('Company', on_delete=models.CASCADE,
                                    related_name='komitent_profile')

    # Status
    status = models.CharField(max_length=20, choices=KomitentStatus.choices,
                              default=KomitentStatus.ACTIVE, verbose_name=_('Status'))

    # Datumi
    client_since = models.DateField(null=True, blank=True, verbose_name=_('Klijent od'))
    notice_date = models.DateField(null=True, blank=True, verbose_name=_('Datum otkaza'))
    left_date = models.DateField(null=True, blank=True, verbose_name=_('Datum odlaska'))
    next_review = models.DateField(null=True, blank=True, verbose_name=_('Sljedeći pregled'))

    # Kontakt
    contact_person = models.CharField(max_length=200, blank=True, verbose_name=_('Kontakt osoba'))
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    contact_email = models.EmailField(blank=True, verbose_name=_('Email'))

    # Ugovor
    contract_type = models.CharField(max_length=30, blank=True, choices=[
        ('mjesecni', _('Mjesečni')),
        ('godisnji', _('Godišnji')),
        ('pausal',   _('Paušal')),
        ('po_satu',  _('Po satu')),
        ('besplatno', _('Besplatno / Pro bono')),
    ], verbose_name=_('Tip ugovora'))
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name=_('Mjesečna naknada (EUR)'))
    notes = models.TextField(blank=True, verbose_name=_('Bilješke'))

    # Kategorija
    category = models.CharField(max_length=30, blank=True, choices=[
        ('obrt',     _('Obrt')),
        ('doo',      _('d.o.o.')),
        ('opg',      _('OPG')),
        ('udruga',   _('Udruga')),
        ('ustanova', _('Ustanova')),
        ('fizicka',  _('Fizička osoba')),
        ('strano',   _('Strano poduzeće')),
    ], verbose_name=_('Kategorija'))

    # Referral
    referred_by = models.CharField(max_length=200, blank=True,
                                    verbose_name=_('Preporuka od'))

    # Synesis legacy
    synesis_imported = models.BooleanField(default=False, verbose_name=_('Uvezeno iz Synesisa'))
    synesis_db_path = models.CharField(max_length=500, blank=True, verbose_name=_('Synesis DB path'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Komitent profil')
        verbose_name_plural = _('Komitent profili')
        ordering = ['company__name']

    def __str__(self):
        return f'{self.company.name} ({self.get_status_display()})'

    @property
    def is_active(self):
        return self.status in ('active', 'onboarding')

    @property
    def is_leaving(self):
        return self.status in ('notice', 'archived')

    @property
    def days_as_client(self):
        if not self.client_since:
            return None
        from datetime import date
        end = self.left_date or date.today()
        return (end - self.client_since).days


class KomitentEvent(models.Model):
    """
    Timeline dogadjaja za komitenta — tko je što promijenio i kada.
    Automatski se kreira na svaku promjenu statusa.
    """
    EVENT_TYPES = [
        ('created',     _('Kreiran')),
        ('activated',   _('Aktiviran')),
        ('paused',      _('Pauziran')),
        ('notice',      _('Otkaz primljen')),
        ('archived',    _('Arhiviran')),
        ('reactivated', _('Reaktiviran')),
        ('blocked',     _('Blokiran')),
        ('plan_change', _('Promjena plana')),
        ('fee_change',  _('Promjena naknade')),
        ('note',        _('Bilješka')),
        ('contact',     _('Kontaktiran')),
        ('meeting',     _('Sastanak')),
        ('document',    _('Dokument')),
        ('import',      _('Uvoz podataka')),
    ]

    profile = models.ForeignKey(KomitentProfile, on_delete=models.CASCADE,
                                 related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField(verbose_name=_('Opis'))
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Komitent događaj')
        verbose_name_plural = _('Komitent događaji')

    def __str__(self):
        return f'{self.profile.company.name} — {self.get_event_type_display()} ({self.created_at.date()})'
# NKD kodovi za vatrogasce — dodati u import ako nedostaju
# 84.25 — Djelatnosti vatrogasnih postrojbi
# 94.99 — Ostale čl. organizacije (DVD koriste ovaj kod)


class WhiteLabelConfig(models.Model):
    """Distributer branding — jedan per agent/distributer."""

    FISCAL_CHOICES = [
        ('HR', 'Hrvatska (FINA)'),
        ('DE', 'Njemačka (KassenSichV)'),
        ('AT', 'Austrija (RKSV)'),
        ('SI', 'Slovenija (FURS)'),
    ]

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='white_label_config',
    )
    brand_name = models.CharField(max_length=80, help_text='Npr. Konjik d.o.o.')
    subdomain = models.SlugField(max_length=50, unique=True,
                                  help_text='Npr. konjik → konjik.limit-connect.com')
    logo_url = models.URLField(blank=True, help_text='URL logotipa')
    primary_color = models.CharField(max_length=7, default='#c9a84c',
                                      help_text='Hex boja npr. #3b82f6')
    tagline = models.CharField(max_length=120, blank=True)
    fiscal_system = models.CharField(max_length=2, choices=FISCAL_CHOICES, default='HR')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('WhiteLabel konfiguracija')
        verbose_name_plural = _('WhiteLabel konfiguracije')

    def __str__(self):
        return f'{self.brand_name} ({self.subdomain})'

    @property
    def full_domain(self):
        return f'{self.subdomain}.limit-connect.com'

    @classmethod
    def get_for_request(cls, request):
        host = request.META.get('HTTP_HOST', '').split(':')[0].lower()
        parts = host.split('.')
        if len(parts) >= 3:
            subdomain = parts[0]
            try:
                return cls.objects.select_related('owner').get(
                    subdomain=subdomain, is_active=True)
            except cls.DoesNotExist:
                pass
        return None


class LicenseToken(models.Model):
    """Licenca za distributer/WhiteLabel — heartbeat + grace period."""
    STATUS_CHOICES = [
        ('active',    'Aktivna'),
        ('grace',     'Grace period'),
        ('suspended', 'Suspendirano'),
        ('cancelled', 'Otkazano'),
    ]

    white_label = models.OneToOneField(
        'WhiteLabelConfig',
        on_delete=models.CASCADE,
        related_name='license_token',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    valid_until = models.DateTimeField()
    grace_until = models.DateTimeField(null=True, blank=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    monthly_amount_eur = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Licencni token')
        verbose_name_plural = _('Licencni tokeni')

    def __str__(self):
        return f'{self.white_label.brand_name} — {self.status} (do {self.valid_until.date()})'

    def is_usable(self):
        from django.utils import timezone
        now = timezone.now()
        if self.status == 'active' and now <= self.valid_until:
            return True
        if self.status == 'grace' and self.grace_until and now <= self.grace_until:
            return True
        return False

    def days_until_expiry(self):
        from django.utils import timezone
        delta = self.valid_until - timezone.now()
        return max(0, delta.days)

    def enter_grace(self):
        from django.utils import timezone
        import datetime
        self.status = 'grace'
        self.grace_until = timezone.now() + datetime.timedelta(days=7)
        self.save(update_fields=['status', 'grace_until', 'updated_at'])

    def suspend(self):
        self.status = 'suspended'
        self.save(update_fields=['status', 'updated_at'])

    def renew(self, months=1):
        from django.utils import timezone
        import datetime
        base = max(self.valid_until, timezone.now())
        self.valid_until = base + datetime.timedelta(days=30 * months)
        self.status = 'active'
        self.grace_until = None
        self.save(update_fields=['status', 'valid_until', 'grace_until', 'updated_at'])


# WORKSPACE — Radni prostor
# ═══════════════════════════════════════════════════════════════════════════
#
# Univerzalni model za SVE tipove radnih prostora:
#   DESK    — fizički stol u uredu (sadašnji stolovi)
#   HOME    — rad od kuće (invalidi, remote radnici, rotacija)
#   REMOTE  — mobilni/digitalni rad bez fiksne adrese
#   PREMISE — POS poslovni prostor (zamjenjuje BusinessPremise u budućnosti)
#
# Svaki radnik ima 1+ workspace. Svaki workspace ima 0+ klijenata.
# Radnik bira klijenta iz svog workspace-a → switch_company → radi.
# ═══════════════════════════════════════════════════════════════════════════

class Workspace(models.Model):
    """
    Radni prostor — fizički ili virtualni kontekst u kojem radnik pristupa klijentima.

    Primjeri:
      - "Stol 1" (DESK) — Ljiljana sjedi u uredu, 14 komitenata
      - "Kuća Ljiljana" (HOME) — ista Ljiljana radi od kuće ponedjeljkom
      - "Remote Marko" (REMOTE) — freelancer, pristupa portalu odakle god
      - "Poslovnica Centar" (PREMISE) — POS blagajna na fizičkoj adresi

    Arhitekturna pravila:
      1. Radnik UVIJEK radi UNUTAR workspace-a
      2. Workspace definira KOJE KLIJENTE radnik vidi
      3. Klik na klijenta → switch_company() → standardni portal flow
      4. Admin raspodjeljuje klijente i radnike na workspace-e
      5. Workspace NIKAD ne ograničava module — to radi CompanyMembership.role
    """

    class Type(models.TextChoices):
        DESK    = 'desk',    'Stol u uredu'
        HOME    = 'home',    'Rad od kuće'
        REMOTE  = 'remote',  'Mobilni / Remote'
        PREMISE = 'premise', 'Poslovni prostor (POS)'

    COLORS = [
        ('#c9a84c', 'Zlatna'),
        ('#22c55e', 'Zelena'),
        ('#3b82f6', 'Plava'),
        ('#f97316', 'Narančasta'),
        ('#ec4899', 'Ružičasta'),
        ('#8b5cf6', 'Ljubičasta'),
        ('#06b6d4', 'Tirkizna'),
        ('#ef4444', 'Crvena'),
        ('#84cc16', 'Vapno'),
        ('#64748b', 'Siva'),
    ]

    # ── Vlasništvo ────────────────────────────────────────────
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='workspaces',
        verbose_name='Matica',
        help_text='Firma kojoj workspace pripada (npr. Konjik d.o.o.)',
    )

    # ── Identifikacija ───────────────────────────────────────
    name = models.CharField(
        max_length=100,
        verbose_name='Naziv',
        help_text='Npr. "Stol 1", "Home Office Ljiljana", "Poslovnica Centar"',
    )
    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        default=Type.DESK,
        verbose_name='Tip',
    )
    color = models.CharField(
        max_length=20,
        choices=COLORS,
        default='#c9a84c',
        verbose_name='Boja',
    )
    position = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Redoslijed',
        help_text='Za sortiranje u admin prikazu',
    )

    # ── Tko radi ──────────────────────────────────────────────
    workers = models.ManyToManyField(
        'auth.User',
        blank=True,
        related_name='workspaces',
        verbose_name='Radnici',
        help_text='Osobe koje rade u ovom prostoru',
    )

    # ── Na čemu se radi ───────────────────────────────────────
    clients = models.ManyToManyField(
        'Company',
        blank=True,
        related_name='workspace_assignments',
        verbose_name='Klijenti',
        help_text='Firme/komitenti dodijeljeni ovom prostoru',
    )

    # ── Lokacija (opcionalno) ─────────────────────────────────
    address = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Adresa',
        help_text='Fizička adresa (za HOME = kućna adresa, za PREMISE = adresa poslovnice)',
    )
    city = models.CharField(max_length=100, blank=True, verbose_name='Grad')
    zip_code = models.CharField(max_length=10, blank=True, verbose_name='Poštanski broj')

    # ── Vremensko ograničenje (studenti, volonteri) ───────────
    valid_from = models.DateField(
        null=True, blank=True,
        verbose_name='Aktivan od',
        help_text='Prazno = odmah aktivan',
    )
    valid_until = models.DateField(
        null=True, blank=True,
        verbose_name='Aktivan do',
        help_text='Prazno = trajno. Za studente/volontere postaviti datum isteka.',
    )

    # ── Status ────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, verbose_name='Aktivan')
    notes = models.TextField(blank=True, verbose_name='Napomena')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'name']
        verbose_name = 'Radni prostor'
        verbose_name_plural = 'Radni prostori'

    def __str__(self):
        workers = ', '.join(
            w.get_full_name() or w.username
            for w in self.workers.all()[:3]
        )
        return f'{self.name} ({workers or "—"})'

    @property
    def client_count(self):
        return self.clients.count()

    @property
    def worker_count(self):
        return self.workers.count()

    @property
    def is_valid(self):
        """Provjeri je li workspace trenutno valjan (vremenski)."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return self.is_active

    @property
    def type_icon(self):
        icons = {
            'desk': 'fas fa-desktop',
            'home': 'fas fa-home',
            'remote': 'fas fa-wifi',
            'premise': 'fas fa-store',
        }
        return icons.get(self.type, 'fas fa-briefcase')

    @classmethod
    def get_for_user(cls, user, company=None):
        """Dohvati sve aktivne workspace-e za korisnika."""
        from django.utils import timezone
        today = timezone.now().date()
        qs = cls.objects.filter(
            workers=user,
            is_active=True,
        ).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=today),
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=today),
        ).prefetch_related('clients', 'workers')

        if company:
            qs = qs.filter(company=company)
        return qs

    @classmethod
    def get_clients_for_user(cls, user, company=None):
        """Dohvati sve klijente kojima korisnik ima pristup kroz workspace-e."""
        workspaces = cls.get_for_user(user, company)
        client_ids = set()
        for ws in workspaces:
            client_ids.update(ws.clients.values_list('id', flat=True))
        return Company.objects.filter(id__in=client_ids).order_by('name')
